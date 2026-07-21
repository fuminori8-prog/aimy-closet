const descriptorCache = new Map()

const ANALYSIS_SIZE = 160
const SAMPLE_SIZE = 48
const PIXEL_STEP = 2
const HASH_WIDTH = 17
const HASH_HEIGHT = 16
const RGB_BINS = 4
const HOG_CELLS = 4
const HOG_BINS = 8

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value))
}

function createCanvas(width, height) {
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  return canvas
}

function getSourceSize(source) {
  return {
    width: source.naturalWidth || source.videoWidth || source.width,
    height: source.naturalHeight || source.videoHeight || source.height,
  }
}

function resolveCrop(source, crop = null) {
  const { width: sourceWidth, height: sourceHeight } = getSourceSize(source)
  const x = crop ? clamp(crop.x, 0, sourceWidth - 1) : 0
  const y = crop ? clamp(crop.y, 0, sourceHeight - 1) : 0
  const width = crop
    ? clamp(crop.width, 1, sourceWidth - x)
    : sourceWidth
  const height = crop
    ? clamp(crop.height, 1, sourceHeight - y)
    : sourceHeight

  return { x, y, width, height }
}

function insetCrop(crop, ratio) {
  const insetX = crop.width * ratio
  const insetY = crop.height * ratio

  return {
    x: crop.x + insetX,
    y: crop.y + insetY,
    width: Math.max(1, crop.width - insetX * 2),
    height: Math.max(1, crop.height - insetY * 2),
  }
}

function drawContained(context, source, sourceCrop, targetRect, mode = 'contain') {
  const sourceRatio = sourceCrop.width / sourceCrop.height
  const targetRatio = targetRect.width / targetRect.height
  let sx = sourceCrop.x
  let sy = sourceCrop.y
  let sw = sourceCrop.width
  let sh = sourceCrop.height
  let dx = targetRect.x
  let dy = targetRect.y
  let dw = targetRect.width
  let dh = targetRect.height

  if (mode === 'cover') {
    if (sourceRatio > targetRatio) {
      sw = sourceCrop.height * targetRatio
      sx = sourceCrop.x + (sourceCrop.width - sw) / 2
    } else {
      sh = sourceCrop.width / targetRatio
      sy = sourceCrop.y + (sourceCrop.height - sh) / 2
    }
  } else if (sourceRatio > targetRatio) {
    dh = targetRect.width / sourceRatio
    dy = targetRect.y + (targetRect.height - dh) / 2
  } else {
    dw = targetRect.height * sourceRatio
    dx = targetRect.x + (targetRect.width - dw) / 2
  }

  context.drawImage(source, sx, sy, sw, sh, dx, dy, dw, dh)
}

function median(values) {
  if (values.length === 0) {
    return 255
  }

  values.sort((left, right) => left - right)
  return values[Math.floor(values.length / 2)]
}

function estimateBackground(imageData) {
  const { data, width, height } = imageData
  const red = []
  const green = []
  const blue = []
  const border = Math.max(2, Math.round(Math.min(width, height) * 0.08))

  for (let y = 0; y < height; y += 2) {
    for (let x = 0; x < width; x += 2) {
      if (
        x > border &&
        x < width - border &&
        y > border &&
        y < height - border
      ) {
        continue
      }

      const index = (y * width + x) * 4
      red.push(data[index])
      green.push(data[index + 1])
      blue.push(data[index + 2])
    }
  }

  return {
    r: median(red),
    g: median(green),
    b: median(blue),
  }
}

function createAnalysisCanvas(source, crop = null, { catalog = false } = {}) {
  const canvas = createCanvas(ANALYSIS_SIZE, ANALYSIS_SIZE)
  const context = canvas.getContext('2d', {
    alpha: false,
    willReadFrequently: true,
  })

  if (!context) {
    throw new Error('画像を解析できるブラウザ環境ではありません。')
  }

  context.imageSmoothingEnabled = true
  context.imageSmoothingQuality = 'high'
  context.fillStyle = '#ffffff'
  context.fillRect(0, 0, ANALYSIS_SIZE, ANALYSIS_SIZE)

  const resolved = catalog
    ? insetCrop(resolveCrop(source, crop), 0.055)
    : resolveCrop(source, crop)

  drawContained(
    context,
    source,
    resolved,
    { x: 0, y: 0, width: ANALYSIS_SIZE, height: ANALYSIS_SIZE },
    'contain',
  )

  if (catalog) {
    const imageData = context.getImageData(0, 0, ANALYSIS_SIZE, ANALYSIS_SIZE)
    const background = estimateBackground(imageData)
    context.fillStyle = `rgb(${background.r}, ${background.g}, ${background.b})`

    // アイテム画像に写り込むレアリティ文字を比較対象から外す。
    context.fillRect(
      Math.round(ANALYSIS_SIZE * 0.72),
      0,
      Math.round(ANALYSIS_SIZE * 0.28),
      Math.round(ANALYSIS_SIZE * 0.21),
    )
  }

  return canvas
}

