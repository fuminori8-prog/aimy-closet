import '../App.css'
import Header from '../components/Header'
import AdBanner from '../components/AdBanner'
import Footer from '../components/Footer'
import GachaItemCard from '../components/GachaItemCard'
import GachaBanner from '../components/GachaBanner'
import { gachas } from '../data/gachas'
import { Link, useNavigate, useParams } from 'react-router-dom'

const raritySections = ['SSR', 'SR', 'NR']

const categoryOrder = [
  '衣装',
  '髪型',
  '目',
  '髪飾り',
  '耳飾り',
  'アクセサリー',
  'メガネ',
  'メイク',
  'チェキフレーム',
  '背景',
  'その他',
]

const groupItemsByCategory = (items) => {
  const groups = items.reduce((result, item) => {
    const category = item.category || 'その他'

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

  const gacha = gachas.find((item) => item.slug === slug)

  if (!gacha) {
    return null
  }

  const hasLineup = gacha.items?.length > 0

  const pageTitle = `${gacha.title}｜排出アイテム・開催期間｜Aimy Closet`

  const pageDescription =
    `${gacha.title}の開催期間と排出アイテム一覧を掲載しています。` +
    `SSR・SRなどのラインナップを確認できるAimy非公式ガチャデータベースです。`

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
              <span className="status-badge">{gacha.status}</span>

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
            確認済みアイテム数: {gacha.items.length}
          </p>
        </section>

        <AdBanner text="広告バナー 728×90" />

        {hasLineup ? (
          raritySections.map((rarity) => {
            const rarityItems = gacha.items.filter(
              (item) => item.rarity === rarity,
            )

            if (rarityItems.length === 0) {
              return null
            }

            const groupedItems = groupItemsByCategory(rarityItems)

            return (
              <section key={rarity} className="lineup-section">
                <h2>{rarity}ラインナップ</h2>

                {groupedItems.map(([category, items]) => (
                  <div key={category} className="lineup-group">
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
            )
          })
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

      <AdBanner text="広告バナー 728×90" />
      <Footer />
    </div>
  )
}

export default GachaDetail