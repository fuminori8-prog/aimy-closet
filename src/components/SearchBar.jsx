import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

function SearchBar({ targetPath = '/item', placeholder = 'アイテム名・ガチャ名・タグで検索' }) {
  const location = useLocation()
  const navigate = useNavigate()
  const [keyword, setKeyword] = useState('')

  useEffect(() => {
    const params = new URLSearchParams(location.search)
    setKeyword(params.get('q') || '')
  }, [location.search])

  const handleSubmit = (event) => {
    event.preventDefault()
    const trimmed = keyword.trim()
    const params = new URLSearchParams()

    if (trimmed) {
      params.set('q', trimmed)
    }

    navigate(`${targetPath}${params.toString() ? `?${params.toString()}` : ''}`)
  }

  return (
    <form className="search" onSubmit={handleSubmit}>
      <span>🔍</span>
      <input
        type="text"
        placeholder={placeholder}
        value={keyword}
        onChange={(event) => setKeyword(event.target.value)}
      />
      <button type="submit">検索</button>
    </form>
  )
}

export default SearchBar
