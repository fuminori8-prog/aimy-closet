#!/bin/zsh
set -e
cd "$(dirname "$0")"
exec python3 scripts/aimy-crop/redetect_gacha_app.py
