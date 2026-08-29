import { mkdir, readFile, readdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { getSiteInsights } from '../src/utils/siteInsights.js'
import { getMainCategory } from '../src/utils/itemCategory.js'

const SITE_URL = 'https://aimycloset.jp'
const project = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const dist = path.join(project, 'dist')
const dataDirectory = path.join(project, 'src', 'data', 'gachas')
const escapeHtml = (value) => String(value ?? '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#039;')

async function loadGachas() {
  const files = (await readdir(dataDirectory)).filter((file) => file.endsWith('.js')).sort((a, b) => a.localeCompare(b, 'ja'))
  const seen = new Set()
  const duplicates = []
  const gachas = []
  for (const file of files) {
    const module = await import(`${pathToFileURL(path.join(dataDirectory, file)).href}?prerender=3`)
    const gacha = module.default ?? module.gacha
    if (!gacha?.slug) continue
    if (seen.has(gacha.slug)) { duplicates.push(`${file} (${gacha.slug})`); continue }
    seen.add(gacha.slug)
    gachas.push(gacha)
  }
  return { gachas, duplicates }
}

const countBy = (values, getter) => values.reduce((result, value) => {
  const key = getter(value)
  result[key] = (result[key] || 0) + 1
  return result
}, {})
const definitionList = (entries) => `<dl>${entries.map(([term, value]) => `<div><dt><strong>${escapeHtml(term)}</strong></dt><dd>${escapeHtml(value)}</dd></div>`).join('')}</dl>`
const infoPage = (title, lead, sections) => `<article><h1>${escapeHtml(title)}</h1><p>${lead}</p></article>${sections.map(([heading, body]) => `<section><h2>${escapeHtml(heading)}</h2>${body}</section>`).join('')}`
const table = (headings, rows) => `<div class="insight-table-wrap"><table class="insight-table"><thead><tr>${headings.map((heading) => `<th>${escapeHtml(heading)}</th>`).join('')}</tr></thead><tbody>${rows.map((row) => `<tr>${row.map((cell) => `<td>${cell}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`

function header() {
  return '<header class="prerender-header"><a class="prerender-brand" href="/">Aimy Closet</a><nav aria-label="主要メニュー"><a href="/item">アイテム図鑑</a><a href="/gacha">ガチャ履歴</a><a href="/image-search">画像検索</a><a href="/insights">データ分析</a><a href="/guide">使い方</a><a href="/about">サイトについて</a></nav></header>'
}

function render(template, page) {
  const canonical = `${SITE_URL}${page.path}`
  return template
    .replace(/<title>[\s\S]*?<\/title>/i, `<title>${escapeHtml(page.title)}</title>`)
    .replace(/<meta\s+name=["']description["'][^>]*>/i, `<meta name="description" content="${escapeHtml(page.description)}" />`)
    .replace(/<meta\s+name=["']robots["'][^>]*>/i, '<meta name="robots" content="index,follow" />')
    .replace(/<link\s+rel=["']canonical["'][^>]*>/i, `<link rel="canonical" href="${canonical}" />`)
    .replace(/<meta\s+property=["']og:title["'][^>]*>/i, `<meta property="og:title" content="${escapeHtml(page.title)}" />`)
    .replace(/<meta\s+property=["']og:description["'][^>]*>/i, `<meta property="og:description" content="${escapeHtml(page.description)}" />`)
    .replace(/<meta\s+property=["']og:url["'][^>]*>/i, `<meta property="og:url" content="${canonical}" />`)
    .replace('<div id="root"></div>', `<div id="root"><div class="prerender-shell">${header()}<main class="prerender-main">${page.content}</main></div></div>`)
}

async function writePage(template, page) {
  const clean = page.path.replace(/^\//, '')
  const output = page.path === '/' ? path.join(dist, 'index.html') : path.join(dist, `${clean}.html`)
  await mkdir(path.dirname(output), { recursive: true })
  await writeFile(output, render(template, page), 'utf8')
}

function createPages(gachas) {
  const analysis = getSiteInsights(gachas)
  const newest = [...analysis.datedGachas].reverse().slice(0, 10)
  const reprints = analysis.datedGachas.filter((gacha) => gacha.returningItems > 0 || gacha.title.includes('復刻')).reverse().slice(0, 12)
  const cycleTable = table(['ガチャ', '開始', '前回から', '開催日数', '登録数'], newest.map((gacha) => [
    `<a href="/gacha/${escapeHtml(gacha.slug)}">${escapeHtml(gacha.title)}</a>`, escapeHtml(gacha.startDate), gacha.intervalFromPrevious ? `${gacha.intervalFromPrevious}日` : '—', gacha.durationDays ? `${gacha.durationDays}日` : '—', `${gacha.itemCount}件`,
  ]))
  const reprintTable = table(['ガチャ', '全登録', '過去収録と一致', '初登場候補'], reprints.map((gacha) => [
    `<a href="/gacha/${escapeHtml(gacha.slug)}">${escapeHtml(gacha.title)}</a>`, `${gacha.itemCount}件`, `${gacha.returningItems}件`, `${gacha.firstSeenItems}件`,
  ]))
  const pages = [
    { path: '/', title: 'Aimy（アイミー）攻略・衣装・アイテム図鑑・ガチャ一覧｜Aimy Closet', description: `Aimyの固有アイテム${analysis.uniqueItemCount}件とガチャ${analysis.gachas.length}件を整理した非公式データベースです。`, content: infoPage('Aimyの衣装・アイテムとガチャ履歴を探す', `服・髪型・アクセサリー・パーツ・背景など固有${analysis.uniqueItemCount}件と、登録済みガチャ${analysis.gachas.length}件を整理しています。`, [['独自集計', `<p>開催日を確認できた${analysis.datedGachas.length}件では、追加間隔の中央値は${analysis.medianIntervalDays}日です。<a href="/insights">数え方と結果を見る</a></p>`], ['カテゴリ別の収録数', definitionList(Object.entries(analysis.categoryCounts))], ['確認方針', '<p>ゲーム内画面を記録し、自動検出結果は人の目で確認します。不明な名称は推測で確定しません。</p>']]) },
    { path: '/item', title: 'アイテム図鑑｜Aimy Closet', description: `Aimyの固有アイテム${analysis.uniqueItemCount}件を検索できます。`, content: infoPage('アイテム図鑑', `正式名とレアリティが一致する復刻候補をまとめた固有${analysis.uniqueItemCount}件を検索できます。`, [['復刻の扱い', '<p>図鑑は初回候補へまとめ、各ガチャ詳細には収録事実を残します。名称未確認は誤統合を避けて別IDのまま扱います。</p>'], ['詳しい数え方', '<p><a href="/guides/reprints">復刻アイテムの確認結果</a>で判定条件と実測値を公開しています。</p>']]) },
    { path: '/gacha', title: 'ガチャ履歴｜Aimy Closet', description: `Aimyの登録済みガチャ${analysis.gachas.length}件を開始日時順に掲載。`, content: infoPage('ガチャ履歴', `同じslugの重複を除いた${analysis.gachas.length}件を開始日時が新しい順に掲載します。`, [['登録済みガチャ', `<ol>${analysis.gachas.map((gacha) => `<li><a href="/gacha/${escapeHtml(gacha.slug)}">${escapeHtml(gacha.title)}</a>：${escapeHtml(gacha.startDate)} ～ ${escapeHtml(gacha.endDate)}（${gacha.items?.length || 0}件）</li>`).join('')}</ol>`], ['時系列分析', '<p><a href="/guides/gacha-cycle">追加ペースと開催期間の実測一覧</a>も確認できます。</p>']]) },
    { path: '/insights', title: 'Aimyデータ分析｜Aimy Closet', description: 'ガチャ追加間隔、開催期間、復刻収録を登録データから集計した独自分析です。', content: infoPage('Aimyデータ分析', 'サイト内の開始日時と収録アイテムを同じ基準で集計し、更新時に数値を再計算します。', [['主な結果', definitionList([['開催日確認済み', `${analysis.datedGachas.length}件`], ['固有アイテム', `${analysis.uniqueItemCount}件`], ['追加間隔の中央値', `${analysis.medianIntervalDays}日`], ['追加間隔の平均', `${analysis.averageIntervalDays}日`], ['最短／最長', `${analysis.shortestIntervalDays}日／${analysis.longestIntervalDays}日`]])], ['分析メニュー', '<ul><li><a href="/guides/gacha-cycle">ガチャ追加ペースと開催期間</a></li><li><a href="/guides/reprints">復刻アイテムの確認結果</a></li><li><a href="/guides/image-search">画像検索の判定方法</a></li></ul>'], ['前提', '<p>同じslugは1ガチャ、正式名とレアリティが一致するものは同一候補です。名称未確認はID単位、常設は間隔計算から除外します。</p>']]) },
    { path: '/guides/gacha-cycle', title: 'ガチャ追加ペースと開催期間｜Aimy Closet', description: '登録済みガチャの開始日時から追加間隔と開催日数を実測した結果です。', content: infoPage('ガチャ追加ペースと開催期間', `追加間隔の中央値は${analysis.medianIntervalDays}日、平均は${analysis.averageIntervalDays}日、最短${analysis.shortestIntervalDays}日、最長${analysis.longestIntervalDays}日でした。`, [['直近10件', cycleTable], ['数値の範囲', '<p>将来日程の予言ではなく過去データの参考値です。記事公開日時ではなく、ゲーム内の開催期間欄だけを採用します。</p>']]) },
    { path: '/guides/reprints', title: '復刻アイテムの確認結果｜Aimy Closet', description: '初回収録と復刻収録を重複させずに数える方法と確認結果です。', content: infoPage('復刻アイテムの確認結果', 'ガチャ詳細には全収録を残し、図鑑では正式名とレアリティが一致する初回候補へまとめます。', [['確認結果', reprintTable], ['判定できないケース', '<p>表記揺れ、名称未確認、レアリティ変更は別候補として残し、ゲーム内で同一と確認できた時点で統合します。</p>']]) },
    { path: '/guides/image-search', title: '画像検索の判定方法｜Aimy Closet', description: '画像検索の比較方法と精度を上げる切り抜き手順です。', content: infoPage('画像検索の判定方法', 'OCRで名称を読むのではなく、選択範囲と登録画像の見た目をカテゴリ内で比較する候補検索です。', [['精度を上げる4手順', '<ol><li>元スクリーンショットを縮小せず使う</li><li>アイテム全体を含め余白を少なく切る</li><li>カテゴリを先に選ぶ</li><li>弱い時は範囲を広げた画像と狭めた画像を試す</li></ol>'], ['一致しにくい条件', '<p>小さい元画像、半透明、向き違い、未登録アイテムは順位が下がります。結果は候補としてガチャ名・カテゴリ・レアリティも照合します。</p>'], ['登録画像', '<p>縦横比は変えず、公開表示は192×192へ高品質変換します。大きい同一画像があれば高解像度側へ差し替えます。</p>']]) },
    { path: '/image-search', title: '画像からアイテム検索｜Aimy Closet', description: 'スクリーンショットから名前が分からないAimyアイテム候補を検索できます。', content: infoPage('画像からアイテム検索', '探したい範囲とカテゴリを指定し、登録済み画像から近い候補を表示します。', [['検索前に', '<p><a href="/guides/image-search">判定方法と切り抜きのコツ</a>を確認してください。</p>']]) },
    { path: '/historical-items', title: 'ガチャ未特定の過去アイテム｜Aimy Closet', description: '正式名・ガチャ未特定の過去アイテムを実装時期別に掲載。', content: infoPage('ガチャ未特定の過去アイテム', '交換所で存在を確認できても正式名や配布ガチャが分からないものを通常図鑑と分けて整理します。', [['推測しない方針', '<p>画像・時期・レアリティ・カテゴリだけが確認できる場合は未特定として残します。</p>']]) },
    { path: '/guide', title: 'Aimy Closetの使い方｜Aimy Closet', description: '図鑑、ガチャ履歴、画像検索、独自分析の使い方です。', content: infoPage('Aimy Closetの使い方', '名前、画像、ガチャ、実装時期のどれが分かるかで機能を選べます。', [['名前から', '<p><a href="/item">図鑑</a>で名前・カテゴリ・レアリティ・ガチャ名から検索します。</p>'], ['画像から', '<p><a href="/image-search">画像検索</a>で範囲とカテゴリを指定します。</p>'], ['傾向から', '<p><a href="/insights">データ分析</a>で追加間隔、開催日数、復刻を確認します。</p>']]) },
    { path: '/about', title: 'Aimy Closetについて｜Aimy Closet', description: '個人運営の非公式ファンデータベースを作った理由と運営方針です。', content: infoPage('Aimy Closetについて', 'Aimyを継続して遊び、衣装とガチャを記録している個人運営者が作った非公式ファンデータベースです。', [['作成した理由', '<p>「この衣装はどのガチャか」「復刻で図鑑が重複していないか」を調べ直せるよう、スクリーンショットと開催日時を一つずつ整理しています。</p>'], ['誰が・どう作るか', '<p>Aimy Closet運営者（個人）が、ゲーム内画面の記録、自動切り抜き、公開前の目視確認、誤りの修正を行います。公式とは関係ありません。</p>'], ['独自性', '<p>開始順、カテゴリ、初回／再収録、追加間隔を同じ基準で集計し、判定方法も公開します。</p>']]) },
    { path: '/data-policy', title: '掲載データの確認・修正方針｜Aimy Closet', description: '登録元、目視確認、重複防止、画像品質、修正方法を説明します。', content: infoPage('掲載データの確認・修正方針', 'ゲーム内のガチャ詳細・お知らせ・交換所を確認先とし、不明な内容は推測で確定しません。', [['登録の流れ', '<ol><li>ゲーム内画面を記録</li><li>開催期間とカードを検出</li><li>画像・名前・レアリティ・カテゴリを目視確認</li><li>件数と並びを再確認して公開</li></ol>'], ['日時', '<p>記事公開日やスクリーンショット時刻ではなく、開催期間見出し直下の開始・終了だけを保存します。</p>'], ['復刻', '<p>正式名とレアリティが一致する候補は初回へ統合し、名称未確認は自動統合しません。</p>']]) },
    { path: '/contact', title: 'お問い合わせ｜Aimy Closet', description: '掲載ミス、不具合、権利関係のお問い合わせ方法です。', content: infoPage('お問い合わせ', 'Aimy Closetを案内しているX運営アカウントへDMまたは返信でご連絡ください。', [['必要な情報', '<ul><li>該当URL</li><li>誤りまたは症状</li><li>正しい情報を確認できる画面</li><li>不具合時の端末とブラウザ</li></ul>']]) },
    { path: '/privacy', title: 'プライバシーポリシー｜Aimy Closet', description: '利用者情報、Cookie、Google AdSenseの取扱いです。', content: infoPage('プライバシーポリシー', '匿名のお気に入り、アクセス解析、広告配信で扱う情報を説明します。', [['取扱い', '<p>匿名識別子、お気に入りID、アクセスログ等を機能提供・不正防止・品質改善に利用する場合があります。</p>']]) },
    { path: '/disclaimer', title: '免責事項｜Aimy Closet', description: '非公式性、掲載情報、著作権、外部リンクの免責事項です。', content: infoPage('免責事項', 'Aimy Closetは個人運営の非公式ファンデータベースです。', [['掲載情報', '<p>正確性に注意しますが完全性は保証しません。期間・仕様は公式情報もご確認ください。</p>'], ['権利', '<p>ゲーム名・画像・キャラクター等の権利は各権利者に帰属します。</p>']]) },
  ]

  for (const gacha of analysis.gachas) {
    const row = analysis.datedGachas.find((entry) => entry.slug === gacha.slug)
    const items = gacha.items || []
    const rarity = countBy(items, (item) => item.rarity || '未確認')
    const categories = countBy(items, (item) => getMainCategory(item.category))
    pages.push({ path: `/gacha/${gacha.slug}`, title: `${gacha.title}｜排出アイテム・開催期間｜Aimy Closet`, description: `${gacha.title}の開催期間、${items.length}件の構成、初回・再収録候補を掲載。`, content: infoPage(gacha.title, `${escapeHtml(gacha.startDate)}から${escapeHtml(gacha.endDate)}まで。確認済み${items.length}件です。`, [['このガチャの実測データ', definitionList([['開催日数', row?.durationDays ? `${row.durationDays}日` : '常設・未確認'], ['前回の開始から', row?.intervalFromPrevious ? `${row.intervalFromPrevious}日` : '比較対象なし'], ['レアリティ構成', Object.entries(rarity).map(([key, value]) => `${key} ${value}件`).join('・') || '確認中'], ['カテゴリ構成', Object.entries(categories).map(([key, value]) => `${key} ${value}件`).join('・') || '確認中'], ['過去収録と一致', `${row?.returningItems || 0}件`], ['初登場候補', `${row?.firstSeenItems ?? items.length}件`]])], ['判定方法', '<p>正式名とレアリティを開始日時の古い順で照合します。名称未確認はID単位です。<a href="/guides/reprints">復刻の数え方</a></p>'], ['確認済みラインナップ', `<ul>${items.map((item) => `<li>${escapeHtml(item.name || '名称未確認')}（${escapeHtml(item.rarity || '未確認')}・${escapeHtml(getMainCategory(item.category))}）</li>`).join('')}</ul>`]]) })
  }
  return pages
}

const template = await readFile(path.join(dist, 'index.html'), 'utf8')
const { gachas, duplicates } = await loadGachas()
const pages = createPages(gachas)
for (const page of pages) await writePage(template, page)
console.log(`事前生成HTML: ${pages.length}ページ（主要ページと固有ガチャ詳細のみ）`)
console.log(`ガチャ詳細: ${gachas.length}ページ`)
console.log('個別アイテム詳細: React内では利用可・薄い静的HTMLは生成しない')
if (duplicates.length) console.log(`重複slugを除外: ${duplicates.join(', ')}`)
