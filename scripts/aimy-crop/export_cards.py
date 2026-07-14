#!/usr/bin/env python3
"""Aimy Crop Tool v1 - export cards from config."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from PIL import Image

BBox = Tuple[int, int, int, int]


def _resolve_input_dir(project_root: Path, slug: str) -> Path:
    public_dir = project_root / "public" / "images" / "gacha" / slug
    archive_dir = project_root / "archive" / "gacha" / slug
    if public_dir.exists():
        return public_dir
    if archive_dir.exists():
        return archive_dir
    raise FileNotFoundError(f"Input slug directory not found for {slug}")


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_candidate_map(candidates_payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    mapping: Dict[str, Dict[str, Any]] = {}
    for idx, cand in enumerate(candidates_payload.get("candidates", []), start=1):
        mapping[cand["id"]] = cand
        mapping[f"#{idx}"] = cand
    return mapping


def _resolve_item_spec(item: Dict[str, Any], candidate_map: Dict[str, Dict[str, Any]]) -> Tuple[str, BBox]:
    if "candidateId" in item:
        cand = candidate_map.get(str(item["candidateId"]))
        if not cand:
            raise ValueError(f"candidateId not found: {item['candidateId']}")
        return cand["source"], tuple(int(v) for v in cand["box"])

    if "candidateIndex" in item:
        key = f"#{int(item['candidateIndex'])}"
        cand = candidate_map.get(key)
        if not cand:
            raise ValueError(f"candidateIndex not found: {item['candidateIndex']}")
        return cand["source"], tuple(int(v) for v in cand["box"])

    if "source" in item and "box" in item:
        box = tuple(int(v) for v in item["box"])
        if len(box) != 4:
            raise ValueError(f"box must contain four integers: {item}")
        return str(item["source"]), box

    raise ValueError("item must define candidateId, candidateIndex, or source+box")


def _crop_without_stretch(image: Image.Image, box: BBox, pad_white: bool = False) -> Image.Image:
    left, top, right, bottom = box
    if left < 0 or top < 0:
        raise ValueError(f"negative crop box is not allowed: {box}")
    crop = image.crop((left, top, right, bottom)).convert("RGBA")
    w, h = crop.size

    if w > 192 or h > 192:
        raise ValueError(f"crop box creates larger than 192x192 image: {box} -> {(w, h)}")

    if (w, h) == (192, 192):
        return crop

    bg = (255, 255, 255, 255) if pad_white else (0, 0, 0, 0)
    canvas = Image.new("RGBA", (192, 192), bg)
    x = (192 - w) // 2
    y = (192 - h) // 2
    canvas.paste(crop, (x, y), crop)
    return canvas


def run_export(slug: str, project_root: Path, config_path: Path | None = None, candidates_path: Path | None = None) -> Dict[str, Any]:
    cfg_path = config_path or (project_root / "scripts" / "aimy-crop" / "configs" / f"{slug}.json")
    if not cfg_path.exists():
        raise FileNotFoundError(f"Config not found: {cfg_path}")

    cfg = _load_json(cfg_path)
    items = cfg.get("items", [])
    if not items:
        raise ValueError("Config has no items")

    input_dir = _resolve_input_dir(project_root, slug)
    out_items_dir = project_root / "scripts" / "aimy-crop" / "output" / slug / "items"
    out_items_dir.mkdir(parents=True, exist_ok=True)

    cand_path = candidates_path or (project_root / "scripts" / "aimy-crop" / "output" / slug / "candidates.json")
    candidate_map: Dict[str, Dict[str, Any]] = {}
    if cand_path.exists():
        candidate_map = _build_candidate_map(_load_json(cand_path))

    exported: List[Dict[str, Any]] = []
    for item in items:
        output_name = item.get("output")
        if not output_name:
            raise ValueError(f"Missing output in item: {item}")

        source_name, box = _resolve_item_spec(item, candidate_map)
        source_path = input_dir / source_name
        if not source_path.exists():
            raise FileNotFoundError(f"Source screenshot not found: {source_path}")

        image = Image.open(source_path)
        result = _crop_without_stretch(image, box, pad_white=bool(item.get("padWhite", False)))

        output_path = out_items_dir / output_name
        output_path.parent.mkdir(parents=True, exist_ok=True)
        result.save(output_path, "PNG")
        exported.append(
            {
                "output": output_name,
                "source": source_name,
                "box": list(box),
                "size": list(result.size),
            }
        )

    report = {
        "slug": slug,
        "config": str(cfg_path),
        "outputDir": str(out_items_dir),
        "exportedCount": len(exported),
        "exported": exported,
    }
    report_path = project_root / "scripts" / "aimy-crop" / "output" / slug / "export-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Export cropped card images from config")
    parser.add_argument("slug", help="gacha slug")
    parser.add_argument("--project-root", default=".", help="project root")
    parser.add_argument("--config", default=None, help="config path")
    parser.add_argument("--candidates", default=None, help="candidates.json path")
    args = parser.parse_args()

    report = run_export(
        args.slug,
        Path(args.project_root).resolve(),
        Path(args.config).resolve() if args.config else None,
        Path(args.candidates).resolve() if args.candidates else None,
    )
    print(json.dumps({
        "slug": report["slug"],
        "exportedCount": report["exportedCount"],
        "outputDir": report["outputDir"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
