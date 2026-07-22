const dmmDoujinWidget = {
  provider: 'dmm-widget',
  desktopId: '1e3cfaeeb93fd3fc35adca4080f0e79d',
  mobileId: '531dff1a4c72ec1b914fb929bc6f4882',
}

export const affiliateAds = {
  enabled: true,
  disclosure:
    '当サイトは18歳以上の方を対象としたアフィリエイト広告を利用しています。広告を経由して商品・サービスが購入された場合、当サイトに報酬が発生することがあります。',
  slots: {
    homePrimary: {
      enabled: true,
      ...dmmDoujinWidget,
    },
    homeSecondary: {
      enabled: false,
      ...dmmDoujinWidget,
    },
    gachaList: {
      enabled: true,
      ...dmmDoujinWidget,
    },
    gachaDetail: {
      enabled: true,
      ...dmmDoujinWidget,
    },
    itemList: {
      enabled: true,
      ...dmmDoujinWidget,
    },
    itemDetail: {
      enabled: true,
      ...dmmDoujinWidget,
    },
  },
}

export function getAffiliateAd(slotName) {
  if (!affiliateAds.enabled) {
    return null
  }

  const slot = affiliateAds.slots[slotName]

  if (!slot?.enabled) {
    return null
  }

  if (slot.provider === 'dmm-widget') {
    return slot.desktopId && slot.mobileId ? slot : null
  }

  if (!slot.html?.trim()) {
    return null
  }

  return slot
}