function findForegroundBounds(canvas) {
  const context = canvas.getContext('2d', { willReadFrequently: true })
  const imageData = context.getImageData(0, 0, canvas.width, canvas.height)
  const { data, width, height } = imageData
  const background = estimateBackground(imageData)
  let minX = width
  let minY = height
  let maxX = -1
  let maxY = -1
  let foregroundCount = 0

  for (let y = 1; y < height - 1; y += 1) {
    for (let x = 1; x < width - 1; x += 1) {
      const index = (y * width + x) * 4
      const dr = data[index] - background.r
      const dg = data[index + 1] - background.g
      const db = data[index + 2] - background.b
      const distance = Math.sqrt(dr * dr + dg * dg + db * db)
      const maxChannel = Math.max(data[index], data[index + 1], data[index + 2])
      const minChannel = Math.min(data[index], data[index + 1], data[index + 2])
      const saturation = maxChannel === 0 ? 0 : (maxChannel - minChannel) / maxChannel
      const foreground = distance > 30 || saturation > 0.2

      if (!foreground) {
        continue
      }

      foregroundCount += 1
      minX = Math.min(minX, x)
      minY = Math.min(minY, y)
      maxX = Math.max(maxX, x)
      maxY = Math.max(maxY, y)
    }
  }

  if (foregroundCount < width * height * 0.015 || maxX < minX || maxY < minY) {
    return null
  }

  const detectedWidth = maxX - minX + 1
  const detectedHeight = maxY - minY + 1
  const coverage = (detectedWidth * detectedHeight) / (width * height)

  if (coverage > 0.92) {
    return null
  }

  const paddingX = Math.max(3, detectedWidth * 0.08)
  const paddingY = Math.max(3, detectedHeight * 0.08)

  return {
    x: clamp(minX - paddingX, 0, width - 1),
    y: clamp(minY - paddingY, 0, height - 1),
    width: clamp(detectedWidth + paddingX * 2, 1, width - minX + paddingX),
    height: clamp(detectedHeight + paddingY * 2, 1, height - minY + paddingY),
  }
}

function normalizeCrop(crop, canvas) {
  const x = clamp(crop.x, 0, canvas.width - 1)
  const y = clamp(crop.y, 0, canvas.height - 1)

  return {
    x,
    y,
    width: clamp(crop.width, 1, canvas.width - x),
    height: clamp(crop.height, 1, canvas.height - y),
  }
}

function createPreparedCanvas(analysisCanvas, crop, mode) {
  const canvas = createCanvas(SAMPLE_SIZE, SAMPLE_SIZE)
  const context = canvas.getContext('2d', {
    alpha: false,
    willReadFrequently: true,
  })

  if (!context) {
    throw new Error('画像を解析できるブラウザ環境ではありません。')
  }

  context.imageSmoothingEnabled = true
  context.imageSmoothingQuality = 'high'
  context.fillStyle = '#ffffff'
  context.fillRect(0, 0, SAMPLE_SIZE, SAMPLE_SIZE)

  drawContained(
    context,
    analysisCanvas,
    normalizeCrop(crop, analysisCanvas),
    { x: 0, y: 0, width: SAMPLE_SIZE, height: SAMPLE_SIZE },
    mode,
  )

  return canvas
}

function createSpatialPixels(data) {
  const sampleWidth = SAMPLE_SIZE / PIXEL_STEP
  const values = new Float32Array(sampleWidth * sampleWidth * 3)
  const means = [0, 0, 0]
  const deviations = [0, 0, 0]
  let pixelCount = 0

  for (let y = 0; y < SAMPLE_SIZE; y += PIXEL_STEP) {
    for (let x = 0; x < SAMPLE_SIZE; x += PIXEL_STEP) {
      const index = (y * SAMPLE_SIZE + x) * 4
      means[0] += data[index]
      means[1] += data[index + 1]
      means[2] += data[index + 2]
      pixelCount += 1
    }
  }

  for (let channel = 0; channel < 3; channel += 1) {
    means[channel] /= pixelCount
  }

  for (let y = 0; y < SAMPLE_SIZE; y += PIXEL_STEP) {
    for (let x = 0; x < SAMPLE_SIZE; x += PIXEL_STEP) {
      const index = (y * SAMPLE_SIZE + x) * 4

      for (let channel = 0; channel < 3; channel += 1) {
        const difference = data[index + channel] - means[channel]
        deviations[channel] += difference * difference
      }
    }
  }

  for (let channel = 0; channel < 3; channel += 1) {
    deviations[channel] = Math.sqrt(deviations[channel] / pixelCount) || 1
  }

  let outputIndex = 0

  for (let y = 0; y < SAMPLE_SIZE; y += PIXEL_STEP) {
    for (let x = 0; x < SAMPLE_SIZE; x += PIXEL_STEP) {
      const index = (y * SAMPLE_SIZE + x) * 4

      for (let channel = 0; channel < 3; channel += 1) {
        values[outputIndex] =
          (data[index + channel] - means[channel]) / deviations[channel]
        outputIndex += 1
      }
    }
  }

  return values
}

