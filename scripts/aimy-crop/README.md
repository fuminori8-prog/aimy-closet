# Aimy Crop Tool v1

Minimal local Python tooling for candidate detection and batch export of gacha card images.

## Location
- scripts/aimy-crop/detect_cards.py
- scripts/aimy-crop/export_cards.py
- scripts/aimy-crop/process_gacha.py
- scripts/aimy-crop/configs/
- scripts/aimy-crop/output/

## Input
- public/images/gacha/{slug}/
- archive/gacha/{slug}/

The tool prefers public first, then archive.

## Output
- scripts/aimy-crop/output/{slug}/candidates.json
- scripts/aimy-crop/output/{slug}/contact-sheet.png
- scripts/aimy-crop/output/{slug}/items/*.png
- scripts/aimy-crop/output/{slug}/export-report.json
- scripts/aimy-crop/output/{slug}/preview.html
- scripts/aimy-crop/output/{slug}/preview-report.json

This tool never writes to public/images/items/{slug}/.

## Modes
Detect only:

```bash
python3 scripts/aimy-crop/process_gacha.py hikoboshi --detect
```

Export only:

```bash
python3 scripts/aimy-crop/process_gacha.py hikoboshi --export
```

Preview only:

```bash
python3 scripts/aimy-crop/process_gacha.py hikoboshi --preview
```

Detect + Export:

```bash
python3 scripts/aimy-crop/process_gacha.py hikoboshi --all
```

Auto config:

```bash
python3 scripts/aimy-crop/process_gacha.py hydrangea --auto-config
```

Publish (safe transaction):

```bash
python3 scripts/aimy-crop/process_gacha.py kyuketsuki --publish
```

Publish dry-run:

```bash
python3 scripts/aimy-crop/process_gacha.py kyuketsuki --publish --dry-run
```

Skip interactive confirmation (CI):

```bash
python3 scripts/aimy-crop/process_gacha.py kyuketsuki --publish --yes
```

`--export` and `--all` automatically regenerate `preview.html`.

## Preview purpose
`preview.html` is a one-page visual QA view to quickly catch number mismatch and wrong image mapping.

Each card shows:
- number
- item image
- item name
- rarity and category
- item id
- image path in data
- output file size
- status (`OK`, `警告`, `ERROR`)

## Visual verification workflow
1. Run export or preview generation.
2. Open `preview.html`.
3. Check each card with the checkbox `画像とアイテム名が一致`.
4. Use rarity/category filters or `未確認のみ表示` to focus.
5. Use `エラー・警告のみ表示` to inspect problematic cards.

The checkbox state is stored in browser localStorage per slug.

## Safe recommended workflow
1. `python3 scripts/aimy-crop/process_gacha.py kyuketsuki --detect`
2. `python3 scripts/aimy-crop/process_gacha.py kyuketsuki --auto-config`
3. `python3 scripts/aimy-crop/process_gacha.py kyuketsuki --export`
4. `open scripts/aimy-crop/output/kyuketsuki/preview.html`
5. 必要なら候補番号を上下ボタンで並び替えし、`config保存`で`{slug}.json`を書き出し、`scripts/aimy-crop/configs/`へ配置
6. 全画像を目視確認して全件チェック
7. `確認結果を書き出す`で`review-status-YYYYMMDD-HHMMSS.json`をダウンロードし、`scripts/aimy-crop/output/kyuketsuki/`へ配置
8. `python3 scripts/aimy-crop/process_gacha.py kyuketsuki --publish --dry-run`
9. `python3 scripts/aimy-crop/process_gacha.py kyuketsuki --publish`
10. サイトを確認

`review-status-YYYYMMDD-HHMMSS.json` は全件チェック時のみ書き出し可能です。
publishは同一slugフォルダ内の最新review-statusファイルを自動選択します。

## Status meaning
- `OK`: output image exists, size is `192x192`, numbering/order is aligned.
- `警告`: output is valid, but data image is not reflected in production (`placeholder` or unset).
- `ERROR`: missing output image, wrong image size, or mismatched production image path format.

## Open preview in Finder/browser

```bash
open scripts/aimy-crop/output/kyuketsuki/preview.html
```

## review-status-YYYYMMDD-HHMMSS.json format

```json
{
  "slug": "kyuketsuki",
  "reviewedAt": "2026-07-13T00:00:00.000Z",
  "checkedItems": ["01", "02"],
  "checkedCount": 2,
  "totalCount": 22,
  "allChecked": false
}
```

## Publish transaction notes
- Publish checks preview-report/review-status/output completeness before modifying production.
- Backups are created at `scripts/aimy-crop/backups/{slug}/{timestamp}/`.
- If `npm run build` fails, images and gacha data are restored from backup automatically.

## Restore manually
If needed, restore from the latest backup:
- image backup: `scripts/aimy-crop/backups/{slug}/{timestamp}/images-items`
- data backup: `scripts/aimy-crop/backups/{slug}/{timestamp}/gacha-js`

## Config format
Path: scripts/aimy-crop/configs/{slug}.json

Each item supports either:
- candidate reference (`candidateId` or `candidateIndex`) from candidates.json
- direct source and box (`source`, `box`)

Example:

```json
{
  "slug": "hikoboshi",
  "items": [
    {
      "output": "01.png",
      "candidateId": "c0001"
    },
    {
      "output": "02.png",
      "source": "IMG_7116.PNG",
      "box": [96, 1887, 288, 2079]
    }
  ]
}
```

## Notes
- Duplicate candidates are grouped with perceptual hash and recorded in candidates.json as duplicateGroup.
- Duplicate groups are not auto-removed.
- Export keeps crop geometry without stretching; if crop is smaller than 192x192, transparent padding is applied.
