import { useFavorites } from '../hooks/useFavorites'

function FavoriteButton({ itemId, className = '' }) {
  const {
    authLoading,
    counts,
    isBusy,
    isFavorite,
    toggleFavorite,
  } = useFavorites()

  const active = isFavorite(itemId)
  const busy = isBusy(itemId)
  const count = Number(counts[itemId] || 0)

  const handleClick = async (event) => {
    event.preventDefault()
    event.stopPropagation()
    await toggleFavorite(itemId)
  }

  return (
    <button
      type="button"
      className={`favorite-button ${active ? 'active' : ''} ${className}`.trim()}
      aria-pressed={active}
      aria-label={active ? 'お気に入りから外す' : 'お気に入りに追加'}
      disabled={authLoading || busy}
      onClick={handleClick}
    >
      <span aria-hidden="true">{active ? '♥' : '♡'}</span>
      <span>{count}</span>
    </button>
  )
}

export default FavoriteButton
