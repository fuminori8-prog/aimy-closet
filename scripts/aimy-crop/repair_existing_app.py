#!/usr/bin/env python3
"""Aimy Closet: repair item-image mappings for an existing gacha.

This local-only tool reads screenshots already stored in
public/images/gacha/<slug>. It deliberately performs no automatic duplicate
removal. The user can insert missing item records, manually crop undetected
cards, keep a valid current image, or exclude genuine duplicate candidates
before publishing the mapping.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import threading
import tempfile
import traceback
import urllib.parse
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

from PIL import Image

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
HTML_PATH = SCRIPT_DIR / "repair_existing.html"
WORK_ROOT = Path(tempfile.gettempdir()) / "aimy-closet-repair-work"
DATA_INDEX = PROJECT_ROOT / "src" / "data" / "gachas.js"
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
STANDARD_CATEGORIES = [
    "衣装",
    "目",
    "髪型",
    "あたま",
    "めがね",
    "ピアス",
    "メイク",
    "チェキフレーム",
    "背景",
    "イベント",
]

import sys

sys.path.insert(0, str(SCRIPT_DIR))
from detect_cards import _detect_boxes, _estimate_rarity  # noqa: E402


class AppError(RuntimeError):
    """A user-facing validation or operation error."""


SESSIONS: Dict[str, Dict[str, Any]] = {}
SESSION_LOCK = threading.Lock()
PUBLISH_LOCK = threading.Lock()


def _natural_key(value: str) -> List[Any]:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", value)]


def _run(command: Sequence[str], *, timeout: int = 180) -> str:
    proc = subprocess.run(
        list(command),
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )
    output = proc.stdout.strip()
    if proc.returncode != 0:
        shown = output[-6000:] if output else "（出力なし）"
        raise AppError(f"コマンドに失敗しました: {' '.join(command)}\n\n{shown}")
    return output


def _load_gachas() -> List[Dict[str, Any]]:
    if not DATA_INDEX.exists():
        raise AppError(f"ガチャ一覧が見つかりません: {DATA_INDEX}")

    node_script = r"""
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
const indexPath = process.argv[1];
const root = path.dirname(indexPath);
const source = fs.readFileSync(indexPath, 'utf8');
const imports = [...source.matchAll(/from\s+['\"](\.\/gachas\/[^'\"]+)['\"]/g)].map(x => x[1]);
const result = [];
for (const rel of imports) {
  const file = path.resolve(root, rel.endsWith('.js') ? rel : `${rel}.js`);
  const mod = await import(`${pathToFileURL(file).href}?mtime=${fs.statSync(file).mtimeMs}`);
  const gacha = mod.default;
  result.push({
    slug: gacha.slug,
    title: gacha.title,
    items: gacha.items,
    dataFile: file,
  });
}
process.stdout.write(JSON.stringify(result));
"""
    proc = subprocess.run(
        ["node", "--input-type=module", "-e", node_script, str(DATA_INDEX)],
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=45,
        check=False,
    )
    if proc.returncode != 0:
        raise AppError(f"既存ガチャデータを読み込めませんでした。\n{proc.stderr[-3000:]}")
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as ex:
        raise AppError("既存ガチャデータの解析結果が不正です。") from ex

    seen: set[str] = set()
    gachas: List[Dict[str, Any]] = []
    for entry in payload:
        slug = str(entry.get("slug", ""))
        if not slug or slug in seen:
            continue
        seen.add(slug)
        entry["dataFile"] = str(Path(entry["dataFile"]).resolve())
        gachas.append(entry)
    return gachas


def _get_gacha(slug: str) -> Dict[str, Any]:
    for gacha in _load_gachas():
        if gacha["slug"] == slug:
            return gacha
    raise AppError(f"ガチャが見つかりません: {slug}")


def _source_files(slug: str) -> List[Path]:
    source_dir = PROJECT_ROOT / "public" / "images" / "gacha" / slug
    if not source_dir.is_dir():
        raise AppError(f"元スクショフォルダが見つかりません: {source_dir}")
    files = [
        path
        for path in source_dir.iterdir()
        if path.is_file()
        and not path.name.startswith(".")
        and path.suffix.lower() in IMAGE_EXTS
        and "banner" not in path.name.lower()
    ]
    files.sort(key=lambda path: _natural_key(path.name))
    if not files:
        raise AppError("元スクショがありません。banner以外の画像を確認してください。")
    return files


def _has_source_files(slug: str) -> bool:
    source_dir = PROJECT_ROOT / "public" / "images" / "gacha" / slug
    if not source_dir.is_dir():
        return False
    return any(
        path.is_file()
        and not path.name.startswith(".")
        and path.suffix.lower() in IMAGE_EXTS
        and "banner" not in path.name.lower()
        for path in source_dir.iterdir()
    )


def _source_signature(gacha: Dict[str, Any], sources: Sequence[Path]) -> str:
    digest = hashlib.sha256()
    data_path = Path(gacha["dataFile"])
    for path in [data_path, *sources]:
        stat = path.stat()
        digest.update(str(path.resolve()).encode("utf-8"))
        digest.update(str(stat.st_size).encode("ascii"))
        digest.update(str(stat.st_mtime_ns).encode("ascii"))
    return digest.hexdigest()


def _crop_card(image: Image.Image, box: Tuple[int, int, int, int]) -> Image.Image:
    crop = image.crop(box).convert("RGBA")
    if crop.size != (192, 192):
        crop = crop.resize((192, 192), Image.Resampling.LANCZOS)
    return crop


def _candidate_payload(session: Dict[str, Any]) -> List[Dict[str, Any]]:
    token = str(session["token"])
    payload: List[Dict[str, Any]] = []
    for index, candidate in enumerate(session["candidates"], start=1):
        public = dict(candidate)
        public["index"] = index
        public["imageUrl"] = f"/candidate/{token}/{urllib.parse.quote(str(candidate['output']))}"
        payload.append(public)
    return payload


def _analyze(slug: str) -> Dict[str, Any]:
    gacha = _get_gacha(slug)
    sources = _source_files(slug)
    token = secrets.token_urlsafe(18)
    work_dir = WORK_ROOT / token
    generated_dir = work_dir / "items"
    generated_dir.mkdir(parents=True, exist_ok=True)

    candidates: List[Dict[str, Any]] = []
    for source_index, source in enumerate(sources, start=1):
        with Image.open(source) as opened:
            image = opened.convert("RGB")
            boxes = sorted(_detect_boxes(image), key=lambda box: (box[1], box[0]))
            for box in boxes:
                index = len(candidates) + 1
                candidate_key = f"auto-{index:04d}"
                output_name = f"{candidate_key}.png"
                _crop_card(image, tuple(box)).save(generated_dir / output_name, "PNG")
                candidates.append(
                    {
                        "key": candidate_key,
                        "index": index,
                        "output": output_name,
                        "source": source.name,
                        "sourceIndex": source_index,
                        "box": list(box),
                        "estimatedRarity": _estimate_rarity(image, tuple(box)),
                        "sourceUrl": f"/source/{urllib.parse.quote(slug)}/{urllib.parse.quote(source.name)}",
                    }
                )

    if not candidates:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise AppError("アイテム画像を1件も検出できませんでした。スクショの横幅を変えていないか確認してください。")

    expected = len(gacha.get("items", []))
    signature = _source_signature(gacha, sources)
    session = {
        "token": token,
        "slug": slug,
        "gacha": gacha,
        "sources": [str(path.resolve()) for path in sources],
        "signature": signature,
        "workDir": str(work_dir.resolve()),
        "candidates": candidates,
        "candidateCount": len(candidates),
    }
    with SESSION_LOCK:
        SESSIONS[token] = session

    categories = list(STANDARD_CATEGORIES)
    for item in gacha.get("items", []):
        category = str(item.get("category", "")).strip()
        if category and category not in categories:
            categories.append(category)

    items = []
    for index, item in enumerate(gacha.get("items", []), start=1):
        image_path = str(item.get("image", ""))
        filename = Path(image_path).name or f"{index:02d}.png"
        items.append(
            {
                "index": index,
                "id": item.get("id", ""),
                "name": item.get("name", ""),
                "rarity": item.get("rarity", ""),
                "category": item.get("category", ""),
                "hasMotion": bool(item.get("hasMotion", False)),
                "isNew": False,
                "currentImageUrl": f"/current/{urllib.parse.quote(slug)}/{urllib.parse.quote(filename)}",
            }
        )

    return {
        "token": token,
        "slug": slug,
        "title": gacha.get("title", slug),
        "sourceFolder": str((PROJECT_ROOT / "public" / "images" / "gacha" / slug).resolve()),
        "sources": [path.name for path in sources],
        "items": items,
        "candidates": _candidate_payload(session),
        "categories": categories,
        "expectedCount": expected,
        "candidateCount": len(candidates),
        "countMatches": expected == len(candidates),
    }


def _add_manual_candidate(payload: Dict[str, Any]) -> Dict[str, Any]:
    token = str(payload.get("token", ""))
    with SESSION_LOCK:
        session = SESSIONS.get(token)
    if not session:
        raise AppError("確認データの有効期限が切れました。もう一度読み取ってください。")

    slug = str(session["slug"])
    if str(payload.get("slug", "")) != slug:
        raise AppError("対象ガチャが一致しません。")
    gacha = _get_gacha(slug)
    sources = _source_files(slug)
    if _source_signature(gacha, sources) != session["signature"]:
        raise AppError("確認後に元スクショまたはデータが変更されました。もう一度読み取ってください。")

    source_name = str(payload.get("source", ""))
    source_by_name = {path.name: path for path in sources}
    source = source_by_name.get(source_name)
    if not source:
        raise AppError("選択した元スクショが見つかりません。")
    try:
        center_x = float(payload.get("centerX"))
        center_y = float(payload.get("centerY"))
    except (TypeError, ValueError) as ex:
        raise AppError("切り抜く位置が不正です。") from ex

    with Image.open(source) as opened:
        image = opened.convert("RGB")
        width, height = image.size
        if not (0 <= center_x < width and 0 <= center_y < height):
            raise AppError("クリック位置がスクショの外です。")
        card_size = max(64, round(192 * width / 1179))
        left = max(0, min(width - card_size, round(center_x - card_size / 2)))
        top = max(0, min(height - card_size, round(center_y - card_size / 2)))
        box = (left, top, left + card_size, top + card_size)
        candidate_key = f"manual-{secrets.token_hex(8)}"
        output_name = f"{candidate_key}.png"
        generated_dir = Path(session["workDir"]) / "items"
        _crop_card(image, box).save(generated_dir / output_name, "PNG")
        estimated_rarity = _estimate_rarity(image, box)

    before_key = str(payload.get("beforeCandidateKey", "")).strip()
    manual = {
        "key": candidate_key,
        "output": output_name,
        "source": source.name,
        "sourceIndex": sources.index(source) + 1,
        "box": list(box),
        "estimatedRarity": estimated_rarity,
        "sourceUrl": f"/source/{urllib.parse.quote(slug)}/{urllib.parse.quote(source.name)}",
        "manual": True,
    }
    with SESSION_LOCK:
        current = SESSIONS.get(token)
        if current is not session:
            raise AppError("確認データの有効期限が切れました。もう一度読み取ってください。")
        candidates = session["candidates"]
        if before_key:
            insert_at = next((index for index, value in enumerate(candidates) if value["key"] == before_key), -1)
            if insert_at < 0:
                raise AppError("追加位置の候補が見つかりません。画面を読み直してください。")
        else:
            insert_at = len(candidates)
        candidates.insert(insert_at, manual)
        session["candidateCount"] = len(candidates)
        public_candidates = _candidate_payload(session)

    return {
        "candidates": public_candidates,
        "candidateCount": len(public_candidates),
        "insertedKey": candidate_key,
    }


def _js_string(value: Any) -> str:
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace("\r", "")
        .replace("\n", "\\n")
    )


def _items_array_span(text: str) -> Tuple[int, int]:
    match = re.search(r"\bitems\s*:\s*\[", text)
    if not match:
        raise AppError("ガチャデータのitems配列が見つかりません。")
    start = text.find("[", match.start())
    depth = 0
    quote = ""
    escaped = False
    line_comment = False
    block_comment = False
    index = start
    while index < len(text):
        char = text[index]
        next_char = text[index + 1] if index + 1 < len(text) else ""
        if line_comment:
            if char == "\n":
                line_comment = False
            index += 1
            continue
        if block_comment:
            if char == "*" and next_char == "/":
                block_comment = False
                index += 2
            else:
                index += 1
            continue
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
            index += 1
            continue
        if char in {"'", '"', "`"}:
            quote = char
            index += 1
            continue
        if char == "/" and next_char == "/":
            line_comment = True
            index += 2
            continue
        if char == "/" and next_char == "*":
            block_comment = True
            index += 2
            continue
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return start, index + 1
        index += 1
    raise AppError("ガチャデータのitems配列終端が見つかりません。")


def _replace_items(data_path: Path, items: Sequence[Dict[str, Any]], slug: str) -> None:
    text = data_path.read_text(encoding="utf-8")
    start, end = _items_array_span(text)
    lines = ["["]
    for index, item in enumerate(items, start=1):
        lines.extend(
            [
                "    {",
                f"      id: '{_js_string(item['id'])}',",
                f"      rarity: '{_js_string(item['rarity'])}',",
                f"      category: '{_js_string(item['category'])}',",
                f"      name: '{_js_string(item['name'])}',",
                f"      image: '/images/items/{_js_string(slug)}/{index:02d}.png',",
            ]
        )
        if item.get("hasMotion"):
            lines.append("      hasMotion: true,")
        lines.extend(["    },"])
    lines.append("  ]")
    replacement = "\n".join(lines)
    updated = text[:start] + replacement + text[end:]
    temp_path = data_path.with_suffix(data_path.suffix + ".aimy-repair-tmp")
    temp_path.write_text(updated, encoding="utf-8")
    os.replace(temp_path, data_path)


def _restore_backup(backup_dir: Path, production_dir: Path, data_path: Path) -> None:
    backup_items = backup_dir / "items"
    backup_data = backup_dir / data_path.name
    if production_dir.exists():
        shutil.rmtree(production_dir)
    shutil.copytree(backup_items, production_dir)
    shutil.copy2(backup_data, data_path)


def _publish(payload: Dict[str, Any]) -> Dict[str, Any]:
    token = str(payload.get("token", ""))
    with SESSION_LOCK:
        session = SESSIONS.get(token)
    if not session:
        raise AppError("確認データの有効期限が切れました。もう一度読み取ってください。")

    slug = str(session["slug"])
    if str(payload.get("slug", "")) != slug:
        raise AppError("対象ガチャが一致しません。")
    gacha = _get_gacha(slug)
    sources = _source_files(slug)
    if _source_signature(gacha, sources) != session["signature"]:
        raise AppError("確認後に元スクショまたはデータが変更されました。もう一度読み取ってください。")

    original_items = gacha.get("items", [])
    expected = len(original_items)
    submitted_items = payload.get("items", [])
    if not isinstance(submitted_items, list) or len(submitted_items) < expected:
        raise AppError("既存アイテムが不足しています。既存登録は削除できません。")

    existing_by_id = {str(item.get("id", "")): item for item in original_items}
    original_ids = [str(item.get("id", "")) for item in original_items]
    submitted_existing_ids: List[str] = []
    normalized_items: List[Dict[str, Any]] = []
    used_ids = set(existing_by_id)
    used_client_keys: set[str] = set()
    id_stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    added_count = 0
    for submitted in submitted_items:
        category = str(submitted.get("category", "")).strip()
        if category not in STANDARD_CATEGORIES:
            raise AppError(f"選択できないカテゴリです: {category}")
        if submitted.get("isNew") is True:
            client_key = str(submitted.get("clientKey", "")).strip()
            name = str(submitted.get("name", "")).strip()
            rarity = str(submitted.get("rarity", "")).strip().upper()
            if not client_key or client_key in used_client_keys:
                raise AppError("追加アイテムの識別情報が不正です。")
            used_client_keys.add(client_key)
            if not name:
                raise AppError("追加アイテムの名前を入力してください。")
            if rarity not in {"SSR", "SR", "NR", "R", "N"}:
                raise AppError(f"追加アイテムのレアリティが不正です: {rarity}")
            added_count += 1
            suffix = added_count
            item_id = f"{slug}-added-{id_stamp}-{suffix:02d}"
            while item_id in used_ids:
                suffix += 1
                item_id = f"{slug}-added-{id_stamp}-{suffix:02d}"
            used_ids.add(item_id)
            normalized_items.append(
                {
                    "id": item_id,
                    "rarity": rarity,
                    "category": category,
                    "name": name,
                    "hasMotion": False,
                }
            )
            continue

        item_id = str(submitted.get("id", ""))
        if item_id not in existing_by_id:
            raise AppError(f"不明な既存アイテムIDです: {item_id}")
        if item_id in submitted_existing_ids:
            raise AppError(f"既存アイテムが重複しています: {item_id}")
        submitted_existing_ids.append(item_id)
        existing = dict(existing_by_id[item_id])
        existing["category"] = category
        normalized_items.append(existing)

    if submitted_existing_ids != original_ids:
        raise AppError("既存アイテムの不足または順序変更があります。追加以外の並び替えはできません。")

    target_count = len(normalized_items)
    image_assignments = payload.get("imageAssignments", [])
    if not isinstance(image_assignments, list) or len(image_assignments) != target_count:
        raise AppError("修正後の全アイテムに画像の割り当てが必要です。")
    candidate_by_key = {str(candidate["key"]): candidate for candidate in session["candidates"]}
    used_candidate_keys: set[str] = set()
    validated_assignments: List[Dict[str, str]] = []
    for submitted, assignment in zip(submitted_items, image_assignments):
        if not isinstance(assignment, dict):
            raise AppError("画像割り当ての形式が不正です。")
        mode = str(assignment.get("mode", ""))
        if mode == "candidate":
            candidate_key = str(assignment.get("candidateKey", ""))
            if candidate_key not in candidate_by_key:
                raise AppError("存在しない画像候補が選択されています。")
            if candidate_key in used_candidate_keys:
                raise AppError("同じ画像候補が複数回選択されています。")
            used_candidate_keys.add(candidate_key)
            validated_assignments.append({"mode": "candidate", "candidateKey": candidate_key})
            continue
        if mode == "current":
            if submitted.get("isNew") is True:
                raise AppError("新規追加アイテムには現在画像がありません。未検出画像を手動追加してください。")
            item_id = str(submitted.get("id", ""))
            existing = existing_by_id.get(item_id)
            if not existing:
                raise AppError("現在画像を維持する既存アイテムが見つかりません。")
            filename = Path(str(existing.get("image", ""))).name
            if not filename:
                raise AppError(f"現在画像のファイル名が不正です: {item_id}")
            validated_assignments.append({"mode": "current", "filename": filename, "itemId": item_id})
            continue
        raise AppError("画像の割り当てが未確認です。")

    checks = payload.get("checks", [])
    if not isinstance(checks, list) or len(checks) != target_count or not all(value is True for value in checks):
        raise AppError("全アイテムの確認チェックが完了していません。")

    if not PUBLISH_LOCK.acquire(blocking=False):
        raise AppError("別の反映処理が進行中です。完了までお待ちください。")

    data_path = Path(gacha["dataFile"])
    source_dir = PROJECT_ROOT / "public" / "images" / "gacha" / slug
    production_dir = PROJECT_ROOT / "public" / "images" / "items" / slug
    work_dir = Path(session["workDir"])
    generated_dir = work_dir / "items"
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = PROJECT_ROOT / "archive" / f"manual-item-repair-backup-{timestamp}" / slug
    committed = False
    try:
        staged_before = _run(["git", "diff", "--cached", "--name-only"], timeout=30)
        if staged_before.strip():
            raise AppError(
                "すでにGitへ追加済みの変更があります。誤って一緒に反映しないため停止しました。\n"
                f"追加済み: {staged_before}"
            )
        if not production_dir.is_dir():
            raise AppError(f"現在のアイテム画像フォルダが見つかりません: {production_dir}")

        backup_dir.mkdir(parents=True, exist_ok=False)
        shutil.copytree(source_dir, backup_dir / "source-screenshots")
        shutil.copytree(production_dir, backup_dir / "items")
        shutil.copy2(data_path, backup_dir / data_path.name)
        (backup_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "slug": slug,
                    "title": gacha.get("title", slug),
                    "createdAt": datetime.now().isoformat(timespec="seconds"),
                    "sources": [Path(path).name for path in session["sources"]],
                    "originalItemCount": expected,
                    "newItemCount": added_count,
                    "itemCount": target_count,
                    "imageAssignments": validated_assignments,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        publish_dir = work_dir / "publish-items"
        if publish_dir.exists():
            shutil.rmtree(publish_dir)
        publish_dir.mkdir(parents=True)
        for output_index, assignment in enumerate(validated_assignments, start=1):
            if assignment["mode"] == "candidate":
                candidate = candidate_by_key[assignment["candidateKey"]]
                source = generated_dir / str(candidate["output"])
            else:
                source = backup_dir / "items" / assignment["filename"]
            if not source.exists():
                raise AppError(f"割り当て画像が見つかりません: {source.name}")
            with Image.open(source) as image:
                if image.size != (192, 192):
                    raise AppError(f"割り当て画像サイズが不正です: {source.name} {image.size}")
            shutil.copy2(source, publish_dir / f"{output_index:02d}.png")

        if production_dir.exists():
            shutil.rmtree(production_dir)
        shutil.copytree(publish_dir, production_dir)

        _replace_items(data_path, normalized_items, slug)
        _run(["npm", "run", "lint"], timeout=180)
        build_log = _run(["npm", "run", "build"], timeout=300)

        image_rel = str(production_dir.relative_to(PROJECT_ROOT))
        source_rel = str(source_dir.relative_to(PROJECT_ROOT))
        data_rel = str(data_path.relative_to(PROJECT_ROOT))
        _run(["git", "add", "--", source_rel, image_rel, data_rel], timeout=60)
        staged = _run(["git", "diff", "--cached", "--name-only"], timeout=30)
        if not staged.strip():
            _restore_backup(backup_dir, production_dir, data_path)
            return {
                "changed": False,
                "message": "現在の登録・画像・カテゴリと同じだったため、GitHubへの反映は不要でした。",
                "backup": str(backup_dir.relative_to(PROJECT_ROOT)),
            }

        title = str(gacha.get("title", slug))
        _run(["git", "commit", "-m", f"Fix {title} item registration and image mapping"], timeout=90)
        committed = True
        push_log = _run(["git", "push"], timeout=180)
        with SESSION_LOCK:
            SESSIONS.pop(token, None)
        shutil.rmtree(work_dir, ignore_errors=True)
        return {
            "changed": True,
            "message": f"確認済み登録・画像・カテゴリをGitHubへ反映しました（新規追加 {added_count}件）。",
            "backup": str(backup_dir.relative_to(PROJECT_ROOT)),
            "buildSummary": build_log[-1200:],
            "pushSummary": push_log[-1200:],
        }
    except Exception:
        if backup_dir.exists() and not committed:
            try:
                _restore_backup(backup_dir, production_dir, data_path)
                subprocess.run(
                    [
                        "git",
                        "restore",
                        "--staged",
                        "--",
                        str(source_dir.relative_to(PROJECT_ROOT)),
                        str(production_dir.relative_to(PROJECT_ROOT)),
                        str(data_path.relative_to(PROJECT_ROOT)),
                    ],
                    cwd=PROJECT_ROOT,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            except Exception:
                traceback.print_exc()
        raise
    finally:
        PUBLISH_LOCK.release()


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False).encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    server_version = "AimyRepair/1.0"

    def log_message(self, format_string: str, *args: Any) -> None:
        print(format_string % args)

    def _send_json(self, value: Any, status: int = 200) -> None:
        data = _json_bytes(value)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _send_file(self, path: Path, content_type: str) -> None:
        if not path.is_file():
            self.send_error(404)
            return
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > 2_000_000:
            raise AppError("送信データのサイズが不正です。")
        try:
            value = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as ex:
            raise AppError("送信データを読み込めません。") from ex
        if not isinstance(value, dict):
            raise AppError("送信データの形式が不正です。")
        return value

    def do_GET(self) -> None:  # noqa: N802
        try:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            if path == "/":
                self._send_file(HTML_PATH, "text/html; charset=utf-8")
                return
            if path == "/api/gachas":
                gachas = _load_gachas()
                self._send_json(
                    {
                        "gachas": [
                            {"slug": gacha["slug"], "title": gacha["title"], "itemCount": len(gacha.get("items", []))}
                            for gacha in gachas
                            if _has_source_files(gacha["slug"])
                        ]
                    }
                )
                return

            parts = [urllib.parse.unquote(part) for part in path.split("/") if part]
            if len(parts) == 3 and parts[0] == "candidate":
                token, filename = parts[1], Path(parts[2]).name
                with SESSION_LOCK:
                    session = SESSIONS.get(token)
                if not session or filename != parts[2]:
                    self.send_error(404)
                    return
                target = Path(session["workDir"]) / "items" / filename
                self._send_file(target, "image/png")
                return
            if len(parts) == 3 and parts[0] == "current":
                slug, filename = parts[1], Path(parts[2]).name
                if filename != parts[2]:
                    self.send_error(404)
                    return
                target = PROJECT_ROOT / "public" / "images" / "items" / slug / filename
                content_type = "image/png" if target.suffix.lower() == ".png" else "image/jpeg"
                self._send_file(target, content_type)
                return
            if len(parts) == 3 and parts[0] == "source":
                slug, filename = parts[1], Path(parts[2]).name
                if filename != parts[2]:
                    self.send_error(404)
                    return
                target = PROJECT_ROOT / "public" / "images" / "gacha" / slug / filename
                content_type = "image/png" if target.suffix.lower() == ".png" else "image/jpeg"
                self._send_file(target, content_type)
                return
            self.send_error(404)
        except AppError as ex:
            self._send_json({"error": str(ex)}, status=400)
        except Exception as ex:
            traceback.print_exc()
            self._send_json({"error": f"予期しないエラーです: {ex}"}, status=500)

    def do_POST(self) -> None:  # noqa: N802
        try:
            path = urllib.parse.urlparse(self.path).path
            payload = self._read_json()
            if path == "/api/analyze":
                self._send_json({"result": _analyze(str(payload.get("slug", "")))})
                return
            if path == "/api/manual-candidate":
                self._send_json({"result": _add_manual_candidate(payload)})
                return
            if path == "/api/publish":
                self._send_json({"result": _publish(payload)})
                return
            self.send_error(404)
        except AppError as ex:
            self._send_json({"error": str(ex)}, status=400)
        except Exception as ex:
            traceback.print_exc()
            self._send_json({"error": f"予期しないエラーです: {ex}"}, status=500)


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def main() -> int:
    if not HTML_PATH.exists():
        print(f"画面ファイルが見つかりません: {HTML_PATH}")
        return 1
    if not (PROJECT_ROOT / "package.json").exists():
        print("Aimy Closetのプロジェクト内で実行してください。")
        return 1

    WORK_ROOT.mkdir(parents=True, exist_ok=True)
    port = _find_free_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print("=" * 68)
    print("Aimy 既存ガチャ画像修正ツールを起動しました")
    print(url)
    print("このターミナルを閉じるまで、Mac内だけで動作します。")
    print("=" * 68)
    threading.Timer(0.7, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
