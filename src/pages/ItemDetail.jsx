import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import '../App.css'
import Header from '../components/Header'
import Footer from '../components/Footer'
import AdBanner from '../components/AdBanner'
import GachaItemCard from '../components/GachaItemCard'
import FavoriteButton from '../components/FavoriteButton'
import { gachas } from '../data/gachas'
import { getAllItems, getItemById } from '../utils/items'
import {
  getMainCategory,
  getSubCategory,
} from '../utils/itemCategory'

function ItemDetail() {
  const { itemId } = useParams()
  const navigate = useNavigate()
  const [hasImageError, setHasImageError] = useState(false)

  const found = useMemo(() => {
    const item = getItemById(itemId)
    if (!item) {
      return null
    }

    const gacha =
      item.sourceType === 'gacha'
        ? gachas.find((currentGacha) => currentGacha.slug === item.gachaSlug) || null
        : null

    return { item, gacha }
  }, [itemId])

  useEffect(() => {
    setHasImageError(false)
  }, [itemId])

  useEffect(() => {
    if (!found) {
      return
    }

    const { item } = found
    const displayName =
      item.sourceType === 'historical'
        ? `${item.name}（${item.implementationPeriod}）`
        : item.name
    const pageTitle = `${displayName}｜アイテム情報｜Aimy Closet`

    document.title = pageTitle

    const pageDescription =
      item.sourceType === 'historical'
        ? `${item.implementationPeriod}に実装された、名称・配布ガチャ未特定の${item.rarity}アイテムです。`
        : `${item.name}の入手方法、排出ガチャ、レアリティ、カテゴリを掲載しています。`

    let meta = document.querySelector('meta[name="description"]')

    if (!meta) {
      meta = document.createElement('meta')
      meta.name = 'description'
      document.head.appendChild(meta)
    }

    meta.content = pageDescription
  }, [found])

  if (!found) {
    return (
      <div className="page">
        <Header />
        <main>
          <nav className="breadcrumb" aria-label="breadcrumb">
            <Link to="/">ホーム</Link>
            <span> &gt; </span>
            <Link to="/item">アイテム図鑑</Link>
            <span> &gt; </span>
            <span>未登録アイテム</span>
          </nav>

          <section className="item-detail-card">
            <h1>アイテムが見つかりませんでした</h1>
            <div className="missing-actions">
              <Link to="/item" className="back-link-button">アイテム図鑑へ戻る</Link>
              <Link to="/gacha" className="back-link-button secondary">ガチャ履歴へ戻る</Link>
            </div>
          </section>
        </main>
        <Footer />
      </div>
    )
  }

  const { item, gacha } = found
  const hasImage = Boolean(item.image) && item.image !== 'placeholder' && !hasImageError
  const relatedItems = (
    gacha
      ? gacha.items || []
      : getAllItems().filter(
          (currentItem) =>
            currentItem.sourceType === 'historical' &&
            currentItem.id !== item.id &&
            currentItem.implementationPeriod === item.implementationPeriod &&
            currentItem.normalizedCategory === item.normalizedCategory,
        )
  ).filter((currentItem) => currentItem.id !== item.id).slice(0, 4)


  
  return (
    <div className="page">
      <Header />
      <main>
        <nav className="breadcrumb" aria-label="breadcrumb">
          <Link to="/">ホーム</Link>
          <span> &gt; </span>
          <Link to="/item">アイテム図鑑</Link>
          <span> &gt; </span>
          <span>{item.name}</span>
        </nav>

        <section className="item-detail-card">
          <div className="item-detail-grid">
            <div className="item-detail-image-wrap">
              <div className="item-image item-detail-image">
                {hasImage ? (
                  <img
                    src={item.image}
                    alt={item.name}
                    className="item-image-content"
                    onError={() => setHasImageError(true)}
                  />
                ) : (
                  <span>画像準備中</span>
                )}
              </div>
            </div>

            <div className="item-detail-info">
              <p className="gacha-label">アイテム詳細</p>
              <h1>{item.name}</h1>
              <p className="gacha-meta">レアリティ: {item.rarity}</p>
              <p className="gacha-meta">
                  カテゴリ: {getMainCategory(item.category)}
              </p>

              {getSubCategory(item.category) ? (
              <p className="gacha-meta">
                 種類: {getSubCategory(item.category)}
              </p>
              ) : null}
              {gacha ? (
                <>
                  <p className="gacha-meta">排出ガチャ: {gacha.title}</p>
                  <p className="gacha-meta">開催期間: {gacha.startDate} ～ {gacha.endDate}</p>
                  <div className="status-group">
                    <span className="status-badge">{gacha.status}</span>
                    {gacha.infoStatus === '情報収集中' ? <span className="info-badge">{gacha.infoStatus}</span> : null}
                  </div>
                </>
              ) : (
                <>
                  <p className="gacha-meta">実装時期: {item.implementationPeriod}</p>
                  <p className="gacha-meta">配布ガチャ: 未特定</p>
                  <div className="status-group">
                    <span className="info-badge">2.5周年交換所で確認</span>
                  </div>
                </>
              )}
              <FavoriteButton itemId={item.id} className="favorite-button-detail" />
              <button
                type="button"
                className="back-to-list-button"
                onClick={() =>
                  navigate(gacha ? `/gacha/${gacha.slug}` : '/historical-items')
                }
              >
                {gacha ? 'ガチャ詳細を見る' : '同時期の過去アイテムを見る'}
              </button>
            </div>
          </div>
        </section>

        <AdBanner slot="itemDetail" />

        {relatedItems.length > 0 ? (
          <section className="lineup-section">
            <h2>{gacha ? '同じガチャの関連アイテム' : '同時期・同カテゴリのアイテム'}</h2>
            <div className="card-grid item-grid">
              {relatedItems.map((relatedItem) => (
                <GachaItemCard
                  key={relatedItem.id}
                  id={relatedItem.id}
                  name={relatedItem.name}
                  rarity={relatedItem.rarity}
                  category={relatedItem.category}
                  image={relatedItem.image}
                />
              ))}
            </div>
          </section>
        ) : null}

        <div className="detail-back-wrap">
          <button type="button" className="back-to-list-button" onClick={() => navigate('/item')}>
            アイテム図鑑へ戻る
          </button>
        </div>
      </main>
      <Footer />
    </div>
  )
}

export default ItemDetail
