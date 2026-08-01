import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import '../App.css'
import Header from '../components/Header'
import Footer from '../components/Footer'
import { historicalItems } from '../data/historicalItems'
import { getMainCategory } from '../utils/itemCategory'

const CATEGORY_TABS = [
  { name: '服', icon: '👕' },
  { name: '髪型', icon: '◉' },
  { name: 'アクセサリー', icon: '◒' },
  { name: 'パーツ', icon: '♙' },
  { name: '背景', icon: '▨' },
]

function periodKey(item) {
  return `${item.implementedFrom || ''}|${item.implementedTo || ''}|${item.implementationPeriod || ''}`
}

function HistoricalItemList() {
  const [selectedCategory, setSelectedCategory] = useState('服')

  useEffect(() => {
    document.title = 'ガチャ未特定の過去アイテム｜Aimy Closet'

    let meta = document.querySelector('meta[name="description"]')
    if (!meta) {
      meta = document.createElement('meta')
      meta.name = 'description'
      document.head.appendChild(meta)
    }
    meta.content =
      '2.5周年交換所で確認できた、ガチャ名・アイテム名が未特定の過去SR・SSRアイテムを実装月とカテゴリ別に掲載しています。'
  }, [])

  const groups = useMemo(() => {
    const filtered = historicalItems.filter(
      (item) => getMainCategory(item.mainCategory || item.category) === selectedCategory,
    )
    const grouped = new Map()

    filtered.forEach((item) => {
      const key = periodKey(item)
      if (!grouped.has(key)) {
        grouped.set(key, {
          key,
          label: item.implementationPeriod || '実装月未確認',
          implementedFrom: item.implementedFrom || '',
          implementedTo: item.implementedTo || '',
          items: [],
        })
      }
      grouped.get(key).items.push(item)
    })

    return [...grouped.values()].sort((left, right) => {
      const leftDate = `${left.implementedFrom}|${left.implementedTo}`
      const rightDate = `${right.implementedFrom}|${right.implementedTo}`
      return rightDate.localeCompare(leftDate, 'ja')
    })
  }, [selectedCategory])

  return (
    <div className="page">
      <Header />

      <main>
        <nav className="breadcrumb" aria-label="breadcrumb">
          <Link to="/">ホーム</Link>
          <span> &gt; </span>
          <Link to="/item">アイテム図鑑</Link>
          <span> &gt; </span>
          <span>ガチャ未特定の過去アイテム</span>
        </nav>

        <section className="historical-page">
          <div className="historical-heading">
            <h1>ガチャ未特定の過去アイテム</h1>
            <p>
              2.5周年交換所で存在を確認できたアイテムです。正式なアイテム名・配布ガチャが判明したものは、通常の図鑑データへ統合します。
            </p>
          </div>

          <div className="historical-category-tabs" role="tablist" aria-label="カテゴリ">
            {CATEGORY_TABS.map((category) => (
              <button
                key={category.name}
                type="button"
                role="tab"
                aria-selected={selectedCategory === category.name}
                className={selectedCategory === category.name ? 'active' : ''}
                onClick={() => setSelectedCategory(category.name)}
              >
                <span aria-hidden="true">{category.icon}</span>
                <strong>{category.name}</strong>
              </button>
            ))}
          </div>

          {groups.length > 0 ? (
            <div className="historical-periods">
              {groups.map((group) => (
                <section key={group.key} className="historical-period-section">
                  <h2>{group.label}</h2>
                  <div className="historical-item-grid">
                    {group.items.map((item) => (
                      <Link
                        key={item.id}
                        to={`/item/${item.id}`}
                        className="historical-item-tile"
                        aria-label={`${item.rarity} ${selectedCategory} 名称未特定`}
                        title={`${item.rarity}・${selectedCategory}・名称未特定`}
                      >
                        <img src={item.image} alt="名称未特定" loading="lazy" />
                      </Link>
                    ))}
                  </div>
                </section>
              ))}
            </div>
          ) : (
            <div className="historical-empty">
              <p>{selectedCategory}のガチャ未特定アイテムは、まだ登録されていません。</p>
            </div>
          )}
        </section>
      </main>

      <Footer />
    </div>
  )
}

export default HistoricalItemList
