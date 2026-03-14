#!/usr/bin/env bash
set -euo pipefail

# Geriye uyumluluk icin eski komut bu script'ten de calismaya devam eder.
exec "$(cd "$(dirname "$0")" && pwd)/build_macos_app.sh"
