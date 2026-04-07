#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "${SCRIPT_DIR}"

APP_NAME="GuitarAmpRecorder"
APP_DIST="dist/${APP_NAME}.app"
ZIP_DIST="dist/${APP_NAME}-macOS.zip"
ZIP_SHA_DIST="${ZIP_DIST}.sha256"
APP_INSTALL_DIR="${HOME}/Applications"
APP_INSTALL_PATH="${APP_INSTALL_DIR}/${APP_NAME}.app"
DESKTOP_ZIP="${HOME}/Desktop/${APP_NAME}-macOS-latest.zip"
DESKTOP_ZIP_SHA="${DESKTOP_ZIP}.sha256"
ARCHIVE_DIR="${SCRIPT_DIR}/cleanup_$(date +%Y%m%d-%H%M%S)"

echo "1) Build basliyor..."
./build_macos_app.sh

if [ ! -d "${APP_DIST}" ]; then
  echo "HATA: Build sonrasi app bulunamadi: ${APP_DIST}"
  exit 1
fi

if [ -f "${ZIP_DIST}" ]; then
  python3 "${SCRIPT_DIR}/scripts/write_sha256.py" "${ZIP_DIST}"
fi

echo "2) Uygulama kurulum klasoru hazirlaniyor..."
mkdir -p "${APP_INSTALL_DIR}"
rm -rf "${APP_INSTALL_PATH}"
ditto "${APP_DIST}" "${APP_INSTALL_PATH}"
xattr -dr com.apple.quarantine "${APP_INSTALL_PATH}" >/dev/null 2>&1 || true

echo "3) Masaustune son zip kopyalaniyor..."
if [ -f "${ZIP_DIST}" ]; then
  cp -f "${ZIP_DIST}" "${DESKTOP_ZIP}"
  xattr -d com.apple.quarantine "${DESKTOP_ZIP}" >/dev/null 2>&1 || true
  if [ -f "${ZIP_SHA_DIST}" ]; then
    cp -f "${ZIP_SHA_DIST}" "${DESKTOP_ZIP_SHA}"
  fi
fi

echo "4) Eski indirilen kopyalar arsivleniyor..."
mkdir -p "${ARCHIVE_DIR}"
for path in \
  "${HOME}/Downloads/${APP_NAME}.app" \
  "${HOME}/Downloads/${APP_NAME}-2.app" \
  "${HOME}/Downloads/${APP_NAME}-macOS.zip" \
  "${HOME}/Downloads/${APP_NAME}-macOS.zip.sha256"; do
  if [ -e "${path}" ]; then
    mv "${path}" "${ARCHIVE_DIR}/"
  fi
done

echo "5) Masaustu baslaticisi olusturuluyor..."
./install_desktop_shortcut.sh

echo
echo "Kurulum tamamlandi."
echo "Uygulama: ${APP_INSTALL_PATH}"
echo "Masaustu baslatici: ${HOME}/Desktop/${APP_NAME}.command"
if [ -f "${DESKTOP_ZIP}" ]; then
  echo "Masaustu zip: ${DESKTOP_ZIP}"
fi
if [ -f "${DESKTOP_ZIP_SHA}" ]; then
  echo "Masaustu SHA256: ${DESKTOP_ZIP_SHA}"
fi
echo "Arsivlenen eski dosyalar: ${ARCHIVE_DIR}"
