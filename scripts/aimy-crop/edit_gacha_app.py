#!/usr/bin/env python3
"""Local editor for existing Aimy gacha titles and banners."""

from __future__ import annotations

import base64
import binascii
import io
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
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from PIL import Image, ImageOps


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
HTML_PATH = SCRIPT_DIR / "edit_gacha.html"
REGISTRY_PATH = PROJECT_ROOT / "src" / "data" / "gachas.js"
PUBLIC_ROOT = (PROJECT_ROOT / "public").resolve()
BANNER_SIZE = (1125, 202)
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


class AppError(RuntimeError):
    pass


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


def _encode_js_string(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace("\r", "\\r")
        .replace("\n", "\\n")
        .replace("\t", "\\t")
    )


def _read_field(text: str, field: str, *, required: bool = True) -> str:
    match = _field_pattern(field).search(text)
    if not match:
        if required:
            raise AppError(f"{field} をデータファイルから読み取れませんでした。")
        return ""
    return _decode_js_string(match.group(2))


def _replace_field(text: str, field: str, value: str) -> str:
    pattern = _field_pattern(field)
    if not pattern.search(text):
        raise AppError(f"{field} をデータファイルから読み取れませんでした。")
    return pattern.sub(
        lambda match: f"{match.group(1)}'{_encode_js_string(value)}'{match.group(3)}",
        text,
        count=1,
    )


def _registered_modules() -> List[Path]:
    if not REGISTRY_PATH.is_file():
        raise AppError("src/data/gachas.js が見つかりません。")
    registry = REGISTRY_PATH.read_text(encoding="utf-8")
    module_names = re.findall(
        r"^import\s+[A-Za-z_$][\w$]*\s+from\s+['\"]\./gachas/([^'\"]+)['\"]",
        registry,
        flags=re.MULTILINE,
    )
    modules: List[Path] = []
    seen: set[Path] = set()
    for module_name in module_names:
        candidate = PROJECT_ROOT / "src" / "data" / "gachas" / f"{module_name}.js"
        if candidate.is_file() and candidate not in seen:
            modules.append(candidate)
            seen.add(candidate)
    return modules


def _resolve_banner_path(value: str) -> Path:
    if not value.startswith("/"):
        raise AppError("バナーの保存先がpublic配下ではありません。")
    relative = Path(urllib.parse.unquote(value.lstrip("/")))
    if ".." in relative.parts or relative.suffix.lower() not in IMAGE_EXTENSIONS:
        raise AppError("バナーの保存先が不正です。")
    resolved = (PUBLIC_ROOT / relative).resolve()
    try:
        resolved.relative_to(PUBLIC_ROOT)
    except ValueError as error:
        raise AppError("バナーの保存先がpublic配下ではありません。") from error
    return resolved


def _load_gachas() -> List[Dict[str, Any]]:
    gachas: List[Dict[str, Any]] = []
    for data_file in _registered_modules():
        text = data_file.read_text(encoding="utf-8")
        slug = _read_field(text, "slug")
        title = _read_field(text, "title")
        banner = _read_field(text, "banner")
        banner_path = _resolve_banner_path(banner)
        version = banner_path.stat().st_mtime_ns if banner_path.exists() else 0
        gachas.append(
            {
                "slug": slug,
                "title": title,
                "banner": banner,
                "bannerExists": banner_path.is_file(),
                "bannerUrl": f"/api/banner/{urllib.parse.quote(slug)}?v={version}",
                "dataFile": str(data_file.relative_to(PROJECT_ROOT)),
            }
        )
    return gachas


def _find_gacha(slug: str) -> Tuple[Dict[str, Any], Path]:
    for gacha in _load_gachas():
        if gacha["slug"] != slug:
            continue
        data_file = PROJECT_ROOT / str(gacha["dataFile"])
        return gacha, data_file
    raise AppError("選択したガチャが見つかりません。")


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


def _decode_banner(data_url: str) -> Image.Image:
    match = re.fullmatch(
        r"data:image/(?:jpeg|jpg|png|webp);base64,([A-Za-z0-9+/=\r\n]+)",
        data_url,
    )
    if not match:
        raise AppError("差し替えバナーを読み取れませんでした。")
    try:
        raw = base64.b64decode(match.group(1), validate=True)
    except (ValueError, binascii.Error) as error:
        raise AppError("差し替えバナーのデータが壊れています。") from error
    if not raw or len(raw) > 25_000_000:
        raise AppError("差し替えバナーの容量が大きすぎます。")
    try:
        with Image.open(io.BytesIO(raw)) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
    except Exception as error:
        raise AppError("差し替えバナーを画像として開けませんでした。") from error

    # Never stretch the image. The browser normally sends 1125x202 already;
    # this fit is a final server-side safety net.
    if image.size != BANNER_SIZE:
        image = ImageOps.fit(image, BANNER_SIZE, method=Image.Resampling.LANCZOS)
    return image


