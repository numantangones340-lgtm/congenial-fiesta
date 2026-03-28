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


class SessionStateTests(unittest.TestCase):
    def make_app(self) -> app.GuitarAmpRecorderApp:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        recorder.app_version = "1.1.3"
        recorder.preset_name = FakeVar("Temiz Gitar")
        recorder.session_mode = FakeVar("Isimli Oturum")
        recorder.session_name = FakeVar("Aksam Kaydi")
        recorder.input_device_choice = FakeVar("Built-in Mic")
        recorder.output_device_choice = FakeVar("Built-in Output")
        recorder.input_device_id = FakeVar("1")
        recorder.output_device_id = FakeVar("2")
        recorder.backing_file = Path("/tmp/backing.mp3")
        recorder.output_name = FakeVar("aksam_take")
        recorder.mp3_quality = FakeVar("Yuksek VBR")
        recorder.wav_export_mode = FakeVar("Tum WAV Dosyalari")
        recorder.record_limit_hours = FakeVar("2")
        recorder.mic_record_seconds = FakeVar("90")
        recorder.gain = FakeVar(7)
        recorder.boost = FakeVar(2)
        recorder.high_pass_hz = FakeVar(80)
        recorder.bass = FakeVar(1)
        recorder.presence = FakeVar(3)
        recorder.treble = FakeVar(2)
        recorder.distortion = FakeVar(9)
        recorder.backing_level = FakeVar(75)
        recorder.vocal_level = FakeVar(88)
        recorder.noise_reduction = FakeVar(12)
        recorder.noise_gate_threshold = FakeVar(11)
        recorder.monitor_level = FakeVar(95)
        recorder.compressor_amount = FakeVar(15)
        recorder.compressor_threshold = FakeVar(-18)
        recorder.compressor_makeup = FakeVar(2)
        recorder.limiter_enabled = FakeVar("Acik")
        recorder.speed_ratio = FakeVar(100)
        recorder.output_gain = FakeVar(-3)
        recorder.output_dir = FakeVar("/tmp/out")
        recorder.status_messages = []
        recorder.set_status = recorder.status_messages.append
        recorder.refresh_recent_exports = mock.Mock()
        recorder.refresh_recent_output_buttons = mock.Mock()
        recorder.load_saved_preset = mock.Mock()
        recorder.last_session_summary_path = None
        return recorder

    def test_build_session_summary_contains_export_and_generated_files(self) -> None:
        recorder = self.make_app()
        output_dir = Path("/tmp/session")
        generated = [output_dir / "take.mp3", output_dir / "take_mix.wav"]

        summary = recorder.build_session_summary(output_dir, generated, "record_export")

        self.assertEqual(summary["app_version"], "1.1.3")
        self.assertEqual(summary["event"], "record_export")
        self.assertEqual(summary["output_dir"], str(output_dir))
        self.assertEqual(summary["preset_name"], "Temiz Gitar")
        self.assertEqual(summary["session_mode"], "Isimli Oturum")
        self.assertEqual(summary["session_name"], "Aksam Kaydi")
        self.assertEqual(summary["backing_file"], "/tmp/backing.mp3")
        self.assertEqual(summary["export"]["output_name"], "aksam_take")
        self.assertEqual(summary["mix"]["limiter_enabled"], "Acik")
        self.assertEqual(summary["generated_files"], [str(path) for path in generated])

    def test_write_and_load_last_session_state_roundtrip(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / ".last_session.json"
            output_dir = Path(tmpdir) / "Aksam Kaydi"
            summary_path = output_dir / "session_summary.json"

            with mock.patch.object(app, "LAST_SESSION_PATH", state_path):
                recorder.write_last_session_state(output_dir, summary_path)
                loaded = recorder.load_last_session_state()

        self.assertEqual(loaded["app_version"], "1.1.3")
        self.assertEqual(loaded["output_dir"], str(output_dir))
        self.assertEqual(loaded["session_mode"], "Isimli Oturum")
        self.assertEqual(loaded["session_name"], "Aksam Kaydi")
        self.assertEqual(loaded["preset_name"], "Temiz Gitar")
        self.assertEqual(loaded["summary_path"], str(summary_path))

    def test_write_last_session_state_keeps_known_summary_when_not_passed(self) -> None:
        recorder = self.make_app()
        recorder.last_session_summary_path = Path("/tmp/onceki/session_summary.json")
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / ".last_session.json"
            output_dir = Path(tmpdir) / "Aksam Kaydi"

            with mock.patch.object(app, "LAST_SESSION_PATH", state_path):
                recorder.write_last_session_state(output_dir)
                loaded = recorder.load_last_session_state()

        self.assertEqual(loaded["summary_path"], "/tmp/onceki/session_summary.json")

    def test_reload_last_session_for_named_session_sets_parent_dir_and_loads_preset(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir) / "exports"
            session_dir = base_dir / "Aksam Kaydi"
            session_dir.mkdir(parents=True)
            state_path = Path(tmpdir) / ".last_session.json"
            state_path.write_text(
                json.dumps(
                    {
                        "output_dir": str(session_dir),
                        "session_mode": "Isimli Oturum",
                        "preset_name": "Parlak Solo",
                        "summary_path": str(session_dir / "session_summary.json"),
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (session_dir / "session_summary.json").write_text("{}", encoding="utf-8")

            with mock.patch.object(app, "LAST_SESSION_PATH", state_path):
                recorder.reload_last_session()

        self.assertEqual(recorder.output_dir.get(), str(base_dir))
        self.assertEqual(recorder.session_name.get(), "Aksam Kaydi")
        self.assertEqual(recorder.session_mode.get(), "Isimli Oturum")
        self.assertEqual(recorder.preset_name.get(), "Parlak Solo")
        self.assertEqual(recorder.last_session_summary_path, session_dir / "session_summary.json")
        recorder.load_saved_preset.assert_called_once()
        recorder.refresh_recent_output_buttons.assert_called_once()
        recorder.refresh_recent_exports.assert_called_once()
        self.assertIn("Son oturum yuklendi", recorder.status_messages[-1])

    def test_reload_last_session_for_single_folder_uses_full_output_dir(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "tek-klasor"
            output_dir.mkdir()
            state_path = Path(tmpdir) / ".last_session.json"
            state_path.write_text(
                json.dumps(
                    {
                        "output_dir": str(output_dir),
                        "session_mode": "Tek Klasor",
                        "preset_name": "",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with mock.patch.object(app, "LAST_SESSION_PATH", state_path):
                recorder.reload_last_session()

        self.assertEqual(recorder.output_dir.get(), str(output_dir))
        self.assertEqual(recorder.session_mode.get(), "Tek Klasor")
        recorder.load_saved_preset.assert_not_called()
        self.assertIn(str(output_dir), recorder.status_messages[-1])


if __name__ == "__main__":
    unittest.main()
