#!/usr/bin/env python3
"""Manual, comprehensive editor for existing Aimy gacha data.

The editor intentionally does not detect or crop replacement images. The user
supplies already-cropped banner/item images, and the original bytes are kept.
"""

from __future__ import annotations

import base64
import binascii
import json
import mimetypes
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import traceback
import urllib.parse
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from PIL import Image


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
HTML_PATH = SCRIPT_DIR / "edit_gacha.html"
REGISTRY_PATH = PROJECT_ROOT / "src" / "data" / "gachas.js"
PUBLIC_ROOT = (PROJECT_ROOT / "public").resolve()
DATA_DIR = PROJECT_ROOT / "src" / "data" / "gachas"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
FORMAT_EXTENSIONS = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}
RARITIES = {"SSR", "SR", "R", "NR", "N"}
CATEGORIES = (
    "衣装",
    "髪型",
    "あたま",
    "めがね",
    "ピアス",
    "目",
    "メイク",
    "口",
    "鼻",
    "まゆげ",
    "背景",
    "チェキフレーム",
    "イベント",
    "未分類",
)
CATEGORY_ALIASES = {
    "服": "衣装",
    "髪": "髪型",
    "髪飾り": "あたま",
    "メガネ": "めがね",
    "眼鏡": "めがね",
    "耳": "ピアス",
    "耳飾り": "ピアス",
    "眉毛": "まゆげ",
}
DATE_PATTERN = re.compile(r"^(\d{4})/(\d{1,2})/(\d{1,2})\s+(\d{1,2}):(\d{2})$")
SAVE_LOCK = threading.Lock()


class AppError(RuntimeError):
    pass


@dataclass(frozen=True)
class RegistryEntry:
    variable: str
    module_name: str
    data_file: Path


@dataclass(frozen=True)
class BackupRecord:
    path: Path
    existed: bool
    was_directory: bool
    backup: Path


def _field_pattern(field: str) -> re.Pattern[str]:
    return re.compile(
        rf"^(\s*{re.escape(field)}\s*:\s*)'((?:\\.|[^'\\])*)'(\s*,?\s*)$",
        flags=re.MULTILINE,
    )


def _decode_js_string(value: str) -> str:
    replacements = {"n": "\n", "r": "\r", "t": "\t"}

    def replace(match: re.Match[str]) -> str:
        escaped = match.group(1)
        return replacements.get(escaped, escaped)

    return re.sub(r"\\(.)", replace, value)


def _read_field(text: str, field: str) -> str:
    match = _field_pattern(field).search(text)
    if not match:
        raise AppError(f"{field} をデータファイルから読み取れませんでした。")
    return _decode_js_string(match.group(2))


def _js_string(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace("\r", "\\r")
        .replace("\n", "\\n")
        .replace("\t", "\\t")
    )


def _entry_start_timestamp(entry: RegistryEntry) -> float:
    try:
        text = entry.data_file.read_text(encoding="utf-8")
        value = _read_field(text, "startDate")
        parsed = datetime.strptime(value, "%Y/%m/%d %H:%M")
        return parsed.timestamp()
    except (AppError, OSError, UnicodeError, ValueError):
        return float("-inf")


def _registered_entries() -> List[RegistryEntry]:
    if not REGISTRY_PATH.is_file():
        raise AppError("src/data/gachas.js が見つかりません。")
    registry = REGISTRY_PATH.read_text(encoding="utf-8")
    matches = re.findall(
        r"^import\s+([A-Za-z_$][\w$]*)\s+from\s+['\"]\./gachas/([^'\"]+)['\"]",
        registry,
        flags=re.MULTILINE,
    )
    entries: List[RegistryEntry] = []
    seen: set[Path] = set()
    for variable, module_name in matches:
        data_file = DATA_DIR / f"{module_name}.js"
        if data_file.is_file() and data_file not in seen:
            entries.append(RegistryEntry(variable, module_name, data_file))
            seen.add(data_file)
    entries.sort(key=_entry_start_timestamp, reverse=True)
    return entries


