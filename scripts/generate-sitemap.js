import { readdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const SITE_URL = 'https://aimycloset.jp'

const currentFilePath = fileURLToPath(import.meta.url)
const scriptsDirectory = path.dirname(currentFilePath)
const projectDirectory = path.resolve(scriptsDirectory, '..')

const gachaDataDirectory = path.join(
  projectDirectory,
  'src',
  'data',
  'gachas',
)

const outputFilePath = path.join(
  projectDirectory,
  'public',
  'sitemap.xml',
)

function escapeXml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&apos;')
}

function normalizePath(value) {
  const pathValue = String(value || '').trim()

  if (!pathValue) {
    return null
  }

  return pathValue.startsWith('/')
    ? pathValue
    : `/${pathValue}`
}

async function loadGachas() {
  const fileNames = await readdir(gachaDataDirectory)

  const dataFileNames = fileNames
    .filter((fileName) => fileName.endsWith('.js'))
    .sort((a, b) => a.localeCompare(b, 'ja'))

  const gachas = []

  for (const fileName of dataFileNames) {
    const filePath = path.join(gachaDataDirectory, fileName)
    const moduleUrl = pathToFileURL(filePath).href
    const importedModule = await import(moduleUrl)

    const gacha =
      importedModule.default ??
      importedModule.gacha ??
      Object.values(importedModule).find(
        (value) =>
          value &&
          typeof value === 'object' &&
          !Array.isArray(value) &&
          value.slug,
      )

    if (!gacha?.slug) {
      console.warn(
        `サイトマップ対象外: ${fileName} にslug付きガチャデータがありません`,
      )
      continue
    }

    gachas.push(gacha)
  }

  return gachas
}

function createUrlSet(gachas) {
  const paths = new Set([
    '/',
    '/item',
    '/gacha',
    '/contact',
    '/disclaimer',
    '/privacy',
  ])

  for (const gacha of gachas) {
    const gachaSlug = String(gacha.slug || '').trim()

    if (gachaSlug) {
      paths.add(`/gacha/${encodeURIComponent(gachaSlug)}`)
    }

    for (const item of gacha.items || []) {
      const itemId = String(item.id || '').trim()

      if (itemId) {
        paths.add(`/item/${encodeURIComponent(itemId)}`)
      }
    }
  }

  return [...paths]
    .map(normalizePath)
    .filter(Boolean)
    .sort((a, b) => {
      if (a === '/') return -1
      if (b === '/') return 1
      return a.localeCompare(b, 'ja')
    })
}

function createSitemapXml(paths) {
  const urlEntries = paths
    .map((pagePath) => {
      const fullUrl = `${SITE_URL}${pagePath}`

      return `  <url>
    <loc>${escapeXml(fullUrl)}</loc>
  </url>`
    })
    .join('\n\n')

  return `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">

${urlEntries}

</urlset>
`
}

async function generateSitemap() {
  try {
    const gachas = await loadGachas()
    const paths = createUrlSet(gachas)
    const sitemapXml = createSitemapXml(paths)

    await writeFile(outputFilePath, sitemapXml, 'utf8')

    const itemCount = new Set(
      gachas.flatMap((gacha) =>
        (gacha.items || [])
          .map((item) => item.id)
          .filter(Boolean),
      ),
    ).size

    console.log('サイトマップを生成しました')
    console.log(`ガチャ数: ${gachas.length}`)
    console.log(`アイテム数: ${itemCount}`)
    console.log(`URL数: ${paths.length}`)
    console.log(`出力先: ${outputFilePath}`)
  } catch (error) {
    console.error('サイトマップの生成に失敗しました')
    console.error(error)
    process.exitCode = 1
  }
}

await generateSitemap()