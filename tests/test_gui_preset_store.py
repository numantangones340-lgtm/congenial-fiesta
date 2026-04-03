import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

sys.modules.setdefault("numpy", types.SimpleNamespace(ndarray=object))
sys.modules.setdefault("sounddevice", types.SimpleNamespace())
sys.modules.setdefault("soundfile", types.SimpleNamespace())

import app


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
        recorder.app_version = "0.1.0-test"
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
        recorder.last_session_summary_path = None
        recorder.input_device_options = ["Varsayılan macOS girişi", "1 - MacBook Air Mikrofonu"]
        recorder.output_device_options = ["Varsayılan macOS çıkışı", "2 - MacBook Air Hoparlörü"]
        return recorder

    def test_builtin_store_includes_macbook_quick_recording_preset(self) -> None:
        store = app.builtin_preset_store()

        self.assertIn("MacBook Mikrofon Hizli Kayit", store["presets"])
        preset = store["presets"]["MacBook Mikrofon Hizli Kayit"]
        self.assertEqual(preset["gain"], 8)
        self.assertEqual(preset["vocal_level"], 100)
        self.assertEqual(preset["noise_gate_threshold"], 0)
        self.assertEqual(preset["output_gain"], 3)

    def test_apply_clean_macbook_preset_updates_controls_for_builtin_mic(self) -> None:
        recorder = self.make_app()

        recorder.apply_clean_macbook_preset()

        self.assertEqual(recorder.preset_name.get(), "MacBook Mikrofon Hizli Kayit")
        self.assertEqual(recorder.input_device_choice.get(), "1 - MacBook Air Mikrofonu")
        self.assertEqual(recorder.output_device_choice.get(), "2 - MacBook Air Hoparlörü")
        self.assertEqual(recorder.gain.get(), 8)
        self.assertEqual(recorder.noise_gate_threshold.get(), 0)
        self.assertEqual(recorder.output_gain.get(), 3)
        recorder.restart_input_meter.assert_called_once()
        self.assertEqual(
            recorder.status_messages[-1],
            "MacBook mikrofon hizli kayit preset uygulandi. Meter ile kontrol edip kayda gecebilirsiniz.",
        )

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

    def test_save_current_preset_creates_parent_directory(self) -> None:
        recorder = self.make_app()
        recorder.preset_name.set("Gece")
        with tempfile.TemporaryDirectory() as tmpdir:
            preset_path = Path(tmpdir) / "nested" / "gui_saved_preset.json"
            with mock.patch.object(app, "GUI_PRESET_PATH", preset_path):
                recorder.save_current_preset()

            raw = json.loads(preset_path.read_text(encoding="utf-8"))

        self.assertEqual(raw["selected"], "Gece")
        self.assertIn("Gece", raw["presets"])

    def test_write_last_session_state_creates_parent_directory(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            last_session_path = Path(tmpdir) / "nested" / "last_session.json"
            with mock.patch.object(app, "LAST_SESSION_PATH", last_session_path):
                recorder.write_last_session_state(Path("/tmp/out"))

            raw = json.loads(last_session_path.read_text(encoding="utf-8"))

        self.assertEqual(raw["output_dir"], "/tmp/out")
        self.assertEqual(raw["preset_name"], "Temiz Gitar")

    def test_selected_device_pair_ignores_stale_id_when_default_choice_selected(self) -> None:
        recorder = self.make_app()
        recorder.input_device_choice.set("Varsayılan macOS girişi")
        recorder.input_device_id.set("2")
        recorder.output_device_choice.set("2 - MacBook Air Hoparlörü")
        recorder.output_device_id.set("2")

        input_idx, output_idx = recorder.selected_device_pair()

        self.assertIsNone(input_idx)
        self.assertEqual(output_idx, 2)

    def test_selected_device_pair_uses_explicit_choice_index(self) -> None:
        recorder = self.make_app()
        recorder.input_device_choice.set("1 - MacBook Air Mikrofonu")
        recorder.input_device_id.set("")

        input_idx, _ = recorder.selected_device_pair()

        self.assertEqual(input_idx, 1)

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


if __name__ == "__main__":
    unittest.main()
