import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from runtime_stubs import load_module, runtime_stubs

with runtime_stubs():
    app = load_module("app_test_gui_presets", "app.py")


class FakeVar:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value) -> None:
        self.value = value


class GuiPresetStoreTests(unittest.TestCase):
    def make_app(self) -> app.GuitarAmpRecorderApp:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        recorder.preset_name = FakeVar("Temiz Gitar")
        recorder.input_device_choice = FakeVar("Built-in Mic")
        recorder.output_device_choice = FakeVar("Built-in Output")
        recorder.input_device_id = FakeVar("1")
        recorder.output_device_id = FakeVar("2")
        recorder.output_name = FakeVar("take")
        recorder.output_dir = FakeVar("/tmp/out")
        recorder.session_mode = FakeVar("Tek Klasor")
        recorder.session_name = FakeVar("session")
        recorder.mp3_quality = FakeVar("Yuksek VBR")
        recorder.wav_export_mode = FakeVar("Sadece Vocal WAV")
        recorder.record_limit_hours = FakeVar("1")
        recorder.mic_record_seconds = FakeVar("60")
        recorder.gain = FakeVar(4)
        recorder.boost = FakeVar(2)
        recorder.high_pass_hz = FakeVar(80)
        recorder.bass = FakeVar(2)
        recorder.presence = FakeVar(1)
        recorder.treble = FakeVar(1)
        recorder.distortion = FakeVar(0)
        recorder.backing_level = FakeVar(100)
        recorder.vocal_level = FakeVar(85)
        recorder.noise_reduction = FakeVar(10)
        recorder.noise_gate_threshold = FakeVar(8)
        recorder.monitor_level = FakeVar(100)
        recorder.compressor_amount = FakeVar(10)
        recorder.compressor_threshold = FakeVar(-20)
        recorder.compressor_makeup = FakeVar(1)
        recorder.limiter_enabled = FakeVar("Acik")
        recorder.speed_ratio = FakeVar(100)
        recorder.output_gain = FakeVar(0)
        recorder.status_messages = []
        recorder.set_status = recorder.status_messages.append
        recorder.refresh_preset_menu = mock.Mock()
        recorder.restart_input_meter = mock.Mock()
        return recorder

    def test_load_preset_store_data_supports_legacy_single_preset_file(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            preset_path = Path(tmpdir) / ".gui_saved_preset.json"
            preset_path.write_text(
                json.dumps({"gain": 9, "output_name": "legacy_take"}, ensure_ascii=False),
                encoding="utf-8",
            )
            with mock.patch.object(app, "GUI_PRESET_PATH", preset_path):
                store = recorder.load_preset_store_data()

        self.assertIn("Varsayilan", store["presets"])
        self.assertEqual(store["selected"], "Temiz Gitar")
        self.assertEqual(store["presets"]["Varsayilan"]["gain"], 9)

    def test_save_current_preset_persists_selected_name(self) -> None:
        recorder = self.make_app()
        recorder.preset_name.set("Aksam")
        with tempfile.TemporaryDirectory() as tmpdir:
            preset_path = Path(tmpdir) / ".gui_saved_preset.json"
            with mock.patch.object(app, "GUI_PRESET_PATH", preset_path):
                recorder.save_current_preset()
                raw = json.loads(preset_path.read_text(encoding="utf-8"))

        self.assertEqual(raw["selected"], "Aksam")
        self.assertIn("Aksam", raw["presets"])
        self.assertEqual(raw["presets"]["Aksam"]["gain"], 4)
        recorder.refresh_preset_menu.assert_called_once_with("Aksam")
        self.assertEqual(recorder.status_messages[-1], "Preset kaydedildi: Aksam")

    def test_save_current_preset_uses_existing_selected_name_when_entry_blank(self) -> None:
        recorder = self.make_app()
        recorder.preset_name.set("")
        recorder.gain.set(7)
        with tempfile.TemporaryDirectory() as tmpdir:
            preset_path = Path(tmpdir) / ".gui_saved_preset.json"
            preset_path.write_text(
                json.dumps(
                    {
                        "selected": "Aksam",
                        "presets": {"Aksam": {"gain": 4}},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with mock.patch.object(app, "GUI_PRESET_PATH", preset_path):
                recorder.save_current_preset()
                raw = json.loads(preset_path.read_text(encoding="utf-8"))

        self.assertEqual(raw["selected"], "Aksam")
        self.assertEqual(raw["presets"]["Aksam"]["gain"], 7)
        recorder.refresh_preset_menu.assert_called_once_with("Aksam")
        self.assertEqual(recorder.status_messages[-1], "Preset kaydedildi: Aksam")

    def test_delete_selected_preset_falls_back_to_builtin_presets(self) -> None:
        recorder = self.make_app()
        recorder.preset_name.set("TekPreset")
        with tempfile.TemporaryDirectory() as tmpdir:
            preset_path = Path(tmpdir) / ".gui_saved_preset.json"
            preset_path.write_text(
                json.dumps({"selected": "TekPreset", "presets": {"TekPreset": {"gain": 4}}}, ensure_ascii=False),
                encoding="utf-8",
            )
            with mock.patch.object(app, "GUI_PRESET_PATH", preset_path):
                recorder.delete_selected_preset()
                raw = json.loads(preset_path.read_text(encoding="utf-8"))

        self.assertNotIn("TekPreset", raw["presets"])
        self.assertIn("Temiz Gitar", raw["presets"])
        self.assertEqual(raw["selected"], sorted(raw["presets"].keys())[0])
        recorder.refresh_preset_menu.assert_called_once_with(raw["selected"])
        self.assertEqual(recorder.status_messages[-1], "Preset silindi: TekPreset")

    def test_delete_selected_preset_rejects_builtin_presets(self) -> None:
        recorder = self.make_app()
        recorder.preset_name.set("Temiz Gitar")
        with tempfile.TemporaryDirectory() as tmpdir:
            preset_path = Path(tmpdir) / ".gui_saved_preset.json"
            preset_path.write_text(
                json.dumps({"selected": "Temiz Gitar", "presets": {"Kullanici": {"gain": 4}}}, ensure_ascii=False),
                encoding="utf-8",
            )
            with mock.patch.object(app, "GUI_PRESET_PATH", preset_path):
                recorder.delete_selected_preset()
                raw = json.loads(preset_path.read_text(encoding="utf-8"))

        self.assertEqual(raw["selected"], "Temiz Gitar")
        self.assertIn("Kullanici", raw["presets"])
        recorder.refresh_preset_menu.assert_not_called()
        self.assertEqual(recorder.status_messages[-1], "Hazir preset silinemez: Temiz Gitar")

    def test_delete_selected_preset_keeps_existing_selection_when_deleting_other_preset(self) -> None:
        recorder = self.make_app()
        recorder.preset_name.set("Aksam")
        with tempfile.TemporaryDirectory() as tmpdir:
            preset_path = Path(tmpdir) / ".gui_saved_preset.json"
            preset_path.write_text(
                json.dumps(
                    {
                        "selected": "Temiz Gitar",
                        "presets": {
                            "Temiz Gitar": {"gain": 6},
                            "Aksam": {"gain": 8},
                            "Parlak": {"gain": 9},
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with mock.patch.object(app, "GUI_PRESET_PATH", preset_path):
                recorder.delete_selected_preset()
                raw = json.loads(preset_path.read_text(encoding="utf-8"))

        self.assertEqual(raw["selected"], "Temiz Gitar")
        self.assertNotIn("Aksam", raw["presets"])
        self.assertIn("Parlak", raw["presets"])
        self.assertIn("Temiz Gitar", raw["presets"])
        recorder.refresh_preset_menu.assert_called_once_with("Temiz Gitar")
        self.assertEqual(recorder.status_messages[-1], "Preset silindi: Aksam")


if __name__ == "__main__":
    unittest.main()
