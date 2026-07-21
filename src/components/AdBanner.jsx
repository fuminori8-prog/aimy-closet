import { getAffiliateAd } from '../config/affiliateAds'

function AdBanner({ slot }) {
  const ad = getAffiliateAd(slot)

  if (!ad) {
    return null
  }

  return (
    <aside className="affiliate-ad" aria-label="広告">
      <span className="affiliate-ad-label">PR</span>
      <div
        className="affiliate-ad-content"
        dangerouslySetInnerHTML={{ __html: ad.html }}
      />
    </aside>
  )
}

export default AdBanner
