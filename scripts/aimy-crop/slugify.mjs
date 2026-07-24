import KuroshiroModule from 'kuroshiro'
import KuromojiAnalyzerModule from 'kuroshiro-analyzer-kuromoji'

const Kuroshiro = KuroshiroModule.default || KuroshiroModule
const KuromojiAnalyzer =
  KuromojiAnalyzerModule.default || KuromojiAnalyzerModule

function normalizeSlug(value) {
  return value
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .replace(/-+/g, '-')
}

const title = process.argv.slice(2).join(' ').trim()
if (!title) {
  process.stdout.write('')
  process.exit(0)
}

const kuroshiro = new Kuroshiro()
await kuroshiro.init(new KuromojiAnalyzer())
const romaji = await kuroshiro.convert(title, {
  to: 'romaji',
  mode: 'spaced',
  romajiSystem: 'hepburn',
})

process.stdout.write(normalizeSlug(romaji))
