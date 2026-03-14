#!/usr/bin/env bash
set -euo pipefail

APP_NAME="GuitarAmpRecorder"
ENTRY="app.py"

pick_python() {
  for candidate in /opt/homebrew/bin/python3.11 python3.11 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
      if "$candidate" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
      then
        echo "$candidate"
        return 0
      fi
    fi
  done
  return 1
}

PYTHON_BIN="$(pick_python || true)"
if [ -z "${PYTHON_BIN}" ]; then
  echo "HATA: Python 3.11+ bulunamadı."
  exit 1
fi

if [ -x ".venv/bin/python" ] && .venv/bin/python - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
then
  :
else
  rm -rf .venv
  "${PYTHON_BIN}" -m venv .venv
fi

source .venv/bin/activate
export PIP_DISABLE_PIP_VERSION_CHECK=1
export PYINSTALLER_CONFIG_DIR="${PWD}/.pyinstaller-cache"
mkdir -p "${PYINSTALLER_CONFIG_DIR}"

pip install -r requirements.txt
pip install pyinstaller

TCL_DIR=""
TK_DIR=""
TK_OUT="$(python - <<'PY'
import sys
import sysconfig
from pathlib import Path

roots = []
for base in [Path(sys.base_prefix), Path(sys.prefix)]:
    roots.extend([base, base / "lib", base / "Resources", base / "Resources" / "lib"])

stdlib = Path(sysconfig.get_paths().get("stdlib", ""))
if stdlib.exists():
    roots.extend([stdlib.parent, stdlib.parent / "lib"])

roots.extend(
    [
        Path("/opt/homebrew/opt/tcl-tk@8/lib"),
        Path("/opt/homebrew/opt/tcl-tk/lib"),
        Path("/opt/homebrew/Cellar/tcl-tk@8"),
        Path("/opt/homebrew/Cellar/tcl-tk"),
        Path("/Library/Frameworks/Python.framework/Versions") / f"{sys.version_info.major}.{sys.version_info.minor}" / "lib",
        Path("/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions")
        / f"{sys.version_info.major}.{sys.version_info.minor}"
        / "lib",
    ]
)

seen = set()
tcl_dir = None
tk_dir = None
for root in roots:
    root = root.resolve() if root.exists() else root
    if root in seen or not root.exists():
        continue
    seen.add(root)
    tcl_candidates = sorted(root.glob("tcl8.*"), reverse=True)
    if not tcl_candidates:
        continue
    for tcl in tcl_candidates:
        tk = tcl.parent / tcl.name.replace("tcl", "tk", 1)
        if tk.exists():
            tcl_dir = tcl
            tk_dir = tk
            break
    if tcl_dir and tk_dir:
        break

print(tcl_dir if tcl_dir else "")
print(tk_dir if tk_dir else "")
PY
)"

TCL_DIR="$(printf '%s\n' "${TK_OUT}" | sed -n '1p')"
TK_DIR="$(printf '%s\n' "${TK_OUT}" | sed -n '2p')"

PYI_ARGS=(--noconfirm --clean --windowed --name "${APP_NAME}")
if [ -n "${TCL_DIR}" ] && [ -d "${TCL_DIR}" ]; then
  PYI_ARGS+=(--add-data "${TCL_DIR}:lib/$(basename "${TCL_DIR}")")
fi
if [ -n "${TK_DIR}" ] && [ -d "${TK_DIR}" ]; then
  PYI_ARGS+=(--add-data "${TK_DIR}:lib/$(basename "${TK_DIR}")")
fi
PYI_ARGS+=("${ENTRY}")

rm -rf build dist "${APP_NAME}.spec"
pyinstaller "${PYI_ARGS[@]}"

ditto -c -k --sequesterRsrc --keepParent "dist/${APP_NAME}.app" "dist/${APP_NAME}-macOS.zip"

echo "Build tamam: dist/${APP_NAME}.app"
echo "Arsiv: dist/${APP_NAME}-macOS.zip"
