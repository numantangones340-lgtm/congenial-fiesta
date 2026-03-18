#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_PATH="${1:-$ROOT_DIR/dist/GuitarAmpRecorder.app}"
KEYCHAIN_PROFILE="${2:-}"
TEAM_ID="${3:-}"

if [[ -z "$KEYCHAIN_PROFILE" || -z "$TEAM_ID" ]]; then
  echo "Kullanim:"
  echo "  ./notarize_macos_app.sh [APP_PATH] <KEYCHAIN_PROFILE> <TEAM_ID>"
  echo
  echo "Ornek:"
  echo "  ./notarize_macos_app.sh ./dist/GuitarAmpRecorder.app AC_PROFILE ABCD123456"
  exit 1
fi

if [[ ! -d "$APP_PATH" ]]; then
  echo "Hata: app bulunamadi: $APP_PATH"
  exit 1
fi

if ! command -v xcrun >/dev/null 2>&1; then
  echo "Hata: xcrun bulunamadi (Xcode Command Line Tools gerekli)."
  exit 1
fi

if ! command -v codesign >/dev/null 2>&1; then
  echo "Hata: codesign bulunamadi."
  exit 1
fi

SIGNATURE_INFO="$(codesign -dv --verbose=4 "$APP_PATH" 2>&1 || true)"
if grep -q "Signature=adhoc" <<<"$SIGNATURE_INFO"; then
  echo "Hata: app ad-hoc imzali. Notarization icin Developer ID Application sertifikasi ile imzalanmali."
  exit 1
fi

ZIP_PATH="$ROOT_DIR/dist/$(basename "$APP_PATH" .app)-notarize.zip"

echo "Zipleme: $ZIP_PATH"
rm -f "$ZIP_PATH"
ditto -c -k --keepParent "$APP_PATH" "$ZIP_PATH"

echo "Notarization submit (wait):"
xcrun notarytool submit "$ZIP_PATH" --keychain-profile "$KEYCHAIN_PROFILE" --team-id "$TEAM_ID" --wait

echo
echo "Staple:"
xcrun stapler staple "$APP_PATH"

echo
echo "Final assess:"
spctl --assess --type execute --verbose=4 "$APP_PATH"
echo "Notarization tamam."
