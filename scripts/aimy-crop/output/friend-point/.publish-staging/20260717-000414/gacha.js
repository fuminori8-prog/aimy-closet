const gacha = {
  id: 'friend-point',
  slug: 'friend-point',
  title: 'フレンドポイントガチャ',
  type: '夏',
  banner: '/images/gacha/friend-point/banner.jpg',
  status: '開催中',
  infoStatus: '確認済み',
  startDate: '常設',
  endDate: '終了予定なし',
  description:
    'フレンドポイントで利用できる夏の恒常ガチャです。衣装・髪型・パーツ・背景・チェキフレーム・イベントなどが排出されます。',
  isPermanent: true,

  items: [
    // SSR 衣装
    {
      id: 'friend-point-shittori-seiso-yukata',
      rarity: 'SSR',
      category: '衣装',
      name: 'しっとり清楚浴衣',
      image: '/images/items/friend-point/01.png',
    },
    {
      id: 'friend-point-shoten-pleats-mini-yukata',
      rarity: 'SSR',
      category: '衣装',
      name: '昇天プリーツミニ浴衣',
      image: '/images/items/friend-point/02.png',
    },
    {
      id: 'friend-point-sailor-marine-mizugi',
      rarity: 'SSR',
      category: '衣装',
      name: 'セーラーマリン水着',
      image: '/images/items/friend-point/03.png',
    },
    {
      id: 'friend-point-genki-ippai-summer-bikini',
      rarity: 'SSR',
      category: '衣装',
      name: '元気いっぱいサマービキニ',
      image: '/images/items/friend-point/04.png',
    },
    {
      id: 'friend-point-sawayaka-girly-style',
      rarity: 'SSR',
      category: '衣装',
      name: '爽やかガーリースタイル',
      image: '/images/items/friend-point/05.png',
    },
    {
      id: 'friend-point-chiteki-oshare-lady',
      rarity: 'SSR',
      category: '衣装',
      name: '知的おしゃれレディ',
      image: '/images/items/friend-point/06.png',
    },

    // SSR 目
    {
      id: 'friend-point-ochitsuki-nekomed-odd-eye-red-green',
      rarity: 'SSR',
      category: '目',
      name: '落ち着き猫目オッドアイ(赤緑)',
      image: '/images/items/friend-point/07.png',
    },
    {
      id: 'friend-point-youki-tareme-odd-eye-blue-yellow',
      rarity: 'SSR',
      category: '目',
      name: '幼気タレ目オッドアイ(水黄)',
      image: '/images/items/friend-point/08.png',
    },
    {
      id: 'friend-point-pacchiri-tareme-odd-eye-green-purple',
      rarity: 'SSR',
      category: '目',
      name: 'ぱっちりタレ目オッドアイ(緑紫)',
      image: '/images/items/friend-point/09.png',
    },
    {
      id: 'friend-point-nekomed-odd-eye-green-blue',
      rarity: 'SSR',
      category: '目',
      name: '猫目オッドアイ(緑水)',
      image: '/images/items/friend-point/10.png',
    },

    // SSR 髪型
    {
      id: 'friend-point-fuwafuwa-high-ponytail-pink',
      rarity: 'SSR',
      category: '髪型',
      name: 'ふわふわ高めポニーテール(ピンク)',
      image: '/images/items/friend-point/11.png',
    },
    {
      id: 'friend-point-sotohane-maki-medium-blue',
      rarity: 'SSR',
      category: '髪型',
      name: '外ハネ巻きミディアム(青)',
      image: '/images/items/friend-point/12.png',
    },
    {
      id: 'friend-point-pattsun-mekakure-bob-light-blue',
      rarity: 'SSR',
      category: '髪型',
      name: 'ぱっつん目隠れボブ(水色)',
      image: '/images/items/friend-point/13.png',
    },
    {
      id: 'friend-point-suzushige-tsuyayaka-up-hair-gold',
      rarity: 'SSR',
      category: '髪型',
      name: '涼しげ艶やかアップヘアー(金)',
      image: '/images/items/friend-point/14.png',
    },
    {
      id: 'friend-point-sukkiri-one-curl-bob-black',
      rarity: 'SSR',
      category: '髪型',
      name: 'すっきりワンカールボブ(黒)',
      image: '/images/items/friend-point/15.png',
    },
    {
      id: 'friend-point-intake-low-pony-mint',
      rarity: 'SSR',
      category: '髪型',
      name: 'インテークローポニー(ミント)',
      image: '/images/items/friend-point/16.png',
    },
    {
      id: 'friend-point-mofukuru-twintail-brown',
      rarity: 'SSR',
      category: '髪型',
      name: 'もふくるツインテール(茶)',
      image: '/images/items/friend-point/17.png',
    },
    {
      id: 'friend-point-high-super-long-twin-red',
      rarity: 'SSR',
      category: '髪型',
      name: '高めスーパーロングツイン(赤)',
      image: '/images/items/friend-point/18.png',
    },

    // SSR イベント
    {
      id: 'friend-point-event-big-incident',
      rarity: 'SSR',
      category: 'イベント',
      name: '大事件発生！？',
      image: '/images/items/friend-point/19.png',
    },
    {
      id: 'friend-point-event-enjoy-ennichi',
      rarity: 'SSR',
      category: 'イベント',
      name: '縁日を満喫しよう',
      image: '/images/items/friend-point/20.png',
    },

    // SR あたま
    {
      id: 'friend-point-kirakira-nyan-headband',
      rarity: 'SR',
      category: 'あたま',
      name: 'キラキラにゃんカチューシャ',
      image: '/images/items/friend-point/21.png',
    },
    {
      id: 'friend-point-koisuru-sailor-beret',
      rarity: 'SR',
      category: 'あたま',
      name: '恋するセーラーベレー帽',
      image: '/images/items/friend-point/22.png',
    },
    {
      id: 'friend-point-koboreta-kakigori',
      rarity: 'SR',
      category: 'あたま',
      name: 'こぼれたかき氷',
      image: '/images/items/friend-point/23.png',
    },
    {
      id: 'friend-point-big-white-ribbon',
      rarity: 'SR',
      category: 'あたま',
      name: 'おおきな白リボン',
      image: '/images/items/friend-point/24.png',
    },

    // SR 衣装
    {
      id: 'friend-point-aozora-check-onepiece',
      rarity: 'SR',
      category: '衣装',
      name: '青空チェックワンピ',
      image: '/images/items/friend-point/25.png',
    },
    {
      id: 'friend-point-amakara-lady-line',
      rarity: 'SR',
      category: '衣装',
      name: '甘辛レディライン',
      image: '/images/items/friend-point/26.png',
    },

    // SR めがね
    {
      id: 'friend-point-silver-boston-glasses',
      rarity: 'SR',
      category: 'めがね',
      name: 'シルバーボストン',
      image: '/images/items/friend-point/27.png',
    },
    {
      id: 'friend-point-square-glasses',
      rarity: 'SR',
      category: 'めがね',
      name: 'スクエアメガネ',
      image: '/images/items/friend-point/28.png',
    },

    // SR 目
    {
      id: 'friend-point-tareme-green',
      rarity: 'SR',
      category: '目',
      name: 'タレ目(グリーン)',
      image: '/images/items/friend-point/29.png',
    },
    {
      id: 'friend-point-jitome-red',
      rarity: 'SR',
      category: '目',
      name: 'ジト目(レッド)',
      image: '/images/items/friend-point/30.png',
    },
    {
      id: 'friend-point-fuseme-yellow',
      rarity: 'SR',
      category: '目',
      name: '伏せ目(イエロー)',
      image: '/images/items/friend-point/31.png',
    },
    {
      id: 'friend-point-iyashi-tareme-white',
      rarity: 'SR',
      category: '目',
      name: '癒しタレ目(ホワイト)',
      image: '/images/items/friend-point/32.png',
    },

    // SR メイク
    {
      id: 'friend-point-yoidore-hoppe',
      rarity: 'SR',
      category: 'メイク',
      name: '酔いどれほっぺ',
      image: '/images/items/friend-point/33.png',
    },

    // SR チェキフレーム
    {
      id: 'friend-point-plumeria-resort',
      rarity: 'SR',
      category: 'チェキフレーム',
      name: 'プルメリアリゾート',
      image: '/images/items/friend-point/34.png',
    },
    {
      id: 'friend-point-mizushibuki',
      rarity: 'SR',
      category: 'チェキフレーム',
      name: '水しぶき',
      image: '/images/items/friend-point/35.png',
    },

    // SR イベント
    {
      id: 'friend-point-event-shooting-gallery-aimy',
      rarity: 'SR',
      category: 'イベント',
      name: '射的屋さんアイミー',
      image: '/images/items/friend-point/36.png',
    },
    {
      id: 'friend-point-event-childhood-memory-place',
      rarity: 'SR',
      category: 'イベント',
      name: '幼馴染と思い出の場所',
      image: '/images/items/friend-point/37.png',
    },

    // SR 背景
    {
      id: 'friend-point-after-rain-park',
      rarity: 'SR',
      category: '背景',
      name: '雨上がりの公園',
      image: '/images/items/friend-point/38.png',
    },
    {
      id: 'friend-point-fashionable-night-pool',
      rarity: 'SR',
      category: '背景',
      name: 'おしゃれなナイトプール',
      image: '/images/items/friend-point/39.png',
    },
    {
      id: 'friend-point-that-summer-station',
      rarity: 'SR',
      category: '背景',
      name: 'あの夏の駅',
      image: '/images/items/friend-point/40.png',
    },
    {
      id: 'friend-point-resort-beach',
      rarity: 'SR',
      category: '背景',
      name: 'リゾートビーチ',
      image: '/images/items/friend-point/41.png',
    },
  ],
}

export default gacha