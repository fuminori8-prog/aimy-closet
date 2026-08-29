import { Link } from 'react-router-dom'
import LegalPage from '../components/LegalPage'
import { gachas } from '../data/gachas'
import { getSiteInsights } from '../utils/siteInsights'

const insights = getSiteInsights(gachas)
const latestRows = [...insights.datedGachas].reverse().slice(0, 10)
const reprintRows = insights.datedGachas
  .filter((gacha) => gacha.returningItems > 0 || gacha.title.includes('復刻'))
  .reverse()
  .slice(0, 12)

function StatGrid() {
  return (
    <dl className="insight-stat-grid">
      <div><dt>開催日を確認できたガチャ</dt><dd>{insights.datedGachas.length}件</dd></div>
      <div><dt>図鑑上の固有アイテム</dt><dd>{insights.uniqueItemCount}件</dd></div>
      <div><dt>追加間隔の中央値</dt><dd>{insights.medianIntervalDays ?? '—'}日</dd></div>
      <div><dt>追加間隔の平均</dt><dd>{insights.averageIntervalDays ?? '—'}日</dd></div>
    </dl>
  )
}

function Insights() {
  return (
    <LegalPage title="Aimyデータ分析" description="Aimy Closetの収集データから、ガチャ追加間隔、開催期間、復刻収録を集計した独自分析です。">
      <p>掲載済みデータを眺めるだけでなく、開始日時と収録アイテムを同じ基準で集計し、追加ペースや復刻の傾向を確認できるようにしました。数値はサイト内データの更新と同時に再計算されます。</p>
      <StatGrid />
      <section className="legal-section">
        <h2>分析メニュー</h2>
        <ul className="insight-link-list">
          <li><Link to="/guides/gacha-cycle">ガチャ追加ペースと開催期間</Link></li>
          <li><Link to="/guides/reprints">復刻アイテムの数え方と確認結果</Link></li>
          <li><Link to="/guides/image-search">画像検索の判定方法と精度を上げる手順</Link></li>
        </ul>
      </section>
      <section className="legal-section">
        <h2>集計の前提</h2>
        <p>同じslugの重複ファイルは1ガチャとして扱います。正式名とレアリティが一致するアイテムは同一候補としてまとめ、名称未確認データはID単位で分けます。常設ガチャは追加間隔の計算から除外します。</p>
      </section>
    </LegalPage>
  )
}

function GachaCycleGuide() {
  return (
    <LegalPage title="ガチャ追加ペースと開催期間" description="Aimyの登録済みガチャを開始日時順に並べ、追加間隔と開催日数を実測した結果です。">
      <p>登録済みガチャの開始日時を古い順に比較すると、追加間隔の中央値は{insights.medianIntervalDays}日、平均は{insights.averageIntervalDays}日でした。最短{insights.shortestIntervalDays}日、最長{insights.longestIntervalDays}日で、一定間隔ではありません。</p>
      <section className="legal-section">
        <h2>直近10件の実測値</h2>
        <div className="insight-table-wrap"><table className="insight-table"><thead><tr><th>ガチャ</th><th>開始</th><th>前回から</th><th>開催日数</th><th>登録数</th></tr></thead><tbody>
          {latestRows.map((gacha) => <tr key={gacha.slug}><td><Link to={`/gacha/${gacha.slug}`}>{gacha.title}</Link></td><td>{gacha.startDate}</td><td>{gacha.intervalFromPrevious ? `${gacha.intervalFromPrevious}日` : '—'}</td><td>{gacha.durationDays ? `${gacha.durationDays}日` : '—'}</td><td>{gacha.itemCount}件</td></tr>)}
        </tbody></table></div>
      </section>
      <section className="legal-section"><h2>この数値の使い方</h2><p>次回日程の予言ではなく、過去の登録結果を見返すための参考値です。開催日時は記事公開日時ではなく、ゲーム内の「開催期間」欄に表示された開始・終了だけを採用しています。</p></section>
    </LegalPage>
  )
}

function ReprintGuide() {
  return (
    <LegalPage title="復刻アイテムの確認結果" description="初回収録と復刻収録を重複させずに数える方法と、登録済みガチャでの確認結果です。">
      <p>復刻ガチャのアイテムはガチャ詳細にはすべて残し、図鑑では正式名とレアリティが一致する初回収録へまとめます。画像だけが似ている場合や名称未確認の場合は、誤統合を避けるため自動では同一扱いにしません。</p>
      <section className="legal-section"><h2>復刻・再収録が確認できたガチャ</h2><div className="insight-table-wrap"><table className="insight-table"><thead><tr><th>ガチャ</th><th>全登録</th><th>過去収録と一致</th><th>初登場候補</th></tr></thead><tbody>
        {reprintRows.map((gacha) => <tr key={gacha.slug}><td><Link to={`/gacha/${gacha.slug}`}>{gacha.title}</Link></td><td>{gacha.itemCount}件</td><td>{gacha.returningItems}件</td><td>{gacha.firstSeenItems}件</td></tr>)}
      </tbody></table></div></section>
      <section className="legal-section"><h2>判定できないケース</h2><p>表記揺れ、正式名未確認、レアリティ変更がある場合は別候補として残します。後からゲーム内画面で同一と確認できた時点で初回データへ統合します。</p></section>
    </LegalPage>
  )
}

function ImageSearchGuide() {
  return (
    <LegalPage title="画像検索の判定方法" description="Aimy Closetの画像検索が候補を比較する仕組みと、検索精度を上げる具体的な切り抜き手順です。">
      <p>画像検索は名称を読み取るOCRではなく、選択範囲の見た目を登録画像と比較する候補検索です。服と目のように形が異なる画像を混ぜないため、先にカテゴリを絞ってから比較します。</p>
      <section className="legal-section"><h2>精度を上げる4手順</h2><ol><li>スクリーンショットを縮小せず読み込む</li><li>アイテム全体を含め、余白は少なめに切り取る</li><li>服・髪型・アクセサリー・パーツなどのカテゴリを先に選ぶ</li><li>上位候補が弱い時は、範囲を少し広げた画像と狭めた画像の両方を試す</li></ol></section>
      <section className="legal-section"><h2>一致しにくい条件</h2><p>元スクリーンショットが小さい、半透明パーツが背景へ溶けている、登録時と向きが違う、未登録アイテムの場合は順位が下がります。結果は確定名ではなく候補として扱い、ガチャ名・カテゴリ・レアリティも照合してください。</p></section>
      <section className="legal-section"><h2>登録画像の扱い</h2><p>カード画像は縦横比を変えず、検出範囲が小さい時は公開表示用の192×192へ高品質変換します。元画像の細部が戻るわけではないため、より大きい同一画像が見つかった場合は高解像度側へ差し替えます。</p></section>
    </LegalPage>
  )
}

export { GachaCycleGuide, ReprintGuide, ImageSearchGuide }
export default Insights
