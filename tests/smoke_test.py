#!/usr/bin/env python3
"""Lightweight CI smoke tests without external audio/UI dependencies."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def stub_module(name: str, **attrs: object) -> None:
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules[name] = module


def prepare_import_stubs() -> None:
    stub_module("numpy", ndarray=object, float32=float)
    stub_module("sounddevice", query_devices=lambda: [])
    stub_module("soundfile")
    stub_module(
        "tkinter",
        Tk=object,
        Label=object,
        Button=object,
        Scale=object,
        HORIZONTAL=0,
        filedialog=object,
        StringVar=object,
        Entry=object,
        OptionMenu=object,
        TclError=Exception,
        Canvas=object,
        Frame=object,
        Scrollbar=object,
    )


def load_module(module_name: str, file_name: str):
    spec = importlib.util.spec_from_file_location(module_name, ROOT / file_name)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {file_name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_release_body_generation() -> None:
    generator = ROOT / "scripts" / "generate_release_notes.py"
    if not generator.exists():
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        (tmp / "VERSION").write_text("9.9.9\n", encoding="utf-8")
        (tmp / "CHANGELOG.md").write_text(
            "# Changelog\n\n"
            "## [9.9.9] - 2026-03-20\n\n"
            "### Eklendi\n\n"
            "- Ornek madde\n\n"
            "## [9.9.8] - 2026-03-19\n\n"
            "- Onceki surum\n",
            encoding="utf-8",
        )
        output = tmp / "generated.md"
        subprocess.run(
            [
                sys.executable,
                str(generator),
                "--version-file",
                str(tmp / "VERSION"),
                "--changelog",
                str(tmp / "CHANGELOG.md"),
                "--output",
                str(output),
            ],
            check=True,
        )
        body = output.read_text(encoding="utf-8")
        assert "# Release 9.9.9" in body
        assert "Ornek madde" in body
        assert "Onceki surum" not in body


def test_app_helpers() -> None:
    prepare_import_stubs()
    app = load_module("app_smoke", "app.py")
    assert app.read_app_version() == (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    assert app.format_mm_ss(65) == "01:05"
    assert app.format_mm_ss(3661) == "01:01:01"

    with tempfile.TemporaryDirectory() as tmpdir:
        directory = Path(tmpdir)
        assert app.next_take_name_for_dir(directory, "take") == "take_001"
        (directory / "take_001.mp3").write_text("", encoding="utf-8")
        assert app.next_take_name_for_dir(directory, "take") == "take_002"


def test_cli_settings_roundtrip() -> None:
    prepare_import_stubs()
    cli = load_module("cli_smoke", "cli_app.py")

    with tempfile.TemporaryDirectory() as tmpdir:
        preset_path = Path(tmpdir) / ".last_preset.json"
        named_preset_path = Path(tmpdir) / ".cli_presets.json"
        cli.PRESET_PATH = preset_path
        cli.NAMED_PRESET_PATH = named_preset_path

        loaded = cli.load_saved_settings()
        assert loaded["gain"] == cli.DEFAULT_SETTINGS["gain"]
        assert loaded["input_device_id"] is None

        cli.save_settings(
            {
                **cli.DEFAULT_SETTINGS,
                "gain": 9,
                "output_device_id": 7,
            }
        )
        raw = json.loads(preset_path.read_text(encoding="utf-8"))
        assert raw["gain"] == 9.0
        assert raw["output_device_id"] == 7

        loaded = cli.load_saved_settings()
        assert loaded["gain"] == 9.0
        assert loaded["output_device_id"] == 7

        cli.save_named_preset(
            "Temiz",
            {
                **cli.DEFAULT_SETTINGS,
                "gain": 11,
                "input_device_id": 3,
            },
        )
        names = cli.list_named_presets()
        assert names == ["Temiz"]
        named_loaded = cli.load_named_preset("Temiz")
        assert named_loaded is not None
        assert named_loaded["gain"] == 11.0
        assert named_loaded["input_device_id"] == 3
        assert cli.delete_named_preset("Temiz") is True
        assert cli.list_named_presets() == []

    assert "Ses aygıtı bulunamadı" in cli.no_device_help_text()
    assert cli.format_cli_value(None) == "varsayılan"
    assert cli.format_cli_value(7) == "7"
    lines = cli.format_kv_lines([("Mod", "test"), ("Mikrofon aygıtı", None)])
    assert lines == [
        "- Mod             : test",
        "- Mikrofon aygıtı : varsayılan",
    ]
    help_text = cli.cli_usage_text()
    assert "--quick" in help_text
    assert "--list-presets" in help_text
    assert "--show-preset ADI" in help_text
    assert "--list-devices" in help_text
    assert "--show-settings" in help_text
    assert "--test" in help_text
    parsed, err = cli.parse_cli_args(["--help"])
    assert err is None
    assert parsed["help_only"] is True
    parsed, err = cli.parse_cli_args(["--list-devices"])
    assert err is None
    assert parsed["list_devices_only"] is True
    parsed, err = cli.parse_cli_args(["--show-settings", "--preset", "Temiz"])
    assert err is None
    assert parsed["show_settings_only"] is True
    assert parsed["preset_name"] == "Temiz"
    parsed, err = cli.parse_cli_args(["--show-preset", "Temiz"])
    assert err is None
    assert parsed["show_named_preset"] == "Temiz"
    parsed, err = cli.parse_cli_args(["--test", "--preset", "Temiz"])
    assert err is None
    assert parsed["test_only"] is True
    assert parsed["preset_name"] == "Temiz"
    cli.next_take_name = lambda prefix: f"{prefix}_001"
    assert cli.device_test_output_name("") == "quick_take_001_device_test"
    assert cli.device_test_output_name("Temiz") == "Temiz_device_test"
    settings_lines = cli.format_kv_lines(
        [
            ("Kaynak", "Temiz"),
            ("Mikrofon aygıtı", None),
            ("Çıkış aygıtı", 8),
        ]
    )
    assert settings_lines == [
        "- Kaynak          : Temiz",
        "- Mikrofon aygıtı : varsayılan",
        "- Çıkış aygıtı    : 8",
    ]
    _, err = cli.parse_cli_args(["--unknown"])
    assert err == "Bilinmeyen secenek: --unknown"


def main() -> int:
    test_release_body_generation()
    test_app_helpers()
    test_cli_settings_roundtrip()
    print("smoke tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
