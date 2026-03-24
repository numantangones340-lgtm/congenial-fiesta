#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo "Kullanim: $0 <app-path> <codesign-identity>" >&2
  exit 1
fi

APP_PATH="$1"
IDENTITY="$2"

if [ ! -d "$APP_PATH" ]; then
  echo "HATA: Uygulama paketi bulunamadi: $APP_PATH" >&2
  exit 1
fi

if ! command -v codesign >/dev/null 2>&1; then
  echo "HATA: codesign komutu bulunamadi." >&2
  exit 1
fi

echo "Uygulama imzalaniyor: $APP_PATH"
/usr/bin/codesign \
  --force \
  --deep \
  --timestamp \
  --options runtime \
  --sign "$IDENTITY" \
  "$APP_PATH"

echo "Imza dogrulamasi yapiliyor..."
/usr/bin/codesign --verify --deep --strict --verbose=2 "$APP_PATH"

echo "Imzalama tamamlandi."
