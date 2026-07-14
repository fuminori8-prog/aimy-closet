import { Link, NavLink } from 'react-router-dom'

function Header() {
  return (
    <header className="header">
      <Link to="/" className="logo logo-link">Aimy Closet</Link>
      <nav>
        <NavLink to="/item">アイテム図鑑</NavLink>
        <NavLink to="/gacha">ガチャ履歴</NavLink>
      </nav>
    </header>
  )
}

export default Header
