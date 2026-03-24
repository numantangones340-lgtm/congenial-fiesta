import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from runtime_stubs import load_module, runtime_stubs

with runtime_stubs():
    cli_app = load_module("cli_app_test_cli_presets", "cli_app.py")


class CliPresetStoreTests(unittest.TestCase):
    def test_saved_settings_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            preset_path = Path(tmpdir) / ".last_preset.json"
            named_preset_path = Path(tmpdir) / ".cli_presets.json"
            with (
                mock.patch.object(cli_app, "PRESET_PATH", preset_path),
                mock.patch.object(cli_app, "NAMED_PRESET_PATH", named_preset_path),
            ):
                loaded = cli_app.load_saved_settings()
                self.assertEqual(loaded["gain"], cli_app.DEFAULT_SETTINGS["gain"])
                self.assertIsNone(loaded["input_device_id"])

                cli_app.save_settings(
                    {
                        **cli_app.DEFAULT_SETTINGS,
                        "gain": 9,
                        "output_device_id": 7,
                    }
                )

                raw = json.loads(preset_path.read_text(encoding="utf-8"))
                self.assertEqual(raw["gain"], 9.0)
                self.assertEqual(raw["output_device_id"], 7)

                loaded = cli_app.load_saved_settings()
                self.assertEqual(loaded["gain"], 9.0)
                self.assertEqual(loaded["output_device_id"], 7)

    def test_named_preset_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            named_preset_path = Path(tmpdir) / ".cli_presets.json"
            with mock.patch.object(cli_app, "NAMED_PRESET_PATH", named_preset_path):
                cli_app.save_named_preset(
                    "Temiz",
                    {
                        **cli_app.DEFAULT_SETTINGS,
                        "gain": 11,
                        "input_device_id": 3,
                    },
                )
                self.assertEqual(cli_app.list_named_presets(), ["Temiz"])
                named_loaded = cli_app.load_named_preset("Temiz")
                self.assertIsNotNone(named_loaded)
                self.assertEqual(named_loaded["gain"], 11.0)
                self.assertEqual(named_loaded["input_device_id"], 3)

                renamed, message = cli_app.rename_named_preset("Temiz", "Parlak")
                self.assertTrue(renamed)
                self.assertIn("Temiz -> Parlak", message)
                self.assertEqual(cli_app.list_named_presets(), ["Parlak"])

                store = cli_app.load_named_preset_store()
                self.assertEqual(store["selected"], "Parlak")
                self.assertTrue(cli_app.delete_named_preset("Parlak"))
                self.assertEqual(cli_app.list_named_presets(), [])

    def test_invalid_named_preset_store_falls_back_to_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            named_preset_path = Path(tmpdir) / ".cli_presets.json"
            named_preset_path.write_text('{"selected": 42, "presets": []}', encoding="utf-8")
            with mock.patch.object(cli_app, "NAMED_PRESET_PATH", named_preset_path):
                store = cli_app.load_named_preset_store()
            self.assertEqual(store, {"selected": "", "presets": {}})

    def test_build_runtime_settings_uses_latest_values(self) -> None:
        settings = cli_app.build_runtime_settings(
            gain=9,
            boost=4,
            bass=1,
            treble=3,
            dist=12,
            noise_reduction=15,
            speed_percent=95,
            output_gain_db=-2,
            backing_level=70,
            vocal_level=90,
            record_seconds=75,
            input_device_id=5,
            output_device_id=7,
        )
        self.assertEqual(
            settings,
            {
                "gain": 9,
                "boost": 4,
                "bass": 1,
                "treble": 3,
                "dist": 12,
                "noise_reduction": 15,
                "speed_percent": 95,
                "output_gain_db": -2,
                "backing_level": 70,
                "vocal_level": 90,
                "record_seconds": 75,
                "input_device_id": 5,
                "output_device_id": 7,
            },
        )

    def test_delete_named_preset_keeps_existing_selection_when_deleting_other_preset(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            named_preset_path = Path(tmpdir) / ".cli_presets.json"
            named_preset_path.write_text(
                json.dumps(
                    {
                        "selected": "Temiz",
                        "presets": {
                            "Temiz": {"gain": 6},
                            "Parlak": {"gain": 9},
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with mock.patch.object(cli_app, "NAMED_PRESET_PATH", named_preset_path):
                self.assertTrue(cli_app.delete_named_preset("Parlak"))
                store = cli_app.load_named_preset_store()

        self.assertEqual(store["selected"], "Temiz")
        self.assertEqual(sorted(store["presets"].keys()), ["Temiz"])


class CliArgParsingTests(unittest.TestCase):
    def test_parse_cli_args_supports_common_paths(self) -> None:
        parsed, err = cli_app.parse_cli_args(["--help"])
        self.assertIsNone(err)
        self.assertTrue(parsed["help_only"])

        parsed, err = cli_app.parse_cli_args(["--list-devices"])
        self.assertIsNone(err)
        self.assertTrue(parsed["list_devices_only"])

        parsed, err = cli_app.parse_cli_args(["--show-settings", "--preset", "Temiz"])
        self.assertIsNone(err)
        self.assertTrue(parsed["show_settings_only"])
        self.assertEqual(parsed["preset_name"], "Temiz")

        parsed, err = cli_app.parse_cli_args(["--show-preset", "Temiz"])
        self.assertIsNone(err)
        self.assertEqual(parsed["show_named_preset"], "Temiz")

        parsed, err = cli_app.parse_cli_args(["--select-preset=Temiz"])
        self.assertIsNone(err)
        self.assertEqual(parsed["select_named_preset"], "Temiz")

        parsed, err = cli_app.parse_cli_args(["--test", "--preset=Temiz"])
        self.assertIsNone(err)
        self.assertTrue(parsed["test_only"])
        self.assertEqual(parsed["preset_name"], "Temiz")

    def test_parse_cli_args_rejects_invalid_inputs(self) -> None:
        _, err = cli_app.parse_cli_args(["--rename-preset", "Tek"])
        self.assertEqual(err, "Eksik deger: --rename-preset")

        _, err = cli_app.parse_cli_args(["--preset="])
        self.assertEqual(err, "Gecersiz bos deger: --preset")

        _, err = cli_app.parse_cli_args(["--unknown"])
        self.assertEqual(err, "Bilinmeyen secenek: --unknown")

    def test_cli_helpers_return_expected_text(self) -> None:
        self.assertIn("Ses aygıtı bulunamadı", cli_app.no_device_help_text())
        self.assertEqual(cli_app.format_cli_value(None), "varsayılan")
        self.assertEqual(cli_app.format_cli_value(7), "7")
        self.assertIn("--rename-preset ESKI YENI", cli_app.cli_usage_text())

        with mock.patch.object(cli_app, "next_take_name", side_effect=lambda prefix: f"{prefix}_001"):
            self.assertEqual(cli_app.device_test_output_name(""), "quick_take_001_device_test")
        self.assertEqual(cli_app.device_test_output_name("Temiz"), "Temiz_device_test")


if __name__ == "__main__":
    unittest.main()
