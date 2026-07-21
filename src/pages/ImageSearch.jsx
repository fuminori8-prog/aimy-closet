import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import '../App.css'
import Header from '../components/Header'
import Footer from '../components/Footer'
import GachaItemCard from '../components/GachaItemCard'
import { getAllItems } from '../utils/items'
import { MAIN_CATEGORIES } from '../utils/itemCategory'
import {
  createQueryDescriptor,
  findSimilarItems,
} from '../utils/imageSearch'

const MIN_SELECTION_SIZE = 24

function normalizeRect(start, end) {
  return {
    x: Math.min(start.x, end.x),
    y: Math.min(start.y, end.y),
    width: Math.abs(end.x - start.x),
    height: Math.abs(end.y - start.y),
  }
}

function ImageSearch() {
  const allItems = useMemo(() => getAllItems(), [])
  const canvasRef = useRef(null)
  const previewCanvasRef = useRef(null)
  const imageRef = useRef(null)
  const dragStartRef = useRef(null)
  const [fileName, setFileName] = useState('')
  const [selectedCategory, setSelectedCategory] = useState('服')
  const [selection, setSelection] = useState(null)
  const [dragging, setDragging] = useState(false)
  const [results, setResults] = useState([])
  const [progress, setProgress] = useState(null)
  const [error, setError] = useState('')
  const [isSearching, setIsSearching] = useState(false)

  useEffect(() => {
    document.title = '画像からアイテムを探す｜Aimy Closet'

    let meta = document.querySelector('meta[name="description"]')

    if (!meta) {
      meta = document.createElement('meta')
      meta.name = 'description'
      document.head.appendChild(meta)
    }

    meta.content =
      'Aimyのスクリーンショットから、服・髪型・アクセサリーなどの似ているアイテムを画像で検索できます。画像は端末内で比較され、サーバーへ送信されません。'
  }, [])

  const drawCanvas = (nextSelection = selection) => {
    const canvas = canvasRef.current
    const image = imageRef.current

    if (!canvas || !image) {
      return
    }

    const maxWidth = 900
    const maxHeight = 600
    const scale = Math.min(
      1,
      maxWidth / image.naturalWidth,
      maxHeight / image.naturalHeight,
    )

    const displayWidth = Math.max(1, Math.round(image.naturalWidth * scale))
    const displayHeight = Math.max(1, Math.round(image.naturalHeight * scale))

    if (canvas.width !== displayWidth || canvas.height !== displayHeight) {
      canvas.width = displayWidth
      canvas.height = displayHeight
    }

    const context = canvas.getContext('2d')
    context.clearRect(0, 0, canvas.width, canvas.height)
    context.drawImage(image, 0, 0, canvas.width, canvas.height)

    if (nextSelection) {
      context.save()
      context.fillStyle = 'rgba(37, 27, 42, 0.48)'
      context.fillRect(0, 0, canvas.width, canvas.height)
      context.clearRect(
        nextSelection.x,
        nextSelection.y,
        nextSelection.width,
        nextSelection.height,
      )
      context.drawImage(
        image,
        nextSelection.x / scale,
        nextSelection.y / scale,
        nextSelection.width / scale,
        nextSelection.height / scale,
        nextSelection.x,
        nextSelection.y,
        nextSelection.width,
        nextSelection.height,
      )
      context.strokeStyle = '#ec5f98'
      context.lineWidth = 3
      context.setLineDash([9, 6])
      context.strokeRect(
        nextSelection.x + 1.5,
        nextSelection.y + 1.5,
        Math.max(0, nextSelection.width - 3),
        Math.max(0, nextSelection.height - 3),
      )
      context.restore()
    }
  }

  const drawPreview = (nextSelection = selection) => {
    const canvas = canvasRef.current
    const preview = previewCanvasRef.current

    if (!canvas || !preview || !nextSelection) {
      return
    }

    const size = 220
    preview.width = size
    preview.height = size
    const context = preview.getContext('2d')
    context.fillStyle = '#ffffff'
    context.fillRect(0, 0, size, size)
    context.drawImage(
      canvas,
      nextSelection.x,
      nextSelection.y,
      nextSelection.width,
      nextSelection.height,
      0,
      0,
      size,
      size,
    )
  }

  useEffect(() => {
    drawCanvas(selection)
    drawPreview(selection)
  }, [selection])

  const handleFile = (file) => {
    if (!file) {
      return
    }

    if (!file.type.startsWith('image/')) {
      setError('画像ファイルを選んでください。')
      return
    }

    setError('')
    setResults([])
    setProgress(null)
    setFileName(file.name)

    const objectUrl = URL.createObjectURL(file)
    const image = new Image()

    image.onload = () => {
      URL.revokeObjectURL(objectUrl)
      imageRef.current = image

      const maxWidth = 900
      const maxHeight = 600
      const scale = Math.min(
        1,
        maxWidth / image.naturalWidth,
        maxHeight / image.naturalHeight,
      )
      const width = image.naturalWidth * scale
      const height = image.naturalHeight * scale
      const aspectRatio = width / height
      let initialSelection

      if (aspectRatio >= 0.8 && aspectRatio <= 1.25) {
        const inset = Math.min(width, height) * 0.02
        initialSelection = {
          x: inset,
          y: inset,
          width: width - inset * 2,
          height: height - inset * 2,
        }
      } else {
        const selectionSize = Math.min(width, height) * 0.62
        initialSelection = {
          x: (width - selectionSize) / 2,
          y: (height - selectionSize) / 2,
          width: selectionSize,
          height: selectionSize,
        }
      }

      setSelection(initialSelection)
      requestAnimationFrame(() => drawCanvas(initialSelection))
    }

    image.onerror = () => {
      URL.revokeObjectURL(objectUrl)
      setError('画像を読み込めませんでした。別の画像を選んでください。')
    }

    image.src = objectUrl
  }

  const getCanvasPoint = (event) => {
    const canvas = canvasRef.current
    const rect = canvas.getBoundingClientRect()
    const scaleX = canvas.width / rect.width
    const scaleY = canvas.height / rect.height

    return {
      x: Math.max(0, Math.min(canvas.width, (event.clientX - rect.left) * scaleX)),
      y: Math.max(0, Math.min(canvas.height, (event.clientY - rect.top) * scaleY)),
    }
  }

  const handlePointerDown = (event) => {
    if (!imageRef.current) {
      return
    }

    event.currentTarget.setPointerCapture(event.pointerId)
    const point = getCanvasPoint(event)
    dragStartRef.current = point
    setDragging(true)
    setSelection({ x: point.x, y: point.y, width: 1, height: 1 })
    setResults([])
  }

  const handlePointerMove = (event) => {
    if (!dragging || !dragStartRef.current) {
      return
    }

    const nextSelection = normalizeRect(
      dragStartRef.current,
      getCanvasPoint(event),
    )
    setSelection(nextSelection)
  }

  const handlePointerUp = (event) => {
    if (!dragging || !dragStartRef.current) {
      return
    }

    const nextSelection = normalizeRect(
      dragStartRef.current,
      getCanvasPoint(event),
    )
    setDragging(false)
    dragStartRef.current = null

    if (
      nextSelection.width < MIN_SELECTION_SIZE ||
      nextSelection.height < MIN_SELECTION_SIZE
    ) {
      setError('探したいアイテムを、もう少し大きく囲んでください。')
      return
    }

    setError('')
    setSelection(nextSelection)
  }

  const handleSearch = async () => {
    const image = imageRef.current
    const canvas = canvasRef.current

    if (!image || !canvas || !selection) {
      setError('先に画像を選び、探したいアイテムを囲んでください。')
      return
    }

    if (
      selection.width < MIN_SELECTION_SIZE ||
      selection.height < MIN_SELECTION_SIZE
    ) {
      setError('探したいアイテムを、もう少し大きく囲んでください。')
      return
    }

    setError('')
    setResults([])
    setIsSearching(true)
    setProgress({ current: 0, total: 0 })

    try {
      const scaleX = image.naturalWidth / canvas.width
      const scaleY = image.naturalHeight / canvas.height
      const sourceCrop = {
        x: selection.x * scaleX,
        y: selection.y * scaleY,
        width: selection.width * scaleX,
        height: selection.height * scaleY,
      }
      const descriptor = createQueryDescriptor(image, sourceCrop)
      const candidates = allItems.filter(
        (item) => item.normalizedCategory === selectedCategory,
      )
      const matches = await findSimilarItems({
        descriptor,
        items: candidates,
        limit: 8,
        onProgress: (current, total) => setProgress({ current, total }),
      })

      setResults(matches)

      if (matches.length === 0) {
        setError('比較できるアイテム画像がありませんでした。')
      }
    } catch (searchError) {
      console.error(searchError)
      setError('画像検索に失敗しました。画像を選び直して再度お試しください。')
    } finally {
      setIsSearching(false)
    }
  }

  return (
    <div className="page">
      <Header />

      <main>
        <nav className="breadcrumb" aria-label="breadcrumb">
          <Link to="/">ホーム</Link>
          <span> &gt; </span>
          <span>画像から探す</span>
        </nav>

        <section className="image-search-page">
          <div className="item-list-intro">
            <h1>画像からアイテムを探す</h1>
            <p>
              スクショを選び、探したいアイテムを指で囲むと、似ている候補を表示します。
            </p>
          </div>

          <div className="image-search-privacy">
            🔒 選んだ画像は端末内で比較し、サーバーには送信しません。
          </div>

          <div className="image-search-controls card">
            <label className="image-search-field">
              <span>1．カテゴリを選択</span>
              <select
                value={selectedCategory}
                onChange={(event) => {
                  setSelectedCategory(event.target.value)
                  setResults([])
                }}
              >
                {MAIN_CATEGORIES.map((category) => (
                  <option key={category} value={category}>
                    {category}
                  </option>
                ))}
              </select>
            </label>

            <label className="image-upload-button">
              <span>2．スクショ・画像を選択</span>
              <input
                type="file"
                accept="image/*"
                onChange={(event) => handleFile(event.target.files?.[0])}
              />
            </label>

            {fileName ? <p className="selected-file-name">{fileName}</p> : null}
          </div>

          {imageRef.current ? (
            <div className="image-crop-layout">
              <section className="image-crop-area">
                <h2>3．探したいアイテムを囲む</h2>
                <p>画像上を指またはマウスで、左上から右下へなぞってください。</p>
                <canvas
                  ref={canvasRef}
                  className="image-crop-canvas"
                  onPointerDown={handlePointerDown}
                  onPointerMove={handlePointerMove}
                  onPointerUp={handlePointerUp}
                  onPointerCancel={handlePointerUp}
                />
              </section>

              <aside className="image-crop-preview card">
                <h2>検索する範囲</h2>
                <canvas ref={previewCanvasRef} />
                <button
                  type="button"
                  className="image-search-submit"
                  onClick={handleSearch}
                  disabled={isSearching}
                >
                  {isSearching ? '比較中…' : 'この画像で探す'}
                </button>

                {progress && isSearching ? (
                  <div className="image-search-progress" aria-live="polite">
                    <span>
                      {progress.current} / {progress.total || '…'}件
                    </span>
                    <progress
                      value={progress.current}
                      max={Math.max(progress.total, 1)}
                    />
                  </div>
                ) : null}
              </aside>
            </div>
          ) : null}

          {error ? (
            <p className="image-search-error" role="alert">
              {error}
            </p>
          ) : null}

          {results.length > 0 ? (
            <section className="image-search-results" aria-live="polite">
              <div className="image-search-results-heading">
                <h2>似ているアイテム候補</h2>
                <p>一致度は参考値です。画像を見て候補を確認してください。</p>
              </div>

              <div className="card-grid item-grid">
                {results.map(({ item, rank, similarity }) => {
                  const categoryLabel = item.subCategory
                    ? `${item.normalizedCategory}：${item.subCategory}`
                    : item.normalizedCategory

                  return (
                    <div className="image-search-result" key={item.id}>
                      <div className="image-search-rank">
                        候補{rank}・一致度 {similarity}%
                      </div>
                      <GachaItemCard
                        item={{ ...item, category: categoryLabel }}
                        subtext={`ガチャ: ${item.gachaTitle}`}
                      />
                    </div>
                  )
                })}
              </div>
            </section>
          ) : null}
        </section>
      </main>

      <Footer />
    </div>
  )
}

export default ImageSearch
