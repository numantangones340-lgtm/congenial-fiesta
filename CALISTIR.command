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

calc_dep_stamp() {
  local pyv reqhash
  pyv="$(python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")' 2>/dev/null || echo unknown)"
  if command -v shasum >/dev/null 2>&1; then
    reqhash="$(shasum requirements.txt | awk '{print $1}')"
  else
    reqhash="$(python - <<'PY'
import hashlib
from pathlib import Path
p = Path("requirements.txt")
print(hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else "missing")
PY
)"
  fi
  echo "python=${pyv};req=${reqhash}"
}

if [ -d ".venv" ]; then
  source .venv/bin/activate

  if ! python - <<'PY' >/dev/null 2>&1
import sys
ok = sys.version_info >= (3, 10)
try:
    import tkinter as tk
    ok = ok and (float(tk.TkVersion) >= 8.6)
except Exception:
    ok = False
raise SystemExit(0 if ok else 1)
PY
  then
    deactivate >/dev/null 2>&1 || true
    BACKUP_DIR=".venv_py39_backup_$(date +%Y%m%d_%H%M%S)"
    echo "Mevcut sanal ortam GUI ile uyumsuz görünüyor. Yedekleniyor: ${BACKUP_DIR}"
    mv .venv "${BACKUP_DIR}"
  fi
fi

if [ ! -d ".venv" ]; then
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
else
  source .venv/bin/activate
fi

export PIP_NO_CACHE_DIR=1
export PIP_DISABLE_PIP_VERSION_CHECK=1
DEPS_STAMP_FILE=".venv/.deps_stamp"
CURRENT_DEPS_STAMP="$(calc_dep_stamp)"
PREV_DEPS_STAMP="$(cat "${DEPS_STAMP_FILE}" 2>/dev/null || true)"

if [ "${CURRENT_DEPS_STAMP}" != "${PREV_DEPS_STAMP}" ]; then
  echo "Gerekli kütüphaneler yükleniyor..."
  pip install -r requirements.txt
  printf "%s\n" "${CURRENT_DEPS_STAMP}" > "${DEPS_STAMP_FILE}"
else
  echo "Kütüphaneler güncel, kurulum adımı atlandı."
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "UYARI: ffmpeg bulunamadı. MP3 oluşturma atlanır, WAV dosyaları yine kaydedilir."
fi

MODE="${1:-auto}"
if [ "$MODE" = "cli" ]; then
  echo "Terminal sürümü açılıyor..."
  python cli_app.py
elif [ "$MODE" = "quick" ]; then
  echo "Hızlı terminal sürümü açılıyor..."
  python cli_app.py --quick
elif [ "$MODE" = "gui" ]; then
  echo "Pencere sürümü açılıyor..."
  python app.py
else
  echo "Pencere sürümü açılıyor..."
  if ! python app.py; then
    echo "GUI açılamadı (tkinter uyumluluk sorunu). CLI sürümüne geçiliyor..."
    python cli_app.py
  fi
fi