function createHistogram(data) {
  const binCount = RGB_BINS ** 3
  const histogram = new Float32Array(binCount)
  let totalWeight = 0

  for (let index = 0; index < data.length; index += 4) {
    const red = data[index]
    const green = data[index + 1]
    const blue = data[index + 2]
    const maximum = Math.max(red, green, blue)
    const minimum = Math.min(red, green, blue)
    const saturation = maximum === 0 ? 0 : (maximum - minimum) / maximum
    const brightness = (red + green + blue) / 3
    const weight = brightness > 246 && saturation < 0.04 ? 0.2 : 1
    const r = Math.min(RGB_BINS - 1, Math.floor((red / 256) * RGB_BINS))
    const g = Math.min(RGB_BINS - 1, Math.floor((green / 256) * RGB_BINS))
    const b = Math.min(RGB_BINS - 1, Math.floor((blue / 256) * RGB_BINS))
    const bin = r * RGB_BINS ** 2 + g * RGB_BINS + b
    histogram[bin] += weight
    totalWeight += weight
  }

  for (let index = 0; index < histogram.length; index += 1) {
    histogram[index] /= totalWeight || 1
  }

  return histogram
}

function createEdgeFeatures(data) {
  const grayscale = new Float32Array(SAMPLE_SIZE * SAMPLE_SIZE)

  for (let index = 0; index < grayscale.length; index += 1) {
    const sourceIndex = index * 4
    grayscale[index] =
      data[sourceIndex] * 0.299 +
      data[sourceIndex + 1] * 0.587 +
      data[sourceIndex + 2] * 0.114
  }

  const edgeSize = 12
  const edgeGrid = new Float32Array(edgeSize * edgeSize)
  const hog = new Float32Array(HOG_CELLS * HOG_CELLS * HOG_BINS)
  let edgeTotal = 0

  for (let y = 1; y < SAMPLE_SIZE - 1; y += 1) {
    for (let x = 1; x < SAMPLE_SIZE - 1; x += 1) {
      const topLeft = grayscale[(y - 1) * SAMPLE_SIZE + x - 1]
      const top = grayscale[(y - 1) * SAMPLE_SIZE + x]
      const topRight = grayscale[(y - 1) * SAMPLE_SIZE + x + 1]
      const left = grayscale[y * SAMPLE_SIZE + x - 1]
      const right = grayscale[y * SAMPLE_SIZE + x + 1]
      const bottomLeft = grayscale[(y + 1) * SAMPLE_SIZE + x - 1]
      const bottom = grayscale[(y + 1) * SAMPLE_SIZE + x]
      const bottomRight = grayscale[(y + 1) * SAMPLE_SIZE + x + 1]
      const gx = -topLeft + topRight - 2 * left + 2 * right - bottomLeft + bottomRight
      const gy = -topLeft - 2 * top - topRight + bottomLeft + 2 * bottom + bottomRight
      const magnitude = Math.sqrt(gx * gx + gy * gy)
      const edgeX = Math.min(edgeSize - 1, Math.floor((x / SAMPLE_SIZE) * edgeSize))
      const edgeY = Math.min(edgeSize - 1, Math.floor((y / SAMPLE_SIZE) * edgeSize))
      edgeGrid[edgeY * edgeSize + edgeX] += magnitude
      edgeTotal += magnitude

      let angle = Math.atan2(gy, gx)
      if (angle < 0) {
        angle += Math.PI
      }
      if (angle >= Math.PI) {
        angle -= Math.PI
      }

      const cellX = Math.min(HOG_CELLS - 1, Math.floor((x / SAMPLE_SIZE) * HOG_CELLS))
      const cellY = Math.min(HOG_CELLS - 1, Math.floor((y / SAMPLE_SIZE) * HOG_CELLS))
      const angleBin = Math.min(HOG_BINS - 1, Math.floor((angle / Math.PI) * HOG_BINS))
      const hogIndex = (cellY * HOG_CELLS + cellX) * HOG_BINS + angleBin
      hog[hogIndex] += magnitude
    }
  }

  for (let index = 0; index < edgeGrid.length; index += 1) {
    edgeGrid[index] /= edgeTotal || 1
  }

  for (let cell = 0; cell < HOG_CELLS * HOG_CELLS; cell += 1) {
    const offset = cell * HOG_BINS
    let norm = 0

    for (let bin = 0; bin < HOG_BINS; bin += 1) {
      norm += hog[offset + bin] * hog[offset + bin]
    }

    norm = Math.sqrt(norm) || 1

    for (let bin = 0; bin < HOG_BINS; bin += 1) {
      hog[offset + bin] /= norm
    }
  }

  return { edgeGrid, hog }
}

