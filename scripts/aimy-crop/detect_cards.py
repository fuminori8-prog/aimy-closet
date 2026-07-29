#!/usr/bin/env python3
"""Aimy Crop Tool v1 - detect card candidates from gacha screenshots."""

from __future__ import annotations

import argparse
import json
import math
from collections import deque
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw

BBox = Tuple[int, int, int, int]


def _resolve_input_dir(project_root: Path, slug: str) -> Path:
    public_dir = project_root / "public" / "images" / "gacha" / slug
    archive_dir = project_root / "archive" / "gacha" / slug
    if public_dir.exists():
        return public_dir
    if archive_dir.exists():
        return archive_dir
    raise FileNotFoundError(f"Input slug directory not found for {slug}")


def _list_screenshots(input_dir: Path) -> List[Path]:
    files: List[Path] = []
    for p in sorted(input_dir.iterdir()):
        if not p.is_file():
            continue
        low = p.name.lower()
        if low.startswith("."):
            continue
        if low.endswith((".png", ".jpg", ".jpeg", ".webp")):
            if "banner" in low:
                continue
            files.append(p)
    return files


def _estimate_rarity(image: Image.Image, box: BBox) -> str:
    left, top, right, bottom = box
    w = right - left
    h = bottom - top
    # Read only the top-right rarity badge. A wider sample can include blonde
    # or orange hair and falsely turn an SSR card into gold/SR.
    sample = image.crop(
        (left + int(w * 0.68), top, right - 1, top + int(h * 0.30))
    ).convert("RGB")
    px = sample.load()
    sw, sh = sample.size

    gold_hits = 0
    rainbow_hits = 0
    for y in range(sh):
        for x in range(sw):
            r, g, b = px[x, y]
            mx = max(r, g, b)
            mn = min(r, g, b)
            sat = mx - mn
            if r > 150 and g > 90 and r > g * 1.05 and g > b * 1.15:
                gold_hits += 1
            if (
                (b > 130 and g > 115 and b > r * 1.05)
                or (g > 130 and g > r * 1.05)
            ):
                rainbow_hits += 1

    total = max(1, sw * sh)
    gold_ratio = gold_hits / total
    rainbow_ratio = rainbow_hits / total
    if gold_ratio > 0.08:
        return "SR"
    if rainbow_ratio > 0.08:
        return "SSR"
    return "UNKNOWN"


def _compute_dhash(image: Image.Image) -> str:
    gray = image.convert("L").resize((9, 8), Image.Resampling.BILINEAR)
    px = gray.load()
    bits = []
    for y in range(8):
        for x in range(8):
            bits.append("1" if px[x, y] > px[x + 1, y] else "0")
    value = int("".join(bits), 2)
    return f"{value:016x}"


def _hamming_distance(hex_a: str, hex_b: str) -> int:
    value = int(hex_a, 16) ^ int(hex_b, 16)
    return bin(value).count("1")


