import LegalPage from '../components/LegalPage'

function About() {
  return (
    <LegalPage
      title="Aimy Closetについて"
      description="Aimy Closetの目的、掲載内容、運営方針について説明します。"
    >
      <p>
        Aimy Closetは、Aimyの衣装やガチャ情報をあとから探しやすくするために、
        個人が運営している非公式のファンデータベースです。
      </p>

      <section className="legal-section">
        <h2>このサイトでできること</h2>
        <ul>
          <li>服・髪型・アクセサリー・パーツ・背景などをカテゴリ別に探す</li>
          <li>開催中・終了済みガチャの期間と確認済みラインナップを見る</li>
          <li>名前が分からないアイテムを画像から検索する</li>
          <li>気になるアイテムをお気に入りに保存する</li>
          <li>ガチャ名が未特定の過去アイテムを実装時期から確認する</li>
        </ul>
      </section>

      <section className="legal-section">
        <h2>作成した理由</h2>
        <p>
          Aimyでは短い間隔で新しいガチャが追加され、過去の衣装や実装時期を
          後から確認しにくいことがあります。ゲーム内で確認できた情報を整理し、
          「このアイテムは何か」「どのガチャに入っていたか」を調べる時間を
          減らすことを目的に作成しています。
        </p>
      </section>

      <section className="legal-section">
        <h2>非公式サイトです</h2>
        <p>
          当サイトはAimyの公式運営、開発元、配信元とは関係ありません。
          ゲーム名・画像・キャラクター等の権利は、それぞれの権利者に帰属します。
        </p>
      </section>

      <section className="legal-section">
        <h2>間違いを見つけた場合</h2>
        <p>
          アイテム名、カテゴリ、開催期間、画像などの誤りは随時修正します。
          該当ページのURLと正しい情報が分かる画面を、お問い合わせページ記載の
          運営アカウントまでお知らせください。
        </p>
      </section>
    </LegalPage>
  )
}

export default About
