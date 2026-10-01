import { readFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { historicalItems } from '../src/data/historicalItems.js'

const project = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

async function read(relativePath) {
  return readFile(path.join(project, relativePath), 'utf8')
}

function capture(html, pattern, label) {
  const match = html.match(pattern)

  if (!match) {
    throw new Error(`${label}を生成HTMLから確認できませんでした`)
  }

  return match[1]
}

const [home, item, insights, itemFinder, dailyTasks, historical, sitemap] =
  await Promise.all([
    read('dist/index.html'),
    read('dist/item.html'),
    read('dist/insights.html'),
    read('dist/guides/item-finder.html'),
    read('dist/guides/daily-tasks.html'),
    read('dist/historical-items.html'),
    read('dist/sitemap.xml'),
  ])

if (!dailyTasks.includes('【Aimy攻略】デイリータスク完全ガイド')) {
  throw new Error('デイリー攻略記事のタイトルを生成HTMLから確認できません')
}

if ((dailyTasks.match(/images\/guides\/aimy-daily-tasks\//g) || []).length < 8) {
  throw new Error('デイリー攻略記事の手順画像が不足しています')
}

if (!dailyTasks.includes('今日のテーマ投稿報酬') || !dailyTasks.includes('オールビンゴ報酬')) {
  throw new Error('テーマ投稿報酬とビンゴ報酬の区別を生成HTMLから確認できません')
}

if (!dailyTasks.includes('ガチャチケット2枚') || !dailyTasks.includes('ジェム100個')) {
  throw new Error('デイリー攻略記事の合計報酬が正しくありません')
}

if (!sitemap.includes('/guides/daily-tasks')) {
  throw new Error('デイリー攻略記事がサイトマップに含まれていません')
}

const counts = {
  top: capture(home, /固有アイテム(\d+)件/, 'TOPのアイテム件数'),
  item: capture(item, /固有アイテム(\d+)件/, '図鑑のアイテム件数'),
  insights: capture(
    insights,
    /固有アイテム<\/strong><\/dt><dd>(\d+)件/,
    '分析ページのアイテム件数',
  ),
  itemFinder: capture(
    itemFinder,
    /全(\d+)件から候補/,
    '探し方ページのアイテム件数',
  ),
}

if (new Set(Object.values(counts)).size !== 1) {
  throw new Error(`ページ間でアイテム件数が一致しません: ${JSON.stringify(counts)}`)
}

if (!/データ最終更新:<\/strong> 20\d{2}年\d{1,2}月\d{1,2}日/.test(insights)) {
  throw new Error('分析ページのデータ最終更新日が自動生成されていません')
}

if (historicalItems.length === 0) {
  if (sitemap.includes('/historical-items')) {
    throw new Error('空の過去アイテムページがサイトマップに含まれています')
  }

  if (!historical.includes('noindex,follow')) {
    throw new Error('空の過去アイテムページにnoindexがありません')
  }
}

console.log(`生成内容を検証しました: アイテム${counts.top}件・ページ間一致`)
