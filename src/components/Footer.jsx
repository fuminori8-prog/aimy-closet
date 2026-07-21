import { affiliateAds } from '../config/affiliateAds'

function Footer() {
  return (
    <footer>
      <p>Aimy非公式ファンデータベース</p>
      <p>このサイトはAimy公式とは関係ありません</p>
      {affiliateAds.enabled ? (
        <p className="affiliate-disclosure">{affiliateAds.disclosure}</p>
      ) : null}
    </footer>
  )
}

export default Footer