function createDifferenceHash(canvas) {
  const hashCanvas = createCanvas(HASH_WIDTH, HASH_HEIGHT)
  const context = hashCanvas.getContext('2d', {
    alpha: false,
    willReadFrequently: true,
  })

  context.drawImage(canvas, 0, 0, HASH_WIDTH, HASH_HEIGHT)
  const data = context.getImageData(0, 0, HASH_WIDTH, HASH_HEIGHT).data
  const hash = new Uint8Array((HASH_WIDTH - 1) * HASH_HEIGHT)

  for (let y = 0; y < HASH_HEIGHT; y += 1) {
    for (let x = 0; x < HASH_WIDTH - 1; x += 1) {
      const leftIndex = (y * HASH_WIDTH + x) * 4
      const rightIndex = leftIndex + 4
      const left =
        data[leftIndex] * 0.299 +
        data[leftIndex + 1] * 0.587 +
        data[leftIndex + 2] * 0.114
      const right =
        data[rightIndex] * 0.299 +
        data[rightIndex + 1] * 0.587 +
        data[rightIndex + 2] * 0.114

      hash[y * (HASH_WIDTH - 1) + x] = left > right ? 1 : 0
    }
  }

  return hash
}

function createDescriptor(preparedCanvas) {
  const context = preparedCanvas.getContext('2d', { willReadFrequently: true })
  const imageData = context.getImageData(0, 0, SAMPLE_SIZE, SAMPLE_SIZE)
  const edges = createEdgeFeatures(imageData.data)

  return {
    pixels: createSpatialPixels(imageData.data),
    histogram: createHistogram(imageData.data),
    edgeGrid: edges.edgeGrid,
    hog: edges.hog,
    hash: createDifferenceHash(preparedCanvas),
  }
}

function addDescriptor(descriptors, analysisCanvas, crop, mode) {
  const normalized = normalizeCrop(crop, analysisCanvas)
  const key = [
    Math.round(normalized.x),
    Math.round(normalized.y),
    Math.round(normalized.width),
    Math.round(normalized.height),
    mode,
  ].join(':')

  if (descriptors.some((entry) => entry.key === key)) {
    return
  }

  descriptors.push({
    key,
    descriptor: createDescriptor(createPreparedCanvas(analysisCanvas, normalized, mode)),
  })
}

function buildDescriptorSet(source, crop, options = {}) {
  const analysisCanvas = createAnalysisCanvas(source, crop, options)
  const descriptors = []
  const full = {
    x: 0,
    y: 0,
    width: analysisCanvas.width,
    height: analysisCanvas.height,
  }
  const focus = findForegroundBounds(analysisCanvas)
  const base = focus || full

  addDescriptor(descriptors, analysisCanvas, full, 'contain')
  addDescriptor(descriptors, analysisCanvas, base, 'contain')
  addDescriptor(descriptors, analysisCanvas, base, 'cover')

  const subCategory = String(options.subCategory || '')

  if (subCategory === '目') {
    const eyeBand = {
      x: base.x,
      y: base.y + base.height * 0.12,
      width: base.width,
      height: base.height * 0.56,
    }
    addDescriptor(descriptors, analysisCanvas, eyeBand, 'contain')
    addDescriptor(
      descriptors,
      analysisCanvas,
      { ...eyeBand, width: eyeBand.width * 0.58 },
      'contain',
    )
    addDescriptor(
      descriptors,
      analysisCanvas,
      {
        ...eyeBand,
        x: eyeBand.x + eyeBand.width * 0.42,
        width: eyeBand.width * 0.58,
      },
      'contain',
    )
  }

  if (['メイク', '口', '鼻', 'まゆげ'].includes(subCategory)) {
    addDescriptor(
      descriptors,
      analysisCanvas,
      {
        x: base.x + base.width * 0.08,
        y: base.y + base.height * 0.18,
        width: base.width * 0.84,
        height: base.height * 0.72,
      },
      'contain',
    )
  }

  return descriptors.map((entry) => entry.descriptor)
}

