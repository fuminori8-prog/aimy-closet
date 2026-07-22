#!/bin/zsh
set -e
cd "$(dirname "$0")"
exec python3 scripts/aimy-crop/repair_existing_app.py
