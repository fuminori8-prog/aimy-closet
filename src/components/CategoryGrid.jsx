import { Link } from 'react-router-dom'

function CategoryGrid({ categories }) {
  return (
    <section className="categories">
      <h2>アイテム図鑑</h2>
      <div className="card-grid">
        {categories.map((item) => (
          <Link key={item.name} to={item.href} className="card category-card-link">
            <div className="card-icon">{item.icon}</div>
            <h3>{item.name}</h3>
            <p className="category-count">{item.count}件</p>
          </Link>
        ))}
      </div>
    </section>
  )
}

export default CategoryGrid
