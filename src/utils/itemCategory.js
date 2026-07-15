export const MAIN_CATEGORIES = [
  '服',
  '髪型',
  'アクセサリー',
  'パーツ',
  '背景',
]

export const CATEGORY_ICONS = {
  服: '👗',
  髪型: '💇',
  アクセサリー: '🎀',
  パーツ: '✨',
  背景: '🌈',
}

export function getMainCategory(category) {
  const value = String(category || '').trim()

  if (['服', '衣装'].includes(value)) {
    return '服'
  }

  if (['髪', '髪型'].includes(value)) {
    return '髪型'
  }

  if (
    [
      'アクセサリー',
      'アクセ',
      'あたま',
      '髪飾り',
      'めがね',
      'メガネ',
      'ピアス',
      '耳飾り',
    ].includes(value)
  ) {
    return 'アクセサリー'
  }

  if (
    [
      'パーツ',
      'メイク',
      '目',
      '口',
      '鼻',
      'まゆげ',
      '眉毛',
    ].includes(value)
  ) {
    return 'パーツ'
  }

  if (value === '背景') {
    return '背景'
  }

  return 'その他'
}

export function getSubCategory(category) {
  const value = String(category || '').trim()

  if (['あたま', '髪飾り'].includes(value)) {
    return 'あたま'
  }

  if (['めがね', 'メガネ'].includes(value)) {
    return 'めがね'
  }

  if (['ピアス', '耳飾り'].includes(value)) {
    return 'ピアス'
  }

  if (['メイク', '目', '口', '鼻', 'まゆげ', '眉毛'].includes(value)) {
    return value === '眉毛' ? 'まゆげ' : value
  }

  return ''
}