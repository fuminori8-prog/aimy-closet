import { Link } from 'react-router-dom'
import LegalPage from '../components/LegalPage'

const IMAGE_BASE = '/images/guides/aimy-daily-tasks'

function GuideImage({ src, alt, caption }) {
  return (
    <figure className="daily-guide-figure">
      <img src={`${IMAGE_BASE}/${src}`} alt={alt} loading="lazy" />
      <figcaption>{caption}</figcaption>
    </figure>
  )
}

function DailyTasksGuide() {
  return (
    <LegalPage
      title="【Aimy攻略】デイリータスク完全ガイド"
      description="Aimyのデイリーミッションとデイリービンゴを効率よくクリアする手順を、実際のゲーム画面つきで解説します。無料ガチャ、ひろば、今日のテーマ投稿、報酬の受け取りまでまとめました。"
    >
      <p className="article-lead">
        Aimyで毎日やっておきたいデイリーミッションとデイリービンゴを、
        取りこぼしにくい順番でまとめました。ログインから報酬受け取りまで、
        実際の画面に沿って進めれば一連のタスクをまとめて達成できます。
      </p>

      <div className="article-stamp" aria-label="記事情報">
        <p><strong>執筆・確認:</strong> Aimy Closet運営者</p>
        <p><strong>画面確認日:</strong> 2026年10月1日</p>
        <p><strong>確認方法:</strong> Aimyアプリ内で実際に操作</p>
      </div>

      <aside className="editorial-notice">
        <strong>先に結論:</strong> 「ひろば」でのツーショット投稿に
        「今日のテーマ」タグを付けると、デイリーミッションとビンゴの複数項目を
        まとめて進められます。すべて完了すると、確認時点では
        <strong>ガチャチケット2枚とジェム100個</strong>を受け取れます。
        各タスクは毎日0時にリセットされます。
      </aside>

      <nav className="daily-guide-summary" aria-label="デイリー攻略の流れ">
        <h2>最短で進める順番</h2>
        <ol>
          <li>ログインする</li>
          <li>アイミーに話しかける</li>
          <li>無料ガチャを引く</li>
          <li>ひろばを開く</li>
          <li>オープンチャットを開く</li>
          <li>ランダム訪問からツーショットを投稿する</li>
          <li>いいね・フォロー・コメントをする</li>
          <li>ギフトとミッション報酬を受け取る</li>
        </ol>
      </nav>

      <section className="legal-section daily-guide-step">
        <p className="daily-guide-step-number">STEP 1</p>
        <h2>ログインして「アイミーに会おう」を達成</h2>
        <p>
          Aimyを起動してホーム画面まで進めば、「アイミーに会おう」は達成です。
          月初や連続ログイン中はログインボーナス画面も表示されるため、受け取り忘れが
          ないか確認しましょう。
        </p>
        <GuideImage
          src="01-login-bonus.webp"
          alt="Aimyの9月ログインボーナス受け取り画面"
          caption="ログインボーナスも表示されたら、その場で受け取ります。"
        />
      </section>

      <section className="legal-section daily-guide-step">
        <p className="daily-guide-step-number">STEP 2</p>
        <h2>アイミーに話しかけて挨拶する</h2>
        <p>
          ホーム画面の「アイミーに話しかける」をタップします。会話を1回始めれば、
          デイリーミッションの挨拶項目を進められます。画面上では1日5回まで無料と
          表示されていますが、無料回数やプラン内容は変更される場合があるため、
          アプリ内の最新表示も確認してください。
        </p>
        <GuideImage
          src="02-talk.webp"
          alt="Aimyホーム画面のアイミーに話しかけるボタン"
          caption="ホーム下部のピンク色のボタンから会話を始めます。"
        />
      </section>

      <section className="legal-section daily-guide-step">
        <p className="daily-guide-step-number">STEP 3</p>
        <h2>女性・男性の無料ガチャを引く</h2>
        <p>
          ガチャ画面の「無料」タブを開き、引ける無料ガチャを消化します。通常時は
          女性向け3枠・男性向け3枠が目安ですが、開催状況によって枠数は変わります。
          周年イベントなどでは、女性5回・男性5回の合計10回になることもあります。
        </p>
        <p>
          女性アバターだけで遊んでいる場合も、余裕があれば男性ガチャまで引くのが
          おすすめです。1回引くごとに親密度ポイントを5獲得でき、重複アイテムは
          交換に使えるメダルになります。背景など男女共通のアイテムもあります。
        </p>
        <GuideImage
          src="03-free-gacha.webp"
          alt="Aimyの無料ガチャ一覧画面"
          caption="上部の「無料」タブで、その日に引けるガチャを確認します。"
        />
        <p className="daily-guide-site-link">
          引いたアイテムの名前や収録ガチャを調べたい場合は、
          <Link to="/">Aimy ClosetのTOPページ</Link>から検索できます。
          終了済みガチャのアイテムやランキングも確認できます。
        </p>
      </section>

      <section className="legal-section daily-guide-step">
        <p className="daily-guide-step-number">STEP 4〜7</p>
        <h2>ひろばでデイリービンゴをまとめて進める</h2>
        <p>
          ホームの「ひろば」を開きます。ここから次の行動をまとめて済ませると、
          デイリービンゴと「チェキを撮影しよう」を効率よく達成できます。
        </p>
        <GuideImage
          src="04-plaza.webp"
          alt="Aimyひろばの交流メニューとランダム訪問ボタン"
          caption="「交流」にオープンチャットとランダム訪問があります。"
        />

        <ol className="daily-guide-action-list">
          <li>
            <strong>オープンチャットを開く</strong>
            <span>「交流」のオープンチャットをタップし、チャットが表示されたら左下の戻るボタンで戻って構いません。</span>
          </li>
          <li>
            <strong>ランダム訪問からツーショットを撮る</strong>
            <span>訪問先でツーショットを撮影します。これでミッションの「チェキを撮影しよう」と、ビンゴの「ツーショットを撮る」を同時に進められます。</span>
          </li>
          <li>
            <strong>「今日のテーマ」タグを付けて投稿する</strong>
            <span>投稿時のタグ一覧で青い目印が付いている「今日のテーマ」を選びます。テーマ投稿のビンゴと投稿報酬をまとめて狙えます。</span>
          </li>
          <li>
            <strong>投稿後に交流する</strong>
            <span>投稿後は、いいね・フォロー・コメントの対象を確認して実行します。新人投稿へのいいねが条件になっている日は、相手の表示を確認してから押しましょう。</span>
          </li>
        </ol>
      </section>

      <section className="legal-section daily-guide-step">
        <p className="daily-guide-step-number">FINISH</p>
        <h2>ビンゴ・ギフト・ミッションの報酬を回収</h2>
        <p>
          ビンゴが完成したら、まず完成画面で報酬を確認します。1列ごとに
          フレンドポイント30pt、オールビンゴ報酬として単発ガチャチケット1枚が
          表示されます。
        </p>
        <div className="daily-guide-image-grid">
          <GuideImage
            src="05-bingo-complete.webp"
            alt="Aimyひろばのデイリービンゴ完成表示"
            caption="ひろばで「デイリービンゴ complete!」を確認。"
          />
          <GuideImage
            src="06-bingo-reward.webp"
            alt="Aimyデイリービンゴのオールビンゴ報酬画面"
            caption="オールビンゴ報酬は単発ガチャチケット1枚。"
          />
        </div>

        <p>
          次にホームへ戻り、「ギフト」を開いて今日のテーマ投稿報酬の
          ガチャチケット1枚を受け取ります。最後に「ミッション」を開き、
          「一括で受け取る」をタップすると、全5項目でジェム100個を受け取れます。
        </p>
        <div className="daily-guide-image-grid">
          <GuideImage
            src="07-theme-reward.webp"
            alt="Aimyギフトボックスの今日のテーマ投稿報酬"
            caption="今日のテーマ投稿報酬はガチャチケット1枚。"
          />
          <GuideImage
            src="08-mission-reward.webp"
            alt="Aimyデイリーミッション全項目達成画面"
            caption="デイリーミッション全5項目でジェム100個。"
          />
        </div>
        <aside className="daily-guide-reward-total">
          <strong>デイリータスクの合計報酬</strong>
          <span>ガチャチケット2枚（ビンゴ1枚＋今日のテーマ投稿1枚）／ジェム100個</span>
        </aside>
      </section>

      <section className="legal-section">
        <h2>デイリー終了後のおすすめの遊び方</h2>
        <div className="decision-grid">
          <article>
            <h3>アイミーを着せ替える</h3>
            <p>
              ホームの「クローゼット」から衣装を変更できます。Aimy Closetでは、
              終了済みガチャのアイテムも図鑑やガチャ履歴から確認できます。
            </p>
            <Link to="/">Aimy ClosetのTOPページでアイテムを探す</Link>
          </article>
          <article>
            <h3>チェキを編集して投稿する</h3>
            <p>
              スタンプの拡大・縮小・回転を組み合わせると、同じ衣装でも印象を変えられます。
              朝チェキ占いなど、時間帯によって楽しめるチェキもあります。
            </p>
          </article>
          <article>
            <h3>アイミーと会話する</h3>
            <p>
              毎日の無料回数を使って会話し、親密度を上げます。追加の会話にはチケットや
              有料プランが必要な場合があるため、購入前に最新の料金と条件を確認してください。
            </p>
          </article>
        </div>
      </section>

      <section className="legal-section daily-guide-faq">
        <h2>Aimy攻略：デイリータスクのよくある質問</h2>
        <details>
          <summary>Aimyのデイリーは何時にリセットされる？</summary>
          <p>デイリーミッションとデイリービンゴの画面では、毎日0時更新と案内されています。</p>
        </details>
        <details>
          <summary>女性アバターでも男性無料ガチャを引く意味はある？</summary>
          <p>親密度ポイントの獲得や、重複時の交換メダルを貯める目的があります。時間に余裕があれば両方確認するのがおすすめです。</p>
        </details>
        <details>
          <summary>今日のテーマ投稿は何と同時達成できる？</summary>
          <p>ランダム訪問先でツーショットを撮り、今日のテーマタグを付けて投稿すると、チェキ撮影・ツーショット・テーマタグ投稿をまとめて進められます。</p>
        </details>
      </section>

      <aside className="editorial-notice">
        Aimyはアップデートやイベントにより、無料回数・報酬・画面配置が変わる場合があります。
        本記事と表示が異なる場合は、アプリ内の最新案内を優先してください。
      </aside>
    </LegalPage>
  )
}

export default DailyTasksGuide
