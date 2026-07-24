#!/usr/bin/env python3
"""Local one-screen workflow for adding an Aimy gacha from screenshots.

User flow:
1. Launch this app (double-click ガチャ追加.command or npm run add-gacha)
2. Drop screenshots into the browser
3. Confirm/edit title and detected items
4. Press publish; build, commit, and push run automatically

No cloud AI or paid API is used. Japanese OCR uses Apple's Vision framework on macOS.
"""

from __future__ import annotations

import hashlib
import html
import io
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import urllib.parse
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from PIL import Image, ImageChops, ImageStat

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
WORKSPACE_ROOT = SCRIPT_DIR / "workspace"
HTML_PATH = SCRIPT_DIR / "add_gacha.html"
SLUGIFY_SCRIPT = SCRIPT_DIR / "slugify.mjs"
NATIVE_OCR_SOURCE = SCRIPT_DIR / "macos_ocr.m"
NATIVE_OCR_BIN = SCRIPT_DIR / ".bin" / "aimy-ocr"
INBOX_DIR = PROJECT_ROOT / "ガチャスクショ投入"
INBOX_ARCHIVE_DIR = INBOX_DIR / "処理済み"
INBOX_POLL_SECONDS = 1.0
INBOX_STABLE_SECONDS = 6.0

sys.path.insert(0, str(SCRIPT_DIR))
from detect_cards import _compute_dhash, _detect_boxes, _estimate_rarity, _hamming_distance  # noqa: E402
from export_cards import _crop_without_stretch  # noqa: E402

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
CATEGORY_ALIASES = {
    "衣装": "衣装",
    "目": "目",
    "髪型": "髪型",
    "髪飾り": "髪飾り",
    "耳": "耳",
    "耳飾り": "耳飾り",
    "背景": "背景",
    "チェキフレーム": "チェキフレーム",
    "メイク": "メイク",
    "めがね": "めがね",
    "あたま": "あたま",
    "イベント": "イベント",
}
CATEGORY_ORDER = list(CATEGORY_ALIASES.values())
BOILERPLATE_WORDS = (
    "ガチャ詳細",
    "ラインナップ紹介",
    "アイミーボックスで",
    "開催期間",
    "運営事務局",
    "イベントを入手",
    "撮影が可能",
)

_INBOX_LOCK = threading.Lock()
_INBOX_RETRY_EVENT = threading.Event()
_INBOX_STATE: Dict[str, Any] = {
    "status": "waiting",
    "message": "スクショ待ちです。",
    "sessionId": "",
    "draft": None,
    "files": [],
    "signature": "",
    "updatedAt": "",
    "folder": str(INBOX_DIR),
}


@dataclass
class OCRLine:
    text: str
    confidence: float
    box: Tuple[float, float, float, float]

    @property
    def left(self) -> float:
        return self.box[0]

    @property
    def top(self) -> float:
        return self.box[1]

    @property
    def right(self) -> float:
        return self.box[2]

    @property
    def bottom(self) -> float:
        return self.box[3]

    @property
    def center_y(self) -> float:
        return (self.top + self.bottom) / 2.0


class AppError(RuntimeError):
    pass


def _set_inbox_state(**changes: Any) -> None:
    with _INBOX_LOCK:
        _INBOX_STATE.update(changes)
        _INBOX_STATE["updatedAt"] = datetime.now().isoformat(timespec="seconds")


def _get_inbox_state() -> Dict[str, Any]:
    with _INBOX_LOCK:
        return dict(_INBOX_STATE)


def _inbox_images() -> List[Path]:
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(
        [
            path
            for path in INBOX_DIR.iterdir()
            if path.is_file()
            and not path.name.startswith(".")
            and path.suffix.lower() in IMAGE_EXTS
        ],
        key=lambda path: _natural_key(path.name),
    )


def _inbox_signature(paths: Sequence[Path]) -> str:
    parts = []
    for path in paths:
        stat = path.stat()
        parts.append(f"{path.name}:{stat.st_size}:{stat.st_mtime_ns}")
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()


