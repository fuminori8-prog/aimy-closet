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
      <div className="article-lead">
        <p>
          Aimyで毎日やるべきデイリーミッションとデイリービンゴをまとめました！
          すべて完了すると、<strong>ガチャチケット2枚とジェム100個</strong>を受け取れます。
        </p>
        <small className="daily-guide-reset">※各タスクは毎日0時にリセットされます。</small>
      </div>

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
          Aimyを開いてホーム画面へ。これだけで「アイミーに会おう」は達成です。
          ログインボーナスが表示されたら、そのまま受け取りましょう。
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
          ホーム画面の「アイミーに話しかける」をタップします。
          話しかけないと不機嫌になるので、毎日忘れずに！
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
          ガチャ画面の「無料」タブを開きます。基本は女性3回、男性3回。
          周年イベントなどでは5回ずつ、合計10回引けることもあります。
        </p>
        <p>
          女性アバターしか使っていなくても、男性ガチャまで引くのがおすすめです。
          1回引くだけで親密度ポイントが5増えます。アイテムが被れば交換用のメダルも
          貯まります。背景などは男女共通なので被りやすいです。
        </p>
        <GuideImage
          src="03-free-gacha.webp"
          alt="Aimyの無料ガチャ一覧画面"
          caption="上部の「無料」タブで、その日に引けるガチャを確認します。"
        />
        <p className="daily-guide-site-link">
          引いたアイテムを調べるなら<Link to="/">Aimy ClosetのTOPページ</Link>へ。
          終了したガチャやアイテムランキングも見られます。
        </p>
      </section>

      <section className="legal-section daily-guide-step">
        <p className="daily-guide-step-number">STEP 4〜7</p>
        <h2>ひろばでデイリービンゴをまとめて進める</h2>
        <p>
          ホームの「ひろば」を開きます。ここからは、いくつかのタスクをまとめて終わらせます。
        </p>
        <GuideImage
          src="04-plaza.webp"
          alt="Aimyひろばの交流メニューとランダム訪問ボタン"
          caption="「交流」にオープンチャットとランダム訪問があります。"
        />

        <ol className="daily-guide-action-list">
          <li>
            <strong>オープンチャットを開く</strong>
            <span>チャットが表示されたら、左下の「＞」で戻ってOKです。</span>
          </li>
          <li>
            <strong>ランダム訪問からツーショットを撮る</strong>
            <span>「交流」のランダム訪問をタップ。訪問先でツーショットを撮ります。</span>
          </li>
          <li>
            <strong>「今日のテーマ」タグを付けて投稿する</strong>
            <span>青い目印が付いたタグを選びます。これだけで「チェキ撮影」「ツーショット」「今日のテーマ投稿」の3つをまとめて達成できます。</span>
          </li>
          <li>
            <strong>投稿後に交流する</strong>
            <span>そのまま「いいね」「フォロー」「コメント」を済ませます。いいねは新人の投稿が対象です。</span>
          </li>
        </ol>
      </section>

      <section className="legal-section daily-guide-step">
        <p className="daily-guide-step-number">FINISH</p>
        <h2>ビンゴ・ギフト・ミッションの報酬を回収</h2>
        <p>
          ビンゴが完成すると、1列ごとにフレンドポイント30ptを獲得できます。
          オールビンゴ報酬は単発ガチャチケット1枚です。
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
          次にホームへ戻って「ギフト」を開きます。今日のテーマ投稿報酬は
          ガチャチケット1枚です。最後に「ミッション」の「一括で受け取る」をタップ。
          全5項目でジェム100個を受け取れます。
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
              TOPの「クローゼット」から着せ替えられます。欲しいアイテムは
              Aimy Closetのお気に入りに保存しておくと便利です。
            </p>
            <Link to="/">Aimy ClosetのTOPページでアイテムを探す</Link>
          </article>
          <article>
            <h3>チェキを編集して投稿する</h3>
            <p>
              スタンプの拡大・縮小や回転を使えば、かなり凝ったチェキも作れます。
              「朝チェキ占い」など、時間限定のチェキもおすすめです。
            </p>
          </article>
          <article>
            <h3>アイミーと会話する</h3>
            <p>
              無料で話せるのは1日5回まで。もっと話したい人は、会話し放題の
              月額プランもチェックしてみましょう。
            </p>
          </article>
        </div>
      </section>

      <section className="legal-section daily-guide-faq">
        <h2>Aimy攻略：デイリータスクのよくある質問</h2>
        <details>
          <summary>Aimyのデイリーは何時にリセットされる？</summary>
          <p>毎日0時です。</p>
        </details>
        <details>
          <summary>女性アバターでも男性無料ガチャを引く意味はある？</summary>
          <p>あります。親密度ポイントが増え、被ったアイテムは交換用のメダルになります。</p>
        </details>
        <details>
          <summary>今日のテーマ投稿は何と同時達成できる？</summary>
          <p>「チェキを撮影」「ツーショットを撮る」「今日のテーマタグをつけて投稿」の3つです。</p>
        </details>
      </section>

      <small className="daily-guide-reset">
        ※アップデートやイベントで回数や報酬が変わることがあります。
      </small>
    </LegalPage>
  )
}

export default DailyTasksGuide
