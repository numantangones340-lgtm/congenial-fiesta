#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_PATH="${1:-$ROOT_DIR/dist/GuitarAmpRecorder.app}"
PROFILE_NAME="${2:-}"
TEAM_ID="${3:-}"
TMP_ZIP="$ROOT_DIR/dist/$(basename "$APP_PATH" .app)-notarize.zip"

if [ ! -d "$APP_PATH" ]; then
  echo "HATA: Uygulama paketi bulunamadi: $APP_PATH" >&2
  exit 1
fi

if [ -z "$PROFILE_NAME" ] || [ -z "$TEAM_ID" ]; then
  echo "Kullanim: $0 <app-path> <notary-profile> <team-id>" >&2
  exit 1
fi

mkdir -p "$ROOT_DIR/dist"
rm -f "$TMP_ZIP"
ditto -c -k --sequesterRsrc --keepParent "$APP_PATH" "$TMP_ZIP"

echo "Notarization gonderiliyor: $TMP_ZIP"
xcrun notarytool submit "$TMP_ZIP" --keychain-profile "$PROFILE_NAME" --team-id "$TEAM_ID" --wait
xcrun stapler staple "$APP_PATH"
xcrun stapler validate "$APP_PATH"

echo "Notarization tamamlandi: $APP_PATH"
