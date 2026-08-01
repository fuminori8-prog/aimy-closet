#!/usr/bin/env python3
"""Import unidentified historical Aimy items from the 2.5th anniversary grid.

The source screenshots expose an implementation period, broad category,
rarity and image, but not the original item/gacha name.  This tool therefore
compares every crop with the *current* gacha catalogue before publishing and
stores only genuinely unmatched items in a separate data file.
"""

from __future__ import annotations

import base64
import binascii
import fnmatch
import hashlib
import io
import json
import math
import mimetypes
import os
import platform
import pickle
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
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageStat


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
HTML_PATH = SCRIPT_DIR / "historical_items.html"
REGISTRY_PATH = PROJECT_ROOT / "src" / "data" / "gachas.js"
GACHA_DATA_DIR = PROJECT_ROOT / "src" / "data" / "gachas"
HISTORICAL_DATA_PATH = PROJECT_ROOT / "src" / "data" / "historicalItems.js"
PUBLIC_ROOT = (PROJECT_ROOT / "public").resolve()
HISTORICAL_IMAGE_DIR = PUBLIC_ROOT / "images" / "items" / "historical-2-5"
SITEMAP_PATH = PROJECT_ROOT / "public" / "sitemap.xml"
WORK_ROOT = Path(tempfile.gettempdir()) / "aimy-historical-items"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAIN_CATEGORIES = ("服", "髪型", "アクセサリー", "パーツ", "背景")
RARITIES = ("SSR", "SR")
SCREENSHOT_BACKGROUND = (234, 245, 255)
SAVE_LOCK = threading.Lock()
CATALOG_LOCK = threading.Lock()
CATALOG_CACHE: Dict[str, Any] = {"signature": None, "items": [], "historical": []}
CATALOG_CACHE_PATH = WORK_ROOT / "catalog-descriptors-v1.pickle"


class AppError(RuntimeError):
    pass


@dataclass(frozen=True)
class Descriptor:
    pixels: bytes
    edges: bytes
    histogram: Tuple[float, ...]
    difference_hash: Tuple[int, ...]


@dataclass(frozen=True)
class BackupRecord:
    path: Path
    existed: bool
    was_directory: bool
    backup: Path


NODE_LOAD_MANY = """
import { pathToFileURL } from 'node:url';
let input = '';
for await (const chunk of process.stdin) input += chunk;
const files = JSON.parse(input);
const values = [];
for (let index = 0; index < files.length; index += 1) {
  const url = pathToFileURL(files[index]).href + '?aimy=' + Date.now() + '-' + index;
  values.push((await import(url)).default);
}
process.stdout.write(JSON.stringify(values));
"""

NODE_LOAD_ONE = """
import { pathToFileURL } from 'node:url';
const file = process.argv[1];
const url = pathToFileURL(file).href + '?aimy=' + Date.now();
const module = await import(url);
process.stdout.write(JSON.stringify(module.default ?? module.historicalItems ?? []));
"""


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False).encode("utf-8")


