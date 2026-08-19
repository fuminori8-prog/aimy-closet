import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'

const SITE_URL = 'https://aimycloset.jp'

function getOrCreateMeta(name) {
  let meta = document.querySelector(`meta[name="${name}"]`)

  if (!meta) {
    meta = document.createElement('meta')
    meta.name = name
    document.head.appendChild(meta)
  }

  return meta
}

function getOrCreateCanonical() {
  let canonical = document.querySelector('link[rel="canonical"]')

  if (!canonical) {
    canonical = document.createElement('link')
    canonical.rel = 'canonical'
    document.head.appendChild(canonical)
  }

  return canonical
}

function RouteSeo() {
  const { pathname } = useLocation()

  useEffect(() => {
    const isItemDetail = /^\/item\/[^/]+$/.test(pathname)
    const isPrivateUtility = pathname === '/favorites'
    const robots = getOrCreateMeta('robots')
    const canonical = getOrCreateCanonical()

    robots.content = isItemDetail || isPrivateUtility
      ? 'noindex,follow'
      : 'index,follow'
    canonical.href = `${SITE_URL}${pathname === '/' ? '/' : pathname}`
  }, [pathname])

  return null
}

export default RouteSeo
