// DMMアフィリエイト審査中は false のままにします。
// 承認後、ChatGPTへDMMで発行された広告HTMLを渡し、各スロットへ設定します。
export const affiliateAds = {
  enabled: false,
  disclosure:
    '当サイトはアフィリエイト広告を利用しています。広告を経由して商品・サービスが購入された場合、当サイトに報酬が発生することがあります。',
  slots: {
    homePrimary: {
      enabled: false,
      html: '',
    },
    homeSecondary: {
      enabled: false,
      html: '',
    },
    gachaList: {
      enabled: false,
      html: '',
    },
    gachaDetail: {
      enabled: false,
      html: '',
    },
    itemList: {
      enabled: false,
      html: '',
    },
    itemDetail: {
      enabled: false,
      html: '',
    },
  },
}

export function getAffiliateAd(slotName) {
  if (!affiliateAds.enabled) {
    return null
  }

  const slot = affiliateAds.slots[slotName]

  if (!slot?.enabled || !slot.html?.trim()) {
    return null
  }

  return slot
}
