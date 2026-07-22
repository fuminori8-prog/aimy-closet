#!/usr/bin/env python3
"""Aimy Closet: repair item-image mappings for an existing gacha.

This local-only tool reads screenshots already stored in
public/images/gacha/<slug>.  It deliberately performs no automatic duplicate
removal.  The user can exclude duplicate candidates, then map the remaining
cards to the existing item list in filename/top-to-bottom order.
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
from detect_cards import _detect_boxes  # noqa: E402


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
                output_name = f"{index:02d}.png"
                _crop_card(image, tuple(box)).save(generated_dir / output_name, "PNG")
                candidates.append(
                    {
                        "index": index,
                        "output": output_name,
                        "source": source.name,
                        "sourceIndex": source_index,
                        "box": list(box),
                        "imageUrl": f"/candidate/{token}/{output_name}",
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
        "candidates": candidates,
        "categories": categories,
        "expectedCount": expected,
        "candidateCount": len(candidates),
        "countMatches": expected == len(candidates),
    }


def _replace_categories(data_path: Path, items: Sequence[Dict[str, Any]]) -> None:
    text = data_path.read_text(encoding="utf-8")
    for item in items:
        item_id = str(item["id"])
        category = str(item["category"])
        id_match = re.search(r"\bid\s*:\s*(['\"])" + re.escape(item_id) + r"\1", text)
        if not id_match:
            raise AppError(f"データ内でアイテムIDを確認できません: {item_id}")
        block_end = text.find("}", id_match.end())
        if block_end < 0:
            raise AppError(f"アイテムデータの終端を確認できません: {item_id}")
        segment = text[id_match.start() : block_end]
        category_match = re.search(r"(\bcategory\s*:\s*)(['\"])(.*?)\2", segment, flags=re.DOTALL)
        if not category_match:
            raise AppError(f"カテゴリ欄を確認できません: {item_id}")
        replacement = f"{category_match.group(1)}{category_match.group(2)}{category}{category_match.group(2)}"
        absolute_start = id_match.start() + category_match.start()
        absolute_end = id_match.start() + category_match.end()
        text = text[:absolute_start] + replacement + text[absolute_end:]

    temp_path = data_path.with_suffix(data_path.suffix + ".aimy-repair-tmp")
    temp_path.write_text(text, encoding="utf-8")
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

    expected = len(gacha.get("items", []))
    candidate_indexes = payload.get("candidateIndexes", [])
    if not isinstance(candidate_indexes, list) or len(candidate_indexes) != expected:
        raise AppError(
            f"使用する画像が登録件数と一致しません（登録 {expected}件／選択 {len(candidate_indexes) if isinstance(candidate_indexes, list) else 0}件）。"
        )
    if any(not isinstance(value, int) for value in candidate_indexes):
        raise AppError("使用する画像番号の形式が不正です。")
    if len(set(candidate_indexes)) != len(candidate_indexes):
        raise AppError("同じ画像候補が複数回選択されています。")
    available_indexes = set(range(1, int(session["candidateCount"]) + 1))
    if not set(candidate_indexes).issubset(available_indexes):
        raise AppError("存在しない画像候補が選択されています。")

    checks = payload.get("checks", [])
    if not isinstance(checks, list) or len(checks) != expected or not all(value is True for value in checks):
        raise AppError("全アイテムの確認チェックが完了していません。")

    submitted_items = payload.get("items", [])
    if not isinstance(submitted_items, list) or len(submitted_items) != expected:
        raise AppError("送信されたアイテム数が一致しません。")

    existing_by_id = {str(item.get("id", "")): item for item in gacha.get("items", [])}
    normalized_items: List[Dict[str, str]] = []
    for submitted in submitted_items:
        item_id = str(submitted.get("id", ""))
        category = str(submitted.get("category", "")).strip()
        if item_id not in existing_by_id:
            raise AppError(f"不明なアイテムIDです: {item_id}")
        if category not in STANDARD_CATEGORIES:
            raise AppError(f"選択できないカテゴリです: {category}")
        normalized_items.append({"id": item_id, "category": category})
    if [item["id"] for item in normalized_items] != [str(item.get("id", "")) for item in gacha["items"]]:
        raise AppError("アイテムの順序が変わっています。もう一度読み取ってください。")

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
                    "itemCount": expected,
                    "selectedCandidateIndexes": candidate_indexes,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        for output_index, candidate_index in enumerate(candidate_indexes, start=1):
            source = generated_dir / f"{candidate_index:02d}.png"
            if not source.exists():
                raise AppError(f"生成画像が見つかりません: {source.name}")
            with Image.open(source) as image:
                if image.size != (192, 192):
                    raise AppError(f"生成画像サイズが不正です: {source.name} {image.size}")
            shutil.copy2(source, production_dir / f"{output_index:02d}.png")

        _replace_categories(data_path, normalized_items)
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
                "message": "現在の画像・カテゴリと同じだったため、GitHubへの反映は不要でした。",
                "backup": str(backup_dir.relative_to(PROJECT_ROOT)),
            }

        title = str(gacha.get("title", slug))
        _run(["git", "commit", "-m", f"Fix {title} item image mapping"], timeout=90)
        committed = True
        push_log = _run(["git", "push"], timeout=180)
        with SESSION_LOCK:
            SESSIONS.pop(token, None)
        shutil.rmtree(work_dir, ignore_errors=True)
        return {
            "changed": True,
            "message": "確認済み画像とカテゴリをGitHubへ反映しました。",
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
