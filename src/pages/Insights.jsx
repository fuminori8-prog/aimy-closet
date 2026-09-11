import { Link } from 'react-router-dom'
import LegalPage from '../components/LegalPage'
import { gachas } from '../data/gachas'
import { getSiteInsights } from '../utils/siteInsights'

const insights = getSiteInsights(gachas)
const latestRows = [...insights.datedGachas].reverse().slice(0, 12)
const reprintRows = insights.datedGachas
  .filter((gacha) => gacha.title.includes('復刻'))
  .reverse()
const reprintExactMatches = reprintRows.flatMap((gacha) =>
  gacha.matchingPriorItems.map((item) => ({
    ...item,
    currentGachaTitle: gacha.title,
    currentGachaSlug: gacha.slug,
  })),
)
const REVIEWED_DATE = '2026年9月11日'

function ArticleStamp({ method }) {
  return (
    <div className="article-stamp" aria-label="記事情報">
      <p><strong>執筆・検証:</strong> Aimy Closet運営者</p>
      <p><strong>最終内容確認:</strong> {REVIEWED_DATE}</p>
      {method ? <p><strong>確認方法:</strong> {method}</p> : null}
    </div>
  )
}

function StatGrid() {
  return (
    <dl className="insight-stat-grid">
      <div>
        <dt>開催日を確認できたガチャ</dt>
        <dd>{insights.datedGachas.length}件</dd>
      </div>
      <div>
        <dt>図鑑上の固有アイテム</dt>
        <dd>{insights.uniqueItemCount}件</dd>
      </div>
      <div>
        <dt>追加間隔の中央値</dt>
        <dd>{insights.medianIntervalDays ?? '—'}日</dd>
      </div>
      <div>
        <dt>最も多い開催日数</dt>
        <dd>{insights.commonDuration?.value ?? '—'}日</dd>
      </div>
    </dl>
  )
}

function ArticleNotice({ children }) {
  return <aside className="editorial-notice">{children}</aside>
}

function Insights() {
  return (
    <LegalPage
      title="Aimyデータ分析"
      description="Aimy Closetの登録データをもとに、ガチャ追加間隔、開催期間、復刻照合の結果と限界を公開しています。"
    >
      <p className="article-lead">
        ガチャ名や画像を並べるだけでは分からない「追加の間隔」「開催期間の偏り」
        「復刻をどこまで確認できたか」を、登録済みデータから同じ条件で計算しています。
        数値だけで結論を作らず、数え方と判断できない範囲も併記します。
      </p>
      <ArticleStamp method="ゲーム内の開催期間と登録済みラインナップを目視確認し、開始日時順に集計" />
      <StatGrid />

      <section className="legal-section">
        <h2>今回の集計から分かったこと</h2>
        <div className="finding-grid">
          <article>
            <p className="finding-label">追加ペース</p>
            <h3>中央値は{insights.medianIntervalDays}日</h3>
            <p>
              平均は{insights.averageIntervalDays}日ですが、最短
              {insights.shortestIntervalDays}日・最長{insights.longestIntervalDays}日です。
              「毎週同じ曜日」のような固定周期としては扱えません。
            </p>
          </article>
          <article>
            <p className="finding-label">開催期間</p>
            <h3>{insights.commonDuration?.value ?? '—'}日が最多</h3>
            <p>
              通常ガチャと周年復刻では期間が異なります。開始日だけでなく終了日も
              確認し、同時開催の候補を比べるための履歴として使うのが適切です。
            </p>
          </article>
          <article>
            <p className="finding-label">復刻照合</p>
            <h3>「一致なし」は新規の意味ではない</h3>
            <p>
              当サイトの登録開始前に登場したアイテムは、復刻元と照合できません。
              完全一致した名称だけを別表にし、不明分を新規とは断定しません。
            </p>
          </article>
        </div>
      </section>

      <section className="legal-section">
        <h2>目的別に読む</h2>
        <div className="editorial-link-grid">
          <Link to="/guides/item-finder">
            <strong>名前が分からない衣装を探す</strong>
            <span>名前・画像・時期のうち、手元にある手掛かりから探し方を選びます。</span>
          </Link>
          <Link to="/guides/gacha-cycle">
            <strong>ガチャ追加ペースと開催期間</strong>
            <span>間隔と開催日数の分布、直近データ、読み違えないための注意点を確認します。</span>
          </Link>
          <Link to="/guides/reprints">
            <strong>復刻アイテムの照合結果</strong>
            <span>何を同一と見なし、どのケースを未判定として残すかを確認します。</span>
          </Link>
          <Link to="/guides/image-search">
            <strong>画像検索の使い方と限界</strong>
            <span>切り抜き範囲、カテゴリ選択、候補が弱い場合のやり直し方をまとめています。</span>
          </Link>
          <Link to="/guides/categories">
            <strong>カテゴリの分類ルール</strong>
            <span>服・髪型・アクセサリー・パーツ・背景・チェキフレームの分け方です。</span>
          </Link>
        </div>
      </section>

      <section className="legal-section">
        <h2>集計の対象と限界</h2>
        <p>
          対象は、当サイトに登録され、開始日時をゲーム内画面で確認できたガチャです。
          同じslugの重複データは1件として扱い、常設ガチャは追加間隔の計算から除外します。
          現在の期間は「{insights.earliestRegisteredGacha?.title}」
          （{insights.earliestRegisteredGacha?.startDate}）以降です。
        </p>
        <ArticleNotice>
          <strong>重要:</strong> この期間より前の初回登場、表記揺れ、名称未確認のアイテムは
          自動照合できません。ここで示す数値は公式の提供割合や将来日程ではなく、
          Aimy Closetで確認済みの履歴に対する集計です。
        </ArticleNotice>
      </section>
    </LegalPage>
  )
}

