#!/usr/bin/env python3
import argparse
import json
import math
from pathlib import Path
import re
import sys

# Fallback import check with clear message.
try:
    from PIL import Image, ImageDraw
except Exception:
    print('Pillow is required. Install with: python3 -m pip install --user Pillow')
    sys.exit(1)


def load_gacha_items_count(gacha_js_path: Path) -> int:
    # Parse JS object by converting export default to CommonJS in Node-like style using regex fallback.
    text = gacha_js_path.read_text(encoding='utf-8')
    # Minimal parse for items array length without executing arbitrary code.
    m = re.search(r"items\s*:\s*\[", text)
    if not m:
        raise ValueError(f'items array not found in {gacha_js_path}')
    start = m.end() - 1
    depth = 0
    i = start
    while i < len(text):
        ch = text[i]
        if ch == '[':
            depth += 1
        elif ch == ']':
            depth -= 1
            if depth == 0:
                arr = text[start : i + 1]
                # Count object literals at depth 1 by simple pattern. Assumes each item begins with "{".
                return len(re.findall(r"\{\s*id\s*:", arr))
        i += 1
    raise ValueError(f'failed to parse items array in {gacha_js_path}')


def detect_card_boxes(image_path: Path):
    img = Image.open(image_path).convert('RGB')
    w, h = img.size
    px = img.load()
    max_x = min(360, w)

    mask = [[False] * max_x for _ in range(h)]
    for y in range(h):
        for x in range(max_x):
            r, g, b = px[x, y]
            mx = max(r, g, b)
            mn = min(r, g, b)
            if mx - mn > 40 and mx > 120:
                mask[y][x] = True

    visited = [[False] * max_x for _ in range(h)]
    dirs = ((1, 0), (-1, 0), (0, 1), (0, -1))
    comps = []

    from collections import deque

    for y in range(h):
        for x in range(max_x):
            if not mask[y][x] or visited[y][x]:
                continue
            q = deque([(x, y)])
            visited[y][x] = True
            min_x = max_x2 = x
            min_y = max_y = y
            cnt = 0
            while q:
                cx, cy = q.popleft()
                cnt += 1
                if cx < min_x:
                    min_x = cx
                if cx > max_x2:
                    max_x2 = cx
                if cy < min_y:
                    min_y = cy
                if cy > max_y:
                    max_y = cy
                for dx, dy in dirs:
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < max_x and 0 <= ny < h and mask[ny][nx] and not visited[ny][nx]:
                        visited[ny][nx] = True
                        q.append((nx, ny))
            bw = max_x2 - min_x + 1
            bh = max_y - min_y + 1
            if 170 <= bw <= 220 and 170 <= bh <= 220 and cnt > 3000 and min_x < 140:
                comps.append((min_x, min_y, max_x2 + 1, max_y + 1))

    comps.sort(key=lambda t: (t[1], t[0]))
    return comps


def write_candidate_sheet(slug: str, sources, root: Path, output_dir: Path):
    cards = []
    for src in sources:
        p = root / 'public' / 'images' / 'gacha' / slug / src
        if not p.exists():
            continue
        boxes = detect_card_boxes(p)
        img = Image.open(p).convert('RGB')
        for i, box in enumerate(boxes, start=1):
            cards.append((f"{src.replace('.PNG', '')}_{i:02d}", img.crop(box)))

    if not cards:
        return None

    thumb = 192
    label_h = 28
    cols = 2
    rows = math.ceil(len(cards) / cols)
    sheet = Image.new('RGB', (cols * thumb, rows * (thumb + label_h)), (245, 245, 245))
    draw = ImageDraw.Draw(sheet)
    for idx, (label, card) in enumerate(cards):
        r = idx // cols
        c = idx % cols
        x = c * thumb
        y = r * (thumb + label_h)
        sheet.paste(card.convert('RGB').resize((thumb, thumb)), (x, y))
        draw.rectangle((x, y + thumb, x + thumb - 1, y + thumb + label_h - 1), fill=(255, 255, 255))
        draw.text((x + 6, y + thumb + 7), label, fill=(20, 20, 20))

    output_dir.mkdir(parents=True, exist_ok=True)
    out = output_dir / f'{slug}-candidates-sheet.png'
    sheet.save(out)
    return out


