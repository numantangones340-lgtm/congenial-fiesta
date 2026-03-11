#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

if [[ ! -x ".venv/bin/python" ]]; then
  echo "Hata: .venv bulunamadı. Önce README'deki kurulum adımlarını çalıştırın."
  exit 1
fi

source .venv/bin/activate

if ! command -v pyinstaller >/dev/null 2>&1; then
  echo "Hata: pyinstaller kurulu değil."
  echo "Kurulum: pip install pyinstaller"
  exit 1
fi

export PYINSTALLER_CONFIG_DIR="$ROOT_DIR/.pyinstaller"

pyinstaller --noconfirm GuitarAmpRecorder.spec

echo "Hazır: $ROOT_DIR/dist/GuitarAmpRecorder.app"
