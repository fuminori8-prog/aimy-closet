import { gachas } from '../data/gachas'
import { historicalItems } from '../data/historicalItems'
import { getMainCategory, getSubCategory } from './itemCategory'

const toTimestamp = (value) => {
  const normalized = String(value || '').replace(/\//g, '-')
  const timestamp = new Date(normalized).getTime()
  return Number.isFinite(timestamp) ? timestamp : 0
}

export function getAllItems() {
  const seenIds = new Set()
  const items = []

  const sortedGachas = [...gachas].sort(
    (a, b) => toTimestamp(b.startDate) - toTimestamp(a.startDate),
  )

  sortedGachas.forEach((gacha) => {
    ;(gacha.items || []).forEach((item) => {
      if (!item?.id || seenIds.has(item.id)) {
        return
      }

      seenIds.add(item.id)
      items.push({
        ...item,
        sourceType: 'gacha',
        gachaSlug: gacha.slug,
        gachaTitle: gacha.title,
        gachaStartDate: gacha.startDate,
        normalizedCategory: getMainCategory(item.category),
        subCategory: getSubCategory(item.category),
      })
    })
  })

  historicalItems.forEach((item) => {
    if (!item?.id || seenIds.has(item.id) || item.matchedItemId) {
      return
    }

    seenIds.add(item.id)
    items.push({
      ...item,
      sourceType: 'historical',
      gachaSlug: '',
      gachaTitle: '',
      gachaStartDate: '',
      normalizedCategory: getMainCategory(
        item.mainCategory || item.category,
      ),
      subCategory: getSubCategory(item.category),
    })
  })

  return items
}

export function getItemById(itemId) {
  return getAllItems().find((item) => item.id === itemId) || null
}
