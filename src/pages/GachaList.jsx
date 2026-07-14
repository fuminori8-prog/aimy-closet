import '../App.css'
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useSearchParams } from 'react-router-dom'
import Header from '../components/Header'
import SearchBar from '../components/SearchBar'
import AdBanner from '../components/AdBanner'
import Footer from '../components/Footer'
import GachaCard from '../components/GachaCard'
import { gachas } from '../data/gachas'

const GACHA_FILTERS = [
  { key: 'all', label: 'すべて' },
  { key: 'active', label: '開催中' },
  { key: 'ended', label: '終了済み' },
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

  const query = (searchParams.get('q') || '').trim().toLowerCase()

  const sortedGachas = useMemo(
    () =>
      [...gachas].sort((a, b) => {
        const timeA = parseStartDate(a.startDate)
        const timeB = parseStartDate(b.startDate)
        return timeB - timeA
      }),
    [],
  )

  const filteredGachas = useMemo(
    () =>
      sortedGachas.filter((gacha) => {
        const byStatus =
          selectedFilter === 'all' ||
          (selectedFilter === 'active' && gacha.status === '開催中') ||
          (selectedFilter === 'ended' && gacha.status === '終了済み') ||
          (selectedFilter === 'collecting' && gacha.infoStatus === '情報収集中')

        if (!byStatus) {
          return false
        }

        if (!query) {
          return true
        }

        const searchableFields = [gacha.title, gacha.type, gacha.status, gacha.infoStatus]
        return searchableFields.some((field) => String(field || '').toLowerCase().includes(query))
      }),
    [query, selectedFilter, sortedGachas],
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

          <AdBanner text="広告バナー 728×90" />

          {filteredGachas.length > 0 ? (
            <div className="gacha-grid">
              {filteredGachas.map((gacha) => (
                <GachaCard
                  key={gacha.id}
                  gacha={gacha}
                  onView={() => navigate(`/gacha/${gacha.slug}`)}
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
