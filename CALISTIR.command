#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "Guitar Amp Recorder baslatiliyor..."

pick_python() {
  for candidate in python3.13 python3.12 python3.11 python3.10 python3.9 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

PYTHON_BIN="$(pick_python || true)"
if [ -z "${PYTHON_BIN}" ]; then
  echo "HATA: Python bulunamadi. Lutfen Python 3.10+ kurun."
  read -n 1 -s -r -p "Cikmak icin bir tusa basin..."
  echo
  exit 1
fi

if ! "$PYTHON_BIN" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY
then
  echo "UYARI: Python surumu 3.10 altinda. GUI uyumsuz olabilir, CLI ile devam edilebilir."
fi

if [ ! -d ".venv" ]; then
  echo "Sanal ortam olusturuluyor..."
  "$PYTHON_BIN" -m venv .venv
fi

source .venv/bin/activate
echo "Gerekli kutuphaneler yukleniyor..."
python -m pip install --upgrade pip >/dev/null
pip install -r requirements.txt

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "UYARI: ffmpeg bulunamadi. MP3 olusturma atlanir, WAV dosyalari yine kaydedilir."
fi

MODE="${1:-auto}"
if [ "$MODE" = "cli" ]; then
  echo "Terminal surumu aciliyor..."
  python cli_app.py
elif [ "$MODE" = "gui" ]; then
  echo "Pencere surumu aciliyor..."
  python app.py
else
  if python - <<'PY' >/dev/null 2>&1
import tkinter as tk
root = tk.Tk()
root.withdraw()
root.destroy()
PY
  then
    echo "Pencere surumu aciliyor..."
    python app.py
  else
    echo "GUI acilamadi (tkinter uyumluluk sorunu). CLI surumune geciliyor..."
    python cli_app.py
  fi
fi
