import { readdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const SITE_URL = 'https://aimycloset.jp'
const CONTENT_REVIEW_DATE = '2026-09-11'
const project = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const dataDirectory = path.join(project, 'src', 'data', 'gachas')
const outputPath = path.join(project, 'public', 'sitemap.xml')

const staticPaths = [
  '/',
  '/item',
  '/gacha',
  '/image-search',
  '/historical-items',
  '/guide',
  '/about',
  '/data-policy',
  '/contact',
  '/disclaimer',
  '/privacy',
  '/insights',
  '/guides/gacha-cycle',
  '/guides/reprints',
  '/guides/image-search',
  '/guides/item-finder',
  '/guides/categories',
]

function escapeXml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&apos;')
}

function toIsoDate(value) {
  const match = String(value || '').match(/^(\d{4})\/(\d{1,2})\/(\d{1,2})/)

  if (!match) {
    return null
  }

  const year = match[1]
  const month = match[2].padStart(2, '0')
  const day = match[3].padStart(2, '0')
  return `${year}-${month}-${day}`
}

async function loadGachas() {
  const files = (await readdir(dataDirectory))
    .filter((file) => file.endsWith('.js'))
    .sort((left, right) => left.localeCompare(right, 'ja'))
  const seen = new Set()
  const gachas = []

  for (const file of files) {
    const module = await import(
      `${pathToFileURL(path.join(dataDirectory, file)).href}?sitemap=4`
    )
    const gacha = module.default ?? module.gacha
    const slug = String(gacha?.slug || '').trim()

    if (!slug || seen.has(slug)) {
      continue
    }

    seen.add(slug)
    gachas.push(gacha)
  }

  return gachas
}

function createSitemap(entries) {
  const urls = entries
    .map(({ pagePath, lastModified }) => `  <url>
    <loc>${escapeXml(`${SITE_URL}${pagePath}`)}</loc>
    <lastmod>${escapeXml(lastModified)}</lastmod>
  </url>`)
    .join('\n')

  return `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls}
</urlset>
`
}

const gachas = await loadGachas()
const latestGachaDate = gachas
  .map((gacha) => toIsoDate(gacha.startDate))
  .filter(Boolean)
  .sort()
  .at(-1) || CONTENT_REVIEW_DATE
const siteUpdatedDate = [latestGachaDate, CONTENT_REVIEW_DATE].sort().at(-1)
const entries = staticPaths.map((pagePath) => ({
  pagePath,
  lastModified: ['/', '/item', '/gacha', '/insights', '/guides/gacha-cycle', '/guides/reprints'].includes(pagePath)
    ? siteUpdatedDate
    : CONTENT_REVIEW_DATE,
}))

for (const gacha of gachas) {
  entries.push({
    pagePath: `/gacha/${encodeURIComponent(gacha.slug)}`,
    lastModified: toIsoDate(gacha.startDate) || CONTENT_REVIEW_DATE,
  })
}

await writeFile(outputPath, createSitemap(entries), 'utf8')

console.log(`サイトマップ: ${entries.length}URL（固有ガチャ${gachas.length}件・実用ガイド5件）`)
console.log('個別アイテムURL: 内部リンクを図鑑検索へ統合・サイトマップ対象外')
console.log(`サイト更新日: ${siteUpdatedDate}`)
