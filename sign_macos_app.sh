#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_PATH="${1:-$ROOT_DIR/dist/GuitarAmpRecorder.app}"
SIGN_IDENTITY="${2:--}"

if [ ! -d "$APP_PATH" ]; then
  echo "HATA: Uygulama paketi bulunamadi: $APP_PATH" >&2
  exit 1
fi

echo "Codesign basliyor: $APP_PATH"
SIGN_ARGS=(--force --deep --sign "$SIGN_IDENTITY")
if [ "$SIGN_IDENTITY" != "-" ]; then
  SIGN_ARGS+=(--options runtime --timestamp)
fi

codesign "${SIGN_ARGS[@]}" "$APP_PATH"
codesign --verify --deep --strict --verbose=2 "$APP_PATH"

echo "Imzalama tamamlandi: $APP_PATH"
if [ "$SIGN_IDENTITY" = "-" ]; then
  echo "Not: ad-hoc imza kullanildi."
fi
