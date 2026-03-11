# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import tkinter as tk


def detect_tcl_tk_dirs() -> tuple[Path, Path, str]:
    interp = tk.Tcl()
    tcl_dir = Path(interp.eval("info library")).resolve()
    patchlevel = interp.eval("info patchlevel")
    version = ".".join(patchlevel.split(".")[:2])
    suffix = tcl_dir.name.removeprefix("tcl")
    tk_framework_guess = Path(str(tcl_dir).replace("/Tcl.framework/", "/Tk.framework/"))
    candidates = [
        tcl_dir.parent / f"tk{suffix}",
        tcl_dir.parent.parent / f"tk{suffix}",
        tk_framework_guess,
        tk_framework_guess.parent,
    ]
    tk_dir = next((path for path in candidates if path.exists()), None)
    if tk_dir is None:
        fallback = sorted(tcl_dir.parent.glob("tk8.*")) + sorted(tcl_dir.parent.glob("Scripts"))
        if fallback:
            tk_dir = fallback[0]
    if tk_dir is None:
        raise RuntimeError(f"tk library folder not found near {tcl_dir}")
    return tcl_dir, tk_dir, version


tcl_dir, tk_dir, tk_version = detect_tcl_tk_dirs()

datas = [
    (str(tcl_dir), f"tcl/tcl{tk_version}"),
    (str(tk_dir), f"tcl/tk{tk_version}"),
]

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="GuitarAmpRecorder",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="GuitarAmpRecorder",
)

app = BUNDLE(
    coll,
    name="GuitarAmpRecorder.app",
    icon=None,
    bundle_identifier=None,
)
