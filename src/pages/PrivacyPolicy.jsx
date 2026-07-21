import LegalPage from '../components/LegalPage'

function PrivacyPolicy() {
  return (
    <LegalPage
      title="プライバシーポリシー"
      description="Aimy Closetにおける利用者情報の取扱いについて説明します。"
    >
      <p className="legal-updated">制定日：2026年7月21日</p>

      <p>
        Aimy Closet（以下「当サイト」）は、利用者の情報を適切に取り扱うため、
        本プライバシーポリシーを定めます。
      </p>

      <section className="legal-section">
        <h2>1. 取得する情報</h2>
        <p>当サイトでは、次の情報を取得または保存する場合があります。</p>
        <ul>
          <li>Firebase Authenticationが発行する匿名のユーザー識別子</li>
          <li>お気に入りに登録したアイテムのIDおよび登録・更新日時</li>
          <li>アイテムごとのお気に入り合計数</li>
          <li>
            アクセス時にサーバーや外部サービスへ自動送信されるIPアドレス、
            ブラウザ・端末情報、参照元URL、アクセス日時等のログ情報
          </li>
        </ul>
        <p>
          当サイトは、お気に入り機能の利用にあたり、氏名、住所、電話番号、
          メールアドレスの入力を求めません。
        </p>
      </section>

      <section className="legal-section">
        <h2>2. 利用目的</h2>
        <ul>
          <li>お気に入りの保存、表示および解除</li>
          <li>全利用者のお気に入り数の集計と人気アイテム表示</li>
          <li>不正利用の防止、セキュリティ確保および障害対応</li>
          <li>サイトの品質改善、利用状況の把握および問い合わせ対応</li>
        </ul>
      </section>

      <section className="legal-section">
        <h2>3. Firebaseの利用</h2>
        <p>
          当サイトは、匿名認証およびお気に入り情報の保存に、Google LLCが提供する
          Firebase AuthenticationおよびCloud Firestoreを利用しています。
          これらのサービスの利用に伴い、情報がGoogleのサーバーで処理される場合があります。
        </p>
        <p>
          Firebaseにおける情報の取扱いについては、
          <a
            href="https://firebase.google.com/support/privacy"
            target="_blank"
            rel="noreferrer"
          >
            Firebaseのプライバシーとセキュリティ情報
          </a>
          および
          <a
            href="https://policies.google.com/privacy?hl=ja"
            target="_blank"
            rel="noreferrer"
          >
            Googleプライバシーポリシー
          </a>
          をご確認ください。
        </p>
      </section>

      <section className="legal-section">
        <h2>4. ブラウザ内の保存情報</h2>
        <p>
          匿名認証の状態を維持するため、ブラウザのローカルストレージ等が利用されます。
          ブラウザの保存情報を削除または制限すると、お気に入り一覧が引き継がれない、
          またはお気に入り機能が正常に動作しない場合があります。
        </p>
      </section>

      <section className="legal-section">
        <h2>5. 広告・アフィリエイトについて</h2>
        <p>
          当サイトは、広告またはアフィリエイトプログラムを利用する場合があります。
          広告を掲載する際は、「PR」「広告」等の表示により広告であることを明示します。
          広告リンク先で取得される情報は、各事業者のプライバシーポリシーに従って取り扱われます。
        </p>
      </section>

      <section className="legal-section">
        <h2>6. 情報の削除</h2>
        <p>
          お気に入りは、各アイテムのハートボタンを再度押すことで解除できます。
          ブラウザの保存情報を削除すると端末上の匿名認証情報は失われますが、
          匿名識別子を失った後は、過去の保存情報を利用者本人のものとして特定できない場合があります。
          個別の削除相談は、お問い合わせページ記載の方法でご連絡ください。
        </p>
      </section>

      <section className="legal-section">
        <h2>7. 安全管理</h2>
        <p>
          当サイトは、取得した情報への不正アクセス、漏えい、改ざん等を防ぐため、
          Firebaseのセキュリティルールその他の合理的な安全管理措置を講じます。
        </p>
      </section>

      <section className="legal-section">
        <h2>8. ポリシーの変更</h2>
        <p>
          法令、サービス内容または利用する外部サービスの変更に応じて、
          本ポリシーを予告なく改定する場合があります。重要な変更は当サイト上でお知らせします。
        </p>
      </section>

      <section className="legal-section">
        <h2>9. お問い合わせ</h2>
        <p>
          本ポリシーに関するお問い合わせは、当サイトのお問い合わせページをご確認ください。
        </p>
      </section>
    </LegalPage>
  )
}

export default PrivacyPolicy
