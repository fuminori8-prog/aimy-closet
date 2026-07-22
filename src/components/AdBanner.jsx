import { useEffect, useRef, useState } from 'react'
import { getAffiliateAd } from '../config/affiliateAds'

const MOBILE_WIDGET_QUERY = '(max-width: 840px)'

// DMMの同じ外部スクリプトを複数枠で同時実行すると、
// 読み込み対象のins要素を取り違える可能性があるため順番に実行する。
let dmmWidgetQueue = Promise.resolve()

function getInitialMobileState() {
  return (
    typeof window !== 'undefined' &&
    window.matchMedia(MOBILE_WIDGET_QUERY).matches
  )
}

function enqueueDmmWidget(host, placementId, isCancelled) {
  dmmWidgetQueue = dmmWidgetQueue
    .catch(() => undefined)
    .then(
      () =>
        new Promise((resolve) => {
          if (isCancelled() || !host.isConnected) {
            resolve()
            return
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

          // DMMが発行したタグにはasync指定がない。
          // 動的scriptも同じ実行順になるよう明示的にfalseへ戻す。
          script.async = false

          let finished = false
          const finish = () => {
            if (finished) return
            finished = true
            window.setTimeout(resolve, 250)
          }

          script.addEventListener('load', finish, { once: true })
          script.addEventListener('error', finish, { once: true })

          // DMM発行コードと同じく ins → script の順で隣接配置する。
          host.append(placement, script)

          // 外部側が応答しない場合でも後続の広告枠を止めない。
          window.setTimeout(finish, 10000)
        }),
    )
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
    let cancelled = false

    if (!host || !placementId) {
      return undefined
    }

    enqueueDmmWidget(host, placementId, () => cancelled)

    return () => {
      cancelled = true
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
