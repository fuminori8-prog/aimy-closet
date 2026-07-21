import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import Header from './Header'
import Footer from './Footer'

function LegalPage({ title, description, children }) {
  useEffect(() => {
    document.title = `${title}｜Aimy Closet`

    let meta = document.querySelector('meta[name="description"]')

    if (!meta) {
      meta = document.createElement('meta')
      meta.name = 'description'
      document.head.appendChild(meta)
    }

    meta.content = description
  }, [description, title])

  return (
    <div className="page">
      <Header />

      <main>
        <nav className="breadcrumb" aria-label="breadcrumb">
          <Link to="/">ホーム</Link>
          <span> &gt; </span>
          <span>{title}</span>
        </nav>

        <article className="legal-page">
          <h1>{title}</h1>
          {children}
        </article>
      </main>

      <Footer />
    </div>
  )
}

export default LegalPage
