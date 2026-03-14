#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

./build_macos_app.sh
cp -f dist/GuitarAmpRecorder-macOS.zip "$HOME/Desktop/GuitarAmpRecorder-macOS.zip"

echo "Masaüstüne kopyalandı: $HOME/Desktop/GuitarAmpRecorder-macOS.zip"
