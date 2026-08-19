import { Link } from 'react-router-dom'
import LegalPage from '../components/LegalPage'

function Guide() {
  return (
    <LegalPage
      title="Aimy Closetの使い方"
      description="アイテム図鑑、ガチャ履歴、画像検索、お気に入りの使い方を案内します。"
    >
      <p>
        探したい情報が分かっている場合と、画像しか残っていない場合で、
        使う機能を選べます。
      </p>

      <section className="legal-section">
        <h2>名前・カテゴリから探す</h2>
        <p>
          <Link to="/item">アイテム図鑑</Link>では、名前の一部、レアリティ、
          ガチャ名を検索できます。服・髪型・アクセサリー・パーツ・背景・
          チェキフレームで絞り込み、パーツは目やメイクなどへさらに分けられます。
        </p>
      </section>

      <section className="legal-section">
        <h2>画像から探す</h2>
        <p>
          <Link to="/image-search">画像検索</Link>にスクリーンショットを追加し、
          探したいアイテムが写っている範囲を指定します。先にカテゴリを選ぶと、
          目と衣装のように見た目が大きく異なる候補が混ざりにくくなります。
        </p>
        <p>
          画像は縦横比を維持して表示します。候補が出ない場合は、アイテムの周囲を
          少し広めに選び直すか、別のスクリーンショットで試してください。
        </p>
      </section>

      <section className="legal-section">
        <h2>ガチャから探す</h2>
        <p>
          <Link to="/gacha">ガチャ履歴</Link>は開始日時が新しい順に表示します。
          詳細ページでは開催期間、確認済み件数、レアリティ別・カテゴリ別の構成と、
          登録済みラインナップを確認できます。
        </p>
      </section>

      <section className="legal-section">
        <h2>名前が未特定の過去アイテム</h2>
        <p>
          <Link to="/historical-items">ガチャ未特定の過去アイテム</Link>には、
          2.5周年交換所で存在を確認できたものを、実装時期・レアリティ・カテゴリ別に
          掲載しています。正式情報が判明したものは通常の図鑑へ統合します。
        </p>
      </section>

      <section className="legal-section">
        <h2>お気に入り</h2>
        <p>
          各アイテムのハートを押すと、同じブラウザの
          <Link to="/favorites">お気に入り一覧</Link>から見返せます。
          ログインや氏名・メールアドレスの入力は不要です。
        </p>
      </section>
    </LegalPage>
  )
}

export default Guide
