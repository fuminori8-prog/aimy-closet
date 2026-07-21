import { useMemo } from 'react'
import { useFavorites } from '../hooks/useFavorites'
import { getAllItems } from '../utils/items'
import ItemSection from './ItemSection'

function PopularItems() {
  const { counts } = useFavorites()
  const allItems = useMemo(() => getAllItems(), [])

  const popularItems = useMemo(
    () =>
      [...allItems]
        .sort((a, b) => {
          const countDifference =
            Number(counts[b.id] || 0) - Number(counts[a.id] || 0)

          if (countDifference !== 0) {
            return countDifference
          }

          return allItems.indexOf(a) - allItems.indexOf(b)
        })
        .slice(0, 5),
    [allItems, counts],
  )

  if (popularItems.length === 0) {
    return null
  }

  return <ItemSection title="人気アイテム" items={popularItems} />
}

export default PopularItems