def generate_from_mapping(config, root: Path):
    slug = config['slug']
    out_rel = config.get('outputDir', f'public/images/items/{slug}')
    out_dir = root / out_rel
    out_dir.mkdir(parents=True, exist_ok=True)

    mappings = config['mappings']
    for m in mappings:
        src = root / 'public' / 'images' / 'gacha' / slug / m['source']
        if not src.exists():
            raise FileNotFoundError(f'missing source: {src}')
        box = tuple(m['cropBox'])
        if len(box) != 4:
            raise ValueError(f'cropBox must be [left, top, right, bottom]: {m}')
        img = Image.open(src).convert('RGBA')
        crop = img.crop(box)
        if crop.size != (192, 192):
            raise ValueError(f'crop size must be 192x192, got {crop.size} for {m["output"]}')
        crop.save(out_dir / m['output'], 'PNG')


def verify_output(config, root: Path):
    slug = config['slug']
    out_rel = config.get('outputDir', f'public/images/items/{slug}')
    out_dir = root / out_rel

    outputs = [m['output'] for m in config['mappings']]
    missing = []
    bad_size = []
    for name in outputs:
        p = out_dir / name
        if not p.exists():
            missing.append(str(p))
            continue
        im = Image.open(p)
        if im.size != (192, 192):
            bad_size.append((str(p), im.size))

    return {
        'expectedCount': len(outputs),
        'missing': missing,
        'badSize': bad_size,
    }


def main():
    parser = argparse.ArgumentParser(description='Extract gacha item card images from screenshot mappings.')
    parser.add_argument('slug', help='gacha slug, e.g. monochrome-rendezvous')
    parser.add_argument('--root', default='.', help='project root')
    parser.add_argument('--config', default=None, help='config path (default: scripts/gacha-configs/{slug}.json)')
    parser.add_argument('--no-generate', action='store_true', help='skip png generation')
    args = parser.parse_args()

    root = Path(args.root).resolve()
    config_path = Path(args.config) if args.config else (root / 'scripts' / 'gacha-configs' / f'{args.slug}.json')
    if not config_path.exists():
        print(f'Config not found: {config_path}')
        return 1

    cfg = json.loads(config_path.read_text(encoding='utf-8'))
    slug = cfg['slug']

    gacha_file = root / 'src' / 'data' / 'gachas' / f'{slug}.js'
    if not gacha_file.exists():
        print(f'Gacha file not found: {gacha_file}')
        return 1

    items_count = load_gacha_items_count(gacha_file)
    print(f'items count: {items_count}')
    print(f'mapping count: {len(cfg["mappings"])}')

    candidate_sheet = write_candidate_sheet(
        slug,
        cfg.get('sourceScreenshots', []),
        root,
        root / 'scripts' / 'artifacts',
    )
    if candidate_sheet:
        print(f'candidate sheet: {candidate_sheet}')

    if not args.no_generate:
        generate_from_mapping(cfg, root)
        print('generated pngs from mapping')

    v = verify_output(cfg, root)
    print(f'expected outputs: {v["expectedCount"]}')
    print(f'missing outputs: {len(v["missing"])}')
    print(f'bad-size outputs: {len(v["badSize"])}')
    if v['missing']:
        for p in v['missing']:
            print('missing:', p)
    if v['badSize']:
        for p, size in v['badSize']:
            print('bad-size:', p, size)

    if len(cfg['mappings']) != items_count:
        print('WARNING: mapping count does not match items count. Do not auto-update gacha data.')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
