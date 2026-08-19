import { mkdir, readFile, readdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const SITE_URL = 'https://aimycloset.jp'
const currentFilePath = fileURLToPath(import.meta.url)
const projectDirectory = path.resolve(path.dirname(currentFilePath), '..')
const distDirectory = path.join(projectDirectory, 'dist')
const templatePath = path.join(distDirectory, 'index.html')
const gachaDataDirectory = path.join(projectDirectory, 'src', 'data', 'gachas')
const historicalDataPath = path.join(projectDirectory, 'src', 'data', 'historicalItems.js')

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;')
}

function parseStartDate(value) {
  const match = String(value || '').match(
    /(\d{4})\/(\d{1,2})\/(\d{1,2})(?:\s+(\d{1,2}):(\d{1,2}))?/,
  )

  if (!match) {
    return Number.NEGATIVE_INFINITY
  }

  return Date.UTC(
    Number(match[1]),
    Number(match[2]) - 1,
    Number(match[3]),
    Number(match[4] || 0),
    Number(match[5] || 0),
  )
}

function mainCategory(category) {
  const value = String(category || '').trim()

  if (['服', '衣装'].includes(value)) return '服'
  if (['髪', '髪型'].includes(value)) return '髪型'
  if (['アクセサリー', 'アクセ', 'あたま', '髪飾り', 'めがね', 'メガネ', 'ピアス', '耳飾り', '耳'].includes(value)) return 'アクセサリー'
  if (['パーツ', 'メイク', '目', '口', '鼻', 'まゆげ', '眉毛'].includes(value)) return 'パーツ'
  if (value === '背景') return '背景'
  if (value === 'チェキフレーム') return 'チェキフレーム'
  return 'その他'
}

async function loadGachas() {
  const fileNames = (await readdir(gachaDataDirectory))
    .filter((fileName) => fileName.endsWith('.js'))
    .sort((left, right) => left.localeCompare(right, 'ja'))
  const gachas = []

  for (const fileName of fileNames) {
    const importedModule = await import(
      `${pathToFileURL(path.join(gachaDataDirectory, fileName)).href}?prerender=1`
    )
    const gacha = importedModule.default ?? importedModule.gacha

    if (gacha?.slug) {
      gachas.push(gacha)
    }
  }

  return gachas.sort(
    (left, right) => parseStartDate(right.startDate) - parseStartDate(left.startDate),
  )
}

async function loadHistoricalItems() {
  const importedModule = await import(
    `${pathToFileURL(historicalDataPath).href}?prerender=1`
  )
  const items = importedModule.default ?? importedModule.historicalItems ?? []
  return Array.isArray(items) ? items : []
}

function getUniqueItems(gachas, historicalItems) {
  const seen = new Set()
  const items = []

  const identityFor = (item) => {
    const name = String(item?.name || '')
      .normalize('NFKC')
      .toLocaleLowerCase('ja-JP')
      .replace(/[\s\u200b-\u200d\ufeff]+/g, '')
    const rarity = String(item?.rarity || '').trim().toUpperCase()
    const isUnconfirmed = /^(?:アイテム\d*|無題|名称?不明|未確認|名前を要確認)$/i.test(name)

    return !name || isUnconfirmed
      ? `id:${String(item?.id || '')}`
      : `item:${rarity}:${name}`
  }

  for (const gacha of gachas) {
    for (const item of gacha.items || []) {
      const identity = identityFor(item)
      if (!item?.id || seen.has(identity)) continue
      seen.add(identity)
      items.push(item)
    }
  }

  for (const item of historicalItems) {
    const identity = identityFor(item)
    if (!item?.id || item.matchedItemId || seen.has(identity)) continue
    seen.add(identity)
    items.push(item)
  }

  return items
}

function getUniqueItemRecords(gachas, historicalItems) {
  const seen = new Set()
  const records = []

  for (const gacha of gachas) {
    for (const item of gacha.items || []) {
      if (!item?.id || seen.has(item.id)) continue
      seen.add(item.id)
      records.push({ item, gacha })
    }
  }

  for (const item of historicalItems) {
    if (!item?.id || item.matchedItemId || seen.has(item.id)) continue
    seen.add(item.id)
    records.push({ item, gacha: null })
  }

  return records
}

function countBy(values, keyGetter) {
  return values.reduce((counts, value) => {
    const key = keyGetter(value)
    counts[key] = (counts[key] || 0) + 1
    return counts
  }, {})
}

function definitionList(entries) {
  return `<dl>${entries
    .map(
      ([term, description]) =>
        `<div><dt><strong>${escapeHtml(term)}</strong></dt><dd>${escapeHtml(description)}</dd></div>`,
    )
    .join('')}</dl>`
}

