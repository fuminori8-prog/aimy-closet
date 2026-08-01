#!/usr/bin/env python3
"""Re-detect and replace only item images for an existing Aimy gacha.

This tool fixes the image-quality failure mode of the original gacha importer:
small card crops were enlarged to 192x192 and permanently saved blurred.  Here
we detect from full-resolution screenshots, retain the native crop pixels, map
them to the existing item order, and never touch the banner or gacha metadata.
"""

from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
import shutil
import socket
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import urllib.parse
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from PIL import Image, ImageChops, ImageFilter, ImageOps, ImageStat


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
HTML_PATH = SCRIPT_DIR / "redetect_gacha.html"
WORKSPACE_ROOT = SCRIPT_DIR / "workspace" / "redetect"
ARCHIVE_ROOT = PROJECT_ROOT / "archive" / "gacha"
PUBLIC_GACHA_ROOT = PROJECT_ROOT / "public" / "images" / "gacha"
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
MIN_CARD_SIDE = 150
MAX_UPLOAD_BYTES = 40_000_000
MAX_JSON_BYTES = 2_000_000
PUBLISH_LOCK = threading.Lock()

sys.path.insert(0, str(SCRIPT_DIR))
from detect_cards import _compute_dhash, _detect_boxes, _hamming_distance  # noqa: E402
from edit_gacha_app import (  # noqa: E402
    AppError,
    _create_backups,
    _entry_summary,
    _find_entry,
    _load_module,
    _registered_entries,
    _resolve_public_image,
    _restore_backups,
    _run_command,
    _unique_paths,
)


BBox = Tuple[int, int, int, int]


@dataclass(frozen=True)
class SourceImage:
    path: Path
    display_name: str
    origin: str
    input_order: int


def _natural_key(value: str) -> List[Any]:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", value)]


def _safe_filename(value: str) -> str:
    name = Path(value).name
    stem = re.sub(r"[^0-9A-Za-z._-]+", "_", name).strip("._")
    return stem or f"source-{time.time_ns()}.png"


def _new_session_id() -> str:
    return hashlib.sha1(f"{time.time_ns()}-{os.getpid()}".encode()).hexdigest()[:18]


def _session_dir(session_id: str) -> Path:
    if not re.fullmatch(r"[a-f0-9]{18}", session_id):
        raise AppError("作業IDが不正です。最初からやり直してください。")
    path = WORKSPACE_ROOT / session_id
    resolved = path.resolve()
    resolved.relative_to(WORKSPACE_ROOT.resolve())
    return path


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _image_dimensions(path: Path) -> Tuple[int, int]:
    try:
        with Image.open(path) as image:
            return image.size
    except Exception as error:
        raise AppError(f"画像を読み込めません: {path.name}") from error


def _stored_sources(slug: str) -> List[SourceImage]:
    """Find screenshots already retained for a gacha, without duplicate bytes."""
    paths: List[Tuple[Path, str]] = []
    public_dir = PUBLIC_GACHA_ROOT / slug
    archive_dir = ARCHIVE_ROOT / slug
    for root, origin in ((public_dir, "public"), (archive_dir, "archive")):
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*"), key=lambda item: _natural_key(item.name)):
            if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            if path.stem.lower() == "banner" or "banner" in path.stem.lower():
                continue
            try:
                width, height = _image_dimensions(path)
            except AppError:
                continue
            # The archive can also contain old, already-cropped item squares.
            # Only portrait gacha-detail screenshots are valid re-detection input.
            if height < 500 or height < width * 1.25:
                continue
            paths.append((path, origin))

    result: List[SourceImage] = []
    seen_hashes: set[str] = set()
    for path, origin in paths:
        digest = _file_sha256(path)
        if digest in seen_hashes:
            continue
        seen_hashes.add(digest)
        result.append(SourceImage(path, path.name, origin, len(result)))
    return result


def _source_summary(source: SourceImage) -> Dict[str, Any]:
    width, height = _image_dimensions(source.path)
    return {
        "name": source.display_name,
        "origin": source.origin,
        "width": width,
        "height": height,
        "sourceQuality": "十分" if width >= 1000 else "低解像度の可能性",
    }


