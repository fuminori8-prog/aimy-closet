const DATE_PATTERN = /(\d{4})\/(\d{1,2})\/(\d{1,2})(?:\s+(\d{1,2}):(\d{1,2}))?/

export function parseGachaDate(value) {
  if (!value) {
    return null
  }

  const match = String(value).match(DATE_PATTERN)
  if (!match) {
    return null
  }

  const [, year, month, day, hour = '0', minute = '0'] = match
  const isoDate = `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}T${hour.padStart(2, '0')}:${minute.padStart(2, '0')}:00+09:00`
  const timestamp = Date.parse(isoDate)

  return Number.isNaN(timestamp) ? null : timestamp
}

export function getGachaEndTime(endDate) {
  const timestamp = parseGachaDate(endDate)

  if (timestamp === null) {
    return null
  }

  // 「14:59」なら14:59:59まで開催中として扱う。
  return timestamp + 60_000 - 1
}

export function getGachaStatus(gacha, currentTime = Date.now()) {
  const endTime = getGachaEndTime(gacha?.endDate)

  if (endTime !== null && currentTime > endTime) {
    return '開催終了'
  }

  return gacha?.status || '開催中'
}

export function isGachaEnded(gacha, currentTime = Date.now()) {
  return getGachaStatus(gacha, currentTime) === '開催終了'
}
