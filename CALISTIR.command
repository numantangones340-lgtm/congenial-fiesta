#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "Guitar Amp Recorder başlatılıyor..."

pick_python() {
  for candidate in python3.13 python3.12 python3.11 python3.10 python3.9 python3; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -V >/dev/null 2>&1; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

if [ -d ".venv" ]; then
  source .venv/bin/activate
else
  PYTHON_BIN="$(pick_python || true)"
  if [ -z "${PYTHON_BIN}" ]; then
    echo "HATA: Python bulunamadı. Lütfen Python 3.9+ kurun."
    read -n 1 -s -r -p "Çıkmak için bir tuşa basın..."
    echo
    exit 1
  fi

  if ! "$PYTHON_BIN" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 9) else 1)
PY
  then
    echo "HATA: Python 3.9+ gerekir."
    read -n 1 -s -r -p "Çıkmak için bir tuşa basın..."
    echo
    exit 1
  fi

  if ! "$PYTHON_BIN" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY
  then
    echo "BİLGİ: Python 3.10+ önerilir (mevcut sürüm yine çalışabilir)."
  fi

  echo "Sanal ortam oluşturuluyor..."
  "$PYTHON_BIN" -m venv .venv
  source .venv/bin/activate
fi

echo "Gerekli kütüphaneler yükleniyor..."
export PIP_NO_CACHE_DIR=1
export PIP_DISABLE_PIP_VERSION_CHECK=1
pip install -r requirements.txt

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "UYARI: ffmpeg bulunamadı. MP3 oluşturma atlanır, WAV dosyaları yine kaydedilir."
fi

MODE="${1:-auto}"
if [ "$MODE" = "cli" ]; then
  echo "Terminal sürümü açılıyor..."
  python cli_app.py
elif [ "$MODE" = "gui" ]; then
  echo "Pencere sürümü açılıyor..."
  python app.py
else
  if python - <<'PY' >/dev/null 2>&1
import tkinter as tk
root = tk.Tk()
root.withdraw()
root.destroy()
PY
  then
    echo "Pencere sürümü açılıyor..."
    python app.py
  else
    echo "GUI açılamadı (tkinter uyumluluk sorunu). CLI sürümüne geçiliyor..."
    python cli_app.py
  fi
fi