def _copy_inbox_to_session(paths: Sequence[Path], signature: str) -> Tuple[str, Dict[str, Any]]:
    session_id = _new_session_id()
    session_dir = _session_dir(session_id)
    upload_dir = session_dir / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    copied_names: List[str] = []
    used_names: set[str] = set()
    source_records: List[Dict[str, Any]] = []
    for index, source in enumerate(paths, start=1):
        filename = _safe_filename(source.name)
        if filename in used_names:
            filename = f"{index:02d}-{filename}"
        used_names.add(filename)
        target = upload_dir / filename
        shutil.copy2(source, target)
        copied_names.append(filename)
        stat = source.stat()
        source_records.append(
            {
                "path": str(source),
                "name": source.name,
                "size": stat.st_size,
                "mtimeNs": stat.st_mtime_ns,
            }
        )

    source_info = {
        "signature": signature,
        "files": source_records,
        "copiedNames": copied_names,
    }
    (session_dir / "inbox-source.json").write_text(
        json.dumps(source_info, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    draft = process_session(session_id)
    return session_id, draft


def _archive_inbox_source(session_id: str, slug: str) -> Optional[str]:
    source_path = _session_dir(session_id) / "inbox-source.json"
    if not source_path.exists():
        return None

    info = json.loads(source_path.read_text(encoding="utf-8"))
    archive_dir = INBOX_ARCHIVE_DIR / f"{datetime.now():%Y%m%d-%H%M%S}-{slug}"
    archive_dir.mkdir(parents=True, exist_ok=True)

    moved = 0
    for record in info.get("files", []):
        source = Path(str(record.get("path", "")))
        try:
            source.resolve().relative_to(INBOX_DIR.resolve())
        except (ValueError, OSError):
            continue
        if not source.is_file():
            continue
        target = archive_dir / source.name
        if target.exists():
            target = archive_dir / f"{moved + 1:02d}-{source.name}"
        shutil.move(str(source), str(target))
        moved += 1

    (archive_dir / "公開済み.txt").write_text(
        f"slug: {slug}\n公開日時: {datetime.now().isoformat(timespec='seconds')}\n",
        encoding="utf-8",
    )
    _set_inbox_state(
        status="published",
        message=f"公開完了。元スクショ{moved}枚を処理済みへ移動しました。",
        sessionId=session_id,
        draft=None,
        files=[],
        signature="",
        archivePath=str(archive_dir),
    )
    return str(archive_dir)


def _watch_inbox() -> None:
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    INBOX_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    last_signature = ""
    stable_since = 0.0
    failed_signature = ""

    while True:
        try:
            paths = _inbox_images()
            if not paths:
                last_signature = ""
                stable_since = 0.0
                state = _get_inbox_state()
                if state.get("status") not in {"processing", "ready"}:
                    _set_inbox_state(
                        status="waiting",
                        message="スクショ待ちです。このフォルダへまとめて入れてください。",
                        files=[],
                        signature="",
                    )
                time.sleep(INBOX_POLL_SECONDS)
                continue

            signature = _inbox_signature(paths)
            names = [path.name for path in paths]
            state = _get_inbox_state()

            if state.get("status") in {"processing", "ready"}:
                time.sleep(INBOX_POLL_SECONDS)
                continue

            retry_requested = _INBOX_RETRY_EVENT.is_set()
            if retry_requested:
                _INBOX_RETRY_EVENT.clear()
                failed_signature = ""
                stable_since = 0.0

            if signature != last_signature:
                last_signature = signature
                stable_since = time.monotonic()
                _set_inbox_state(
                    status="settling",
                    message=f"{len(paths)}枚を検出しました。コピー完了を待っています…",
                    files=names,
                    signature=signature,
                    draft=None,
                    sessionId="",
                )
                time.sleep(INBOX_POLL_SECONDS)
                continue

            if signature == failed_signature and not retry_requested:
                time.sleep(INBOX_POLL_SECONDS)
                continue

            elapsed = time.monotonic() - stable_since
            if elapsed < INBOX_STABLE_SECONDS:
                remaining = max(1, int(INBOX_STABLE_SECONDS - elapsed + 0.999))
                _set_inbox_state(
                    status="settling",
                    message=f"{len(paths)}枚を検出。あと約{remaining}秒、追加を待ちます…",
                    files=names,
                    signature=signature,
                )
                time.sleep(INBOX_POLL_SECONDS)
                continue

            _set_inbox_state(
                status="processing",
                message=f"{len(paths)}枚からタイトル・バナー・アイテムを読み取り中です…",
                files=names,
                signature=signature,
                draft=None,
                sessionId="",
            )
            try:
                session_id, draft = _copy_inbox_to_session(paths, signature)
            except Exception as ex:
                failed_signature = signature
                traceback.print_exc()
                _set_inbox_state(
                    status="error",
                    message=str(ex),
                    files=names,
                    signature=signature,
                    sessionId="",
                    draft=None,
                )
            else:
                failed_signature = ""
                _set_inbox_state(
                    status="ready",
                    message="自動生成が完了しました。タイトル・バナー・アイテムを確認してください。",
                    files=names,
                    signature=signature,
                    sessionId=session_id,
                    draft=draft,
                )
        except Exception as ex:
            traceback.print_exc()
            _set_inbox_state(status="error", message=f"フォルダ監視エラー: {ex}")
        time.sleep(INBOX_POLL_SECONDS)


def _json_dumps(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False).encode("utf-8")


def _natural_key(value: str) -> List[Any]:
    return [int(x) if x.isdigit() else x.lower() for x in re.split(r"(\d+)", value)]


def _capture_datetime(path: Path) -> Optional[datetime]:
    """Read the screenshot capture time embedded by iPhone/Photos.

    Photos-exported JPEGs have random UUID filenames, so filename order is not
    page order.  EXIF DateTimeOriginal/DateTime is the reliable top-to-bottom
    order because the screenshots are taken while scrolling down the page.
    """
    try:
        with Image.open(path) as image:
            exif = image.getexif()
            for tag in (36867, 36868, 306):  # DateTimeOriginal, DateTimeDigitized, DateTime
                raw = exif.get(tag)
                if not raw:
                    continue
                value = str(raw).strip().replace("-", ":", 2)
                for fmt in ("%Y:%m:%d %H:%M:%S", "%Y:%m:%d %H:%M:%S%z"):
                    try:
                        return datetime.strptime(value, fmt).replace(tzinfo=None)
                    except ValueError:
                        pass
    except Exception:
        pass
    return None


def _screenshot_sort_key(path: Path) -> Tuple[int, Any, int, List[Any]]:
    captured = _capture_datetime(path)
    if captured is not None:
        return (0, captured, path.stat().st_mtime_ns, _natural_key(path.name))
    # PNG screenshots usually keep sequential IMG_#### names.  For other files,
    # upload mtime preserves the order selected in the browser.
    return (1, datetime.min, path.stat().st_mtime_ns, _natural_key(path.name))


def _page_top_score(lines: Sequence[OCRLine]) -> int:
    text = _normalized_text("".join(line.text for line in lines))
    score = 0
    if "アイミーボックス" in text:
        score += 100
    if "開催期間" in text:
        score += 80
    if "登場" in text:
        score += 50
    if "ラインナップ紹介" in text:
        score += 30
    if re.search(r"20\d{2}[/年.]\d{1,2}", text):
        score += 20
    if "ガチャ詳細" in text:
        score += 5
    return score


def _order_screenshots(
    screenshots: Sequence[Path], ocr_by_file: Dict[str, List[OCRLine]]
) -> List[Path]:
    """Return screenshots in vertical page order.

    First use EXIF capture time.  Then make sure the page containing the gacha
    title/period is first, even when a file picker returns an unexpected order.
    """
    ordered = sorted(screenshots, key=_screenshot_sort_key)
    if len(ordered) <= 1:
        return ordered
    scores = [_page_top_score(ocr_by_file.get(path.name, [])) for path in ordered]
    best_index = max(range(len(ordered)), key=lambda index: scores[index])
    if scores[best_index] >= 80 and best_index != 0:
        ordered.insert(0, ordered.pop(best_index))
    return ordered


def _safe_filename(name: str) -> str:
    name = Path(name).name
    cleaned = re.sub(r"[^0-9A-Za-z._-]+", "_", name)
    if not cleaned:
        cleaned = f"image-{int(time.time())}.png"
    return cleaned


def _session_dir(session_id: str) -> Path:
    if not re.fullmatch(r"[a-f0-9]{12,40}", session_id):
        raise AppError("不正な作業IDです。")
    return WORKSPACE_ROOT / session_id


def _new_session_id() -> str:
    return hashlib.sha1(f"{time.time_ns()}-{os.getpid()}".encode()).hexdigest()[:16]


def _compile_native_ocr() -> Path:
    if platform.system() != "Darwin":
        raise AppError("Apple Vision OCR はmacOSでのみ使用できます。")
    if not NATIVE_OCR_SOURCE.exists():
        raise AppError(f"OCRソースがありません: {NATIVE_OCR_SOURCE}")

    NATIVE_OCR_BIN.parent.mkdir(parents=True, exist_ok=True)
    needs_build = (
        not NATIVE_OCR_BIN.exists()
        or NATIVE_OCR_BIN.stat().st_mtime < NATIVE_OCR_SOURCE.stat().st_mtime
    )
    if not needs_build:
        return NATIVE_OCR_BIN

    clang = shutil.which("clang") or "/usr/bin/clang"
    proc = subprocess.run(
        [
            clang,
            "-fobjc-arc",
            "-fblocks",
            "-framework",
            "Foundation",
            "-framework",
            "Vision",
            "-framework",
            "ImageIO",
            "-framework",
            "CoreGraphics",
            "-framework",
            "CoreServices",
            str(NATIVE_OCR_SOURCE),
            "-o",
            str(NATIVE_OCR_BIN),
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()
        raise AppError(
            "macOS標準OCRの準備に失敗しました。Xcode Command Line Toolsを確認してください。\n"
            + detail
        )
    return NATIVE_OCR_BIN


def _run_native_ocr(image_path: Path) -> List[OCRLine]:
    binary = _compile_native_ocr()
    proc = subprocess.run(
        [str(binary), str(image_path)],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        raise AppError(f"OCRに失敗しました: {image_path.name}\n{proc.stderr.strip()}")
    obj = json.loads(proc.stdout)
    return [
        OCRLine(
            text=str(x.get("text", "")).strip(),
            confidence=float(x.get("confidence", 0.0)),
            box=tuple(float(v) for v in x.get("box", [0, 0, 0, 0])),
        )
        for x in obj.get("lines", [])
        if str(x.get("text", "")).strip()
    ]


def _run_tesseract_ocr(image_path: Path) -> List[OCRLine]:
    """Development fallback for non-macOS. Not required by the user's Mac."""
    tesseract = shutil.which("tesseract")
    if not tesseract:
        raise AppError("OCRエンジンが見つかりません。macOSで実行してください。")
    proc = subprocess.run(
        [tesseract, str(image_path), "stdout", "-l", "jpn+eng", "--psm", "11", "tsv"],
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        raise AppError(f"OCRに失敗しました: {proc.stderr.strip()}")

    groups: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = {}
    rows = proc.stdout.splitlines()
    if not rows:
        return []
    headers = rows[0].split("\t")
    for row in rows[1:]:
        parts = row.split("\t")
        if len(parts) != len(headers):
            continue
        item = dict(zip(headers, parts))
        text = item.get("text", "").strip()
        try:
            conf = float(item.get("conf", "-1"))
        except ValueError:
            conf = -1
        if not text or conf < 0:
            continue
        key = (item.get("block_num", ""), item.get("par_num", ""), item.get("line_num", ""))
        groups.setdefault(key, []).append(
            {
                "text": text,
                "conf": conf / 100.0,
                "left": int(item.get("left", "0")),
                "top": int(item.get("top", "0")),
                "width": int(item.get("width", "0")),
                "height": int(item.get("height", "0")),
            }
        )

    lines: List[OCRLine] = []
    for words in groups.values():
        words.sort(key=lambda x: x["left"])
        text = "".join(x["text"] for x in words)
        left = min(x["left"] for x in words)
        top = min(x["top"] for x in words)
        right = max(x["left"] + x["width"] for x in words)
        bottom = max(x["top"] + x["height"] for x in words)
        confidence = sum(x["conf"] for x in words) / max(1, len(words))
        lines.append(OCRLine(text=text, confidence=confidence, box=(left, top, right, bottom)))
    return sorted(lines, key=lambda x: (x.top, x.left))


def run_ocr(image_path: Path) -> List[OCRLine]:
    if platform.system() == "Darwin":
        return _run_native_ocr(image_path)
    return _run_tesseract_ocr(image_path)


def _crop_item_for_output(image: Image.Image, box: Tuple[int, int, int, int]) -> Image.Image:
    """Crop a detected card and normalize it to the site's 192x192 item size."""
    crop = image.crop(box).convert("RGBA")
    if crop.size != (192, 192):
        crop = crop.resize((192, 192), Image.Resampling.LANCZOS)
    return crop


def _normalized_text(text: str) -> str:
    text = text.replace(" ", "").replace("　", "")
    text = text.replace("（", "(").replace("）", ")")
    text = text.replace("『", "「").replace("』", "」")
    return re.sub(r"[\s|｜]", "", text)


def _clean_item_name(text: str) -> str:
    value = _normalized_text(text)
    value = re.sub(r"^(SSR|SR|NR|R|N)+", "", value, flags=re.IGNORECASE)
    value = value.strip("・:：-—_.,。")
    value = re.sub(r"\(([^)]*)\)", lambda m: f"({m.group(1).strip()})", value)
    return value


def _is_probable_item_name(text: str) -> bool:
    value = _clean_item_name(text)
    if len(value) < 2:
        return False
    if any(word in value for word in BOILERPLATE_WORDS):
        return False
    if value in CATEGORY_ALIASES:
        return False
    if re.fullmatch(r"(?:SSR|SR|R|N)+", value, flags=re.IGNORECASE):
        return False
    if re.fullmatch(r"[0-9/():~〜年月日時分金月火水木土日]+", value):
        return False
    return True


def _detect_category(text: str) -> Optional[str]:
    value = _normalized_text(text)
    # Longer labels first so 耳 does not win over 耳飾り.
    for alias in sorted(CATEGORY_ALIASES, key=len, reverse=True):
        if value == alias or (len(value) <= len(alias) + 2 and alias in value):
            return CATEGORY_ALIASES[alias]
    return None


def _merge_name_lines(lines: Sequence[OCRLine], card_box: Tuple[int, int, int, int]) -> Tuple[str, float]:
    _, top, right, bottom = card_box
    center = (top + bottom) / 2.0
    possible = [
        line
        for line in lines
        if line.left >= right + 8
        and top - 45 <= line.center_y <= bottom + 45
        and _is_probable_item_name(line.text)
    ]
    if not possible:
        return "", 0.0

    # Group close OCR lines. A wrapped item name can occupy two nearby lines.
    possible.sort(key=lambda x: (x.center_y, x.left))
    clusters: List[List[OCRLine]] = []
    for line in possible:
        if not clusters or abs(line.center_y - clusters[-1][-1].center_y) > 55:
            clusters.append([line])
        else:
            clusters[-1].append(line)

    def cluster_score(cluster: Sequence[OCRLine]) -> float:
        cy = sum(x.center_y for x in cluster) / len(cluster)
        conf = sum(x.confidence for x in cluster) / len(cluster)
        return abs(cy - center) - conf * 35.0

    chosen = min(clusters, key=cluster_score)
    chosen = sorted(chosen, key=lambda x: (x.top, x.left))
    text = "".join(_clean_item_name(x.text) for x in chosen)
    confidence = sum(x.confidence for x in chosen) / max(1, len(chosen))
    return _clean_item_name(text), confidence


BANNER_LAYOUTS: Tuple[Tuple[str, float, float, float], ...] = (
    # Horizontal geometry learned from the existing hand-cropped banners.
    # The vertical position varies by title wrapping, so it is searched.
    ("current-inset", 96 / 1179, 1083 / 1179, 987 / 185),
    ("legacy-wide", 52 / 1179, 1178 / 1179, 1126 / 202),
)


def _banner_score(crop: Image.Image) -> float:
    """Score whether a small preview crop is a real Aimy banner."""
    preview = crop.convert("RGB")
    pixels = list(preview.getdata())
    total = max(1, len(pixels))

    colourful = 0
    nonwhite = 0
    for r, g, b in pixels:
        mx = max(r, g, b)
        mn = min(r, g, b)
        if mx - mn > 24 and mx > 90:
            colourful += 1
        if mn < 242:
            nonwhite += 1

    covered_columns = 0
    for x in range(preview.width):
        hits = 0
        for y in range(preview.height):
            r, g, b = preview.getpixel((x, y))
            if max(r, g, b) - min(r, g, b) > 24 and max(r, g, b) > 90:
                hits += 1
        if hits / max(1, preview.height) >= 0.14:
            covered_columns += 1

    colourful_ratio = colourful / total
    nonwhite_ratio = nonwhite / total
    width_coverage = covered_columns / max(1, preview.width)
    return colourful_ratio * 2.4 + nonwhite_ratio * 1.2 + width_coverage * 2.8


def _best_banner_in_image(
    image: Image.Image, lines: Sequence[OCRLine],
) -> Optional[Tuple[float, str, Tuple[int, int, int, int]]]:
    rgb = image.convert("RGB")
    width, height = rgb.size

    # Search on one small copy, then map the winning coordinates back to the
    # original image. This keeps processing fast even for 1179x2556 PNGs.
    preview_width = min(160, width)
    scale = preview_width / max(1, width)
    preview_height = max(1, round(height * scale))
    preview = rgb.resize((preview_width, preview_height), Image.Resampling.BILINEAR)

    best: Optional[Tuple[float, str, Tuple[int, int, int, int]]] = None
    for layout_name, left_ratio, right_ratio, aspect in BANNER_LAYOUTS:
        left_p = max(0, round(preview_width * left_ratio))
        right_p = min(preview_width, round(preview_width * right_ratio))
        crop_width_p = right_p - left_p
        crop_height_p = max(4, round(crop_width_p / aspect))
        date_lines = sorted(
            [line for line in lines if _parse_datetime(line.text)],
            key=lambda line: (line.top, line.left),
        )
        if len(date_lines) >= 2:
            # In Aimy detail pages the real banner sits between the first date
            # shown near the title and the following "開催期間" dates.
            original_top = max(0.0, date_lines[0].bottom - width * 0.01)
            original_bottom = min(
                float(height - round(crop_width_p / max(scale, 1e-9) / aspect)),
                date_lines[1].top + width * 0.015,
            )
            search_top_p = max(0, round(original_top * scale))
            search_bottom_p = min(
                preview_height - crop_height_p,
                round(original_bottom * scale),
            )
        else:
            search_top_p = max(0, round(preview_height * 0.16))
            search_bottom_p = min(preview_height - crop_height_p, round(preview_height * 0.43))
        if search_bottom_p < search_top_p:
            continue

        for top_p in range(search_top_p, search_bottom_p + 1):
            preview_box = (left_p, top_p, right_p, top_p + crop_height_p)
            score = _banner_score(preview.crop(preview_box))
            left = max(0, round(width * left_ratio))
            right = min(width, round(width * right_ratio))
            crop_height = max(1, round((right - left) / aspect))
            top = max(0, min(height - crop_height, round(top_p / scale)))
            bottom = top + crop_height
            candidate = (score, layout_name, (left, top, right, bottom))
            if best is None or candidate[0] > best[0]:
                best = candidate

    return best


def _extract_banner(
    screenshots: Sequence[Path],
    ocr_by_file: Dict[str, List[OCRLine]],
    output_path: Path,
) -> Dict[str, Any]:
    best: Optional[Tuple[float, Path, str, Tuple[int, int, int, int], float, int]] = None
    for source in screenshots:
        with Image.open(source) as image:
            candidate = _best_banner_in_image(image, ocr_by_file.get(source.name, []))
        if candidate is None:
            continue
        score, layout_name, box = candidate
        page_score = _page_top_score(ocr_by_file.get(source.name, []))
        combined_score = score + min(page_score, 200) / 40.0
        combined = (combined_score, source, layout_name, box, score, page_score)
        if best is None or combined[0] > best[0]:
            best = combined

    if best is None or best[0] < 2.2:
        raise AppError("ガチャバナーをスクリーンショットから見つけられませんでした。")

    combined_score, source, layout_name, box, visual_score, page_score = best
    with Image.open(source) as image:
        banner = image.convert("RGB").crop(box)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        banner.save(output_path, "JPEG", quality=95, optimize=True)
    return {
        "source": source.name,
        "box": list(box),
        "size": list(banner.size),
        "template": layout_name,
        "score": round(visual_score, 3),
        "pageScore": page_score,
    }


def _parse_datetime(text: str) -> Optional[str]:
    value = _normalized_text(text)
    value = value.replace("年", "/").replace("月", "/").replace("日", " ")
    value = value.replace("．", ".").replace("：", ":")
    match = re.search(
        r"(20\d{2})[/.\-](\d{1,2})[/.\-](\d{1,2})(?:\([^)]*\))?\s*(\d{1,2})[:.](\d{2})",
        value,
    )
    if not match:
        return None
    year, month, day, hour, minute = (int(x) for x in match.groups())
    return f"{year:04d}/{month:02d}/{day:02d} {hour:02d}:{minute:02d}"


def _extract_metadata(all_lines: Sequence[OCRLine]) -> Dict[str, str]:
    texts = [line.text.strip() for line in sorted(all_lines, key=lambda x: (x.top, x.left)) if line.text.strip()]
    joined = "\n".join(texts)
    compact = _normalized_text(joined)

    title = ""
    title_patterns = [
        r"[「『]([^」』]{2,80})[」』](?:登場|がスタート|スタート)",
        r"アイミーボックス[「『]([^」』]{2,80})[」』]",
    ]
    for pattern in title_patterns:
        match = re.search(pattern, compact)
        if match:
            title = match.group(1).strip()
            break
    if not title:
        for text in texts:
            if "登場" in text and len(text) <= 100:
                candidate = re.sub(r"登場.*$", "", _normalized_text(text)).strip("「」『』!！")
                candidate = re.sub(r"^アイミーボックス", "", candidate)
                if len(candidate) >= 2:
                    title = candidate
                    break

    unique_dates: List[str] = []
    for text in texts:
        dt = _parse_datetime(text)
        if dt and dt not in unique_dates:
            unique_dates.append(dt)
    start_date = unique_dates[0] if unique_dates else ""
    end_date = unique_dates[1] if len(unique_dates) >= 2 else ""

    gacha_type = "アイミーボックス" if "アイミーボックス" in compact else "ガチャ"
    return {
        "title": title,
        "type": gacha_type,
        "startDate": start_date,
        "endDate": end_date,
    }


def _slugify(title: str, start_date: str) -> str:
    result = ""
    if title and SLUGIFY_SCRIPT.is_file():
        try:
            proc = subprocess.run(
                ["node", str(SLUGIFY_SCRIPT), title],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                timeout=30,
            )
            if proc.returncode == 0:
                result = proc.stdout.strip()
        except Exception:
            result = ""
    if not result:
        date_match = re.search(r"(20\d{2})/(\d{2})/(\d{2})", start_date)
        date_part = "".join(date_match.groups()) if date_match else datetime.now().strftime("%Y%m%d")
        digest = hashlib.sha1(title.encode("utf-8")).hexdigest()[:6] if title else "new"
        result = f"gacha-{date_part}-{digest}"
    result = re.sub(r"[^a-z0-9-]+", "-", result.lower()).strip("-")
    result = re.sub(r"-+", "-", result)
    if not result:
        result = f"gacha-{datetime.now():%Y%m%d-%H%M%S}"
    return result[:80]


def _normalize_manual_item_image(data: bytes) -> Image.Image:
    if not data or len(data) > 40_000_000:
        raise AppError("追加画像のサイズが不正です。")
    try:
        with Image.open(io.BytesIO(data)) as source:
            image = source.convert("RGBA")
    except Exception as ex:
        raise AppError("追加画像を読み込めません。") from ex

    image.thumbnail((192, 192), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (192, 192), (0, 0, 0, 0))
    left = (192 - image.width) // 2
    top = (192 - image.height) // 2
    canvas.paste(image, (left, top), image)
    return canvas


def add_manual_items(session_id: str, position: int, payloads: Sequence[Tuple[str, bytes]]) -> Dict[str, Any]:
    session_dir = _session_dir(session_id)
    draft_path = session_dir / "draft.json"
    items_dir = session_dir / "generated" / "items"
    if not draft_path.is_file() or not items_dir.is_dir():
        raise AppError("追加先の処理データがありません。スクショをもう一度処理してください。")
    if not payloads:
        raise AppError("追加する画像を選択してください。")

    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    items = list(draft.get("items", []))
    insert_at = max(0, min(len(items), position - 1))
    added_count = len(payloads)

    for old_index in range(len(items), insert_at, -1):
        old_path = items_dir / f"{old_index:02d}.png"
        new_path = items_dir / f"{old_index + added_count:02d}.png"
        if old_path.is_file():
            old_path.replace(new_path)

    additions = []
    for offset, (filename, data) in enumerate(payloads):
        item_index = insert_at + offset + 1
        output = _normalize_manual_item_image(data)
        output.save(items_dir / f"{item_index:02d}.png", "PNG")
        additions.append(
            {
                "index": item_index,
                "sourceImageIndex": item_index,
                "name": "",
                "rarity": "SR",
                "category": "未分類",
                "confidence": 0,
                "source": f"manual:{_safe_filename(filename)}",
                "box": [0, 0, output.width, output.height],
                "imageUrl": f"/workspace/{session_id}/generated/items/{item_index:02d}.png",
            }
        )

    items[insert_at:insert_at] = additions
    for index, item in enumerate(items, start=1):
        item["index"] = index
        item["sourceImageIndex"] = index
        item["imageUrl"] = f"/workspace/{session_id}/generated/items/{index:02d}.png"

    draft["items"] = items
    warnings = [x for x in draft.get("warnings", []) if "手動追加" not in x]
    warnings.append(f"未検出画像を{added_count}件手動追加しました。名前・レアリティ・カテゴリを確認してください。")
    draft["warnings"] = warnings
    draft_path.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")
    return draft


def add_manual_crop(
    session_id: str, position: int, source_name: str, box: Sequence[float]
) -> Dict[str, Any]:
    """Insert only an image into the existing rows; names stay where they are."""
    safe_name = _safe_filename(source_name)
    source_path = _session_dir(session_id) / "uploads" / safe_name
    if not source_path.is_file():
        raise AppError("選択した元スクショが見つかりません。")
    if len(box) != 4:
        raise AppError("切り抜き範囲が不正です。")
    with Image.open(source_path) as source:
        width, height = source.size
        left, top, right, bottom = (int(round(float(value))) for value in box)
        left = max(0, min(width - 1, left))
        top = max(0, min(height - 1, top))
        right = max(left + 1, min(width, right))
        bottom = max(top + 1, min(height, bottom))
        if right - left < 20 or bottom - top < 20:
            raise AppError("アイテムを囲うように、もう少し大きく範囲選択してください。")
        cropped = source.convert("RGBA").crop((left, top, right, bottom))
        buffer = io.BytesIO()
        cropped.save(buffer, "PNG")

    session_dir = _session_dir(session_id)
    draft_path = session_dir / "draft.json"
    items_dir = session_dir / "generated" / "items"
    if not draft_path.is_file() or not items_dir.is_dir():
        raise AppError("差し込み先の処理データがありません。")
    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    items = list(draft.get("items", []))
    if not items:
        raise AppError("差し込み先のアイテムがありません。")
    insert_at = max(0, min(len(items) - 1, position - 1))

    # Convert older drafts to immutable image references before changing order.
    for index, item in enumerate(items, start=1):
        if not item.get("sourceImageFile"):
            old_index = int(item.get("sourceImageIndex", index))
            item["sourceImageFile"] = f"{old_index:02d}.png"

    # Add one row first so shifting never discards the image at the end.
    last_item = items[-1]
    items.append(
        {
            "index": len(items) + 1,
            "sourceImageIndex": len(items) + 1,
            "sourceImageFile": "",
            "name": "末尾アイテム名を入力",
            "rarity": last_item.get("rarity", "SR"),
            "category": last_item.get("category", "未分類"),
            "confidence": 0,
            "source": "manual:shifted-tail",
            "box": [0, 0, 192, 192],
            "imageUrl": "",
        }
    )
    for index in range(len(items) - 1, insert_at, -1):
        items[index]["sourceImageFile"] = items[index - 1]["sourceImageFile"]

    image_file = f"manual-{time.time_ns()}.png"
    output = _normalize_manual_item_image(buffer.getvalue())
    output.save(items_dir / image_file, "PNG")
    items[insert_at]["sourceImageFile"] = image_file

    revision = time.time_ns()
    for index, item in enumerate(items, start=1):
        item["index"] = index
        item["imageUrl"] = (
            f"/workspace/{session_id}/generated/items/"
            f"{urllib.parse.quote(str(item['sourceImageFile']))}?v={revision}"
        )

    draft["items"] = items
    warnings = [x for x in draft.get("warnings", []) if "画像を差し込み" not in x]
    warnings.append(
        f"{position}番へ画像を差し込み、元の画像だけを後続行へ送りました。"
        "アイテム名は移動していません。末尾に増えた行の正式名を入力してください。"
    )
    draft["warnings"] = warnings
    draft_path.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")
    return draft


def _unique_slug(base: str) -> str:
    slug = base
    number = 2
    while (
        (PROJECT_ROOT / "src" / "data" / "gachas" / f"{slug}.js").exists()
        or (PROJECT_ROOT / "public" / "images" / "items" / slug).exists()
    ):
        slug = f"{base}-{number}"
        number += 1
    return slug


def _item_name_key(name: str) -> str:
    return re.sub(r"[\s・,.。()（）\-ー]", "", name).lower()


def _thumbnail_difference(a: Image.Image, b: Image.Image) -> float:
    left = a.convert("RGB").resize((32, 32), Image.Resampling.LANCZOS)
    right = b.convert("RGB").resize((32, 32), Image.Resampling.LANCZOS)
    difference = ImageChops.difference(left, right)
    means = ImageStat.Stat(difference).mean
    return float(sum(means) / max(1, len(means)))


def _is_cross_screenshot_duplicate(
    candidate: Dict[str, Any], previous: Sequence[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """Find only a near-identical card repeated in a scroll overlap.

    dHash alone can confuse several different eye items because their shapes are
    similar.  Require both a close hash and a low RGB pixel difference.
    """
    for old in reversed(previous[-8:]):
        if old["sourceIndex"] == candidate["sourceIndex"]:
            continue
        if abs(old["sourceIndex"] - candidate["sourceIndex"]) > 1:
            continue
        if _hamming_distance(old["dhash"], candidate["dhash"]) > 5:
            continue
        if _thumbnail_difference(old["thumbnail"], candidate["thumbnail"]) <= 4.5:
            return old
    return None


def process_session(session_id: str) -> Dict[str, Any]:
    session_dir = _session_dir(session_id)
    upload_dir = session_dir / "uploads"
    screenshots = [
        p for p in upload_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS
    ]
    if not screenshots:
        raise AppError("スクリーンショットがありません。")

    output_dir = session_dir / "generated"
    if output_dir.exists():
        shutil.rmtree(output_dir)
    items_dir = output_dir / "items"
    items_dir.mkdir(parents=True, exist_ok=True)

    ocr_by_file: Dict[str, List[OCRLine]] = {}
    for path in screenshots:
        ocr_by_file[path.name] = run_ocr(path)

    screenshots = _order_screenshots(screenshots, ocr_by_file)
    all_lines: List[OCRLine] = []
    for path in screenshots:
        all_lines.extend(ocr_by_file.get(path.name, []))

    banner_info = _extract_banner(screenshots, ocr_by_file, output_dir / "banner.jpg")
    banner_source_name = str(banner_info["source"])
    banner_source = next((path for path in screenshots if path.name == banner_source_name), screenshots[0])
    if screenshots[0] != banner_source:
        screenshots = [banner_source, *[path for path in screenshots if path != banner_source]]
    metadata = _extract_metadata(ocr_by_file.get(screenshots[0].name, []))
    if not metadata.get("title"):
        fallback_metadata = _extract_metadata(all_lines)
        for key, value in fallback_metadata.items():
            if not metadata.get(key) and value:
                metadata[key] = value

    detected: List[Dict[str, Any]] = []
    current_category = ""
    current_rarity = ""

    for source_index, path in enumerate(screenshots):
        with Image.open(path) as image:
            rgb = image.convert("RGB")
            boxes = _detect_boxes(rgb)
            lines = ocr_by_file.get(path.name, [])

            category_events: List[Tuple[float, str]] = []
            rarity_events: List[Tuple[float, str]] = []
            for line in lines:
                category = _detect_category(line.text)
                if category and line.left < rgb.width * (420 / 1179):
                    category_events.append((line.top, category))
                normalized = _normalized_text(line.text).upper()
                if "SSR" in normalized and "ラインナップ" in normalized:
                    rarity_events.append((line.top, "SSR"))
                elif re.search(r"(^|[^S])SR", normalized) and "ラインナップ" in normalized:
                    rarity_events.append((line.top, "SR"))

            for box in boxes:
                top = box[1]
                for event_y, category in sorted(category_events):
                    if event_y <= top + 30:
                        current_category = category
                for event_y, rarity in sorted(rarity_events):
                    if event_y <= top + 30:
                        current_rarity = rarity

                name, confidence = _merge_name_lines(lines, box)
                rarity = _estimate_rarity(rgb, box)
                if rarity == "UNKNOWN" and current_rarity:
                    rarity = current_rarity
                if rarity == "UNKNOWN":
                    rarity = "SR"

                crop = rgb.crop(box)
                candidate = {
                    "source": path.name,
                    "sourceIndex": source_index,
                    "imageWidth": rgb.width,
                    "imageHeight": rgb.height,
                    "box": list(box),
                    "name": name,
                    "nameConfidence": round(confidence, 3),
                    "category": current_category or "未分類",
                    "rarity": rarity,
                    "dhash": _compute_dhash(crop),
                    "thumbnail": crop.resize((32, 32), Image.Resampling.LANCZOS),
                }
                duplicate = _is_cross_screenshot_duplicate(candidate, detected)
                if duplicate is not None:
                    # 色違いの目・髪などを画像の類似だけで消さない。
                    # OCRで同じ正式名と確認できた場合だけスクロール重複として除外する。
                    same_name = name and _item_name_key(name) == _item_name_key(duplicate.get("name", ""))
                    if same_name:
                        continue
                detected.append(candidate)

    if not detected:
        raise AppError("アイテム画像を検出できませんでした。")

    items: List[Dict[str, Any]] = []
    for candidate in detected:
        name = candidate["name"]

        index = len(items) + 1
        source_path = upload_dir / candidate["source"]
        with Image.open(source_path) as image:
            output = _crop_item_for_output(image, tuple(candidate["box"]))
            output.save(items_dir / f"{index:02d}.png", "PNG")

        if not name:
            name = f"アイテム {index:02d}"
        items.append(
            {
                "index": index,
                "sourceImageIndex": index,
                "sourceImageFile": f"{index:02d}.png",
                "name": name,
                "rarity": candidate["rarity"],
                "category": candidate["category"],
                "confidence": candidate["nameConfidence"],
                "source": candidate["source"],
                "box": candidate["box"],
                "imageUrl": f"/workspace/{session_id}/generated/items/{index:02d}.png",
            }
        )

    title = metadata["title"] or "タイトル未認識"
    base_slug = _slugify(title, metadata["startDate"])
    slug = _unique_slug(base_slug)
    warnings = []
    if title == "タイトル未認識":
        warnings.append("タイトルを自動認識できませんでした。タイトル欄を修正してください。")
    missing_names = sum(1 for item in items if item["name"].startswith("アイテム "))
    if missing_names:
        warnings.append(f"{missing_names}件のアイテム名を認識できませんでした。該当欄を修正してください。")
    if any(item["category"] == "未分類" for item in items):
        warnings.append("カテゴリ未分類のアイテムがあります。")

    draft = {
        "sessionId": session_id,
        "slug": slug,
        "title": title,
        "type": metadata["type"],
        "startDate": metadata["startDate"],
        "endDate": metadata["endDate"],
        "status": "開催中",
        "description": f"{title}の限定ガチャです。" if title != "タイトル未認識" else "",
        "bannerUrl": f"/workspace/{session_id}/generated/banner.jpg",
        "bannerInfo": banner_info,
        "items": items,
        "sourceImages": [
            {
                "name": path.name,
                "url": f"/workspace/{session_id}/uploads/{urllib.parse.quote(path.name)}",
            }
            for path in screenshots
        ],
        "warnings": warnings,
        "screenshotCount": len(screenshots),
        "screenshotOrder": [path.name for path in screenshots],
    }
    (session_dir / "draft.json").write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")
    return draft


def _js_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")


def _render_gacha_js(draft: Dict[str, Any]) -> str:
    slug = draft["slug"]
    lines = [
        "const gacha = {",
        f"  id: '{_js_string(slug)}',",
        f"  slug: '{_js_string(slug)}',",
        f"  title: '{_js_string(str(draft['title']))}',",
        f"  type: '{_js_string(str(draft.get('type') or 'アイミーボックス'))}',",
        f"  banner: '/images/gacha/{_js_string(slug)}/banner.jpg',",
        f"  status: '{_js_string(str(draft.get('status') or '開催中'))}',",
        "  infoStatus: '確認済み',",
        f"  startDate: '{_js_string(str(draft.get('startDate') or ''))}',",
        f"  endDate: '{_js_string(str(draft.get('endDate') or ''))}',",
        f"  description: '{_js_string(str(draft.get('description') or ''))}',",
        "  items: [",
    ]
    for index, item in enumerate(draft["items"], start=1):
        item_id = f"{slug}-{index:02d}"
        lines.extend(
            [
                "    {",
                f"      id: '{_js_string(item_id)}',",
                f"      rarity: '{_js_string(str(item.get('rarity') or 'SR'))}',",
                f"      category: '{_js_string(str(item.get('category') or '未分類'))}',",
                f"      name: '{_js_string(str(item.get('name') or f'アイテム {index:02d}'))}',",
                f"      image: '/images/items/{_js_string(slug)}/{index:02d}.png',",
                "    },",
            ]
        )
    lines.extend(["  ],", "}", "", "export default gacha", ""])
    return "\n".join(lines)


def _variable_name(slug: str) -> str:
    parts = [x for x in slug.split("-") if x]
    name = (parts[0] if parts else "gacha") + "".join(x[:1].upper() + x[1:] for x in parts[1:])
    name = re.sub(r"[^A-Za-z0-9_$]", "", name)
    if not name or name[0].isdigit():
        name = "gacha" + name[:1].upper() + name[1:]
    return name


def _update_registry_text(original: str, slug: str) -> str:
    import_path = f"./gachas/{slug}"
    if import_path in original:
        return original

    existing_vars = set(re.findall(r"^import\s+([A-Za-z_$][\w$]*)\s+from", original, flags=re.MULTILINE))
    base = _variable_name(slug)
    var = base
    number = 2
    while var in existing_vars:
        var = f"{base}{number}"
        number += 1

    import_line = f"import {var} from '{import_path}'\n"
    updated = import_line + original
    match = re.search(r"export\s+const\s+gachas\s*=\s*\[", updated)
    if not match:
        raise AppError("src/data/gachas.js の配列を見つけられませんでした。")
    insert_at = match.end()
    updated = updated[:insert_at] + f"\n  {var}," + updated[insert_at:]
    return updated


def _validate_draft(draft: Dict[str, Any]) -> None:
    slug = str(draft.get("slug", ""))
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        raise AppError("slugは英小文字・数字・ハイフンのみで入力してください。")
    title = str(draft.get("title", "")).strip()
    if not title or title == "タイトル未認識":
        raise AppError("ガチャタイトルを確認してください。")
    items = draft.get("items", [])
    if not isinstance(items, list) or not items:
        raise AppError("アイテムがありません。")
    for index, item in enumerate(items, start=1):
        if not str(item.get("name", "")).strip() or str(item.get("name", "")).startswith("アイテム "):
            raise AppError(f"{index:02d}番のアイテム名を確認してください。")
        if str(item.get("category", "")) in {"", "未分類"}:
            raise AppError(f"{index:02d}番のカテゴリを確認してください。")
        if str(item.get("rarity", "")) not in {"SSR", "SR", "NR", "R", "N"}:
            raise AppError(f"{index:02d}番のレアリティを確認してください。")


def _copytree_replace(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def _run_command(command: Sequence[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        list(command),
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
    )
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()
        raise AppError(f"コマンドに失敗しました: {' '.join(command)}\n{detail}")
    return proc


def publish_session(session_id: str, incoming: Dict[str, Any]) -> Dict[str, Any]:
    session_dir = _session_dir(session_id)
    draft_path = session_dir / "draft.json"
    if not draft_path.exists():
        raise AppError("処理済みデータがありません。")
    stored = json.loads(draft_path.read_text(encoding="utf-8"))

    # Only allow the editable fields from the browser; keep generated file paths server-owned.
    for key in ["slug", "title", "type", "startDate", "endDate", "status", "description", "items"]:
        if key in incoming:
            stored[key] = incoming[key]
    stored["slug"] = re.sub(r"-+", "-", str(stored["slug"]).strip().lower()).strip("-")
    _validate_draft(stored)

    staged_before = _run_command(["git", "diff", "--cached", "--name-only"], check=False).stdout.strip()
    if staged_before:
        raise AppError(
            "公開前からステージ済みの変更があります。別の変更を誤ってコミットしないため停止しました。\n"
            + staged_before
        )

    slug = stored["slug"]
    generated = session_dir / "generated"
    source_items = generated / "items"
    source_banner = generated / "banner.jpg"
    uploads = session_dir / "uploads"
    if not source_banner.exists() or not source_items.exists():
        raise AppError("生成画像がありません。もう一度スクショを処理してください。")

    generated_images = list(source_items.glob("*.png"))
    if not generated_images:
        raise AppError("生成済みアイテム画像がありません。")

    ordered_items_stage = session_dir / "publish-items"
    if ordered_items_stage.exists():
        shutil.rmtree(ordered_items_stage)
    ordered_items_stage.mkdir(parents=True)
    for new_index, item in enumerate(stored["items"], start=1):
        source_file = str(item.get("sourceImageFile", "")).strip()
        if not source_file:
            source_index = int(item.get("sourceImageIndex", item.get("index", new_index)))
            source_file = f"{source_index:02d}.png"
        source_file = Path(source_file).name
        source_image = source_items / source_file
        if not source_image.exists():
            raise AppError(f"{new_index:02d}番に対応する生成画像がありません。")
        shutil.copy2(source_image, ordered_items_stage / f"{new_index:02d}.png")

    data_file = PROJECT_ROOT / "src" / "data" / "gachas" / f"{slug}.js"
    registry_file = PROJECT_ROOT / "src" / "data" / "gachas.js"
    prod_items = PROJECT_ROOT / "public" / "images" / "items" / slug
    prod_gacha = PROJECT_ROOT / "public" / "images" / "gacha" / slug
    archive_dir = PROJECT_ROOT / "archive" / "gacha" / slug
    sitemap = PROJECT_ROOT / "public" / "sitemap.xml"

    if data_file.exists() and stored.get("slug") != json.loads(draft_path.read_text(encoding="utf-8")).get("slug"):
        raise AppError(f"同じslugのガチャがすでに存在します: {slug}")

    backup_root = session_dir / "publish-backup"
    if backup_root.exists():
        shutil.rmtree(backup_root)
    backup_root.mkdir(parents=True)

    paths_to_backup = {
        "data": data_file,
        "registry": registry_file,
        "items": prod_items,
        "gacha": prod_gacha,
        "archive": archive_dir,
        "sitemap": sitemap,
    }
    existed: Dict[str, bool] = {}
    for key, path in paths_to_backup.items():
        existed[key] = path.exists()
        if not path.exists():
            continue
        target = backup_root / key
        if path.is_dir():
            shutil.copytree(path, target)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)

    def rollback() -> None:
        for key, path in paths_to_backup.items():
            if path.exists():
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
            backup = backup_root / key
            if existed.get(key) and backup.exists():
                if backup.is_dir():
                    shutil.copytree(backup, path)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(backup, path)

    try:
        data_file.parent.mkdir(parents=True, exist_ok=True)
        data_file.write_text(_render_gacha_js(stored), encoding="utf-8")
        registry_original = registry_file.read_text(encoding="utf-8")
        registry_file.write_text(_update_registry_text(registry_original, slug), encoding="utf-8")

        _copytree_replace(ordered_items_stage, prod_items)
        prod_gacha.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_banner, prod_gacha / "banner.jpg")
        _copytree_replace(uploads, archive_dir)
        (archive_dir / ".gitkeep").touch()

        build = _run_command(["npm", "run", "build"])

        # Automatic deployment through the existing Git remote.
        stage_paths = [
            str(data_file.relative_to(PROJECT_ROOT)),
            str(registry_file.relative_to(PROJECT_ROOT)),
            str(prod_items.relative_to(PROJECT_ROOT)),
            str(prod_gacha.relative_to(PROJECT_ROOT)),
            str(archive_dir.relative_to(PROJECT_ROOT)),
        ]
        if sitemap.exists():
            stage_paths.append(str(sitemap.relative_to(PROJECT_ROOT)))
        _run_command(["git", "add", "--", *stage_paths])

        staged = _run_command(["git", "diff", "--cached", "--name-only"], check=False).stdout.strip()
        commit_result = "変更なし"
        push_result = "未実行"
        if staged:
            message = f"Add {stored['title']} gacha"
            _run_command(["git", "commit", "-m", message])
            commit_result = message
        _run_command(["git", "push"])
        push_result = "完了"

        stored["publishedAt"] = datetime.now().isoformat(timespec="seconds")
        draft_path.write_text(json.dumps(stored, ensure_ascii=False, indent=2), encoding="utf-8")
        inbox_archive = None
        try:
            inbox_archive = _archive_inbox_source(session_id, slug)
        except Exception as archive_error:
            traceback.print_exc()
            _set_inbox_state(
                status="published",
                message=f"公開は成功しましたが、元スクショの移動に失敗しました: {archive_error}",
                sessionId=session_id,
                draft=None,
            )
        return {
            "status": "published",
            "title": stored["title"],
            "slug": slug,
            "itemCount": len(stored["items"]),
            "build": "成功",
            "commit": commit_result,
            "push": push_result,
            "sitePath": f"/gacha/{slug}",
            "inboxArchive": inbox_archive or "",
            "buildLog": build.stdout[-2000:],
        }
    except Exception:
        # If a commit has already happened, restoring working files would create a confusing state.
        # Check whether HEAD contains our generated data file before rolling back.
        try:
            committed = _run_command(["git", "show", "--name-only", "--format=", "HEAD"], check=False).stdout
        except Exception:
            committed = ""
        if str(data_file.relative_to(PROJECT_ROOT)) not in committed:
            rollback()
            _run_command(["git", "reset"], check=False)
        raise


class Handler(BaseHTTPRequestHandler):
    server_version = "AimyGachaAdder/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def _send_json(self, obj: Any, status: int = 200) -> None:
        data = _json_dumps(obj)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _send_error_json(self, ex: Exception, status: int = 500) -> None:
        traceback.print_exc()
        self._send_json({"ok": False, "error": str(ex)}, status=status)

    def _read_json(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length > 50_000_000:
            raise AppError("送信データが大きすぎます。")
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8")) if raw else {}

    def do_GET(self) -> None:  # noqa: N802
        try:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            if path == "/":
                data = HTML_PATH.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data)
                return
            if path == "/api/inbox-status":
                self._send_json({"ok": True, **_get_inbox_state()})
                return
            if path.startswith("/workspace/"):
                relative = Path(urllib.parse.unquote(path[len("/workspace/") :]))
                if ".." in relative.parts:
                    raise AppError("不正なパスです。")
                file_path = WORKSPACE_ROOT / relative
                if not file_path.is_file():
                    self.send_error(404)
                    return
                content_type = "image/png"
                if file_path.suffix.lower() in {".jpg", ".jpeg"}:
                    content_type = "image/jpeg"
                data = file_path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data)
                return
            self.send_error(404)
        except Exception as ex:
            self._send_error_json(ex)

    def do_POST(self) -> None:  # noqa: N802
        try:
            parsed = urllib.parse.urlparse(self.path)
            query = urllib.parse.parse_qs(parsed.query)
            if parsed.path == "/api/open-inbox":
                INBOX_DIR.mkdir(parents=True, exist_ok=True)
                if platform.system() == "Darwin":
                    subprocess.Popen(["open", str(INBOX_DIR)])
                self._send_json({"ok": True, "folder": str(INBOX_DIR)})
                return

            if parsed.path == "/api/inbox-retry":
                _INBOX_RETRY_EVENT.set()
                _set_inbox_state(status="settling", message="再試行を受け付けました。")
                self._send_json({"ok": True})
                return

            if parsed.path == "/api/session":
                session_id = _new_session_id()
                directory = _session_dir(session_id)
                (directory / "uploads").mkdir(parents=True, exist_ok=True)
                self._send_json({"ok": True, "sessionId": session_id})
                return

            if parsed.path == "/api/upload":
                session_id = query.get("session", [""])[0]
                filename = _safe_filename(query.get("name", [""])[0])
                if Path(filename).suffix.lower() not in IMAGE_EXTS:
                    raise AppError(f"画像以外は追加できません: {filename}")
                directory = _session_dir(session_id) / "uploads"
                directory.mkdir(parents=True, exist_ok=True)
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 40_000_000:
                    raise AppError("画像サイズが不正です。")
                target = directory / filename
                target.write_bytes(self.rfile.read(length))
                try:
                    with Image.open(target) as image:
                        image.verify()
                except Exception:
                    target.unlink(missing_ok=True)
                    raise AppError(f"画像を読み込めません: {filename}")
                self._send_json({"ok": True, "name": filename})
                return

            if parsed.path == "/api/process":
                obj = self._read_json()
                draft = process_session(str(obj.get("sessionId", "")))
                self._send_json({"ok": True, "draft": draft})
                return

            if parsed.path == "/api/save-draft":
                obj = self._read_json()
                session_id = str(obj.get("sessionId", ""))
                draft = obj.get("draft", {})
                if not isinstance(draft, dict):
                    raise AppError("確認内容を保存できません。")
                draft_path = _session_dir(session_id) / "draft.json"
                if not draft_path.is_file():
                    raise AppError("処理データがありません。")
                draft_path.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")
                self._send_json({"ok": True})
                return

            if parsed.path == "/api/manual-item":
                session_id = query.get("session", [""])[0]
                filename = _safe_filename(query.get("name", ["manual.png"])[0])
                try:
                    position = int(query.get("position", ["1"])[0])
                except ValueError as ex:
                    raise AppError("追加位置が不正です。") from ex
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 40_000_000:
                    raise AppError("追加画像のサイズが不正です。")
                draft = add_manual_items(session_id, position, [(filename, self.rfile.read(length))])
                self._send_json({"ok": True, "draft": draft})
                return

            if parsed.path == "/api/manual-crop":
                obj = self._read_json()
                try:
                    position = int(obj.get("position", 1))
                except (TypeError, ValueError) as ex:
                    raise AppError("追加位置が不正です。") from ex
                draft = add_manual_crop(
                    str(obj.get("sessionId", "")),
                    position,
                    str(obj.get("source", "")),
                    obj.get("box", []),
                )
                self._send_json({"ok": True, "draft": draft})
                return

            if parsed.path == "/api/publish":
                obj = self._read_json()
                result = publish_session(str(obj.get("sessionId", "")), obj.get("draft", {}))
                self._send_json({"ok": True, "result": result})
                return

            self.send_error(404)
        except AppError as ex:
            self._send_error_json(ex, status=400)
        except Exception as ex:
            self._send_error_json(ex, status=500)


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def main() -> int:
    if not HTML_PATH.exists():
        print(f"UI file not found: {HTML_PATH}", file=sys.stderr)
        return 1
    WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    INBOX_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    watcher = threading.Thread(target=_watch_inbox, name="gacha-inbox-watcher", daemon=True)
    watcher.start()

    port = _find_free_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print("=" * 64)
    print("Aimy ガチャ追加ツールを起動しました")
    print(url)
    print(f"監視フォルダ: {INBOX_DIR}")
    print("このターミナルを開いている間、フォルダへのスクショ投入を自動検知します。")
    print("=" * 64)
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
