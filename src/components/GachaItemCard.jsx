import { Link } from 'react-router-dom'
import FavoriteButton from './FavoriteButton'
import { getCanonicalItemId } from '../utils/items'

function GachaItemCard({ item, id, name, rarity, category, image, subtext }) {
  const itemData = item || { id, name, rarity, category, image }
  const canonicalItemId = getCanonicalItemId(itemData.id)
  const hasImage = Boolean(itemData.image) && itemData.image !== 'placeholder'

  return (
    <article className="card item-card gacha-item-card">
      <Link to={`/item/${canonicalItemId}`} className="item-card-main-link">
        <div className="item-image">
          {hasImage ? (
            <img
              src={itemData.image}
              alt={itemData.name}
              className="item-image-content"
            />
          ) : (
            <span>画像準備中</span>
          )}
        </div>
        <h3>{itemData.name}</h3>
        <p>{itemData.category}</p>
        {subtext ? <p className="item-subtext">{subtext}</p> : null}
      </Link>

      <FavoriteButton itemId={canonicalItemId} />
    </article>
  )
}

export default GachaItemCard
