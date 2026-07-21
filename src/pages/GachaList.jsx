import '../App.css'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useSearchParams } from 'react-router-dom'
import Header from '../components/Header'
import SearchBar from '../components/SearchBar'
import AdBanner from '../components/AdBanner'
import Footer from '../components/Footer'
import GachaCard from '../components/GachaCard'
import { gachas } from '../data/gachas'
import { getGachaStatus } from '../utils/gachaStatus'

const GACHA_FILTERS = [
  { key: 'all', label: 'すべて' },
  { key: 'active', label: '開催中' },
  { key: 'ended', label: '開催終了' },
  { key: 'collecting', label: '情報収集中' },
]

function parseStartDate(value) {
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

function GachaList() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [selectedFilter, setSelectedFilter] = useState('all')
  const [currentTime, setCurrentTime] = useState(Date.now())

  const query = (searchParams.get('q') || '').trim().toLowerCase()

  useEffect(() => {
    const timer = window.setInterval(() => {
      setCurrentTime(Date.now())
    }, 30_000)

    return () => window.clearInterval(timer)
  }, [])

  const sortedGachas = useMemo(
    () =>
      [...gachas].sort((a, b) => {
        const timeA = parseStartDate(a.startDate)
        const timeB = parseStartDate(b.startDate)
        return timeB - timeA
      }),
    [],
  )

useEffect(() => {
  document.title = 'ガチャ履歴｜Aimy Closet'

  let meta = document.querySelector('meta[name="description"]')

  if (!meta) {
    meta = document.createElement('meta')
    meta.name = 'description'
    document.head.appendChild(meta)
  }

  meta.content =
    'Aimyの開催中・終了済みガチャの開催期間や排出アイテムを確認できる非公式ガチャデータベースです。'
}, [])

  const filteredGachas = useMemo(
    () =>
      sortedGachas.filter((gacha) => {
        const status = getGachaStatus(gacha, currentTime)
        const byStatus =
          selectedFilter === 'all' ||
          (selectedFilter === 'active' && status === '開催中') ||
          (selectedFilter === 'ended' && status === '開催終了') ||
          (selectedFilter === 'collecting' && gacha.infoStatus === '情報収集中')

        if (!byStatus) {
          return false
        }

        if (!query) {
          return true
        }

        const searchableFields = [gacha.title, gacha.type, status, gacha.infoStatus]
        return searchableFields.some((field) => String(field || '').toLowerCase().includes(query))
      }),
    [currentTime, query, selectedFilter, sortedGachas],
  )

  return (
    <div className="page">
      <Header />
      <main>
        <SearchBar targetPath="/gacha" />
        <section className="gacha-list-page">
          <div className="gacha-list-intro">
            <h1>ガチャ履歴</h1>
            <p>開催中・終了済みのガチャと排出アイテムを確認できます。</p>
          </div>

          <div className="filter-group" aria-label="gacha filters">
            {GACHA_FILTERS.map((filter) => (
              <button
                key={filter.key}
                type="button"
                className={`filter-button ${selectedFilter === filter.key ? 'active' : ''}`}
                onClick={() => setSelectedFilter(filter.key)}
              >
                {filter.label}
              </button>
            ))}
          </div>

          <p className="result-count">{filteredGachas.length}件 / 全{gachas.length}件</p>

          <AdBanner slot="gachaList" />

          {filteredGachas.length > 0 ? (
            <div className="gacha-grid">
              {filteredGachas.map((gacha) => (
                <GachaCard
                  key={gacha.id}
                  gacha={gacha}
                  onView={() => navigate(`/gacha/${gacha.slug}`)}
                  currentTime={currentTime}
                />
              ))}
            </div>
          ) : (
            <p className="lineup-note">該当するガチャはありません</p>
          )}
        </section>
      </main>
      <Footer />
    </div>
  )
}

export default GachaList
