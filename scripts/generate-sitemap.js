import { readdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const SITE_URL = 'https://aimycloset.jp'
const project = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const dataDirectory = path.join(project, 'src', 'data', 'gachas')
const fixedPaths = ['/', '/item', '/gacha', '/image-search', '/historical-items', '/guide', '/about', '/data-policy', '/contact', '/disclaimer', '/privacy', '/insights', '/guides/gacha-cycle', '/guides/reprints', '/guides/image-search']
const escapeXml = (value) => String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&apos;')

const files = (await readdir(dataDirectory)).filter((file) => file.endsWith('.js')).sort((a, b) => a.localeCompare(b, 'ja'))
const seen = new Set()
const duplicates = []
const slugs = []
for (const file of files) {
  const module = await import(`${pathToFileURL(path.join(dataDirectory, file)).href}?sitemap=3`)
  const gacha = module.default ?? module.gacha
  if (!gacha?.slug) continue
  if (seen.has(gacha.slug)) { duplicates.push(`${file} (${gacha.slug})`); continue }
  seen.add(gacha.slug)
  slugs.push(gacha.slug)
}

const paths = [...fixedPaths, ...slugs.map((slug) => `/gacha/${encodeURIComponent(slug)}`)]
const xml = `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${paths.map((pagePath) => `  <url><loc>${escapeXml(`${SITE_URL}${pagePath}`)}</loc></url>`).join('\n')}\n</urlset>\n`
await writeFile(path.join(project, 'public', 'sitemap.xml'), xml, 'utf8')
console.log(`サイトマップ: ${paths.length}URL（固有ガチャ${slugs.length}件・分析記事4件）`)
console.log('個別アイテムURL: サイト内では利用可・サイトマップ対象外')
if (duplicates.length) console.log(`重複slugを除外: ${duplicates.join(', ')}`)
