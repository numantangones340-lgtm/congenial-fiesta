#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SOURCE_FILE="${SCRIPT_DIR}/CALISTIR.command"
TARGET_FILE="${HOME}/Desktop/GuitarAmpRecorder.command"

if [ ! -f "${SOURCE_FILE}" ]; then
  echo "HATA: CALISTIR.command bulunamadi: ${SOURCE_FILE}"
  exit 1
fi

cp "${SOURCE_FILE}" "${TARGET_FILE}"
chmod +x "${TARGET_FILE}"

# macOS bazen indirilen dosyalari karantinaya alabilir; varsa temizle.
xattr -d com.apple.quarantine "${TARGET_FILE}" >/dev/null 2>&1 || true

echo "Masaustu kisayolu hazir: ${TARGET_FILE}"
echo "Simdi masaustundeki GuitarAmpRecorder.command dosyasina cift tiklayabilirsiniz."