def _run_node(script: str, *, arguments: Sequence[str] = (), input_text: str = "") -> Any:
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script, *arguments],
        cwd=PROJECT_ROOT,
        input=input_text,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise AppError(f"登録済みデータを読み取れませんでした。\n{detail}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise AppError("登録済みデータの解析結果が不正です。") from error


def _registered_gacha_files() -> List[Path]:
    if not REGISTRY_PATH.is_file():
        raise AppError("src/data/gachas.js が見つかりません。")
    registry = REGISTRY_PATH.read_text(encoding="utf-8")
    module_names = re.findall(
        r"^import\s+[A-Za-z_$][\w$]*\s+from\s+['\"]\./gachas/([^'\"]+)['\"]",
        registry,
        flags=re.MULTILINE,
    )
    files: List[Path] = []
    seen: set[Path] = set()
    for module_name in module_names:
        path = GACHA_DATA_DIR / f"{module_name}.js"
        if path.is_file() and path not in seen:
            files.append(path)
            seen.add(path)
    return files


def _load_gachas() -> List[Dict[str, Any]]:
    files = _registered_gacha_files()
    values = _run_node(NODE_LOAD_MANY, input_text=json.dumps([str(path) for path in files]))
    if not isinstance(values, list) or not all(isinstance(value, dict) for value in values):
        raise AppError("登録済みガチャを確認できませんでした。")
    return values


def _load_historical_items() -> List[Dict[str, Any]]:
    if not HISTORICAL_DATA_PATH.is_file():
        return []
    values = _run_node(NODE_LOAD_ONE, arguments=[str(HISTORICAL_DATA_PATH)])
    if not isinstance(values, list) or not all(isinstance(value, dict) for value in values):
        raise AppError("過去アイテムデータを確認できませんでした。")
    return values


def _main_category(value: Any) -> str:
    category = str(value or "").strip()
    if category in {"服", "衣装"}:
        return "服"
    if category in {"髪", "髪型"}:
        return "髪型"
    if category in {
        "アクセサリー",
        "アクセ",
        "あたま",
        "髪飾り",
        "めがね",
        "メガネ",
        "ピアス",
        "耳",
        "耳飾り",
    }:
        return "アクセサリー"
    if category in {"パーツ", "目", "メイク", "口", "鼻", "まゆげ", "眉毛"}:
        return "パーツ"
    if category == "背景":
        return "背景"
    return "その他"


def _stored_category(main_category: str) -> str:
    return {
        "服": "衣装",
        "髪型": "髪型",
        "アクセサリー": "アクセサリー",
        "パーツ": "パーツ",
        "背景": "背景",
    }[main_category]


def _resolve_public_image(value: str) -> Optional[Path]:
    if not value.startswith("/") or value == "placeholder":
        return None
    relative = Path(urllib.parse.unquote(value.lstrip("/")))
    if ".." in relative.parts or relative.suffix.lower() not in IMAGE_EXTENSIONS:
        return None
    resolved = (PUBLIC_ROOT / relative).resolve()
    try:
        resolved.relative_to(PUBLIC_ROOT)
    except ValueError:
        return None
    return resolved if resolved.is_file() else None


def _catalog_signature() -> Tuple[Tuple[str, int, int], ...]:
    paths = [REGISTRY_PATH, *_registered_gacha_files()]
    if HISTORICAL_DATA_PATH.is_file():
        paths.append(HISTORICAL_DATA_PATH)
    item_image_root = PUBLIC_ROOT / "images" / "items"
    if item_image_root.is_dir():
        paths.extend(
            sorted(
                path
                for path in item_image_root.rglob("*")
                if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
            )
        )
    signature: List[Tuple[str, int, int]] = []
    for path in paths:
        stat = path.stat()
        signature.append((str(path), stat.st_mtime_ns, stat.st_size))
    return tuple(signature)


def _catalog_item_count() -> int:
    count = 0
    for gacha in _load_gachas():
        for item in gacha.get("items") or []:
            if (
                _main_category(item.get("category")) in MAIN_CATEGORIES
                and str(item.get("rarity") or "").upper() in RARITIES
                and _resolve_public_image(str(item.get("image") or "")) is not None
            ):
                count += 1
    return count


def _median(values: List[int]) -> int:
    if not values:
        return 255
    values.sort()
    return values[len(values) // 2]


def _estimate_background(image: Image.Image) -> Tuple[int, int, int]:
    rgb = image.convert("RGB")
    width, height = rgb.size
    border = max(2, round(min(width, height) * 0.08))
    red: List[int] = []
    green: List[int] = []
    blue: List[int] = []
    step = max(1, min(width, height) // 80)
    pixels = rgb.load()
    for y in range(0, height, step):
        for x in range(0, width, step):
            if border < x < width - border and border < y < height - border:
                continue
            r, g, b = pixels[x, y]
            red.append(r)
            green.append(g)
            blue.append(b)
    return _median(red), _median(green), _median(blue)


def _color_distance(left: Tuple[int, int, int], right: Tuple[int, int, int]) -> float:
    return math.sqrt(sum((left[index] - right[index]) ** 2 for index in range(3)))


def _normalize_background(image: Image.Image) -> Tuple[Image.Image, Tuple[int, int, int, int]]:
    """Turn only edge-connected background pixels white and find item bounds."""
    working = image.convert("RGB").resize((96, 96), Image.Resampling.LANCZOS)
    background = _estimate_background(working)
    pixels = working.load()
    width, height = working.size
    visited = bytearray(width * height)
    queue: List[Tuple[int, int]] = []

    def is_background(x: int, y: int) -> bool:
        color = pixels[x, y]
        maximum = max(color)
        minimum = min(color)
        saturation = 0 if maximum == 0 else (maximum - minimum) / maximum
        return _color_distance(color, background) < 39 or (
            min(color) > 242 and saturation < 0.055
        )

    for x in range(width):
        queue.append((x, 0))
        queue.append((x, height - 1))
    for y in range(1, height - 1):
        queue.append((0, y))
        queue.append((width - 1, y))

    head = 0
    while head < len(queue):
        x, y = queue[head]
        head += 1
        index = y * width + x
        if visited[index] or not is_background(x, y):
            continue
        visited[index] = 1
        if x > 0:
            queue.append((x - 1, y))
        if x + 1 < width:
            queue.append((x + 1, y))
        if y > 0:
            queue.append((x, y - 1))
        if y + 1 < height:
            queue.append((x, y + 1))

    output = working.copy()
    output_pixels = output.load()
    min_x, min_y, max_x, max_y = width, height, -1, -1
    for y in range(height):
        for x in range(width):
            index = y * width + x
            if visited[index]:
                output_pixels[x, y] = (255, 255, 255)
                continue
            if x >= round(width * 0.71) and y <= round(height * 0.22):
                output_pixels[x, y] = (255, 255, 255)
                continue
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x)
            max_y = max(max_y, y)

    if max_x < min_x or max_y < min_y:
        return output, (0, 0, width, height)
    detected_width = max_x - min_x + 1
    detected_height = max_y - min_y + 1
    padding_x = max(3, round(detected_width * 0.08))
    padding_y = max(3, round(detected_height * 0.08))
    return output, (
        max(0, min_x - padding_x),
        max(0, min_y - padding_y),
        min(width, max_x + padding_x + 1),
        min(height, max_y + padding_y + 1),
    )


def _contain(image: Image.Image, size: int = 48) -> Image.Image:
    source = image.convert("RGB")
    source.thumbnail((size, size), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (size, size), "white")
    canvas.paste(source, ((size - source.width) // 2, (size - source.height) // 2))
    return canvas


def _descriptor(image: Image.Image) -> Descriptor:
    prepared = _contain(image, 48)
    sample = prepared.resize((32, 32), Image.Resampling.LANCZOS)
    pixels = bytes(sample.tobytes())
    edges_image = sample.convert("L").filter(ImageFilter.FIND_EDGES)
    edges = bytes(edges_image.tobytes())
    histogram_raw = sample.histogram()
    histogram: List[float] = []
    total = 32 * 32 * 3
    for channel in range(3):
        values = histogram_raw[channel * 256 : (channel + 1) * 256]
        for start in range(0, 256, 32):
            histogram.append(sum(values[start : start + 32]) / total)
    hash_image = prepared.convert("L").resize((17, 16), Image.Resampling.LANCZOS)
    hash_pixels = list(hash_image.getdata())
    difference_hash: List[int] = []
    for y in range(16):
        offset = y * 17
        for x in range(16):
            difference_hash.append(1 if hash_pixels[offset + x] > hash_pixels[offset + x + 1] else 0)
    return Descriptor(pixels, edges, tuple(histogram), tuple(difference_hash))


def _descriptor_variants(image: Image.Image, *, catalog: bool) -> Tuple[Descriptor, ...]:
    rgb = image.convert("RGB")
    if catalog:
        inset_x = round(rgb.width * 0.055)
        inset_y = round(rgb.height * 0.055)
        if rgb.width - inset_x * 2 >= 24 and rgb.height - inset_y * 2 >= 24:
            rgb = rgb.crop((inset_x, inset_y, rgb.width - inset_x, rgb.height - inset_y))
    normalized, foreground_box = _normalize_background(rgb)
    focus = normalized.crop(foreground_box)
    variants = [_descriptor(normalized), _descriptor(focus)]
    if focus.width > 4 and focus.height > 4:
        side = min(focus.width, focus.height)
        left = (focus.width - side) // 2
        top = (focus.height - side) // 2
        variants.append(_descriptor(focus.crop((left, top, left + side, top + side))))
    return tuple(variants)


def _mean_absolute_bytes(left: bytes, right: bytes) -> float:
    return sum(abs(a - b) for a, b in zip(left, right)) / max(1, len(left)) / 255


def _histogram_distance(left: Tuple[float, ...], right: Tuple[float, ...]) -> float:
    return max(0.0, min(1.0, 1 - sum(min(a, b) for a, b in zip(left, right))))


def _hash_distance(left: Tuple[int, ...], right: Tuple[int, ...]) -> float:
    return sum(a != b for a, b in zip(left, right)) / max(1, len(left))


def _descriptor_distance(left: Descriptor, right: Descriptor) -> float:
    pixels = _mean_absolute_bytes(left.pixels, right.pixels)
    edges = _mean_absolute_bytes(left.edges, right.edges)
    histogram = _histogram_distance(left.histogram, right.histogram)
    hash_distance = _hash_distance(left.difference_hash, right.difference_hash)
    return pixels * 0.42 + edges * 0.22 + histogram * 0.24 + hash_distance * 0.12


def _variant_distance(
    left: Sequence[Descriptor], right: Sequence[Descriptor]
) -> float:
    values = sorted(_descriptor_distance(a, b) for a in left for b in right)
    if not values:
        return 1.0
    best = values[0]
    second = values[1] if len(values) > 1 else best
    return best * 0.82 + second * 0.18


def _catalog_items() -> List[Dict[str, Any]]:
    signature = _catalog_signature()
    with CATALOG_LOCK:
        if CATALOG_CACHE["signature"] == signature:
            return CATALOG_CACHE["items"]

        signature_hash = hashlib.sha1(
            json.dumps(signature, ensure_ascii=False).encode()
        ).hexdigest()
        if CATALOG_CACHE_PATH.is_file():
            try:
                with CATALOG_CACHE_PATH.open("rb") as file_handle:
                    cached = pickle.load(file_handle)
                if (
                    isinstance(cached, dict)
                    and cached.get("signatureHash") == signature_hash
                    and isinstance(cached.get("items"), list)
                    and isinstance(cached.get("historical"), list)
                ):
                    CATALOG_CACHE["signature"] = signature
                    CATALOG_CACHE["items"] = cached["items"]
                    CATALOG_CACHE["historical"] = cached["historical"]
                    return CATALOG_CACHE["items"]
            except Exception:
                CATALOG_CACHE_PATH.unlink(missing_ok=True)

        records: List[Dict[str, Any]] = []
        for gacha in _load_gachas():
            for item in gacha.get("items") or []:
                image_value = str(item.get("image") or "")
                image_path = _resolve_public_image(image_value)
                if image_path is None:
                    continue
                category = _main_category(item.get("category"))
                rarity = str(item.get("rarity") or "").upper()
                if category not in MAIN_CATEGORIES or rarity not in RARITIES:
                    continue
                try:
                    with Image.open(image_path) as image:
                        descriptors = _descriptor_variants(image, catalog=True)
                except Exception:
                    continue
                records.append(
                    {
                        "id": str(item.get("id") or ""),
                        "name": str(item.get("name") or ""),
                        "rarity": rarity,
                        "category": category,
                        "image": image_value,
                        "gachaSlug": str(gacha.get("slug") or ""),
                        "gachaTitle": str(gacha.get("title") or ""),
                        "descriptors": descriptors,
                    }
                )

        historical_records: List[Dict[str, Any]] = []
        for item in _load_historical_items():
            image_value = str(item.get("image") or "")
            image_path = _resolve_public_image(image_value)
            category = _main_category(item.get("mainCategory") or item.get("category"))
            rarity = str(item.get("rarity") or "").upper()
            if image_path is None or category not in MAIN_CATEGORIES or rarity not in RARITIES:
                continue
            try:
                with Image.open(image_path) as image:
                    descriptors = _descriptor_variants(image, catalog=True)
            except Exception:
                continue
            historical_records.append(
                {
                    "id": str(item.get("id") or ""),
                    "name": str(item.get("name") or "名称未特定"),
                    "rarity": rarity,
                    "category": category,
                    "image": image_value,
                    "gachaSlug": "",
                    "gachaTitle": "登録済みのガチャ未特定アイテム",
                    "descriptors": descriptors,
                }
            )

        CATALOG_CACHE["signature"] = signature
        CATALOG_CACHE["items"] = records
        CATALOG_CACHE["historical"] = historical_records
        WORK_ROOT.mkdir(parents=True, exist_ok=True)
        try:
            with CATALOG_CACHE_PATH.open("wb") as file_handle:
                pickle.dump(
                    {
                        "signatureHash": signature_hash,
                        "items": records,
                        "historical": historical_records,
                    },
                    file_handle,
                    protocol=pickle.HIGHEST_PROTOCOL,
                )
        except OSError:
            pass
        return records


def _best_catalog_matches(
    descriptors: Sequence[Descriptor], category: str, rarity: str, limit: int = 3
) -> List[Tuple[float, Dict[str, Any]]]:
    matches = [
        (_variant_distance(descriptors, record["descriptors"]), record)
        for record in _catalog_items()
        if record["category"] == category and record["rarity"] == rarity
    ]
    matches.sort(key=lambda entry: entry[0])
    return matches[:limit]


def _best_historical_matches(
    descriptors: Sequence[Descriptor], category: str, rarity: str, limit: int = 3
) -> List[Tuple[float, Dict[str, Any]]]:
    _catalog_items()
    matches = [
        (_variant_distance(descriptors, record["descriptors"]), record)
        for record in CATALOG_CACHE["historical"]
        if record["category"] == category and record["rarity"] == rarity
    ]
    matches.sort(key=lambda entry: entry[0])
    return matches[:limit]


def _safe_filename(value: str) -> str:
    name = Path(value).name
    stem = re.sub(r"[^0-9A-Za-z._-]+", "_", name).strip("._")
    return stem or f"screenshot-{time.time_ns()}.png"


def _decode_image(data_url: str) -> Tuple[bytes, str]:
    match = re.fullmatch(
        r"data:image/(png|jpeg|jpg|webp);base64,([A-Za-z0-9+/=]+)", data_url
    )
    if not match:
        raise AppError("画像を読み取れませんでした。PNG・JPEG・WebPを選んでください。")
    try:
        raw = base64.b64decode(match.group(2), validate=True)
    except (ValueError, binascii.Error) as error:
        raise AppError("画像データが壊れています。") from error
    if not raw or len(raw) > 45_000_000:
        raise AppError("画像の容量が大きすぎます。")
    try:
        with Image.open(io.BytesIO(raw)) as image:
            width, height = image.size
            image.verify()
    except Exception as error:
        raise AppError("画像として開けませんでした。") from error
    if width < 320 or height < 480:
        raise AppError("一覧が読める元サイズのスクリーンショットを選んでください。")
    extension = ".jpg" if match.group(1) in {"jpeg", "jpg"} else f".{match.group(1)}"
    return raw, extension


def _near_background(color: Tuple[int, int, int], tolerance: int = 16) -> bool:
    return max(abs(color[index] - SCREENSHOT_BACKGROUND[index]) for index in range(3)) <= tolerance


def _header_bands(image: Image.Image) -> List[Tuple[int, int]]:
    rgb = image.convert("RGB")
    width, height = rgb.size
    left = round(width * 0.52)
    right = max(left + 1, width - round(width * 0.01))
    step = max(1, width // 240)
    sample_x = list(range(left, right, step))
    scores: List[float] = []
    pixels = rgb.load()
    for y in range(height):
        score = sum(_near_background(pixels[x, y]) for x in sample_x) / max(1, len(sample_x))
        scores.append(score)
    minimum_height = max(22, round(width * 0.045))
    bands: List[Tuple[int, int]] = []
    start: Optional[int] = None
    for y, score in enumerate(scores):
        is_header = score >= 0.72
        if is_header and start is None:
            start = y
        elif not is_header and start is not None:
            if y - start >= minimum_height:
                bands.append((start, y - 1))
            start = None
    if start is not None and height - start >= minimum_height:
        bands.append((start, height - 1))
    return bands


def _read_ocr_lines(image_path: Path) -> List[Any]:
    try:
        from add_gacha_app import run_ocr  # local shared Apple Vision wrapper

        return list(run_ocr(image_path))
    except Exception:
        return []


def _period_from_ocr(lines: Sequence[Any], band: Tuple[int, int]) -> Tuple[str, str]:
    top, bottom = band
    relevant = [
        str(line.text)
        for line in lines
        if float(getattr(line, "bottom", 0)) >= top - 8
        and float(getattr(line, "top", 0)) <= bottom + 8
    ]
    text = "".join(relevant).replace(" ", "").replace("　", "")
    match = re.search(
        r"(20\d{2})\D{0,2}(\d{1,2})\D{0,5}(20\d{2})\D{0,2}(\d{1,2})",
        text,
    )
    if not match:
        return "", ""
    start = f"{int(match.group(1)):04d}-{int(match.group(2)):02d}"
    end = f"{int(match.group(3)):04d}-{int(match.group(4)):02d}"
    return start, end


def _rarity_from_crop(crop: Image.Image) -> Optional[str]:
    rgb = crop.convert("RGB")
    width, height = rgb.size
    area = rgb.crop((round(width * 0.54), 0, width, round(height * 0.36)))
    orange = 0
    cyan = 0
    magenta = 0
    for r, g, b in area.getdata():
        if r > 220 and 65 < g < 205 and b < 115:
            orange += 1
        if g > 145 and b > 145 and (b - r > 24 or g - r > 24):
            cyan += 1
        if r > 175 and b > 125 and r - g > 35:
            magenta += 1
    scale = max(0.2, (width * height) / (176 * 176))
    if cyan >= 80 * scale and magenta >= 45 * scale:
        return "SSR"
    if orange >= 70 * scale:
        return "SR"
    return None


def _overlay_obscures(crop: Image.Image) -> bool:
    rgb = crop.convert("RGB").resize((64, 64), Image.Resampling.BILINEAR)
    gray = 0
    for r, g, b in rgb.getdata():
        if abs(r - g) < 8 and abs(g - b) < 8 and 198 < r < 249:
            gray += 1
    return gray / (64 * 64) > 0.52


def _remove_owned_icon(image: Image.Image) -> Image.Image:
    """Keep source pixels intact; an overlay cannot reveal the hidden item art."""
    return image.convert("RGB")


def _add_rarity_frame(image: Image.Image, rarity: str) -> Image.Image:
    """Overlay the missing rarity frame inside the native crop; never pad it."""
    rgb = image.convert("RGB")
    side = min(rgb.size)
    left = (rgb.width - side) // 2
    top = (rgb.height - side) // 2
    rgb = rgb.crop((left, top, left + side, top + side))
    overlay = Image.new("RGBA", rgb.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    border = max(3, round(side * 0.035))
    radius = max(8, round(side * 0.105))
    if rarity == "SR":
        colors = [(255, 221, 63), (255, 171, 31), (255, 226, 84), (222, 151, 20)]
    else:
        colors = [
            (72, 231, 224),
            (110, 247, 124),
            (97, 163, 255),
            (205, 91, 255),
            (255, 92, 189),
            (72, 231, 224),
        ]
    for offset in range(border):
        ratio = offset / max(1, border - 1)
        position = ratio * (len(colors) - 1)
        index = min(len(colors) - 2, int(position))
        blend = position - index
        color = tuple(
            round(colors[index][channel] * (1 - blend) + colors[index + 1][channel] * blend)
            for channel in range(3)
        )
        draw.rounded_rectangle(
            (offset, offset, side - 1 - offset, side - 1 - offset),
            radius=max(1, radius - offset),
            outline=(*color, 255),
            width=1,
        )
    return Image.alpha_composite(rgb.convert("RGBA"), overlay)


def _period_label(start: str, end: str) -> str:
    start_match = re.fullmatch(r"(20\d{2})-(0[1-9]|1[0-2])", start)
    end_match = re.fullmatch(r"(20\d{2})-(0[1-9]|1[0-2])", end)
    if not start_match or not end_match:
        raise AppError("実装月を開始・終了ともに選択してください。")
    return (
        f"{int(start_match.group(1))}年{int(start_match.group(2))}月 ～ "
        f"{int(end_match.group(1))}年{int(end_match.group(2))}月"
    )


def _session_dir(session_id: str) -> Path:
    if not re.fullmatch(r"[a-f0-9]{16}", session_id):
        raise AppError("作業IDが不正です。")
    return WORK_ROOT / session_id


def _new_session() -> Tuple[str, Path]:
    session_id = hashlib.sha1(f"{time.time_ns()}-{os.getpid()}".encode()).hexdigest()[:16]
    path = _session_dir(session_id)
    path.mkdir(parents=True, exist_ok=False)
    return session_id, path


def _match_status(matches: Sequence[Tuple[float, Dict[str, Any]]]) -> str:
    if not matches:
        return "new"
    best = matches[0][0]
    second = matches[1][0] if len(matches) > 1 else 1.0
    margin = second - best
    if best <= 0.025 or (best <= 0.045 and margin >= 0.008):
        return "existing"
    if best <= 0.075:
        return "review"
    return "new"


def analyze(payload: Dict[str, Any]) -> Dict[str, Any]:
    incoming = payload.get("files")
    if not isinstance(incoming, list) or not incoming:
        raise AppError("スクリーンショットを選択してください。")
    if len(incoming) > 80:
        raise AppError("一度に処理できる画像は80枚までです。")

    session_id, session = _new_session()
    upload_dir = session / "uploads"
    candidate_dir = session / "candidates"
    upload_dir.mkdir()
    candidate_dir.mkdir()
    all_candidates: List[Dict[str, Any]] = []
    duplicate_descriptors: List[Tuple[str, str, Tuple[Descriptor, ...], str]] = []
    warnings: List[str] = []

    for file_index, raw_file in enumerate(incoming):
        if not isinstance(raw_file, dict):
            raise AppError("画像情報が不正です。")
        category = str(raw_file.get("category") or "").strip()
        if category not in MAIN_CATEGORIES:
            raise AppError("各スクリーンショットのカテゴリを選択してください。")
        raw, extension = _decode_image(str(raw_file.get("dataUrl") or ""))
        name = _safe_filename(str(raw_file.get("name") or f"image-{file_index + 1}"))
        source_path = upload_dir / f"{file_index + 1:03d}-{Path(name).stem}{extension}"
        source_path.write_bytes(raw)

        with Image.open(source_path) as opened:
            screenshot = opened.convert("RGB")
        width, height = screenshot.size
        bands = _header_bands(screenshot)
        if not bands:
            warnings.append(
                f"{name}: 水色の実装月見出しを検出できなかったため、この画像は追加候補を作っていません。"
            )
            continue
        ocr_lines = _read_ocr_lines(source_path)
        periods = [(*band, *_period_from_ocr(ocr_lines, band)) for band in bands]
        scale = width / 944
        cell = max(56, round(176 * scale))
        column_step = max(cell + 2, round(182 * scale))
        margin_x = max(0, round(16 * scale))
        row_step = max(cell + 2, round(189 * scale))
        header_gap = max(4, round(13 * scale))

        for period_index, (band_top, band_bottom, implemented_from, implemented_to) in enumerate(periods):
            section_bottom = periods[period_index + 1][0] if period_index + 1 < len(periods) else height
            row_top = band_bottom + 1 + header_gap
            while row_top + cell <= section_bottom:
                for column in range(5):
                    left = margin_x + column * column_step
                    if left + cell > width:
                        continue
                    crop = screenshot.crop((left, row_top, left + cell, row_top + cell))
                    rarity = _rarity_from_crop(crop)
                    if rarity is None or _overlay_obscures(crop):
                        continue
                    cleaned = _remove_owned_icon(crop)
                    descriptors = _descriptor_variants(cleaned, catalog=False)
                    duplicate_of = ""
                    for old_category, old_rarity, old_descriptors, old_id in duplicate_descriptors:
                        if old_category != category or old_rarity != rarity:
                            continue
                        if _variant_distance(descriptors, old_descriptors) <= 0.045:
                            duplicate_of = old_id
                            break
                    candidate_id = f"c{len(all_candidates) + 1:04d}"
                    if not duplicate_of:
                        duplicate_descriptors.append((category, rarity, descriptors, candidate_id))
                    preview_path = candidate_dir / f"{candidate_id}.png"
                    cleaned.save(preview_path, "PNG")
                    gacha_matches = _best_catalog_matches(descriptors, category, rarity)
                    historical_matches = _best_historical_matches(descriptors, category, rarity)
                    matches = sorted([*gacha_matches, *historical_matches], key=lambda entry: entry[0])[:3]
                    status = "duplicate" if duplicate_of else _match_status(matches)
                    best_match = matches[0] if matches else None
                    all_candidates.append(
                        {
                            "id": candidate_id,
                            "source": name,
                            "sourceIndex": file_index,
                            "category": category,
                            "rarity": rarity,
                            "implementedFrom": implemented_from,
                            "implementedTo": implemented_to,
                            "imageUrl": f"/api/media?session={session_id}&candidate={candidate_id}",
                            "status": status,
                            "decision": (
                                "exclude"
                                if status in {"existing", "duplicate"}
                                else "review"
                                if status == "review"
                                else "add"
                            ),
                            "duplicateOf": duplicate_of,
                            "match": (
                                {
                                    "id": best_match[1]["id"],
                                    "name": best_match[1]["name"],
                                    "gachaTitle": best_match[1]["gachaTitle"],
                                    "gachaSlug": best_match[1]["gachaSlug"],
                                    "image": best_match[1]["image"],
                                    "distance": round(best_match[0], 4),
                                    "similarity": max(0, min(100, round((1 - best_match[0] / 0.42) * 100))),
                                }
                                if best_match
                                else None
                            ),
                        }
                    )
                row_top += row_step

    if not all_candidates:
        shutil.rmtree(session, ignore_errors=True)
        detail = "\n".join(warnings)
        raise AppError("アイテム候補を検出できませんでした。" + (f"\n{detail}" if detail else ""))

    manifest = {"sessionId": session_id, "candidates": all_candidates}
    (session / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    counts = {
        key: sum(candidate["status"] == key for candidate in all_candidates)
        for key in ("existing", "duplicate", "review", "new")
    }
    return {
        "sessionId": session_id,
        "candidates": all_candidates,
        "counts": counts,
        "catalogItemCount": len(_catalog_items()),
        "warnings": warnings,
    }


def _js_string(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace("\r", "\\r")
        .replace("\n", "\\n")
        .replace("\t", "\\t")
    )


def _render_historical_items(items: Sequence[Dict[str, Any]]) -> str:
    lines = ["export const historicalItems = ["]
    for item in items:
        lines.extend(
            [
                "  {",
                f"    id: '{_js_string(str(item['id']))}',",
                f"    name: '{_js_string(str(item.get('name') or '名称未特定'))}',",
                f"    rarity: '{_js_string(str(item['rarity']))}',",
                f"    category: '{_js_string(str(item['category']))}',",
                f"    mainCategory: '{_js_string(str(item['mainCategory']))}',",
                f"    implementationPeriod: '{_js_string(str(item['implementationPeriod']))}',",
                f"    implementedFrom: '{_js_string(str(item['implementedFrom']))}',",
                f"    implementedTo: '{_js_string(str(item['implementedTo']))}',",
                f"    image: '{_js_string(str(item['image']))}',",
                "    source: '2.5周年交換所',",
                "    identificationStatus: '未特定',",
                "  },",
            ]
        )
    lines.extend(["]", "", "export default historicalItems", ""])
    return "\n".join(lines)


def _run(command: Sequence[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(list(command), cwd=PROJECT_ROOT, text=True, capture_output=True)
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise AppError(f"コマンドに失敗しました: {' '.join(command)}\n{detail}")
    return result


def _unique_paths(paths: Iterable[Path]) -> List[Path]:
    output: List[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path.resolve(strict=False))
        if key not in seen:
            output.append(path)
            seen.add(key)
    return output


def _create_backups(paths: Iterable[Path], root: Path) -> List[BackupRecord]:
    records: List[BackupRecord] = []
    for index, path in enumerate(_unique_paths(paths)):
        existed = path.exists()
        was_directory = path.is_dir() and not path.is_symlink()
        backup = root / f"{index:03d}"
        if existed:
            if was_directory:
                shutil.copytree(path, backup)
            else:
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, backup)
        records.append(BackupRecord(path, existed, was_directory, backup))
    return records


def _restore_backups(records: Sequence[BackupRecord]) -> None:
    for record in reversed(records):
        if record.path.exists():
            if record.path.is_dir() and not record.path.is_symlink():
                shutil.rmtree(record.path)
            else:
                record.path.unlink()
        if record.existed:
            record.path.parent.mkdir(parents=True, exist_ok=True)
            if record.was_directory:
                shutil.copytree(record.backup, record.path)
            else:
                shutil.copy2(record.backup, record.path)


def _publish_transaction(
    new_items: Sequence[Dict[str, Any]], image_sources: Dict[str, Path], commit_message: str
) -> None:
    staged = _run(["git", "diff", "--cached", "--name-only"], check=False).stdout.strip()
    if staged:
        raise AppError("ステージ済みの変更があります。別の保存処理を完了してから再実行してください。")
    targets = [HISTORICAL_DATA_PATH, HISTORICAL_IMAGE_DIR, SITEMAP_PATH]
    with tempfile.TemporaryDirectory(prefix="aimy-historical-backup-") as temp_name:
        backups = _create_backups(targets, Path(temp_name))
        committed = False
        try:
            HISTORICAL_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
            for identifier, source in image_sources.items():
                shutil.copy2(source, HISTORICAL_IMAGE_DIR / f"{identifier}.png")
            HISTORICAL_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
            HISTORICAL_DATA_PATH.write_text(
                _render_historical_items(new_items), encoding="utf-8"
            )
            _run(["npm", "run", "build"])
            sitemap_backup = next(record for record in backups if record.path == SITEMAP_PATH)
            if SITEMAP_PATH.exists():
                SITEMAP_PATH.unlink()
            if sitemap_backup.existed:
                shutil.copy2(sitemap_backup.backup, SITEMAP_PATH)
            relative_data = str(HISTORICAL_DATA_PATH.relative_to(PROJECT_ROOT))
            relative_images = str(HISTORICAL_IMAGE_DIR.relative_to(PROJECT_ROOT))
            _run(["git", "diff", "--check", "--", relative_data, relative_images])
            _run(["git", "add", "--", relative_data, relative_images])
            if _run(["git", "diff", "--cached", "--quiet"], check=False).returncode != 0:
                _run(["git", "commit", "-m", commit_message])
                committed = True
                _run(["git", "push"])
        except Exception:
            if not committed:
                _run(
                    [
                        "git",
                        "reset",
                        "--",
                        str(HISTORICAL_DATA_PATH.relative_to(PROJECT_ROOT)),
                        str(HISTORICAL_IMAGE_DIR.relative_to(PROJECT_ROOT)),
                    ],
                    check=False,
                )
                _restore_backups(backups)
            raise
    CATALOG_CACHE["signature"] = None


def publish(payload: Dict[str, Any]) -> Dict[str, Any]:
    session_id = str(payload.get("sessionId") or "")
    session = _session_dir(session_id)
    manifest_path = session / "manifest.json"
    if not manifest_path.is_file():
        raise AppError("解析結果が見つかりません。もう一度画像を解析してください。")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    original_by_id = {candidate["id"]: candidate for candidate in manifest["candidates"]}
    incoming = payload.get("candidates")
    if not isinstance(incoming, list):
        raise AppError("確認結果を読み取れませんでした。")

    existing = _load_historical_items()
    existing_ids = {str(item.get("id") or "") for item in existing}
    additions: List[Dict[str, Any]] = []
    image_sources: Dict[str, Path] = {}
    unresolved = 0
    for decision in incoming:
        if not isinstance(decision, dict):
            continue
        candidate_id = str(decision.get("id") or "")
        original = original_by_id.get(candidate_id)
        if not original:
            raise AppError("解析時に存在しなかった候補が含まれています。")
        action = str(decision.get("decision") or "")
        if action == "review":
            unresolved += 1
            continue
        if action != "add":
            continue
        category = str(decision.get("category") or original["category"])
        rarity = str(decision.get("rarity") or original["rarity"])
        if category not in MAIN_CATEGORIES or rarity not in RARITIES:
            raise AppError("カテゴリまたはレア度を確認してください。")
        implemented_from = str(decision.get("implementedFrom") or "")
        implemented_to = str(decision.get("implementedTo") or "")
        label = _period_label(implemented_from, implemented_to)
        source = session / "candidates" / f"{candidate_id}.png"
        if not source.is_file():
            raise AppError("追加候補の画像が見つかりません。")
        with Image.open(source) as image:
            cleaned = _remove_owned_icon(image)
            framed = _add_rarity_frame(cleaned, rarity)
            buffer = io.BytesIO()
            framed.save(buffer, "PNG", optimize=True)
            output_bytes = buffer.getvalue()
        identifier = "archive-2-5-" + hashlib.sha1(
            output_bytes + f"|{category}|{rarity}".encode()
        ).hexdigest()[:14]
        if identifier in existing_ids or any(item["id"] == identifier for item in additions):
            continue
        framed_path = session / "candidates" / f"publish-{identifier}.png"
        framed_path.write_bytes(output_bytes)
        item = {
            "id": identifier,
            "name": "名称未特定",
            "rarity": rarity,
            "category": _stored_category(category),
            "mainCategory": category,
            "implementationPeriod": label,
            "implementedFrom": implemented_from,
            "implementedTo": implemented_to,
            "image": f"/images/items/historical-2-5/{identifier}.png",
            "source": "2.5周年交換所",
            "identificationStatus": "未特定",
        }
        additions.append(item)
        image_sources[identifier] = framed_path

    if unresolved:
        raise AppError(f"確認待ちが{unresolved}件あります。『既存』か『追加』を選んでください。")
    if not additions:
        return {"added": 0, "total": len(existing), "message": "追加対象はありませんでした。"}
    combined = [*existing, *additions]
    combined.sort(
        key=lambda item: (
            str(item.get("implementedFrom") or ""),
            str(item.get("implementedTo") or ""),
            str(item.get("mainCategory") or ""),
            str(item.get("rarity") or ""),
            str(item.get("id") or ""),
        ),
        reverse=True,
    )
    _publish_transaction(
        combined,
        image_sources,
        f"Add {len(additions)} unidentified historical Aimy items",
    )
    return {"added": len(additions), "total": len(combined)}


def recompare() -> Dict[str, Any]:
    items = _load_historical_items()
    results: List[Dict[str, Any]] = []
    for item in items:
        image_path = _resolve_public_image(str(item.get("image") or ""))
        if image_path is None:
            continue
        category = _main_category(item.get("mainCategory") or item.get("category"))
        rarity = str(item.get("rarity") or "").upper()
        try:
            with Image.open(image_path) as image:
                descriptors = _descriptor_variants(image, catalog=True)
        except Exception:
            continue
        matches = _best_catalog_matches(descriptors, category, rarity)
        status = _match_status(matches)
        if status not in {"existing", "review"} or not matches:
            continue
        distance, match = matches[0]
        results.append(
            {
                "historicalId": str(item.get("id") or ""),
                "historicalImage": str(item.get("image") or ""),
                "period": str(item.get("implementationPeriod") or ""),
                "category": category,
                "rarity": rarity,
                "status": status,
                "match": {
                    "id": match["id"],
                    "name": match["name"],
                    "gachaTitle": match["gachaTitle"],
                    "gachaSlug": match["gachaSlug"],
                    "image": match["image"],
                    "distance": round(distance, 4),
                    "similarity": max(0, min(100, round((1 - distance / 0.42) * 100))),
                },
            }
        )
    return {"items": results, "historicalCount": len(items), "catalogItemCount": len(_catalog_items())}


def reconcile(payload: Dict[str, Any]) -> Dict[str, Any]:
    identifiers = payload.get("historicalIds")
    if not isinstance(identifiers, list) or not identifiers:
        raise AppError("統合するアイテムを選択してください。")
    selected = {str(value) for value in identifiers}
    existing = _load_historical_items()
    current_ids = {str(item.get("id") or "") for item in existing}
    if not selected <= current_ids:
        raise AppError("登録済みでない過去アイテムが選択されています。")
    remaining = [item for item in existing if str(item.get("id") or "") not in selected]
    image_sources: Dict[str, Path] = {}

    # _publish_transaction copies incoming images but leaves old files. Remove
    # only the selected historical images inside its rollback-protected window.
    staged = _run(["git", "diff", "--cached", "--name-only"], check=False).stdout.strip()
    if staged:
        raise AppError("ステージ済みの変更があります。別の保存処理を完了してから再実行してください。")
    targets = [HISTORICAL_DATA_PATH, HISTORICAL_IMAGE_DIR, SITEMAP_PATH]
    with tempfile.TemporaryDirectory(prefix="aimy-historical-reconcile-") as temp_name:
        backups = _create_backups(targets, Path(temp_name))
        committed = False
        try:
            for identifier in selected:
                (HISTORICAL_IMAGE_DIR / f"{identifier}.png").unlink(missing_ok=True)
            HISTORICAL_DATA_PATH.write_text(_render_historical_items(remaining), encoding="utf-8")
            _run(["npm", "run", "build"])
            sitemap_backup = next(record for record in backups if record.path == SITEMAP_PATH)
            if SITEMAP_PATH.exists():
                SITEMAP_PATH.unlink()
            if sitemap_backup.existed:
                shutil.copy2(sitemap_backup.backup, SITEMAP_PATH)
            paths = [
                str(HISTORICAL_DATA_PATH.relative_to(PROJECT_ROOT)),
                str(HISTORICAL_IMAGE_DIR.relative_to(PROJECT_ROOT)),
            ]
            _run(["git", "diff", "--check", "--", *paths])
            _run(["git", "add", "-A", "--", *paths])
            if _run(["git", "diff", "--cached", "--quiet"], check=False).returncode != 0:
                _run(["git", "commit", "-m", f"Reconcile {len(selected)} historical Aimy items"])
                committed = True
                _run(["git", "push"])
        except Exception:
            if not committed:
                _run(
                    [
                        "git",
                        "reset",
                        "--",
                        str(HISTORICAL_DATA_PATH.relative_to(PROJECT_ROOT)),
                        str(HISTORICAL_IMAGE_DIR.relative_to(PROJECT_ROOT)),
                    ],
                    check=False,
                )
                _restore_backups(backups)
            raise
    CATALOG_CACHE["signature"] = None
    return {"removed": len(selected), "remaining": len(remaining)}


class Handler(BaseHTTPRequestHandler):
    server_version = "AimyHistoricalItems/1.0"

    def log_message(self, format_string: str, *args: Any) -> None:
        sys.stdout.write("%s - %s\n" % (self.log_date_time_string(), format_string % args))

    def _send_bytes(self, body: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, value: Any, status: int = 200) -> None:
        self._send_bytes(_json_bytes(value), "application/json; charset=utf-8", status)

    def _send_error_json(self, error: Exception, status: int = 400) -> None:
        self._send_json({"ok": False, "error": str(error)}, status)

    def _read_json(self) -> Dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise AppError("リクエストサイズが不正です。") from error
        if length <= 0 or length > 220_000_000:
            raise AppError("送信データの容量が不正です。")
        try:
            value = json.loads(self.rfile.read(length))
        except json.JSONDecodeError as error:
            raise AppError("送信データを読み取れませんでした。") from error
        if not isinstance(value, dict):
            raise AppError("送信データの形式が不正です。")
        return value

    def do_GET(self) -> None:  # noqa: N802
        try:
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path == "/":
                self._send_bytes(HTML_PATH.read_bytes(), "text/html; charset=utf-8")
                return
            if parsed.path == "/api/summary":
                self._send_json(
                    {
                        "ok": True,
                        "catalogItemCount": _catalog_item_count(),
                        "historicalItemCount": len(_load_historical_items()),
                        "categories": list(MAIN_CATEGORIES),
                    }
                )
                return
            if parsed.path == "/api/recompare":
                self._send_json({"ok": True, "result": recompare()})
                return
            if parsed.path == "/api/media":
                query = urllib.parse.parse_qs(parsed.query)
                session_id = str(query.get("session", [""])[0])
                candidate = str(query.get("candidate", [""])[0])
                if not re.fullmatch(r"c\d{4}", candidate):
                    raise AppError("画像指定が不正です。")
                path = _session_dir(session_id) / "candidates" / f"{candidate}.png"
                if not path.is_file():
                    raise AppError("候補画像が見つかりません。")
                self._send_bytes(path.read_bytes(), "image/png")
                return
            if parsed.path == "/api/public-media":
                query = urllib.parse.parse_qs(parsed.query)
                image_value = str(query.get("path", [""])[0])
                path = _resolve_public_image(image_value)
                if path is None:
                    raise AppError("登録画像が見つかりません。")
                content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
                self._send_bytes(path.read_bytes(), content_type)
                return
            self.send_error(404)
        except AppError as error:
            self._send_error_json(error, 400)
        except Exception as error:
            traceback.print_exc()
            self._send_error_json(error, 500)

    def do_POST(self) -> None:  # noqa: N802
        try:
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path == "/api/analyze":
                self._send_json({"ok": True, "result": analyze(self._read_json())})
                return
            if parsed.path not in {"/api/publish", "/api/reconcile"}:
                self.send_error(404)
                return
            if not SAVE_LOCK.acquire(blocking=False):
                raise AppError("別の保存処理が実行中です。完了するまで待ってください。")
            try:
                result = (
                    publish(self._read_json())
                    if parsed.path == "/api/publish"
                    else reconcile(self._read_json())
                )
            finally:
                SAVE_LOCK.release()
            self._send_json({"ok": True, "result": result})
        except AppError as error:
            self._send_error_json(error, 400)
        except Exception as error:
            traceback.print_exc()
            self._send_error_json(error, 500)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def main() -> int:
    if not HTML_PATH.is_file():
        print(f"UI file not found: {HTML_PATH}", file=sys.stderr)
        return 1
    try:
        catalog_count = _catalog_item_count()
        historical_count = len(_load_historical_items())
    except AppError as error:
        print(error, file=sys.stderr)
        return 1
    WORK_ROOT.mkdir(parents=True, exist_ok=True)
    port = _free_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print("=" * 68)
    print("Aimy 2.5周年・過去アイテム取込ツールを起動しました")
    print(f"照合対象: 現在登録済みのSR・SSRアイテム {catalog_count}件")
    print(f"登録済みのガチャ未特定アイテム: {historical_count}件")
    print(url)
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
