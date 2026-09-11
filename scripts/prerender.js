import { mkdir, readFile, readdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import {
  getItemIdentity,
  getSiteInsights,
} from '../src/utils/siteInsights.js'
import { getMainCategory } from '../src/utils/itemCategory.js'

const SITE_URL = 'https://aimycloset.jp'
const REVIEWED_DATE = '2026-09-11'
const project = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const dist = path.join(project, 'dist')
const dataDirectory = path.join(project, 'src', 'data', 'gachas')

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;')
}

async function loadGachas() {
  const files = (await readdir(dataDirectory))
    .filter((file) => file.endsWith('.js'))
    .sort((left, right) => left.localeCompare(right, 'ja'))
  const seen = new Set()
  const duplicates = []
  const gachas = []

  for (const file of files) {
    const module = await import(
      `${pathToFileURL(path.join(dataDirectory, file)).href}?prerender=4`
    )
    const gacha = module.default ?? module.gacha

    if (!gacha?.slug) {
      continue
    }

    if (seen.has(gacha.slug)) {
      duplicates.push(`${file} (${gacha.slug})`)
      continue
    }

    seen.add(gacha.slug)
    gachas.push(gacha)
  }

  return { gachas, duplicates }
}

function countBy(values, getter) {
  return values.reduce((result, value) => {
    const key = getter(value)
    result[key] = (result[key] || 0) + 1
    return result
  }, {})
}

function table(headings, rows) {
  return `<div class="insight-table-wrap"><table class="insight-table"><thead><tr>${headings
    .map((heading) => `<th>${escapeHtml(heading)}</th>`)
    .join('')}</tr></thead><tbody>${rows
    .map((row) => `<tr>${row.map((cell) => `<td>${cell}</td>`).join('')}</tr>`)
    .join('')}</tbody></table></div>`
}

function definitionList(entries) {
  return `<dl>${entries
    .map(
      ([term, value]) =>
        `<div><dt><strong>${escapeHtml(term)}</strong></dt><dd>${escapeHtml(value)}</dd></div>`,
    )
    .join('')}</dl>`
}

function articleStamp(method) {
  return `<div class="article-stamp"><p><strong>執筆・検証:</strong> Aimy Closet運営者</p><p><strong>最終内容確認:</strong> 2026年9月11日</p>${
    method ? `<p><strong>確認方法:</strong> ${escapeHtml(method)}</p>` : ''
  }</div>`
}

function notice(body) {
  return `<aside class="editorial-notice">${body}</aside>`
}

function infoPage(title, lead, sections, method = '') {
  return `<article><h1>${escapeHtml(title)}</h1><p class="article-lead">${lead}</p>${articleStamp(method)}${sections
    .map(([heading, body]) => `<section><h2>${escapeHtml(heading)}</h2>${body}</section>`)
    .join('')}</article>`
}

function header() {
  return `<header class="prerender-header">
    <a class="prerender-brand" href="/">Aimy Closet</a>
    <nav aria-label="主要メニュー">
      <a href="/item">アイテム図鑑</a>
      <a href="/gacha">ガチャ履歴</a>
      <a href="/image-search">画像検索</a>
      <a href="/insights">データ分析</a>
      <a href="/guide">使い方</a>
      <a href="/about">サイトについて</a>
    </nav>
  </header>`
}

function jsonLdFor(page, canonical) {
  const base = {
    '@context': 'https://schema.org',
    '@type': page.kind === 'article' ? 'Article' : 'WebPage',
    headline: page.title,
    description: page.description,
    url: canonical,
    inLanguage: 'ja',
    isPartOf: {
      '@type': 'WebSite',
      name: 'Aimy Closet',
      url: SITE_URL,
    },
  }

  if (page.kind === 'article') {
    base.author = { '@type': 'Person', name: 'Aimy Closet運営者' }
    base.datePublished = page.datePublished || REVIEWED_DATE
    base.dateModified = page.dateModified || REVIEWED_DATE
  }

  return JSON.stringify(base).replaceAll('<', '\\u003c')
}

