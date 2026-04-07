#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

APP_PATH="$ROOT_DIR/dist/GuitarAmpRecorder.app"
ZIP_PATH="$ROOT_DIR/dist/GuitarAmpRecorder-macOS.zip"
ZIP_SHA_PATH="${ZIP_PATH}.sha256"
DESKTOP_ZIP="$HOME/Desktop/GuitarAmpRecorder-macOS.zip"
DESKTOP_ZIP_SHA="${DESKTOP_ZIP}.sha256"
EXPECTED_VERSION="$(tr -d '\r\n' < "$ROOT_DIR/VERSION" 2>/dev/null || printf '')"
CURRENT_APP_VERSION="$(
  python3 - <<'PY'
from pathlib import Path
import plistlib

info_path = Path("dist/GuitarAmpRecorder.app/Contents/Info.plist")
if not info_path.exists():
    print("")
else:
    with info_path.open("rb") as fh:
        info = plistlib.load(fh)
    print(info.get("CFBundleShortVersionString", ""))
PY
)"

if [ ! -d "$APP_PATH" ] || [ "$CURRENT_APP_VERSION" != "$EXPECTED_VERSION" ]; then
  echo "Uygulama paketi bulunamadi, once build aliniyor..."
  ./build_macos_app.sh
fi

rm -f "$ZIP_PATH"
ditto -c -k --sequesterRsrc --keepParent "$APP_PATH" "$ZIP_PATH"
python3 "$ROOT_DIR/scripts/write_sha256.py" "$ZIP_PATH"

echo "Hazir zip: $ZIP_PATH"
if cp "$ZIP_PATH" "$DESKTOP_ZIP" 2>/dev/null; then
  echo "Masaustune kopyalandi: $DESKTOP_ZIP"
  if cp "$ZIP_SHA_PATH" "$DESKTOP_ZIP_SHA" 2>/dev/null; then
    echo "SHA256 de masaustune kopyalandi: $DESKTOP_ZIP_SHA"
  else
    echo "Not: SHA256 masaustu kopyasi olusturulamadi. Checksum dist klasorunde hazir."
  fi
else
  echo "Not: Masaustu kopyasi olusturulamadi. Zip dosyasi dist klasorunde hazir."
fi
