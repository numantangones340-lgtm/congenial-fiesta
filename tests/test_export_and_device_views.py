import os
import sys
import tempfile
import time
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


class FakeButton:
    def __init__(self) -> None:
        self.config_calls = []

    def configure(self, **kwargs) -> None:
        self.config_calls.append(kwargs)


class ExportAndDeviceViewTests(unittest.TestCase):
    def make_app(self) -> app.GuitarAmpRecorderApp:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
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
        recorder.last_export_path = None
        recorder.last_session_summary_path = None
        recorder.open_last_export_button = FakeButton()
        recorder.open_last_summary_button = FakeButton()
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

    def test_refresh_recent_exports_includes_session_summary_hint(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            audio_path = output_dir / "take_001.wav"
            audio_path.write_text("audio", encoding="utf-8")
            summary_path = output_dir / "session_summary.json"
            summary_path.write_text("{}", encoding="utf-8")
            recorder.last_session_summary_path = summary_path
            recorder.resolve_output_dir = mock.Mock(return_value=output_dir)

            recorder.refresh_recent_exports()

        self.assertIn("- take_001.wav", recorder.recent_exports_text.get())
        self.assertIn("- session_summary.json (Oturum ozeti hazir)", recorder.recent_exports_text.get())

    def test_refresh_recent_exports_restores_last_export_from_newest_file(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            first = output_dir / "take_001.wav"
            second = output_dir / "take_002.mp3"
            first.write_text("audio", encoding="utf-8")
            second.write_text("audio", encoding="utf-8")
            os.utime(first, (time.time(), time.time()))
            os.utime(second, (time.time() + 10, time.time() + 10))
            recorder.resolve_output_dir = mock.Mock(return_value=output_dir)

            recorder.refresh_recent_exports()

        self.assertEqual(recorder.last_export_path, second)
        self.assertEqual(recorder.open_last_export_button.config_calls[-1], {"state": "normal"})

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

    def test_open_last_session_summary_handles_missing_summary(self) -> None:
        recorder = self.make_app()
        recorder.last_session_summary_path = None

        recorder.open_last_session_summary()

        self.assertEqual(recorder.status_messages[-1], "Son oturum ozeti bulunamadi.")


if __name__ == "__main__":
    unittest.main()
