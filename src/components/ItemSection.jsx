function ItemSection({ title, items, showRarity }) {
  return (
    <section className="latest">
      <h2>{title}</h2>
      <div className="card-grid item-grid">
        {items.map((item) => (
          <div key={item.name} className="card item-card">
            {showRarity ? <span className="rarity-badge">{item.rarity}</span> : null}
            <div className="item-image" />
            <h3>{item.name}</h3>
            <p>{showRarity ? `配信日 ${item.date}` : `♡ ${item.hearts}`}</p>
          </div>
        ))}
      </div>
    </section>
  )
}

export default ItemSection
