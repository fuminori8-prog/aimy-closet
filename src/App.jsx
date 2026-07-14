import './App.css'
import Header from './components/Header'
import SearchBar from './components/SearchBar'
import LatestGacha from './components/LatestGacha'
import CategoryGrid from './components/CategoryGrid'
import ItemSection from './components/ItemSection'
import AdBanner from './components/AdBanner'
import Footer from './components/Footer'
import { gachas } from './data/gachas'

const categoryConfig = [
  { name: '衣装', icon: '👗' },
  { name: '髪型', icon: '💇' },
  { name: '目', icon: '👁️' },
  { name: '髪飾り', icon: '🎀' },
  { name: '耳飾り', icon: '✨' },
  { name: 'メガネ', icon: '🕶️' },
  { name: 'メイク', icon: '💄' },
  { name: 'チェキフレーム', icon: '🖼️' },
  { name: '背景', icon: '🌈' },
]

const categoryAliases = {
  服: '衣装',
  髪: '髪型',
}

const categorySet = new Set(categoryConfig.map((category) => category.name))

const countByCategory = (() => {
  const counts = Object.fromEntries(categoryConfig.map((category) => [category.name, 0]))
  const seenItemIds = new Set()

  gachas.forEach((gacha) => {
    ;(gacha.items || []).forEach((item) => {
      if (seenItemIds.has(item.id)) {
        return
      }
      seenItemIds.add(item.id)

      const rawCategory = (item.category || '').trim()
      const normalizedCategory = categoryAliases[rawCategory] || rawCategory

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

const latestItems = latestGacha.items.slice(0, 5)

function App() {
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
          showRarity
          />
        <AdBanner text="広告バナー 728×90" />
      </main>
      <Footer />
    </div>
  )
}

export default App
