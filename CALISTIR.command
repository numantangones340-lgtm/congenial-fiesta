#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "Guitar Amp Recorder baslatiliyor..."

if ! command -v python3 >/dev/null 2>&1; then
  echo "HATA: python3 bulunamadi. Lutfen Python 3.10+ kurun."
  read -n 1 -s -r -p "Cikmak icin bir tusa basin..."
  echo
  exit 1
fi

if [ ! -d ".venv" ]; then
  echo "Sanal ortam olusturuluyor..."
  python3 -m venv .venv
fi

source .venv/bin/activate

echo "Gerekli kutuphaneler yukleniyor..."
python -m pip install --upgrade pip >/dev/null
pip install -r requirements.txt

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "UYARI: ffmpeg bulunamadi. MP3 olusturma atlanir, WAV dosyalari yine kaydedilir."
fi

MODE="${1:-gui}"
if [ "$MODE" = "cli" ]; then
  echo "Terminal surumu aciliyor..."
  python cli_app.py
else
  echo "Pencere surumu aciliyor..."
  python app.py
fi