function render(template, page) {
  const canonical = `${SITE_URL}${page.path === '/' ? '/' : page.path}`
  const ogImage = page.ogImage
    ? `${SITE_URL}${page.ogImage}`
    : `${SITE_URL}/AimyCloset_OGP.png`
  const structuredData = `<script type="application/ld+json">${jsonLdFor(page, canonical)}</script>`

  return template
    .replace(/<title>[\s\S]*?<\/title>/i, `<title>${escapeHtml(page.title)}</title>`)
    .replace(
      /<meta\s+name=["']description["'][^>]*>/i,
      `<meta name="description" content="${escapeHtml(page.description)}" />`,
    )
    .replace(
      /<meta\s+name=["']robots["'][^>]*>/i,
      `<meta name="robots" content="${escapeHtml(page.robots || 'index,follow')}" />`,
    )
    .replace(
      /<link\s+rel=["']canonical["'][^>]*>/i,
      `<link rel="canonical" href="${canonical}" />`,
    )
    .replace(
      /<meta\s+property=["']og:title["'][^>]*>/i,
      `<meta property="og:title" content="${escapeHtml(page.title)}" />`,
    )
    .replace(
      /<meta\s+property=["']og:description["'][^>]*>/i,
      `<meta property="og:description" content="${escapeHtml(page.description)}" />`,
    )
    .replace(
      /<meta\s+property=["']og:url["'][^>]*>/i,
      `<meta property="og:url" content="${canonical}" />`,
    )
    .replace(
      /<meta\s+property=["']og:image["'][^>]*>/i,
      `<meta property="og:image" content="${escapeHtml(ogImage)}" />`,
    )
    .replace('</head>', `${structuredData}\n  </head>`)
    .replace(
      '<div id="root"></div>',
      `<div id="root"><div class="prerender-shell">${header()}<main class="prerender-main">${page.content}</main></div></div>`,
    )
}

async function writePage(template, page) {
  const clean = page.path.replace(/^\//, '')
  const output = page.path === '/'
    ? path.join(dist, 'index.html')
    : path.join(dist, `${clean}.html`)

  await mkdir(path.dirname(output), { recursive: true })
  await writeFile(output, render(template, page), 'utf8')
}

function createPages(gachas) {
  const analysis = getSiteInsights(gachas)
  const newest = [...analysis.datedGachas].reverse().slice(0, 12)
  const reprints = analysis.datedGachas
    .filter((gacha) => gacha.title.includes('復刻'))
    .reverse()
  const reprintExactMatches = reprints.flatMap((gacha) =>
    gacha.matchingPriorItems.map((item) => ({
      ...item,
      currentGachaTitle: gacha.title,
      currentGachaSlug: gacha.slug,
    })),
  )
  const latestThree = [...analysis.datedGachas].reverse().slice(0, 3)
  const datedSlugs = new Set(analysis.datedGachas.map((gacha) => gacha.slug))
  const itemSourceGachas = [
    ...[...analysis.datedGachas].reverse(),
    ...analysis.gachas.filter((gacha) => !datedSlugs.has(gacha.slug)),
  ]
  const seenItems = new Set()
  const uniqueItemRows = []

  for (const gacha of itemSourceGachas) {
    for (const item of gacha.items || []) {
      const identity = getItemIdentity(item)

      if (seenItems.has(identity)) {
        continue
      }

      seenItems.add(identity)
      uniqueItemRows.push({
        ...item,
        gachaTitle: gacha.title,
      })
    }
  }

  const latestItemList = `<ul>${uniqueItemRows
    .slice(0, 48)
    .map(
      (item) =>
        `<li>${escapeHtml(item.name || '名称未確認')}（${escapeHtml(
          item.rarity || '未確認',
        )}・${escapeHtml(getMainCategory(item.category))}）— ${escapeHtml(
          item.gachaTitle,
        )}</li>`,
    )
    .join('')}</ul>`
  const intervalTable = table(
    ['前回から', '確認回数', '読み方'],
    analysis.intervalDistribution.map((row) => [
      `${row.value}日`,
      `${row.count}回`,
      row.value <= 2 ? '短い間隔' : row.value <= 4 ? '中心的な間隔' : '長めの間隔',
    ]),
  )
  const cycleTable = table(
    ['ガチャ', '開始', '前回から', '開催日数', '登録数'],
    newest.map((gacha) => [
      `<a href="/gacha/${escapeHtml(gacha.slug)}">${escapeHtml(gacha.title)}</a>`,
      escapeHtml(gacha.startDate),
      gacha.intervalFromPrevious ? `${gacha.intervalFromPrevious}日` : '—',
      gacha.durationDays ? `${gacha.durationDays}日` : '—',
      `${gacha.itemCount}件`,
    ]),
  )
  const reprintTable = table(
    ['ガチャ', '全登録', '既存履歴と完全一致', '履歴内では未判定'],
    reprints.map((gacha) => [
      `<a href="/gacha/${escapeHtml(gacha.slug)}">${escapeHtml(gacha.title)}</a>`,
      `${gacha.itemCount}件`,
      `${gacha.returningItems}件`,
      `${gacha.unmatchedToRegisteredHistory}件`,
    ]),
  )
  const matchTable = reprintExactMatches.length
    ? table(
        ['アイテム', 'レアリティ', '先に確認したガチャ', '再収録先'],
        reprintExactMatches.map((item) => [
          escapeHtml(item.name),
          escapeHtml(item.rarity || '未確認'),
          `<a href="/gacha/${escapeHtml(item.firstGachaSlug)}">${escapeHtml(item.firstGachaTitle)}</a>`,
          `<a href="/gacha/${escapeHtml(item.currentGachaSlug)}">${escapeHtml(item.currentGachaTitle)}</a>`,
        ]),
      )
    : '<p>現在の登録範囲では完全一致した再収録を確認できていません。</p>'
  const categoryTable = table(
    ['カテゴリ', '主な対象', '迷いやすい境界'],
    [
      ['服', '衣装・コーデ・ワンピース', '帽子や耳だけならアクセサリー'],
      ['髪型', '前髪・後ろ髪を含むヘア全体', '髪飾りだけならアクセサリー'],
      ['アクセサリー', 'あたま・めがね・ピアス', '目やメイクはパーツ'],
      ['パーツ', '目・メイク・口・鼻・まゆげ', '顔の前に付ける物はアクセサリー'],
      ['背景', '部屋・屋外・会場', '前面の枠はチェキフレーム'],
      ['チェキフレーム', '画面端の装飾・文字枠', '場所や景色は背景'],
    ],
  )
  const pages = [
    {
      path: '/',
      title: 'Aimy（アイミー）衣装・アイテム図鑑・ガチャ履歴｜Aimy Closet',
      description: `Aimyの固有アイテム${analysis.uniqueItemCount}件とガチャ${analysis.gachas.length}件を、画像・カテゴリ・開催時期から探せる非公式データベースです。`,
      content: infoPage(
        'Aimyの衣装・アイテムとガチャ履歴を探す',
        `服・髪型・アクセサリー・パーツ・背景など固有${analysis.uniqueItemCount}件と、登録済みガチャ${analysis.gachas.length}件を整理しています。画像しかない場合、見た時期だけ分かる場合にも、確認方法を選べます。`,
        [
          ['目的から探す', '<ul><li><a href="/guides/item-finder">名前が分からない衣装の探し方</a></li><li><a href="/guides/gacha-cycle">追加間隔と開催日数の実測</a></li><li><a href="/guides/reprints">復刻アイテムの照合結果</a></li></ul>'],
          ['最新ガチャ', `<ul>${latestThree.map((gacha) => `<li><a href="/gacha/${escapeHtml(gacha.slug)}">${escapeHtml(gacha.title)}</a>：${escapeHtml(gacha.startDate)}開始・確認済み${gacha.itemCount}件</li>`).join('')}</ul>`],
          ['このサイトの確認方法', '<p>ゲーム内のガチャ詳細・お知らせ・交換所を記録し、自動検出後に画像・名前・カテゴリ・開催期間を目視確認します。不明な内容は推測で確定しません。</p>'],
        ],
        'ゲーム内画面を記録し、自動検出後に目視確認',
      ),
    },
    {
      path: '/item',
      title: 'アイテム図鑑｜Aimy Closet',
      description: `Aimyの固有アイテム${analysis.uniqueItemCount}件を、名前・カテゴリ・レアリティ・ガチャから検索できます。`,
      content: infoPage(
        'アイテム図鑑',
        `確認済みの固有アイテム${analysis.uniqueItemCount}件を検索できます。初期表示は48件ずつとし、名前・カテゴリ・レアリティ・収録ガチャから絞り込みます。`,
        [
          ['探し方に迷ったら', '<ul><li><a href="/guides/item-finder">手掛かり別の探し方</a></li><li><a href="/guides/categories">カテゴリの分類ルール</a></li><li><a href="/guides/image-search">画像検索の切り抜き方</a></li></ul>'],
          ['復刻の扱い', '<p>ガチャ詳細には収録事実を残し、図鑑では正式名とレアリティが一致する初回候補へまとめます。名称未確認は誤統合を避けて別IDのまま扱います。</p>'],
          ['直近に登録したアイテム', `${latestItemList}<p>画面上では48件ずつ表示し、検索条件を変えると対象だけに絞れます。</p>`],
        ],
        '登録画像・正式名・レアリティ・カテゴリを目視確認',
      ),
    },
    {
      path: '/gacha',
      title: 'ガチャ履歴｜Aimy Closet',
      description: `Aimyの登録済みガチャ${analysis.gachas.length}件を開始日時順に掲載し、開催期間と確認済みラインナップを確認できます。`,
      content: infoPage(
        'ガチャ履歴',
        `登録順ではなく、ゲーム内で確認した開始日時の新しい順に${analysis.gachas.length}件を掲載しています。`,
        [
          ['登録済みガチャ', `<ol>${[...analysis.gachas].sort((left, right) => String(right.startDate).localeCompare(String(left.startDate))).map((gacha) => `<li><a href="/gacha/${escapeHtml(gacha.slug)}">${escapeHtml(gacha.title)}</a>：${escapeHtml(gacha.startDate)} ～ ${escapeHtml(gacha.endDate)}（${gacha.items?.length || 0}件）</li>`).join('')}</ol>`],
          ['履歴の使い方', '<p>スクリーンショットを撮った時期の前後を開き、画像・カテゴリ・レアリティを照合します。追加間隔は固定ではないため、開始日だけで収録先を断定しません。</p>'],
        ],
        '記事公開日ではなく、ゲーム内「開催期間」欄の日時を採用',
      ),
    },
    {
      path: '/insights',
      title: 'Aimyデータ分析｜Aimy Closet',
      description: 'ガチャ追加間隔、開催期間、復刻照合の結果と判断できない範囲を、登録データから公開しています。',
      kind: 'article',
      content: infoPage(
        'Aimyデータ分析',
        'ガチャ名や画像の一覧だけでは分からない追加ペース、開催期間の偏り、復刻をどこまで確認できたかを同じ条件で集計します。',
        [
          ['今回の主な結果', definitionList([['開催日確認済み', `${analysis.datedGachas.length}件`], ['固有アイテム', `${analysis.uniqueItemCount}件`], ['追加間隔の中央値', `${analysis.medianIntervalDays}日`], ['追加間隔の平均', `${analysis.averageIntervalDays}日`], ['最も多い開催日数', `${analysis.commonDuration?.value ?? '—'}日`]])],
          ['結果の読み方', `<p>追加間隔は最短${analysis.shortestIntervalDays}日・最長${analysis.longestIntervalDays}日で、固定周期ではありません。「既存履歴と一致なし」は新規を意味せず、登録開始前の復刻元は照合できません。</p>`],
          ['目的別ガイド', '<ul><li><a href="/guides/item-finder">名前が分からない衣装を探す</a></li><li><a href="/guides/gacha-cycle">ガチャ追加ペースと開催期間</a></li><li><a href="/guides/reprints">復刻アイテムの照合結果</a></li><li><a href="/guides/image-search">画像検索の使い方と限界</a></li><li><a href="/guides/categories">カテゴリの分類ルール</a></li></ul>'],
          ['対象と限界', `<p>同じslugは1件、常設は追加間隔から除外します。対象期間は${escapeHtml(analysis.earliestRegisteredGacha?.title)}（${escapeHtml(analysis.earliestRegisteredGacha?.startDate)}）以降です。それ以前の初回登場や表記揺れは自動照合できません。</p>`],
        ],
        '開催期間とラインナップを目視確認し、開始日時順に集計',
      ),
    },
    {
      path: '/guides/gacha-cycle',
      title: 'ガチャ追加ペースと開催期間｜Aimy Closet',
      description: 'Aimyの登録済みガチャについて、追加間隔と開催日数の分布、直近12件の実測値、数値の読み方を掲載します。',
      kind: 'article',
      content: infoPage(
        'ガチャ追加ペースと開催期間',
        `開始日時を古い順に比べると、追加間隔の中央値は${analysis.medianIntervalDays}日、平均は${analysis.averageIntervalDays}日でした。次回予測ではなく、過去ガチャを探す目安として使います。`,
        [
          ['先に結論', notice(`<strong>3〜4日間隔が中心ですが固定周期ではありません。</strong> 最短${analysis.shortestIntervalDays}日・最長${analysis.longestIntervalDays}日で、周年復刻のような短期開催は通常ガチャと分けて確認します。`)],
          ['追加間隔の分布', `<p>ひとつ前に始まったガチャから何日後に次が始まったかを数えています。</p>${intervalTable}`],
          ['開催日数の分布', `<p>${analysis.durationDistribution.map((row) => `${row.value}日が${row.count}件`).join('、')}です。終了時刻が14:59や23:59の場合があるため、日付だけの感覚と1日程度ずれる場合があります。</p>`],
          ['直近12件の実測値', cycleTable],
          ['役立つ場面と限界', '<p>撮影日付から候補ガチャを絞る、同時開催を比べる、短期復刻の見落としを防ぐ用途に使えます。将来日程や内容を予言する数値ではありません。</p>'],
        ],
        '常設を除き、ゲーム内「開催期間」欄の開始・終了日時を比較',
      ),
    },
    {
      path: '/guides/reprints',
      title: '復刻アイテムの照合結果｜Aimy Closet',
      description: 'Aimyの復刻ガチャを登録済み履歴と照合し、完全一致、未判定、図鑑で重複させない基準を説明します。',
      kind: 'article',
      content: infoPage(
        '復刻アイテムの照合結果',
        '復刻ガチャの全収録は詳細へ残し、図鑑では同一アイテムを重複させない方針です。復刻元が登録開始前なら自動では特定できません。',
        [
          ['表示の訂正', notice('<strong>「既存履歴と一致しない件数」を「初登場候補」とする表示を撤回しました。</strong> 復刻元が未登録のケースを新規扱いする表現だったため、現在は「完全一致」と「履歴内では未判定」に分けています。')],
          ['周年復刻ガチャの照合状況', `${reprintTable}<p>未判定には登録開始前の初登場、表記変更、読み取り誤差が含まれます。新規数ではありません。</p>`],
          ['完全一致を確認できたアイテム', matchTable],
          ['図鑑で統合する条件', '<ol><li>正式名が確認済み</li><li>文字幅と空白をそろえた名前が一致</li><li>レアリティも一致</li><li>仮名ではない</li></ol><p>画像が似ているだけでは統合せず、色違いや目・髪色の違いを残します。</p>'],
          ['自分で確認する手順', '<ol><li>復刻ガチャで名前とレアリティを確認</li><li>図鑑で特徴的な名前を検索</li><li>候補の収録ガチャを開き画像・色・カテゴリを比較</li><li>表記が違う場合は断定しない</li></ol>'],
        ],
        '正式名を正規化し、レアリティも一致した場合だけ照合',
      ),
    },
    {
      path: '/guides/image-search',
      title: '画像検索の使い方と限界｜Aimy Closet',
      description: 'Aimy Closetの画像検索について、切り抜き、カテゴリ選択、候補が弱い場合の直し方、画像の取扱いを説明します。',
      kind: 'article',
      content: infoPage(
        '画像検索の使い方と限界',
        '画像検索はOCRではなく、選択範囲の色・輪郭・見た目を登録画像と比べる候補検索です。上位1件を正解と決める機能ではありません。',
        [
          ['失敗しにくい5手順', '<ol><li>写真アプリの元スクリーンショットを選ぶ</li><li>カテゴリを先に選ぶ</li><li>対象全体を含め、隣のカードや文字を入れすぎず囲む</li><li>画像だけでなくガチャ名・レアリティ・色も照合する</li><li>弱い場合は広い範囲と狭い範囲の両方を試す</li></ol>'],
          ['カテゴリの選び方', categoryTable],
          ['候補が弱くなる条件', '<dl><div><dt><strong>小さい・ぼやけた画像</strong></dt><dd>端末の原本へ戻す</dd></div><div><dt><strong>半透明</strong></dt><dd>輪郭が分かる範囲を少し広げる</dd></div><div><dt><strong>文字や隣のカードが入る</strong></dt><dd>対象の端を切らない範囲で狭める</dd></div><div><dt><strong>全く違う候補</strong></dt><dd>カテゴリを見直し、未登録の可能性も残す</dd></div></dl>'],
          ['画像の取扱い', '<p>画像と比較処理はブラウザ内で扱い、検索のためにサーバーへアップロードしません。192×192への変換は表示サイズをそろえるもので、元画像以上の細部は復元しません。</p>'],
        ],
        '端末内で選択画像を整え、選択カテゴリ内の登録画像と比較',
      ),
    },
    {
      path: '/guides/item-finder',
      title: '名前が分からないAimy衣装の探し方｜Aimy Closet',
      description: '名前、画像、実装時期、ガチャの雰囲気など、手元にある情報別にAimyアイテムを探す手順です。',
      kind: 'article',
      content: infoPage(
        '名前が分からないAimy衣装の探し方',
        `名前を覚えていなくても、画像・カテゴリ・見かけた時期・ガチャのテーマのいずれかが分かれば、全${analysis.uniqueItemCount}件から候補を減らせます。`,
        [
          ['手掛かり別の入口', '<ul><li>名前の一部：<a href="/item">図鑑で特徴語を検索</a></li><li>画像だけ：<a href="/image-search">カテゴリを選んで画像検索</a></li><li>時期：<a href="/gacha">開始順のガチャ履歴</a></li><li>かなり古い：<a href="/historical-items">ガチャ未特定の過去アイテム</a></li></ul>'],
          ['名前の一部から探す', '<ol><li>リボン・猫目・紫陽花など特徴を1語にする</li><li>カテゴリで絞る</li><li>括弧内の色と画像を比べる</li><li>収録ガチャの開催時期も確認する</li></ol><p>「白」だけより、形を表す語を組み合わせると候補を減らせます。</p>'],
          ['画像と時期を組み合わせる', '<p>画像検索の上位候補が似ている場合は、撮影日の前後に開催中だったガチャを開き、候補名がラインナップにあるか確認します。撮影日は初登場日とは限らないため、日付だけで断定しません。</p>'],
          ['見つからないとき', '<ol><li>隣接カテゴリへ変える</li><li>名前を短くする</li><li>切り抜き範囲を変える</li><li>未特定一覧を確認する</li><li>未登録として情報提供する</li></ol>'],
        ],
        '図鑑・画像検索・ガチャ履歴を情報量別に比較',
      ),
    },
    {
      path: '/guides/categories',
      title: 'アイテムカテゴリの分類ルール｜Aimy Closet',
      description: 'Aimy Closetで服・髪型・アクセサリー・パーツ・背景・チェキフレームを分類する基準を説明します。',
      kind: 'article',
      content: infoPage(
        'アイテムカテゴリの分類ルール',
        'ゲーム内の表記を保存しながら、検索時に同種がまとまるよう6つの主カテゴリへ正規化します。「あたま」「目」などは種類として残します。',
        [
          ['6つの主カテゴリ', categoryTable],
          ['正規化する理由', '<p>「衣装」と「服」、「髪」と「髪型」のような表記差で検索結果が分かれないようにするためです。元の種類を消さないので、アクセサリー内のめがね、パーツ内の目などへさらに絞れます。</p>'],
          ['誤分類がある場合', '<p>自動読取りの結果を目視確認しますが、誤りを見つけた場合は該当URL、現在の分類、ゲーム内で確認できる表記をお問い合わせください。</p>'],
        ],
        'ゲーム内カテゴリを保存し、検索用の主カテゴリだけ共通化',
      ),
    },
    {
      path: '/image-search',
      title: '画像からアイテム検索｜Aimy Closet',
      description: 'スクリーンショットからAimyの服・髪型・アクセサリーなど、似ている登録アイテム候補を端末内で検索できます。',
      content: infoPage(
        '画像からアイテムを探す',
        'カテゴリとスクリーンショット内の範囲を選び、登録済み画像から近い候補を表示します。画像は検索のためにサーバーへ送りません。',
        [['検索前の確認', '<p><a href="/guides/image-search">切り抜き方、カテゴリの選び方、候補が弱い場合の直し方</a>を先に確認できます。検索結果は確率ではなく候補順位です。</p>']],
      ),
    },
    {
      path: '/historical-items',
      title: 'ガチャ未特定の過去アイテム｜Aimy Closet',
      description: '正式名・ガチャ未特定の過去アイテムを実装時期、レアリティ、カテゴリ別に掲載します。',
      content: infoPage(
        'ガチャ未特定の過去アイテム',
        '交換所で存在を確認できても、正式名や配布ガチャを確認できないものを通常図鑑と分けて整理します。',
        [['推測しない方針', '<p>画像・時期・レアリティ・カテゴリだけが確認できる場合は未特定として残し、ゲーム内で同一と確認できた時点で通常図鑑へ統合します。</p>']],
        '2.5周年交換所と登録済み図鑑を照合',
      ),
    },
    {
      path: '/guide',
      title: 'Aimy Closetの使い方｜Aimy Closet',
      description: '名前、画像、時期、ガチャ名など、分かっている手掛かり別にAimyの衣装とアイテムを探す方法を案内します。',
      content: infoPage(
        'Aimy Closetの使い方',
        '名前・画像・時期・ガチャのうち、分かっている手掛かりに合う入口から探します。画像だけで決めず、カテゴリ・レアリティ・開催時期も照合します。',
        [
          ['手掛かり別の入口', '<ul><li><a href="/item">名前・特徴から図鑑検索</a></li><li><a href="/image-search">スクリーンショットから画像検索</a></li><li><a href="/gacha">見た時期からガチャ履歴</a></li><li><a href="/historical-items">古い未特定アイテム</a></li></ul>'],
          ['図鑑の読み方', '<p>各カードには名前、カテゴリ、種類、収録ガチャを表示します。同名でも色やレアリティが違う場合は別候補です。</p>'],
          ['復刻を確認する', '<p>当サイトの登録開始前の復刻元は照合できません。「一致なし＝新規」とは判断せず、<a href="/guides/reprints">確認済みと未判定を分けます。</a></p>'],
          ['見つからない場合', '<p>カテゴリ変更、短い名前、切り抜き直し、未特定一覧の順で確認します。誤りは確認できる画面とURLを添えてお問い合わせください。</p>'],
        ],
      ),
    },
    {
      path: '/about',
      title: 'Aimy Closetについて｜Aimy Closet',
      description: '個人運営のAimy非公式ファンデータベースを作った理由、確認方法、運営方針を説明します。',
      content: infoPage(
        'Aimy Closetについて',
        'Aimyを継続して遊び、衣装とガチャを記録している個人が運営する非公式ファンデータベースです。',
        [
          ['作成した理由', '<p>「この衣装はどのガチャか」「見逃した期間はいつか」「復刻で図鑑が重複していないか」を後から調べ直せるよう、スクリーンショットと開催日時を整理しています。</p>'],
          ['誰が・どう作るか', '<p>Aimy Closet運営者がゲーム内画面の記録、自動切り抜き、公開前の目視確認、誤りの修正を行います。開始順、カテゴリ、再収録、追加間隔を同じ基準で扱い、判断できない範囲も公開します。</p>'],
          ['非公式サイト', '<p>Aimy公式、開発元、配信元とは関係ありません。ゲーム名・画像・キャラクター等の権利は各権利者に帰属します。</p>'],
        ],
        '運営者本人がゲーム内画面と公開データを確認',
      ),
    },
    {
      path: '/data-policy',
      title: '掲載データの確認・修正方針｜Aimy Closet',
      description: 'Aimy Closetの登録元、目視確認、日時、復刻重複、画像品質、修正方法を説明します。',
      content: infoPage(
        '掲載データの確認・修正方針',
        'ゲーム内のガチャ詳細・お知らせ・交換所で確認できた内容を登録し、不明な内容は推測で確定しません。',
        [
          ['登録の流れ', '<ol><li>ゲーム内画面を記録</li><li>バナー、期間、カード、名前、レアリティ、カテゴリを検出</li><li>人の目で修正</li><li>件数と並びを再確認して公開</li></ol>'],
          ['開催日時', '<p>記事公開日や撮影時刻ではなく、「開催期間」見出し直下の開始・終了だけを保存します。読めない場合は空欄のまま確認します。</p>'],
          ['復刻と重複', '<p>正式名とレアリティが一致した場合だけ図鑑の初回候補へ統合します。一致しないものを新規とは断定しません。</p>'],
          ['画像品質', '<p>公開表示を192×192へそろえても元画像以上の細部は戻りません。より鮮明な同一画像があれば高解像度側へ差し替えます。</p>'],
        ],
      ),
    },
    {
      path: '/contact',
      title: 'お問い合わせ｜Aimy Closet',
      description: '掲載ミス、不具合、権利関係について、確認に必要な情報と連絡方法を案内します。',
      content: infoPage('お問い合わせ', 'Aimy Closetを案内している運営アカウントへご連絡ください。', [['連絡時に必要な情報', '<ul><li>該当ページのURL</li><li>誤りまたは症状</li><li>正しい情報を確認できる画面</li><li>不具合時の端末・OS・ブラウザ</li></ul>']]),
    },
    {
      path: '/privacy',
      title: 'プライバシーポリシー｜Aimy Closet',
      description: 'Aimy Closetの利用者情報、Cookie、アクセス解析、Google AdSenseの取扱いを説明します。',
      content: infoPage('プライバシーポリシー', '匿名のお気に入り、アクセス解析、広告配信で扱う情報を説明します。', [['取扱い', '<p>匿名識別子、お気に入りID、アクセスログ等を機能提供・不正防止・品質改善に利用する場合があります。画像検索に選んだ画像は検索のためにサーバーへ送りません。</p>']]),
    },
    {
      path: '/disclaimer',
      title: '免責事項｜Aimy Closet',
      description: 'Aimy Closetの非公式性、掲載情報、著作権、外部リンクに関する免責事項です。',
      content: infoPage('免責事項', 'Aimy Closetは個人運営の非公式ファンデータベースです。', [['掲載情報', '<p>正確性に注意しますが完全性は保証しません。期間・仕様はゲーム内または公式情報も確認してください。</p>'], ['権利', '<p>ゲーム名・画像・キャラクター等の権利は各権利者に帰属します。</p>']]),
    },
    {
      path: '/favorites',
      title: 'お気に入り｜Aimy Closet',
      description: 'このブラウザでお気に入りにしたAimyアイテムを確認できます。',
      robots: 'noindex,follow',
      content: infoPage('お気に入り', 'このブラウザでハートを押したアイテムを見返す個人用ページです。氏名・メールアドレスの入力は不要です。', [['表示されない場合', '<p>端末やブラウザが変わった場合、同じお気に入り一覧にならないことがあります。</p>']]),
    },
  ]

  for (const gacha of analysis.gachas) {
    const row = analysis.datedGachas.find((entry) => entry.slug === gacha.slug)
    const items = gacha.items || []
    const rarity = countBy(items, (item) => item.rarity || '未確認')
    const categories = countBy(items, (item) => getMainCategory(item.category))
    const matches = row?.matchingPriorItems || []
    const matchDetails = matches.length
      ? `<ul>${matches.map((item) => `<li>${escapeHtml(item.name)}（${escapeHtml(item.rarity || '未確認')}）— <a href="/gacha/${escapeHtml(item.firstGachaSlug)}">${escapeHtml(item.firstGachaTitle)}</a>で先に確認</li>`).join('')}</ul>`
      : '<p>登録済みの過去履歴と、正式名・レアリティが完全一致した項目はありません。</p>'

    pages.push({
      path: `/gacha/${gacha.slug}`,
      title: `${gacha.title}｜排出アイテム・開催期間｜Aimy Closet`,
      description: `${gacha.title}の開催期間、確認済み${items.length}件のカテゴリ・レアリティ構成、登録済み履歴との照合結果を掲載。`,
      ogImage: gacha.banner,
      content: infoPage(
        gacha.title,
        `${escapeHtml(gacha.startDate)}から${escapeHtml(gacha.endDate)}まで。ゲーム内画面で確認できた${items.length}件を掲載しています。`,
        [
          ['このガチャの確認結果', definitionList([['開催日数', row?.durationDays ? `${row.durationDays}日` : '常設・未確認'], ['前回の開始から', row?.intervalFromPrevious ? `${row.intervalFromPrevious}日` : '比較対象なし'], ['レアリティ構成', Object.entries(rarity).map(([key, value]) => `${key} ${value}件`).join('・') || '確認中'], ['カテゴリ構成', Object.entries(categories).map(([key, value]) => `${key} ${value}件`).join('・') || '確認中'], ['登録済み履歴と一致', `${row?.returningItems || 0}件`], ['履歴内では未判定', `${row?.unmatchedToRegisteredHistory ?? items.length}件`]])],
          ['復刻照合の読み方', `<p>未判定は新規の意味ではありません。当サイトの登録開始前の復刻元や表記差は照合できません。</p>${matchDetails}<p><a href="/guides/reprints">照合条件と限界を見る</a></p>`],
          ['確認済みラインナップ', `<ul>${items.map((item) => `<li>${escapeHtml(item.name || '名称未確認')}（${escapeHtml(item.rarity || '未確認')}・${escapeHtml(getMainCategory(item.category))}）</li>`).join('')}</ul>`],
        ],
        'ゲーム内の開催期間・画像・名前・レアリティ・カテゴリを目視確認',
      ),
    })
  }

  return pages
}

const template = await readFile(path.join(dist, 'index.html'), 'utf8')
const { gachas, duplicates } = await loadGachas()
const pages = createPages(gachas)

for (const page of pages) {
  await writePage(template, page)
}

console.log(`事前生成HTML: ${pages.length}ページ（主要ページ・実用ガイド・固有ガチャ詳細）`)
console.log(`ガチャ詳細: ${gachas.length}ページ`)
console.log('個別アイテム詳細: 図鑑の絞り込みURLへ統合・旧URLはVercelでリダイレクト')

if (duplicates.length) {
  console.log(`重複slugを除外: ${duplicates.join(', ')}`)
}
