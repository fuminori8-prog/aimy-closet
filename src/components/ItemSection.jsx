function ItemSection({ title, items, showRarity }) {
  return (
    <section className="latest">
      <h2>{title}</h2>

      <div className="card-grid item-grid">
        {items.map((item) => (
          <div key={item.id || item.name} className="card item-card">
            {showRarity && <span className="rarity-badge">{item.rarity}</span>}

            {item.image && (
              <img
                src={item.image}
                alt={item.name}
                className="item-image"
              />
            )}

            <h3>{item.name}</h3>

            <p>
              {showRarity
                ? item.category
                : `♡ ${item.hearts}`}
            </p>
          </div>
        ))}
      </div>
    </section>
  )
}

export default ItemSection