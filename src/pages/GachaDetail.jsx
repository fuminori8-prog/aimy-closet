import '../App.css'
import { useEffect, useState } from 'react'
import Header from '../components/Header'
import Footer from '../components/Footer'
import GachaItemCard from '../components/GachaItemCard'
import GachaBanner from '../components/GachaBanner'
import { gachas } from '../data/gachas'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { MAIN_CATEGORIES, getMainCategory } from '../utils/itemCategory'
import { getGachaStatus } from '../utils/gachaStatus'

const categoryOrder = MAIN_CATEGORIES

const groupItemsByCategory = (items) => {
  const groups = items.reduce((result, item) => {
    const category = getMainCategory(item.category)

    if (!result[category]) {
      result[category] = []
    }

    result[category].push(item)
    return result
  }, {})

  return categoryOrder
    .filter((category) => groups[category]?.length)
    .map((category) => [category, groups[category]])
}

function GachaDetail() {
  const { slug } = useParams()
  const navigate = useNavigate()
  const [currentTime, setCurrentTime] = useState(Date.now())

  useEffect(() => {
    const timer = window.setInterval(() => {
      setCurrentTime(Date.now())
    }, 30_000)

    return () => window.clearInterval(timer)
  }, [])

  const gacha = gachas.find((item) => item.slug === slug)

  if (!gacha) {
    return null
  }

  const hasLineup = gacha.items?.length > 0
  const status = getGachaStatus(gacha, currentTime)
  const items = gacha.items || []
  const groupedItems = groupItemsByCategory(items)
  const rarityCounts = items.reduce((counts, item) => {
    const rarity = String(item.rarity || '未確認')
    counts[rarity] = (counts[rarity] || 0) + 1
    return counts
  }, {})
  const raritySummary = ['SSR', 'SR', 'R', '未確認']
    .filter((rarity) => rarityCounts[rarity])
    .map((rarity) => `${rarity} ${rarityCounts[rarity]}件`)
    .join('・')
  const categorySummary = groupedItems
    .map(([category, categoryItems]) => `${category} ${categoryItems.length}件`)
    .join('・')

  const pageTitle = `${gacha.title}｜排出アイテム・開催期間｜Aimy Closet`

  const pageDescription =
    `${gacha.title}は${gacha.startDate}から${gacha.endDate}まで開催。` +
    `確認済み${items.length}件の排出アイテムを、レアリティ・カテゴリ別に掲載しています。`

  const pageUrl = `https://aimycloset.jp/gacha/${gacha.slug}`

  const ogImage = gacha.banner
    ? `https://aimycloset.jp${gacha.banner}`
    : 'https://aimycloset.jp/AimyCloset_OGP.png'

  return (
    <div className="page">
      <title>{pageTitle}</title>

      <meta name="description" content={pageDescription} />
      <link rel="canonical" href={pageUrl} />

      <meta property="og:type" content="article" />
      <meta property="og:site_name" content="Aimy Closet" />
      <meta property="og:title" content={pageTitle} />
      <meta property="og:description" content={pageDescription} />
      <meta property="og:url" content={pageUrl} />
      <meta property="og:image" content={ogImage} />
      <meta property="og:locale" content="ja_JP" />

      <meta name="twitter:card" content="summary_large_image" />
      <meta name="twitter:title" content={pageTitle} />
      <meta name="twitter:description" content={pageDescription} />
      <meta name="twitter:image" content={ogImage} />

      <Header />

      <main>
        <nav className="breadcrumb" aria-label="breadcrumb">
          <Link to="/">ホーム</Link>
          <span> &gt; </span>
          <Link to="/gacha">ガチャ履歴</Link>
          <span> &gt; </span>
          <span>{gacha.title}</span>
        </nav>

        <section className="gacha-detail-card">
          <div className="gacha-detail-header">
            <div>
              <p className="gacha-label">ガチャ詳細</p>
              <h1>{gacha.title}</h1>
              <p className="gacha-meta">{gacha.type}</p>
            </div>

            <div className="status-group">
              <span className={`status-badge ${status === '開催終了' ? 'status-badge--ended' : ''}`}>{status}</span>

              {gacha.infoStatus === '情報収集中' ? (
                <span className="info-badge">{gacha.infoStatus}</span>
              ) : null}
            </div>
          </div>

          <GachaBanner
            src={gacha.banner}
            alt={gacha.title}
            title={gacha.title}
            className="gacha-detail-banner"
          />

          <div className="gacha-dates">
            <p>開始: {gacha.startDate}</p>
            <p>終了: {gacha.endDate}</p>
          </div>

          <p className="gacha-description">{gacha.description}</p>

          <p className="confirmed-count">
            確認済みアイテム数: {items.length}
          </p>
        </section>

        <section className="gacha-data-summary" aria-labelledby="gacha-data-summary-title">
          <h2 id="gacha-data-summary-title">このガチャの登録内容</h2>
          {hasLineup ? (
            <>
              <p>
                当サイトで確認できた{items.length}件を掲載しています。
                レアリティ別では{raritySummary || '情報確認中'}、
                カテゴリ別では{categorySummary || '情報確認中'}です。
              </p>
              <dl className="gacha-summary-grid">
                <div>
                  <dt>開催期間</dt>
                  <dd>{gacha.startDate} ～ {gacha.endDate}</dd>
                </div>
                <div>
                  <dt>レアリティ構成</dt>
                  <dd>{raritySummary || '情報確認中'}</dd>
                </div>
                <div>
                  <dt>カテゴリ構成</dt>
                  <dd>{categorySummary || '情報確認中'}</dd>
                </div>
              </dl>
            </>
          ) : (
            <p>
              開催期間と基本情報を先に掲載しています。ラインナップは確認後に追加します。
            </p>
          )}
          <p className="data-policy-link">
            自動検出だけで確定せず、画像・名称・カテゴリを確認して登録しています。{' '}
            <Link to="/data-policy">掲載データの確認・修正方針を見る</Link>
          </p>
        </section>

        {hasLineup ? (
          <section className="lineup-section">
            <h2>アイテムラインナップ</h2>

            {groupedItems.map(([category, items]) => (
              <div className="lineup-group" key={category}>
                <h3>{category}</h3>

                <div className="card-grid item-grid">
                  {items.map((item) => (
                    <GachaItemCard
                      key={item.id}
                      id={item.id}
                      name={item.name}
                      rarity={item.rarity}
                      category={item.category}
                      image={item.image}
                    />
                  ))}
                </div>
              </div>
            ))}
          </section>
        ) : (
          <section className="lineup-section">
            <h2>ラインナップ情報</h2>

            <p className="lineup-note">
              現在確認できる情報を掲載しています。
              <br />
              排出アイテムの詳細は情報収集中です。
            </p>
          </section>
        )}
        <div className="detail-back-wrap">
          <button
            type="button"
            className="back-to-list-button"
            onClick={() => navigate('/gacha')}
          >
            ガチャ履歴へ戻る
          </button>
        </div>
      </main>

      <Footer />
    </div>
  )
}

export default GachaDetail