def _save_banner(image: Image.Image, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
    try:
        if destination.suffix.lower() == ".png":
            image.save(temporary, format="PNG", optimize=True)
        else:
            image.save(
                temporary,
                format="JPEG",
                quality=95,
                optimize=True,
                subsampling=0,
            )
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def _restore_file(backup: Path, destination: Path, existed: bool) -> None:
    if existed:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup, destination)
    else:
        destination.unlink(missing_ok=True)


def update_gacha(slug: str, title: str, banner_data_url: str) -> Dict[str, Any]:
    title = title.strip()
    if not title:
        raise AppError("ガチャ名を入力してください。")
    if len(title) > 120:
        raise AppError("ガチャ名が長すぎます。")

    gacha, data_file = _find_gacha(slug)
    banner_file = _resolve_banner_path(str(gacha["banner"]))
    sitemap_file = PROJECT_ROOT / "public" / "sitemap.xml"
    original_text = data_file.read_text(encoding="utf-8")
    old_title = str(gacha["title"])
    title_changed = title != old_title
    banner_changed = bool(banner_data_url)
    if not title_changed and not banner_changed:
        raise AppError("変更がありません。ガチャ名かバナーを修正してください。")

    staged_before = _run_command(["git", "diff", "--cached", "--name-only"], check=False).stdout.strip()
    if staged_before:
        raise AppError(
            "保存前からステージ済みの変更があります。誤って一緒に公開しないため停止しました。\n"
            + staged_before
        )

    decoded_banner: Optional[Image.Image] = None
    if banner_changed:
        decoded_banner = _decode_banner(banner_data_url)

    targets = [data_file, banner_file, sitemap_file]
    relative_targets = [str(path.relative_to(PROJECT_ROOT)) for path in targets]
    committed = False
    commit_message = f"Update {title} gacha details"

    with tempfile.TemporaryDirectory(prefix="aimy-gacha-edit-") as backup_name:
        backup_root = Path(backup_name)
        existed: Dict[Path, bool] = {}
        backups: Dict[Path, Path] = {}
        for index, path in enumerate(targets):
            existed[path] = path.is_file()
            backup = backup_root / f"{index:02d}-{path.name}"
            backups[path] = backup
            if path.is_file():
                shutil.copy2(path, backup)

        try:
            if title_changed:
                updated_text = _replace_field(original_text, "title", title)
                description = _read_field(updated_text, "description", required=False)
                if description and old_title in description:
                    updated_text = _replace_field(
                        updated_text,
                        "description",
                        description.replace(old_title, title),
                    )
                data_file.write_text(updated_text, encoding="utf-8")

            if decoded_banner is not None:
                _save_banner(decoded_banner, banner_file)

            build = _run_command(["npm", "run", "build"])
            stage_paths = [str(data_file.relative_to(PROJECT_ROOT))]
            if banner_changed:
                stage_paths.append(str(banner_file.relative_to(PROJECT_ROOT)))
            if sitemap_file.exists():
                stage_paths.append(str(sitemap_file.relative_to(PROJECT_ROOT)))
            _run_command(["git", "add", "--", *stage_paths])

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

            refreshed, _ = _find_gacha(slug)
            return {
                "slug": slug,
                "oldTitle": old_title,
                "title": title,
                "titleChanged": title_changed,
                "bannerChanged": banner_changed,
                "bannerUrl": refreshed["bannerUrl"],
                "build": "成功",
                "commit": commit_message,
                "push": "完了",
                "sitePath": f"/gacha/{slug}",
                "buildLog": build.stdout[-1500:],
            }
        except Exception:
            if not committed:
                for path in targets:
                    _restore_file(backups[path], path, existed[path])
                _run_command(["git", "reset", "--", *relative_targets], check=False)
            raise


class Handler(BaseHTTPRequestHandler):
    server_version = "AimyGachaEditor/1.0"

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
        data = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self._send_bytes(data, "application/json; charset=utf-8", status)

    def _send_error_json(self, error: Exception, status: int) -> None:
        traceback.print_exc()
        self._send_json({"ok": False, "error": str(error)}, status)

    def _read_json(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > 35_000_000:
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
                self._send_json({"ok": True, "gachas": _load_gachas()})
                return
            if parsed.path.startswith("/api/banner/"):
                slug = urllib.parse.unquote(parsed.path[len("/api/banner/") :])
                gacha, _ = _find_gacha(slug)
                banner_path = _resolve_banner_path(str(gacha["banner"]))
                if not banner_path.is_file():
                    self.send_error(404)
                    return
                content_type = mimetypes.guess_type(banner_path.name)[0] or "image/jpeg"
                self._send_bytes(banner_path.read_bytes(), content_type)
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
            payload = self._read_json()
            result = update_gacha(
                str(payload.get("slug", "")),
                str(payload.get("title", "")),
                str(payload.get("bannerDataUrl", "")),
            )
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
        count = len(_load_gachas())
    except AppError as error:
        print(error, file=sys.stderr)
        return 1

    port = _find_free_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print("=" * 64)
    print("Aimy 既存ガチャ編集ツールを起動しました")
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
