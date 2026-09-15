import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import './App.css'
import './home-v41.css'
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
    document.title = 'Aimy Closet｜Aimy非公式アイテム図鑑・ガチャ履歴'

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
        <section className="home-intro home-intro--compact">
          <div className="home-intro-copy">
            <p className="gacha-label">Aimy非公式アイテム図鑑</p>
            <h1>衣装・アイテムをすぐ探す</h1>
            <p>
              全{allItems.length}件の図鑑と、ガチャの開催期間・ラインナップを確認できます。
            </p>
          </div>
          <div className="home-intro-links" aria-label="サイト案内">
            <Link to="/guide">使い方</Link>
            <Link to="/insights">データ分析</Link>
          </div>
        </section>

        <LatestGacha />
        <CategoryGrid categories={categories} />
        <PopularItems />

        <section
          className="home-editorial home-editorial--compact"
          aria-labelledby="home-editorial-title"
        >
          <div className="section-heading-row">
            <div>
              <p className="gacha-label">調べ方・データの見方</p>
              <h2 id="home-editorial-title">探し方と検証方法</h2>
            </div>
            <Link to="/insights" className="text-link">ガイド一覧</Link>
          </div>

          <div className="editorial-card-grid">
            <Link to="/guides/item-finder" className="editorial-card">
              <span className="editorial-card-kicker">探し方</span>
              <h3>名前が分からない衣装を探す</h3>
              <p>画像・時期・カテゴリから探す手順を案内します。</p>
            </Link>
            <Link to="/guides/gacha-cycle" className="editorial-card">
              <span className="editorial-card-kicker">実測</span>
              <h3>ガチャは何日間隔で追加される？</h3>
              <p>登録済みの開催日時から間隔と期間を集計します。</p>
            </Link>
            <Link to="/guides/reprints" className="editorial-card">
              <span className="editorial-card-kicker">検証</span>
              <h3>復刻アイテムをどう数える？</h3>
              <p>一致条件と判定できないケースを分けて説明します。</p>
            </Link>
          </div>
        </section>
      </main>
      <Footer />
    </div>
  )
}

export default App
