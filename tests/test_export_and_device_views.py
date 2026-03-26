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
        recorder.prep_summary_text = FakeVar("")
        recorder.next_step_text = FakeVar("")
        recorder.selected_route_text = FakeVar("")
        recorder.input_device_choice = FakeVar("Varsayılan macOS girişi")
        recorder.output_device_choice = FakeVar("Varsayılan macOS çıkışı")
        recorder.input_device_id = FakeVar("")
        recorder.output_device_id = FakeVar("")
        recorder.device_summary_text = FakeVar("")
        recorder.setup_hint_text = FakeVar("")
        recorder.recording_active = False
        recorder.status_messages = []
        recorder.set_status = recorder.status_messages.append
        recorder.refresh_device_menus = mock.Mock()
        recorder.restart_input_meter = mock.Mock()
        recorder.backing_label = mock.Mock()
        recorder.recent_output_summary_label = mock.Mock()
        recorder.input_device_menu = FakeOptionMenu()
        recorder.output_device_menu = FakeOptionMenu()
        recorder.backing_file = None
        recorder.last_output_dir = None
        recorder.last_export_path = None
        recorder.last_summary_path = None
        recorder.last_take_notes_path = None
        recorder.last_recovery_note_path = None
        recorder.last_preparation_summary_path = None
        recorder.open_last_preparation_button = mock.Mock()
        recorder.open_last_output_dir_button = mock.Mock()
        recorder.write_last_session_state = mock.Mock()
        recorder.update_recent_output_summary = mock.Mock()
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
                '{"event":"record_export","timestamp":"2026-03-25 21:00:00","output_dir":"/tmp/session","preset_name":"Temiz Gitar","generated_files":["/tmp/session/take.mp3"],"recording":{"mode":"Sadece mikrofon","duration_seconds":42.0,"requested_duration_seconds":60.0,"input_peak":0.612,"processed_peak":0.701,"mix_peak":0.822,"stopped_early":true}}',
                encoding="utf-8",
            )
            recorder.last_summary_path = summary_path

            recorder.copy_last_session_brief_to_clipboard()

        recorder.root.clipboard_clear.assert_called_once_with()
        copied_text = recorder.root.clipboard_append.call_args[0][0]
        self.assertIn("Olay: record_export", copied_text)
        self.assertIn("Preset: Temiz Gitar", copied_text)
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
                '{"event":"record_export","timestamp":"2026-03-25 21:00:00","output_dir":"/tmp/session","preset_name":"Temiz Gitar","generated_files":["/tmp/session/take.mp3"],"recording":{"mode":"Sadece mikrofon","duration_seconds":42.0,"requested_duration_seconds":60.0,"input_peak":0.612,"processed_peak":0.701,"mix_peak":0.822,"stopped_early":false}}',
                encoding="utf-8",
            )
            recorder.last_summary_path = summary_path

            recorder.export_last_session_brief_file()

            brief_path = Path(tmpdir) / "session_brief.txt"
            self.assertTrue(brief_path.exists())
            self.assertIn("Preset: Temiz Gitar", brief_path.read_text(encoding="utf-8"))

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
        recorder.output_device_id.set("7")
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
        self.assertEqual(recorder.status_messages[-1], "Son kayıt oynatıldı: take.wav")

    def test_open_last_export_in_finder_selects_file_and_updates_status(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "take.wav"
            export_path.write_text("audio", encoding="utf-8")
            recorder.last_export_path = export_path

            with mock.patch.object(app.subprocess, "run") as run_mock:
                recorder.open_last_export_in_finder()

        run_mock.assert_called_once_with(["open", "-R", str(export_path)], check=False)
        self.assertEqual(recorder.status_messages[-1], "Son kayıt Finder'da seçildi: take.wav")

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

    def test_notify_success_uses_root_bell(self) -> None:
        recorder = self.make_app()

        recorder.notify_success()

        recorder.root.bell.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
