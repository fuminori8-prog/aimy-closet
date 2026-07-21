const descriptorCache = new Map()

const SAMPLE_SIZE = 32
const HASH_WIDTH = 9
const HASH_HEIGHT = 8
const HISTOGRAM_BINS = 4

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value))
}

function createCanvas(width, height) {
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  return canvas
}

function drawSourceToCanvas(source, crop = null) {
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

  const sourceWidth = source.naturalWidth || source.videoWidth || source.width
  const sourceHeight = source.naturalHeight || source.videoHeight || source.height

  const sx = crop ? clamp(crop.x, 0, sourceWidth - 1) : 0
  const sy = crop ? clamp(crop.y, 0, sourceHeight - 1) : 0
  const sw = crop
    ? clamp(crop.width, 1, sourceWidth - sx)
    : sourceWidth
  const sh = crop
    ? clamp(crop.height, 1, sourceHeight - sy)
    : sourceHeight

  context.drawImage(
    source,
    sx,
    sy,
    sw,
    sh,
    0,
    0,
    SAMPLE_SIZE,
    SAMPLE_SIZE,
  )

  return context.getImageData(0, 0, SAMPLE_SIZE, SAMPLE_SIZE)
}

function normalizePixels(data) {
  const values = new Float32Array(SAMPLE_SIZE * SAMPLE_SIZE * 3)
  const means = [0, 0, 0]
  const deviations = [0, 0, 0]
  const pixelCount = SAMPLE_SIZE * SAMPLE_SIZE

  for (let index = 0; index < pixelCount; index += 1) {
    const sourceIndex = index * 4
    for (let channel = 0; channel < 3; channel += 1) {
      means[channel] += data[sourceIndex + channel]
    }
  }

  for (let channel = 0; channel < 3; channel += 1) {
    means[channel] /= pixelCount
  }

  for (let index = 0; index < pixelCount; index += 1) {
    const sourceIndex = index * 4
    for (let channel = 0; channel < 3; channel += 1) {
      const difference = data[sourceIndex + channel] - means[channel]
      deviations[channel] += difference * difference
    }
  }

  for (let channel = 0; channel < 3; channel += 1) {
    deviations[channel] = Math.sqrt(deviations[channel] / pixelCount) || 1
  }

  for (let index = 0; index < pixelCount; index += 1) {
    const sourceIndex = index * 4
    const targetIndex = index * 3

    for (let channel = 0; channel < 3; channel += 1) {
      values[targetIndex + channel] =
        (data[sourceIndex + channel] - means[channel]) / deviations[channel]
    }
  }

  return values
}

function createHistogram(data) {
  const binCount = HISTOGRAM_BINS ** 3
  const histogram = new Float32Array(binCount)
  const pixelCount = SAMPLE_SIZE * SAMPLE_SIZE

  for (let index = 0; index < pixelCount; index += 1) {
    const sourceIndex = index * 4
    const r = Math.min(
      HISTOGRAM_BINS - 1,
      Math.floor((data[sourceIndex] / 256) * HISTOGRAM_BINS),
    )
    const g = Math.min(
      HISTOGRAM_BINS - 1,
      Math.floor((data[sourceIndex + 1] / 256) * HISTOGRAM_BINS),
    )
    const b = Math.min(
      HISTOGRAM_BINS - 1,
      Math.floor((data[sourceIndex + 2] / 256) * HISTOGRAM_BINS),
    )
    const bin = r * HISTOGRAM_BINS ** 2 + g * HISTOGRAM_BINS + b
    histogram[bin] += 1
  }

  for (let index = 0; index < histogram.length; index += 1) {
    histogram[index] /= pixelCount
  }

  return histogram
}

function createDifferenceHash(source, crop = null) {
  const canvas = createCanvas(HASH_WIDTH, HASH_HEIGHT)
  const context = canvas.getContext('2d', {
    alpha: false,
    willReadFrequently: true,
  })

  if (!context) {
    throw new Error('画像を解析できるブラウザ環境ではありません。')
  }

  const sourceWidth = source.naturalWidth || source.videoWidth || source.width
  const sourceHeight = source.naturalHeight || source.videoHeight || source.height
  const sx = crop ? clamp(crop.x, 0, sourceWidth - 1) : 0
  const sy = crop ? clamp(crop.y, 0, sourceHeight - 1) : 0
  const sw = crop
    ? clamp(crop.width, 1, sourceWidth - sx)
    : sourceWidth
  const sh = crop
    ? clamp(crop.height, 1, sourceHeight - sy)
    : sourceHeight

  context.drawImage(
    source,
    sx,
    sy,
    sw,
    sh,
    0,
    0,
    HASH_WIDTH,
    HASH_HEIGHT,
  )

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

function createDescriptor(source, crop = null) {
  const imageData = drawSourceToCanvas(source, crop)

  return {
    pixels: normalizePixels(imageData.data),
    histogram: createHistogram(imageData.data),
    hash: createDifferenceHash(source, crop),
  }
}

function pixelDistance(left, right) {
  let total = 0

  for (let index = 0; index < left.length; index += 1) {
    total += Math.abs(left[index] - right[index])
  }

  return total / left.length
}

function histogramDistance(left, right) {
  let overlap = 0

  for (let index = 0; index < left.length; index += 1) {
    overlap += Math.min(left[index], right[index])
  }

  return 1 - overlap
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
  const pixels = Math.min(1, pixelDistance(left.pixels, right.pixels) / 2.25)
  const histogram = histogramDistance(left.histogram, right.histogram)
  const hash = hashDistance(left.hash, right.hash)

  return pixels * 0.54 + histogram * 0.22 + hash * 0.24
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

async function getItemDescriptor(item) {
  if (descriptorCache.has(item.image)) {
    return descriptorCache.get(item.image)
  }

  const promise = loadImage(item.image).then((image) => createDescriptor(image))
  descriptorCache.set(item.image, promise)

  try {
    return await promise
  } catch (error) {
    descriptorCache.delete(item.image)
    throw error
  }
}

export function createQueryDescriptor(image, crop) {
  return createDescriptor(image, crop)
}

export async function findSimilarItems({
  descriptor,
  items,
  limit = 8,
  onProgress,
}) {
  const candidates = items.filter(
    (item) => item.image && item.image !== 'placeholder',
  )
  const results = []
  const batchSize = 10

  for (let start = 0; start < candidates.length; start += batchSize) {
    const batch = candidates.slice(start, start + batchSize)
    const compared = await Promise.all(
      batch.map(async (item) => {
        try {
          const itemDescriptor = await getItemDescriptor(item)
          return {
            item,
            distance: descriptorDistance(descriptor, itemDescriptor),
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
      similarity: Math.max(0, Math.round((1 - result.distance) * 100)),
    }))
}