function vectorDistance(left, right, divisor = 1) {
  let total = 0

  for (let index = 0; index < left.length; index += 1) {
    total += Math.abs(left[index] - right[index])
  }

  return Math.min(1, total / left.length / divisor)
}

function histogramDistance(left, right) {
  let overlap = 0

  for (let index = 0; index < left.length; index += 1) {
    overlap += Math.min(left[index], right[index])
  }

  return clamp(1 - overlap, 0, 1)
}

function cosineDistance(left, right) {
  let dot = 0
  let leftNorm = 0
  let rightNorm = 0

  for (let index = 0; index < left.length; index += 1) {
    dot += left[index] * right[index]
    leftNorm += left[index] * left[index]
    rightNorm += right[index] * right[index]
  }

  const denominator = Math.sqrt(leftNorm * rightNorm)
  return denominator ? clamp(1 - dot / denominator, 0, 1) : 1
}

function hashDistance(left, right) {
  let differences = 0

  for (let index = 0; index < left.length; index += 1) {
    if (left[index] !== right[index]) {
      differences += 1
    }
  }

  return differences / left.length
}

function descriptorDistance(left, right) {
  const pixels = vectorDistance(left.pixels, right.pixels, 2.5)
  const histogram = histogramDistance(left.histogram, right.histogram)
  const edges = cosineDistance(left.edgeGrid, right.edgeGrid)
  const hog = cosineDistance(left.hog, right.hog)
  const hash = hashDistance(left.hash, right.hash)

  return (
    pixels * 0.16 +
    histogram * 0.28 +
    edges * 0.2 +
    hog * 0.26 +
    hash * 0.1
  )
}

function descriptorSetDistance(leftSet, rightSet) {
  const distances = []

  leftSet.forEach((left) => {
    rightSet.forEach((right) => {
      distances.push(descriptorDistance(left, right))
    })
  })

  distances.sort((left, right) => left - right)
  const best = distances[0] ?? 1
  const second = distances[1] ?? best

  return best * 0.78 + second * 0.22
}

function loadImage(source) {
  return new Promise((resolve, reject) => {
    const image = new Image()
    image.decoding = 'async'
    image.onload = () => resolve(image)
    image.onerror = () => reject(new Error(`画像を読み込めませんでした: ${source}`))
    image.src = source
  })
}

async function getItemDescriptors(item) {
  const cacheKey = `${item.image}:${item.subCategory || ''}`

  if (descriptorCache.has(cacheKey)) {
    return descriptorCache.get(cacheKey)
  }

  const promise = loadImage(item.image).then((image) =>
    buildDescriptorSet(image, null, {
      catalog: true,
      subCategory: item.subCategory,
    }),
  )
  descriptorCache.set(cacheKey, promise)

  try {
    return await promise
  } catch (error) {
    descriptorCache.delete(cacheKey)
    throw error
  }
}

export function createQueryDescriptors(image, crop, options = {}) {
  return buildDescriptorSet(image, crop, {
    catalog: false,
    subCategory: options.subCategory,
  })
}

export async function findSimilarItems({
  descriptors,
  items,
  limit = 20,
  onProgress,
}) {
  const candidates = items.filter(
    (item) => item.image && item.image !== 'placeholder',
  )
  const results = []
  const batchSize = 8

  for (let start = 0; start < candidates.length; start += batchSize) {
    const batch = candidates.slice(start, start + batchSize)
    const compared = await Promise.all(
      batch.map(async (item) => {
        try {
          const itemDescriptors = await getItemDescriptors(item)
          return {
            item,
            distance: descriptorSetDistance(descriptors, itemDescriptors),
          }
        } catch {
          return null
        }
      }),
    )

    results.push(...compared.filter(Boolean))
    onProgress?.(Math.min(candidates.length, start + batch.length), candidates.length)
    await new Promise((resolve) => requestAnimationFrame(resolve))
  }

  return results
    .sort((left, right) => left.distance - right.distance)
    .slice(0, limit)
    .map((result, index) => ({
      ...result,
      rank: index + 1,
      similarity: Math.round(
        (1 - clamp((result.distance - 0.06) / 0.72, 0, 1)) * 100,
      ),
    }))
}
