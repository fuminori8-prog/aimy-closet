import { useEffect, useMemo } from 'react'
import { Link } from 'react-router-dom'
import '../App.css'
import Header from '../components/Header'
import Footer from '../components/Footer'
import GachaItemCard from '../components/GachaItemCard'
import { useFavorites } from '../hooks/useFavorites'
import { getAllItems } from '../utils/items'

function Favorites() {
  const { authLoading, error, favoriteIds } = useFavorites()
  const allItems = useMemo(() => getAllItems(), [])

  const favoriteItems = useMemo(
    () => allItems.filter((item) => favoriteIds.has(item.id)),
    [allItems, favoriteIds],
  )

  useEffect(() => {
    document.title = 'お気に入り｜Aimy Closet'

    let meta = document.querySelector('meta[name="description"]')

    if (!meta) {
      meta = document.createElement('meta')
      meta.name = 'description'
      document.head.appendChild(meta)
    }

    meta.content = 'Aimy Closetでお気に入りに登録したアイテムの一覧です。'
  }, [])

  return (
    <div className="page">
      <meta name="robots" content="noindex,nofollow" />
      <Header />

      <main>
        <nav className="breadcrumb" aria-label="breadcrumb">
          <Link to="/">ホーム</Link>
          <span> &gt; </span>
          <span>お気に入り</span>
        </nav>

        <section className="item-list-page">
          <div className="item-list-intro">
            <h1>お気に入り</h1>
            <p>お気に入りに登録したアイテムを一覧で確認できます。</p>
          </div>

          {error ? <p className="favorite-error">{error}</p> : null}

          {authLoading ? (
            <p className="lineup-note">お気に入りを読み込んでいます。</p>
          ) : favoriteItems.length > 0 ? (
            <>
              <p className="result-count">{favoriteItems.length}件</p>
              <div className="card-grid item-grid">
                {favoriteItems.map((item) => (
                  <GachaItemCard
                    key={item.id}
                    item={item}
                    subtext={`排出: ${item.gachaTitle}`}
                  />
                ))}
              </div>
            </>
          ) : (
            <div className="favorites-empty">
              <p>お気に入りに登録したアイテムはまだありません。</p>
              <Link to="/item" className="back-link-button">
                アイテム図鑑を見る
              </Link>
            </div>
          )}
        </section>
      </main>

      <Footer />
    </div>
  )
}

export default Favorites
