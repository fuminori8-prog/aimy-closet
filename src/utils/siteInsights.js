import { getMainCategory } from './itemCategory.js'
import { getGachaDateTimestamp } from './gachaOrder.js'

const DAY_MS = 24 * 60 * 60 * 1000
const UNCONFIRMED_NAME = /^(?:アイテム\d*|無題|名称?不明|未確認|名前を要確認)$/i

export function dedupeGachasBySlug(values) {
  const seen = new Set()
  return values.filter((gacha) => {
    const slug = String(gacha?.slug || '').trim()
    if (!slug || seen.has(slug)) return false
    seen.add(slug)
    return true
  })
}

export function getItemIdentity(item) {
  const name = String(item?.name || '')
    .normalize('NFKC')
    .toLocaleLowerCase('ja-JP')
    .replace(/[\s\u200b-\u200d\ufeff]+/g, '')
  const rarity = String(item?.rarity || '').trim().toUpperCase()

  if (!name || UNCONFIRMED_NAME.test(name)) {
    return `id:${String(item?.id || '')}`
  }

  return `item:${rarity}:${name}`
}

function roundDays(milliseconds) {
  return Math.max(1, Math.round(milliseconds / DAY_MS))
}

function median(values) {
  if (!values.length) return null
  const sorted = [...values].sort((a, b) => a - b)
  const middle = Math.floor(sorted.length / 2)
  return sorted.length % 2
    ? sorted[middle]
    : Math.round((sorted[middle - 1] + sorted[middle]) / 2)
}

export function getSiteInsights(inputGachas) {
  const gachas = dedupeGachasBySlug(inputGachas)
  const dated = gachas
    .map((gacha) => ({ gacha, timestamp: getGachaDateTimestamp(gacha.startDate) }))
    .filter((entry) => entry.timestamp !== null)
    .sort((left, right) => left.timestamp - right.timestamp)
  const intervals = dated.slice(1).map((entry, index) =>
    roundDays(entry.timestamp - dated[index].timestamp),
  )
  const categoryCounts = {}
  const rarityCounts = {}
  const uniqueItems = new Set()

  for (const gacha of gachas) {
    for (const item of gacha.items || []) {
      uniqueItems.add(getItemIdentity(item))
      const category = getMainCategory(item.category)
      const rarity = String(item.rarity || '未確認')
      categoryCounts[category] = (categoryCounts[category] || 0) + 1
      rarityCounts[rarity] = (rarityCounts[rarity] || 0) + 1
    }
  }

  const seenItems = new Set()
  const gachaRows = dated.map(({ gacha, timestamp }, index) => {
    const items = gacha.items || []
    let returningItems = 0
    for (const item of items) {
      const identity = getItemIdentity(item)
      if (seenItems.has(identity)) returningItems += 1
    }
    for (const item of items) seenItems.add(getItemIdentity(item))

    const endTimestamp = getGachaDateTimestamp(gacha.endDate)
    return {
      ...gacha,
      timestamp,
      itemCount: items.length,
      returningItems,
      firstSeenItems: Math.max(0, items.length - returningItems),
      durationDays: endTimestamp === null ? null : roundDays(endTimestamp - timestamp),
      intervalFromPrevious: index === 0
        ? null
        : roundDays(timestamp - dated[index - 1].timestamp),
    }
  })

  return {
    gachas,
    datedGachas: gachaRows,
    uniqueItemCount: uniqueItems.size,
    categoryCounts,
    rarityCounts,
    medianIntervalDays: median(intervals),
    averageIntervalDays: intervals.length
      ? Math.round(intervals.reduce((sum, value) => sum + value, 0) / intervals.length * 10) / 10
      : null,
    shortestIntervalDays: intervals.length ? Math.min(...intervals) : null,
    longestIntervalDays: intervals.length ? Math.max(...intervals) : null,
  }
}

export function getGachaInsight(inputGachas, slug) {
  const insights = getSiteInsights(inputGachas)
  const chronologicalIndex = insights.datedGachas.findIndex((gacha) => gacha.slug === slug)
  const row = insights.datedGachas[chronologicalIndex]
  if (!row) return null

  const previous = chronologicalIndex > 0
    ? insights.datedGachas[chronologicalIndex - 1]
    : null
  const next = chronologicalIndex < insights.datedGachas.length - 1
    ? insights.datedGachas[chronologicalIndex + 1]
    : null

  return { ...row, previous, next }
}
