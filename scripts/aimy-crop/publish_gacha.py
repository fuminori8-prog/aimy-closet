#!/usr/bin/env python3
"""Aimy Crop Tool v1 - safe publish workflow for one gacha slug."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from PIL import Image


@dataclass
class PublishPaths:
    project_root: Path
    slug: str

    @property
    def output_slug_dir(self) -> Path:
        return self.project_root / "scripts" / "aimy-crop" / "output" / self.slug

    @property
    def output_items_dir(self) -> Path:
        return self.output_slug_dir / "items"

    @property
    def preview_report(self) -> Path:
        return self.output_slug_dir / "preview-report.json"

    @property
    def review_status(self) -> Path:
        return self.output_slug_dir / "review-status.json"

    @property
    def review_status_pattern(self) -> str:
        return "review-status-*.json"

    @property
    def data_file(self) -> Path:
        return self.project_root / "src" / "data" / "gachas" / f"{self.slug}.js"

    @property
    def prod_items_dir(self) -> Path:
        return self.project_root / "public" / "images" / "items" / self.slug

    @property
    def backup_root(self) -> Path:
        return self.project_root / "scripts" / "aimy-crop" / "backups" / self.slug

    @property
    def stage_root(self) -> Path:
        return self.project_root / "scripts" / "aimy-crop" / "output" / self.slug / ".publish-staging"


def _load_gacha(slug: str, project_root: Path) -> Dict[str, Any]:
    gacha_path = project_root / "src" / "data" / "gachas" / f"{slug}.js"
    if not gacha_path.exists():
        raise FileNotFoundError(f"Gacha file not found: {gacha_path}")

    node_script = r"""
