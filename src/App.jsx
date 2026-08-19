import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import './App.css'
import Header from './components/Header'
import SearchBar from './components/SearchBar'
import LatestGacha from './components/LatestGacha'
import CategoryGrid from './components/CategoryGrid'
import PopularItems from './components/PopularItems'
import Footer from './components/Footer'
import { getAllItems } from './utils/items'
import { MAIN_CATEGORIES } from './utils/itemCategory'

const categoryConfig = [
  { name: '服', icon: '👗' },
  { name: '髪型', icon: '💇‍♀️' },
  { name: 'アクセサリー', icon: '🎀' },
  { name: 'パーツ', icon: '👁️' },
  { name: '背景', icon: '🌈' },
  { name: 'チェキフレーム', icon: '🖼️' },
]

const categorySet = new Set(MAIN_CATEGORIES)
const allItems = getAllItems()

const countByCategory = allItems.reduce(
  (counts, item) => {
    if (categorySet.has(item.normalizedCategory)) {
      counts[item.normalizedCategory] += 1
    }
    return counts
  },
  Object.fromEntries(categoryConfig.map((category) => [category.name, 0])),
)

const categories = categoryConfig.map((category) => ({
  ...category,
  count: countByCategory[category.name] || 0,
  href: `/item?category=${encodeURIComponent(category.name)}`,
}))

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
      'Aimyの服・髪型・アクセサリー・パーツ・背景・チェキフレームのアイテム図鑑や、開催中・終了済みガチャの排出アイテムを掲載している非公式データベースです。'
  }, [])

  return (
    <div className="page">
      <Header />
      <main>
        <SearchBar />
        <section className="home-intro">
          <p className="gacha-label">Aimy非公式ファンデータベース</p>
          <h1>Aimyの衣装・アイテムとガチャ履歴を探す</h1>
          <p>
            服・髪型・アクセサリー・目・背景など全{allItems.length}件と、
            登録済みガチャの開催期間・確認済みラインナップをまとめています。
            名前が分からないアイテムは画像からも検索できます。
          </p>
          <div className="home-intro-links">
            <Link to="/guide">はじめての方へ・使い方</Link>
            <Link to="/data-policy">掲載データの確認方法</Link>
            <Link to="/about">Aimy Closetについて</Link>
          </div>
        </section>
        <LatestGacha />
        <CategoryGrid categories={categories} />
        <PopularItems />
      </main>
      <Footer />
    </div>
  )
}

export default App