function siteHeader() {
  return `<header class="prerender-header">
    <a class="prerender-brand" href="/">Aimy Closet</a>
    <nav aria-label="主要メニュー">
      <a href="/item">アイテム図鑑</a>
      <a href="/gacha">ガチャ履歴</a>
      <a href="/image-search">画像検索</a>
      <a href="/guide">使い方</a>
      <a href="/about">サイトについて</a>
    </nav>
  </header>`
}

function shell(content) {
  return `<div class="prerender-shell">${siteHeader()}<main class="prerender-main">${content}</main></div>`
}

function updateMeta(html, { title, description, pagePath, robots = 'index,follow' }) {
  const canonical = `${SITE_URL}${pagePath === '/' ? '/' : pagePath}`
  let output = html
    .replace(/<title>[\s\S]*?<\/title>/i, `<title>${escapeHtml(title)}</title>`)
    .replace(
      /<meta\s+name=["']description["'][^>]*>/i,
      `<meta name="description" content="${escapeHtml(description)}" />`,
    )
    .replace(
      /<meta\s+name=["']robots["'][^>]*>/i,
      `<meta name="robots" content="${escapeHtml(robots)}" />`,
    )
    .replace(
      /<link\s+rel=["']canonical["'][^>]*>/i,
      `<link rel="canonical" href="${escapeHtml(canonical)}" />`,
    )
    .replace(
      /<meta\s+property=["']og:title["'][^>]*>/i,
      `<meta property="og:title" content="${escapeHtml(title)}" />`,
    )
    .replace(
      /<meta\s+property=["']og:description["'][^>]*>/i,
      `<meta property="og:description" content="${escapeHtml(description)}" />`,
    )
    .replace(
      /<meta\s+property=["']og:url["'][^>]*>/i,
      `<meta property="og:url" content="${escapeHtml(canonical)}" />`,
    )

  output = output.replace('<div id="root"></div>', `<div id="root">${shell('')}</div>`)
  return output
}

async function writePage(template, page) {
  const cleanPath = page.path.replace(/^\//, '')
  const outputDirectory = page.path === '/'
    ? distDirectory
    : path.join(distDirectory, cleanPath)
  const outputPaths = page.path === '/'
    ? [path.join(distDirectory, 'index.html')]
    : [
        path.join(distDirectory, `${cleanPath}.html`),
        path.join(outputDirectory, 'index.html'),
      ]
  let html = updateMeta(template, {
    title: page.title,
    description: page.description,
    pagePath: page.path,
    robots: page.robots,
  })

  html = html.replace(
    '<div id="root"><div class="prerender-shell">',
    `<div id="root"><div class="prerender-shell">`,
  )
  html = html.replace(
    '<main class="prerender-main"></main>',
    `<main class="prerender-main">${page.content}</main>`,
  )

  await mkdir(outputDirectory, { recursive: true })
  await Promise.all(outputPaths.map((outputPath) => writeFile(outputPath, html, 'utf8')))
}

function infoPage(title, lead, sections) {
  return `<article><h1>${escapeHtml(title)}</h1><p>${escapeHtml(lead)}</p></article>${sections
    .map(
      ({ title: sectionTitle, body }) =>
        `<section><h2>${escapeHtml(sectionTitle)}</h2>${body}</section>`,
    )
    .join('')}`
}

function createPages(gachas, historicalItems) {
  const items = getUniqueItems(gachas, historicalItems)
  const itemRecords = getUniqueItemRecords(gachas, historicalItems)
  const categoryCounts = countBy(items, (item) => mainCategory(item.category || item.mainCategory))
  const latest = gachas.slice(0, 3)

  const pages = [
    {
      path: '/',
      title: 'Aimy（アイミー）攻略・衣装・アイテム図鑑・ガチャ一覧｜Aimy Closet',
      description: `Aimyのアイテム${items.length}件とガチャ${gachas.length}件を掲載。衣装・髪型・目・背景などを名前・カテゴリ・画像から探せます。`,
      content: `<article><p>Aimy非公式ファンデータベース</p><h1>Aimyの衣装・アイテムとガチャ履歴を探す</h1><p>服・髪型・アクセサリー・パーツ・背景など${items.length}件と、登録済みガチャ${gachas.length}件を整理しています。名前が分からないアイテムは画像から検索できます。</p></article>
      <section><h2>最新ガチャ</h2><ul>${latest.map((gacha) => `<li><a href="/gacha/${escapeHtml(gacha.slug)}">${escapeHtml(gacha.title)}</a>：${escapeHtml(gacha.startDate)}開始・確認済み${gacha.items?.length || 0}件</li>`).join('')}</ul></section>
      <section><h2>カテゴリ別の登録数</h2>${definitionList(Object.entries(categoryCounts))}</section>
      <section><h2>掲載方針</h2><p>ゲーム内で確認できた内容を整理し、自動検出結果は人の目で確認します。不明な名称やガチャは推測で確定せず、未特定として掲載します。</p><p><a href="/data-policy">掲載データの確認・修正方針</a></p></section>`,
    },
    {
      path: '/item',
      title: 'アイテム図鑑｜Aimy Closet',
      description: `Aimyの確認済みアイテム${items.length}件を、名前・カテゴリ・レアリティ・ガチャから検索できます。`,
      content: `<article><h1>アイテム図鑑</h1><p>確認済みの${items.length}件を、名前・カテゴリ・レアリティ・収録ガチャから検索できます。復刻で同じIDのアイテムが再収録された場合、図鑑では一件にまとめます。</p></article><section><h2>カテゴリ別の登録数</h2>${definitionList(Object.entries(categoryCounts))}</section><section><h2>探し方</h2><p>名前が分かる場合はテキスト検索、分からない場合は<a href="/image-search">画像検索</a>を利用できます。ガチャ名が未特定の過去アイテムは<a href="/historical-items">実装時期別一覧</a>に掲載しています。</p></section>`,
    },
    {
      path: '/gacha',
      title: 'ガチャ履歴｜Aimy Closet',
      description: `Aimyの登録済みガチャ${gachas.length}件を開始日時が新しい順に掲載。開催期間と排出アイテムを確認できます。`,
      content: `<article><h1>ガチャ履歴</h1><p>登録済みの${gachas.length}件を開始日時が新しい順に掲載しています。各詳細ページで開催期間、確認済み件数、レアリティ・カテゴリ別の構成を確認できます。</p></article><section><h2>登録済みガチャ</h2><ol>${gachas.map((gacha) => `<li><a href="/gacha/${escapeHtml(gacha.slug)}">${escapeHtml(gacha.title)}</a>：${escapeHtml(gacha.startDate)} ～ ${escapeHtml(gacha.endDate)}（${gacha.items?.length || 0}件）</li>`).join('')}</ol></section>`,
    },
    {
      path: '/image-search',
      title: '画像からアイテム検索｜Aimy Closet',
      description: 'Aimyのスクリーンショットから、名前が分からない服・髪型・目・アクセサリーなどを検索できます。',
      content: infoPage('画像からアイテム検索', 'スクリーンショット内の探したい範囲とカテゴリを指定し、登録済み画像から近い候補を表示します。', [
        { title: '検索のコツ', body: '<ol><li>アイテム全体が写った画像を選ぶ</li><li>縦横比を変えずに探したい範囲を指定する</li><li>服・髪型・目など、先にカテゴリを選ぶ</li><li>候補が出なければ周囲を少し広めに選び直す</li></ol>' },
        { title: '候補が出ない場合', body: '<p>元画像が小さい、背景と同化している、未登録アイテムである場合は一致しないことがあります。画像検索結果は候補として確認し、名称や収録ガチャも併せて判断してください。</p>' },
      ]),
    },
    {
      path: '/historical-items',
      title: 'ガチャ未特定の過去アイテム｜Aimy Closet',
      description: `2.5周年交換所で確認できたガチャ名・名称未特定の過去SR・SSRアイテム${historicalItems.length}件を実装時期別に掲載しています。`,
      content: infoPage('ガチャ未特定の過去アイテム', `2.5周年交換所で存在を確認できた${historicalItems.length}件を、実装時期・レアリティ・カテゴリ別に掲載しています。`, [
        { title: '通常図鑑との分け方', body: '<p>画像、実装時期、レアリティ、カテゴリは確認できる一方、正式名称や配布ガチャが分からないものがあります。推測で名称を付けず、情報が判明するまでは未特定データとして扱います。</p>' },
        { title: '重複を防ぐ方法', body: '<p>登録済みアイテムと同一であることが確認できたものは、通常図鑑のデータへ統合し、未特定一覧から除外します。</p>' },
      ]),
    },
    {
      path: '/guide',
      title: 'Aimy Closetの使い方｜Aimy Closet',
      description: 'アイテム図鑑、ガチャ履歴、画像検索、お気に入りの使い方を案内します。',
      content: infoPage('Aimy Closetの使い方', '探したい情報が分かっている場合と、画像しか残っていない場合で使う機能を選べます。', [
        { title: '名前・カテゴリから探す', body: '<p><a href="/item">アイテム図鑑</a>では、名前の一部、レアリティ、ガチャ名で検索できます。服・髪型・アクセサリー・パーツ・背景・チェキフレームで絞り込めます。</p>' },
        { title: '画像から探す', body: '<p><a href="/image-search">画像検索</a>でスクリーンショットとカテゴリを指定すると、登録済み画像から近い候補を表示します。</p>' },
        { title: 'ガチャから探す', body: '<p><a href="/gacha">ガチャ履歴</a>は開始日時が新しい順です。詳細ページでは開催期間とアイテム構成を確認できます。</p>' },
      ]),
    },
    {
      path: '/about',
      title: 'Aimy Closetについて｜Aimy Closet',
      description: 'Aimy Closetの目的、掲載内容、運営方針について説明します。',
      content: infoPage('Aimy Closetについて', 'Aimyの衣装やガチャ情報をあとから探しやすくするために、個人が運営している非公式のファンデータベースです。', [
        { title: '作成した理由', body: '<p>短い間隔で追加されるガチャと過去アイテムを整理し、「このアイテムは何か」「どのガチャに入っていたか」を調べる時間を減らすことを目的にしています。</p>' },
        { title: '非公式サイトです', body: '<p>Aimyの公式運営、開発元、配信元とは関係ありません。ゲーム名・画像・キャラクター等の権利は各権利者に帰属します。</p>' },
        { title: '修正について', body: '<p>アイテム名、カテゴリ、開催期間、画像などの誤りは、確認でき次第修正します。</p>' },
      ]),
    },
    {
      path: '/data-policy',
      title: '掲載データの確認・修正方針｜Aimy Closet',
      description: 'ガチャとアイテム情報の登録、手動確認、重複防止、画像品質、修正方法を説明します。',
      content: infoPage('掲載データの確認・修正方針', 'ゲーム内のガチャ詳細・お知らせ・交換所で確認できた内容を整理し、不明な内容は推測で確定しません。', [
        { title: '登録の流れ', body: '<ol><li>ゲーム内画面を記録する</li><li>バナー、期間、画像、名前、レアリティ、カテゴリを読み取る</li><li>自動結果を人の目で確認して手動修正する</li><li>画像と名称の並び、件数、カテゴリを再確認して公開する</li></ol>' },
        { title: '復刻と重複', body: '<p>同じIDのアイテムが複数ガチャへ再収録された場合、ガチャのラインナップには掲載し、図鑑では一件にまとめます。</p>' },
        { title: '画像品質', body: '<p>低解像度画像を機械的に拡大せず、より鮮明な元画像を確認できた場合に差し替えます。手動画像も縦横比を変えません。</p>' },
      ]),
    },
    {
      path: '/contact',
      title: 'お問い合わせ｜Aimy Closet',
      description: '掲載ミス、権利関係、不具合、広告に関するお問い合わせ方法です。',
      content: infoPage('お問い合わせ', 'Aimy Closetを案内しているXの運営アカウントへ、DMまたは返信でご連絡ください。', [
        { title: '連絡時に必要な情報', body: '<ul><li>該当ページのURL</li><li>誤っている箇所または不具合の症状</li><li>正しい情報が確認できる画面</li><li>不具合の場合は端末とブラウザ</li></ul>' },
      ]),
    },
    {
      path: '/privacy',
      title: 'プライバシーポリシー｜Aimy Closet',
      description: 'Aimy Closetにおける利用者情報、Firebase、Google AdSense、Cookieの取扱いを説明します。',
      content: infoPage('プライバシーポリシー', '匿名のお気に入り機能、アクセス解析、広告配信で扱う情報について説明します。', [
        { title: '取得・保存する情報', body: '<p>匿名ユーザー識別子、お気に入りID、アクセスログ等を、機能提供・不正利用防止・品質改善のために扱う場合があります。氏名やメールアドレスの入力は求めません。</p>' },
        { title: '広告', body: '<p>Google AdSenseを利用する場合、Googleを含む第三者配信事業者が興味に応じた広告のためCookie等を使用することがあります。</p>' },
      ]),
    },
    {
      path: '/disclaimer',
      title: '免責事項｜Aimy Closet',
      description: 'Aimy Closetの非公式性、掲載情報、著作権、外部リンクに関する免責事項です。',
      content: infoPage('免責事項', 'Aimy Closetは個人が運営する非公式のファンデータベースです。', [
        { title: '掲載情報', body: '<p>正確性と最新性には注意しますが、完全性を保証するものではありません。ゲーム内の仕様・名称・期間は公式情報もご確認ください。</p>' },
        { title: '権利帰属', body: '<p>ゲーム名、画像、キャラクター、ロゴ等の権利は各権利者に帰属します。権利者からの修正・削除要請には内容を確認のうえ対応します。</p>' },
      ]),
    },
  ]

  for (const gacha of gachas) {
    const gachaItems = gacha.items || []
    const rarityCounts = countBy(gachaItems, (item) => item.rarity || '未確認')
    const gachaCategoryCounts = countBy(gachaItems, (item) => mainCategory(item.category))
    const raritySummary = Object.entries(rarityCounts).map(([key, value]) => `${key} ${value}件`).join('・')
    const categorySummary = Object.entries(gachaCategoryCounts).map(([key, value]) => `${key} ${value}件`).join('・')

    pages.push({
      path: `/gacha/${gacha.slug}`,
      title: `${gacha.title}｜排出アイテム・開催期間｜Aimy Closet`,
      description: `${gacha.title}は${gacha.startDate}から${gacha.endDate}まで開催。確認済み${gachaItems.length}件を掲載しています。`,
      content: `<article><p>ガチャ詳細</p><h1>${escapeHtml(gacha.title)}</h1><p>${escapeHtml(gacha.type)}</p>${gacha.banner ? `<img src="${escapeHtml(gacha.banner)}" alt="${escapeHtml(gacha.title)}" width="1128" height="202" style="width:100%;height:auto" />` : ''}<p>開催期間：${escapeHtml(gacha.startDate)} ～ ${escapeHtml(gacha.endDate)}</p><p>${escapeHtml(gacha.description)}</p></article>
      <section><h2>このガチャの登録内容</h2><p>確認済み${gachaItems.length}件。レアリティ別は${escapeHtml(raritySummary || '情報確認中')}、カテゴリ別は${escapeHtml(categorySummary || '情報確認中')}です。</p></section>
      <section><h2>確認済みアイテム</h2>${gachaItems.length ? `<ul>${gachaItems.map((item) => `<li>${escapeHtml(item.name)}：${escapeHtml(item.rarity)}・${escapeHtml(mainCategory(item.category))}</li>`).join('')}</ul>` : '<p>ラインナップは情報確認中です。</p>'}</section>
      <section><h2>掲載方法</h2><p>自動検出だけで確定せず、画像・名称・カテゴリを確認して登録しています。<a href="/data-policy">確認・修正方針を見る</a></p></section>`,
    })
  }

  for (const { item, gacha } of itemRecords) {
    const itemName = item.name || '名称未特定アイテム'
    const category = mainCategory(item.category || item.mainCategory)
    const sourceSummary = gacha
      ? `${gacha.title}（${gacha.startDate} ～ ${gacha.endDate}）`
      : `${item.implementationPeriod || '実装時期未確認'}・配布ガチャ未特定`

    pages.push({
      path: `/item/${encodeURIComponent(item.id)}`,
      title: `${itemName}｜アイテム情報｜Aimy Closet`,
      description: `${itemName}は${item.rarity || '未確認'}・${category}のアイテムです。入手元：${sourceSummary}。`,
      robots: 'noindex,follow',
      content: `<article><p>アイテム詳細</p><h1>${escapeHtml(itemName)}</h1>${item.image ? `<img src="${escapeHtml(item.image)}" alt="${escapeHtml(itemName)}" width="192" height="192" />` : ''}${definitionList([
        ['レアリティ', item.rarity || '未確認'],
        ['カテゴリ', category],
        ['入手元', sourceSummary],
      ])}</article><section><h2>掲載について</h2><p>この個別ページはサイト内検索とガチャ詳細からの確認用です。検索エンジンの審査用サイトマップには含めていません。</p><p><a href="${gacha ? `/gacha/${escapeHtml(gacha.slug)}` : '/historical-items'}">${gacha ? '収録ガチャを見る' : '同時期の過去アイテムを見る'}</a></p></section>`,
    })
  }

  return pages
}

async function prerender() {
  const [template, gachas, historicalItems] = await Promise.all([
    readFile(templatePath, 'utf8'),
    loadGachas(),
    loadHistoricalItems(),
  ])
  const pages = createPages(gachas, historicalItems)

  for (const page of pages) {
    await writePage(template, page)
  }

  console.log(`事前生成HTML: ${pages.length}ページ`)
  console.log(`ガチャ詳細: ${gachas.length}ページ`)
  console.log('個別アイテム詳細: noindexで事前生成・サイトマップ対象外')
}

await prerender()
