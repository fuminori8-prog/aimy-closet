import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import './index.css'
import App from './App.jsx'
import GachaDetail from './pages/GachaDetail.jsx'
import GachaList from './pages/GachaList.jsx'
import ItemList from './pages/ItemList.jsx'
import ItemDetail from './pages/ItemDetail.jsx'
import Favorites from './pages/Favorites.jsx'
import ScrollToTop from './components/ScrollToTop'
import { FavoritesProvider } from './contexts/FavoritesContext.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <FavoritesProvider>
        <ScrollToTop />

        <Routes>
          <Route path="/" element={<App />} />
          <Route path="/item" element={<ItemList />} />
          <Route path="/item/:itemId" element={<ItemDetail />} />
          <Route path="/gacha" element={<GachaList />} />
          <Route path="/gacha/:slug" element={<GachaDetail />} />
          <Route path="/favorites" element={<Favorites />} />
        </Routes>
      </FavoritesProvider>
    </BrowserRouter>
  </StrictMode>,
)
