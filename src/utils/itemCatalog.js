import { getGachaDateTimestamp } from './gachaOrder'

const UNCONFIRMED_NAME_PATTERN =
  /^(?:アイテム\d*|無題|名称?不明|未確認|名前を要確認)$/i

function normalizeItemName(value) {
  return String(value || '')
    .normalize('NFKC')
    .toLocaleLowerCase('ja-JP')
    .replace(/[\s\u200b-\u200d\ufeff]+/g, '')
}

function getItemIdentity(item) {
  const name = normalizeItemName(item?.name)
  const rarity = String(item?.rarity || '').trim().toUpperCase()

  if (!name || UNCONFIRMED_NAME_PATTERN.test(name)) {
    return `id:${String(item?.id || '')}`
  }

  return `item:${rarity}:${name}`
}

function canonicalRank(item, rawIndex) {
  const sourceRank = item.sourceType === 'gacha' ? 0 : 1
  const timestamp = getGachaDateTimestamp(item.gachaStartDate)
  const dateRank = timestamp === null ? Number.POSITIVE_INFINITY : timestamp
  return [sourceRank, dateRank, rawIndex]
}

function isEarlierRank(left, right) {
  for (let index = 0; index < left.length; index += 1) {
    if (left[index] !== right[index]) {
      return left[index] < right[index]
    }
  }

  return false
}

function makeAppearance(item) {
  return {
    slug: String(item.gachaSlug || ''),
    title: String(item.gachaTitle || ''),
    startDate: String(item.gachaStartDate || ''),
  }
}

export function buildItemCatalog(rawItems) {
  const groups = new Map()

  rawItems.forEach((item, rawIndex) => {
    if (!item?.id) {
      return
    }

    const identity = getItemIdentity(item)
    const group = groups.get(identity) || []
    group.push({ item, rawIndex })
    groups.set(identity, group)
  })

  const canonicalEntries = []
  const idToCanonicalId = new Map()

  groups.forEach((entries) => {
    let canonicalEntry = entries[0]
    let bestRank = canonicalRank(canonicalEntry.item, canonicalEntry.rawIndex)

    entries.slice(1).forEach((entry) => {
      const rank = canonicalRank(entry.item, entry.rawIndex)

      if (isEarlierRank(rank, bestRank)) {
        canonicalEntry = entry
        bestRank = rank
      }
    })

    const appearances = []
    const seenAppearances = new Set()

    entries.forEach(({ item }) => {
      idToCanonicalId.set(String(item.id), String(canonicalEntry.item.id))

      if (item.sourceType !== 'gacha') {
        return
      }

      const appearance = makeAppearance(item)
      const key = `${appearance.slug}\u0000${appearance.startDate}`

      if (!seenAppearances.has(key)) {
        appearances.push(appearance)
        seenAppearances.add(key)
      }
    })

    canonicalEntries.push({
      item: {
        ...canonicalEntry.item,
        gachaAppearances: appearances,
      },
      rawIndex: canonicalEntry.rawIndex,
    })
  })

  canonicalEntries.sort((left, right) => left.rawIndex - right.rawIndex)

  const items = canonicalEntries.map((entry) => entry.item)
  const byId = new Map(items.map((item) => [String(item.id), item]))

  return { items, byId, idToCanonicalId }
}
