#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SOURCE_FILE="${SCRIPT_DIR}/CALISTIR.command"
TARGET_FILE="${HOME}/Desktop/GuitarAmpRecorder.command"
QUICK_TARGET_FILE="${HOME}/Desktop/GuitarAmpRecorder-Quick.command"

if [ ! -f "${SOURCE_FILE}" ]; then
  echo "HATA: CALISTIR.command bulunamadi: ${SOURCE_FILE}"
  exit 1
fi

cat > "${TARGET_FILE}" <<EOF
#!/usr/bin/env bash
set -e
cd "${SCRIPT_DIR}"
./CALISTIR.command
EOF
chmod +x "${TARGET_FILE}"

cat > "${QUICK_TARGET_FILE}" <<EOF
#!/usr/bin/env bash
set -e
cd "${SCRIPT_DIR}"
./CALISTIR.command quick
EOF
chmod +x "${QUICK_TARGET_FILE}"

# macOS bazen indirilen dosyalari karantinaya alabilir; varsa temizle.
xattr -d com.apple.quarantine "${TARGET_FILE}" >/dev/null 2>&1 || true
xattr -d com.apple.quarantine "${QUICK_TARGET_FILE}" >/dev/null 2>&1 || true

echo "Masaustu kisayolu hazir: ${TARGET_FILE}"
echo "Hizli kayit kisayolu hazir: ${QUICK_TARGET_FILE}"
echo "GUI/normal acilis icin: GuitarAmpRecorder.command"
echo "Sorusuz quick kayit icin: GuitarAmpRecorder-Quick.command"