def _detect_boxes(image: Image.Image) -> List[BBox]:
    """Detect item-card squares at any screenshot resolution.

    The original detector was tuned to 1179px-wide iPhone screenshots and used
    fixed pixel sizes. Card geometry follows image width even when the screenshot
    is vertically cropped, so thresholds must be scaled from width only.
    """
    rgb = image.convert("RGB")
    w, h = rgb.size
    px = rgb.load()

    reference_w = 1179.0
    reference_h = 2556.0
    scale = w / reference_w
    # Avoid extreme thresholds for unusual but still usable images.
    scale = max(0.35, min(2.0, scale))

    max_x = min(max(1, round(380 * scale)), w)
    min_component_pixels = max(200, round(2800 * scale * scale))
    min_card_size = max(45, round(165 * scale))
    max_card_size = max(min_card_size + 10, round(230 * scale))
    max_card_left = round(180 * scale)

    mask = [[False] * max_x for _ in range(h)]
    for y in range(h):
        for x in range(max_x):
            r, g, b = px[x, y]
            mx = max(r, g, b)
            mn = min(r, g, b)
            sat = mx - mn
            if sat > 35 and mx > 105:
                mask[y][x] = True

    visited = [[False] * max_x for _ in range(h)]
    components: List[BBox] = []
    dirs = ((1, 0), (-1, 0), (0, 1), (0, -1))

    for y in range(h):
        for x in range(max_x):
            if visited[y][x] or not mask[y][x]:
                continue
            queue: deque[Tuple[int, int]] = deque([(x, y)])
            visited[y][x] = True
            min_x = max_x2 = x
            min_y = max_y = y
            count = 0

            while queue:
                cx, cy = queue.popleft()
                count += 1
                min_x = min(min_x, cx)
                max_x2 = max(max_x2, cx)
                min_y = min(min_y, cy)
                max_y = max(max_y, cy)
                for dx, dy in dirs:
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < max_x and 0 <= ny < h and not visited[ny][nx] and mask[ny][nx]:
                        visited[ny][nx] = True
                        queue.append((nx, ny))

            bw = max_x2 - min_x + 1
            bh = max_y - min_y + 1
            if count < min_component_pixels:
                continue
            if not (min_card_size <= bw <= max_card_size and min_card_size <= bh <= max_card_size):
                continue
            aspect = bw / max(1, bh)
            if not (0.85 <= aspect <= 1.15):
                continue
            if min_x > max_card_left:
                continue
            components.append((min_x, min_y, max_x2 + 1, max_y + 1))

    components.sort(key=lambda b: (b[1], b[0]))

    # JPEG compression can break an SSR rainbow border into several disconnected
    # pieces. Detect card-sized vertical colour bands as a geometry fallback.
    soft_left = max(0, round(45 * scale))
    soft_right = min(w, max(soft_left + 20, round(320 * scale)))
    soft_threshold = max(4, round(16 * scale))
    soft_rows: List[int] = []
    for y in range(h):
        hits = 0
        for x in range(soft_left, soft_right):
            r, g, b = px[x, y]
            if max(r, g, b) > 100 and max(r, g, b) - min(r, g, b) > 15:
                hits += 1
        soft_rows.append(hits)

    intervals: List[Tuple[int, int]] = []
    start: Optional[int] = None
    last_hit = -10
    for y, hits in enumerate(soft_rows):
        if hits >= soft_threshold:
            if start is None:
                start = y
            last_hit = y
        elif start is not None and y - last_hit > 2:
            intervals.append((start, last_hit + 1))
            start = None
    if start is not None:
        intervals.append((start, last_hit + 1))

    fallback: List[BBox] = []
    for top, bottom in intervals:
        height = bottom - top
        if not (min_card_size <= height <= max_card_size + round(12 * scale)):
            continue

        xs: List[int] = []
        left_colour = 0
        right_colour = 0
        for y in range(top, bottom):
            for x in range(soft_left, soft_right):
                r, g, b = px[x, y]
                if max(r, g, b) > 100 and max(r, g, b) - min(r, g, b) > 15:
                    xs.append(x)
                    left_colour += 1
            for x in range(soft_right, w):
                r, g, b = px[x, y]
                if max(r, g, b) > 100 and max(r, g, b) - min(r, g, b) > 15:
                    right_colour += 1

        if not xs or right_colour > left_colour * 0.6:
            continue
        left = min(xs)
        right = max(xs) + 1
        width = right - left
        if not (min_card_size <= width <= max_card_size + round(12 * scale)):
            continue
        if not 0.78 <= width / max(1, height) <= 1.28:
            continue
        fallback.append((left, top, right, bottom))

    def overlaps(a: BBox, b: BBox) -> bool:
        ax = (a[0] + a[2]) / 2
        ay = (a[1] + a[3]) / 2
        bx = (b[0] + b[2]) / 2
        by = (b[1] + b[3]) / 2
        return abs(ax - bx) <= max(8, 20 * scale) and abs(ay - by) <= max(8, 20 * scale)

    for box in fallback:
        if not any(overlaps(box, old) for old in components):
            components.append(box)

    components.sort(key=lambda b: (b[1], b[0]))
    return components


