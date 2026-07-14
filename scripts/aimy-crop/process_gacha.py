#!/usr/bin/env python3
"""Aimy Crop Tool v1 - unified entry point."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from detect_cards import run_detection
from export_cards import run_export
from auto_config import run_auto_config
from generate_preview import run_preview
from publish_gacha import run_publish


def main() -> int:
    parser = argparse.ArgumentParser(description="Run detect/export workflow for one gacha slug")
    parser.add_argument("slug", help="gacha slug")
    parser.add_argument("--project-root", default=".", help="project root")
    parser.add_argument("--detect", action="store_true", help="run candidate detection only")
    parser.add_argument("--export", dest="do_export", action="store_true", help="run export from config only")
    parser.add_argument("--preview", action="store_true", help="generate preview.html only")
    parser.add_argument("--auto-config", action="store_true", help="auto generate config from candidates")
    parser.add_argument("--publish", action="store_true", help="publish to production safely")
    parser.add_argument("--all", action="store_true", help="run both detection and export")
    parser.add_argument("--config", default=None, help="custom config path")
    parser.add_argument("--candidates", default=None, help="custom candidates path")
    parser.add_argument("--yes", action="store_true", help="skip interactive confirmation for publish")
    parser.add_argument("--dry-run", action="store_true", help="show publish plan without changes")
    args = parser.parse_args()

    run_detect = args.detect
    run_export_mode = args.do_export
    run_preview_mode = args.preview
    run_auto_config_mode = args.auto_config
    run_publish_mode = args.publish

    if args.all or (not args.detect and not args.do_export and not args.preview and not args.auto_config and not args.publish):
        run_detect = True
        run_export_mode = True

    project_root = Path(args.project_root).resolve()
    summary = {
        "slug": args.slug,
        "ranDetect": False,
        "ranAutoConfig": False,
        "ranExport": False,
        "ranPreview": False,
        "ranPublish": False,
    }

    if run_detect:
        detect_result = run_detection(args.slug, project_root)
        summary["ranDetect"] = True
        summary["detect"] = detect_result

    if run_auto_config_mode:
        auto_result = run_auto_config(args.slug, project_root)
        summary["ranAutoConfig"] = True
        summary["autoConfig"] = auto_result

    if run_export_mode:
        export_result = run_export(
            args.slug,
            project_root,
            Path(args.config).resolve() if args.config else None,
            Path(args.candidates).resolve() if args.candidates else None,
        )
        summary["ranExport"] = True
        summary["export"] = {
            "exportedCount": export_result["exportedCount"],
            "outputDir": export_result["outputDir"],
        }

    if run_export_mode or run_preview_mode:
        preview_result = run_preview(args.slug, project_root)
        summary["ranPreview"] = True
        summary["preview"] = {
            "previewPath": preview_result["previewPath"],
            "itemsCount": preview_result["itemsCount"],
            "outputImageCount": preview_result["outputImageCount"],
            "okCount": preview_result["okCount"],
            "warningCount": preview_result["warningCount"],
            "errorCount": preview_result["errorCount"],
            "localStorageKey": preview_result["localStorageKey"],
        }

    if run_publish_mode:
        publish_result = run_publish(
            args.slug,
            project_root,
            yes=args.yes,
            dry_run=args.dry_run,
        )
        summary["ranPublish"] = True
        summary["publish"] = publish_result

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
