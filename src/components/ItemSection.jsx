import GachaItemCard from './GachaItemCard'

function ItemSection({ title, items }) {
  return (
    <section className="latest">
      <h2>{title}</h2>

      <div className="card-grid item-grid">
        {items.map((item) => (
          <GachaItemCard
            key={item.id || item.name}
            item={item}
          />
        ))}
      </div>
    </section>
  )
}

export default ItemSection
