import '../App.css'
import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import Header from '../components/Header'
import Footer from '../components/Footer'
import AdBanner from '../components/AdBanner'
import SearchBar from '../components/SearchBar'
import GachaItemCard from '../components/GachaItemCard'
import { getAllItems } from '../utils/items'
import {
  MAIN_CATEGORIES,
  getMainCategory,
} from '../utils/itemCategory'

const CATEGORY_LABELS = MAIN_CATEGORIES

const SUB_CATEGORY_OPTIONS = {
  アクセサリー: ['あたま', 'めがね', 'ピアス'],
  パーツ: ['メイク', '目', '口', '鼻', 'まゆげ'],
}

function ItemList() {
  const [searchParams] = useSearchParams()
  const [selectedCategory, setSelectedCategory] = useState('すべて')
  const [selectedSubCategory, setSelectedSubCategory] = useState('すべて')
  const allItems = useMemo(() => getAllItems(), [])

  const query = (searchParams.get('q') || '').trim().toLowerCase()
  const categoryQuery = (searchParams.get('category') || '').trim()

  useEffect(() => {
    if (!categoryQuery) {
      setSelectedCategory('すべて')
      setSelectedSubCategory('すべて')
      return
    }

    const normalized = getMainCategory(categoryQuery)

    setSelectedCategory(
      CATEGORY_LABELS.includes(normalized) ? normalized : 'すべて',
    )
    setSelectedSubCategory('すべて')
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
      'Aimyの服・髪型・アクセサリー・パーツ・背景・チェキフレームを検索・一覧表示できる非公式アイテム図鑑です。'
  }, [])

  const filteredItems = useMemo(
    () =>
      allItems.filter((item) => {
        const byCategory =
          selectedCategory === 'すべて' ||
          item.normalizedCategory === selectedCategory

        if (!byCategory) {
          return false
        }

        const bySubCategory =
          selectedSubCategory === 'すべて' ||
          item.subCategory === selectedSubCategory

        if (!bySubCategory) {
          return false
        }

        if (!query) {
          return true
        }

        const searchableFields = [
          item.name,
          item.normalizedCategory,
          item.subCategory,
          item.rarity,
          item.gachaTitle,
        ]

        return searchableFields.some((field) =>
          String(field || '').toLowerCase().includes(query),
        )
      }),
    [allItems, query, selectedCategory, selectedSubCategory],
  )

  const subCategoryOptions = SUB_CATEGORY_OPTIONS[selectedCategory] || []

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
              className={`filter-button ${
                selectedCategory === 'すべて' ? 'active' : ''
              }`}
              onClick={() => {
                setSelectedCategory('すべて')
                setSelectedSubCategory('すべて')
              }}
            >
              すべて
            </button>

            {CATEGORY_LABELS.map((category) => (
              <button
                key={category}
                type="button"
                className={`filter-button ${
                  selectedCategory === category ? 'active' : ''
                }`}
                onClick={() => {
                  setSelectedCategory(category)
                  setSelectedSubCategory('すべて')
                }}
              >
                {category}
              </button>
            ))}
          </div>

          {subCategoryOptions.length > 0 ? (
            <div
              className="filter-group subcategory-filter-group"
              aria-label="item subcategory filters"
            >
              <button
                type="button"
                className={`filter-button ${
                  selectedSubCategory === 'すべて' ? 'active' : ''
                }`}
                onClick={() => setSelectedSubCategory('すべて')}
              >
                種類：すべて
              </button>

              {subCategoryOptions.map((subCategory) => (
                <button
                  key={subCategory}
                  type="button"
                  className={`filter-button ${
                    selectedSubCategory === subCategory ? 'active' : ''
                  }`}
                  onClick={() => setSelectedSubCategory(subCategory)}
                >
                  {subCategory}
                </button>
              ))}
            </div>
          ) : null}

          <p className="result-count">
            {filteredItems.length}件 / 全{allItems.length}件
          </p>

          <AdBanner text="広告バナー 728×90" />

          {filteredItems.length > 0 ? (
            <div className="card-grid item-grid">
              {filteredItems.map((item) => {
                const categoryLabel = item.subCategory
                  ? `${item.normalizedCategory}：${item.subCategory}`
                  : item.normalizedCategory

                return (
                  <GachaItemCard
                    key={item.id}
                    item={{ ...item, category: categoryLabel }}
                    subtext={`排出: ${item.gachaTitle}`}
                  />
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
