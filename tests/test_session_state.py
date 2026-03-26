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
        recorder.operation_state_text = FakeVar("")
        recorder.compact_status_text = FakeVar("")
        recorder.readiness_text = FakeVar("")
        recorder.readiness_subtitle_text = FakeVar("")
        recorder.next_step_subtitle_text = FakeVar("")
        recorder.recent_output_summary_text = FakeVar("")
        recorder.recent_output_subtitle_text = FakeVar("")
        recorder.operation_state_label = mock.Mock()
        recorder.readiness_label = mock.Mock()
        recorder.recent_output_summary_label = mock.Mock()
        recorder.setup_status_label = mock.Mock()
        recorder.setup_next_label = mock.Mock()
        recorder.setup_status_text = FakeVar("")
        recorder.setup_hint_text = FakeVar("")
        recorder.setup_next_text = FakeVar("")
        recorder.mp3_quality_label_text = FakeVar("")
        recorder.mp3_quality_menu = mock.Mock()
        recorder.preset_name = FakeVar("Temiz Gitar")
        recorder.session_mode = FakeVar("İsimli Oturum")
        recorder.session_name = FakeVar("Akşam Kaydı")
        recorder.input_device_choice = FakeVar("Built-in Mic")
        recorder.output_device_choice = FakeVar("Built-in Output")
        recorder.action_guidance_text = FakeVar("")
        recorder.action_subtitle_text = FakeVar("")
        recorder.record_progress_text = FakeVar("")
        recorder.progress_subtitle_text = FakeVar("")
        recorder.preflight_warning_text = FakeVar("")
        recorder.preflight_subtitle_text = FakeVar("")
        recorder.source_subtitle_text = FakeVar("")
        recorder.output_subtitle_text = FakeVar("")
        recorder.option_subtitle_text = FakeVar("")
        recorder.prep_subtitle_text = FakeVar("")
        recorder.merge_subtitle_text = FakeVar("")
        recorder.merge_summary_text = FakeVar("")
        recorder.tone_subtitle_text = FakeVar("")
        recorder.mix_subtitle_text = FakeVar("")
        recorder.input_device_id = FakeVar("1")
        recorder.output_device_id = FakeVar("2")
        recorder.backing_file = Path("/tmp/backing.mp3")
        recorder.output_name = FakeVar("aksam_take")
        recorder.mp3_quality = FakeVar("Yüksek VBR")
        recorder.wav_export_mode = FakeVar("Tüm WAV Dosyaları")
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
        recorder.limiter_enabled = FakeVar("Açık")
        recorder.speed_ratio = FakeVar(100)
        recorder.output_gain = FakeVar(-3)
        recorder.output_dir = FakeVar("/tmp/out")
        recorder.recording_active = False
        recorder.stop_recording_requested = False
        recorder.recording_mode = ""
        recorder.current_input_device_count = 1
        recorder.current_output_device_count = 1
        recorder.last_input_peak = 0.0
        recorder.meter_stream = None
        recorder.monitor_stream = None
        recorder.status_messages = []
        recorder.set_status = recorder.status_messages.append
        recorder.refresh_recent_exports = mock.Mock()
        recorder.load_saved_preset = mock.Mock()
        recorder.preflight_warning_label = mock.Mock()
        recorder.start_test_button = mock.Mock()
        recorder.start_quick_record_button = mock.Mock()
        recorder.start_recording_button = mock.Mock()
        recorder.stop_recording_button = mock.Mock()
        recorder.open_last_export_button = mock.Mock()
        recorder.play_last_export_button = mock.Mock()
        recorder.copy_last_export_path_button = mock.Mock()
        recorder.open_last_summary_button = mock.Mock()
        recorder.copy_last_summary_button = mock.Mock()
        recorder.copy_last_summary_path_button = mock.Mock()
        recorder.copy_last_brief_button = mock.Mock()
        recorder.export_last_brief_button = mock.Mock()
        recorder.open_last_take_notes_button = mock.Mock()
        recorder.copy_last_recovery_note_button = mock.Mock()
        recorder.open_last_output_dir_button = mock.Mock()
        recorder.open_last_preparation_button = mock.Mock()
        recorder.last_output_dir = None
        recorder.last_export_path = None
        recorder.last_summary_path = None
        recorder.last_take_notes_path = None
        recorder.last_recovery_note_path = None
        recorder.last_preparation_summary_path = None
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
        self.assertEqual(summary["session_mode"], "İsimli Oturum")
        self.assertEqual(summary["session_name"], "Akşam Kaydı")
        self.assertEqual(summary["backing_file"], "/tmp/backing.mp3")
        self.assertEqual(summary["export"]["output_name"], "aksam_take")
        self.assertEqual(summary["mix"]["limiter_enabled"], "Açık")
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

        self.assertIn("Kurtarma Notu", note_text)
        self.assertIn("Take: take_007", note_text)
        self.assertIn("Hata: ffmpeg failed", note_text)
        self.assertIn("- take_007.mp3", note_text)
        self.assertIn("- take_007_mix.wav", note_text)
        self.assertIn("- take_007_vocal.wav", note_text)

    def test_build_recording_prep_text_summarizes_plan_clearly(self) -> None:
        recorder = self.make_app()
        recorder.backing_file = Path("/tmp/backing_track.wav")
        recorder.session_mode.set("İsimli Oturum")
        recorder.session_name.set("Canlı Set")
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "take.mp3"
            export_path.write_text("audio", encoding="utf-8")
            recovery_note_path = Path(tmpdir) / "export_recovery_note.txt"
            recovery_note_path.write_text("recovery", encoding="utf-8")
            recorder.last_export_path = export_path
            recorder.last_recovery_note_path = recovery_note_path
            with mock.patch.object(app.GuitarAmpRecorderApp, "resolve_output_dir", return_value=Path("/tmp/out/Canlı Set")):
                prep_text = recorder.build_recording_prep_text()
            latest_audio = app.recent_audio_status_text(export_path)

        self.assertIn("Preset/Oturum: Temiz Gitar | İsimli Oturum (Canlı Set)", prep_text)
        self.assertIn("Kaynak: Arka plan + mikrofon (backing_track.wav)", prep_text)
        self.assertIn("Take/Hedef: aksam_take | /tmp/out/Canlı Set", prep_text)
        self.assertIn("Dosyalar: Mix WAV, Vokal WAV, session_summary.json, take_notes.txt", prep_text)
        self.assertIn("Cihazlar: Built-in Mic -> Built-in Output", prep_text)
        self.assertIn(f"Kurtarma: {recovery_note_path.name} hazır | Son iyi kayıt: {latest_audio}", prep_text)

    def test_build_recording_prep_subtitle_text_requires_output_dir(self) -> None:
        recorder = self.make_app()
        recorder.output_dir.set("")

        subtitle_text = recorder.build_recording_prep_subtitle_text()

        self.assertEqual(subtitle_text, "Planı netleştirmek için önce kayıt klasörünü seçin.")

    def test_build_recording_prep_subtitle_text_reports_target_and_count(self) -> None:
        recorder = self.make_app()
        recorder.backing_file = Path("/tmp/backing_track.wav")
        with mock.patch.object(app.GuitarAmpRecorderApp, "resolve_output_dir", return_value=Path("/tmp/out/Canlı Set")):
            subtitle_text = recorder.build_recording_prep_subtitle_text()

        self.assertEqual(subtitle_text, "4 çıktı hazırlanacak. Hedef: /tmp/out/Canlı Set")

    def test_build_recording_prep_subtitle_text_marks_recovery_note(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "take.mp3"
            export_path.write_text("audio", encoding="utf-8")
            recovery_note_path = Path(tmpdir) / "export_recovery_note.txt"
            recovery_note_path.write_text("recovery", encoding="utf-8")
            recorder.last_export_path = export_path
            recorder.last_recovery_note_path = recovery_note_path

            subtitle_text = recorder.build_recording_prep_subtitle_text()
            latest_audio = app.recent_audio_status_text(export_path)

        self.assertEqual(
            subtitle_text,
            f"4 çıktı hazırlanacak. Hedef: /tmp/out/Akşam Kaydı | kurtarma notu var | son iyi kayıt: {latest_audio}",
        )

    def test_planned_output_labels_fall_back_to_mix_wav_when_ffmpeg_missing(self) -> None:
        recorder = self.make_app()
        recorder.wav_export_mode.set("Sadece Vokal WAV")

        with mock.patch.object(app.shutil, "which", return_value=None):
            labels = recorder.planned_output_labels()

        self.assertEqual(labels, ["Mix WAV (MP3 yerine)", "Vokal WAV", "session_summary.json", "take_notes.txt"])

    def test_build_recording_prep_text_mentions_mix_wav_fallback_when_ffmpeg_missing(self) -> None:
        recorder = self.make_app()
        recorder.wav_export_mode.set("Sadece Vokal WAV")
        with mock.patch.object(app.shutil, "which", return_value=None), mock.patch.object(
            app.GuitarAmpRecorderApp, "resolve_output_dir", return_value=Path("/tmp/out")
        ):
            prep_text = recorder.build_recording_prep_text()

        self.assertIn("Dosyalar: Mix WAV (MP3 yerine), Vokal WAV, session_summary.json, take_notes.txt", prep_text)

    def test_update_recording_prep_summary_updates_subtitle(self) -> None:
        recorder = self.make_app()
        recorder.output_dir.set("")

        recorder.update_recording_prep_summary()

        self.assertEqual(recorder.prep_subtitle_text.get(), "Planı netleştirmek için önce kayıt klasörünü seçin.")

    def test_build_current_preparation_brief_text_includes_core_sections(self) -> None:
        recorder = self.make_app()

        brief_text = recorder.build_current_preparation_brief_text()

        self.assertIn("Hazırlık Özeti", brief_text)
        self.assertIn("Sonraki Adım:", brief_text)
        self.assertIn("Hazırlık:", brief_text)
        self.assertIn("Kayıt Planı:", brief_text)
        self.assertIn("Seçenekler:", brief_text)
        self.assertIn("Ton: Kazanç 7 dB", brief_text)
        self.assertIn("Mix: Arka plan %75", brief_text)

    def test_build_compact_status_text_summarizes_core_state_on_one_line(self) -> None:
        recorder = self.make_app()
        recorder.backing_file = Path("/tmp/backing_track.wav")
        recorder.session_mode.set("İsimli Oturum")
        recorder.session_name.set("Canlı Set")
        with mock.patch.object(app.GuitarAmpRecorderApp, "resolve_output_dir", return_value=Path("/tmp/out/Canlı Set")):
            compact_text = recorder.build_compact_status_text()

        self.assertEqual(
            compact_text,
            "Preset: Temiz Gitar | Kaynak: backing_track.wav + mikrofon | Oturum: İsimli Oturum (Canlı Set) | Take: aksam_take | Hedef: /tmp/out/Canlı Set",
        )

    def test_build_compact_status_text_marks_auto_take_and_missing_folder(self) -> None:
        recorder = self.make_app()
        recorder.backing_file = None
        recorder.output_name.set("")
        recorder.output_dir.set("")
        compact_text = recorder.build_compact_status_text()

        self.assertIn("Kaynak: Sadece mikrofon", compact_text)
        self.assertIn("Take: otomatik", compact_text)
        self.assertIn("Hedef: klasör seçilmedi", compact_text)

    def test_build_compact_status_text_mentions_last_good_take_when_recovery_exists(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "take.mp3"
            export_path.write_text("audio", encoding="utf-8")
            recovery_note_path = Path(tmpdir) / "export_recovery_note.txt"
            recovery_note_path.write_text("recovery", encoding="utf-8")
            recorder.last_export_path = export_path
            recorder.last_recovery_note_path = recovery_note_path

            compact_text = recorder.build_compact_status_text()

        self.assertIn(f"Kurtarma: var | Son iyi kayıt: {app.recent_audio_status_text(export_path)}", compact_text)

    def test_build_completion_status_text_summarizes_primary_file_and_output_dir(self) -> None:
        recorder = self.make_app()
        output_dir = Path("/tmp/out/Canlı Set")
        primary_path = output_dir / "take.mp3"
        generated_files = [primary_path, output_dir / "take_vocal.wav"]

        status_text = recorder.build_completion_status_text("Kayıt", output_dir, primary_path, generated_files)

        self.assertEqual(
            status_text,
            "Kayıt hazır | Ana dosya: take.mp3 (MP3 | Canlı Set) | Dosya sayısı: 2 | Klasör: /tmp/out/Canlı Set",
        )

    def test_build_completion_status_text_handles_missing_primary_file(self) -> None:
        recorder = self.make_app()
        output_dir = Path("/tmp/out/Test")

        status_text = recorder.build_completion_status_text("Test", output_dir, None, [])

        self.assertEqual(status_text, "Test hazır | Klasör: /tmp/out/Test")

    def test_build_completion_status_text_mentions_wav_fallback_when_ffmpeg_missing(self) -> None:
        recorder = self.make_app()
        recorder.wav_export_mode.set("Sadece Vokal WAV")
        output_dir = Path("/tmp/out/Canlı Set")
        primary_path = output_dir / "take_mix.wav"

        with mock.patch.object(app.shutil, "which", return_value=None):
            status_text = recorder.build_completion_status_text("Kayıt", output_dir, primary_path, [primary_path])

        self.assertEqual(
            status_text,
            "Kayıt hazır | Ana dosya: take_mix.wav (WAV | Canlı Set) | Not: MP3 yerine WAV kullanıldı | Dosya sayısı: 1 | Klasör: /tmp/out/Canlı Set",
        )

    def test_build_ready_recording_progress_text_includes_latest_audio_summary(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "Canlı Set"
            output_dir.mkdir()
            recorder.last_export_path = output_dir / "take.mp3"
            recorder.last_export_path.write_text("audio", encoding="utf-8")

            progress_text = recorder.build_ready_recording_progress_text(output_dir)

        self.assertIn("Hazır | Dosyalar hazır | Klasör:", progress_text)
        self.assertIn("Son kayıt: take.mp3 (MP3 | Canlı Set)", progress_text)

    def test_build_ready_recording_progress_text_mentions_wav_fallback_when_ffmpeg_missing(self) -> None:
        recorder = self.make_app()
        recorder.wav_export_mode.set("Sadece Vokal WAV")
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "Canlı Set"
            output_dir.mkdir()
            recorder.last_export_path = output_dir / "take_mix.wav"
            recorder.last_export_path.write_text("audio", encoding="utf-8")

            with mock.patch.object(app.shutil, "which", return_value=None):
                progress_text = recorder.build_ready_recording_progress_text(output_dir)

        self.assertIn("Son kayıt: take_mix.wav (WAV | Canlı Set)", progress_text)
        self.assertIn("MP3 yerine WAV kullanıldı", progress_text)

    def test_build_operation_state_text_reports_idle_state(self) -> None:
        recorder = self.make_app()

        state_text = recorder.build_operation_state_text()

        self.assertEqual(state_text, "Durum: hazır")

    def test_build_operation_state_text_reports_meter_state(self) -> None:
        recorder = self.make_app()
        recorder.meter_stream = object()

        state_text = recorder.build_operation_state_text()

        self.assertEqual(state_text, "Durum: mikrofon seviyesi izleniyor")

    def test_build_operation_state_text_reports_monitor_state(self) -> None:
        recorder = self.make_app()
        recorder.monitor_stream = object()

        state_text = recorder.build_operation_state_text()

        self.assertEqual(state_text, "Durum: canlı monitor açık")

    def test_build_operation_state_text_reports_recording_state(self) -> None:
        recorder = self.make_app()
        recorder.recording_active = True
        recorder.recording_mode = "Sadece mikrofon"

        state_text = recorder.build_operation_state_text()

        self.assertEqual(state_text, "Durum: kayıt sürüyor (Sadece mikrofon)")

    def test_build_operation_state_text_reports_stop_request_state(self) -> None:
        recorder = self.make_app()
        recorder.recording_active = True
        recorder.stop_recording_requested = True

        state_text = recorder.build_operation_state_text()

        self.assertEqual(state_text, "Durum: kayıt durduruluyor")

    def test_build_operation_state_palette_reports_idle_colors(self) -> None:
        recorder = self.make_app()

        palette = recorder.build_operation_state_palette()

        self.assertEqual(palette, {"bg": "#182028", "fg": "#9fb0c2"})

    def test_summary_card_style_returns_compact_shared_layout(self) -> None:
        recorder = self.make_app()

        style = recorder.summary_card_style("#111111", "#eeeeee")

        self.assertEqual(
            style,
            {
                "bg": "#111111",
                "fg": "#eeeeee",
                "justify": "left",
                "wraplength": 620,
                "padx": 9,
                "pady": 7,
            },
        )

    def test_build_operation_state_palette_reports_meter_colors(self) -> None:
        recorder = self.make_app()
        recorder.meter_stream = object()

        palette = recorder.build_operation_state_palette()

        self.assertEqual(palette, {"bg": "#10283a", "fg": "#d7eefb"})

    def test_build_operation_state_palette_reports_monitor_colors(self) -> None:
        recorder = self.make_app()
        recorder.monitor_stream = object()

        palette = recorder.build_operation_state_palette()

        self.assertEqual(palette, {"bg": "#33261a", "fg": "#ffe0a8"})

    def test_build_operation_state_palette_reports_recording_colors(self) -> None:
        recorder = self.make_app()
        recorder.recording_active = True
        recorder.recording_mode = "Sadece mikrofon"

        palette = recorder.build_operation_state_palette()

        self.assertEqual(palette, {"bg": "#1f3527", "fg": "#d8f3dc"})

    def test_build_operation_state_palette_reports_stop_request_colors(self) -> None:
        recorder = self.make_app()
        recorder.recording_active = True
        recorder.stop_recording_requested = True

        palette = recorder.build_operation_state_palette()

        self.assertEqual(palette, {"bg": "#3a2316", "fg": "#ffd7a8"})

    def test_update_operation_state_summary_updates_text_and_label_style(self) -> None:
        recorder = self.make_app()
        recorder.monitor_stream = object()

        recorder.update_operation_state_summary()

        self.assertEqual(recorder.operation_state_text.get(), "Durum: canlı monitor açık")
        recorder.operation_state_label.configure.assert_called_once_with(bg="#33261a", fg="#ffe0a8")

    def test_set_recording_action_button_states_disables_start_buttons_during_recording(self) -> None:
        recorder = self.make_app()

        recorder.set_recording_action_button_states(recording_active=True)

        recorder.start_test_button.configure.assert_called_once_with(state="disabled")
        recorder.start_quick_record_button.configure.assert_called_once_with(state="disabled")
        recorder.start_recording_button.configure.assert_called_once_with(state="disabled")
        recorder.stop_recording_button.configure.assert_called_once_with(state="normal")

    def test_set_recording_action_button_states_restores_start_buttons_after_recording(self) -> None:
        recorder = self.make_app()
        recorder.backing_file = None

        recorder.set_recording_action_button_states(recording_active=False)

        recorder.start_test_button.configure.assert_called_once_with(state="normal")
        recorder.start_quick_record_button.configure.assert_called_once_with(state="normal")
        recorder.start_recording_button.configure.assert_called_once_with(state="normal")
        recorder.stop_recording_button.configure.assert_called_once_with(state="disabled")

    def test_set_recording_action_button_states_disables_quick_record_when_backing_selected(self) -> None:
        recorder = self.make_app()

        recorder.set_recording_action_button_states(recording_active=False)

        recorder.start_test_button.configure.assert_called_once_with(state="normal")
        recorder.start_quick_record_button.configure.assert_called_once_with(state="disabled")
        recorder.start_recording_button.configure.assert_called_once_with(state="normal")
        recorder.stop_recording_button.configure.assert_called_once_with(state="disabled")

    def test_set_recording_action_button_states_disables_start_buttons_when_setup_is_incomplete(self) -> None:
        recorder = self.make_app()
        recorder.current_input_device_count = 0

        recorder.set_recording_action_button_states(recording_active=False)

        recorder.start_test_button.configure.assert_called_once_with(state="disabled")
        recorder.start_quick_record_button.configure.assert_called_once_with(state="disabled")
        recorder.start_recording_button.configure.assert_called_once_with(state="disabled")
        recorder.stop_recording_button.configure.assert_called_once_with(state="disabled")

    def test_set_recent_output_button_states_disables_recent_actions(self) -> None:
        recorder = self.make_app()

        recorder.set_recent_output_button_states(enabled=False)

        recorder.open_last_export_button.configure.assert_called_once_with(state="disabled")
        recorder.play_last_export_button.configure.assert_called_once_with(state="disabled")
        recorder.copy_last_export_path_button.configure.assert_called_once_with(state="disabled")
        recorder.open_last_summary_button.configure.assert_called_once_with(state="disabled")
        recorder.copy_last_summary_button.configure.assert_called_once_with(state="disabled")
        recorder.copy_last_summary_path_button.configure.assert_called_once_with(state="disabled")
        recorder.copy_last_brief_button.configure.assert_called_once_with(state="disabled")
        recorder.export_last_brief_button.configure.assert_called_once_with(state="disabled")
        recorder.open_last_take_notes_button.configure.assert_called_once_with(state="disabled")
        recorder.copy_last_recovery_note_button.configure.assert_called_once_with(state="disabled")
        recorder.open_last_output_dir_button.configure.assert_called_once_with(state="disabled")
        recorder.open_last_preparation_button.configure.assert_called_once_with(state="disabled")

    def test_build_next_step_text_prefers_recovery_guidance_when_note_exists(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "take.mp3"
            export_path.write_text("audio", encoding="utf-8")
            recovery_note_path = Path(tmpdir) / "export_recovery_note.txt"
            recovery_note_path.write_text("recovery", encoding="utf-8")
            recorder.last_export_path = export_path
            recorder.last_recovery_note_path = recovery_note_path

            next_step = recorder.build_next_step_text()
            latest_audio = app.recent_audio_status_text(export_path)

        self.assertEqual(
            next_step,
            f"Son çıktı alma denemesi hata verdi. Kurtarma notunu inceleyin. Son iyi kayıt: {latest_audio}. Sonra ayarları değiştirip kaydı yeniden başlatın.",
        )

    def test_build_next_step_subtitle_text_prefers_recovery_state(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "take.mp3"
            export_path.write_text("audio", encoding="utf-8")
            recovery_note_path = Path(tmpdir) / "export_recovery_note.txt"
            recovery_note_path.write_text("recovery", encoding="utf-8")
            recorder.last_export_path = export_path
            recorder.last_recovery_note_path = recovery_note_path

            subtitle_text = recorder.build_next_step_subtitle_text()
            latest_audio = app.recent_audio_status_text(export_path)

        self.assertEqual(
            subtitle_text,
            f"Yeniden denemeden önce kurtarma notu kontrol edilmeli. Son iyi kayıt: {latest_audio}.",
        )

    def test_build_next_step_text_guides_microphone_mode_when_no_backing(self) -> None:
        recorder = self.make_app()
        recorder.backing_file = None

        next_step = recorder.build_next_step_text()

        self.assertEqual(next_step, "Mikrofon modu hazır. Test kaydı alın, sonra doğrudan kaydı başlatın.")

    def test_build_next_step_subtitle_text_reports_mic_only_flow(self) -> None:
        recorder = self.make_app()
        recorder.backing_file = None

        subtitle_text = recorder.build_next_step_subtitle_text()

        self.assertEqual(subtitle_text, "Sadece mikrofon akışı hazır.")

    def test_build_next_step_text_reports_missing_ffmpeg_when_mp3_enabled(self) -> None:
        recorder = self.make_app()
        recorder.backing_file = None
        recorder.wav_export_mode.set("Sadece Vokal WAV")

        with mock.patch.object(app.shutil, "which", return_value=None):
            next_step = recorder.build_next_step_text()

        self.assertEqual(next_step, "MP3 için ffmpeg eksik. ffmpeg kurun veya bu tur WAV ile devam edip önce kısa test alın.")

    def test_build_next_step_subtitle_text_reports_missing_ffmpeg_when_mp3_enabled(self) -> None:
        recorder = self.make_app()
        recorder.backing_file = None
        recorder.wav_export_mode.set("Sadece Vokal WAV")

        with mock.patch.object(app.shutil, "which", return_value=None):
            subtitle_text = recorder.build_next_step_subtitle_text()

        self.assertEqual(subtitle_text, "MP3 için ffmpeg eksik; kayıt WAV olarak devam edecek.")

    def test_build_next_step_text_guides_full_recording_when_backing_ready(self) -> None:
        recorder = self.make_app()
        recorder.backing_file = Path("/tmp/backing_track.wav")

        next_step = recorder.build_next_step_text()

        self.assertEqual(next_step, "Backing ve cihazlar hazır. Test kaydı iyi ise tam kaydı başlatabilirsiniz.")

    def test_build_next_step_subtitle_text_reports_backing_flow(self) -> None:
        recorder = self.make_app()
        recorder.backing_file = Path("/tmp/backing_track.wav")

        subtitle_text = recorder.build_next_step_subtitle_text()

        self.assertEqual(subtitle_text, "Arka planlı kayıt akışı hazır.")

    def test_build_next_step_subtitle_text_reports_missing_input(self) -> None:
        recorder = self.make_app()
        recorder.input_device_choice.set("")

        subtitle_text = recorder.build_next_step_subtitle_text()

        self.assertEqual(subtitle_text, "Önce mikrofon seçimi tamamlanmalı.")

    def test_build_next_step_subtitle_text_reports_active_recording_state(self) -> None:
        recorder = self.make_app()
        recorder.recording_active = True

        subtitle_text = recorder.build_next_step_subtitle_text()

        self.assertEqual(subtitle_text, "Kayıt aktif. Sıradaki adım durdurma olacak.")

    def test_update_next_step_summary_updates_subtitle(self) -> None:
        recorder = self.make_app()
        recorder.backing_file = None

        recorder.update_next_step_summary()

        self.assertEqual(recorder.next_step_subtitle_text.get(), "Sadece mikrofon akışı hazır.")

    def test_build_readiness_text_summarizes_ready_state(self) -> None:
        recorder = self.make_app()
        recorder.backing_file = Path("/tmp/backing_track.wav")
        readiness_text = recorder.build_readiness_text()

        self.assertIn("Genel durum: Kayda hazır", readiness_text)
        self.assertIn("Hazır olanlar: giriş, çıkış, klasör, kaynak", readiness_text)
        self.assertIn("Kaynak: Arka plan + mikrofon (backing_track.wav)", readiness_text)
        self.assertIn("Take adı: aksam_take", readiness_text)

    def test_build_readiness_subtitle_text_reports_ready_state(self) -> None:
        recorder = self.make_app()

        subtitle_text = recorder.build_readiness_subtitle_text()

        self.assertEqual(subtitle_text, "Giriş, çıkış, klasör ve kaynak hazır görünüyor.")

    def test_build_source_subtitle_text_reports_mic_only_mode(self) -> None:
        recorder = self.make_app()
        recorder.backing_file = None

        subtitle_text = recorder.build_source_subtitle_text()

        self.assertEqual(
            subtitle_text,
            "Şu an sadece mikrofon etkin. İsterseniz arka plan ekleyebilir veya hızlı kayda geçebilirsiniz.",
        )

    def test_build_source_subtitle_text_reports_backing_mode(self) -> None:
        recorder = self.make_app()

        subtitle_text = recorder.build_source_subtitle_text()

        self.assertEqual(
            subtitle_text,
            "Arka plan etkin: backing.mp3. Bu modda tam kayıt kullanılacak.",
        )

    def test_update_source_subtitle_updates_visible_subtitle(self) -> None:
        recorder = self.make_app()
        recorder.backing_file = None

        recorder.update_source_subtitle()

        self.assertEqual(
            recorder.source_subtitle_text.get(),
            "Şu an sadece mikrofon etkin. İsterseniz arka plan ekleyebilir veya hızlı kayda geçebilirsiniz.",
        )

    def test_build_output_subtitle_text_reports_single_folder_mode(self) -> None:
        recorder = self.make_app()
        recorder.session_mode.set("Tek Klasör")
        recorder.wav_export_mode.set("Sadece Vokal WAV")

        subtitle_text = recorder.build_output_subtitle_text()

        self.assertEqual(subtitle_text, "Dosyalar doğrudan /tmp/out klasörüne yazılacak.")

    def test_build_output_subtitle_text_reports_named_session_mode(self) -> None:
        recorder = self.make_app()
        recorder.wav_export_mode.set("Sadece Vokal WAV")

        subtitle_text = recorder.build_output_subtitle_text()

        self.assertEqual(subtitle_text, "Dosyalar /tmp/out içinde Akşam Kaydı klasörüne yazılacak.")

    def test_build_output_subtitle_text_reports_dated_session_mode(self) -> None:
        recorder = self.make_app()
        recorder.session_mode.set("Tarihli Oturum")
        recorder.wav_export_mode.set("Sadece Vokal WAV")

        subtitle_text = recorder.build_output_subtitle_text()

        self.assertEqual(subtitle_text, "Dosyalar /tmp/out içinde tarihli bir klasöre yazılacak.")

    def test_build_output_subtitle_text_requires_folder_selection(self) -> None:
        recorder = self.make_app()
        recorder.output_dir.set("")
        recorder.wav_export_mode.set("Sadece Vokal WAV")

        subtitle_text = recorder.build_output_subtitle_text()

        self.assertEqual(subtitle_text, "Önce bir klasör seçin. MP3 ve WAV dosyaları seçtiğiniz yere yazılacak.")

    def test_build_output_subtitle_text_reports_wav_only_when_mp3_disabled(self) -> None:
        recorder = self.make_app()
        recorder.wav_export_mode.set("Sadece WAV (Mix + Vokal)")

        subtitle_text = recorder.build_output_subtitle_text()

        self.assertEqual(subtitle_text, "Dosyalar /tmp/out içinde Akşam Kaydı klasörüne yazılacak. Yalnız WAV yazılacak.")

    def test_build_output_subtitle_text_reports_wav_only_when_folder_missing(self) -> None:
        recorder = self.make_app()
        recorder.output_dir.set("")
        recorder.wav_export_mode.set("Sadece WAV (Mix + Vokal)")

        subtitle_text = recorder.build_output_subtitle_text()

        self.assertEqual(subtitle_text, "Önce bir klasör seçin. Bu tur yalnız WAV dosyaları seçtiğiniz yere yazılacak.")

    def test_build_output_subtitle_text_mentions_wav_fallback_when_ffmpeg_missing(self) -> None:
        recorder = self.make_app()
        recorder.wav_export_mode.set("Sadece Vokal WAV")

        with mock.patch.object(app.shutil, "which", return_value=None):
            subtitle_text = recorder.build_output_subtitle_text()

        self.assertEqual(subtitle_text, "Dosyalar /tmp/out içinde Akşam Kaydı klasörüne yazılacak. MP3 yerine Mix WAV yazılacak.")

    def test_build_output_name_label_text_mentions_wav_fallback_when_ffmpeg_missing(self) -> None:
        recorder = self.make_app()
        recorder.wav_export_mode.set("Sadece Vokal WAV")

        with mock.patch.object(app.shutil, "which", return_value=None):
            label_text = recorder.build_output_name_label_text()

        self.assertEqual(label_text, "Çıkış Dosya Adı (WAV fallback)")

    def test_update_output_subtitle_updates_visible_subtitle(self) -> None:
        recorder = self.make_app()
        recorder.session_mode.set("Tek Klasör")
        recorder.wav_export_mode.set("Sadece Vokal WAV")

        recorder.update_output_subtitle()

        self.assertEqual(recorder.output_subtitle_text.get(), "Dosyalar doğrudan /tmp/out klasörüne yazılacak.")

    def test_build_readiness_text_flags_missing_items_and_auto_take_name(self) -> None:
        recorder = self.make_app()
        recorder.input_device_choice.set("")
        recorder.output_device_choice.set("")
        recorder.output_dir.set("")
        recorder.output_name.set("")
        recorder.backing_file = None
        readiness_text = recorder.build_readiness_text()

        self.assertIn("Genel durum: Eksik seçimler var", readiness_text)
        self.assertIn("Eksikler: giriş, çıkış, klasör", readiness_text)
        self.assertIn("Kaynak: Sadece mikrofon (90 sn)", readiness_text)
        self.assertIn("Take adı: otomatik oluşturulacak", readiness_text)

    def test_build_readiness_subtitle_text_reports_missing_items(self) -> None:
        recorder = self.make_app()
        recorder.output_dir.set("")

        subtitle_text = recorder.build_readiness_subtitle_text()

        self.assertEqual(subtitle_text, "Eksik seçimler: klasör")

    def test_build_readiness_subtitle_text_prioritizes_recovery_note(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "take.mp3"
            export_path.write_text("audio", encoding="utf-8")
            recovery_note_path = Path(tmpdir) / "export_recovery_note.txt"
            recovery_note_path.write_text("recovery", encoding="utf-8")
            recorder.last_export_path = export_path
            recorder.last_recovery_note_path = recovery_note_path

            subtitle_text = recorder.build_readiness_subtitle_text()
            latest_audio = app.recent_audio_status_text(export_path)

        self.assertEqual(
            subtitle_text,
            f"Hazırlık tamamlanmadan önce kurtarma notunu kontrol edin. Son iyi kayıt: {latest_audio}.",
        )

    def test_build_readiness_text_mentions_missing_ffmpeg_when_mp3_enabled(self) -> None:
        recorder = self.make_app()
        recorder.wav_export_mode.set("Sadece Vokal WAV")

        with mock.patch.object(app.shutil, "which", return_value=None):
            readiness_text = recorder.build_readiness_text()

        self.assertIn("MP3 durumu: ffmpeg eksik, çıktı WAV olarak kalacak", readiness_text)

    def test_build_readiness_subtitle_text_mentions_missing_ffmpeg_when_mp3_enabled(self) -> None:
        recorder = self.make_app()
        recorder.wav_export_mode.set("Sadece Vokal WAV")

        with mock.patch.object(app.shutil, "which", return_value=None):
            subtitle_text = recorder.build_readiness_subtitle_text()

        self.assertEqual(subtitle_text, "Temel hazırlık tamam. MP3 için ffmpeg eksik.")

    def test_build_readiness_palette_reports_ready_colors(self) -> None:
        recorder = self.make_app()

        palette = recorder.build_readiness_palette()

        self.assertEqual(palette, {"bg": "#1f2b22", "fg": "#d8f3dc"})

    def test_build_readiness_palette_reports_attention_colors_when_items_missing(self) -> None:
        recorder = self.make_app()
        recorder.output_dir.set("")

        palette = recorder.build_readiness_palette()

        self.assertEqual(palette, {"bg": "#2c2418", "fg": "#ffe7b3"})

    def test_update_readiness_summary_updates_text_and_label_style(self) -> None:
        recorder = self.make_app()
        recorder.output_dir.set("")

        recorder.update_readiness_summary()

        self.assertEqual(recorder.readiness_subtitle_text.get(), "Eksik seçimler: klasör")
        self.assertIn("Eksikler: klasör", recorder.readiness_text.get())
        recorder.readiness_label.configure.assert_called_once_with(bg="#2c2418", fg="#ffe7b3")

    def test_build_recent_output_summary_text_reports_recording_state(self) -> None:
        recorder = self.make_app()
        recorder.recording_active = True

        summary_text = recorder.build_recent_output_summary_text()

        self.assertEqual(summary_text, "Canlı kayıt sürüyor. Son çıktı işlemleri kayıt bitince yeniden açılacak.")

    def test_build_recent_output_subtitle_text_reports_recording_state(self) -> None:
        recorder = self.make_app()
        recorder.recording_active = True

        subtitle_text = recorder.build_recent_output_subtitle_text()

        self.assertEqual(subtitle_text, "Kayıt sürerken eski çıktı işlemleri geçici olarak kapalıdır.")

    def test_build_recent_output_summary_text_prioritizes_recovery_note(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            export_path = output_dir / "take.mp3"
            export_path.write_text("audio", encoding="utf-8")
            recovery_path = output_dir / "export_recovery_note.txt"
            recovery_path.write_text("recovery", encoding="utf-8")
            recorder.last_export_path = export_path
            recorder.last_recovery_note_path = recovery_path

            summary_text = recorder.build_recent_output_summary_text()
            latest_audio = app.recent_audio_status_text(export_path)

        self.assertEqual(
            summary_text,
            f"Kurtarma notu hazır. Son iyi kayıt: {latest_audio}. Önce notu kopyalayın, sonra son kaydı veya klasörü açın.",
        )

    def test_build_recent_output_subtitle_text_prioritizes_recovery_note(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            export_path = output_dir / "take.mp3"
            export_path.write_text("audio", encoding="utf-8")
            recovery_path = output_dir / "export_recovery_note.txt"
            recovery_path.write_text("recovery", encoding="utf-8")
            recorder.last_export_path = export_path
            recorder.last_recovery_note_path = recovery_path

            subtitle_text = recorder.build_recent_output_subtitle_text()
            latest_audio = app.recent_audio_status_text(export_path)

        self.assertEqual(
            subtitle_text,
            f"Sorun yaşandıysa önce kurtarma notunu inceleyin. Son iyi kayıt: {latest_audio}.",
        )

    def test_build_recent_output_summary_text_prefers_last_export_actions(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            export_path = output_dir / "take.mp3"
            summary_path = output_dir / "session_summary.json"
            notes_path = output_dir / "take_notes.txt"
            prep_path = output_dir / "preparation_summary.txt"
            export_path.write_text("audio", encoding="utf-8")
            summary_path.write_text("{}", encoding="utf-8")
            notes_path.write_text("notes", encoding="utf-8")
            prep_path.write_text("prep", encoding="utf-8")
            recorder.last_export_path = export_path
            recorder.last_summary_path = summary_path
            recorder.last_take_notes_path = notes_path
            recorder.last_preparation_summary_path = prep_path

            summary_text = recorder.build_recent_output_summary_text()
            latest_audio = app.recent_audio_status_text(export_path)

        self.assertEqual(
            summary_text,
            f"Hazır: son kayıt {latest_audio}, özet, take notu, hazırlık dosyası. Önce son kaydı açın veya oynatın.",
        )

    def test_build_recent_output_subtitle_text_includes_latest_audio_summary(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            export_path = output_dir / "take.mp3"
            export_path.write_text("audio", encoding="utf-8")
            recorder.last_export_path = export_path

            subtitle_text = recorder.build_recent_output_subtitle_text()

        self.assertEqual(
            subtitle_text,
            f"Son kayıt hazır: {app.recent_audio_status_text(export_path)}. Dosyayı açabilir, oynatabilir veya yolları kopyalayabilirsiniz.",
        )

    def test_update_recent_output_summary_updates_text_and_label_style(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            summary_path = output_dir / "session_summary.json"
            summary_path.write_text("{}", encoding="utf-8")
            recorder.last_summary_path = summary_path

            recorder.update_recent_output_summary()

        self.assertEqual(recorder.recent_output_subtitle_text.get(), "Özet hazır. Oturum bilgisini açabilir veya kopyalayabilirsiniz.")
        self.assertEqual(recorder.recent_output_summary_text.get(), "Hazır: oturum özeti. Önce özeti açın veya kısa raporu kopyalayın.")
        recorder.recent_output_summary_label.configure.assert_called_once_with(bg="#1f2b22", fg="#d8f3dc")

    def test_build_recent_output_summary_text_reports_preparation_file_when_it_is_only_artifact(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            prep_path = output_dir / "preparation_summary.txt"
            prep_path.write_text("prep", encoding="utf-8")
            recorder.last_preparation_summary_path = prep_path

            summary_text = recorder.build_recent_output_summary_text()
            subtitle_text = recorder.build_recent_output_subtitle_text()

        self.assertEqual(summary_text, "Hazır: hazırlık dosyası. Önce dosyayı açın veya klasörü açın.")
        self.assertEqual(subtitle_text, "Hazırlık dosyası hazır. Dosyayı açabilir veya oturum klasörüne geçebilirsiniz.")

    def test_build_action_guidance_text_prefers_test_then_quick_for_mic_mode(self) -> None:
        recorder = self.make_app()
        recorder.backing_file = None

        guidance_text = recorder.build_action_guidance_text()

        self.assertIn("Önce 5 saniyelik test yapın.", guidance_text)
        self.assertIn("Hızlı Kayıt hızlı yol", guidance_text)

    def test_build_action_subtitle_text_prefers_mic_only_flow(self) -> None:
        recorder = self.make_app()
        recorder.backing_file = None

        subtitle_text = recorder.build_action_subtitle_text()

        self.assertEqual(subtitle_text, "Önce test yapın, sonra hızlı kayıt veya tam kayıt seçin.")

    def test_build_action_subtitle_text_prefers_full_record_when_backing_selected(self) -> None:
        recorder = self.make_app()

        subtitle_text = recorder.build_action_subtitle_text()

        self.assertEqual(subtitle_text, "Önce test yapın, sonra tam kayda geçin. Hızlı kayıt bu modda kapalıdır.")

    def test_build_action_guidance_text_prefers_full_record_when_backing_selected(self) -> None:
        recorder = self.make_app()

        guidance_text = recorder.build_action_guidance_text()

        self.assertEqual(guidance_text, "Önerilen sıra: 5 saniyelik test ile dengeyi kontrol edin. Denge doğruysa tam kaydı başlatın.")

    def test_build_action_subtitle_text_reports_recording_lock_state(self) -> None:
        recorder = self.make_app()
        recorder.recording_active = True

        subtitle_text = recorder.build_action_subtitle_text()

        self.assertEqual(subtitle_text, "Kayıt sürüyor. Bu bölüm geçici olarak kilitli.")

    def test_update_action_subtitle_updates_visible_subtitle(self) -> None:
        recorder = self.make_app()
        recorder.backing_file = None

        recorder.update_action_subtitle()

        self.assertEqual(recorder.action_subtitle_text.get(), "Önce test yapın, sonra hızlı kayıt veya tam kayıt seçin.")

    def test_build_progress_subtitle_text_reports_idle_state(self) -> None:
        recorder = self.make_app()

        subtitle_text = recorder.build_progress_subtitle_text()

        self.assertEqual(subtitle_text, "Kayıt başlamadığında son durum burada görünür.")

    def test_build_progress_subtitle_text_reports_active_recording_state(self) -> None:
        recorder = self.make_app()
        recorder.recording_active = True

        subtitle_text = recorder.build_progress_subtitle_text()

        self.assertEqual(subtitle_text, "Kayıt sürerken geçen ve kalan süre burada yenilenir.")

    def test_build_progress_subtitle_text_reports_stop_request_state(self) -> None:
        recorder = self.make_app()
        recorder.recording_active = True
        recorder.stop_recording_requested = True

        subtitle_text = recorder.build_progress_subtitle_text()

        self.assertEqual(subtitle_text, "Kayıt durduruluyor. Elde edilen bölüm hazırlanıyor.")

    def test_update_progress_subtitle_updates_visible_subtitle(self) -> None:
        recorder = self.make_app()
        recorder.recording_active = True

        recorder.update_progress_subtitle()

        self.assertEqual(recorder.progress_subtitle_text.get(), "Kayıt sürerken geçen ve kalan süre burada yenilenir.")

    def test_build_quick_record_button_text_reports_mic_only_mode(self) -> None:
        recorder = self.make_app()
        recorder.backing_file = None

        button_text = recorder.build_quick_record_button_text()

        self.assertEqual(button_text, "Hızlı Kayıt (Sadece Mikrofon)")

    def test_build_quick_record_button_text_reports_backing_requires_full_record(self) -> None:
        recorder = self.make_app()

        button_text = recorder.build_quick_record_button_text()

        self.assertEqual(button_text, "Hızlı Kayıt (Sadece Mikrofon Modunda)")

    def test_build_main_record_button_text_reports_backing_mode(self) -> None:
        recorder = self.make_app()

        button_text = recorder.build_main_record_button_text()

        self.assertEqual(button_text, "Tam Kayıt (Arka Plan + Mikrofon)")

    def test_update_action_button_copy_updates_visible_button_labels(self) -> None:
        recorder = self.make_app()

        recorder.update_action_button_copy()

        recorder.start_quick_record_button.configure.assert_called_once_with(text="Hızlı Kayıt (Sadece Mikrofon Modunda)")
        recorder.start_recording_button.configure.assert_called_once_with(text="Tam Kayıt (Arka Plan + Mikrofon)")

    def test_build_action_guidance_text_requires_input_selection_first(self) -> None:
        recorder = self.make_app()
        recorder.input_device_choice.set("")

        guidance_text = recorder.build_action_guidance_text()

        self.assertEqual(
            guidance_text,
            "Önerilen sıra: 1. Mikrofonları tara. 2. Girişi seç. 3. Sonra 5 saniyelik testi çalıştır.",
        )

    def test_build_action_guidance_text_prefers_recovery_before_retry(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "take.mp3"
            export_path.write_text("audio", encoding="utf-8")
            recovery_note_path = Path(tmpdir) / "export_recovery_note.txt"
            recovery_note_path.write_text("recovery", encoding="utf-8")
            recorder.last_export_path = export_path
            recorder.last_recovery_note_path = recovery_note_path

            guidance_text = recorder.build_action_guidance_text()
            latest_audio = app.recent_audio_status_text(export_path)

        self.assertEqual(
            guidance_text,
            f"Önerilen sıra: Önce kurtarma notunu inceleyin. Son iyi kayıt: {latest_audio}. Ardından kısa test yapın, sonra tam kaydı yeniden başlatın.",
        )

    def test_build_action_guidance_text_during_active_recording_uses_stop_only_message(self) -> None:
        recorder = self.make_app()
        recorder.recording_active = True

        guidance_text = recorder.build_action_guidance_text()

        self.assertEqual(guidance_text, "Önerilen sıra: Kayıt sürüyor. Şu anda yalnız durdur butonunu kullanın.")

    def test_build_action_guidance_text_after_stop_request_waits_for_processing(self) -> None:
        recorder = self.make_app()
        recorder.recording_active = True
        recorder.stop_recording_requested = True

        guidance_text = recorder.build_action_guidance_text()

        self.assertEqual(
            guidance_text,
            "Önerilen sıra: Durdurma istendi. Kayıt bölümü hazırlanırken yeni işlem başlatmayın.",
        )

    def test_start_quick_record_thread_blocks_when_backing_is_selected(self) -> None:
        recorder = self.make_app()
        recorder.stop_live_monitor = mock.Mock()

        recorder.start_quick_record_thread()

        recorder.stop_live_monitor.assert_not_called()
        self.assertEqual(
            recorder.status_messages[-1],
            "Hızlı Kayıt sadece mikrofon modunda kullanılabilir. Arka planı temizleyin veya tam kaydı başlatın.",
        )

    def test_start_test_thread_blocks_when_input_device_is_missing(self) -> None:
        recorder = self.make_app()
        recorder.current_input_device_count = 0

        with mock.patch.object(app.threading, "Thread") as thread_mock:
            recorder.start_test_thread()

        thread_mock.assert_not_called()
        self.assertEqual(
            recorder.status_messages[-1],
            "Test başlamadan önce mikrofonu görünür hale getirip yeniden tarayın.",
        )

    def test_start_recording_thread_blocks_when_output_device_is_missing(self) -> None:
        recorder = self.make_app()
        recorder.current_output_device_count = 0
        recorder.stop_live_monitor = mock.Mock()

        with mock.patch.object(app.threading, "Thread") as thread_mock:
            recorder.start_recording_thread()

        thread_mock.assert_not_called()
        recorder.stop_live_monitor.assert_not_called()
        self.assertEqual(
            recorder.status_messages[-1],
            "Kayıt başlamadan önce çıkışı görünür hale getirip yeniden tarayın.",
        )

    def test_start_quick_record_thread_blocks_when_output_dir_is_missing(self) -> None:
        recorder = self.make_app()
        recorder.backing_file = None
        recorder.output_dir.set("")
        recorder.stop_live_monitor = mock.Mock()

        with mock.patch.object(app.threading, "Thread") as thread_mock:
            recorder.start_quick_record_thread()

        thread_mock.assert_not_called()
        recorder.stop_live_monitor.assert_not_called()
        self.assertEqual(recorder.status_messages[-1], "Hızlı kayıt öncesi çıkış klasörü seçin.")

    def test_build_preflight_warning_text_requires_output_dir_first(self) -> None:
        recorder = self.make_app()
        recorder.output_dir.set("")

        warning_text = recorder.build_preflight_warning_text()

        self.assertEqual(warning_text, "Ön uyarı: kayıt klasörü seçilmedi.")

    def test_build_preflight_subtitle_text_requires_output_dir_first(self) -> None:
        recorder = self.make_app()
        recorder.output_dir.set("")

        subtitle_text = recorder.build_preflight_subtitle_text()

        self.assertEqual(subtitle_text, "Önce kayıt klasörünü seçin.")

    def test_build_preflight_warning_text_flags_clipping_risk(self) -> None:
        recorder = self.make_app()
        recorder.last_input_peak = 0.99

        warning_text = recorder.build_preflight_warning_text()

        self.assertEqual(warning_text, "Ön uyarı: giriş çok yüksek, gain düşürmeden kayda başlamayın.")

    def test_build_preflight_subtitle_text_flags_clipping_risk(self) -> None:
        recorder = self.make_app()
        recorder.last_input_peak = 0.99

        subtitle_text = recorder.build_preflight_subtitle_text()

        self.assertEqual(subtitle_text, "Giriş seviyesi fazla yüksek.")

    def test_build_preflight_warning_text_flags_very_low_input(self) -> None:
        recorder = self.make_app()
        recorder.last_input_peak = 0.005

        warning_text = recorder.build_preflight_warning_text()

        self.assertEqual(warning_text, "Ön uyarı: giriş çok zayıf, önce kısa test yapın.")

    def test_build_preflight_subtitle_text_flags_very_low_input(self) -> None:
        recorder = self.make_app()
        recorder.last_input_peak = 0.005

        subtitle_text = recorder.build_preflight_subtitle_text()

        self.assertEqual(subtitle_text, "Giriş seviyesi neredeyse yok.")

    def test_build_preflight_warning_text_reports_ready_when_level_is_good(self) -> None:
        recorder = self.make_app()
        recorder.last_input_peak = 0.32

        warning_text = recorder.build_preflight_warning_text()

        self.assertEqual(warning_text, "Hazır: seviye uygun görünüyor, kısa testten sonra kayda geçebilirsiniz.")

    def test_build_preflight_subtitle_text_reports_ready_state(self) -> None:
        recorder = self.make_app()
        recorder.last_input_peak = 0.32

        subtitle_text = recorder.build_preflight_subtitle_text()

        self.assertEqual(subtitle_text, "Ön kontrol temiz görünüyor.")

    def test_build_preflight_warning_text_reports_missing_ffmpeg_for_mp3(self) -> None:
        recorder = self.make_app()
        recorder.wav_export_mode.set("Sadece Vokal WAV")
        with mock.patch.object(app.shutil, "which", return_value=None):
            warning_text = recorder.build_preflight_warning_text()

        self.assertEqual(warning_text, "Ön uyarı: MP3 açık ama ffmpeg yok, kayıt WAV olarak kalacak.")

    def test_build_preflight_subtitle_text_reports_missing_ffmpeg_for_mp3(self) -> None:
        recorder = self.make_app()
        recorder.wav_export_mode.set("Sadece Vokal WAV")
        with mock.patch.object(app.shutil, "which", return_value=None):
            subtitle_text = recorder.build_preflight_subtitle_text()

        self.assertEqual(subtitle_text, "MP3 için ffmpeg kurulmalı veya WAV ile devam edilmeli.")

    def test_build_preflight_subtitle_text_prioritizes_recovery_note(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "take.mp3"
            export_path.write_text("audio", encoding="utf-8")
            recovery_note_path = Path(tmpdir) / "export_recovery_note.txt"
            recovery_note_path.write_text("recovery", encoding="utf-8")
            recorder.last_export_path = export_path
            recorder.last_recovery_note_path = recovery_note_path

            subtitle_text = recorder.build_preflight_subtitle_text()
            latest_audio = app.recent_audio_status_text(export_path)

        self.assertEqual(
            subtitle_text,
            f"Son hatayı incelemeden yeni kayıt başlatmayın. Son iyi kayıt: {latest_audio}.",
        )

    def test_build_preflight_warning_text_prioritizes_recovery_note_with_last_good_take(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "take.mp3"
            export_path.write_text("audio", encoding="utf-8")
            recovery_note_path = Path(tmpdir) / "export_recovery_note.txt"
            recovery_note_path.write_text("recovery", encoding="utf-8")
            recorder.last_export_path = export_path
            recorder.last_recovery_note_path = recovery_note_path

            warning_text = recorder.build_preflight_warning_text()
            latest_audio = app.recent_audio_status_text(export_path)

        self.assertEqual(
            warning_text,
            f"Ön uyarı: son çıktı için kurtarma notu var (export_recovery_note.txt). Son iyi kayıt: {latest_audio}.",
        )

    def test_update_preflight_warning_summary_updates_subtitle(self) -> None:
        recorder = self.make_app()
        recorder.output_dir.set("")

        recorder.update_preflight_warning_summary()

        self.assertEqual(recorder.preflight_subtitle_text.get(), "Önce kayıt klasörünü seçin.")

    def test_build_option_explanation_text_summarizes_selected_behaviors(self) -> None:
        recorder = self.make_app()
        recorder.mp3_quality.set("320 kbps")
        recorder.wav_export_mode.set("Mix + Vokal WAV")
        recorder.monitor_level.set(140)
        recorder.speed_ratio.set(85)
        recorder.limiter_enabled.set("Açık")

        option_text = recorder.build_option_explanation_text()

        self.assertIn("MP3: en yüksek sabit kalite", option_text)
        self.assertIn("WAV: mix + vokal ayrı yazılacak", option_text)
        self.assertIn("İzleme: yüksek (%140)", option_text)
        self.assertIn("Hız: daha yavaş (%85)", option_text)
        self.assertIn("Limiter: açık, tepeler sınırlanacak", option_text)

    def test_build_option_subtitle_text_reports_default_selection(self) -> None:
        recorder = self.make_app()

        subtitle_text = recorder.build_option_subtitle_text()

        self.assertEqual(subtitle_text, "MP3 kapalı | tüm WAV dosyaları | limiter açık")

    def test_build_option_subtitle_text_reports_mp3_and_mix_vocal_mode(self) -> None:
        recorder = self.make_app()
        recorder.wav_export_mode.set("Mix + Vokal WAV")
        recorder.limiter_enabled.set("Kapalı")

        subtitle_text = recorder.build_option_subtitle_text()

        self.assertEqual(subtitle_text, "MP3 açık | mix + vokal WAV | limiter kapalı")

    def test_update_option_explanation_summary_updates_subtitle(self) -> None:
        recorder = self.make_app()
        recorder.wav_export_mode.set("Sadece Vokal WAV")

        recorder.update_option_explanation_summary()

        self.assertEqual(recorder.option_subtitle_text.get(), "MP3 açık | yalnız vokal WAV | limiter açık")

    def test_build_option_subtitle_text_flags_missing_ffmpeg_when_mp3_enabled(self) -> None:
        recorder = self.make_app()
        recorder.wav_export_mode.set("Sadece Vokal WAV")
        with mock.patch.object(app.shutil, "which", return_value=None):
            subtitle_text = recorder.build_option_subtitle_text()
            option_text = recorder.build_option_explanation_text()

        self.assertEqual(subtitle_text, "MP3 açık (ffmpeg eksik) | yalnız vokal WAV | limiter açık")
        self.assertIn("MP3: ffmpeg eksik", option_text)

    def test_build_tone_subtitle_text_reports_default_tone_summary(self) -> None:
        recorder = self.make_app()

        subtitle_text = recorder.build_tone_subtitle_text()

        self.assertEqual(subtitle_text, "Kazanç 7 dB | boost 2 dB | temiz/sakin drive | high-pass 80 Hz")

    def test_build_tone_subtitle_text_reports_high_drive(self) -> None:
        recorder = self.make_app()
        recorder.distortion.set(70)

        subtitle_text = recorder.build_tone_subtitle_text()

        self.assertEqual(subtitle_text, "Kazanç 7 dB | boost 2 dB | yüksek drive | high-pass 80 Hz")

    def test_build_mix_subtitle_text_reports_mix_summary(self) -> None:
        recorder = self.make_app()

        subtitle_text = recorder.build_mix_subtitle_text()

        self.assertEqual(
            subtitle_text,
            "Arka plan %75 | vokal %88 | gürültü azaltma %12 | izleme %95 | kompresör %15 | limiter açık",
        )

    def test_build_merge_summary_text_reports_mic_only_mode(self) -> None:
        recorder = self.make_app()
        recorder.backing_file = None

        merge_text = recorder.build_merge_summary_text()

        self.assertEqual(merge_text, "Kanal: kapalı\nDurum: yalnız mikrofon kaydı\nHızlı Kayıt: açık")

    def test_build_merge_summary_text_reports_backing_mix_mode(self) -> None:
        recorder = self.make_app()
        recorder.backing_file = Path("/tmp/backing_track.wav")
        recorder.wav_export_mode.set("Sadece Vokal WAV")

        with mock.patch.object(app.shutil, "which", return_value="/opt/homebrew/bin/ffmpeg"):
            merge_text = recorder.build_merge_summary_text()

        self.assertIn("Kanal: arka plan + mikrofon", merge_text)
        self.assertIn("Dosya: backing_track.wav", merge_text)
        self.assertIn("Denge: müzik %75 | vokal %88", merge_text)
        self.assertIn("Çıktı: MP3 (Yüksek VBR), Vokal WAV", merge_text)
        self.assertIn("Akış: önce test, sonra tam kayıt", merge_text)

    def test_build_merge_subtitle_text_reports_wav_fallback_when_ffmpeg_missing(self) -> None:
        recorder = self.make_app()
        recorder.wav_export_mode.set("Sadece Vokal WAV")

        with mock.patch.object(app.shutil, "which", return_value=None):
            subtitle_text = recorder.build_merge_subtitle_text()

        self.assertEqual(subtitle_text, "Arka planlı kayıt hazır. MP3 yerine Mix WAV yazılacak.")

    def test_update_tone_and_mix_subtitles_refresh_visible_state(self) -> None:
        recorder = self.make_app()

        recorder.update_tone_subtitle()
        recorder.update_mix_subtitle()
        recorder.update_merge_summary()

        self.assertEqual(recorder.tone_subtitle_text.get(), "Kazanç 7 dB | boost 2 dB | temiz/sakin drive | high-pass 80 Hz")
        self.assertEqual(
            recorder.mix_subtitle_text.get(),
            "Arka plan %75 | vokal %88 | gürültü azaltma %12 | izleme %95 | kompresör %15 | limiter açık",
        )
        self.assertEqual(recorder.merge_subtitle_text.get(), "Arka planlı kayıt hazır. Önce test yapın, sonra tam kayda geçin.")
        self.assertIn("Dosya: backing.mp3", recorder.merge_summary_text.get())

    def test_on_slider_settings_changed_refreshes_dependent_summaries(self) -> None:
        recorder = self.make_app()
        recorder.update_option_explanation_summary = mock.Mock()

        recorder.on_slider_settings_changed("85")

        self.assertEqual(recorder.tone_subtitle_text.get(), "Kazanç 7 dB | boost 2 dB | temiz/sakin drive | high-pass 80 Hz")
        self.assertEqual(
            recorder.mix_subtitle_text.get(),
            "Arka plan %75 | vokal %88 | gürültü azaltma %12 | izleme %95 | kompresör %15 | limiter açık",
        )
        self.assertIn("Denge: müzik %75 | vokal %88", recorder.merge_summary_text.get())
        recorder.update_option_explanation_summary.assert_called_once_with()

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
            output_dir = Path(tmpdir) / "Akşam Kaydı"
            summary_path = output_dir / "session_summary.json"

            with mock.patch.object(app, "LAST_SESSION_PATH", state_path):
                recorder.write_last_session_state(output_dir, summary_path)
                loaded = recorder.load_last_session_state()

        self.assertEqual(loaded["app_version"], "1.1.3")
        self.assertEqual(loaded["output_dir"], str(output_dir))
        self.assertEqual(loaded["session_mode"], "İsimli Oturum")
        self.assertEqual(loaded["session_name"], "Akşam Kaydı")
        self.assertEqual(loaded["preset_name"], "Temiz Gitar")
        self.assertEqual(loaded["last_export_path"], "")
        self.assertEqual(loaded["take_notes_path"], "")
        self.assertEqual(loaded["recovery_note_path"], "")
        self.assertEqual(loaded["preparation_summary_path"], "")
        self.assertEqual(loaded["summary_path"], str(summary_path))

    def test_reload_last_session_for_named_session_sets_parent_dir_and_loads_preset(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir) / "exports"
            session_dir = base_dir / "Akşam Kaydı"
            session_dir.mkdir(parents=True)
            state_path = Path(tmpdir) / ".last_session.json"
            state_path.write_text(
                json.dumps(
                    {
                        "output_dir": str(session_dir),
                        "session_mode": "İsimli Oturum",
                        "preset_name": "Parlak Solo",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with mock.patch.object(app, "LAST_SESSION_PATH", state_path):
                recorder.reload_last_session()

        self.assertEqual(recorder.output_dir.get(), str(base_dir))
        self.assertEqual(recorder.session_name.get(), "Akşam Kaydı")
        self.assertEqual(recorder.session_mode.get(), "İsimli Oturum")
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
                        "session_mode": "Tek Klasör",
                        "preset_name": "",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with mock.patch.object(app, "LAST_SESSION_PATH", state_path):
                recorder.reload_last_session()

        self.assertEqual(recorder.output_dir.get(), str(output_dir))
        self.assertEqual(recorder.session_mode.get(), "Tek Klasör")
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
                        "session_mode": "Tek Klasör",
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
            preparation_path = output_dir / "preparation_summary.txt"
            preparation_path.write_text("prep", encoding="utf-8")
            state_path = Path(tmpdir) / ".last_session.json"
            state_path.write_text(
                json.dumps(
                    {
                        "output_dir": str(output_dir),
                        "session_mode": "Tek Klasör",
                        "take_notes_path": str(take_notes_path),
                        "recovery_note_path": str(recovery_note_path),
                        "preparation_summary_path": str(preparation_path),
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with mock.patch.object(app, "LAST_SESSION_PATH", state_path):
                recorder.reload_last_session()

        self.assertEqual(recorder.last_take_notes_path, take_notes_path)
        self.assertEqual(recorder.last_recovery_note_path, recovery_note_path)
        self.assertEqual(recorder.last_preparation_summary_path, preparation_path)

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
                        "session_mode": "Tek Klasör",
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
                        "session_mode": "Tek Klasör",
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
