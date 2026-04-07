#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

SIGN_IDENTITY="${1:-}"
NOTARY_PROFILE="${2:-}"
TEAM_ID="${3:-}"
APP_PATH="$ROOT_DIR/dist/GuitarAmpRecorder.app"
ZIP_PATH="$ROOT_DIR/dist/GuitarAmpRecorder-macOS.zip"
ZIP_SHA_PATH="${ZIP_PATH}.sha256"
DESKTOP_ZIP="$HOME/Desktop/GuitarAmpRecorder-macOS.zip"
DESKTOP_ZIP_SHA="$HOME/Desktop/GuitarAmpRecorder-macOS.zip.sha256"

./build_macos_app.sh

if [ -n "$SIGN_IDENTITY" ]; then
  ./sign_macos_app.sh "$APP_PATH" "$SIGN_IDENTITY"
else
  ./sign_macos_app.sh "$APP_PATH"
fi

if [ -n "$NOTARY_PROFILE" ] || [ -n "$TEAM_ID" ]; then
  if [ -z "$NOTARY_PROFILE" ] || [ -z "$TEAM_ID" ]; then
    echo "HATA: Notarization icin hem profile hem team id gerekli." >&2
    exit 1
  fi
  if [ -z "$SIGN_IDENTITY" ]; then
    echo "HATA: Notarization icin Developer ID identity parametresi de gerekli." >&2
    exit 1
  fi
  ./notarize_macos_app.sh "$APP_PATH" "$NOTARY_PROFILE" "$TEAM_ID"
fi

./package_macos_release.sh

if [ ! -f "$ZIP_PATH" ]; then
  echo "HATA: Release zip bulunamadi: $ZIP_PATH" >&2
  exit 1
fi

if [ ! -f "$ZIP_SHA_PATH" ]; then
  echo "HATA: Release checksum bulunamadi: $ZIP_SHA_PATH" >&2
  exit 1
fi

echo "Release hazir:"
echo "- App: $APP_PATH"
echo "- Zip: $ZIP_PATH"
echo "- Zip SHA256: $ZIP_SHA_PATH"
if [ -f "$DESKTOP_ZIP" ]; then
  echo "- Masaustu kopyasi: $DESKTOP_ZIP"
else
  echo "- Masaustu kopyasi: olusturulamadi, dist zip hazir: $ZIP_PATH"
fi

if [ -f "$DESKTOP_ZIP_SHA" ]; then
  echo "- Masaustu SHA256: $DESKTOP_ZIP_SHA"
else
  echo "- Masaustu SHA256: olusturulamadi, dist checksum hazir: $ZIP_SHA_PATH"
fi
