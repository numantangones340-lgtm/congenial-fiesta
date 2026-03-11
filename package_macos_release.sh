#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

APP_PATH="$ROOT_DIR/dist/GuitarAmpRecorder.app"
ZIP_PATH="$ROOT_DIR/dist/GuitarAmpRecorder-macOS.zip"
DESKTOP_ZIP="$HOME/Desktop/GuitarAmpRecorder-macOS.zip"

if [ ! -d "$APP_PATH" ]; then
  echo "Uygulama paketi bulunamadi, once build aliniyor..."
  ./build_macos_app.sh
fi

rm -f "$ZIP_PATH"
ditto -c -k --sequesterRsrc --keepParent "$APP_PATH" "$ZIP_PATH"
cp "$ZIP_PATH" "$DESKTOP_ZIP"

echo "Hazir zip: $ZIP_PATH"
echo "Masaustune kopyalandi: $DESKTOP_ZIP"
