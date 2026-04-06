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
    app = load_module("app_test_export_views", "app.py")


class FakeVar:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value) -> None:
        self.value = value


class FakeMenu:
    def __init__(self) -> None:
        self.deleted = []
        self.commands = []

    def delete(self, start, end) -> None:
        self.deleted.append((start, end))

    def add_command(self, label, command) -> None:
        self.commands.append((label, command))


class FakeOptionMenu:
    def __init__(self) -> None:
        self.menu = FakeMenu()

    def __getitem__(self, key):
        if key != "menu":
            raise KeyError(key)
        return self.menu


class ExportAndDeviceViewTests(unittest.TestCase):
    def make_app(self) -> app.GuitarAmpRecorderApp:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        recorder.root = mock.Mock()
        recorder.recent_exports_text = FakeVar("")
        recorder.recent_output_summary_text = FakeVar("")
        recorder.recent_output_filter = FakeVar("Tümü")
        recorder.recent_output_meta_text = FakeVar("")
        recorder.prep_summary_text = FakeVar("")
        recorder.prep_subtitle_text = FakeVar("")
        recorder.prep_status_text = FakeVar("")
        recorder.prep_meta_text = FakeVar("")
        recorder.next_step_text = FakeVar("")
        recorder.selected_route_text = FakeVar("")
        recorder.output_dir = FakeVar("/tmp/gar-default-out")
        recorder.preset_name = FakeVar("Temiz Gitar")
        recorder.preset_note = FakeVar("")
        recorder.share_title = FakeVar("")
        recorder.share_description = FakeVar("")
        recorder.share_image_path = FakeVar("")
        recorder.share_meta_text = FakeVar("")
        recorder.session_mode = FakeVar("Tek Klasör")
        recorder.session_name = FakeVar("session_20260404")
        recorder.input_device_choice = FakeVar("Varsayılan macOS girişi")
        recorder.output_device_choice = FakeVar("Varsayılan macOS çıkışı")
        recorder.mp3_quality = FakeVar("Yüksek VBR")
        recorder.wav_export_mode = FakeVar("Sadece Vokal WAV")
        recorder.mic_record_seconds = FakeVar("60")
        recorder.input_device_id = FakeVar("")
        recorder.output_device_id = FakeVar("")
        recorder.device_summary_text = FakeVar("")
        recorder.setup_hint_text = FakeVar("")
        recorder.setup_status_text = FakeVar("")
        recorder.setup_next_text = FakeVar("")
        recorder.mp3_quality_label_text = FakeVar("")
        recorder.recording_active = False
        recorder.current_input_device_count = 0
        recorder.current_output_device_count = 0
        recorder.status_messages = []
        recorder.set_status = recorder.status_messages.append
        recorder.refresh_device_menus = mock.Mock()
        recorder.restart_input_meter = mock.Mock()
        recorder.backing_label = mock.Mock()
        recorder.recent_output_summary_label = mock.Mock()
        recorder.prep_status_label = mock.Mock()
        recorder.setup_status_label = mock.Mock()
        recorder.setup_next_label = mock.Mock()
        recorder.mp3_quality_menu = mock.Mock()
        recorder.input_device_menu = FakeOptionMenu()
        recorder.output_device_menu = FakeOptionMenu()
        recorder.backing_file = None
        recorder.last_output_dir = None
        recorder.last_export_path = None
        recorder.last_summary_path = None
        recorder.last_take_notes_path = None
        recorder.last_recovery_note_path = None
        recorder.last_preparation_summary_path = None
        recorder.last_share_package_dir = None
        recorder.open_preparation_button = mock.Mock()
        recorder.open_last_preparation_button = mock.Mock()
        recorder.open_last_output_dir_button = mock.Mock()
        recorder.archive_last_session_button = mock.Mock()
        recorder.reset_session_state_button = mock.Mock()
        recorder.cleanup_old_trials_button = mock.Mock()
        recorder.resolve_output_dir = mock.Mock(return_value=Path("/tmp/gar-default-out"))
        recorder.write_last_session_state = mock.Mock()
        recorder.update_recent_output_summary = mock.Mock()
        recorder.update_compact_status_summary = mock.Mock()
        recorder.update_recording_prep_summary = mock.Mock()
        recorder.update_recording_prep_subtitle = mock.Mock()
        recorder.update_next_step_summary = mock.Mock()
        recorder.update_readiness_summary = mock.Mock()
        recorder.update_preflight_warning_summary = mock.Mock()
        recorder.update_action_guidance_summary = mock.Mock()
        recorder.plan_session_hint = mock.Mock(return_value="Tek Klasör")
        recorder.plan_take_name_hint = mock.Mock(return_value="take_001")
        recorder.planned_output_labels = mock.Mock(return_value=["MP3", "Vokal WAV"])
        return recorder

    def test_refresh_recent_exports_shows_newest_audio_and_artifact_files(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            files = []
            for index in range(6):
                suffix = ".mp3" if index % 2 == 0 else ".wav"
                path = output_dir / f"take_{index}{suffix}"
                path.write_text("audio", encoding="utf-8")
                os.utime(path, (time.time() + index, time.time() + index))
                files.append(path)
            for offset, name in enumerate(
                ["session_summary.json", "take_notes.txt", "preparation_summary.txt", "session_brief.txt"]
            ):
                path = output_dir / name
                path.write_text(name, encoding="utf-8")
                os.utime(path, (time.time() + 10 + offset, time.time() + 10 + offset))
                files.append(path)
            (output_dir / "ignore.txt").write_text("skip", encoding="utf-8")

            recorder.resolve_output_dir = mock.Mock(return_value=output_dir)
            recorder.refresh_recent_exports()
            expected_lines = [app.recent_output_file_line(path) for path in sorted(files, key=lambda path: path.stat().st_mtime, reverse=True)[:8]]
            latest_audio = app.latest_audio_file_in_dir(output_dir)
            expected = f"{app.recent_audio_highlight_line(latest_audio)}\n\n" + "\n".join(expected_lines)

        self.assertEqual(recorder.recent_exports_text.get(), expected)

    def test_refresh_recent_exports_handles_missing_dir(self) -> None:
        recorder = self.make_app()
        missing_dir = Path("/tmp/does-not-exist-gar")
        recorder.resolve_output_dir = mock.Mock(return_value=missing_dir)

        recorder.refresh_recent_exports()

        self.assertEqual(recorder.recent_exports_text.get(), f"Klasör bulunamadı: {missing_dir}")

    def test_refresh_recent_exports_prefers_last_output_dir(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            newer = output_dir / "latest_take.wav"
            newer.write_text("audio", encoding="utf-8")
            recorder.last_output_dir = output_dir
            recorder.resolve_output_dir = mock.Mock(return_value=Path("/tmp/unused-output"))

            recorder.refresh_recent_exports()
            expected = f"{app.recent_audio_highlight_line(newer)}\n\n{app.recent_output_file_line(newer)}"

        self.assertEqual(recorder.recent_exports_text.get(), expected)
        recorder.resolve_output_dir.assert_not_called()

    def test_cleanup_candidate_output_files_targets_legacy_quick_takes_and_old_device_tests(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            old_mp3 = output_dir / "quick_take_001.mp3"
            old_vocal = output_dir / "quick_take_001_vocal.wav"
            new_mp3 = output_dir / "quick_take_20260403_191431.mp3"
            newest_test = output_dir / "guitar_mix_device_test.wav"
            older_test = output_dir / "quick_take_device_test.wav"
            keep_mix = output_dir / "guitar_mix_20260403_184247.mp3"
            for index, path in enumerate([old_mp3, old_vocal, new_mp3, older_test, newest_test, keep_mix]):
                path.write_text(path.name, encoding="utf-8")
                timestamp = time.time() + index
                os.utime(path, (timestamp, timestamp))

            candidates = app.cleanup_candidate_output_files(output_dir)

        self.assertEqual(candidates, [older_test, old_vocal, old_mp3])

    def test_clean_old_trial_outputs_removes_only_safe_candidates(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            old_mp3 = output_dir / "quick_take_001.mp3"
            old_vocal = output_dir / "quick_take_001_vocal.wav"
            new_mp3 = output_dir / "quick_take_20260403_191431.mp3"
            latest_test = output_dir / "guitar_mix_device_test.wav"
            old_test = output_dir / "legacy_device_test.wav"
            for index, path in enumerate([old_mp3, old_vocal, new_mp3, old_test, latest_test]):
                path.write_text(path.name, encoding="utf-8")
                timestamp = time.time() + index
                os.utime(path, (timestamp, timestamp))
            recorder.last_output_dir = output_dir

            recorder.clean_old_trial_outputs()

            self.assertFalse(old_mp3.exists())
            self.assertFalse(old_vocal.exists())
            self.assertFalse(old_test.exists())
            self.assertTrue(new_mp3.exists())
            self.assertTrue(latest_test.exists())

        self.assertEqual(recorder.status_messages[-1], "Eski denemeler temizlendi: 3 dosya")

    def test_clean_old_trial_outputs_reports_when_nothing_to_clean(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            clean_file = output_dir / "quick_take_20260403_191431.mp3"
            clean_file.write_text("fresh", encoding="utf-8")
            recorder.last_output_dir = output_dir

            recorder.clean_old_trial_outputs()

        self.assertEqual(recorder.status_messages[-1], "Temizlenecek eski deneme yok.")

    def test_current_session_archive_candidates_collects_generated_and_support_files(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            export_path = output_dir / "quick_take_20260403_191431.mp3"
            vocal_path = output_dir / "quick_take_20260403_191431_vocal.wav"
            summary_path = output_dir / "session_summary.json"
            take_notes_path = output_dir / "take_notes.txt"
            for path in (export_path, vocal_path, take_notes_path):
                path.write_text(path.name, encoding="utf-8")
            summary_path.write_text(
                json.dumps(
                    {
                        "generated_files": [str(export_path), str(vocal_path)],
                    }
                ),
                encoding="utf-8",
            )
            recorder.last_output_dir = output_dir
            recorder.last_export_path = export_path
            recorder.last_summary_path = summary_path
            recorder.last_take_notes_path = take_notes_path

            candidates = recorder.current_session_archive_candidates(output_dir)

        self.assertEqual(candidates, [export_path, vocal_path, summary_path, take_notes_path])

    def test_archive_last_session_outputs_moves_current_session_bundle(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            export_path = output_dir / "quick_take_20260403_191431.mp3"
            vocal_path = output_dir / "quick_take_20260403_191431_vocal.wav"
            summary_path = output_dir / "session_summary.json"
            take_notes_path = output_dir / "take_notes.txt"
            older_keep = output_dir / "guitar_mix_20260403_184247.mp3"
            for path in (export_path, vocal_path, take_notes_path, older_keep):
                path.write_text(path.name, encoding="utf-8")
            summary_path.write_text(
                json.dumps(
                    {
                        "generated_files": [str(export_path), str(vocal_path)],
                    }
                ),
                encoding="utf-8",
            )
            recorder.last_output_dir = output_dir
            recorder.last_export_path = export_path
            recorder.last_summary_path = summary_path
            recorder.last_take_notes_path = take_notes_path

            recorder.archive_last_session_outputs()

            archive_dir = output_dir / "_arsiv" / "quick_take_20260403_191431"
            self.assertTrue((archive_dir / export_path.name).exists())
            self.assertTrue((archive_dir / vocal_path.name).exists())
            self.assertTrue((archive_dir / summary_path.name).exists())
            self.assertTrue((archive_dir / take_notes_path.name).exists())
            self.assertTrue(older_keep.exists())
            self.assertEqual(recorder.last_export_path, older_keep)
            self.assertIsNone(recorder.last_summary_path)
            self.assertIsNone(recorder.last_take_notes_path)
            recorder.write_last_session_state.assert_called_once_with(output_dir, None)

        self.assertEqual(
            recorder.status_messages[-1],
            "Son oturum arşivlendi: quick_take_20260403_191431 (4 dosya)",
        )

    def test_refresh_recent_exports_without_audio_skips_highlight_line(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            files = []
            for offset, name in enumerate(["session_summary.json", "take_notes.txt"]):
                path = output_dir / name
                path.write_text(name, encoding="utf-8")
                os.utime(path, (time.time() + offset, time.time() + offset))
                files.append(path)

            recorder.resolve_output_dir = mock.Mock(return_value=output_dir)
            recorder.refresh_recent_exports()
            expected = "\n".join(
                app.recent_output_file_line(path) for path in sorted(files, key=lambda path: path.stat().st_mtime, reverse=True)
            )

        self.assertEqual(recorder.recent_exports_text.get(), expected)

    def test_recent_output_matches_filter_separates_audio_and_documents(self) -> None:
        audio_path = Path("/tmp/take.mp3")
        summary_path = Path("/tmp/session_summary.json")

        self.assertTrue(app.recent_output_matches_filter(audio_path, "Tümü"))
        self.assertTrue(app.recent_output_matches_filter(audio_path, "Sadece Ses"))
        self.assertFalse(app.recent_output_matches_filter(audio_path, "Sadece Belgeler"))
        self.assertTrue(app.recent_output_matches_filter(summary_path, "Sadece Belgeler"))
        self.assertFalse(app.recent_output_matches_filter(summary_path, "Sadece Ses"))

    def test_refresh_recent_exports_filters_to_audio_only(self) -> None:
        recorder = self.make_app()
        recorder.recent_output_filter.set("Sadece Ses")
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            audio_path = output_dir / "take.mp3"
            summary_path = output_dir / "session_summary.json"
            audio_path.write_text("audio", encoding="utf-8")
            summary_path.write_text("{}", encoding="utf-8")
            now = time.time()
            os.utime(audio_path, (now, now))
            os.utime(summary_path, (now + 1, now + 1))
            recorder.resolve_output_dir = mock.Mock(return_value=output_dir)

            recorder.refresh_recent_exports()
            expected = f"{app.recent_audio_highlight_line(audio_path)}\n\n{app.recent_output_file_line(audio_path)}"

        self.assertEqual(recorder.recent_exports_text.get(), expected)

    def test_refresh_recent_exports_reports_empty_result_for_document_filter(self) -> None:
        recorder = self.make_app()
        recorder.recent_output_filter.set("Sadece Belgeler")
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            audio_path = output_dir / "take.mp3"
            audio_path.write_text("audio", encoding="utf-8")
            recorder.resolve_output_dir = mock.Mock(return_value=output_dir)

            recorder.refresh_recent_exports()

        self.assertEqual(recorder.recent_exports_text.get(), "Sadece Belgeler filtresine uygun çıktı yok.")

    def test_build_recent_output_texts_include_filter_detail(self) -> None:
        recorder = self.make_app()
        recorder.recent_output_filter.set("Sadece Ses")
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            export_path = output_dir / "take.mp3"
            summary_path = output_dir / "session_summary.json"
            export_path.write_text("audio", encoding="utf-8")
            summary_path.write_text("{}", encoding="utf-8")
            recorder.last_output_dir = output_dir
            recorder.last_export_path = export_path
            recorder.last_summary_path = summary_path

            summary_text = recorder.build_recent_output_summary_text()
            subtitle_text = recorder.build_recent_output_subtitle_text()

        self.assertIn("Görünüm: Sadece Ses | 1 öğe.", summary_text)
        self.assertIn("Gösterim: Sadece Ses | 1 öğe.", subtitle_text)

    def test_build_recent_output_meta_text_reports_counts_and_last_update(self) -> None:
        recorder = self.make_app()
        recorder.recent_output_filter.set("Sadece Ses")
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            audio_path = output_dir / "take.mp3"
            summary_path = output_dir / "session_summary.json"
            audio_path.write_text("audio", encoding="utf-8")
            summary_path.write_text("{}", encoding="utf-8")
            now = time.time()
            os.utime(audio_path, (now, now))
            os.utime(summary_path, (now + 5, now + 5))
            recorder.last_output_dir = output_dir

            meta_text = recorder.build_recent_output_meta_text()

        self.assertIn(f"Klasör: {output_dir.name}", meta_text)
        self.assertIn("Görünen: 1 / Toplam: 2", meta_text)
        self.assertIn("Son güncelleme:", meta_text)

    def test_session_state_available_detects_cached_state(self) -> None:
        recorder = self.make_app()
        recorder.last_export_path = Path("/tmp/take.mp3")

        self.assertTrue(recorder.session_state_available())

    def test_reset_session_state_clears_cached_paths_and_last_session_file(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            export_path = output_dir / "take.mp3"
            summary_path = output_dir / "session_summary.json"
            export_path.write_text("audio", encoding="utf-8")
            summary_path.write_text("{}", encoding="utf-8")
            recorder.last_output_dir = output_dir
            recorder.last_export_path = export_path
            recorder.last_summary_path = summary_path

            with mock.patch.object(app, "LAST_SESSION_PATH", output_dir / "last_session.json"):
                app.LAST_SESSION_PATH.write_text("{}", encoding="utf-8")
                recorder.reset_session_state()

                self.assertFalse(app.LAST_SESSION_PATH.exists())

        self.assertIsNone(recorder.last_output_dir)
        self.assertIsNone(recorder.last_export_path)
        self.assertIsNone(recorder.last_summary_path)
        recorder.update_compact_status_summary.assert_called_once_with()
        recorder.update_recording_prep_summary.assert_called_once_with()
        recorder.update_next_step_summary.assert_called_once_with()
        recorder.update_readiness_summary.assert_called_once_with()
        recorder.update_preflight_warning_summary.assert_called_once_with()
        recorder.update_action_guidance_summary.assert_called_once_with()
        self.assertEqual(recorder.status_messages[-1], "Oturum durumu sıfırlandı. Yeni kayıt için temiz başlangıç hazır.")

    def test_recent_audio_highlight_line_includes_duration_when_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = Path(tmpdir) / "take.wav"
            audio_path.write_text("audio", encoding="utf-8")
            with mock.patch.object(app.sf, "info", return_value=mock.Mock(duration=125.4), create=True):
                line = app.recent_audio_highlight_line(audio_path)

        self.assertIn("WAV", line)
        self.assertIn("2:05", line)
        self.assertIn(Path(tmpdir).name, line)
        self.assertIn("take.wav", line)

    def test_build_device_summary_limits_list_and_reports_counts(self) -> None:
        recorder = self.make_app()
        inputs = [(index, f"Input {index}") for index in range(6)]
        outputs = [(index, f"Output {index}") for index in range(3)]

        with mock.patch.object(app, "list_input_devices", return_value=inputs), mock.patch.object(
            app, "list_output_devices", return_value=outputs
        ):
            summary = recorder.build_device_summary()

        self.assertIn("Giriş Aygıtları (6):", summary)
        self.assertIn("Çıkış Aygıtları (3):", summary)
        self.assertIn("• 0: Input 0", summary)
        self.assertIn("• 4: Input 4", summary)
        self.assertNotIn("Input 5", summary)

    def test_inspect_devices_without_inputs_sets_help_status(self) -> None:
        recorder = self.make_app()

        with mock.patch.object(app, "list_input_devices", return_value=[]), mock.patch.object(
            app, "list_output_devices", return_value=[(2, "Built-in Output")]
        ), mock.patch.object(app, "no_device_help_text", return_value="No devices help"), mock.patch.object(
            app.GuitarAmpRecorderApp, "build_device_summary", return_value="summary"
        ):
            recorder.inspect_devices()

        recorder.refresh_device_menus.assert_called_once_with([], [(2, "Built-in Output")])
        recorder.restart_input_meter.assert_not_called()
        self.assertEqual(recorder.device_summary_text.get(), "summary")
        self.assertIn("Mikrofon içinde izin verin", recorder.setup_hint_text.get())
        self.assertEqual(recorder.status_messages[-1], "No devices help")

    def test_build_setup_hint_text_warns_when_ffmpeg_missing_for_mp3(self) -> None:
        recorder = self.make_app()
        recorder.output_dir = FakeVar("/tmp/out")

        with mock.patch.object(app.shutil, "which", return_value=None):
            hint = recorder.build_setup_hint_text(1, 1)

        self.assertIn("MP3 için ffmpeg bulunamadı", hint)

    def test_build_setup_hint_text_requests_output_dir_before_recording(self) -> None:
        recorder = self.make_app()
        recorder.output_dir = FakeVar("")

        with mock.patch.object(app.shutil, "which", return_value="/opt/homebrew/bin/ffmpeg"):
            hint = recorder.build_setup_hint_text(1, 1)

        self.assertEqual(hint, "Kurulum tamamlanmak üzere. Son adım olarak kayıt klasörünü seçin.")

    def test_build_setup_status_text_reports_ready_state(self) -> None:
        recorder = self.make_app()
        recorder.output_dir = FakeVar("/tmp/out")

        with mock.patch.object(app.shutil, "which", return_value="/opt/homebrew/bin/ffmpeg"):
            status = recorder.build_setup_status_text(1, 1)

        self.assertEqual(status, "Kurulum: Giriş hazır | Çıkış hazır | ffmpeg hazır | Klasör hazır")

    def test_build_setup_status_text_reports_missing_ffmpeg(self) -> None:
        recorder = self.make_app()
        recorder.output_dir = FakeVar("/tmp/out")

        with mock.patch.object(app.shutil, "which", return_value=None):
            status = recorder.build_setup_status_text(1, 1)

        self.assertEqual(status, "Kurulum: Giriş hazır | Çıkış hazır | ffmpeg eksik | Klasör hazır")

    def test_build_setup_next_text_requests_mic_rescan_when_input_missing(self) -> None:
        recorder = self.make_app()
        recorder.output_dir = FakeVar("/tmp/out")

        with mock.patch.object(app.shutil, "which", return_value="/opt/homebrew/bin/ffmpeg"):
            next_step = recorder.build_setup_next_text(0, 1)

        self.assertEqual(next_step, "Sıradaki adım: mikrofon iznini açıp yeniden tara.")

    def test_build_setup_next_text_offers_wav_fallback_when_ffmpeg_missing(self) -> None:
        recorder = self.make_app()
        recorder.output_dir = FakeVar("/tmp/out")

        with mock.patch.object(app.shutil, "which", return_value=None):
            next_step = recorder.build_setup_next_text(1, 1)

        self.assertEqual(next_step, "Sıradaki adım: ffmpeg kur veya WAV ile devam et.")

    def test_build_setup_next_text_requests_output_dir_before_test(self) -> None:
        recorder = self.make_app()
        recorder.output_dir = FakeVar("")

        with mock.patch.object(app.shutil, "which", return_value="/opt/homebrew/bin/ffmpeg"):
            next_step = recorder.build_setup_next_text(1, 1)

        self.assertEqual(next_step, "Sıradaki adım: kayıt klasörü seç.")

    def test_build_setup_next_text_recommends_test_when_ready(self) -> None:
        recorder = self.make_app()
        recorder.output_dir = FakeVar("/tmp/out")
        recorder.input_device_id = FakeVar("")
        recorder.output_device_id = FakeVar("")

        with mock.patch.object(app.shutil, "which", return_value="/opt/homebrew/bin/ffmpeg"):
            next_step = recorder.build_setup_next_text(1, 1)

        self.assertEqual(next_step, "Sıradaki adım: 5 saniyelik test yap.")

    def test_build_mp3_quality_label_text_reports_missing_ffmpeg(self) -> None:
        recorder = self.make_app()

        with mock.patch.object(app.shutil, "which", return_value=None):
            label = recorder.build_mp3_quality_label_text()

        self.assertEqual(label, "MP3 Kalitesi (ffmpeg eksik)")

    def test_update_mp3_quality_controls_disables_menu_when_mp3_unavailable(self) -> None:
        recorder = self.make_app()

        with mock.patch.object(app.shutil, "which", return_value=None):
            recorder.update_mp3_quality_controls()

        self.assertEqual(recorder.mp3_quality_label_text.get(), "MP3 Kalitesi (ffmpeg eksik)")
        recorder.mp3_quality_menu.configure.assert_called_once_with(state="disabled")

    def test_refresh_device_menus_resets_unknown_choices_and_updates_route(self) -> None:
        recorder = self.make_app()
        recorder.input_device_choice.set("999 - Missing Input")
        recorder.output_device_choice.set("999 - Missing Output")

        app.GuitarAmpRecorderApp.refresh_device_menus(recorder, [(1, "USB Mic")], [(2, "USB Output")])

        self.assertEqual(recorder.input_device_options, ["Varsayılan macOS girişi", "1 - USB Mic"])
        self.assertEqual(recorder.output_device_options, ["Varsayılan macOS çıkışı", "2 - USB Output"])
        self.assertEqual(recorder.input_device_choice.get(), "Varsayılan macOS girişi")
        self.assertEqual(recorder.output_device_choice.get(), "Varsayılan macOS çıkışı")
        self.assertIn("Aktif giriş: Varsayılan macOS girişi", recorder.selected_route_text.get())
        self.assertEqual(recorder.input_device_menu.menu.deleted, [(0, "end")])
        self.assertEqual(recorder.output_device_menu.menu.deleted, [(0, "end")])
        self.assertEqual(
            [label for label, _command in recorder.input_device_menu.menu.commands],
            ["Varsayılan macOS girişi", "1 - USB Mic"],
        )

    def test_choice_change_helpers_sync_ids(self) -> None:
        recorder = self.make_app()
        recorder.input_device_choice.set("4 - USB Mic")
        recorder.output_device_choice.set("Varsayılan macOS çıkışı")

        app.GuitarAmpRecorderApp.on_input_choice_changed(recorder)
        app.GuitarAmpRecorderApp.on_output_choice_changed(recorder)

        self.assertEqual(recorder.input_device_id.get(), "4")
        self.assertEqual(recorder.output_device_id.get(), "")
        self.assertIn("Aktif çıkış: Varsayılan macOS çıkışı", recorder.selected_route_text.get())

    def test_open_last_export_in_finder_handles_missing_export(self) -> None:
        recorder = self.make_app()
        recorder.last_export_path = None

        recorder.open_last_export_in_finder()

        self.assertEqual(recorder.status_messages[-1], "Son kayıt yok.")

    def test_open_last_session_summary_in_finder_handles_missing_summary(self) -> None:
        recorder = self.make_app()
        recorder.last_summary_path = None

        recorder.open_last_session_summary_in_finder()

        self.assertEqual(recorder.status_messages[-1], "Özet yok.")

    def test_open_last_take_notes_in_finder_handles_missing_file(self) -> None:
        recorder = self.make_app()
        recorder.last_take_notes_path = None

        recorder.open_last_take_notes_in_finder()

        self.assertEqual(recorder.status_messages[-1], "Take notu yok.")

    def test_clear_backing_selection_returns_to_microphone_mode(self) -> None:
        recorder = self.make_app()
        recorder.backing_file = Path("/tmp/backing.wav")

        recorder.clear_backing_selection()

        self.assertIsNone(recorder.backing_file)
        recorder.backing_label.config.assert_called_once_with(text="Dosya seçilmedi", fg="#9aa7b5")
        self.assertEqual(recorder.status_messages[-1], "Arka plan müziği temizlendi. Sadece mikrofon moduna geçildi.")

    def test_clear_backing_selection_is_blocked_during_active_recording(self) -> None:
        recorder = self.make_app()
        recorder.recording_active = True
        recorder.backing_file = Path("/tmp/backing.wav")

        recorder.clear_backing_selection()

        self.assertEqual(recorder.backing_file, Path("/tmp/backing.wav"))
        recorder.backing_label.config.assert_not_called()
        self.assertEqual(recorder.status_messages[-1], "Kayıt sürerken kayıt kaynağı değiştirilemez. Önce kaydı durdurun.")

    def test_select_output_dir_is_blocked_during_active_recording(self) -> None:
        recorder = self.make_app()
        recorder.recording_active = True

        recorder.select_output_dir()
        self.assertEqual(recorder.status_messages[-1], "Kayıt sürerken çıkış klasörü değiştirilemez. Önce kaydı durdurun.")

    def test_copy_last_session_summary_to_clipboard_reads_and_copies_content(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            summary_path = Path(tmpdir) / "session_summary.json"
            summary_path.write_text('{"event":"record_export"}', encoding="utf-8")
            recorder.last_summary_path = summary_path

            recorder.copy_last_session_summary_to_clipboard()

        recorder.root.clipboard_clear.assert_called_once_with()
        recorder.root.clipboard_append.assert_called_once_with('{"event":"record_export"}')
        recorder.root.update.assert_called_once_with()
        self.assertEqual(recorder.status_messages[-1], "Özet panoya alındı: session_summary.json")

    def test_copy_recent_outputs_to_clipboard_copies_visible_list(self) -> None:
        recorder = self.make_app()
        recorder.recent_exports_text.set("Son kayıt\n- take.mp3")

        recorder.copy_recent_outputs_to_clipboard()

        recorder.root.clipboard_clear.assert_called_once_with()
        recorder.root.clipboard_append.assert_called_once_with("Son kayıt\n- take.mp3")
        recorder.root.update.assert_called_once_with()
        self.assertEqual(recorder.status_messages[-1], "Son çıktı listesi panoya alındı")

    def test_copy_recent_outputs_to_clipboard_reports_empty_content(self) -> None:
        recorder = self.make_app()
        recorder.recent_exports_text.set("   ")

        recorder.copy_recent_outputs_to_clipboard()

        recorder.root.clipboard_clear.assert_not_called()
        self.assertEqual(recorder.status_messages[-1], "Kopyalanacak çıktı listesi yok.")

    def test_copy_last_export_path_to_clipboard_copies_file_path(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "take.mp3"
            export_path.write_text("audio", encoding="utf-8")
            recorder.last_export_path = export_path

            recorder.copy_last_export_path_to_clipboard()

        recorder.root.clipboard_clear.assert_called_once_with()
        recorder.root.clipboard_append.assert_called_once_with(str(export_path))
        recorder.root.update.assert_called_once_with()
        self.assertEqual(recorder.status_messages[-1], "Dosya yolu panoya alındı: take.mp3")

    def test_copy_last_session_summary_path_to_clipboard_copies_file_path(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            summary_path = Path(tmpdir) / "session_summary.json"
            summary_path.write_text("{}", encoding="utf-8")
            recorder.last_summary_path = summary_path

            recorder.copy_last_session_summary_path_to_clipboard()

        recorder.root.clipboard_clear.assert_called_once_with()
        recorder.root.clipboard_append.assert_called_once_with(str(summary_path))
        recorder.root.update.assert_called_once_with()
        self.assertEqual(recorder.status_messages[-1], "Özet yolu panoya alındı: session_summary.json")

    def test_copy_last_session_brief_to_clipboard_formats_human_readable_report(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            summary_path = Path(tmpdir) / "session_summary.json"
            summary_path.write_text(
                '{"event":"record_export","timestamp":"2026-03-25 21:00:00","output_dir":"/tmp/session","preset_name":"Temiz Gitar","preset_note":"Canli deneme","generated_files":["/tmp/session/take.mp3"],"recording":{"mode":"Sadece mikrofon","duration_seconds":42.0,"requested_duration_seconds":60.0,"input_peak":0.612,"processed_peak":0.701,"mix_peak":0.822,"stopped_early":true}}',
                encoding="utf-8",
            )
            recorder.last_summary_path = summary_path

            recorder.copy_last_session_brief_to_clipboard()

        recorder.root.clipboard_clear.assert_called_once_with()
        copied_text = recorder.root.clipboard_append.call_args[0][0]
        self.assertIn("Olay: record_export", copied_text)
        self.assertIn("Preset: Temiz Gitar", copied_text)
        self.assertIn("Preset Notu: Canli deneme", copied_text)
        self.assertIn("Sure: 0:42", copied_text)
        self.assertIn("Hedef Sure: 1:00", copied_text)
        self.assertIn("Giris Peak: 0.612", copied_text)
        self.assertIn("Clip Durumu: Clip riski yok", copied_text)
        self.assertIn("Durum: erken durduruldu", copied_text)
        self.assertIn("- take.mp3", copied_text)
        recorder.root.update.assert_called_once_with()
        self.assertEqual(recorder.status_messages[-1], "Kısa rapor panoya alındı: session_summary.json")

    def test_export_last_session_brief_file_writes_text_file(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            summary_path = Path(tmpdir) / "session_summary.json"
            summary_path.write_text(
                '{"event":"record_export","timestamp":"2026-03-25 21:00:00","output_dir":"/tmp/session","preset_name":"Temiz Gitar","preset_note":"Canli deneme","generated_files":["/tmp/session/take.mp3"],"recording":{"mode":"Sadece mikrofon","duration_seconds":42.0,"requested_duration_seconds":60.0,"input_peak":0.612,"processed_peak":0.701,"mix_peak":0.822,"stopped_early":false}}',
                encoding="utf-8",
            )
            recorder.last_summary_path = summary_path

            recorder.export_last_session_brief_file()

            brief_path = Path(tmpdir) / "session_brief.txt"
            self.assertTrue(brief_path.exists())
            self.assertIn("Preset: Temiz Gitar", brief_path.read_text(encoding="utf-8"))
            self.assertIn("Preset Notu: Canli deneme", brief_path.read_text(encoding="utf-8"))

        self.assertIn("Kısa rapor yazıldı:", recorder.status_messages[-1])

    def test_copy_last_recovery_note_to_clipboard_reads_and_copies_content(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            recovery_path = Path(tmpdir) / "export_recovery_note.txt"
            recovery_path.write_text("Kurtarma Notu", encoding="utf-8")
            recorder.last_recovery_note_path = recovery_path

            recorder.copy_last_recovery_note_to_clipboard()

        recorder.root.clipboard_clear.assert_called_once_with()
        recorder.root.clipboard_append.assert_called_once_with("Kurtarma Notu")
        recorder.root.update.assert_called_once_with()
        self.assertEqual(recorder.status_messages[-1], "Kurtarma notu panoya alındı: export_recovery_note.txt")

    def test_copy_current_preparation_to_clipboard_copies_live_preparation_summary(self) -> None:
        recorder = self.make_app()
        recorder.build_current_preparation_brief_text = mock.Mock(return_value="Hazırlık Özeti\nKayıt Planı")

        recorder.copy_current_preparation_to_clipboard()

        recorder.build_current_preparation_brief_text.assert_called_once_with()
        recorder.root.clipboard_clear.assert_called_once_with()
        recorder.root.clipboard_append.assert_called_once_with("Hazırlık Özeti\nKayıt Planı")
        recorder.root.update.assert_called_once_with()
        self.assertEqual(recorder.status_messages[-1], "Hazırlık özeti panoya alındı")

    def test_export_current_preparation_file_writes_text_file(self) -> None:
        recorder = self.make_app()
        recorder.output_dir = FakeVar("/tmp/out")
        recorder.build_current_preparation_brief_text = mock.Mock(return_value="Hazırlık Özeti\nKayıt Planı")
        with tempfile.TemporaryDirectory() as tmpdir:
            target_dir = Path(tmpdir) / "Akşam Kaydı"
            recorder.resolve_output_dir = mock.Mock(return_value=target_dir)

            recorder.export_current_preparation_file()

            prep_path = target_dir / "preparation_summary.txt"
            self.assertTrue(prep_path.exists())
            self.assertEqual(prep_path.read_text(encoding="utf-8"), "Hazırlık Özeti\nKayıt Planı")
            self.assertEqual(recorder.last_output_dir, target_dir)
            self.assertEqual(recorder.last_preparation_summary_path, prep_path)
            recorder.resolve_output_dir.assert_called_once_with()
            recorder.build_current_preparation_brief_text.assert_called_once_with()
            recorder.write_last_session_state.assert_called_once_with(target_dir, recorder.last_summary_path)
            recorder.update_recent_output_summary.assert_called_once_with()
            recorder.open_last_output_dir_button.configure.assert_called_once_with(state="normal")
            recorder.open_last_preparation_button.configure.assert_called_once_with(state="normal")
            self.assertEqual(recorder.status_messages[-1], f"Hazırlık özeti yazıldı: {prep_path}")

    def test_export_current_preparation_file_requires_output_dir(self) -> None:
        recorder = self.make_app()
        recorder.output_dir = FakeVar("")

        recorder.export_current_preparation_file()

        self.assertEqual(recorder.status_messages[-1], "Hazırlık özeti için önce kayıt klasörünü seçin.")

    def test_reset_preparation_state_clears_last_preparation_reference(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            prep_path = output_dir / "preparation_summary.txt"
            prep_path.write_text("Hazırlık Özeti", encoding="utf-8")
            recorder.last_output_dir = output_dir
            recorder.last_preparation_summary_path = prep_path
            summary_path = output_dir / "session_summary.json"
            summary_path.write_text("{}", encoding="utf-8")
            recorder.last_summary_path = summary_path

            recorder.reset_preparation_state()

        self.assertIsNone(recorder.last_preparation_summary_path)
        recorder.write_last_session_state.assert_called_once_with(output_dir, summary_path)
        recorder.update_recording_prep_summary.assert_called_once_with()
        recorder.update_recording_prep_subtitle.assert_called_once_with()
        recorder.update_recent_output_summary.assert_called_once_with()
        recorder.open_preparation_button.configure.assert_called_once_with(state="disabled")
        recorder.open_last_preparation_button.configure.assert_called_once_with(state="disabled")
        self.assertEqual(recorder.status_messages[-1], "Hazırlık durumu sıfırlandı. Yeni plan için özet temizlendi.")

    def test_build_recording_prep_meta_text_reports_pending_target_before_file_exists(self) -> None:
        recorder = self.make_app()
        recorder.output_dir = FakeVar("/tmp/out")
        recorder.resolve_output_dir = mock.Mock(return_value=Path("/tmp/out/Session"))

        text = recorder.build_recording_prep_meta_text()

        self.assertEqual(text, "Hazırlık dosyası: henüz yazılmadı | Hedef: preparation_summary.txt")

    def test_update_recording_prep_summary_sets_meta_text_for_existing_preparation_file(self) -> None:
        recorder = self.make_app()
        recorder.update_recording_prep_summary = app.GuitarAmpRecorderApp.update_recording_prep_summary.__get__(recorder, app.GuitarAmpRecorderApp)
        recorder.update_recording_prep_subtitle = app.GuitarAmpRecorderApp.update_recording_prep_subtitle.__get__(recorder, app.GuitarAmpRecorderApp)
        recorder.build_recording_prep_text = mock.Mock(return_value="Hazırlık Planı")
        recorder.output_dir = FakeVar("/tmp/out")
        with tempfile.TemporaryDirectory() as tmpdir:
            prep_path = Path(tmpdir) / "preparation_summary.txt"
            prep_path.write_text("Hazırlık Özeti", encoding="utf-8")
            recorder.last_preparation_summary_path = prep_path

            recorder.update_recording_prep_summary()

        self.assertEqual(recorder.prep_summary_text.get(), "Hazırlık Planı")
        self.assertEqual(recorder.prep_status_text.get(), "Hazırlık durumu: dosya hazır")
        self.assertIn("Hazırlık dosyası: preparation_summary.txt", recorder.prep_meta_text.get())
        self.assertIn("Son güncelleme:", recorder.prep_meta_text.get())
        recorder.prep_status_label.configure.assert_called_once_with(bg="#1f3527", fg="#d8f3dc")

    def test_build_hero_preparation_card_text_reports_ready_file(self) -> None:
        recorder = self.make_app()
        recorder.output_dir = FakeVar("/tmp/out")
        with tempfile.TemporaryDirectory() as tmpdir:
            prep_path = Path(tmpdir) / "preparation_summary.txt"
            prep_path.write_text("Hazırlık Özeti", encoding="utf-8")
            recorder.last_preparation_summary_path = prep_path

            text = recorder.build_hero_preparation_card_text()

        self.assertEqual(text, "Hazırlık dosyası hazır\npreparation_summary.txt")

    def test_build_hero_summary_text_includes_preparation_summary(self) -> None:
        recorder = self.make_app()
        recorder.build_hero_status_card_text = mock.Mock(return_value="Canlı\nDurum")
        recorder.build_hero_setup_card_text = mock.Mock(return_value="Kurulum\nHazır")
        recorder.build_hero_preparation_card_text = mock.Mock(return_value="Hazırlık\nHazır")
        recorder.build_hero_output_card_text = mock.Mock(return_value="Çıktı\nHazır")

        text = recorder.build_hero_summary_text()

        self.assertEqual(
            text,
            "Canlı Durum: Canlı | Durum    •    Kurulum: Kurulum | Hazır    •    Hazırlık: Hazırlık | Hazır    •    Son Çıktı: Çıktı | Hazır",
        )

    def test_copy_preparation_summary_path_to_clipboard_copies_existing_path(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            prep_path = Path(tmpdir) / "preparation_summary.txt"
            prep_path.write_text("Hazırlık Özeti", encoding="utf-8")
            recorder.last_preparation_summary_path = prep_path

            recorder.copy_preparation_summary_path_to_clipboard()

        recorder.root.clipboard_clear.assert_called_once_with()
        recorder.root.clipboard_append.assert_called_once_with(str(prep_path))
        recorder.root.update.assert_called_once_with()
        self.assertEqual(recorder.status_messages[-1], "Hazırlık yolu panoya alındı: preparation_summary.txt")

    def test_copy_preparation_summary_path_to_clipboard_reports_missing_file(self) -> None:
        recorder = self.make_app()
        recorder.resolve_output_dir = mock.Mock(return_value=Path("/tmp/out/Session"))

        recorder.copy_preparation_summary_path_to_clipboard()

        self.assertEqual(recorder.status_messages[-1], "Hazırlık dosyası yok.")

    def test_open_preparation_summary_in_finder_handles_missing_file(self) -> None:
        recorder = self.make_app()
        recorder.resolve_output_dir = mock.Mock(return_value=Path("/tmp/out/Session"))

        recorder.open_preparation_summary_in_finder()

        self.assertEqual(recorder.status_messages[-1], "Hazırlık dosyası yok.")

    def test_open_preparation_summary_in_finder_selects_file_and_updates_status(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            prep_path = Path(tmpdir) / "preparation_summary.txt"
            prep_path.write_text("Hazırlık Özeti", encoding="utf-8")
            recorder.last_preparation_summary_path = prep_path

            with mock.patch.object(app.subprocess, "run") as run_mock:
                recorder.open_preparation_summary_in_finder()

        run_mock.assert_called_once_with(["open", "-R", str(prep_path)], check=False)
        self.assertEqual(recorder.status_messages[-1], "Hazırlık dosyası Finder'da seçildi: preparation_summary.txt")

    def test_play_last_export_audio_reads_file_and_plays_it(self) -> None:
        recorder = self.make_app()
        recorder.output_device_choice.set("7 - USB Output")
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "take.wav"
            export_path.write_text("audio", encoding="utf-8")
            recorder.last_export_path = export_path

            with mock.patch.object(app.sf, "read", return_value=([0.1, 0.2], 44100), create=True) as read_mock, mock.patch.object(
                app.sd, "play", create=True
            ) as play_mock, mock.patch.object(app.sd, "wait", create=True) as wait_mock:
                recorder.play_last_export_audio()

        read_mock.assert_called_once_with(export_path, dtype="float32")
        play_mock.assert_called_once_with([0.1, 0.2], samplerate=44100, device=7)
        wait_mock.assert_called_once_with()
        self.assertEqual(recorder.status_messages[-1], f"Son kayıt oynatıldı: {app.recent_audio_status_text(export_path)}")

    def test_current_filtered_recent_audio_file_returns_first_visible_audio(self) -> None:
        recorder = self.make_app()
        recorder.recent_output_filter = FakeVar("Sadece Ses")
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            newer_audio = output_dir / "take_new.mp3"
            newer_audio.write_text("audio", encoding="utf-8")
            older_doc = output_dir / "session_summary.json"
            older_doc.write_text("{}", encoding="utf-8")
            os.utime(older_doc, (time.time() - 10, time.time() - 10))
            recorder.last_output_dir = output_dir

            result = recorder.current_filtered_recent_audio_file()

        self.assertEqual(result, newer_audio)

    def test_start_visible_recent_audio_playback_thread_reports_missing_audio(self) -> None:
        recorder = self.make_app()
        recorder.current_filtered_recent_audio_file = mock.Mock(return_value=None)

        recorder.start_visible_recent_audio_playback_thread()

        self.assertEqual(recorder.status_messages[-1], "Görünen filtrede oynatılacak ses yok.")

    def test_start_visible_recent_audio_playback_thread_starts_worker_for_filtered_audio(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = Path(tmpdir) / "take.wav"
            audio_path.write_text("audio", encoding="utf-8")
            recorder.current_filtered_recent_audio_file = mock.Mock(return_value=audio_path)

            started_targets: list[tuple] = []

            class FakeThread:
                def __init__(self, target=None, args=(), daemon=None):
                    started_targets.append((target, args, daemon))

                def start(self):
                    return None

            with mock.patch.object(app.threading, "Thread", FakeThread):
                recorder.start_visible_recent_audio_playback_thread()

        self.assertEqual(len(started_targets), 1)
        target, args, daemon = started_targets[0]
        self.assertEqual(target, recorder.play_audio_file)
        self.assertEqual(args, (audio_path, "Görünen ses"))
        self.assertTrue(daemon)

    def test_current_filtered_recent_output_file_returns_first_visible_file(self) -> None:
        recorder = self.make_app()
        recorder.recent_output_filter = FakeVar("Tümü")
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            newest = output_dir / "take_new.mp3"
            newest.write_text("audio", encoding="utf-8")
            older = output_dir / "session_summary.json"
            older.write_text("{}", encoding="utf-8")
            os.utime(older, (time.time() - 10, time.time() - 10))
            recorder.last_output_dir = output_dir

            result = recorder.current_filtered_recent_output_file()

        self.assertEqual(result, newest)

    def test_open_visible_recent_output_in_finder_reports_missing_output(self) -> None:
        recorder = self.make_app()
        recorder.current_filtered_recent_output_file = mock.Mock(return_value=None)

        recorder.open_visible_recent_output_in_finder()

        self.assertEqual(recorder.status_messages[-1], "Görünen filtrede gösterilecek çıktı yok.")

    def test_open_visible_recent_output_in_finder_selects_filtered_output(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "take_new.mp3"
            output_path.write_text("audio", encoding="utf-8")
            recorder.current_filtered_recent_output_file = mock.Mock(return_value=output_path)

            with mock.patch.object(app.subprocess, "run") as run_mock:
                recorder.open_visible_recent_output_in_finder()

        run_mock.assert_called_once_with(["open", "-R", str(output_path)], check=False)
        self.assertEqual(recorder.status_messages[-1], "Görünen çıktı Finder'da seçildi: take_new.mp3")

    def test_copy_visible_recent_output_path_to_clipboard_reports_missing_output(self) -> None:
        recorder = self.make_app()
        recorder.current_filtered_recent_output_file = mock.Mock(return_value=None)

        recorder.copy_visible_recent_output_path_to_clipboard()

        self.assertEqual(recorder.status_messages[-1], "Görünen filtrede kopyalanacak çıktı yok.")

    def test_copy_visible_recent_output_path_to_clipboard_copies_filtered_output_path(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "take_new.mp3"
            output_path.write_text("audio", encoding="utf-8")
            recorder.current_filtered_recent_output_file = mock.Mock(return_value=output_path)

            recorder.copy_visible_recent_output_path_to_clipboard()

        recorder.root.clipboard_clear.assert_called_once_with()
        recorder.root.clipboard_append.assert_called_once_with(str(output_path))
        recorder.root.update.assert_called_once_with()
        self.assertEqual(recorder.status_messages[-1], "Görünen çıktı yolu panoya alındı: take_new.mp3")

    def test_open_last_export_in_finder_selects_file_and_updates_status(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "take.wav"
            export_path.write_text("audio", encoding="utf-8")
            recorder.last_export_path = export_path

            with mock.patch.object(app.subprocess, "run") as run_mock:
                recorder.open_last_export_in_finder()

        run_mock.assert_called_once_with(["open", "-R", str(export_path)], check=False)
        self.assertEqual(recorder.status_messages[-1], f"Son kayıt Finder'da seçildi: {app.recent_audio_status_text(export_path)}")

    def test_open_last_take_notes_in_finder_selects_file_and_updates_status(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            note_path = Path(tmpdir) / "take_notes.txt"
            note_path.write_text("note", encoding="utf-8")
            recorder.last_take_notes_path = note_path

            with mock.patch.object(app.subprocess, "run") as run_mock:
                recorder.open_last_take_notes_in_finder()

        run_mock.assert_called_once_with(["open", "-R", str(note_path)], check=False)
        self.assertEqual(recorder.status_messages[-1], "Take notu Finder'da seçildi: take_notes.txt")

    def test_open_last_session_summary_in_finder_selects_file_and_updates_status(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            summary_path = Path(tmpdir) / "session_summary.json"
            summary_path.write_text("{}", encoding="utf-8")
            recorder.last_summary_path = summary_path

            with mock.patch.object(app.subprocess, "run") as run_mock:
                recorder.open_last_session_summary_in_finder()

        run_mock.assert_called_once_with(["open", "-R", str(summary_path)], check=False)
        self.assertEqual(recorder.status_messages[-1], "Özet Finder'da seçildi: session_summary.json")

    def test_open_output_dir_in_finder_uses_last_output_dir(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            recorder.last_output_dir = output_dir
            recorder.resolve_output_dir = mock.Mock(return_value=Path("/tmp/unused-output"))

            with mock.patch.object(app.subprocess, "run") as run_mock:
                recorder.open_output_dir_in_finder()

        run_mock.assert_called_once_with(["open", str(output_dir)], check=False)
        recorder.resolve_output_dir.assert_not_called()
        self.assertEqual(recorder.status_messages[-1], f"Klasör açıldı: {output_dir.name}")

    def test_export_share_package_writes_audio_image_and_metadata_files(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "out"
            output_dir.mkdir(parents=True, exist_ok=True)
            audio_path = output_dir / "take_001.mp3"
            image_path = output_dir / "cover.jpg"
            audio_path.write_text("audio", encoding="utf-8")
            image_path.write_text("image", encoding="utf-8")
            recorder.last_export_path = audio_path
            recorder.output_dir.set(str(output_dir))
            recorder.resolve_output_dir = mock.Mock(return_value=output_dir)
            recorder.preset_name.set("Temiz Gitar")
            recorder.preset_note.set("YouTube deneme")
            recorder.share_title.set("Benim Basligim")
            recorder.share_description.set("Kisa aciklama")
            recorder.share_image_path.set(str(image_path))

            recorder.embed_cover_art_in_mp3 = mock.Mock(return_value=(True, "Kapak görseli mp3 içine eklendi."))
            recorder.export_share_package()

            package_dir = output_dir / "_paylasim" / "take_001_youtube_paketi"
            self.assertTrue((package_dir / "take_001.mp3").exists())
            self.assertTrue((package_dir / "kapak.jpg").exists())
            self.assertEqual((package_dir / "youtube_baslik.txt").read_text(encoding="utf-8"), "Benim Basligim")
            self.assertEqual((package_dir / "youtube_aciklama.txt").read_text(encoding="utf-8"), "Kisa aciklama")
            self.assertIn("# YouTube Paylaşım Paketi", (package_dir / "paylasim_paketi.md").read_text(encoding="utf-8"))
            self.assertIn("MP3 Kapak: Kapak görseli mp3 içine eklendi.", (package_dir / "paylasim_paketi.md").read_text(encoding="utf-8"))
            recorder.embed_cover_art_in_mp3.assert_called_once_with(package_dir / "take_001.mp3", package_dir / "kapak.jpg")
            self.assertEqual(recorder.last_share_package_dir, package_dir)

        self.assertEqual(recorder.status_messages[-1], f"YouTube paylaşım paketi hazır: {package_dir}")

    def test_export_share_package_reports_missing_image(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "out"
            output_dir.mkdir(parents=True, exist_ok=True)
            audio_path = output_dir / "take_001.mp3"
            audio_path.write_text("audio", encoding="utf-8")
            recorder.last_export_path = audio_path
            recorder.output_dir.set(str(output_dir))
            recorder.resolve_output_dir = mock.Mock(return_value=output_dir)
            recorder.share_image_path.set("")

            recorder.export_share_package()

        self.assertEqual(recorder.status_messages[-1], "Paylaşım için kapak görseli seçin.")

    def test_open_youtube_upload_page_opens_browser_and_updates_status(self) -> None:
        recorder = self.make_app()

        with mock.patch.object(app.webbrowser, "open") as open_mock:
            recorder.open_youtube_upload_page()

        open_mock.assert_called_once_with("https://www.youtube.com/upload")
        self.assertEqual(recorder.status_messages[-1], "YouTube yükleme sayfası açıldı.")

    def test_apply_share_template_sets_live_title_and_description(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = Path(tmpdir) / "canli_take.mp3"
            audio_path.write_text("audio", encoding="utf-8")
            recorder.last_export_path = audio_path
            recorder.preset_name.set("Temiz Gitar")
            recorder.preset_note.set("Gece için hazır")

            recorder.apply_share_template("Canlı")

            self.assertEqual(recorder.share_title.get(), "canli take | Canlı Kayıt")
            self.assertEqual(
                recorder.share_description.get(),
                "Canlı kayıt paylaşımı | Kayıt: canli take | Preset: Temiz Gitar | Not: Gece için hazır",
            )
            self.assertEqual(recorder.status_messages[-1], "Paylaşım şablonu uygulandı: Canlı")

    def test_share_template_values_falls_back_without_audio_path(self) -> None:
        recorder = self.make_app()
        recorder.preset_name.set("Temiz Gitar")
        recorder.preset_note.set("")

        title, description = recorder.share_template_values("Tanıtım", None)

        self.assertEqual(title, "Yeni kayıt | Yeni Paylaşım")
        self.assertEqual(description, "Yeni kayıt paylaşımı | Kayıt: Yeni kayıt | Preset: Temiz Gitar")

    def test_append_share_hashtags_adds_expected_tags(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = Path(tmpdir) / "temiz_gitar_take.mp3"
            audio_path.write_text("audio", encoding="utf-8")
            recorder.last_export_path = audio_path
            recorder.preset_name.set("Temiz Gitar")
            recorder.preset_note.set("Canlı deneme")
            recorder.share_description.set("Kisa aciklama")

            recorder.append_share_hashtags()

            self.assertIn("Kisa aciklama", recorder.share_description.get())
            self.assertIn("#YouTube #Muzik #Kayit #Gitar #TemizGitar #CanliKayit", recorder.share_description.get())
            self.assertEqual(recorder.status_messages[-1], "Paylaşım hashtagleri eklendi.")

    def test_clear_share_text_resets_title_and_description(self) -> None:
        recorder = self.make_app()
        recorder.share_title.set("Baslik")
        recorder.share_description.set("Aciklama")

        recorder.clear_share_text()

        self.assertEqual(recorder.share_title.get(), "")
        self.assertEqual(recorder.share_description.get(), "")
        self.assertEqual(recorder.status_messages[-1], "Paylaşım başlık ve açıklaması temizlendi.")

    def test_append_share_footer_adds_ready_closing_text(self) -> None:
        recorder = self.make_app()
        recorder.preset_name.set("Temiz Gitar")
        recorder.preset_note.set("Gece için hazır")
        recorder.share_description.set("Kisa aciklama")

        recorder.append_share_footer()

        self.assertIn("Kisa aciklama", recorder.share_description.get())
        self.assertIn("Dinlediğiniz için teşekkürler.", recorder.share_description.get())
        self.assertIn("Kullanılan preset: Temiz Gitar", recorder.share_description.get())
        self.assertIn("Preset notu: Gece için hazır", recorder.share_description.get())
        self.assertEqual(recorder.status_messages[-1], "Paylaşım sonu eklendi.")

    def test_normalize_share_title_collapses_spaces_and_limits_length(self) -> None:
        recorder = self.make_app()
        recorder.share_title.set("  Yeni   Kayıt  |  Çok   Uzun   Başlık  " + ("x" * 120))

        recorder.normalize_share_title()

        self.assertTrue(recorder.share_title.get().startswith("Yeni Kayıt | Çok Uzun Başlık"))
        self.assertLessEqual(len(recorder.share_title.get()), 100)
        self.assertEqual(recorder.status_messages[-1], "Paylaşım başlığı düzenlendi.")

    def test_apply_concise_share_description_uses_audio_preset_and_note(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = Path(tmpdir) / "aksam_take.mp3"
            audio_path.write_text("audio", encoding="utf-8")
            recorder.last_export_path = audio_path
            recorder.preset_name.set("Temiz Gitar")
            recorder.preset_note.set("Gece için hazır")

            recorder.apply_concise_share_description()

            self.assertEqual(
                recorder.share_description.get(),
                "Kayıt: aksam take | Preset: Temiz Gitar | Not: Gece için hazır",
            )
            self.assertEqual(recorder.status_messages[-1], "Kısa paylaşım açıklaması uygulandı.")

    def test_copy_share_upload_note_copies_music_defaults(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = Path(tmpdir) / "gitar_take.mp3"
            audio_path.write_text("audio", encoding="utf-8")
            recorder.last_export_path = audio_path
            recorder.preset_name.set("Temiz Gitar")

            recorder.copy_share_upload_note()

            recorder.root.clipboard_clear.assert_called_once()
            recorder.root.clipboard_append.assert_called_once()
            copied = recorder.root.clipboard_append.call_args[0][0]
            self.assertIn("Kategori: Music", copied)
            self.assertIn("Görünürlük: Herkese Açık", copied)
            self.assertEqual(recorder.status_messages[-1], "YouTube yükleme notu panoya alındı")

    def test_write_share_upload_note_writes_text_file_into_share_package(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "out"
            output_dir.mkdir(parents=True, exist_ok=True)
            audio_path = output_dir / "gitar_take.mp3"
            audio_path.write_text("audio", encoding="utf-8")
            recorder.last_export_path = audio_path
            recorder.output_dir.set(str(output_dir))
            recorder.resolve_output_dir = mock.Mock(return_value=output_dir)

            recorder.write_share_upload_note()

            note_path = output_dir / "_paylasim" / "gitar_take_youtube_paketi" / "youtube_yukleme_notu.txt"
            self.assertTrue(note_path.exists())
            self.assertIn("Kategori: Music", note_path.read_text(encoding="utf-8"))
            self.assertEqual(recorder.last_share_package_dir, note_path.parent)
            self.assertEqual(recorder.status_messages[-1], f"YouTube yükleme notu yazıldı: {note_path}")

    def test_copy_share_package_path_copies_existing_package_dir(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            package_dir = Path(tmpdir) / "_paylasim" / "gitar_take_youtube_paketi"
            package_dir.mkdir(parents=True, exist_ok=True)
            recorder.last_share_package_dir = package_dir

            recorder.copy_share_package_path()

            recorder.root.clipboard_clear.assert_called_once()
            recorder.root.clipboard_append.assert_called_once_with(str(package_dir))
            self.assertEqual(recorder.status_messages[-1], "Paylaşım paketi yolu panoya alındı")

    def test_copy_share_package_zip_path_copies_existing_zip(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            package_dir = Path(tmpdir) / "_paylasim" / "gitar_take_youtube_paketi"
            package_dir.mkdir(parents=True, exist_ok=True)
            zip_path = package_dir.parent / "gitar_take_youtube_paketi.zip"
            zip_path.write_text("zip", encoding="utf-8")
            recorder.last_share_package_dir = package_dir

            recorder.copy_share_package_zip_path()

            recorder.root.clipboard_clear.assert_called_once()
            recorder.root.clipboard_append.assert_called_once_with(str(zip_path))
            self.assertEqual(recorder.status_messages[-1], "Paylaşım paketi ZIP yolu panoya alındı")

    def test_copy_share_image_path_copies_existing_image(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "kapak.jpg"
            image_path.write_text("image", encoding="utf-8")
            recorder.share_image_path.set(str(image_path))

            recorder.copy_share_image_path()

            recorder.root.clipboard_clear.assert_called_once()
            recorder.root.clipboard_append.assert_called_once_with(str(image_path))
            self.assertEqual(recorder.status_messages[-1], "Kapak görseli yolu panoya alındı")

    def test_copy_share_meta_summary_copies_visible_summary(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = Path(tmpdir) / "gitar_take.mp3"
            image_path = Path(tmpdir) / "kapak.jpg"
            package_dir = Path(tmpdir) / "_paylasim" / "gitar_take_youtube_paketi"
            audio_path.write_text("audio", encoding="utf-8")
            image_path.write_text("image", encoding="utf-8")
            package_dir.mkdir(parents=True, exist_ok=True)
            recorder.last_export_path = audio_path
            recorder.share_image_path.set(str(image_path))
            recorder.last_share_package_dir = package_dir

            recorder.copy_share_meta_summary()

            expected_summary = "Ses: gitar_take.mp3 | Kapak: kapak.jpg | Paket: gitar_take_youtube_paketi"
            recorder.root.clipboard_clear.assert_called_once()
            recorder.root.clipboard_append.assert_called_once_with(expected_summary)
            self.assertEqual(recorder.status_messages[-1], "Paylaşım özeti panoya alındı")

    def test_write_share_meta_summary_writes_text_file_into_share_package(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "out"
            output_dir.mkdir(parents=True, exist_ok=True)
            audio_path = output_dir / "gitar_take.mp3"
            image_path = output_dir / "kapak.jpg"
            audio_path.write_text("audio", encoding="utf-8")
            image_path.write_text("image", encoding="utf-8")
            recorder.last_export_path = audio_path
            recorder.share_image_path.set(str(image_path))
            recorder.output_dir.set(str(output_dir))
            recorder.resolve_output_dir = mock.Mock(return_value=output_dir)

            recorder.write_share_meta_summary()

            summary_path = output_dir / "_paylasim" / "gitar_take_youtube_paketi" / "paylasim_ozeti.txt"
            self.assertTrue(summary_path.exists())
            self.assertEqual(
                summary_path.read_text(encoding="utf-8"),
                "Ses: gitar_take.mp3 | Kapak: kapak.jpg | Paket: gitar_take_youtube_paketi",
            )
            self.assertEqual(recorder.last_share_package_dir, summary_path.parent)
            self.assertEqual(recorder.status_messages[-1], f"Paylaşım özeti yazıldı: {summary_path}")

    def test_open_share_meta_summary_in_finder_reveals_existing_summary(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            package_dir = Path(tmpdir) / "_paylasim" / "gitar_take_youtube_paketi"
            package_dir.mkdir(parents=True, exist_ok=True)
            summary_path = package_dir / "paylasim_ozeti.txt"
            summary_path.write_text("summary", encoding="utf-8")
            recorder.last_share_package_dir = package_dir

            with mock.patch.object(app.subprocess, "run") as run_mock:
                recorder.open_share_meta_summary_in_finder()

        run_mock.assert_called_once_with(["open", "-R", str(summary_path)], check=False)
        self.assertEqual(recorder.status_messages[-1], f"Paylaşım özeti açıldı: {summary_path.name}")

    def test_export_share_package_zip_creates_zip_next_to_package(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            package_dir = Path(tmpdir) / "_paylasim" / "gitar_take_youtube_paketi"
            package_dir.mkdir(parents=True, exist_ok=True)
            (package_dir / "youtube_baslik.txt").write_text("Baslik", encoding="utf-8")
            recorder.last_share_package_dir = package_dir

            recorder.export_share_package_zip()

            zip_path = package_dir.parent / "gitar_take_youtube_paketi.zip"
            self.assertTrue(zip_path.exists())
            self.assertEqual(recorder.status_messages[-1], f"Paylaşım paketi ZIP hazır: {zip_path}")

    def test_open_share_package_zip_in_finder_reveals_existing_zip(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            package_dir = Path(tmpdir) / "_paylasim" / "gitar_take_youtube_paketi"
            package_dir.mkdir(parents=True, exist_ok=True)
            zip_path = package_dir.parent / "gitar_take_youtube_paketi.zip"
            zip_path.write_text("zip", encoding="utf-8")
            recorder.last_share_package_dir = package_dir

            with mock.patch.object(app.subprocess, "run") as run_mock:
                recorder.open_share_package_zip_in_finder()

        run_mock.assert_called_once_with(["open", "-R", str(zip_path)], check=False)
        self.assertEqual(recorder.status_messages[-1], f"Paylaşım paketi ZIP açıldı: {zip_path.name}")

    def test_write_share_guide_file_writes_combined_share_notes(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "out"
            output_dir.mkdir(parents=True, exist_ok=True)
            audio_path = output_dir / "gitar_take.mp3"
            audio_path.write_text("audio", encoding="utf-8")
            recorder.last_export_path = audio_path
            recorder.output_dir.set(str(output_dir))
            recorder.resolve_output_dir = mock.Mock(return_value=output_dir)
            recorder.share_title.set("Benim Basligim")
            recorder.share_description.set("Benim Aciklamam")

            recorder.write_share_guide_file()

            guide_path = output_dir / "_paylasim" / "gitar_take_youtube_paketi" / "paylasim_rehberi.txt"
            self.assertTrue(guide_path.exists())
            content = guide_path.read_text(encoding="utf-8")
            self.assertIn("Başlık: Benim Basligim", content)
            self.assertIn("Benim Aciklamam", content)
            self.assertIn("YouTube yükleme notu", content)
            self.assertEqual(recorder.last_share_package_dir, guide_path.parent)
            self.assertEqual(recorder.status_messages[-1], f"Paylaşım rehberi yazıldı: {guide_path}")

    def test_open_share_guide_in_finder_reveals_existing_guide(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            package_dir = Path(tmpdir) / "_paylasim" / "gitar_take_youtube_paketi"
            package_dir.mkdir(parents=True, exist_ok=True)
            guide_path = package_dir / "paylasim_rehberi.txt"
            guide_path.write_text("guide", encoding="utf-8")
            recorder.last_share_package_dir = package_dir

            with mock.patch.object(app.subprocess, "run") as run_mock:
                recorder.open_share_guide_in_finder()

        run_mock.assert_called_once_with(["open", "-R", str(guide_path)], check=False)
        self.assertEqual(recorder.status_messages[-1], f"Paylaşım rehberi açıldı: {guide_path.name}")

    def test_share_meta_summary_reports_audio_image_and_package_state(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = Path(tmpdir) / "gitar_take.mp3"
            image_path = Path(tmpdir) / "kapak.jpg"
            package_dir = Path(tmpdir) / "_paylasim" / "gitar_take_youtube_paketi"
            audio_path.write_text("audio", encoding="utf-8")
            image_path.write_text("image", encoding="utf-8")
            package_dir.mkdir(parents=True, exist_ok=True)
            recorder.last_export_path = audio_path
            recorder.share_image_path.set(str(image_path))
            recorder.last_share_package_dir = package_dir

            recorder.update_share_meta_text()

            self.assertEqual(
                recorder.share_meta_text.get(),
                "Ses: gitar_take.mp3 | Kapak: kapak.jpg | Paket: gitar_take_youtube_paketi",
            )

    def test_embed_cover_art_in_mp3_uses_mutagen_apic_tag(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            mp3_path = Path(tmpdir) / "take.mp3"
            image_path = Path(tmpdir) / "cover.jpg"
            mp3_path.write_text("audio", encoding="utf-8")
            image_path.write_bytes(b"fake-image")

            class FakeTags(dict):
                def add(self, frame) -> None:
                    self["APIC:new"] = frame

            class FakeAudio:
                def __init__(self) -> None:
                    self.tags = FakeTags({"APIC:old": "old"})
                    self.saved = False

                def add_tags(self) -> None:
                    self.tags = FakeTags()

                def save(self) -> None:
                    self.saved = True

            fake_audio = FakeAudio()

            class FakeAPIC:
                def __init__(self, **kwargs) -> None:
                    self.kwargs = kwargs

            with mock.patch.object(app, "MUTAGEN_AVAILABLE", True), mock.patch.object(app, "MP3", return_value=fake_audio), mock.patch.object(
                app, "ID3", object()
            ), mock.patch.object(app, "APIC", FakeAPIC):
                ok, message = recorder.embed_cover_art_in_mp3(mp3_path, image_path)

        self.assertTrue(ok)
        self.assertEqual(message, "Kapak görseli mp3 içine eklendi.")
        self.assertIn("APIC:new", fake_audio.tags)
        self.assertEqual(fake_audio.tags["APIC:new"].kwargs["mime"], "image/jpeg")
        self.assertEqual(fake_audio.tags["APIC:new"].kwargs["data"], b"fake-image")

    def test_notify_success_uses_root_bell(self) -> None:
        recorder = self.make_app()

        recorder.notify_success()

        recorder.root.bell.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
