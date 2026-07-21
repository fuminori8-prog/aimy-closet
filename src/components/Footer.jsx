import { Link } from 'react-router-dom'
import { affiliateAds } from '../config/affiliateAds'

function Footer() {
  return (
    <footer>
      <p>Aimy非公式ファンデータベース</p>
      <p>このサイトはAimy公式とは関係ありません</p>

      <nav className="footer-links" aria-label="フッターナビ">
        <Link to="/privacy">プライバシーポリシー</Link>
        <Link to="/disclaimer">免責事項</Link>
        <Link to="/contact">お問い合わせ</Link>
      </nav>

      {affiliateAds.enabled ? (
        <p className="affiliate-disclosure">{affiliateAds.disclosure}</p>
      ) : null}
    </footer>
  )
}

export default Footer
