import { Link } from 'react-router-dom'

function GachaItemCard({ id, name, rarity, category, image }) {
  const hasImage = Boolean(image) && image !== 'placeholder'

  return (
    <Link to={`/item/${id}`} className="card item-card gacha-item-card">
      <div className="item-image">
        {hasImage ? <img src={image} alt={name} className="item-image-content" /> : <span>画像準備中</span>}
      </div>
      <h3>{name}</h3>
      <p>{category}</p>
    </Link>
  )
}

export default GachaItemCard
