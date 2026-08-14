const GACHA_DATE_PATTERN =
  /^(\d{4})\/(\d{1,2})\/(\d{1,2})(?:\s+(\d{1,2}):(\d{2}))?$/

export function getGachaDateTimestamp(value) {
  const match = String(value || '').trim().match(GACHA_DATE_PATTERN)

  if (!match) {
    return null
  }

  const year = Number(match[1])
  const month = Number(match[2])
  const day = Number(match[3])
  const hour = Number(match[4] || 0)
  const minute = Number(match[5] || 0)

  if (
    month < 1 ||
    month > 12 ||
    day < 1 ||
    day > 31 ||
    hour < 0 ||
    hour > 23 ||
    minute < 0 ||
    minute > 59
  ) {
    return null
  }

  const timestamp = Date.UTC(year, month - 1, day, hour, minute)
  const parsed = new Date(timestamp)

  if (
    parsed.getUTCFullYear() !== year ||
    parsed.getUTCMonth() !== month - 1 ||
    parsed.getUTCDate() !== day ||
    parsed.getUTCHours() !== hour ||
    parsed.getUTCMinutes() !== minute
  ) {
    return null
  }

  return timestamp
}

function compareDateValues(leftValue, rightValue, newestFirst) {
  const left = getGachaDateTimestamp(leftValue)
  const right = getGachaDateTimestamp(rightValue)

  if (left === null && right === null) {
    return 0
  }

  if (left === null) {
    return 1
  }

  if (right === null) {
    return -1
  }

  return newestFirst ? right - left : left - right
}

export function compareGachasByStartDate(left, right) {
  const startDifference = compareDateValues(
    left?.startDate,
    right?.startDate,
    true,
  )

  if (startDifference !== 0) {
    return startDifference
  }

  return compareDateValues(left?.endDate, right?.endDate, true)
}

export function compareGachasByOldestStartDate(left, right) {
  const startDifference = compareDateValues(
    left?.startDate,
    right?.startDate,
    false,
  )

  if (startDifference !== 0) {
    return startDifference
  }

  return compareDateValues(left?.endDate, right?.endDate, false)
}
