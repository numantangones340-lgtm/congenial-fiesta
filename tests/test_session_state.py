import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from runtime_stubs import load_module, runtime_stubs

with runtime_stubs():
    app = load_module("app_test_session_state", "app.py")


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
        recorder.load_saved_preset = mock.Mock()
        recorder.last_output_dir = None
        recorder.last_export_path = None
        recorder.last_summary_path = None
        recorder.last_take_notes_path = None
        recorder.last_recovery_note_path = None
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
        self.assertEqual(summary["artifacts"]["session_summary"], str(output_dir / "session_summary.json"))
        self.assertEqual(summary["artifacts"]["take_notes"], str(output_dir / "take_notes.txt"))
        self.assertEqual(summary["recording"], {})

    def test_build_session_summary_includes_recording_metrics_when_provided(self) -> None:
        recorder = self.make_app()
        output_dir = Path("/tmp/session")
        generated = [output_dir / "take.mp3"]

        summary = recorder.build_session_summary(
            output_dir,
            generated,
            "record_export",
            {
                "mode": "Sadece mikrofon",
                "duration_seconds": 42.5,
                "input_peak": 0.61,
                "mix_peak": 0.83,
                "stopped_early": True,
            },
        )

        self.assertEqual(summary["recording"]["mode"], "Sadece mikrofon")
        self.assertEqual(summary["recording"]["duration_seconds"], 42.5)
        self.assertEqual(summary["recording"]["input_peak"], 0.61)
        self.assertTrue(summary["recording"]["stopped_early"])

    def test_build_take_notes_text_includes_clip_warning_and_files(self) -> None:
        recorder = self.make_app()
        output_dir = Path("/tmp/session")
        summary = recorder.build_session_summary(
            output_dir,
            [output_dir / "take.mp3", output_dir / "take_vocal.wav"],
            "record_export",
            {
                "mode": "Sadece mikrofon",
                "duration_seconds": 42.0,
                "requested_duration_seconds": 60.0,
                "input_peak": 0.991,
                "processed_peak": 0.812,
                "mix_peak": 0.0,
                "clip_warning": "Giris clipping riski",
                "stopped_early": False,
            },
        )

        note_text = recorder.build_take_notes_text(summary)

        self.assertIn("Clip Durumu: Giris clipping riski", note_text)
        self.assertIn("Sure: 0:42", note_text)
        self.assertIn("- take.mp3", note_text)
        self.assertIn("- take_vocal.wav", note_text)

    def test_take_name_helpers_reserve_skip_conflicts_and_release_lock(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            (output_dir / "quick_take_001_vocal.wav").write_text("audio", encoding="utf-8")
            reserved = app.reserve_take_name_for_dir(output_dir, "quick_take")

            self.assertEqual(reserved, "quick_take_002")
            self.assertTrue(app.take_lock_path(output_dir, reserved).exists())
            self.assertEqual(app.next_take_name_for_dir(output_dir, "quick_take"), "quick_take_003")

            app.release_take_name_lock(output_dir, reserved)

            self.assertFalse(app.take_lock_path(output_dir, reserved).exists())

    def test_build_export_recovery_note_lists_expected_targets(self) -> None:
        output_dir = Path("/tmp/session")

        note_text = app.build_export_recovery_note(output_dir, "take_007", RuntimeError("ffmpeg failed"))

        self.assertIn("Export Recovery Note", note_text)
        self.assertIn("Take: take_007", note_text)
        self.assertIn("Hata: ffmpeg failed", note_text)
        self.assertIn("- take_007.mp3", note_text)
        self.assertIn("- take_007_mix.wav", note_text)
        self.assertIn("- take_007_vocal.wav", note_text)

    def test_build_recording_prep_text_summarizes_plan_clearly(self) -> None:
        recorder = self.make_app()
        recorder.backing_file = Path("/tmp/backing_track.wav")
        recorder.session_mode.set("Isimli Oturum")
        recorder.session_name.set("Canli Set")
        with tempfile.TemporaryDirectory() as tmpdir:
            recovery_note_path = Path(tmpdir) / "export_recovery_note.txt"
            recovery_note_path.write_text("recovery", encoding="utf-8")
            recorder.last_recovery_note_path = recovery_note_path
            with mock.patch.object(app.GuitarAmpRecorderApp, "resolve_output_dir", return_value=Path("/tmp/out/Canli Set")):
                prep_text = recorder.build_recording_prep_text()

        self.assertIn("Preset: Temiz Gitar", prep_text)
        self.assertIn("Oturum: Isimli Oturum (Canli Set)", prep_text)
        self.assertIn("Kaynak: Arka plan + mikrofon (backing_track.wav)", prep_text)
        self.assertIn("Take Adi: aksam_take", prep_text)
        self.assertIn("Klasor: /tmp/out/Canli Set", prep_text)
        self.assertIn("Ciktilar: MP3 (Yuksek VBR), Vocal WAV, session_summary.json, take_notes.txt", prep_text)
        self.assertIn(f"Not: Son export hatasi icin recovery notu hazir ({recovery_note_path.name})", prep_text)

    def test_remember_completed_take_name_updates_output_name(self) -> None:
        recorder = self.make_app()

        recorder.remember_completed_take_name("quick_take_004")

        self.assertEqual(recorder.output_name.get(), "quick_take_004")

    def test_restore_previous_success_paths_puts_back_last_good_files(self) -> None:
        recorder = self.make_app()
        output_dir = Path("/tmp/last-good")
        export_path = output_dir / "take.mp3"
        summary_path = output_dir / "session_summary.json"
        take_notes_path = output_dir / "take_notes.txt"

        recorder.restore_previous_success_paths(output_dir, export_path, summary_path, take_notes_path)

        self.assertEqual(recorder.last_output_dir, output_dir)
        self.assertEqual(recorder.last_export_path, export_path)
        self.assertEqual(recorder.last_summary_path, summary_path)
        self.assertEqual(recorder.last_take_notes_path, take_notes_path)

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
        self.assertEqual(loaded["last_export_path"], "")
        self.assertEqual(loaded["take_notes_path"], "")
        self.assertEqual(loaded["recovery_note_path"], "")
        self.assertEqual(loaded["summary_path"], str(summary_path))

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
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with mock.patch.object(app, "LAST_SESSION_PATH", state_path):
                recorder.reload_last_session()

        self.assertEqual(recorder.output_dir.get(), str(base_dir))
        self.assertEqual(recorder.session_name.get(), "Aksam Kaydi")
        self.assertEqual(recorder.session_mode.get(), "Isimli Oturum")
        self.assertEqual(recorder.preset_name.get(), "Parlak Solo")
        recorder.load_saved_preset.assert_called_once()
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

    def test_reload_last_session_sets_existing_summary_path(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "session"
            output_dir.mkdir()
            summary_path = output_dir / "session_summary.json"
            summary_path.write_text("{}", encoding="utf-8")
            state_path = Path(tmpdir) / ".last_session.json"
            state_path.write_text(
                json.dumps(
                    {
                        "output_dir": str(output_dir),
                        "session_mode": "Tek Klasor",
                        "summary_path": str(summary_path),
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with mock.patch.object(app, "LAST_SESSION_PATH", state_path):
                recorder.reload_last_session()

        self.assertEqual(recorder.last_summary_path, summary_path)
        self.assertEqual(recorder.last_output_dir, output_dir)

    def test_reload_last_session_sets_take_notes_and_recovery_paths(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "session"
            output_dir.mkdir()
            take_notes_path = output_dir / "take_notes.txt"
            take_notes_path.write_text("note", encoding="utf-8")
            recovery_note_path = output_dir / "export_recovery_note.txt"
            recovery_note_path.write_text("recovery", encoding="utf-8")
            state_path = Path(tmpdir) / ".last_session.json"
            state_path.write_text(
                json.dumps(
                    {
                        "output_dir": str(output_dir),
                        "session_mode": "Tek Klasor",
                        "take_notes_path": str(take_notes_path),
                        "recovery_note_path": str(recovery_note_path),
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with mock.patch.object(app, "LAST_SESSION_PATH", state_path):
                recorder.reload_last_session()

        self.assertEqual(recorder.last_take_notes_path, take_notes_path)
        self.assertEqual(recorder.last_recovery_note_path, recovery_note_path)

    def test_reload_last_session_restores_last_export_path(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "session"
            output_dir.mkdir()
            export_path = output_dir / "take.mp3"
            export_path.write_text("audio", encoding="utf-8")
            state_path = Path(tmpdir) / ".last_session.json"
            state_path.write_text(
                json.dumps(
                    {
                        "output_dir": str(output_dir),
                        "session_mode": "Tek Klasor",
                        "last_export_path": str(export_path),
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with mock.patch.object(app, "LAST_SESSION_PATH", state_path):
                recorder.reload_last_session()

        self.assertEqual(recorder.last_export_path, export_path)
        self.assertEqual(recorder.last_output_dir, output_dir)

    def test_reload_last_session_falls_back_to_latest_audio_when_export_path_missing(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "session"
            output_dir.mkdir()
            older = output_dir / "older_take.wav"
            older.write_text("old", encoding="utf-8")
            newer = output_dir / "new_take.mp3"
            newer.write_text("new", encoding="utf-8")
            now = time.time()
            os.utime(older, (now - 10, now - 10))
            os.utime(newer, (now, now))
            state_path = Path(tmpdir) / ".last_session.json"
            state_path.write_text(
                json.dumps(
                    {
                        "output_dir": str(output_dir),
                        "session_mode": "Tek Klasor",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with mock.patch.object(app, "LAST_SESSION_PATH", state_path):
                recorder.reload_last_session()

        self.assertEqual(recorder.last_export_path, newer)


if __name__ == "__main__":
    unittest.main()