def _entry_summary(entry: RegistryEntry) -> Dict[str, Any]:
    text = entry.data_file.read_text(encoding="utf-8")
    slug = _read_field(text, "slug")
    title = _read_field(text, "title")
    identifier = _read_field(text, "id")
    banner = _read_field(text, "banner")
    banner_path = _resolve_public_image(banner, allow_missing=True)
    version = banner_path.stat().st_mtime_ns if banner_path.is_file() else 0
    return {
        "id": identifier,
        "slug": slug,
        "title": title,
        "banner": banner,
        "bannerExists": banner_path.is_file(),
        "bannerUrl": _media_url(banner, version),
        "dataFile": str(entry.data_file.relative_to(PROJECT_ROOT)),
        "moduleName": entry.module_name,
    }


def _summaries() -> List[Dict[str, Any]]:
    return [_entry_summary(entry) for entry in _registered_entries()]


def _find_entry(slug: str) -> Tuple[RegistryEntry, Dict[str, Any]]:
    for entry in _registered_entries():
        summary = _entry_summary(entry)
        if summary["slug"] == slug:
            return entry, summary
    raise AppError("選択したガチャが見つかりません。")


NODE_LOAD_ONE = """
import { pathToFileURL } from 'node:url';
const file = process.argv[1];
const url = pathToFileURL(file).href + '?aimy=' + Date.now();
const value = (await import(url)).default;
process.stdout.write(JSON.stringify(value));
"""

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
        raise AppError(f"ガチャデータを読み取れませんでした。\n{detail}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise AppError("ガチャデータの解析結果が不正です。") from error


def _load_module(data_file: Path) -> Dict[str, Any]:
    value = _run_node(NODE_LOAD_ONE, arguments=[str(data_file)])
    if not isinstance(value, dict):
        raise AppError("ガチャデータがオブジェクトではありません。")
    return value


def _load_all_modules() -> List[Dict[str, Any]]:
    files = [str(entry.data_file) for entry in _registered_entries()]
    values = _run_node(NODE_LOAD_MANY, input_text=json.dumps(files, ensure_ascii=False))
    if not isinstance(values, list) or not all(isinstance(value, dict) for value in values):
        raise AppError("全ガチャデータを確認できませんでした。")
    return values


def _normalize_category(value: Any) -> str:
    category = str(value or "未分類").strip() or "未分類"
    return CATEGORY_ALIASES.get(category, category)


def _resolve_public_image(value: str, *, allow_missing: bool = False) -> Path:
    if not value.startswith("/") or value == "placeholder":
        raise AppError(f"画像パスが不正です: {value or '(空欄)'}")
    relative = Path(urllib.parse.unquote(value.lstrip("/")))
    if ".." in relative.parts or relative.suffix.lower() not in IMAGE_EXTENSIONS:
        raise AppError(f"画像パスが不正です: {value}")
    resolved = (PUBLIC_ROOT / relative).resolve()
    try:
        resolved.relative_to(PUBLIC_ROOT)
    except ValueError as error:
        raise AppError("画像パスがpublic配下ではありません。") from error
    if not allow_missing and not resolved.is_file():
        raise AppError(f"画像ファイルが見つかりません: {value}")
    return resolved


def _media_url(image_path: str, version: int = 0) -> str:
    return "/api/media?" + urllib.parse.urlencode({"path": image_path, "v": version})


def _gacha_detail(slug: str) -> Dict[str, Any]:
    entry, summary = _find_entry(slug)
    gacha = _load_module(entry.data_file)
    items: List[Dict[str, Any]] = []
    for index, raw_item in enumerate(gacha.get("items") or [], start=1):
        item = dict(raw_item)
        item["category"] = _normalize_category(item.get("category"))
        source_image = str(item.get("image") or "")
        image_url = ""
        if source_image and source_image != "placeholder":
            try:
                source_path = _resolve_public_image(source_image)
                image_url = _media_url(source_image, source_path.stat().st_mtime_ns)
            except AppError:
                image_url = ""
        item.update(
            {
                "sourceImage": source_image,
                "imageUrl": image_url,
                "clientKey": f"existing-{index}-{item.get('id', '')}",
                "hasMotion": bool(item.get("hasMotion", False)),
            }
        )
        items.append(item)

    detail = {
        "id": str(gacha.get("id") or summary["id"]),
        "slug": str(gacha.get("slug") or summary["slug"]),
        "title": str(gacha.get("title") or summary["title"]),
        "type": str(gacha.get("type") or ""),
        "banner": str(gacha.get("banner") or summary["banner"]),
        "bannerUrl": summary["bannerUrl"],
        "status": str(gacha.get("status") or "開催中"),
        "infoStatus": str(gacha.get("infoStatus") or "確認済み"),
        "startDate": str(gacha.get("startDate") or ""),
        "endDate": str(gacha.get("endDate") or ""),
        "description": str(gacha.get("description") or ""),
        "isPermanent": bool(gacha.get("isPermanent", False)),
        "items": items,
        "categories": list(CATEGORIES),
        "rarities": sorted(RARITIES, key=lambda value: ["SSR", "SR", "R", "NR", "N"].index(value)),
    }
    return detail


def _run_command(command: Sequence[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        list(command),
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
    )
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise AppError(f"コマンドに失敗しました: {' '.join(command)}\n{detail}")
    return result


def _decode_replacement(data_url: str, kind: str) -> Tuple[bytes, str, Tuple[int, int]]:
    match = re.fullmatch(
        r"data:image/(?:jpeg|jpg|png|webp);base64,([A-Za-z0-9+/=]+)",
        data_url,
    )
    if not match:
        raise AppError("差し替え画像を読み取れませんでした。PNG・JPEG・WebPを選んでください。")
    try:
        raw = base64.b64decode(match.group(1), validate=True)
    except (ValueError, binascii.Error) as error:
        raise AppError("差し替え画像のデータが壊れています。") from error
    if not raw or len(raw) > 35_000_000:
        raise AppError("差し替え画像の容量が大きすぎます。")

    try:
        import io

        with Image.open(io.BytesIO(raw)) as image:
            width, height = image.size
            image_format = str(image.format or "").upper()
            image.verify()
    except Exception as error:
        raise AppError("差し替え画像を画像として開けませんでした。") from error

    extension = FORMAT_EXTENSIONS.get(image_format)
    if not extension:
        raise AppError("PNG・JPEG・WebP以外の画像は使用できません。")
    if width < 40 or height < 40:
        raise AppError("差し替え画像が小さすぎます。")

    ratio = width / height
    if kind == "item" and not 0.90 <= ratio <= 1.10:
        raise AppError(
            f"アイテム画像は正方形に切り抜いたものを選んでください（現在 {width}×{height}）。"
        )
    if kind == "banner" and not 4.5 <= ratio <= 6.5:
        raise AppError(
            f"バナー画像は横長に切り抜いたものを選んでください（現在 {width}×{height}）。"
        )
    return raw, extension, (width, height)


def _parse_date(value: str, label: str) -> datetime:
    match = DATE_PATTERN.fullmatch(value.strip())
    if not match:
        raise AppError(f"{label}は『2026/08/01 15:00』の形式で入力してください。")
    try:
        return datetime(
            int(match.group(1)),
            int(match.group(2)),
            int(match.group(3)),
            int(match.group(4)),
            int(match.group(5)),
        )
    except ValueError as error:
        raise AppError(f"{label}に存在しない日時が入力されています。") from error


def _validate_metadata(incoming: Dict[str, Any], original_slug: str) -> Dict[str, Any]:
    fields = {
        key: str(incoming.get(key, "")).strip()
        for key in (
            "id",
            "slug",
            "title",
            "type",
            "status",
            "infoStatus",
            "startDate",
            "endDate",
            "description",
        )
    }
    if not fields["id"]:
        raise AppError("ガチャIDを入力してください。")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", fields["slug"]):
        raise AppError("slugは英小文字・数字・ハイフンだけで入力してください。")
    if not fields["title"]:
        raise AppError("ガチャ名を入力してください。")
    if not fields["type"]:
        raise AppError("ガチャ種類を入力してください。")
    if fields["status"] not in {"開催中", "開催終了"}:
        raise AppError("表示状態を選択してください。")
    if fields["infoStatus"] not in {"確認済み", "情報収集中"}:
        raise AppError("情報確認状態を選択してください。")
    if not fields["description"]:
        raise AppError("説明文を入力してください。")

    is_permanent = bool(incoming.get("isPermanent", False))
    if is_permanent:
        if not fields["startDate"]:
            fields["startDate"] = "常設"
        if not fields["endDate"]:
            fields["endDate"] = "終了予定なし"
    else:
        start = _parse_date(fields["startDate"], "開始日時")
        end = _parse_date(fields["endDate"], "終了日時")
        if end <= start:
            raise AppError("終了日時は開始日時より後にしてください。")

    for summary in _summaries():
        if summary["slug"] == original_slug:
            continue
        if summary["slug"] == fields["slug"]:
            raise AppError(f"同じslugのガチャがすでにあります: {fields['slug']}")
        if summary["id"] == fields["id"]:
            raise AppError(f"同じガチャIDがすでにあります: {fields['id']}")

    return {**fields, "isPermanent": is_permanent}


def _validate_items(
    incoming: Any,
    original_slug: str,
    all_gachas: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if not isinstance(incoming, list):
        raise AppError("アイテム一覧を読み取れませんでした。")
    other_ids = {
        str(item.get("id") or "")
        for gacha in all_gachas
        if str(gacha.get("slug") or "") != original_slug
        for item in (gacha.get("items") or [])
    }
    seen: set[str] = set()
    validated: List[Dict[str, Any]] = []
    for index, raw in enumerate(incoming, start=1):
        if not isinstance(raw, dict):
            raise AppError(f"{index:02d}番のアイテム情報が不正です。")
        identifier = str(raw.get("id") or "").strip()
        name = str(raw.get("name") or "").strip()
        rarity = str(raw.get("rarity") or "").strip().upper()
        category = _normalize_category(raw.get("category"))
        source_image = str(raw.get("sourceImage") or "").strip()
        replacement = str(raw.get("replacementDataUrl") or "").strip()
        if not identifier:
            raise AppError(f"{index:02d}番のアイテムIDを入力してください。")
        if identifier in seen or identifier in other_ids:
            raise AppError(f"アイテムIDが重複しています: {identifier}")
        if not name:
            raise AppError(f"{index:02d}番のアイテム名を入力してください。")
        if rarity not in RARITIES:
            raise AppError(f"{index:02d}番のレアリティを確認してください。")
        if not category:
            raise AppError(f"{index:02d}番のカテゴリを確認してください。")
        if not replacement and (not source_image or source_image == "placeholder"):
            raise AppError(f"{index:02d}番のアイテム画像を選択してください。")
        seen.add(identifier)
        validated.append(
            {
                "id": identifier,
                "name": name,
                "rarity": rarity,
                "category": category,
                "hasMotion": bool(raw.get("hasMotion", False)),
                "sourceImage": source_image,
                "replacementDataUrl": replacement,
            }
        )
    return validated


def _render_gacha(metadata: Dict[str, Any], banner: str, items: Sequence[Dict[str, Any]]) -> str:
    lines = [
        "const gacha = {",
        f"  id: '{_js_string(metadata['id'])}',",
        f"  slug: '{_js_string(metadata['slug'])}',",
        f"  title: '{_js_string(metadata['title'])}',",
        f"  type: '{_js_string(metadata['type'])}',",
        f"  banner: '{_js_string(banner)}',",
        f"  status: '{_js_string(metadata['status'])}',",
        f"  infoStatus: '{_js_string(metadata['infoStatus'])}',",
        f"  startDate: '{_js_string(metadata['startDate'])}',",
        f"  endDate: '{_js_string(metadata['endDate'])}',",
        f"  description: '{_js_string(metadata['description'])}',",
    ]
    if metadata.get("isPermanent"):
        lines.append("  isPermanent: true,")
    lines.append("  items: [")
    for item in items:
        lines.extend(
            [
                "    {",
                f"      id: '{_js_string(item['id'])}',",
                f"      rarity: '{_js_string(item['rarity'])}',",
                f"      category: '{_js_string(item['category'])}',",
                f"      name: '{_js_string(item['name'])}',",
            ]
        )
        if item.get("hasMotion"):
            lines.append("      hasMotion: true,")
        lines.extend(
            [
                f"      image: '{_js_string(item['image'])}',",
                "    },",
            ]
        )
    lines.extend(["  ],", "}", "", "export default gacha", ""])
    return "\n".join(lines)


def _replace_directory(source: Path, destination: Path) -> None:
    if destination.exists():
        if destination.is_dir() and not destination.is_symlink():
            shutil.rmtree(destination)
        else:
            destination.unlink()
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination)


def _unique_paths(paths: Iterable[Path]) -> List[Path]:
    result: List[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path.resolve(strict=False))
        if key not in seen:
            result.append(path)
            seen.add(key)
    return result


def _create_backups(paths: Sequence[Path], backup_root: Path) -> List[BackupRecord]:
    records: List[BackupRecord] = []
    for index, path in enumerate(_unique_paths(paths)):
        existed = path.exists()
        was_directory = path.is_dir() and not path.is_symlink()
        backup = backup_root / f"{index:02d}"
        if existed:
            if was_directory:
                shutil.copytree(path, backup)
            else:
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, backup)
        records.append(BackupRecord(path, existed, was_directory, backup))
    return records


def _restore_backups(records: Sequence[BackupRecord]) -> None:
    for record in records:
        if record.path.exists() or record.path.is_symlink():
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


def _registry_for_slug_change(entry: RegistryEntry, new_slug: str) -> str:
    original = REGISTRY_PATH.read_text(encoding="utf-8")
    old_import = f"./gachas/{entry.module_name}"
    new_import = f"./gachas/{new_slug}"
    if old_import not in original:
        raise AppError("ガチャ一覧のimport行を見つけられませんでした。")
    return original.replace(old_import, new_import, 1)


def update_gacha(payload: Dict[str, Any]) -> Dict[str, Any]:
    original_slug = str(payload.get("originalSlug") or "").strip()
    entry, original_summary = _find_entry(original_slug)
    original_gacha = _load_module(entry.data_file)
    metadata_raw = payload.get("gacha")
    if not isinstance(metadata_raw, dict):
        raise AppError("ガチャ基本情報を読み取れませんでした。")
    metadata = _validate_metadata(metadata_raw, original_slug)
    all_gachas = _load_all_modules()
    items = _validate_items(payload.get("items"), original_slug, all_gachas)
    new_slug = metadata["slug"]
    slug_changed = new_slug != original_slug

    old_data_file = entry.data_file
    new_data_file = DATA_DIR / (f"{new_slug}.js" if slug_changed else old_data_file.name)
    old_items_dir = PROJECT_ROOT / "public" / "images" / "items" / original_slug
    new_items_dir = PROJECT_ROOT / "public" / "images" / "items" / new_slug
    old_gacha_dir = PROJECT_ROOT / "public" / "images" / "gacha" / original_slug
    new_gacha_dir = PROJECT_ROOT / "public" / "images" / "gacha" / new_slug
    sitemap_file = PROJECT_ROOT / "public" / "sitemap.xml"

    if slug_changed:
        for path, label in (
            (new_data_file, "データファイル"),
            (new_items_dir, "アイテム画像フォルダ"),
            (new_gacha_dir, "ガチャ画像フォルダ"),
        ):
            if path.exists():
                raise AppError(f"変更後slugの{label}がすでに存在します: {path.name}")

    staged_before = _run_command(["git", "diff", "--cached", "--name-only"], check=False).stdout.strip()
    if staged_before:
        raise AppError(
            "保存前からステージ済みの変更があります。誤って一緒に公開しないため停止しました。\n"
            + staged_before
        )

    banner_replacement = str(payload.get("bannerDataUrl") or "").strip()
    old_banner_value = str(original_gacha.get("banner") or original_summary["banner"])
    old_banner_file = _resolve_public_image(old_banner_value)
    old_banner_bytes = old_banner_file.read_bytes()
    old_banner_extension = old_banner_file.suffix.lower()

    committed = False
    commit_message = f"Update {metadata['title']} gacha"
    with tempfile.TemporaryDirectory(prefix="aimy-gacha-editor-") as temp_name:
        temp_root = Path(temp_name)
        stage_items = temp_root / "stage-items"
        stage_gacha = temp_root / "stage-gacha"
        backup_root = temp_root / "backups"
        stage_items.mkdir(parents=True)
        if old_gacha_dir.is_dir():
            shutil.copytree(old_gacha_dir, stage_gacha)
        else:
            stage_gacha.mkdir(parents=True)

        rendered_items: List[Dict[str, Any]] = []
        for index, item in enumerate(items, start=1):
            replacement = item.pop("replacementDataUrl")
            source_image = item.pop("sourceImage")
            if replacement:
                raw, extension, _ = _decode_replacement(replacement, "item")
            else:
                source_path = _resolve_public_image(source_image)
                raw = source_path.read_bytes()
                extension = source_path.suffix.lower()
                if extension == ".jpeg":
                    extension = ".jpg"
            filename = f"{index:02d}{extension}"
            (stage_items / filename).write_bytes(raw)
            rendered_items.append(
                {
                    **item,
                    "image": f"/images/items/{new_slug}/{filename}",
                }
            )

        for candidate in list(stage_gacha.iterdir()):
            if candidate.is_file() and candidate.stem.lower() == "banner" and candidate.suffix.lower() in IMAGE_EXTENSIONS:
                candidate.unlink()
        if banner_replacement:
            banner_bytes, banner_extension, _ = _decode_replacement(banner_replacement, "banner")
        else:
            banner_bytes = old_banner_bytes
            banner_extension = ".jpg" if old_banner_extension == ".jpeg" else old_banner_extension
        banner_filename = f"banner{banner_extension}"
        (stage_gacha / banner_filename).write_bytes(banner_bytes)
        banner_value = f"/images/gacha/{new_slug}/{banner_filename}"

        rendered_data = _render_gacha(metadata, banner_value, rendered_items)
        registry_text = (
            _registry_for_slug_change(entry, new_slug)
            if slug_changed
            else REGISTRY_PATH.read_text(encoding="utf-8")
        )

        transaction_paths = _unique_paths(
            [
                REGISTRY_PATH,
                sitemap_file,
                old_data_file,
                new_data_file,
                old_items_dir,
                new_items_dir,
                old_gacha_dir,
                new_gacha_dir,
            ]
        )
        backups = _create_backups(transaction_paths, backup_root)
        relative_paths = [str(path.relative_to(PROJECT_ROOT)) for path in transaction_paths]

        try:
            if slug_changed:
                old_data_file.unlink(missing_ok=True)
                if old_items_dir.exists():
                    shutil.rmtree(old_items_dir)
                if old_gacha_dir.exists():
                    shutil.rmtree(old_gacha_dir)
            new_data_file.parent.mkdir(parents=True, exist_ok=True)
            new_data_file.write_text(rendered_data, encoding="utf-8")
            REGISTRY_PATH.write_text(registry_text, encoding="utf-8")
            _replace_directory(stage_items, new_items_dir)
            _replace_directory(stage_gacha, new_gacha_dir)

            build = _run_command(["npm", "run", "build"])
            _run_command(["git", "diff", "--check", "--", *relative_paths])
            _run_command(["git", "add", "-A", "--", *relative_paths])
            no_changes = _run_command(["git", "diff", "--cached", "--quiet"], check=False).returncode == 0
            if no_changes:
                raise AppError("ファイル内容に変更がありませんでした。")

            _run_command(["git", "commit", "-m", commit_message])
            committed = True
            try:
                _run_command(["git", "push"])
            except AppError as error:
                raise AppError(
                    "修正とcommitは完了しましたが、GitHubへのpushに失敗しました。\n"
                    "通信を確認して、ターミナルで git push を実行してください。\n"
                    f"{error}"
                ) from error

            return {
                "slug": new_slug,
                "oldSlug": original_slug,
                "title": metadata["title"],
                "itemCount": len(rendered_items),
                "bannerChanged": bool(banner_replacement),
                "slugChanged": slug_changed,
                "build": "成功",
                "commit": commit_message,
                "push": "完了",
                "sitePath": f"/gacha/{new_slug}",
                "buildLog": build.stdout[-1500:],
            }
        except Exception:
            if not committed:
                _restore_backups(backups)
                _run_command(["git", "reset", "--", *relative_paths], check=False)
            raise


class Handler(BaseHTTPRequestHandler):
    server_version = "AimyGachaEditor/2.0"

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

    def _send_error_json(self, error: Exception, status: int) -> None:
        traceback.print_exc()
        self._send_json({"ok": False, "error": str(error)}, status)

    def _read_json(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > 200_000_000:
            raise AppError("送信データのサイズが不正です。")
        try:
            value = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise AppError("送信内容を読み取れませんでした。") from error
        if not isinstance(value, dict):
            raise AppError("送信内容が不正です。")
        return value

    def do_GET(self) -> None:  # noqa: N802
        try:
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path == "/":
                self._send_bytes(HTML_PATH.read_bytes(), "text/html; charset=utf-8")
                return
            if parsed.path == "/api/gachas":
                self._send_json({"ok": True, "gachas": _summaries()})
                return
            if parsed.path.startswith("/api/gacha/"):
                slug = urllib.parse.unquote(parsed.path[len("/api/gacha/") :])
                self._send_json({"ok": True, "gacha": _gacha_detail(slug)})
                return
            if parsed.path == "/api/media":
                query = urllib.parse.parse_qs(parsed.query)
                image_value = query.get("path", [""])[0]
                image_path = _resolve_public_image(image_value)
                content_type = mimetypes.guess_type(image_path.name)[0] or "application/octet-stream"
                self._send_bytes(image_path.read_bytes(), content_type)
                return
            self.send_error(404)
        except AppError as error:
            self._send_error_json(error, 400)
        except Exception as error:
            self._send_error_json(error, 500)

    def do_POST(self) -> None:  # noqa: N802
        try:
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path != "/api/save":
                self.send_error(404)
                return
            if not SAVE_LOCK.acquire(blocking=False):
                raise AppError("別の保存処理が実行中です。完了するまで待ってください。")
            try:
                result = update_gacha(self._read_json())
            finally:
                SAVE_LOCK.release()
            self._send_json({"ok": True, "result": result})
        except AppError as error:
            self._send_error_json(error, 400)
        except Exception as error:
            self._send_error_json(error, 500)


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def main() -> int:
    if not HTML_PATH.is_file():
        print(f"UI file not found: {HTML_PATH}", file=sys.stderr)
        return 1
    try:
        count = len(_summaries())
    except AppError as error:
        print(error, file=sys.stderr)
        return 1

    port = _find_free_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print("=" * 64)
    print("Aimy 既存ガチャ総合修正ツールを起動しました")
    print(f"登録済みガチャ: {count}件")
    print(url)
    print("このターミナルを閉じるとツールも終了します。")
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
