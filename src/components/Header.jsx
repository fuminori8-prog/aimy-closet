import { Link, NavLink } from 'react-router-dom'

function Header() {
  return (
    <header className="header">
      <div className="logo-area">
        <Link to="/" className="logo logo-link">
            Aimy Closet
        </Link>

            <span className="logo-description">
                Aimy非公式アイテム図鑑・ガチャデータベース
            </span>
    </div>

      <nav className="header-nav">
        <NavLink to="/item" className="nav-button">
          📖 アイテム図鑑
        </NavLink>

        <NavLink to="/gacha" className="nav-button">
          🎲 ガチャ履歴
        </NavLink>
      </nav>
    </header>
  )
}

export default Header