const fs = require('fs');
const vm = require('vm');
const file = process.argv[1];
const src = fs.readFileSync(file, 'utf8').replace(/export\s+default/, 'module.exports =');
const ctx = { module: { exports: {} }, exports: {} };
vm.runInNewContext(src, ctx, { filename: file });
const g = ctx.module.exports;
console.log(JSON.stringify({
  slug: g.slug,
  title: g.title,
  infoStatus: g.infoStatus,
  items: (g.items || []).map((x) => ({ id: x.id, name: x.name, rarity: x.rarity, category: x.category, image: x.image }))
}));
"""
    proc = subprocess.run(
        ["node", "-e", node_script, str(gacha_path)],
        cwd=project_root,
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(proc.stdout)


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _find_latest_review_status(paths: PublishPaths) -> Path:
    candidates = sorted(paths.output_slug_dir.glob(paths.review_status_pattern))
    if candidates:
        return candidates[-1]
    if paths.review_status.exists():
        return paths.review_status
    raise FileNotFoundError(
        f"Required file not found: {paths.output_slug_dir / paths.review_status_pattern}"
    )


def _validate_items_output(paths: PublishPaths, items_count: int) -> Dict[str, Any]:
    missing_numbers: List[str] = []
    wrong_size: List[str] = []
    existing = 0
    expected_outputs: List[str] = []

    for i in range(1, items_count + 1):
        num = f"{i:02d}"
        expected_outputs.append(num)
        p = paths.output_items_dir / f"{num}.png"
        if not p.exists():
            missing_numbers.append(num)
            continue
        existing += 1
        with Image.open(p) as img:
            if img.size != (192, 192):
                wrong_size.append(num)

    return {
        "itemsCount": items_count,
        "outputImageCount": existing,
        "missingNumbers": missing_numbers,
        "wrongSize": wrong_size,
        "all192": len(wrong_size) == 0,
        "noMissing": len(missing_numbers) == 0,
    }


def _validate_review_status(paths: PublishPaths, items_count: int) -> Dict[str, Any]:
    review_path = _find_latest_review_status(paths)
    review = _load_json(review_path)
    checked_count = int(review.get("checkedCount", 0))
    total_count = int(review.get("totalCount", 0))
    all_checked = bool(review.get("allChecked", False))
    checked_items = review.get("checkedItems", [])

    if not isinstance(checked_items, list):
        raise ValueError("review-status.json checkedItems must be an array")

    return {
        "slug": review.get("slug"),
        "checkedCount": checked_count,
        "totalCount": total_count,
        "allChecked": all_checked,
        "checkedItems": checked_items,
        "reviewedAt": review.get("reviewedAt"),
        "filePath": str(review_path),
        "valid": (
            review.get("slug") == paths.slug
            and total_count == items_count
            and checked_count == items_count
            and all_checked
        ),
    }


def _build_validation(paths: PublishPaths) -> Dict[str, Any]:
    gacha = _load_gacha(paths.slug, paths.project_root)
    items = gacha.get("items", [])
    items_count = len(items)
    if items_count <= 0:
        raise ValueError("items must contain at least one entry")

    preview_report = _load_json(paths.preview_report)
    output_check = _validate_items_output(paths, items_count)
    review_check = _validate_review_status(paths, items_count)

    image_updates = [f"/images/items/{paths.slug}/{i:02d}.png" for i in range(1, items_count + 1)]

    errors: List[str] = []
    if output_check["outputImageCount"] != items_count:
        errors.append("output画像数とitems件数が一致しません")
    if not output_check["all192"]:
        errors.append("192x192ではない画像があります")
    if not output_check["noMissing"]:
        errors.append("連番画像の欠落があります")
    if int(preview_report.get("errorCount", -1)) != 0:
        errors.append("preview-report.json の errorCount が0ではありません")
    if not review_check["valid"]:
        errors.append("review-status.json が全件チェック済み状態ではありません")

    existing_prod_files: List[str] = []
    if paths.prod_items_dir.exists():
        existing_prod_files = sorted([p.name for p in paths.prod_items_dir.iterdir() if p.is_file()])

    return {
        "gacha": gacha,
        "previewReport": preview_report,
        "outputCheck": output_check,
        "reviewCheck": review_check,
        "imageUpdates": image_updates,
        "errors": errors,
        "existingProdFiles": existing_prod_files,
    }


def _print_publish_plan(paths: PublishPaths, validation: Dict[str, Any], dry_run: bool) -> None:
    gacha = validation["gacha"]
    out = validation["outputCheck"]
    review = validation["reviewCheck"]

    print("--- Publish Plan ---")
    print(f"ガチャ名: {gacha['title']}")
    print(f"slug: {paths.slug}")
    print(f"items件数: {out['itemsCount']}")
    print(f"出力画像数: {out['outputImageCount']}")
    print(f"review-status確認件数: {review['checkedCount']} / {review['totalCount']}")
    print(f"review-statusファイル: {review['filePath']}")
    print(f"コピー先: {paths.prod_items_dir}")
    print(f"変更予定データファイル: {paths.data_file}")
    print(f"現在のinfoStatus: {gacha.get('infoStatus', '')}")
    print("変更後のinfoStatus: 確認済み")
    print(f"dry-run: {'ON' if dry_run else 'OFF'}")


def _prepare_backup(paths: PublishPaths, timestamp: str) -> Dict[str, Path]:
    backup_dir = paths.backup_root / timestamp
    backup_dir.mkdir(parents=True, exist_ok=True)

    images_backup = backup_dir / "images-items"
    data_backup = backup_dir / "gacha-js"
    meta_file = backup_dir / "meta.json"

    had_prod_images = paths.prod_items_dir.exists()
    had_data_file = paths.data_file.exists()

    if had_prod_images:
        shutil.copytree(paths.prod_items_dir, images_backup)
    if had_data_file:
        data_backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(paths.data_file, data_backup)

    meta = {
        "slug": paths.slug,
        "createdAt": timestamp,
        "hadProdImages": had_prod_images,
        "hadDataFile": had_data_file,
        "prodItemsDir": str(paths.prod_items_dir),
        "dataFile": str(paths.data_file),
    }
    meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "backupDir": backup_dir,
        "imagesBackup": images_backup,
        "dataBackup": data_backup,
        "meta": meta_file,
    }


def _build_updated_gacha_text(original_text: str, slug: str, items_count: int) -> str:
    image_pattern = re.compile(r"image:\s*'[^']*'")

    counter = {"i": 0}

    def repl(_m: re.Match[str]) -> str:
        counter["i"] += 1
        if counter["i"] > items_count:
            return _m.group(0)
        return f"image: '/images/items/{slug}/{counter['i']:02d}.png'"

    updated = image_pattern.sub(repl, original_text)
    if counter["i"] < items_count:
        raise ValueError("Could not update enough image fields in gacha data file")

    status_pattern = re.compile(r"infoStatus:\s*'[^']*'")
    if status_pattern.search(updated):
        updated = status_pattern.sub("infoStatus: '確認済み'", updated, count=1)
    else:
        raise ValueError("infoStatus field not found in gacha data file")

    return updated


def _restore_from_backup(paths: PublishPaths, backup: Dict[str, Path]) -> None:
    images_backup = backup["imagesBackup"]
    data_backup = backup["dataBackup"]

    if paths.prod_items_dir.exists():
        shutil.rmtree(paths.prod_items_dir)

    if images_backup.exists():
        shutil.copytree(images_backup, paths.prod_items_dir)

    if data_backup.exists():
        shutil.copy2(data_backup, paths.data_file)


def run_publish(slug: str, project_root: Path, yes: bool = False, dry_run: bool = False) -> Dict[str, Any]:
    paths = PublishPaths(project_root=project_root, slug=slug)
    validation = _build_validation(paths)

    _print_publish_plan(paths, validation, dry_run=dry_run)

    if validation["errors"]:
        return {
            "slug": slug,
            "status": "rejected",
            "dryRun": dry_run,
            "errors": validation["errors"],
        }

    has_existing_prod = len(validation["existingProdFiles"]) > 0
    if not dry_run and not yes:
        if has_existing_prod:
            answer = input("既存の本番画像を上書きします。本番へ反映しますか？ [y/N] ").strip().lower()
        else:
            answer = input("本番へ反映しますか？ [y/N] ").strip().lower()
        if answer != "y":
            return {
                "slug": slug,
                "status": "aborted",
                "dryRun": dry_run,
                "reason": "user cancelled",
            }

    if dry_run:
        return {
            "slug": slug,
            "status": "dry-run",
            "dryRun": True,
            "itemsCount": validation["outputCheck"]["itemsCount"],
            "outputImageCount": validation["outputCheck"]["outputImageCount"],
            "reviewStatusFile": validation["reviewCheck"]["filePath"],
            "copyFrom": str(paths.output_items_dir),
            "copyTo": str(paths.prod_items_dir),
            "dataFile": str(paths.data_file),
            "infoStatusBefore": validation["gacha"].get("infoStatus"),
            "infoStatusAfter": "確認済み",
            "imageUpdates": validation["imageUpdates"],
            "backupRoot": str(paths.backup_root),
            "build": "skip",
        }

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = _prepare_backup(paths, timestamp)

    stage_root = paths.stage_root / timestamp
    stage_images = stage_root / "items"
    stage_data = stage_root / "gacha.js"
    stage_root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(paths.output_items_dir, stage_images)

    original_text = paths.data_file.read_text(encoding="utf-8")
    stage_text = _build_updated_gacha_text(original_text, slug, validation["outputCheck"]["itemsCount"])
    stage_data.write_text(stage_text, encoding="utf-8")

    try:
        if paths.prod_items_dir.exists():
            shutil.rmtree(paths.prod_items_dir)
        shutil.copytree(stage_images, paths.prod_items_dir)

        shutil.copy2(stage_data, paths.data_file)

        build = subprocess.run(
            ["npm", "run", "build"],
            cwd=project_root,
            text=True,
            capture_output=True,
        )
        if build.returncode != 0:
            raise RuntimeError("npm run build failed")

        return {
            "slug": slug,
            "status": "published",
            "dryRun": False,
            "backupDir": str(backup["backupDir"]),
            "buildExitCode": build.returncode,
        }
    except Exception as ex:
        _restore_from_backup(paths, backup)
        return {
            "slug": slug,
            "status": "rolled-back",
            "dryRun": False,
            "error": str(ex),
            "backupDir": str(backup["backupDir"]),
        }


def run_backup_self_test(project_root: Path) -> Dict[str, Any]:
    base = project_root / "scripts" / "aimy-crop" / "output" / "_backup-self-test"
    src = base / "src"
    dst = base / "dst"
    backup = base / "backup"

    if base.exists():
        shutil.rmtree(base)
    src.mkdir(parents=True)
    dst.mkdir(parents=True)
    backup.mkdir(parents=True)

    (src / "01.txt").write_text("new", encoding="utf-8")
    (dst / "01.txt").write_text("old", encoding="utf-8")

    snapshot = backup / "dst-snapshot"
    shutil.copytree(dst, snapshot)

    shutil.rmtree(dst)
    shutil.copytree(src, dst)

    shutil.rmtree(dst)
    shutil.copytree(snapshot, dst)

    restored = (dst / "01.txt").read_text(encoding="utf-8")

    shutil.rmtree(base)

    return {
        "selfTest": "backup-restore",
        "result": "ok" if restored == "old" else "failed",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish gacha outputs to production safely")
    parser.add_argument("slug", help="gacha slug")
    parser.add_argument("--project-root", default=".", help="project root")
    parser.add_argument("--yes", action="store_true", help="skip interactive confirmation")
    parser.add_argument("--dry-run", action="store_true", help="validate and print plan only")
    parser.add_argument("--self-test", action="store_true", help="run backup/restore self test")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()

    if args.self_test:
        result = run_backup_self_test(root)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    result = run_publish(args.slug, root, yes=args.yes, dry_run=args.dry_run)
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if result.get("status") in {"rejected", "aborted", "rolled-back"}:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
