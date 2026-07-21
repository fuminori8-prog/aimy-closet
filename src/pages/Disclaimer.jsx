import LegalPage from '../components/LegalPage'

function Disclaimer() {
  return (
    <LegalPage
      title="免責事項"
      description="Aimy Closetの非公式性、掲載情報、著作権および広告に関する免責事項です。"
    >
      <p className="legal-updated">制定日：2026年7月21日</p>

      <section className="legal-section">
        <h2>非公式サイトについて</h2>
        <p>
          Aimy Closetは個人が運営する非公式のファンデータベースです。
          Aimyの公式運営、開発元、配信元および関係各社とは一切関係ありません。
          当サイトについて、公式運営へのお問い合わせはご遠慮ください。
        </p>
      </section>

      <section className="legal-section">
        <h2>掲載情報について</h2>
        <p>
          掲載内容の正確性および最新性には注意していますが、完全性を保証するものではありません。
          ゲーム内の仕様、名称、開催期間、排出内容等については、必ず公式情報もご確認ください。
          掲載情報の誤りを見つけた場合は、お問い合わせページ記載の方法でお知らせください。
        </p>
      </section>

      <section className="legal-section">
        <h2>損害等について</h2>
        <p>
          当サイトの情報を利用したこと、利用できなかったこと、または外部リンクを利用したことにより
          生じた損害・不利益について、運営者は法令上責任を免れない場合を除き責任を負いません。
          当サイトの利用は、利用者ご自身の判断と責任でお願いいたします。
        </p>
      </section>

      <section className="legal-section">
        <h2>著作権・権利帰属</h2>
        <p>
          ゲーム名、画像、キャラクター、ロゴその他の著作物および商標に関する権利は、
          各権利者に帰属します。当サイトは権利侵害を目的とするものではありません。
          権利者から修正・削除等の要請があった場合は、内容を確認のうえ対応します。
        </p>
      </section>

      <section className="legal-section">
        <h2>外部リンク</h2>
        <p>
          当サイトから移動した外部サイトの内容、商品、サービス、個人情報の取扱い等について、
          当サイトは管理せず、保証も行いません。各外部サイトの規約や方針をご確認ください。
        </p>
      </section>

      <section className="legal-section">
        <h2>広告・アフィリエイト</h2>
        <p>
          当サイトは、アフィリエイト広告を掲載する場合があります。
          利用者が広告を経由して商品・サービスを購入または利用した場合、
          当サイトに報酬が発生することがあります。広告には「PR」「広告」等を表示します。
        </p>
      </section>

      <section className="legal-section">
        <h2>内容の変更・公開停止</h2>
        <p>
          当サイトは、予告なく掲載内容の修正、機能変更、一時停止または公開終了を行う場合があります。
        </p>
      </section>
    </LegalPage>
  )
}

export default Disclaimer
