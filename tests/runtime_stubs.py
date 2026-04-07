from __future__ import annotations

import importlib.util
import sys
import types
from contextlib import contextmanager
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STUBBED_MODULES = ("numpy", "sounddevice", "soundfile", "tkinter")


def _stub_module(name: str, **attrs: object) -> None:
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules[name] = module


@contextmanager
def runtime_stubs():
    previous = {name: sys.modules.get(name) for name in STUBBED_MODULES}

    _stub_module("numpy", ndarray=object, float32=float)
    _stub_module("sounddevice", query_devices=lambda: [])
    _stub_module("soundfile")
    _stub_module(
        "tkinter",
        Tk=object,
        Label=object,
        Button=object,
        Scale=object,
        HORIZONTAL=0,
        filedialog=types.SimpleNamespace(askopenfilename=lambda **kwargs: ""),
        StringVar=object,
        Entry=object,
        OptionMenu=object,
        TclError=Exception,
        Canvas=object,
        Frame=object,
        Scrollbar=object,
        Toplevel=object,
    )
    try:
        yield
    finally:
        for name, module in previous.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


def load_module(module_name: str, file_name: str):
    spec = importlib.util.spec_from_file_location(module_name, ROOT / file_name)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {file_name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
