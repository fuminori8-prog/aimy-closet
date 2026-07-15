import { useEffect } from 'react'
import './App.css'
import Header from './components/Header'
import SearchBar from './components/SearchBar'
import LatestGacha from './components/LatestGacha'
import CategoryGrid from './components/CategoryGrid'
import ItemSection from './components/ItemSection'
import AdBanner from './components/AdBanner'
import Footer from './components/Footer'
import { gachas } from './data/gachas'
import {
  MAIN_CATEGORIES,
  getMainCategory,
} from './utils/itemCategory'

const categoryConfig = [
  { name: '服', icon: '👗' },
  { name: '髪型', icon: '💇‍♀️' },
  { name: 'アクセサリー', icon: '🎀' },
  { name: 'パーツ', icon: '👁️' },
  { name: '背景', icon: '🌈' },
]

const categorySet = new Set(MAIN_CATEGORIES)

const countByCategory = (() => {
  const counts = Object.fromEntries(categoryConfig.map((category) => [category.name, 0]))
  const seenItemIds = new Set()

  gachas.forEach((gacha) => {
    ;(gacha.items || []).forEach((item) => {
      if (seenItemIds.has(item.id)) {
        return
      }
      seenItemIds.add(item.id)

      const normalizedCategory = getMainCategory(item.category)

      if (categorySet.has(normalizedCategory)) {
        counts[normalizedCategory] += 1
      }
    })
  })

  return counts
})()

const categories = categoryConfig.map((category) => ({
  ...category,
  count: countByCategory[category.name] || 0,
  href: `/item?category=${encodeURIComponent(category.name)}`,
}))

const latestGacha = [...gachas].sort((a, b) => {
  const toDate = (str) => new Date(str.replace(/\//g, "-"))
  return toDate(b.startDate) - toDate(a.startDate)
})[0]

const latestItems = latestGacha.items.slice(0, 5)

function App() {

  useEffect(() => {
    document.title = 'Aimy Closet｜Aimy非公式アイテム図鑑・ガチャデータベース'

    let meta = document.querySelector('meta[name="description"]')

    if (!meta) {
      meta = document.createElement('meta')
      meta.name = 'description'
      document.head.appendChild(meta)
    }

    meta.content =
  'Aimyの服・髪型・アクセサリー・パーツ・背景のアイテム図鑑や、開催中・終了済みガチャの排出アイテムを掲載している非公式データベースです。'
 }, [])

  return (
    <div className="page">
      <Header />
      <main>
        <SearchBar />
        <LatestGacha />
        <AdBanner text="広告バナー 728×90" />
        <CategoryGrid categories={categories} />
        
        <ItemSection
          title="新着アイテム"
          items={latestItems}
          />
        <AdBanner text="広告バナー 728×90" />
      </main>
      <Footer />
    </div>
  )
}

export default App