def _gacha_summaries() -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for entry in _registered_entries():
        summary = _entry_summary(entry)
        gacha = _load_module(entry.data_file)
        sources = _stored_sources(summary["slug"])
        item_sizes: List[Tuple[int, int]] = []
        for item in gacha.get("items") or []:
            try:
                item_sizes.append(_image_dimensions(_resolve_public_image(str(item.get("image") or ""))))
            except AppError:
                pass
        result.append(
            {
                "slug": summary["slug"],
                "title": summary["title"],
                "itemCount": len(gacha.get("items") or []),
                "storedSourceCount": len(sources),
                "storedSources": [_source_summary(source) for source in sources],
                "currentImageSizes": sorted({f"{w}×{h}" for w, h in item_sizes}),
            }
        )
    return result


def _square_box(image_size: Tuple[int, int], box: BBox) -> BBox:
    image_width, image_height = image_size
    left, top, right, bottom = box
    side = max(right - left, bottom - top)
    center_x = (left + right) / 2
    center_y = (top + bottom) / 2
    new_left = round(center_x - side / 2)
    new_top = round(center_y - side / 2)
    new_left = max(0, min(image_width - side, new_left))
    new_top = max(0, min(image_height - side, new_top))
    return (new_left, new_top, new_left + side, new_top + side)


def _comparison_image(image: Image.Image) -> Image.Image:
    return ImageOps.fit(
        image.convert("RGB"),
        (64, 64),
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.5),
    ).filter(ImageFilter.GaussianBlur(0.55))


def _match_cost(left: Image.Image, right: Image.Image) -> float:
    left_cmp = _comparison_image(left)
    right_cmp = _comparison_image(right)
    pixel_difference = sum(ImageStat.Stat(ImageChops.difference(left_cmp, right_cmp)).mean) / 3
    hash_difference = _hamming_distance(_compute_dhash(left_cmp), _compute_dhash(right_cmp))
    return float(pixel_difference + hash_difference * 0.65)


def _sharpness(image: Image.Image) -> float:
    gray = image.convert("L")
    edges = gray.filter(ImageFilter.FIND_EDGES)
    return round(float(ImageStat.Stat(edges).var[0]), 1)


def _read_existing_items(slug: str) -> Tuple[Any, Dict[str, Any], List[Dict[str, Any]]]:
    entry, summary = _find_entry(slug)
    gacha = _load_module(entry.data_file)
    raw_items = gacha.get("items") or []
    if not raw_items:
        raise AppError("このガチャには登録済みアイテムがありません。")

    items: List[Dict[str, Any]] = []
    seen_paths: set[Path] = set()
    for index, raw in enumerate(raw_items, start=1):
        image_value = str(raw.get("image") or "")
        image_path = _resolve_public_image(image_value)
        resolved = image_path.resolve()
        if resolved in seen_paths:
            raise AppError(
                "複数アイテムが同じ画像ファイルを共有しているため、安全に一括差し替えできません: "
                + image_value
            )
        seen_paths.add(resolved)
        with Image.open(image_path) as image:
            current = image.convert("RGB")
            items.append(
                {
                    "index": index,
                    "id": str(raw.get("id") or ""),
                    "name": str(raw.get("name") or f"アイテム {index:02d}"),
                    "imageValue": image_value,
                    "imagePath": image_path,
                    "comparison": current.copy(),
                    "currentSize": list(current.size),
                    "currentSharpness": _sharpness(current),
                }
            )
    return entry, {**summary, "dataHash": _file_sha256(entry.data_file)}, items


def _detect_source_candidates(
    source: SourceImage,
    source_index: int,
    candidates_dir: Path,
) -> List[Dict[str, Any]]:
    with Image.open(source.path) as opened:
        image = opened.convert("RGB")
    boxes = _detect_boxes(image)
    candidates: List[Dict[str, Any]] = []
    for box_index, detected_box in enumerate(boxes, start=1):
        box = _square_box(image.size, tuple(int(value) for value in detected_box))
        crop = image.crop(box)
        filename = f"source-{source_index + 1:02d}-card-{box_index:02d}.png"
        crop.save(candidates_dir / filename, "PNG")
        candidates.append(
            {
                "sourceIndex": source_index,
                "sourceName": source.display_name,
                "sourceOrigin": source.origin,
                "sourcePath": source.path,
                "box": list(box),
                "width": crop.width,
                "height": crop.height,
                "side": min(crop.size),
                "filename": filename,
                "image": crop,
                "sharpness": _sharpness(crop),
            }
        )
    return candidates


