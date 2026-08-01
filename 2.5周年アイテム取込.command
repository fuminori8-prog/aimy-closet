#!/bin/zsh
set -e
cd "$(dirname "$0")"
export PYTHONDONTWRITEBYTECODE=1
exec python3 scripts/aimy-crop/historical_items_app.py
