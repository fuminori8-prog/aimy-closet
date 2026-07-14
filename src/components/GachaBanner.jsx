import { useEffect, useState } from 'react'

function GachaBanner({ src, alt, title, className = '' }) {
  const [hasImageError, setHasImageError] = useState(false)

  useEffect(() => {
    setHasImageError(false)
  }, [src])

  const showPlaceholder = hasImageError

  return (
    <div className={`gacha-banner ${className}`.trim()}>
      {showPlaceholder ? (
        <span>画像準備中</span>
      ) : (
        <img
          src={src || ''}
          alt={alt || title}
          className="gacha-banner-image"
          onError={() => setHasImageError(true)}
        />
      )}
    </div>
  )
}

export default GachaBanner
