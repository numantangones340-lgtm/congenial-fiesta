#!/usr/bin/env bash
set -euo pipefail

APP_NAME="GuitarAmpRecorder"
ENTRY="app.py"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

rm -rf build dist "${APP_NAME}.spec"

pyinstaller --windowed --name "${APP_NAME}" "${ENTRY}"

cd dist
zip -r "${APP_NAME}-macOS.zip" "${APP_NAME}.app" >/dev/null

echo "Build tamam: dist/${APP_NAME}.app"
echo "Arsiv: dist/${APP_NAME}-macOS.zip"
