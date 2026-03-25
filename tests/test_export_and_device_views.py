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
        recorder.selected_route_text = FakeVar("")
        recorder.input_device_choice = FakeVar("Varsayılan macOS girişi")
        recorder.output_device_choice = FakeVar("Varsayılan macOS çıkışı")
        recorder.input_device_id = FakeVar("")
        recorder.output_device_id = FakeVar("")
        recorder.device_summary_text = FakeVar("")
        recorder.setup_hint_text = FakeVar("")
        recorder.status_messages = []
        recorder.set_status = recorder.status_messages.append
        recorder.refresh_device_menus = mock.Mock()
        recorder.restart_input_meter = mock.Mock()
        recorder.input_device_menu = FakeOptionMenu()
        recorder.output_device_menu = FakeOptionMenu()
        recorder.last_output_dir = None
        recorder.last_export_path = None
        recorder.last_summary_path = None
        return recorder

    def test_refresh_recent_exports_shows_newest_six_audio_files(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            files = []
            for index in range(7):
                suffix = ".mp3" if index % 2 == 0 else ".wav"
                path = output_dir / f"take_{index}{suffix}"
                path.write_text("audio", encoding="utf-8")
                os.utime(path, (time.time() + index, time.time() + index))
                files.append(path)
            (output_dir / "ignore.txt").write_text("skip", encoding="utf-8")

            recorder.resolve_output_dir = mock.Mock(return_value=output_dir)
            recorder.refresh_recent_exports()
            expected = [
                f"- {path.name}" for path in sorted(files, key=lambda path: path.stat().st_mtime, reverse=True)[:6]
            ]

        self.assertEqual(recorder.recent_exports_text.get(), "\n".join(expected))

    def test_refresh_recent_exports_handles_missing_dir(self) -> None:
        recorder = self.make_app()
        missing_dir = Path("/tmp/does-not-exist-gar")
        recorder.resolve_output_dir = mock.Mock(return_value=missing_dir)

        recorder.refresh_recent_exports()

        self.assertEqual(recorder.recent_exports_text.get(), f"Klasor bulunamadi: {missing_dir}")

    def test_refresh_recent_exports_prefers_last_output_dir(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            newer = output_dir / "latest_take.wav"
            newer.write_text("audio", encoding="utf-8")
            recorder.last_output_dir = output_dir
            recorder.resolve_output_dir = mock.Mock(return_value=Path("/tmp/unused-output"))

            recorder.refresh_recent_exports()

        self.assertEqual(recorder.recent_exports_text.get(), f"- {newer.name}")
        recorder.resolve_output_dir.assert_not_called()

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

        self.assertEqual(recorder.status_messages[-1], "Son export dosyasi bulunamadi.")

    def test_open_last_session_summary_in_finder_handles_missing_summary(self) -> None:
        recorder = self.make_app()
        recorder.last_summary_path = None

        recorder.open_last_session_summary_in_finder()

        self.assertEqual(recorder.status_messages[-1], "Oturum ozeti bulunamadi.")

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
        self.assertEqual(recorder.status_messages[-1], "Oturum ozeti panoya kopyalandi: session_summary.json")

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
        self.assertEqual(recorder.status_messages[-1], "Son export yolu panoya kopyalandi: take.mp3")

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
        self.assertEqual(recorder.status_messages[-1], "Oturum ozeti yolu panoya kopyalandi: session_summary.json")

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
        self.assertEqual(recorder.status_messages[-1], "Kisa oturum raporu panoya kopyalandi: session_summary.json")

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

        self.assertIn("Kisa rapor dosyaya yazildi:", recorder.status_messages[-1])

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
        self.assertEqual(recorder.status_messages[-1], "Son kayit oynatildi: take.wav")

    def test_open_last_export_in_finder_selects_file_and_updates_status(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "take.wav"
            export_path.write_text("audio", encoding="utf-8")
            recorder.last_export_path = export_path

            with mock.patch.object(app.subprocess, "run") as run_mock:
                recorder.open_last_export_in_finder()

        run_mock.assert_called_once_with(["open", "-R", str(export_path)], check=False)
        self.assertEqual(recorder.status_messages[-1], "Son dosya Finder'da secili gosterildi: take.wav")

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

    def test_notify_success_uses_root_bell(self) -> None:
        recorder = self.make_app()

        recorder.notify_success()

        recorder.root.bell.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
