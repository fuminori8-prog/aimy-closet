import '../App.css'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useSearchParams } from 'react-router-dom'
import Header from '../components/Header'
import Footer from '../components/Footer'
import AdBanner from '../components/AdBanner'
import SearchBar from '../components/SearchBar'
import { gachas } from '../data/gachas'

const CATEGORY_LABELS = [
  '衣装',
  '髪型',
  '目',
  '髪飾り',
  '耳飾り',
  'メガネ',
  'メイク',
  'チェキフレーム',
  '背景',
]

const CATEGORY_ALIASES = {
  服: '衣装',
  髪: '髪型',
  アクセ: 'アクセサリー',
}

function normalizeCategory(category) {
  const trimmed = (category || '').trim()

  if (CATEGORY_ALIASES[trimmed]) {
    return CATEGORY_ALIASES[trimmed]
  }

  if (CATEGORY_LABELS.includes(trimmed)) {
    return trimmed
  }

  return 'その他'
}

function ItemList() {
  const [searchParams] = useSearchParams()
  const [selectedCategory, setSelectedCategory] = useState('すべて')

  const allItems = useMemo(
    () =>
      gachas.flatMap((gacha) =>
        (gacha.items || []).map((item) => ({
          ...item,
          gachaSlug: gacha.slug,
          gachaTitle: gacha.title,
          normalizedCategory: normalizeCategory(item.category),
        })),
      ),
    [],
  )

  const query = (searchParams.get('q') || '').trim().toLowerCase()
  const categoryQuery = (searchParams.get('category') || '').trim()

  useEffect(() => {
    if (!categoryQuery) {
      setSelectedCategory('すべて')
      return
    }

    if (CATEGORY_LABELS.includes(categoryQuery)) {
      setSelectedCategory(categoryQuery)
      return
    }

    const normalized = CATEGORY_ALIASES[categoryQuery]
    setSelectedCategory(normalized && CATEGORY_LABELS.includes(normalized) ? normalized : 'すべて')
  }, [categoryQuery])

useEffect(() => {
  document.title = 'アイテム図鑑｜Aimy Closet'

  let meta = document.querySelector('meta[name="description"]')

  if (!meta) {
    meta = document.createElement('meta')
    meta.name = 'description'
    document.head.appendChild(meta)
  }

  meta.content =
    'Aimyの衣装・髪型・目・背景などのアイテムを検索・一覧表示できる非公式アイテム図鑑です。'
}, [])

  const filteredItems = useMemo(
    () =>
      allItems.filter((item) => {
        const byCategory = selectedCategory === 'すべて' || item.normalizedCategory === selectedCategory
        if (!byCategory) {
          return false
        }

        if (!query) {
          return true
        }

        const searchableFields = [item.name, item.normalizedCategory, item.rarity, item.gachaTitle]
        return searchableFields.some((field) => String(field || '').toLowerCase().includes(query))
      }),
    [allItems, query, selectedCategory],
  )

  return (
    <div className="page">
      <Header />
      <main>
        <nav className="breadcrumb" aria-label="breadcrumb">
          <Link to="/">ホーム</Link>
          <span> &gt; </span>
          <span>アイテム図鑑</span>
        </nav>

        <section className="item-list-page">
          <div className="item-list-intro">
            <h1>アイテム図鑑</h1>
            <p>確認済みのアイテムを一覧で確認できます。</p>
          </div>

          <SearchBar targetPath="/item" />

          <div className="filter-group" aria-label="item category filters">
            <button
              type="button"
              className={`filter-button ${selectedCategory === 'すべて' ? 'active' : ''}`}
              onClick={() => setSelectedCategory('すべて')}
            >
              すべて
            </button>
            {CATEGORY_LABELS.map((category) => (
              <button
                key={category}
                type="button"
                className={`filter-button ${selectedCategory === category ? 'active' : ''}`}
                onClick={() => setSelectedCategory(category)}
              >
                {category}
              </button>
            ))}
          </div>

          <p className="result-count">{filteredItems.length}件 / 全{allItems.length}件</p>

          <AdBanner text="広告バナー 728×90" />

          {filteredItems.length > 0 ? (
            <div className="card-grid item-grid">
              {filteredItems.map((item) => {
                const hasImage = Boolean(item.image) && item.image !== 'placeholder'

                return (
                  <Link to={`/item/${item.id}`} key={item.id} className="card item-card gacha-item-card">
                    <div className="item-image">
                      {hasImage ? (
                        <img src={item.image} alt={item.name} className="item-image-content" />
                      ) : (
                        <span>画像準備中</span>
                      )}
                    </div>
                    <h3>{item.name}</h3>
                    <p>{item.normalizedCategory}</p>
                    <p className="item-subtext">排出: {item.gachaTitle}</p>
                  </Link>
                )
              })}
            </div>
          ) : (
            <p className="lineup-note">該当するアイテムはありません</p>
          )}
        </section>
      </main>
      <Footer />
    </div>
  )
}

export default ItemList