def _group_duplicates(candidates: List[Dict[str, Any]], threshold: int = 6) -> int:
    n = len(candidates)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for i in range(n):
        for j in range(i + 1, n):
            if _hamming_distance(candidates[i]["dhash"], candidates[j]["dhash"]) <= threshold:
                union(i, j)

    groups: Dict[int, List[int]] = {}
    for idx in range(n):
        groups.setdefault(find(idx), []).append(idx)

    group_index = 1
    for _, indices in sorted(groups.items(), key=lambda t: min(t[1])):
        if len(indices) <= 1:
            continue
        gid = f"dup-{group_index:02d}"
        ids = [candidates[i]["id"] for i in indices]
        for i in indices:
            candidates[i]["duplicateGroup"] = gid
            candidates[i]["duplicateCandidateIds"] = [x for x in ids if x != candidates[i]["id"]]
        group_index += 1

    for c in candidates:
        if "duplicateGroup" not in c:
            c["duplicateGroup"] = None
            c["duplicateCandidateIds"] = []

    return group_index - 1


def _write_contact_sheet(candidates: List[Dict[str, Any]], output_path: Path) -> None:
    if not candidates:
        img = Image.new("RGB", (640, 120), (245, 245, 245))
        draw = ImageDraw.Draw(img)
        draw.text((20, 50), "No candidates found", fill=(30, 30, 30))
        img.save(output_path)
        return

    thumb = 192
    label_h = 42
    cols = 4
    rows = math.ceil(len(candidates) / cols)
    sheet = Image.new("RGB", (cols * thumb, rows * (thumb + label_h)), (242, 242, 242))
    draw = ImageDraw.Draw(sheet)

    for idx, c in enumerate(candidates):
        r = idx // cols
        col = idx % cols
        x = col * thumb
        y = r * (thumb + label_h)

        crop = Image.open(c["sourcePath"]).convert("RGB").crop(tuple(c["box"]))
        sheet.paste(crop, (x, y))

        draw.rectangle((x, y + thumb, x + thumb - 1, y + thumb + label_h - 1), fill=(255, 255, 255))
        label1 = f"#{c['orderFromTop']:02d} {c['id']} {c['estimatedRarity']}"
        label2 = c["source"]
        draw.text((x + 4, y + thumb + 4), label1, fill=(20, 20, 20))
        draw.text((x + 4, y + thumb + 21), label2, fill=(70, 70, 70))

    sheet.save(output_path)


def run_detection(slug: str, project_root: Path) -> Dict[str, Any]:
    input_dir = _resolve_input_dir(project_root, slug)
    screenshots = _list_screenshots(input_dir)

    output_dir = project_root / "scripts" / "aimy-crop" / "output" / slug
    output_dir.mkdir(parents=True, exist_ok=True)
    candidates_path = output_dir / "candidates.json"
    contact_sheet_path = output_dir / "contact-sheet.png"

    candidates: List[Dict[str, Any]] = []
    global_order = 1
    for src in screenshots:
        image = Image.open(src).convert("RGB")
        boxes = _detect_boxes(image)
        for box in boxes:
            crop = image.crop(box)
            cand_id = f"c{global_order:04d}"
            candidates.append(
                {
                    "id": cand_id,
                    "source": src.name,
                    "sourcePath": str(src),
                    "box": [int(box[0]), int(box[1]), int(box[2]), int(box[3])],
                    "estimatedRarity": _estimate_rarity(image, box),
                    "orderFromTop": global_order,
                    "dhash": _compute_dhash(crop),
                }
            )
            global_order += 1

    duplicate_groups = _group_duplicates(candidates)

    for c in candidates:
        c.pop("sourcePath", None)

    payload = {
        "slug": slug,
        "inputDir": str(input_dir),
        "candidateCount": len(candidates),
        "duplicateGroupCount": duplicate_groups,
        "candidates": candidates,
    }
    candidates_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    sheet_candidates = []
    for c in candidates:
        c2 = dict(c)
        c2["sourcePath"] = str(input_dir / c["source"])
        sheet_candidates.append(c2)
    _write_contact_sheet(sheet_candidates, contact_sheet_path)

    return {
        "slug": slug,
        "inputDir": str(input_dir),
        "candidatesPath": str(candidates_path),
        "contactSheetPath": str(contact_sheet_path),
        "candidateCount": len(candidates),
        "duplicateGroupCount": duplicate_groups,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect card candidates from gacha screenshots")
    parser.add_argument("slug", help="gacha slug")
    parser.add_argument("--project-root", default=".", help="project root")
    args = parser.parse_args()

    result = run_detection(args.slug, Path(args.project_root).resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
