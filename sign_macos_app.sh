#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_PATH="${1:-$ROOT_DIR/dist/GuitarAmpRecorder.app}"
IDENTITY="${2:--}"

if [[ ! -d "$APP_PATH" ]]; then
  echo "Hata: app bulunamadi: $APP_PATH"
  echo "Once build alin: ./build_macos_app.sh"
  exit 1
fi

echo "Signing app: $APP_PATH"
echo "Identity: $IDENTITY"

if [[ "$IDENTITY" == "-" ]]; then
  codesign --force --deep --sign "$IDENTITY" "$APP_PATH"
else
  codesign --force --deep --options runtime --timestamp --sign "$IDENTITY" "$APP_PATH"
fi

echo
echo "codesign verify:"
codesign --verify --deep --strict "$APP_PATH"
codesign -dv --verbose=4 "$APP_PATH" 2>&1 | sed -n '1,30p'

echo
echo "spctl assess:"
if spctl --assess --type execute --verbose=4 "$APP_PATH"; then
  echo "spctl: accepted"
else
  echo "spctl: rejected (ad-hoc imzada beklenebilir)."
fi
