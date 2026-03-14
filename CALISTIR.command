#!/bin/bash
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

pause_and_exit() {
  local code="${1:-0}"
  echo
  read -n 1 -s -r -p "Kapatmak için bir tusa basin..."
  echo
  exit "$code"
}

echo "Guitar Amp Recorder başlatılıyor..."

pick_python() {
  for candidate in /opt/homebrew/bin/python3.11 python3.13 python3.12 python3.11 python3.10 python3.9 python3; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -V >/dev/null 2>&1; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

if [ -x ".venv/bin/python" ] && [ -f ".venv/bin/activate" ] && .venv/bin/python - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
then
  source .venv/bin/activate
else
  if [ -d ".venv" ]; then
    rm -rf .venv
  fi
  PYTHON_BIN="$(pick_python || true)"
  if [ -z "${PYTHON_BIN}" ]; then
    echo "HATA: Python bulunamadı. Lütfen Python 3.9+ kurun."
    pause_and_exit 1
  fi

  if ! "$PYTHON_BIN" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 9) else 1)
PY
  then
    echo "HATA: Python 3.9+ gerekir."
    pause_and_exit 1
  fi

  if ! "$PYTHON_BIN" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
  then
    echo "BİLGİ: Python 3.11+ önerilir (mevcut sürüm yine çalışabilir)."
  fi

  echo "Sanal ortam oluşturuluyor..."
  "$PYTHON_BIN" -m venv .venv
  source .venv/bin/activate
fi

echo "Gerekli kütüphaneler yükleniyor..."
export PIP_NO_CACHE_DIR=1
export PIP_DISABLE_PIP_VERSION_CHECK=1
if ! pip install -r requirements.txt; then
  echo "HATA: Kutuphaneler yuklenemedi."
  pause_and_exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "UYARI: ffmpeg bulunamadı. MP3 oluşturma atlanır, WAV dosyaları yine kaydedilir."
fi

MODE="${1:-auto}"
if [ "$MODE" = "cli" ]; then
  echo "Terminal sürümü açılıyor..."
  python cli_app.py || pause_and_exit 1
elif [ "$MODE" = "gui" ]; then
  echo "Pencere sürümü açılıyor..."
  python app.py || pause_and_exit 1
else
  if python - <<'PY' >/dev/null 2>&1
import tkinter as tk
root = tk.Tk()
root.withdraw()
root.destroy()
PY
  then
    echo "Pencere sürümü açılıyor..."
    python app.py || pause_and_exit 1
  else
    echo "GUI acilamadi (tkinter uyumluluk sorunu). Terminal surumune geciliyor..."
    python cli_app.py || pause_and_exit 1
  fi
fi

pause_and_exit 0
