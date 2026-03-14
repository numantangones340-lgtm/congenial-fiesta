#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET_FILE="${HOME}/Desktop/GuitarAmpRecorder.command"
cat > "${TARGET_FILE}" <<EOF
#!/bin/bash
cd "${SCRIPT_DIR}"
APP_BIN="\${HOME}/Applications/GuitarAmpRecorder.app/Contents/MacOS/GuitarAmpRecorder"
if [ -x "\${APP_BIN}" ]; then
  exec "\${APP_BIN}"
fi
exec "./CALISTIR.command" auto
EOF
chmod +x "${TARGET_FILE}"

# macOS bazen indirilen dosyalari karantinaya alabilir; varsa temizle.
xattr -d com.apple.quarantine "${TARGET_FILE}" >/dev/null 2>&1 || true

echo "Masaustu kisayolu hazir: ${TARGET_FILE}"
echo "Simdi masaustundeki GuitarAmpRecorder.command dosyasina cift tiklayabilirsiniz."