function GachaCycleGuide() {
  return (
    <LegalPage
      title="ガチャ追加ペースと開催期間"
      description="Aimyの登録済みガチャについて、追加間隔と開催日数の分布、直近12件の実測値、数値の読み方を掲載します。"
    >
      <p className="article-lead">
        開始日時を古い順に並べて隣り合う差を測ると、追加間隔の中央値は
        {insights.medianIntervalDays}日、平均は{insights.averageIntervalDays}日でした。
        ただし間隔には幅があるため、次回開始日の予測ではなく、過去ガチャを探すための目安として使います。
      </p>
      <ArticleStamp method="常設を除き、ゲーム内『開催期間』欄の開始・終了日時だけを日単位で比較" />

      <ArticleNotice>
        <strong>先に結論:</strong> 登録範囲では3〜4日間隔が中心ですが固定周期ではありません。
        通常ガチャは{insights.commonDuration?.value ?? '—'}日前後の開催が多く、周年復刻のような短期開催は別に確認する必要があります。
      </ArticleNotice>

      <section className="legal-section">
        <h2>追加間隔は何日が多いか</h2>
        <p>
          下表は、ひとつ前に始まったガチャから何日後に次のガチャが始まったかを数えたものです。
          同日に複数追加された場合や、開始日時を確認できないデータは集計に入りません。
        </p>
        <div className="insight-table-wrap">
          <table className="insight-table">
            <thead><tr><th>前回から</th><th>確認回数</th><th>読み方</th></tr></thead>
            <tbody>
              {insights.intervalDistribution.map((row) => (
                <tr key={row.value}>
                  <td>{row.value}日</td>
                  <td>{row.count}回</td>
                  <td>{row.value <= 2 ? '短い間隔' : row.value <= 4 ? '中心的な間隔' : '長めの間隔'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="legal-section">
        <h2>開催日数の分布</h2>
        <p>
          開始と終了の差を日単位へ丸めています。終了時刻が14:59や23:59の場合があるため、
          ゲーム画面上の表示と日付だけを数えた感覚に1日程度の差が出ることがあります。
        </p>
        <div className="distribution-list">
          {insights.durationDistribution.map((row) => (
            <div key={row.value}>
              <strong>{row.value}日</strong>
              <span>{row.count}件</span>
            </div>
          ))}
        </div>
      </section>

      <section className="legal-section">
        <h2>直近12件の実測値</h2>
        <div className="insight-table-wrap">
          <table className="insight-table">
            <thead>
              <tr><th>ガチャ</th><th>開始</th><th>前回から</th><th>開催日数</th><th>登録数</th></tr>
            </thead>
            <tbody>
              {latestRows.map((gacha) => (
                <tr key={gacha.slug}>
                  <td><Link to={`/gacha/${gacha.slug}`}>{gacha.title}</Link></td>
                  <td>{gacha.startDate}</td>
                  <td>{gacha.intervalFromPrevious ? `${gacha.intervalFromPrevious}日` : '—'}</td>
                  <td>{gacha.durationDays ? `${gacha.durationDays}日` : '—'}</td>
                  <td>{gacha.itemCount}件</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="legal-section">
        <h2>この数値が役立つ場面</h2>
        <ul>
          <li>スクリーンショットの日付から、近い時期のガチャを数件まで絞る</li>
          <li>複数ガチャが同時開催だった期間を確認し、アイテムの収録先を見比べる</li>
          <li>周年復刻のような短期開催を通常ガチャと分けて見落としを防ぐ</li>
        </ul>
        <p>
          反対に、次回ガチャの日付や内容を当てる用途には使えません。追加間隔は運営上の都合や
          イベントで変わるため、開催中かどうかは必ず各ガチャ詳細の終了日時で確認してください。
        </p>
      </section>
    </LegalPage>
  )
}

function ReprintGuide() {
  return (
    <LegalPage
      title="復刻アイテムの照合結果"
      description="Aimyの復刻ガチャを登録済み履歴と照合し、完全一致したアイテム、照合できない範囲、図鑑で重複させない基準を説明します。"
    >
      <p className="article-lead">
        復刻ガチャの全アイテムはガチャ詳細に残し、図鑑では同じアイテムを何度も並べない方針です。
        ただし「復刻」と書かれていても、復刻元が当サイトの登録開始前なら自動では突き止められません。
      </p>
      <ArticleStamp method="開始日時の古い順に、正式名を正規化し、レアリティも一致した場合だけ同一候補として照合" />

      <ArticleNotice>
        <strong>前回表示の訂正:</strong> 「既存履歴と一致しない件数」を「初登場候補」と表示していましたが、
        復刻元が未登録のケースを新規扱いしてしまう表現でした。現在は
        「登録済み履歴と一致」「当サイトの履歴だけでは未判定」に分けています。
      </ArticleNotice>

      <section className="legal-section">
        <h2>周年復刻ガチャの照合状況</h2>
        <div className="insight-table-wrap">
          <table className="insight-table">
            <thead>
              <tr><th>ガチャ</th><th>全登録</th><th>既存履歴と完全一致</th><th>履歴内では未判定</th></tr>
            </thead>
            <tbody>
              {reprintRows.map((gacha) => (
                <tr key={gacha.slug}>
                  <td><Link to={`/gacha/${gacha.slug}`}>{gacha.title}</Link></td>
                  <td>{gacha.itemCount}件</td>
                  <td>{gacha.returningItems}件</td>
                  <td>{gacha.unmatchedToRegisteredHistory}件</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p>
          「履歴内では未判定」には、当サイトの登録開始前に初登場したもの、表記が変わったもの、
          読み取り誤差が残るものが含まれます。新規アイテム数を示す欄ではありません。
        </p>
      </section>

      <section className="legal-section">
        <h2>完全一致を確認できたアイテム</h2>
        {reprintExactMatches.length ? (
          <div className="insight-table-wrap">
            <table className="insight-table">
              <thead><tr><th>アイテム</th><th>レアリティ</th><th>先に確認したガチャ</th><th>再収録先</th></tr></thead>
              <tbody>
                {reprintExactMatches.map((item) => (
                  <tr key={`${item.currentGachaSlug}-${item.id}`}>
                    <td>{item.name}</td>
                    <td>{item.rarity || '未確認'}</td>
                    <td><Link to={`/gacha/${item.firstGachaSlug}`}>{item.firstGachaTitle}</Link></td>
                    <td><Link to={`/gacha/${item.currentGachaSlug}`}>{item.currentGachaTitle}</Link></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p>現在の登録範囲では、正式名とレアリティが完全一致した再収録を確認できていません。</p>
        )}
      </section>

      <section className="legal-section">
        <h2>図鑑で統合する条件</h2>
        <ol>
          <li>正式なアイテム名が確認済みである</li>
          <li>空白や文字幅をそろえた後の名前が一致する</li>
          <li>レアリティも一致する</li>
          <li>「名称未確認」「アイテム01」のような仮名ではない</li>
        </ol>
        <p>
          画像が似ているだけでは統合しません。色違い、目の色、髪色、記号の違いを別アイテムとして
          残す必要があるためです。逆に、同一と確認できたものは初回側の図鑑項目へまとめても、
          復刻ガチャ詳細には収録アイテムとして残します。
        </p>
      </section>

      <section className="legal-section">
        <h2>自分で復刻元を確かめる手順</h2>
        <ol>
          <li>復刻ガチャ詳細でアイテム名とレアリティを確認する</li>
          <li><Link to="/item">アイテム図鑑</Link>で名前の特徴的な部分を検索する</li>
          <li>候補カードのガチャ名を開き、画像・色・カテゴリを見比べる</li>
          <li>表記が違う場合は、同一と決めつけず未判定として残す</li>
        </ol>
      </section>
    </LegalPage>
  )
}

function ImageSearchGuide() {
  return (
    <LegalPage
      title="画像検索の使い方と限界"
      description="Aimy Closetの画像検索について、切り抜き方、カテゴリ選択、候補が弱い場合の直し方、画像の取扱いを具体的に説明します。"
    >
      <p className="article-lead">
        画像検索は文字を読むOCRではなく、スクリーンショットの選択範囲と登録画像の
        色・輪郭・見た目を比べる候補検索です。上位1件を正解と決める機能ではなく、
        名前が分からない状態から確認候補を減らすために使います。
      </p>
      <ArticleStamp method="端末内で選択画像を正方形へ整え、選択カテゴリ内の登録画像と比較" />

      <section className="legal-section">
        <h2>失敗しにくい5手順</h2>
        <ol className="step-list">
          <li><strong>元スクリーンショットを選ぶ。</strong> メッセージアプリ等で縮小された画像より、端末の写真にある原本が適しています。</li>
          <li><strong>カテゴリを先に選ぶ。</strong> 服と目のように形が違う画像を同じ候補群へ混ぜないためです。</li>
          <li><strong>アイテム全体を囲む。</strong> 端が欠けない範囲で、カード外の文字や隣のアイテムは入れすぎないようにします。</li>
          <li><strong>上位候補の名前以外も見る。</strong> ガチャ名、レアリティ、カテゴリ、色を一緒に照合します。</li>
          <li><strong>弱い場合は範囲を変えて再試行する。</strong> 少し広めと少し狭めの2通りを比べます。</li>
        </ol>
        <p><Link to="/image-search" className="inline-cta">画像検索を開く</Link></p>
      </section>

      <section className="legal-section">
        <h2>カテゴリはどう選ぶか</h2>
        <div className="insight-table-wrap">
          <table className="insight-table">
            <thead><tr><th>カテゴリ</th><th>選ぶもの</th><th>迷いやすい点</th></tr></thead>
            <tbody>
              <tr><td>服</td><td>全身衣装、トップスを含むコーデ</td><td>帽子や耳だけならアクセサリー</td></tr>
              <tr><td>髪型</td><td>前髪・後ろ髪を含むヘア全体</td><td>髪飾りだけならアクセサリー</td></tr>
              <tr><td>アクセサリー</td><td>あたま、めがね、ピアス</td><td>顔の色・模様はパーツ</td></tr>
              <tr><td>パーツ</td><td>目、メイク、口、鼻、まゆげ</td><td>顔全体ではなく対象部分を囲む</td></tr>
              <tr><td>背景</td><td>部屋・屋外など画面の背景</td><td>キャラクターをできるだけ除く</td></tr>
              <tr><td>チェキフレーム</td><td>画面端の装飾・文字枠</td><td>中央の衣装を囲まない</td></tr>
            </tbody>
          </table>
        </div>
      </section>

      <section className="legal-section">
        <h2>候補が弱くなる原因と直し方</h2>
        <dl className="troubleshoot-list">
          <div><dt>画像が小さい・ぼやけている</dt><dd>写真アプリ内の原本へ戻し、同じアイテムがより大きく写る画面があればそちらを使います。</dd></div>
          <div><dt>半透明パーツが背景へ溶ける</dt><dd>背景色が登録画像に近いスクリーンショットを試すか、輪郭が分かる範囲を少し広げます。</dd></div>
          <div><dt>隣のカードや文字が入る</dt><dd>対象の端を切らない範囲で選択を狭めます。カード枠そのものはできるだけ除きます。</dd></div>
          <div><dt>上位に全く違う候補が出る</dt><dd>カテゴリを見直します。未登録アイテムの場合は正解が候補内に存在しません。</dd></div>
        </dl>
      </section>

      <section className="legal-section">
        <h2>画像の取扱いと精度の限界</h2>
        <p>
          選んだ画像と比較処理はブラウザ内で扱い、検索のためにサーバーへアップロードしません。
          元スクリーンショットより細部を増やすことはできず、192×192への変換は表示サイズを
          そろえるためのものです。候補の順位は確率でも本人確認でもないため、最終確認には
          ガチャ詳細とレアリティを併用してください。
        </p>
      </section>
    </LegalPage>
  )
}

function ItemFinderGuide() {
  return (
    <LegalPage
      title="名前が分からないAimy衣装の探し方"
      description="名前、スクリーンショット、実装時期、ガチャの雰囲気など、手元にある情報別にAimyアイテムを探す手順を案内します。"
    >
      <p className="article-lead">
        アイテム名を覚えていなくても、画像・カテゴリ・見かけた時期・ガチャのテーマの
        いずれかが分かれば候補を減らせます。最初から全{insights.uniqueItemCount}件を眺めず、
        手元に残っている情報に合う入口を選ぶのが近道です。
      </p>
      <ArticleStamp method="実際の図鑑・画像検索・ガチャ履歴を使い、情報量別に検索手順を整理" />

      <section className="legal-section">
        <h2>まず、分かっている情報を選ぶ</h2>
        <div className="decision-grid">
          <article><h3>名前の一部が分かる</h3><p>色名や「リボン」「ツイン」など特徴的な語を図鑑で検索します。</p><Link to="/item">図鑑で検索</Link></article>
          <article><h3>画像だけある</h3><p>服・髪型・目などのカテゴリを決め、画像検索で候補を絞ります。</p><Link to="/image-search">画像から検索</Link></article>
          <article><h3>見た時期が分かる</h3><p>ガチャ履歴を開始日時順に見て、その前後に開催されたガチャを開きます。</p><Link to="/gacha">開催順で確認</Link></article>
          <article><h3>かなり古い・ガチャ不明</h3><p>通常図鑑で見つからなければ、交換所で確認した未特定アイテムも確認します。</p><Link to="/historical-items">未特定一覧を見る</Link></article>
        </div>
      </section>

      <section className="legal-section">
        <h2>名前の一部から探す場合</h2>
        <ol>
          <li>見た目の特徴を1語にする（例: リボン、猫目、紫陽花、マーメイド）</li>
          <li>図鑑の検索欄へ入れ、服・髪型などのカテゴリで絞る</li>
          <li>色違いが並んだら、括弧内の色と画像を見比べる</li>
          <li>カードに表示されるガチャ名から詳細を開き、開催時期も確認する</li>
        </ol>
        <p>
          長い正式名を完全一致で入力する必要はありません。逆に「白」「黒」だけでは候補が多いため、
          形を表す語と組み合わせると探しやすくなります。
        </p>
      </section>

      <section className="legal-section">
        <h2>画像と時期を組み合わせる場合</h2>
        <p>
          画像検索の上位候補が似ている場合は、スクリーンショットの撮影日を確認します。
          その日付に開催中だったガチャを履歴から開き、候補名がラインナップにあるかを照合します。
          画像だけの順位より、時期・カテゴリ・レアリティまで一致する候補を優先してください。
        </p>
        <ArticleNotice>
          スクリーンショットの撮影日は、アイテムの初登場日とは限りません。
          復刻、交換所、過去に入手したコーデの可能性があるため、日付だけで断定しないことが重要です。
        </ArticleNotice>
      </section>

      <section className="legal-section">
        <h2>見つからないときの確認順</h2>
        <ol>
          <li>アクセサリーとパーツなど、隣接カテゴリを変えて検索する</li>
          <li>OCRの表記揺れを考え、名前を短くして検索する</li>
          <li>画像検索の選択範囲を広い・狭いの2通りで試す</li>
          <li>ガチャ未特定の過去アイテムを確認する</li>
          <li>未登録の可能性として、分かる画面を添えて情報提供する</li>
        </ol>
      </section>
    </LegalPage>
  )
}

function CategoryGuide() {
  return (
    <LegalPage
      title="アイテムカテゴリの分類ルール"
      description="Aimy Closetで服・髪型・アクセサリー・パーツ・背景・チェキフレームをどう分類しているか、迷いやすい境界とともに説明します。"
    >
      <p className="article-lead">
        ゲーム内の表示を基本にしながら、検索時に同じ種類がまとまるよう6つの主カテゴリへ正規化しています。
        元データの「あたま」「めがね」「目」「メイク」などは消さず、主カテゴリの下の種類として残します。
      </p>
      <ArticleStamp method="ゲーム内のカテゴリ表記を保存し、検索用の主カテゴリだけ共通化" />

      <section className="legal-section">
        <h2>6つの主カテゴリ</h2>
        <div className="category-rule-grid">
          <article><h3>服</h3><p>衣装・コーデ・ワンピースなど、体へ着用するセット。元表記が「衣装」の場合も検索上は服へまとめます。</p></article>
          <article><h3>髪型</h3><p>ショート、ロング、ツインテールなど髪全体。髪に付けるリボンや帽子はアクセサリーです。</p></article>
          <article><h3>アクセサリー</h3><p>あたま、めがね、ピアス、耳飾り。どこへ付けるかは種類として残し、まとめて検索もできます。</p></article>
          <article><h3>パーツ</h3><p>目、メイク、口、鼻、まゆげなど顔の見た目を変える要素。目の色違いは別アイテムとして扱います。</p></article>
          <article><h3>背景</h3><p>部屋、屋外、会場などキャラクターの背後に表示する景色。フレーム装飾とは分けます。</p></article>
          <article><h3>チェキフレーム</h3><p>画面端の装飾、文字、写真風の枠。背景と一緒に見えても、枠として登録されたものはこちらです。</p></article>
        </div>
      </section>

      <section className="legal-section">
        <h2>迷いやすい境界</h2>
        <div className="insight-table-wrap">
          <table className="insight-table">
            <thead><tr><th>迷う組み合わせ</th><th>判断基準</th></tr></thead>
            <tbody>
              <tr><td>髪型 / あたま</td><td>髪そのものは髪型、帽子・リボン・耳など追加装飾はアクセサリー</td></tr>
              <tr><td>めがね / 目</td><td>顔の前に付ける物はアクセサリー、瞳の形や色はパーツ</td></tr>
              <tr><td>メイク / チェキフレーム</td><td>顔へ付く色や模様はパーツ、画面全体の装飾はチェキフレーム</td></tr>
              <tr><td>背景 / チェキフレーム</td><td>後ろの場所・景色は背景、前面や端へ重なる枠はチェキフレーム</td></tr>
            </tbody>
          </table>
        </div>
      </section>

      <section className="legal-section">
        <h2>分類に誤りがある場合</h2>
        <p>
          自動読取りで「衣装」が別カテゴリになった場合などは、元画像を確認して修正します。
          該当ページのURL、現在の分類、ゲーム内で確認できる正しい表記を
          <Link to="/contact">お問い合わせ</Link>からお知らせください。
        </p>
      </section>
    </LegalPage>
  )
}

export {
  CategoryGuide,
  GachaCycleGuide,
  ImageSearchGuide,
  ItemFinderGuide,
  ReprintGuide,
}
export default Insights
