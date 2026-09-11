import { Link } from 'react-router-dom'
import LegalPage from '../components/LegalPage'

function Guide() {
  return (
    <LegalPage
      title="Aimy Closetの使い方"
      description="名前、画像、見た時期、ガチャ名など、分かっている手掛かり別にAimyの衣装とアイテムを探す方法を案内します。"
    >
      <p className="article-lead">
        すべての機能を順番に試す必要はありません。名前・画像・時期・ガチャのうち、
        今分かっている手掛かりに合う入口から探してください。候補が複数出たときは、
        画像だけで決めず、カテゴリ・レアリティ・開催時期も照合します。
      </p>

      <section className="legal-section">
        <h2>手掛かり別の入口</h2>
        <div className="decision-grid">
          <article>
            <h3>名前・特徴を覚えている</h3>
            <p>「リボン」「猫目」「マーメイド」など名前の一部とカテゴリで絞ります。</p>
            <Link to="/item">アイテム図鑑を開く</Link>
          </article>
          <article>
            <h3>スクリーンショットだけある</h3>
            <p>対象を囲み、服・髪型・パーツなどのカテゴリ内から似た候補を探します。</p>
            <Link to="/image-search">画像検索を開く</Link>
          </article>
          <article>
            <h3>見かけた時期が分かる</h3>
            <p>開始日時が新しい順の履歴から、その時期に開催されたガチャを確認します。</p>
            <Link to="/gacha">ガチャ履歴を開く</Link>
          </article>
          <article>
            <h3>古いアイテム・ガチャ不明</h3>
            <p>2.5周年交換所で確認した、正式名や配布ガチャが未特定の記録も確認できます。</p>
            <Link to="/historical-items">未特定アイテムを見る</Link>
          </article>
        </div>
      </section>

      <section className="legal-section">
        <h2>図鑑の検索結果を読む</h2>
        <p>
          各カードには名前、主カテゴリ、種類、収録ガチャを表示します。復刻で同じアイテムが
          再収録された場合、ガチャ詳細には両方の収録を残し、図鑑は初回側の1件へまとめます。
          同名でも色やレアリティが違う場合は別候補です。
        </p>
        <p><Link to="/guides/categories">カテゴリの分類ルールを詳しく見る</Link></p>
      </section>

      <section className="legal-section">
        <h2>画像から探すとき</h2>
        <ol>
          <li>写真アプリにある元のスクリーンショットを選ぶ</li>
          <li>服・髪型・アクセサリー・パーツ・背景・チェキフレームを選ぶ</li>
          <li>対象全体を含め、隣のカードや文字を入れすぎないよう囲む</li>
          <li>上位候補の画像・名前・ガチャ名・レアリティを照合する</li>
        </ol>
        <p>
          選んだ画像はブラウザ内で比較し、検索のためにサーバーへ送りません。
          候補が弱い場合の直し方は<Link to="/guides/image-search">画像検索の使い方と限界</Link>にまとめています。
        </p>
      </section>

      <section className="legal-section">
        <h2>時期と復刻から探すとき</h2>
        <p>
          ガチャ履歴は登録順ではなく、ゲーム内で確認した開始日時の新しい順です。
          周年復刻は、当サイトに復刻元の履歴がないアイテムも含むため、
          「過去履歴と一致しない＝新規」とは判断しません。
        </p>
        <div className="guide-inline-links">
          <Link to="/guides/gacha-cycle">追加間隔と開催日数の実測</Link>
          <Link to="/guides/reprints">復刻アイテムの照合結果</Link>
        </div>
      </section>

      <section className="legal-section">
        <h2>お気に入りと個人情報</h2>
        <p>
          各カードのハートを押すと、同じブラウザの<Link to="/favorites">お気に入り一覧</Link>から見返せます。
          氏名・メールアドレスの入力は不要です。端末やブラウザを変えた場合、同じ一覧にならないことがあります。
        </p>
      </section>

      <section className="legal-section">
        <h2>見つからない・誤りがある場合</h2>
        <p>
          表記揺れや読み取り誤差、まだ登録していないアイテムの可能性があります。
          該当ページのURLと正しい情報を確認できる画面を添えて
          <Link to="/contact">お問い合わせ</Link>ください。登録と修正の基準は
          <Link to="/data-policy">掲載データの確認・修正方針</Link>で公開しています。
        </p>
      </section>
    </LegalPage>
  )
}

export default Guide
