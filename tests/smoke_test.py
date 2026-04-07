#!/usr/bin/env python3
"""Lightweight CI smoke tests without external audio/UI dependencies."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import types
from contextlib import contextmanager
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STUBBED_MODULES = ("numpy", "sounddevice", "soundfile", "tkinter")


def stub_module(name: str, **attrs: object) -> None:
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules[name] = module


@contextmanager
def import_stubs():
    previous = {name: sys.modules.get(name) for name in STUBBED_MODULES}

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
        assert "# Release Notes 9.9.9" in body
        assert "Ornek madde" in body
        assert "Onceki surum" not in body


def test_release_scripts_exist() -> None:
    expected = [
        "build_macos_app.sh",
        "package_macos_release.sh",
        "sign_macos_app.sh",
        "notarize_macos_app.sh",
        "scripts/write_sha256.py",
    ]
    for name in expected:
        path = ROOT / name
        assert path.exists(), f"Eksik release scripti: {name}"
        if path.suffix == ".sh":
            assert path.read_text(encoding="utf-8").startswith("#!/usr/bin/env bash")
        else:
            assert path.read_text(encoding="utf-8").startswith("#!/usr/bin/env python3")


def test_release_workflow_publishes_checksum_assets() -> None:
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    expected_snippets = [
        "python scripts/write_sha256.py dist/GuitarAmpRecorder-macOS.zip",
        "python scripts/write_sha256.py dist/GuitarAmpRecorder-Windows.zip",
        "${{ matrix.platform.asset_path }}.sha256",
    ]
    for snippet in expected_snippets:
        assert snippet in workflow, f"release workflow checksum adimi eksik: {snippet}"


def test_build_script_stamps_bundle_metadata() -> None:
    script = (ROOT / "build_macos_app.sh").read_text(encoding="utf-8")
    expected_snippets = [
        'APP_VERSION="$(tr -d \'\\r\\n\' < VERSION',
        "plistlib",
        "Info.plist",
        'SPEC_DIR="build/spec"',
        'SPEC_PATH="${SPEC_DIR}/${APP_NAME}.spec"',
        'cp "${SPEC_TEMPLATE}" "${SPEC_PATH}"',
        'info["CFBundleShortVersionString"] = os.environ["APP_VERSION"]',
        'info["CFBundleVersion"] = os.environ["APP_VERSION"]',
        'info["NSMicrophoneUsageDescription"] = os.environ["MIC_USAGE_TEXT"]',
    ]
    for snippet in expected_snippets:
        assert snippet in script, f"build_macos_app.sh metadata adimi eksik: {snippet}"
    assert 'rm -rf build dist "${APP_NAME}.spec"' not in script, "build script tracked spec dosyasini silmemeli"


def test_package_script_rebuilds_when_bundle_version_mismatches() -> None:
    script = (ROOT / "package_macos_release.sh").read_text(encoding="utf-8")
    expected_snippets = [
        'EXPECTED_VERSION="$(tr -d \'\\r\\n\' < "$ROOT_DIR/VERSION"',
        'CURRENT_APP_VERSION="$(',
        'Path("dist/GuitarAmpRecorder.app/Contents/Info.plist")',
        '[ "$CURRENT_APP_VERSION" != "$EXPECTED_VERSION" ]',
        'ZIP_SHA_PATH="${ZIP_PATH}.sha256"',
        'DESKTOP_ZIP_SHA="${DESKTOP_ZIP}.sha256"',
        'cp "$ZIP_SHA_PATH" "$DESKTOP_ZIP_SHA"',
    ]
    for snippet in expected_snippets:
        assert snippet in script, f"package_macos_release.sh surum uyum kontrolu eksik: {snippet}"


def test_release_script_reports_checksum_locations() -> None:
    script = (ROOT / "release_macos_desktop.sh").read_text(encoding="utf-8")
    expected_snippets = [
        'DESKTOP_ZIP="$HOME/Desktop/GuitarAmpRecorder-macOS.zip"',
        'ZIP_SHA_PATH="${ZIP_PATH}.sha256"',
        'DESKTOP_ZIP_SHA="$HOME/Desktop/GuitarAmpRecorder-macOS.zip.sha256"',
        'echo "- Zip SHA256: $ZIP_SHA_PATH"',
        'if [ -f "$DESKTOP_ZIP" ]; then',
        'echo "- Masaustu kopyasi: $DESKTOP_ZIP"',
        'echo "- Masaustu kopyasi: olusturulamadi, dist zip hazir"',
        'if [ -f "$DESKTOP_ZIP_SHA" ]; then',
        'echo "- Masaustu SHA256: $DESKTOP_ZIP_SHA"',
        'echo "- Masaustu SHA256: olusturulamadi, dist checksum hazir"',
    ]
    for snippet in expected_snippets:
        assert snippet in script, f"release_macos_desktop.sh checksum ciktilari eksik: {snippet}"


def test_notarize_script_cleans_temporary_zip() -> None:
    script = (ROOT / "notarize_macos_app.sh").read_text(encoding="utf-8")
    expected_snippets = [
        'TMP_ZIP="$ROOT_DIR/dist/$(basename "$APP_PATH" .app)-notarize.zip"',
        "cleanup() {",
        'rm -f "$TMP_ZIP"',
        "trap cleanup EXIT",
    ]
    for snippet in expected_snippets:
        assert snippet in script, f"notarize_macos_app.sh gecici zip temizligi eksik: {snippet}"


def test_professional_install_script_handles_desktop_checksum() -> None:
    script = (ROOT / "install_macos_professional.sh").read_text(encoding="utf-8")
    expected_snippets = [
        'ZIP_SHA_DIST="${ZIP_DIST}.sha256"',
        'DESKTOP_ZIP_SHA="${DESKTOP_ZIP}.sha256"',
        'if [ -f "${ZIP_SHA_DIST}" ]; then',
        'cp -f "${ZIP_SHA_DIST}" "${DESKTOP_ZIP_SHA}"',
        'if [ -f "${DESKTOP_ZIP_SHA}" ]; then',
        'echo "Masaustu SHA256: ${DESKTOP_ZIP_SHA}"',
    ]
    for snippet in expected_snippets:
        assert snippet in script, f"install_macos_professional.sh masaustu checksum akisi eksik: {snippet}"


def test_release_metadata_is_version_aligned() -> None:
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    tag = f"v{version}"
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    release_prep = (ROOT / "docs" / "RELEASE_PREP.md").read_text(encoding="utf-8")

    assert f"## [{version}]" in changelog, "CHANGELOG.md en ust surum bolumu VERSION ile uyusmuyor"
    assert f"`VERSION`: `{version}`" in release_prep, "RELEASE_PREP.md hedef surumu VERSION ile uyusmuyor"
    assert f"`git tag {tag}`" in release_prep, "RELEASE_PREP.md tag ornegi VERSION ile uyusmuyor"
    assert f"`git push origin {tag}`" in release_prep, "RELEASE_PREP.md push ornegi VERSION ile uyusmuyor"
    assert f"git tag {tag}" in readme, "README.md release tag ornegi VERSION ile uyusmuyor"
    assert f"git push origin {tag}" in readme, "README.md release push ornegi VERSION ile uyusmuyor"


def test_app_helpers() -> None:
    with import_stubs():
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
    with import_stubs():
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
            renamed, message = cli.rename_named_preset("Temiz", "Parlak")
            assert renamed is True
            assert "Temiz -> Parlak" in message
            assert cli.list_named_presets() == ["Parlak"]
            renamed_loaded = cli.load_named_preset("Parlak")
            assert renamed_loaded is not None
            assert renamed_loaded["gain"] == 11.0
            assert renamed_loaded["input_device_id"] == 3
            store = cli.load_named_preset_store()
            assert store["selected"] == "Parlak"
            assert cli.delete_named_preset("Parlak") is True
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
        assert "--select-preset ADI" in help_text
        assert "--rename-preset ESKI YENI" in help_text
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
        parsed, err = cli.parse_cli_args(["--select-preset", "Temiz"])
        assert err is None
        assert parsed["select_named_preset"] == "Temiz"
        parsed, err = cli.parse_cli_args(["--rename-preset", "Eski", "Yeni"])
        assert err is None
        assert parsed["rename_named_preset"] == ("Eski", "Yeni")
        parsed, err = cli.parse_cli_args(["--test", "--preset", "Temiz"])
        assert err is None
        assert parsed["test_only"] is True
        assert parsed["preset_name"] == "Temiz"
        _, err = cli.parse_cli_args(["--rename-preset", "Tek"])
        assert err == "Eksik deger: --rename-preset"
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


def test_import_stubs_restore_modules() -> None:
    original_numpy = sys.modules.get("numpy")
    with import_stubs():
        assert sys.modules["numpy"].float32 is float
    assert sys.modules.get("numpy") is original_numpy


def main() -> int:
    test_release_body_generation()
    test_release_scripts_exist()
    test_build_script_stamps_bundle_metadata()
    test_package_script_rebuilds_when_bundle_version_mismatches()
    test_release_metadata_is_version_aligned()
    test_app_helpers()
    test_cli_settings_roundtrip()
    print("smoke tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