def _order_sources_by_existing_items(
    candidate_groups: Sequence[List[Dict[str, Any]]],
    items: Sequence[Dict[str, Any]],
) -> List[List[Dict[str, Any]]]:
    """Order random-named screenshots by the items they visually contain."""
    ranked: List[Tuple[float, int, List[Dict[str, Any]]]] = []
    for original_index, group in enumerate(candidate_groups):
        best_indices: List[int] = []
        for candidate in group:
            costs = [_match_cost(candidate["image"], item["comparison"]) for item in items]
            if costs:
                best_indices.append(min(range(len(costs)), key=costs.__getitem__))
        rank = statistics.median(best_indices) if best_indices else 10_000 + original_index
        ranked.append((float(rank), original_index, group))
    return [group for _, _, group in sorted(ranked, key=lambda value: (value[0], value[1]))]


def _align_candidates(
    candidates: Sequence[Dict[str, Any]],
    items: Sequence[Dict[str, Any]],
) -> Tuple[List[int], List[List[float]]]:
    """Select an ordered candidate subsequence matching every existing item."""
    item_count = len(items)
    candidate_count = len(candidates)
    costs: List[List[float]] = [
        [_match_cost(candidate["image"], item["comparison"]) for item in items]
        for candidate in candidates
    ]
    if candidate_count < item_count:
        return [], costs

    infinity = float("inf")
    dp = [[infinity] * (candidate_count + 1) for _ in range(item_count + 1)]
    take = [[False] * (candidate_count + 1) for _ in range(item_count + 1)]
    for candidate_index in range(candidate_count + 1):
        dp[0][candidate_index] = 0.0

    for item_index in range(1, item_count + 1):
        for candidate_index in range(1, candidate_count + 1):
            skip_cost = dp[item_index][candidate_index - 1]
            take_cost = dp[item_index - 1][candidate_index - 1] + costs[candidate_index - 1][item_index - 1]
            if take_cost <= skip_cost:
                dp[item_index][candidate_index] = take_cost
                take[item_index][candidate_index] = True
            else:
                dp[item_index][candidate_index] = skip_cost

    selected: List[int] = []
    item_index = item_count
    candidate_index = candidate_count
    while item_index > 0 and candidate_index > 0:
        if take[item_index][candidate_index]:
            selected.append(candidate_index - 1)
            item_index -= 1
            candidate_index -= 1
        else:
            candidate_index -= 1
    selected.reverse()
    return (selected if len(selected) == item_count else []), costs


