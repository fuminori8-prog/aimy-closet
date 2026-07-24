#!/bin/zsh
set -e
cd "$(dirname "$0")"
mkdir -p "ガチャスクショ投入/処理済み"
open "ガチャスクショ投入" >/dev/null 2>&1 || true
exec python3 scripts/aimy-crop/add_gacha_app.py
