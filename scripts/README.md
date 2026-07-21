# Aimy Closet scripts

現在使用している主なスクリプトです。

- `generate-sitemap.js`: ビルド前にサイトマップを生成
- `aimy-crop/add_gacha_app.py`: スクショからガチャページを生成・公開するローカルツール
- `aimy-crop/add_gacha.html`: ガチャ追加ツールの確認画面
- `aimy-crop/detect_cards.py`: アイテム画像の検出処理
- `aimy-crop/export_cards.py`: 画像切り抜きの共通処理
- `aimy-crop/macos_ocr.m`: macOS Vision OCR

ガチャ追加は、プロジェクト直下の `ガチャ追加.command` を開くか、次を実行します。

```bash
npm run add-gacha
```

`workspace` と `.bin` は自動生成され、Gitには保存しません。
