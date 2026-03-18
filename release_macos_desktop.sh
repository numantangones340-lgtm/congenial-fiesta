#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_PATH="$ROOT_DIR/dist/GuitarAmpRecorder.app"
IDENTITY="${1:--}"
KEYCHAIN_PROFILE="${2:-}"
TEAM_ID="${3:-}"

cd "$ROOT_DIR"

if [[ ! -x ".venv/bin/python" ]]; then
  echo "Hata: .venv bulunamadi. Once README'deki kurulum adimlarini calistirin."
  exit 1
fi

if [[ -n "$KEYCHAIN_PROFILE" && -z "$TEAM_ID" ]]; then
  echo "Hata: notarization icin KEYCHAIN_PROFILE ile birlikte TEAM_ID de verilmeli."
  echo "Kullanim:"
  echo '  ./release_macos_desktop.sh "<Developer ID Application: NAME (TEAMID)>" <KEYCHAIN_PROFILE> <TEAM_ID>'
  exit 1
fi

if [[ -n "$KEYCHAIN_PROFILE" && "$IDENTITY" == "-" ]]; then
  echo "Hata: notarization ad-hoc imza ile yapilamaz."
  echo 'Developer ID identity verin: ./release_macos_desktop.sh "<Developer ID Application: NAME (TEAMID)>" <KEYCHAIN_PROFILE> <TEAM_ID>'
  exit 1
fi

if [[ ! -d "$APP_PATH" ]]; then
  echo "Uygulama paketi bulunamadi, build aliniyor..."
  ./build_macos_app.sh
else
  echo "Mevcut app paketi kullaniliyor: $APP_PATH"
fi

echo
if [[ "$IDENTITY" == "-" ]]; then
  echo "Ad-hoc imza uygulanacak."
else
  echo "Developer ID ile imza uygulanacak: $IDENTITY"
fi
./sign_macos_app.sh "$APP_PATH" "$IDENTITY"

if [[ -n "$KEYCHAIN_PROFILE" ]]; then
  echo
  echo "Notarization baslatiliyor..."
  ./notarize_macos_app.sh "$APP_PATH" "$KEYCHAIN_PROFILE" "$TEAM_ID"
fi

echo
./package_macos_release.sh

echo
DIST_ZIP="$ROOT_DIR/dist/GuitarAmpRecorder-macOS.zip"
DESKTOP_ZIP="$HOME/Desktop/GuitarAmpRecorder-macOS.zip"
if [[ -f "$DESKTOP_ZIP" && -f "$DIST_ZIP" && "$DESKTOP_ZIP" -nt "$DIST_ZIP" ]]; then
  echo "Hazir. Paylasilabilir paket masaustunde:"
  echo "  $DESKTOP_ZIP"
else
  echo "Hazir. Paylasilabilir paket burada:"
  echo "  $DIST_ZIP"
fi
