#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 2 ] || [ "$#" -gt 3 ]; then
  echo "Kullanim: $0 <app-path> <notary-profile> [team-id]" >&2
  exit 1
fi

APP_PATH="$1"
PROFILE_NAME="$2"
TEAM_ID="${3:-}"

if [ ! -d "$APP_PATH" ]; then
  echo "HATA: Uygulama paketi bulunamadi: $APP_PATH" >&2
  exit 1
fi

if ! command -v xcrun >/dev/null 2>&1; then
  echo "HATA: xcrun komutu bulunamadi." >&2
  exit 1
fi

TMP_DIR="$(mktemp -d)"
ZIP_PATH="$TMP_DIR/$(basename "$APP_PATH").zip"
cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

echo "Notarization icin zip hazirlaniyor..."
ditto -c -k --sequesterRsrc --keepParent "$APP_PATH" "$ZIP_PATH"

if [ -n "$TEAM_ID" ]; then
  echo "Notarization baslatiliyor (team: $TEAM_ID)..."
else
  echo "Notarization baslatiliyor..."
fi

xcrun notarytool submit "$ZIP_PATH" --keychain-profile "$PROFILE_NAME" --wait

echo "Staple islemi yapiliyor..."
xcrun stapler staple -v "$APP_PATH"
xcrun stapler validate -v "$APP_PATH"

if command -v spctl >/dev/null 2>&1; then
  spctl -a -vv -t exec "$APP_PATH"
fi

echo "Notarization tamamlandi."
