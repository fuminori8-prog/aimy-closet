import LegalPage from '../components/LegalPage'

function Contact() {
  return (
    <LegalPage
      title="お問い合わせ"
      description="Aimy Closetへの掲載ミス、権利関係、不具合、広告に関するお問い合わせ方法です。"
    >
      <p>
        お問い合わせは、Aimy Closetを案内しているX（旧Twitter）の運営アカウントへ、
        DMまたは返信でご連絡ください。
      </p>

      <section className="legal-section">
        <h2>優先して確認する内容</h2>
        <ul>
          <li>アイテム名、ガチャ名、開催期間、画像等の掲載ミス</li>
          <li>権利者からの画像・文章の修正または削除依頼</li>
          <li>サイトが開けない、お気に入りが動かない等の不具合</li>
          <li>広告掲載およびプライバシーに関する連絡</li>
        </ul>
      </section>

      <section className="legal-section">
        <h2>連絡時に記載してほしいこと</h2>
        <ul>
          <li>該当するページのURL</li>
          <li>誤っている箇所または発生している症状</li>
          <li>正しい情報が確認できる公式ページやスクリーンショット</li>
          <li>利用端末とブラウザ（不具合の場合）</li>
        </ul>
      </section>

      <section className="legal-section">
        <h2>返信について</h2>
        <p>
          内容は確認しますが、すべての連絡への返信や対応を保証するものではありません。
          個別の攻略相談、ゲームへの要望、実装時期の指定を伴う機能追加要望には、
          原則として返信できません。
        </p>
      </section>

      <aside className="legal-notice">
        <strong>ご注意</strong>
        <p>
          Aimy Closetは非公式サイトです。当サイトに関する内容をAimy公式運営へ問い合わせないでください。
        </p>
      </aside>
    </LegalPage>
  )
}

export default Contact
