#!/usr/bin/env python3
"""Aimy Crop Tool v1 - generate preview.html for visual QA."""

from __future__ import annotations

import argparse
import html
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image


def _load_candidates(slug: str, project_root: Path) -> List[Dict[str, Any]]:
  path = project_root / "scripts" / "aimy-crop" / "output" / slug / "candidates.json"
  if not path.exists():
    return []
  obj = json.loads(path.read_text(encoding="utf-8"))
  out: List[Dict[str, Any]] = []
  for idx, c in enumerate(obj.get("candidates", []), start=1):
    cp = dict(c)
    cp["candidateIndex"] = idx
    out.append(cp)
  return out


def _load_config_items(slug: str, project_root: Path) -> List[Dict[str, Any]]:
  path = project_root / "scripts" / "aimy-crop" / "configs" / f"{slug}.json"
  if not path.exists():
    return []
  obj = json.loads(path.read_text(encoding="utf-8"))
  items = obj.get("items", [])
  return items if isinstance(items, list) else []


def _candidate_maps(candidates: List[Dict[str, Any]]) -> Tuple[Dict[str, Dict[str, Any]], Dict[int, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
  by_id: Dict[str, Dict[str, Any]] = {}
  by_index: Dict[int, Dict[str, Any]] = {}
  by_source_box: Dict[str, Dict[str, Any]] = {}
  for c in candidates:
    cid = str(c.get("id", ""))
    cidx = int(c.get("candidateIndex", 0))
    source = str(c.get("source", ""))
    box = c.get("box", [])
    key = f"{source}|{','.join(str(v) for v in box)}"
    if cid:
      by_id[cid] = c
    if cidx > 0:
      by_index[cidx] = c
    by_source_box[key] = c
  return by_id, by_index, by_source_box


def _find_candidate_for_config_item(item: Dict[str, Any], by_id: Dict[str, Dict[str, Any]], by_index: Dict[int, Dict[str, Any]], by_source_box: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
  if "candidateId" in item:
    c = by_id.get(str(item.get("candidateId")))
    if c:
      return c
  if "candidateIndex" in item:
    try:
      idx = int(item.get("candidateIndex"))
      c = by_index.get(idx)
      if c:
        return c
    except Exception:
      pass
  source = str(item.get("source", ""))
  box = item.get("box", [])
  if source and isinstance(box, list) and len(box) == 4:
    key = f"{source}|{','.join(str(v) for v in box)}"
    return by_source_box.get(key)
  return None


def _load_gacha(slug: str, project_root: Path) -> Dict[str, Any]:
    gacha_path = project_root / "src" / "data" / "gachas" / f"{slug}.js"
    if not gacha_path.exists():
        raise FileNotFoundError(f"Gacha file not found: {gacha_path}")

    node_script = r"""
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const file = process.argv[1];
const src = fs.readFileSync(file, 'utf8').replace(/export\s+default/, 'module.exports =');
const ctx = { module: { exports: {} }, exports: {} };
vm.runInNewContext(src, ctx, { filename: file });
const g = ctx.module.exports;
const items = (g.items || []).map((x) => ({
  id: x.id,
  name: x.name,
  rarity: x.rarity,
  category: x.category,
  image: x.image,
}));
console.log(JSON.stringify({
  slug: g.slug,
  title: g.title,
  infoStatus: g.infoStatus,
  items,
}));
"""
    proc = subprocess.run(
        ["node", "-e", node_script, str(gacha_path)],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout)


def _image_size(path: Path) -> List[int] | None:
    if not path.exists():
        return None
    with Image.open(path) as img:
        return [img.size[0], img.size[1]]


def _build_items(slug: str, gacha: Dict[str, Any], items_dir: Path, project_root: Path) -> Dict[str, Any]:
  rows: List[Dict[str, Any]] = []
  items = gacha.get("items", [])
  config_items = _load_config_items(slug, project_root)
  candidates = _load_candidates(slug, project_root)
  by_id, by_index, by_source_box = _candidate_maps(candidates)

  ok_count = 0
  warn_count = 0
  error_count = 0
  output_count = 0
  all_images_set = True

  for idx, item in enumerate(items, start=1):
      number = f"{idx:02d}"
      output_name = f"{number}.png"
      output_path = items_dir / output_name
      expected_image_path = f"/images/items/{slug}/{output_name}"
      image_value = item.get("image")
      image_set = bool(image_value and image_value != "placeholder")
      all_images_set = all_images_set and image_set

      size = _image_size(output_path)
      exists = size is not None
      is_192 = bool(size and size[0] == 192 and size[1] == 192)
      if exists:
          output_count += 1

      errors: List[str] = []
      warnings: List[str] = []

      if not exists:
          errors.append("出力画像がありません")
      elif not is_192:
          errors.append("画像サイズが192x192ではありません")

      image_path_ok = (not image_set) or (image_value == expected_image_path)
      if image_set and not image_path_ok:
          errors.append("本番imageパスが期待形式と不一致です")

      if not errors and not image_set:
          warnings.append("本番未反映")

      if errors:
          level = "error"
          status_label = "ERROR"
          error_count += 1
      elif warnings:
          level = "warning"
          status_label = "警告"
          warn_count += 1
      else:
          level = "ok"
          status_label = "OK"
          ok_count += 1

      cfg_item = config_items[idx - 1] if idx - 1 < len(config_items) else {}
      cand = _find_candidate_for_config_item(cfg_item, by_id, by_index, by_source_box)
      cand_index = int(cand.get("candidateIndex", 0)) if cand else 0
      cand_source = str(cand.get("source", cfg_item.get("source", ""))) if (cand or cfg_item) else ""
      cand_box = cand.get("box", cfg_item.get("box", [])) if (cand or cfg_item) else []

      rows.append(
          {
              "index": idx,
              "number": number,
              "outputName": output_name,
              "outputRel": f"items/{output_name}",
              "itemId": item.get("id") or "",
              "name": item.get("name") or "",
              "rarity": item.get("rarity") or "UNKNOWN",
              "category": item.get("category") or "-",
              "imagePath": image_value if image_value else "",
              "expectedImagePath": expected_image_path,
              "imageSet": image_set,
              "exists": exists,
              "size": size,
              "is192": is_192,
              "status": status_label,
              "level": level,
              "errors": errors,
              "warnings": warnings,
              "candidateIndex": cand_index,
              "candidateLabel": f"候補{cand_index}" if cand_index > 0 else "候補未設定",
              "candidateSource": cand_source,
              "candidateBox": cand_box if isinstance(cand_box, list) and len(cand_box) == 4 else [],
          }
      )

  items_count = len(rows)
  all_192 = items_count > 0 and all(r["exists"] and r["is192"] for r in rows)
  no_missing_numbers = items_count > 0 and all((items_dir / f"{i:02d}.png").exists() for i in range(1, items_count + 1))
  completion_candidate = (
      items_count > 0
      and output_count == items_count
      and all_192
      and no_missing_numbers
      and error_count == 0
  )

  categories = sorted({str(r["category"]) for r in rows if r["category"]})

  return {
      "items": rows,
      "summary": {
          "itemsCount": items_count,
          "outputImageCount": output_count,
          "okCount": ok_count,
          "warningCount": warn_count,
          "errorCount": error_count,
          "infoStatus": gacha.get("infoStatus") or "",
          "allImagesSet": all_images_set,
          "all192": all_192,
          "noMissingNumbers": no_missing_numbers,
          "completionCandidate": completion_candidate,
          "categories": categories,
      },
  }


def _card_html(item: Dict[str, Any]) -> str:
    rarity = html.escape(item["rarity"])
    category = html.escape(str(item["category"]))
    status = html.escape(item["status"])
    item_id = html.escape(item["itemId"])
    name = html.escape(item["name"])
    image_path = html.escape(item["imagePath"] or "(未設定)")
    output_size = "-"
    if item["size"]:
        output_size = f"{item['size'][0]}x{item['size'][1]}"

    issue_text = ""
    issue_lines = item["errors"] + item["warnings"]
    if issue_lines:
        issue_text = "<div class=\"issue-text\">" + " / ".join(html.escape(x) for x in issue_lines) + "</div>"

    cand_source = html.escape(item.get("candidateSource", ""))
    cand_box = item.get("candidateBox", [])
    cand_box_text = ",".join(str(v) for v in cand_box) if isinstance(cand_box, list) and len(cand_box) == 4 else ""

    return f"""
<div class="item-card {item['level']}" data-rarity="{html.escape(item['rarity'])}" data-category="{category}" data-level="{item['level']}" data-index="{item['index']}" data-candidate-index="{item.get('candidateIndex', 0)}" data-candidate-source="{cand_source}" data-candidate-box="{html.escape(cand_box_text)}">
  <div class="rarity-head {item['rarity'].lower()}">{rarity}</div>
  <div class="num">{item['number']}</div>
  <div class="line candidate-line" data-role="candidate-line">{html.escape(item.get('candidateLabel', '候補未設定'))}</div>
  <div class="move-row">
    <button type="button" class="move-btn move-up">↑</button>
    <button type="button" class="move-btn move-down">↓</button>
  </div>
  <div class="img-wrap"><img src="{html.escape(item['outputRel'])}" alt="{name}"></div>
  <div class="name">{name}</div>
  <div class="meta">{rarity} / {category}</div>
  <div class="line">id: {item_id}</div>
  <div class="line">image: {image_path}</div>
  <div class="line">output: {output_size}</div>
  <div class="line status {item['level']}">status: {status}</div>
  {issue_text}
  <label class="check-row">
    <input type="checkbox" class="name-match-check" data-index="{item['index']}">
    画像とアイテム名が一致
  </label>
</div>
"""


def _build_html(slug: str, gacha: Dict[str, Any], payload: Dict[str, Any]) -> str:
    items = payload["items"]
    summary = payload["summary"]
    cards_html = "\n".join(_card_html(item) for item in items)

    rarity_options = """
<option value="ALL">すべて</option>
<option value="SSR">SSR</option>
<option value="SR">SR</option>
<option value="NR">NR</option>
"""
    category_options = "\n".join(
        f"<option value=\"{html.escape(c)}\">{html.escape(c)}</option>" for c in summary["categories"]
    )

    state_text = "情報収集完了候補" if summary["completionCandidate"] else "情報収集継続中"
    state_class = "candidate-ok" if summary["completionCandidate"] else "candidate-warn"

    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Aimy Crop Preview - {html.escape(slug)}</title>
<style>
:root {{
  --bg: #f4f5f7;
  --card: #ffffff;
  --text: #1d2530;
  --muted: #6d7482;
  --ok: #198754;
  --warn: #e3a100;
  --err: #d93025;
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: radial-gradient(circle at top, #ffffff, var(--bg)); color: var(--text); }}
.container {{ max-width: 1360px; margin: 0 auto; padding: 20px; }}
.header {{ background: var(--card); border-radius: 14px; padding: 18px; box-shadow: 0 4px 16px rgba(0,0,0,0.06); }}
.title {{ font-size: 24px; font-weight: 800; margin: 0 0 4px; }}
.sub {{ color: var(--muted); margin: 0 0 12px; }}
.summary {{ display: grid; grid-template-columns: repeat(4, minmax(120px, 1fr)); gap: 10px; margin-bottom: 12px; }}
.kpi {{ background: #f8f9fb; border-radius: 10px; padding: 10px; }}
.kpi .k {{ font-size: 12px; color: var(--muted); }}
.kpi .v {{ font-size: 20px; font-weight: 800; }}
.note {{ font-size: 13px; margin: 6px 0; }}
.candidate-ok {{ color: var(--ok); font-weight: 800; }}
.candidate-warn {{ color: var(--warn); font-weight: 800; }}
.controls {{ margin-top: 14px; display: grid; grid-template-columns: repeat(4, minmax(120px, 1fr)); gap: 10px; }}
select, .toggle {{ width: 100%; border: 1px solid #d0d6e0; border-radius: 8px; background: #fff; padding: 8px; font-size: 14px; }}
.toggle {{ display: flex; align-items: center; gap: 8px; }}
.actions {{ margin-top: 10px; display: flex; flex-wrap: wrap; gap: 8px; }}
.btn {{ border: 1px solid #c7cfdd; background: #fff; padding: 8px 10px; border-radius: 8px; font-weight: 700; cursor: pointer; }}
.btn.primary {{ background: #1f6feb; color: #fff; border-color: #1f6feb; }}
.btn.secondary {{ background: #f6f8fc; color: #2a3445; border-color: #c7cfdd; }}
.btn:disabled {{ opacity: 0.45; cursor: not-allowed; }}
.json-preview {{ margin-top: 10px; width: 100%; min-height: 120px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; border: 1px solid #d0d6e0; border-radius: 8px; padding: 8px; background: #f9fbff; }}
.move-row {{ display: flex; gap: 6px; margin-bottom: 8px; }}
.move-btn {{ border: 1px solid #ccd4e1; background: #fff; border-radius: 6px; padding: 3px 7px; font-size: 12px; cursor: pointer; }}
.candidate-line {{ font-weight: 700; color: #38508a; margin-bottom: 4px; }}
.grid {{ margin-top: 16px; display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; }}
.item-card {{ background: var(--card); border: 2px solid #e2e6ed; border-radius: 14px; padding: 10px; box-shadow: 0 3px 10px rgba(0,0,0,0.05); }}
.item-card.ok {{ border-color: #98dfb5; }}
.item-card.warning {{ border-color: #f4cf73; }}
.item-card.error {{ border-color: var(--err); }}
.rarity-head {{ font-size: 12px; font-weight: 800; margin-bottom: 4px; }}
.rarity-head.ssr {{ background: linear-gradient(90deg,#56d8ff,#8b8cff,#ff6ae8); -webkit-background-clip: text; color: transparent; }}
.rarity-head.sr {{ background: linear-gradient(90deg,#f8d33f,#ff8f24); -webkit-background-clip: text; color: transparent; }}
.rarity-head.nr {{ color: #677085; }}
.num {{ font-size: 24px; font-weight: 900; line-height: 1; margin-bottom: 8px; }}
.img-wrap {{ width: 100%; aspect-ratio: 1 / 1; background: #f2f6fb; border-radius: 10px; display: flex; align-items: center; justify-content: center; overflow: hidden; margin-bottom: 8px; }}
.img-wrap img {{ width: 100%; height: 100%; object-fit: contain; image-rendering: auto; }}
.name {{ font-size: 15px; font-weight: 800; margin-bottom: 4px; min-height: 38px; }}
.meta {{ font-size: 13px; color: #1f2d40; margin-bottom: 4px; }}
.line {{ font-size: 12px; color: var(--muted); word-break: break-all; }}
.status.ok {{ color: var(--ok); font-weight: 800; }}
.status.warning {{ color: var(--warn); font-weight: 800; }}
.status.error {{ color: var(--err); font-weight: 800; }}
.issue-text {{ margin-top: 4px; font-size: 12px; color: var(--err); }}
.check-row {{ margin-top: 8px; display: flex; gap: 8px; align-items: center; font-size: 13px; }}
.badge {{ display: inline-block; background: #eef2f8; padding: 4px 8px; border-radius: 999px; font-size: 12px; margin-left: 4px; }}
@media (max-width: 1100px) {{ .grid {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }} }}
@media (max-width: 760px) {{
  .summary {{ grid-template-columns: repeat(2, minmax(120px, 1fr)); }}
  .controls {{ grid-template-columns: repeat(2, minmax(120px, 1fr)); }}
  .grid {{ grid-template-columns: repeat(1, minmax(0, 1fr)); }}
}}
</style>
</head>
<body>
  <div class="container">
    <section class="header">
      <h1 class="title">{html.escape(gacha.get('title') or slug)}</h1>
      <p class="sub">slug: {html.escape(slug)}</p>
      <div class="summary">
        <div class="kpi"><div class="k">データ内items件数</div><div class="v" id="kItems">{summary['itemsCount']}</div></div>
        <div class="kpi"><div class="k">出力画像件数</div><div class="v">{summary['outputImageCount']}</div></div>
        <div class="kpi"><div class="k">OK / 警告 / エラー</div><div class="v">{summary['okCount']} / {summary['warningCount']} / {summary['errorCount']}</div></div>
        <div class="kpi"><div class="k">infoStatus</div><div class="v">{html.escape(summary['infoStatus'])}</div></div>
      </div>
      <p class="note">全itemにimage設定: <strong>{'YES' if summary['allImagesSet'] else 'NO'}</strong></p>
      <p class="note {state_class}">{state_text}</p>
      <p class="note">最終確定には人間の目視確認が必要です。</p>
      <p class="note">目視確認 <strong id="checkedCount">0</strong> / <strong id="totalCount">{summary['itemsCount']}</strong>件 <span id="visualDone" class="badge">未完了</span></p>
      <p class="note">最終確認日時: <strong id="reviewedAt">-</strong></p>
      <div class="controls">
        <select id="rarityFilter">{rarity_options}</select>
        <select id="categoryFilter"><option value="ALL">カテゴリ: すべて</option>{category_options}</select>
        <label class="toggle"><input type="checkbox" id="uncheckedOnly"> 未確認のみ表示</label>
        <label class="toggle"><input type="checkbox" id="issueOnly"> エラー・警告のみ表示</label>
      </div>
      <div class="actions">
        <button type="button" id="checkAll" class="btn">全選択</button>
        <button type="button" id="uncheckAll" class="btn">全解除</button>
        <button type="button" id="exportReview" class="btn primary" disabled>確認結果を書き出す</button>
        <button type="button" id="saveConfig" class="btn secondary">config保存</button>
      </div>
      <textarea id="reviewJsonPreview" class="json-preview" readonly></textarea>
      <textarea id="configJsonPreview" class="json-preview" readonly></textarea>
      <p class="note">保存方法: ボタンでダウンロードした review-status-YYYYMMDD-HHMMSS.json を scripts/aimy-crop/output/{html.escape(slug)}/ に配置してください。</p>
      <p class="note">config保存: ダウンロードした {html.escape(slug)}.json を scripts/aimy-crop/configs/ に配置してください。</p>
    </section>

    <section class="grid" id="cardsGrid">
      {cards_html}
    </section>
  </div>

<script>
(() => {{
  const slug = {json.dumps(slug)};
  const storageKey = `aimy-crop-preview:${{slug}}:checks:v1`;
  const cards = Array.from(document.querySelectorAll('.item-card'));
  const rarityFilter = document.getElementById('rarityFilter');
  const categoryFilter = document.getElementById('categoryFilter');
  const uncheckedOnly = document.getElementById('uncheckedOnly');
  const issueOnly = document.getElementById('issueOnly');
  const checkedCountEl = document.getElementById('checkedCount');
  const totalCountEl = document.getElementById('totalCount');
  const visualDoneEl = document.getElementById('visualDone');
  const reviewedAtEl = document.getElementById('reviewedAt');
  const exportBtn = document.getElementById('exportReview');
  const checkAllBtn = document.getElementById('checkAll');
  const uncheckAllBtn = document.getElementById('uncheckAll');
  const reviewPreview = document.getElementById('reviewJsonPreview');
  const reviewMetaKey = `${{storageKey}}:meta:v1`;
  const configPreview = document.getElementById('configJsonPreview');
  const saveConfigBtn = document.getElementById('saveConfig');

  function loadChecks() {{
    try {{
      const raw = localStorage.getItem(storageKey);
      if (!raw) return {{}};
      const parsed = JSON.parse(raw);
      return parsed && typeof parsed === 'object' ? parsed : {{}};
    }} catch (_e) {{
      return {{}};
    }}
  }}

  function saveChecks(state) {{
    localStorage.setItem(storageKey, JSON.stringify(state));
  }}

  function loadReviewMeta() {{
    try {{
      const raw = localStorage.getItem(reviewMetaKey);
      if (!raw) return {{}};
      const parsed = JSON.parse(raw);
      return parsed && typeof parsed === 'object' ? parsed : {{}};
    }} catch (_e) {{
      return {{}};
    }}
  }}

  function saveReviewMeta(meta) {{
    localStorage.setItem(reviewMetaKey, JSON.stringify(meta));
  }}

  let checks = loadChecks();
  let reviewMeta = loadReviewMeta();

  function buildReviewStatus() {{
    const checkedItems = cards
      .filter((c) => c.querySelector('.name-match-check').checked)
      .map((c) => String(c.dataset.index).padStart(2, '0'));
    const nowIso = new Date().toISOString();
    return {{
      slug,
      reviewedAt: nowIso,
      checkedItems,
      checkedCount: checkedItems.length,
      totalCount: cards.length,
      allChecked: checkedItems.length === cards.length && cards.length > 0,
    }};
  }}

  function getAssignment(card) {{
    const boxRaw = card.dataset.candidateBox || '';
    const box = boxRaw ? boxRaw.split(',').map((x) => Number(x)) : [];
    return {{
      candidateIndex: Number(card.dataset.candidateIndex || '0'),
      source: card.dataset.candidateSource || '',
      box,
    }};
  }}

  function setAssignment(card, data) {{
    card.dataset.candidateIndex = String(data.candidateIndex || 0);
    card.dataset.candidateSource = data.source || '';
    card.dataset.candidateBox = Array.isArray(data.box) ? data.box.join(',') : '';
    const label = (data.candidateIndex && data.candidateIndex > 0) ? `候補${{data.candidateIndex}}` : '候補未設定';
    const line = card.querySelector('[data-role="candidate-line"]');
    if (line) line.textContent = label;
  }}

  function swapAssignments(a, b) {{
    if (a < 0 || b < 0 || a >= cards.length || b >= cards.length) return;
    const da = getAssignment(cards[a]);
    const db = getAssignment(cards[b]);
    setAssignment(cards[a], db);
    setAssignment(cards[b], da);
    renderConfigPreview();
  }}

  function buildConfigJson() {{
    const items = cards.map((card, i) => {{
      const a = getAssignment(card);
      return {{
        output: `${{String(i + 1).padStart(2, '0')}}.png`,
        source: a.source,
        box: a.box,
        candidateIndex: a.candidateIndex,
      }};
    }});
    return {{ slug, items }};
  }}

  function renderConfigPreview() {{
    configPreview.value = JSON.stringify(buildConfigJson(), null, 2);
  }}

  function saveConfigJson() {{
    const cfg = buildConfigJson();
    const text = JSON.stringify(cfg, null, 2);
    const blob = new Blob([text], {{ type: 'application/json' }});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${{slug}}.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }}

  function renderReviewPreview() {{
    const obj = buildReviewStatus();
    reviewPreview.value = JSON.stringify(obj, null, 2);
    reviewedAtEl.textContent = reviewMeta.reviewedAt || '-';
    exportBtn.disabled = !obj.allChecked;
  }}

  function applyChecksToInputs() {{
    for (const card of cards) {{
      const idx = String(card.dataset.index);
      const cb = card.querySelector('.name-match-check');
      cb.checked = Boolean(checks[idx]);
      cb.addEventListener('change', () => {{
        checks[idx] = cb.checked;
        saveChecks(checks);
        updateCounters();
        applyFilters();
        renderReviewPreview();
      }});

      const up = card.querySelector('.move-up');
      const down = card.querySelector('.move-down');
      const zeroBased = Number(card.dataset.index || '1') - 1;
      if (up) up.addEventListener('click', () => swapAssignments(zeroBased, zeroBased - 1));
      if (down) down.addEventListener('click', () => swapAssignments(zeroBased, zeroBased + 1));
    }}
  }}

  function updateCounters() {{
    const total = cards.length;
    const checked = cards.filter((c) => {{
      const cb = c.querySelector('.name-match-check');
      return cb.checked;
    }}).length;

    checkedCountEl.textContent = String(checked);
    totalCountEl.textContent = String(total);
    if (checked === total && total > 0) {{
      visualDoneEl.textContent = '目視確認完了';
      visualDoneEl.style.background = '#dff4e8';
      visualDoneEl.style.color = '#198754';
    }} else {{
      visualDoneEl.textContent = '未完了';
      visualDoneEl.style.background = '#eef2f8';
      visualDoneEl.style.color = '#5e6878';
    }}
  }}

  function setAllChecks(value) {{
    for (const card of cards) {{
      const idx = String(card.dataset.index);
      const cb = card.querySelector('.name-match-check');
      cb.checked = value;
      checks[idx] = value;
    }}
    saveChecks(checks);
    updateCounters();
    applyFilters();
    renderReviewPreview();
  }}

  function downloadReviewStatus() {{
    const obj = buildReviewStatus();
    if (!obj.allChecked) return;

    const now = new Date();
    const pad = (n) => String(n).padStart(2, '0');
    const filename = `review-status-${{now.getFullYear()}}${{pad(now.getMonth() + 1)}}${{pad(now.getDate())}}-${{pad(now.getHours())}}${{pad(now.getMinutes())}}${{pad(now.getSeconds())}}.json`;

    const text = JSON.stringify(obj, null, 2);
    const blob = new Blob([text], {{ type: 'application/json' }});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);

    reviewMeta = {{ reviewedAt: obj.reviewedAt, fileName: filename }};
    saveReviewMeta(reviewMeta);
    renderReviewPreview();
  }}

  function applyFilters() {{
    const r = rarityFilter.value;
    const c = categoryFilter.value;
    const u = uncheckedOnly.checked;
    const i = issueOnly.checked;

    for (const card of cards) {{
      const rarityOk = r === 'ALL' || card.dataset.rarity === r;
      const categoryOk = c === 'ALL' || card.dataset.category === c;
      const checked = card.querySelector('.name-match-check').checked;
      const uncheckedOk = !u || !checked;
      const level = card.dataset.level;
      const issueOk = !i || (level === 'warning' || level === 'error');
      card.style.display = rarityOk && categoryOk && uncheckedOk && issueOk ? '' : 'none';
    }}
  }}

  rarityFilter.addEventListener('change', applyFilters);
  categoryFilter.addEventListener('change', applyFilters);
  uncheckedOnly.addEventListener('change', applyFilters);
  issueOnly.addEventListener('change', applyFilters);
  checkAllBtn.addEventListener('click', () => setAllChecks(true));
  uncheckAllBtn.addEventListener('click', () => setAllChecks(false));
  exportBtn.addEventListener('click', downloadReviewStatus);
  saveConfigBtn.addEventListener('click', saveConfigJson);

  applyChecksToInputs();
  updateCounters();
  applyFilters();
  renderReviewPreview();
  renderConfigPreview();
  console.log('localStorage key:', storageKey);
}})();
</script>
</body>
</html>
"""


def run_preview(slug: str, project_root: Path) -> Dict[str, Any]:
    gacha = _load_gacha(slug, project_root)
    items_dir = project_root / "scripts" / "aimy-crop" / "output" / slug / "items"
    output_dir = project_root / "scripts" / "aimy-crop" / "output" / slug
    output_dir.mkdir(parents=True, exist_ok=True)

    payload = _build_items(slug, gacha, items_dir, project_root)
    html_text = _build_html(slug, gacha, payload)

    html_path = output_dir / "preview.html"
    html_path.write_text(html_text, encoding="utf-8")

    report = {
        "slug": slug,
        "title": gacha.get("title"),
        "previewPath": str(html_path),
        **payload["summary"],
        "localStorageKey": f"aimy-crop-preview:{slug}:checks:v1",
    }
    report_path = output_dir / "preview-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate preview.html for one slug")
    parser.add_argument("slug", help="gacha slug")
    parser.add_argument("--project-root", default=".", help="project root")
    args = parser.parse_args()

    report = run_preview(args.slug, Path(args.project_root).resolve())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
