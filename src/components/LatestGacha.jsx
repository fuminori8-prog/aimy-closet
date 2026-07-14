import { useMemo } from 'react'
import { gachas } from '../data/gachas'
import { useNavigate } from 'react-router-dom'
import GachaCard from './GachaCard'

const parseStartDate = (value) => {
  if (!value) {
    return Number.NEGATIVE_INFINITY
  }

  const match = String(value).match(/(\d{4})\/(\d{1,2})\/(\d{1,2})(?:\s+(\d{1,2}):(\d{1,2}))?/)
  if (!match) {
    return Number.NEGATIVE_INFINITY
  }

  const year = Number(match[1])
  const month = Number(match[2])
  const day = Number(match[3])
  const hour = Number(match[4] || 0)
  const minute = Number(match[5] || 0)

  return Date.UTC(year, month - 1, day, hour, minute)
}

function LatestGacha() {
  const navigate = useNavigate()
  const latestThreeGachas = useMemo(
    () =>
      [...gachas]
        .sort((a, b) => parseStartDate(b.startDate) - parseStartDate(a.startDate))
        .slice(0, 3),
    [],
  )

  if (latestThreeGachas.length === 0) {
    return null
  }

  return (
    <section className="latest">
      <div className="gacha-list-intro">
        <h2>最新ガチャ</h2>
      </div>
      <div className="gacha-grid">
        {latestThreeGachas.map((gacha) => (
          <GachaCard key={gacha.id} gacha={gacha} onView={() => navigate(`/gacha/${gacha.slug}`)} />
        ))}
      </div>
    </section>
  )
}

export default LatestGacha