def _write_session_manifest(
    session_dir: Path,
    slug: str,
    summary: Dict[str, Any],
    sources: Sequence[SourceImage],
    candidates: Sequence[Dict[str, Any]],
    selected: Sequence[int],
    items: Sequence[Dict[str, Any]],
    costs: Sequence[Sequence[float]],
) -> Dict[str, Any]:
    mapping: List[Dict[str, Any]] = []
    for item_index, candidate_index in enumerate(selected):
        item = items[item_index]
        candidate = candidates[candidate_index]
        cost = round(float(costs[candidate_index][item_index]), 1)
        mapping.append(
            {
                "index": item_index + 1,
                "itemId": item["id"],
                "name": item["name"],
                "imageValue": item["imageValue"],
                "currentSize": item["currentSize"],
                "currentSharpness": item["currentSharpness"],
                "candidateFile": candidate["filename"],
                "candidateUrl": "",
                "sourceName": candidate["sourceName"],
                "sourceOrigin": candidate["sourceOrigin"],
                "sourceBox": candidate["box"],
                "candidateSize": [candidate["width"], candidate["height"]],
                "candidateSharpness": candidate["sharpness"],
                "matchCost": cost,
                "matchQuality": "良好" if cost <= 34 else ("要確認" if cost <= 55 else "弱い"),
                "resolutionQuality": "十分" if candidate["side"] >= MIN_CARD_SIDE else "低解像度",
            }
        )

    source_records = [
        {
            **_source_summary(source),
            "path": str(source.path),
            "sha256": _file_sha256(source.path),
        }
        for source in sources
    ]
    manifest = {
        "slug": slug,
        "title": summary["title"],
        "dataFile": str(_find_entry(slug)[0].data_file),
        "dataHash": summary["dataHash"],
        "itemCount": len(items),
        "candidateCount": len(candidates),
        "selectedCandidateIndexes": list(selected),
        "mapping": mapping,
        "sources": source_records,
        "createdAt": time.time(),
    }
    serializable = dict(manifest)
    (session_dir / "manifest.json").write_text(
        json.dumps(serializable, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest


def process_sources(slug: str, session_id: str, use_stored: bool) -> Dict[str, Any]:
    session_dir = _session_dir(session_id)
    candidates_dir = session_dir / "candidates"
    if candidates_dir.exists():
        shutil.rmtree(candidates_dir)
    candidates_dir.mkdir(parents=True, exist_ok=True)

    if use_stored:
        sources = _stored_sources(slug)
    else:
        uploads_dir = session_dir / "uploads"
        upload_paths = sorted(
            [
                path
                for path in uploads_dir.iterdir()
                if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
            ],
            key=lambda path: _natural_key(path.name),
        ) if uploads_dir.is_dir() else []
        sources = [SourceImage(path, re.sub(r"^\d{2}-", "", path.name), "今回選択", index) for index, path in enumerate(upload_paths)]
    if not sources:
        raise AppError("再検出する元スクリーンショットがありません。")

    _, summary, items = _read_existing_items(slug)
    candidate_groups = [
        _detect_source_candidates(source, index, candidates_dir)
        for index, source in enumerate(sources)
    ]
    if not any(candidate_groups):
        raise AppError("アイテム枠を1件も検出できませんでした。元のガチャ詳細スクショを選んでください。")

    ordered_groups = _order_sources_by_existing_items(candidate_groups, items)
    candidates = [candidate for group in ordered_groups for candidate in group]
    selected, costs = _align_candidates(candidates, items)
    manifest = _write_session_manifest(
        session_dir, slug, summary, sources, candidates, selected, items, costs
    )

    mapping = manifest["mapping"]
    for row in mapping:
        row["currentUrl"] = "/api/media?" + urllib.parse.urlencode({"path": row["imageValue"], "v": time.time_ns()})
        row["candidateUrl"] = "/api/session-media?" + urllib.parse.urlencode(
            {"session": session_id, "file": row["candidateFile"], "v": time.time_ns()}
        )

    low_resolution_count = sum(row["resolutionQuality"] == "低解像度" for row in mapping)
    weak_match_count = sum(row["matchQuality"] == "弱い" for row in mapping)
    warnings: List[str] = []
    if len(candidates) < len(items):
        warnings.append(
            f"登録アイテム{len(items)}件に対して検出は{len(candidates)}件です。"
            "不足している範囲のスクショを追加して、もう一度実行してください。"
        )
    elif len(candidates) > len(items):
        warnings.append(
            f"スクロール重複など{len(candidates) - len(items)}候補を自動で除外しました。"
        )
    if low_resolution_count:
        warnings.append(
            f"{low_resolution_count}件は元カードが{MIN_CARD_SIDE}px未満です。"
            "拡大加工はせず、検出した原寸のまま保存できます。"
            "より高画質にしたい場合だけ、iPhoneの元サイズ（目安：スクショ幅1000px以上）で再検出してください。"
        )
    if weak_match_count:
        warnings.append(
            f"{weak_match_count}件は現画像との一致度が弱いため、左右の画像対応を重点確認してください。"
        )

    # Resolution is information for the user, not a reason to take control away.
    # When every existing item has exactly one candidate, native-size saving is safe.
    publish_ready = len(selected) == len(items)
    return {
        "sessionId": session_id,
        "slug": slug,
        "title": summary["title"],
        "itemCount": len(items),
        "candidateCount": len(candidates),
        "mappedCount": len(mapping),
        "publishReady": publish_ready,
        "lowResolutionCount": low_resolution_count,
        "minimumCardSide": MIN_CARD_SIDE,
        "sources": [_source_summary(source) for source in sources],
        "mapping": mapping,
        "warnings": warnings,
    }


def _save_crop_for_target(source: Path, destination: Path) -> None:
    with Image.open(source) as opened:
        image = opened.convert("RGBA")
    extension = destination.suffix.lower()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if extension == ".png":
        image.save(destination, "PNG", optimize=True)
    elif extension in {".jpg", ".jpeg"}:
        background = Image.new("RGB", image.size, "white")
        background.paste(image, mask=image.getchannel("A"))
        background.save(destination, "JPEG", quality=96, subsampling=0, optimize=True)
    elif extension == ".webp":
        image.save(destination, "WEBP", quality=96, method=6)
    else:
        raise AppError(f"保存先画像形式に対応していません: {destination.name}")


def _archive_sources(manifest: Dict[str, Any]) -> int:
    destination = ARCHIVE_ROOT / manifest["slug"]
    destination.mkdir(parents=True, exist_ok=True)
    existing_hashes = {
        _file_sha256(path)
        for path in destination.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    }
    copied = 0
    for source in manifest["sources"]:
        path = Path(source["path"])
        digest = str(source["sha256"])
        if digest in existing_hashes or not path.is_file():
            continue
        extension = path.suffix.lower()
        target = destination / f"original-{digest[:12]}{extension}"
        shutil.copy2(path, target)
        existing_hashes.add(digest)
        copied += 1
    return copied


def publish_session(session_id: str, confirmed: bool) -> Dict[str, Any]:
    session_dir = _session_dir(session_id)
    manifest_path = session_dir / "manifest.json"
    if not manifest_path.is_file():
        raise AppError("再検出結果がありません。最初からやり直してください。")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if time.time() - float(manifest.get("createdAt", 0)) > 6 * 60 * 60:
        raise AppError("再検出結果が古いため、もう一度検出してください。")

    slug = str(manifest["slug"])
    entry, summary, items = _read_existing_items(slug)
    if _file_sha256(entry.data_file) != manifest.get("dataHash"):
        raise AppError("検出後にガチャデータが変更されています。もう一度検出してください。")
    mapping = manifest.get("mapping") or []
    if len(mapping) != len(items):
        raise AppError("検出数と登録アイテム数が一致していません。")
    if not confirmed:
        raise AppError("左右の画像とアイテム名が一致していることを確認してください。")

    staged_before = _run_command(["git", "diff", "--cached", "--name-only"], check=False).stdout.strip()
    if staged_before:
        raise AppError("ステージ済み変更があるため、安全のため停止しました。\n" + staged_before)

    target_paths = [item["imagePath"] for item in items]
    sitemap_file = PROJECT_ROOT / "public" / "sitemap.xml"
    transaction_paths = _unique_paths([*target_paths, sitemap_file])
    relative_targets = [str(path.relative_to(PROJECT_ROOT)) for path in target_paths]
    committed = False
    commit_message = f"Restore {summary['title']} item image quality"

    with tempfile.TemporaryDirectory(prefix="aimy-redetect-publish-") as temporary:
        backup_root = Path(temporary) / "backups"
        backups = _create_backups(transaction_paths, backup_root)
        try:
            for item, row in zip(items, mapping):
                if item["id"] != row.get("itemId") or item["imageValue"] != row.get("imageValue"):
                    raise AppError("検出後にアイテム順または画像パスが変わっています。もう一度検出してください。")
                candidate = session_dir / "candidates" / str(row["candidateFile"])
                if not candidate.is_file():
                    raise AppError("再検出画像が見つかりません。もう一度検出してください。")
                _save_crop_for_target(candidate, item["imagePath"])

            build = _run_command(["npm", "run", "build"])
            # Image-only replacement must not include a regenerated sitemap.
            sitemap_backup = next(record for record in backups if record.path == sitemap_file)
            _restore_backups([sitemap_backup])
            _run_command(["git", "diff", "--check", "--", *relative_targets])
            _run_command(["git", "add", "--", *relative_targets])
            if _run_command(["git", "diff", "--cached", "--quiet"], check=False).returncode == 0:
                raise AppError("差し替え後の画像が現在の画像と同じで、変更がありませんでした。")
            _run_command(["git", "commit", "-m", commit_message])
            committed = True
            try:
                _run_command(["git", "push"])
            except AppError as error:
                raise AppError(
                    "画像差し替えとcommitは完了しましたが、GitHubへのpushに失敗しました。\n"
                    "通信を確認して、ターミナルで git push を実行してください。\n"
                    + str(error)
                ) from error

            archived_count = _archive_sources(manifest)
            return {
                "slug": slug,
                "title": summary["title"],
                "itemCount": len(items),
                "bannerChanged": False,
                "metadataChanged": False,
                "build": "成功",
                "commit": commit_message,
                "push": "完了",
                "archivedSourceCount": archived_count,
                "buildLog": build.stdout[-1200:],
            }
        except Exception:
            if not committed:
                _restore_backups(backups)
                _run_command(["git", "reset", "--", *relative_targets], check=False)
            raise


class Handler(BaseHTTPRequestHandler):
    server_version = "AimyGachaRedetect/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def _send_bytes(self, data: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, value: Any, status: int = 200) -> None:
        self._send_bytes(
            json.dumps(value, ensure_ascii=False).encode("utf-8"),
            "application/json; charset=utf-8",
            status,
        )

    def _read_json(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > MAX_JSON_BYTES:
            raise AppError("送信内容のサイズが不正です。")
        try:
            value = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise AppError("送信内容を読み取れませんでした。") from error
        if not isinstance(value, dict):
            raise AppError("送信内容が不正です。")
        return value

    def _error(self, error: Exception, status: int) -> None:
        traceback.print_exc()
        self._send_json({"ok": False, "error": str(error)}, status)

    def do_GET(self) -> None:  # noqa: N802
        try:
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path == "/":
                self._send_bytes(HTML_PATH.read_bytes(), "text/html; charset=utf-8")
                return
            if parsed.path == "/api/gachas":
                self._send_json({"ok": True, "gachas": _gacha_summaries()})
                return
            if parsed.path == "/api/media":
                query = urllib.parse.parse_qs(parsed.query)
                image_path = _resolve_public_image(query.get("path", [""])[0])
                self._send_bytes(
                    image_path.read_bytes(),
                    mimetypes.guess_type(image_path.name)[0] or "application/octet-stream",
                )
                return
            if parsed.path == "/api/session-media":
                query = urllib.parse.parse_qs(parsed.query)
                session_dir = _session_dir(query.get("session", [""])[0])
                filename = Path(query.get("file", [""])[0]).name
                image_path = session_dir / "candidates" / filename
                if not image_path.is_file():
                    self.send_error(404)
                    return
                self._send_bytes(image_path.read_bytes(), "image/png")
                return
            self.send_error(404)
        except AppError as error:
            self._error(error, 400)
        except Exception as error:
            self._error(error, 500)

    def do_POST(self) -> None:  # noqa: N802
        try:
            parsed = urllib.parse.urlparse(self.path)
            query = urllib.parse.parse_qs(parsed.query)
            if parsed.path == "/api/session":
                session_id = _new_session_id()
                (_session_dir(session_id) / "uploads").mkdir(parents=True, exist_ok=True)
                self._send_json({"ok": True, "sessionId": session_id})
                return
            if parsed.path == "/api/upload":
                session_id = query.get("session", [""])[0]
                try:
                    order = int(query.get("order", ["1"])[0])
                except ValueError as error:
                    raise AppError("スクショの順番が不正です。") from error
                filename = f"{order:02d}-{_safe_filename(query.get('name', ['source.png'])[0])}"
                if Path(filename).suffix.lower() not in IMAGE_EXTENSIONS:
                    raise AppError("PNG・JPEG・WebPのスクリーンショットを選んでください。")
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > MAX_UPLOAD_BYTES:
                    raise AppError("スクリーンショットの容量が不正です。")
                destination = _session_dir(session_id) / "uploads" / filename
                destination.write_bytes(self.rfile.read(length))
                try:
                    with Image.open(destination) as image:
                        width, height = image.size
                        image.verify()
                except Exception as error:
                    destination.unlink(missing_ok=True)
                    raise AppError(f"画像を読み込めません: {filename}") from error
                self._send_json({"ok": True, "name": filename, "width": width, "height": height})
                return
            if parsed.path == "/api/process":
                payload = self._read_json()
                result = process_sources(
                    str(payload.get("slug") or ""),
                    str(payload.get("sessionId") or ""),
                    bool(payload.get("useStored", False)),
                )
                self._send_json({"ok": True, "result": result})
                return
            if parsed.path == "/api/publish":
                if not PUBLISH_LOCK.acquire(blocking=False):
                    raise AppError("別の本番反映を実行中です。完了まで待ってください。")
                try:
                    payload = self._read_json()
                    result = publish_session(
                        str(payload.get("sessionId") or ""),
                        bool(payload.get("confirmed", False)),
                    )
                finally:
                    PUBLISH_LOCK.release()
                self._send_json({"ok": True, "result": result})
                return
            self.send_error(404)
        except AppError as error:
            self._error(error, 400)
        except Exception as error:
            self._error(error, 500)


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def main() -> int:
    if not HTML_PATH.is_file():
        print(f"UI file not found: {HTML_PATH}", file=sys.stderr)
        return 1
    WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
    try:
        count = len(_gacha_summaries())
    except AppError as error:
        print(error, file=sys.stderr)
        return 1
    port = _find_free_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print("=" * 68)
    print("Aimy 既存ガチャ・アイテム画像再検出ツールを起動しました")
    print(f"登録済みガチャ: {count}件")
    print(url)
    print("バナー・名前・カテゴリ・開催時期は変更しません。")
    print("このターミナルを閉じるとツールも終了します。")
    print("=" * 68)
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
