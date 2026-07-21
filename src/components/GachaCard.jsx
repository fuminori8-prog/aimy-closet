import GachaBanner from './GachaBanner'
import { Link, useNavigate } from 'react-router-dom'
import { getGachaStatus } from '../utils/gachaStatus'

function GachaCard({ gacha, onView, currentTime }) {
  const navigate = useNavigate()
  const detailPath = `/gacha/${gacha.slug}`
  const status = getGachaStatus(gacha, currentTime)

  const handleView = () => {
    if (onView) {
      onView()
      return
    }
    navigate(detailPath)
  }

  return (
    <article className="gacha-card">
      <Link to={detailPath} className="gacha-card-banner-link" aria-label={`${gacha.title}の詳細へ`}>
        <GachaBanner
          src={gacha.banner}
          alt={gacha.title}
          title={gacha.title}
          className="gacha-card-banner"
        />
      </Link>
      <div className="gacha-card-body">
        <h3>{gacha.title}</h3>
        <p className="gacha-card-type">{gacha.type}</p>
        <p className="gacha-card-date">開始: {gacha.startDate}</p>
        <p className="gacha-card-date">終了: {gacha.endDate}</p>
        <div className="gacha-card-footer">
          <div className="status-group">
            <span className={`status-badge ${status === '開催終了' ? 'status-badge--ended' : ''}`}>{status}</span>
            {gacha.infoStatus === '情報収集中' ? <span className="info-badge">{gacha.infoStatus}</span> : null}
          </div>
          <span className="item-count">確認済みアイテム: {gacha.items.length}</span>
        </div>
        <button type="button" onClick={handleView}>
          詳細を見る
        </button>
      </div>
    </article>
  )
}

export default GachaCard
