# Image Extraction Scripts

## Overview
`scripts/extract-gacha-items.py` helps reuse the validated card-frame extraction flow.

It does the following:
- checks `items` count in `src/data/gachas/{slug}.js`
- lists card candidates from screenshots and outputs a candidate sheet
- generates 192x192 PNGs from a mapping JSON
- verifies output count and output dimensions

## Required files
- script: `scripts/extract-gacha-items.py`
- config: `scripts/gacha-configs/{slug}.json`

## Config format (minimum)
- `slug`
- `sourceScreenshots`
- `mappings`
  - `index`
  - `source`
  - `cropBox` (`[left, top, right, bottom]`)
  - `output`

## Example run
```bash
python3 scripts/extract-gacha-items.py monochrome-rendezvous
```

This script intentionally does **not** auto-map item order from detected candidates.
Use config mapping to avoid wrong registrations.
