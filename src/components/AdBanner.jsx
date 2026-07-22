import { useEffect, useRef, useState } from 'react'
import { getAffiliateAd } from '../config/affiliateAds'

const MOBILE_WIDGET_QUERY = '(max-width: 840px)'

function getInitialMobileState() {
  return typeof window !== 'undefined' && window.matchMedia(MOBILE_WIDGET_QUERY).matches
}

function DmmWidget({ desktopId, mobileId }) {
  const hostRef = useRef(null)
  const [isMobile, setIsMobile] = useState(getInitialMobileState)
  const placementId = isMobile ? mobileId : desktopId

  useEffect(() => {
    const mediaQuery = window.matchMedia(MOBILE_WIDGET_QUERY)
    const handleChange = (event) => setIsMobile(event.matches)

    setIsMobile(mediaQuery.matches)
    mediaQuery.addEventListener('change', handleChange)

    return () => mediaQuery.removeEventListener('change', handleChange)
  }, [])

  useEffect(() => {
    const host = hostRef.current

    if (!host || !placementId) {
      return undefined
    }

    host.replaceChildren()

    const placement = document.createElement('ins')
    placement.className = 'dmm-widget-placement'
    placement.dataset.id = placementId
    placement.style.background = 'transparent'

    const script = document.createElement('script')
    script.src = 'https://widget-view.dmm.co.jp/js/placement.js'
    script.className = 'dmm-widget-scripts'
    script.dataset.id = placementId
    script.async = true

    host.append(placement, script)

    return () => {
      host.replaceChildren()
    }
  }, [placementId])

  return (
    <div
      ref={hostRef}
      className={`dmm-widget-host ${isMobile ? 'is-mobile' : 'is-desktop'}`}
    />
  )
}

function AdBanner({ slot }) {
  const ad = getAffiliateAd(slot)

  if (!ad) {
    return null
  }

  return (
    <aside className="affiliate-ad" aria-label="18歳以上向け広告">
      <span className="affiliate-ad-label">PR・18歳以上</span>
      <div className="affiliate-ad-content">
        {ad.provider === 'dmm-widget' ? (
          <DmmWidget desktopId={ad.desktopId} mobileId={ad.mobileId} />
        ) : (
          <div dangerouslySetInnerHTML={{ __html: ad.html }} />
        )}
      </div>
    </aside>
  )
}

export default AdBanner
