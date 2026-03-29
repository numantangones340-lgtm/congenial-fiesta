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

    def test_empty_recent_exports_message_matches_empty_state_copy(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.empty_recent_exports_message(),
            "Henuz ses kaydi yok. Yeni kayitlar burada gosterilir.",
        )

    def test_list_recent_export_audio_files_filters_audio_only(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            wav_path = output_dir / "take_001.wav"
            mp3_path = output_dir / "take_002.mp3"
            txt_path = output_dir / "notes.txt"
            wav_path.write_text("audio", encoding="utf-8")
            mp3_path.write_text("audio", encoding="utf-8")
            txt_path.write_text("skip", encoding="utf-8")

            audio_files = recorder.list_recent_export_audio_files(output_dir)

        self.assertEqual(sorted(path.name for path in audio_files), ["take_001.wav", "take_002.mp3"])

    def test_limit_recent_export_audio_files_returns_newest_six(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            files = []
            for index in range(7):
                path = output_dir / f"take_{index}.wav"
                path.write_text("audio", encoding="utf-8")
                os.utime(path, (time.time() + index, time.time() + index))
                files.append(path)

            recent_files = recorder.limit_recent_export_audio_files(files)

        self.assertEqual(len(recent_files), 6)
        self.assertEqual(recent_files[0].name, "take_6.wav")
        self.assertEqual(recent_files[-1].name, "take_1.wav")

    def test_should_refresh_last_export_path_when_missing(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            newest = output_dir / "take_002.wav"
            newest.write_text("audio", encoding="utf-8")

            self.assertTrue(recorder.should_refresh_last_export_path(None, output_dir, newest))

    def test_should_refresh_last_export_path_when_stale(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            current = output_dir / "take_001.wav"
            newest = output_dir / "take_002.wav"
            current.write_text("audio", encoding="utf-8")
            newest.write_text("audio", encoding="utf-8")

            self.assertTrue(recorder.should_refresh_last_export_path(current, output_dir, newest))

    def test_should_refresh_last_export_path_when_current_is_latest(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            newest = output_dir / "take_002.wav"
            newest.write_text("audio", encoding="utf-8")

            self.assertFalse(recorder.should_refresh_last_export_path(newest, output_dir, newest))

    def test_refresh_last_export_path_updates_when_needed(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            newest = output_dir / "take_002.wav"
            newest.write_text("audio", encoding="utf-8")
            recorder.last_export_path = None

            recorder.refresh_last_export_path(output_dir, newest)

            self.assertEqual(recorder.last_export_path, newest)

    def test_refresh_last_export_path_keeps_current_when_latest(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            newest = output_dir / "take_002.wav"
            newest.write_text("audio", encoding="utf-8")
            recorder.last_export_path = newest

            recorder.refresh_last_export_path(output_dir, newest)

            self.assertEqual(recorder.last_export_path, newest)

    def test_empty_recent_exports_summary_message_matches_summary_only_copy(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.empty_recent_exports_summary_message(),
            "Henuz ses kaydi yok. Alttaki ozeti acabilirsiniz.",
        )

    def test_summary_ready_status_message_matches_status_copy(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.summary_ready_status_message(),
            "Ozet hazir. Isterseniz acabilirsiniz.",
        )

    def test_recent_output_exists_returns_false_without_path(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertFalse(recorder.recent_output_exists(None))

    def test_recent_output_exists_returns_false_for_missing_path(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertFalse(recorder.recent_output_exists(Path("/tmp/does-not-exist-gar")))

    def test_recent_output_exists_returns_true_for_existing_path(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "take.wav"
            path.write_text("audio", encoding="utf-8")

            self.assertTrue(recorder.recent_output_exists(path))

    def test_has_recent_session_summary_returns_false_without_path(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        recorder.last_session_summary_path = None

        self.assertFalse(recorder.has_recent_session_summary())

    def test_has_recent_session_summary_returns_true_for_existing_file(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        with tempfile.TemporaryDirectory() as tmpdir:
            summary_path = Path(tmpdir) / "session_summary.json"
            summary_path.write_text("{}", encoding="utf-8")
            recorder.last_session_summary_path = summary_path

            self.assertTrue(recorder.has_recent_session_summary())

    def test_resolved_recent_session_summary_path_returns_matching_current_path(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            summary_path = output_dir / "session_summary.json"
            summary_path.write_text("{}", encoding="utf-8")
            recorder.last_session_summary_path = summary_path

            self.assertEqual(recorder.resolved_recent_session_summary_path(output_dir), summary_path)

    def test_resolved_recent_session_summary_path_returns_candidate_when_current_is_stale(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        with tempfile.TemporaryDirectory() as tmpdir, tempfile.TemporaryDirectory() as olddir:
            output_dir = Path(tmpdir)
            summary_path = output_dir / "session_summary.json"
            summary_path.write_text("{}", encoding="utf-8")
            old_summary = Path(olddir) / "session_summary.json"
            old_summary.write_text("{}", encoding="utf-8")
            recorder.last_session_summary_path = old_summary

            self.assertEqual(recorder.resolved_recent_session_summary_path(output_dir), summary_path)

    def test_resolved_recent_session_summary_path_returns_none_when_missing(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        recorder.last_session_summary_path = None
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            self.assertIsNone(recorder.resolved_recent_session_summary_path(output_dir))

    def test_recent_output_button_state_is_disabled_without_path(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(recorder.recent_output_button_state(None), "disabled")

    def test_recent_output_button_state_is_disabled_for_missing_path(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(recorder.recent_output_button_state(Path("/tmp/does-not-exist-gar")), "disabled")

    def test_recent_output_button_state_is_normal_for_existing_path(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "take.wav"
            path.write_text("audio", encoding="utf-8")

            self.assertEqual(recorder.recent_output_button_state(path), "normal")

    def test_apply_recent_output_button_state_configures_button(self) -> None:
        recorder = self.make_app()
        button = recorder.open_last_export_button
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "take.wav"
            path.write_text("audio", encoding="utf-8")

            recorder.apply_recent_output_button_state(button, path)

        self.assertEqual(button.config_calls[-1], {"state": "normal"})

    def test_recent_output_buttons_returns_export_and_summary_buttons(self) -> None:
        recorder = self.make_app()

        self.assertEqual(
            recorder.recent_output_buttons(),
            (recorder.open_last_export_button, recorder.open_last_summary_button),
        )

    def test_recent_output_button_paths_returns_export_and_summary_paths(self) -> None:
        recorder = self.make_app()
        recorder.last_export_path = Path("/tmp/take.wav")
        recorder.last_session_summary_path = Path("/tmp/session_summary.json")

        self.assertEqual(
            recorder.recent_output_button_paths(),
            (Path("/tmp/take.wav"), Path("/tmp/session_summary.json")),
        )

    def test_recent_output_button_bindings_returns_buttons_with_paths(self) -> None:
        recorder = self.make_app()
        recorder.last_export_path = Path("/tmp/take.wav")
        recorder.last_session_summary_path = Path("/tmp/session_summary.json")

        self.assertEqual(
            recorder.recent_output_button_bindings(),
            (
                (recorder.open_last_export_button, Path("/tmp/take.wav")),
                (recorder.open_last_summary_button, Path("/tmp/session_summary.json")),
            ),
        )

    def test_apply_recent_output_button_bindings_configures_bound_buttons(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "take.wav"
            summary_path = Path(tmpdir) / "session_summary.json"
            export_path.write_text("audio", encoding="utf-8")
            summary_path.write_text("{}", encoding="utf-8")

            recorder.apply_recent_output_button_bindings(
                (
                    (recorder.open_last_export_button, export_path),
                    (recorder.open_last_summary_button, summary_path),
                )
            )

        self.assertEqual(recorder.open_last_export_button.config_calls[-1], {"state": "normal"})
        self.assertEqual(recorder.open_last_summary_button.config_calls[-1], {"state": "normal"})

    def test_clear_recent_output_target_path_clears_named_attribute(self) -> None:
        recorder = self.make_app()
        recorder.last_export_path = Path("/tmp/take.wav")

        recorder.clear_recent_output_target_path("last_export_path")

        self.assertIsNone(recorder.last_export_path)

    def test_recent_outputs_refresh_callback_returns_refresh_method(self) -> None:
        recorder = self.make_app()
        recorder.refresh_recent_exports = mock.Mock()

        self.assertIs(recorder.recent_outputs_refresh_callback(), recorder.refresh_recent_exports)

    def test_clear_missing_recent_output_target_clears_path_and_updates_status(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "take.wav"
            export_path.write_text("audio", encoding="utf-8")
            recorder.last_export_path = export_path

            recorder.clear_missing_recent_output_target(
                "last_export_path",
                "Son export dosyasi bulunamadi; son ciktilar yenilendi.",
            )

        self.assertIsNone(recorder.last_export_path)
        self.assertEqual(recorder.open_last_export_button.config_calls[-1], {"state": "disabled"})
        self.assertEqual(recorder.open_last_summary_button.config_calls[-1], {"state": "disabled"})
        self.assertEqual(recorder.status_messages[-1], "Son export dosyasi bulunamadi; son ciktilar yenilendi.")

    def test_set_recent_output_open_status_reports_filename(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "take.wav"
            export_path.write_text("audio", encoding="utf-8")

            recorder.set_recent_output_open_status("Son export Finder'da gosteriliyor", export_path)

        self.assertEqual(recorder.status_messages[-1], "Son export Finder'da gosteriliyor: take.wav")

    def test_recent_output_open_status_text_formats_filename(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        path = Path("/tmp/take.wav")

        self.assertEqual(
            recorder.recent_output_open_status_text("Son export Finder'da gosteriliyor", path),
            "Son export Finder'da gosteriliyor: take.wav",
        )

    def test_recent_output_open_status_name_returns_filename(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_output_open_status_name(Path("/tmp/take.wav")),
            "take.wav",
        )

    def test_recent_output_open_status_target_text_returns_filename(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_output_open_status_target_text(Path("/tmp/take.wav")),
            "take.wav",
        )

    def test_output_dir_open_status_prefix_matches_created_copy(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(recorder.output_dir_open_status_prefix(True), "Klasor hazirlandi ve acildi")
        self.assertEqual(recorder.output_dir_open_status_prefix(False), "Klasor acildi")

    def test_output_dir_open_status_target_text_uses_recent_output_dir_text(self) -> None:
        recorder = self.make_app()
        output_dir = Path("/tmp/new-session-folder")
        recorder.recent_output_dir_text = mock.Mock(return_value="~/new-session-folder")

        self.assertEqual(
            recorder.output_dir_open_status_target_text(output_dir),
            "~/new-session-folder",
        )
        recorder.recent_output_dir_text.assert_called_once_with(output_dir)

    def test_output_dir_open_status_text_formats_created_copy(self) -> None:
        recorder = self.make_app()
        recorder.recent_output_dir_text = mock.Mock(return_value="~/new-session-folder")
        output_dir = Path("/tmp/new-session-folder")

        self.assertEqual(
            recorder.output_dir_open_status_text(output_dir, created_now=True),
            "Klasor hazirlandi ve acildi: ~/new-session-folder",
        )

    def test_set_output_dir_open_status_reports_created_folder(self) -> None:
        recorder = self.make_app()
        recorder.recent_output_dir_text = mock.Mock(return_value="~/new-session-folder")
        output_dir = Path("/tmp/new-session-folder")

        recorder.set_output_dir_open_status(output_dir, created_now=True)

        recorder.recent_output_dir_text.assert_called_once_with(output_dir)
        self.assertEqual(recorder.status_messages[-1], "Klasor hazirlandi ve acildi: ~/new-session-folder")

    def test_set_output_dir_open_status_reports_existing_folder(self) -> None:
        recorder = self.make_app()
        recorder.recent_output_dir_text = mock.Mock(return_value="~/existing-session-folder")
        output_dir = Path("/tmp/existing-session-folder")

        recorder.set_output_dir_open_status(output_dir, created_now=False)

        recorder.recent_output_dir_text.assert_called_once_with(output_dir)
        self.assertEqual(recorder.status_messages[-1], "Klasor acildi: ~/existing-session-folder")

    def test_output_dir_was_missing_detects_missing_and_existing_dir(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        with tempfile.TemporaryDirectory() as tmpdir:
            existing_dir = Path(tmpdir)
            missing_dir = existing_dir / "new-session-folder"

            self.assertFalse(recorder.output_dir_was_missing(existing_dir))
            self.assertTrue(recorder.output_dir_was_missing(missing_dir))

    def test_open_output_dir_creates_missing_directory_and_reports_created(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "new-session-folder"

            with mock.patch.object(app.subprocess, "run") as run_mock:
                created_now = recorder.open_output_dir(output_dir)

            self.assertTrue(created_now)
            self.assertTrue(output_dir.exists())
            run_mock.assert_called_once_with(["open", str(output_dir)], check=False)

    def test_open_output_dir_returns_false_for_existing_directory(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            with mock.patch.object(app.subprocess, "run") as run_mock:
                created_now = recorder.open_output_dir(output_dir)

        self.assertFalse(created_now)
        run_mock.assert_called_once_with(["open", str(output_dir)], check=False)

    def test_refresh_recent_exports_after_output_dir_open_refreshes_resolved_dir(self) -> None:
        recorder = self.make_app()
        output_dir = Path("/tmp/new-session-folder")
        recorder.refresh_recent_exports_for_resolved_output_dir = mock.Mock()

        recorder.refresh_recent_exports_after_output_dir_open(output_dir)

        recorder.refresh_recent_exports_for_resolved_output_dir.assert_called_once_with(output_dir)

    def test_open_output_dir_and_refresh_recent_exports_returns_created_state(self) -> None:
        recorder = self.make_app()
        output_dir = Path("/tmp/new-session-folder")
        recorder.open_output_dir = mock.Mock(return_value=True)
        recorder.refresh_recent_exports_for_resolved_output_dir = mock.Mock()

        created_now = recorder.open_output_dir_and_refresh_recent_exports(output_dir)

        self.assertTrue(created_now)
        recorder.open_output_dir.assert_called_once_with(output_dir)
        recorder.refresh_recent_exports_for_resolved_output_dir.assert_called_once_with(output_dir)

    def test_open_output_dir_and_refresh_recent_exports_keeps_existing_state(self) -> None:
        recorder = self.make_app()
        output_dir = Path("/tmp/existing-session-folder")
        recorder.open_output_dir = mock.Mock(return_value=False)
        recorder.refresh_recent_exports_for_resolved_output_dir = mock.Mock()

        created_now = recorder.open_output_dir_and_refresh_recent_exports(output_dir)

        self.assertFalse(created_now)
        recorder.open_output_dir.assert_called_once_with(output_dir)
        recorder.refresh_recent_exports_for_resolved_output_dir.assert_called_once_with(output_dir)

    def test_open_output_dir_with_status_reports_created_state(self) -> None:
        recorder = self.make_app()
        output_dir = Path("/tmp/new-session-folder")
        recorder.open_output_dir_and_refresh_recent_exports = mock.Mock(return_value=True)
        recorder.set_output_dir_open_status = mock.Mock()

        recorder.open_output_dir_with_status(output_dir)

        recorder.open_output_dir_and_refresh_recent_exports.assert_called_once_with(output_dir)
        recorder.set_output_dir_open_status.assert_called_once_with(output_dir, True)

    def test_output_dir_open_error_text_formats_exception(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.output_dir_open_error_text(RuntimeError("boom")),
            "Klasor acilamadi: boom",
        )

    def test_output_dir_open_error_prefix_returns_copy(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(recorder.output_dir_open_error_prefix(), "Klasor acilamadi")

    def test_output_dir_open_error_detail_text_returns_exception_text(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.output_dir_open_error_detail_text(RuntimeError("boom")),
            "boom",
        )

    def test_set_output_dir_open_error_status_reports_exception(self) -> None:
        recorder = self.make_app()

        recorder.set_output_dir_open_error_status(RuntimeError("boom"))

        self.assertEqual(recorder.status_messages[-1], "Klasor acilamadi: boom")

    def test_open_resolved_output_dir_in_finder_reports_created_directory(self) -> None:
        recorder = self.make_app()
        output_dir = Path("/tmp/new-session-folder")
        recorder.open_output_dir_and_refresh_recent_exports = mock.Mock(return_value=True)
        recorder.set_output_dir_open_status = mock.Mock()

        recorder.open_resolved_output_dir_in_finder(output_dir)

        recorder.open_output_dir_and_refresh_recent_exports.assert_called_once_with(output_dir)
        recorder.set_output_dir_open_status.assert_called_once_with(output_dir, True)

    def test_open_resolved_output_dir_in_finder_reports_open_error(self) -> None:
        recorder = self.make_app()
        output_dir = Path("/tmp/broken-session-folder")
        recorder.open_output_dir_and_refresh_recent_exports = mock.Mock(side_effect=RuntimeError("boom"))

        recorder.open_resolved_output_dir_in_finder(output_dir)

        self.assertEqual(recorder.status_messages[-1], "Klasor acilamadi: boom")

    def test_open_current_output_dir_in_finder_resolves_and_delegates(self) -> None:
        recorder = self.make_app()
        output_dir = Path("/tmp/current-session-folder")
        recorder.current_recent_output_dir = mock.Mock(return_value=output_dir)
        recorder.open_resolved_output_dir_in_finder = mock.Mock()

        resolved_output_dir = recorder.open_current_output_dir_in_finder()

        self.assertEqual(resolved_output_dir, output_dir)
        recorder.current_recent_output_dir.assert_called_once_with()
        recorder.open_resolved_output_dir_in_finder.assert_called_once_with(output_dir)

    def test_refresh_recent_exports_for_resolved_output_dir_returns_dir(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        output_dir = Path("/tmp/demo-output")
        recorder.show_recent_exports_for_resolved_output_dir = mock.Mock()

        resolved = recorder.refresh_recent_exports_for_resolved_output_dir(output_dir)

        self.assertEqual(resolved, output_dir)
        recorder.show_recent_exports_for_resolved_output_dir.assert_called_once_with(output_dir)

    def test_output_dir_open_command_returns_open_command(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        output_dir = Path("/tmp/demo-output")

        self.assertEqual(
            recorder.output_dir_open_command(output_dir),
            ["open", "/tmp/demo-output"],
        )

    def test_output_dir_open_command_prefix_returns_open(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(recorder.output_dir_open_command_prefix(), ["open"])

    def test_output_dir_open_command_text_returns_path_string(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        output_dir = Path("/tmp/demo-output")

        self.assertEqual(recorder.output_dir_open_command_text(output_dir), "/tmp/demo-output")

    def test_recent_output_open_command_prefix_matches_reveal_mode(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(recorder.recent_output_open_command_prefix(True), ["open", "-R"])
        self.assertEqual(recorder.recent_output_open_command_prefix(False), ["open"])

    def test_recent_output_open_command_text_returns_path_string(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        path = Path("/tmp/take.wav")

        self.assertEqual(recorder.recent_output_open_command_text(path), "/tmp/take.wav")

    def test_recent_output_open_command_for_finder_reveal(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        path = Path("/tmp/take.wav")

        self.assertEqual(
            recorder.recent_output_open_command(path, reveal_in_finder=True),
            ["open", "-R", "/tmp/take.wav"],
        )

    def test_recent_output_open_command_for_direct_open(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        path = Path("/tmp/session_summary.json")

        self.assertEqual(
            recorder.recent_output_open_command(path, reveal_in_finder=False),
            ["open", "/tmp/session_summary.json"],
        )

    def test_recent_output_target_path_reads_named_attribute(self) -> None:
        recorder = self.make_app()
        recorder.last_export_path = Path("/tmp/take.wav")

        self.assertEqual(
            recorder.recent_output_target_path("last_export_path"),
            Path("/tmp/take.wav"),
        )

    def test_existing_recent_output_target_path_returns_existing_path(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "take.wav"
            export_path.write_text("audio", encoding="utf-8")
            recorder.last_export_path = export_path

            self.assertEqual(
                recorder.existing_recent_output_target_path("last_export_path"),
                export_path,
            )

    def test_refreshed_recent_output_target_path_refreshes_and_returns_existing_path(self) -> None:
        recorder = self.make_app()
        recorder.refresh_recent_exports = mock.Mock()
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "take.wav"
            export_path.write_text("audio", encoding="utf-8")
            recorder.last_export_path = export_path

            self.assertEqual(
                recorder.refreshed_recent_output_target_path("last_export_path"),
                export_path,
            )

        recorder.refresh_recent_exports.assert_called_once()

    def test_open_recent_output_path_runs_open_command_and_reports_success(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "take.wav"
            export_path.write_text("audio", encoding="utf-8")

            with mock.patch.object(app.subprocess, "run") as run_mock:
                recorder.open_recent_output_path(
                    export_path,
                    success_prefix="Son export Finder'da gosteriliyor",
                    error_prefix="Finder acilamadi",
                    reveal_in_finder=True,
                )

        run_mock.assert_called_once_with(["open", "-R", str(export_path)], check=False)
        self.assertEqual(recorder.status_messages[-1], "Son export Finder'da gosteriliyor: take.wav")

    def test_recent_output_open_error_text_formats_exception(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_output_open_error_text("Finder acilamadi", RuntimeError("boom")),
            "Finder acilamadi: boom",
        )

    def test_recent_output_open_error_prefix_returns_copy(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_output_open_error_prefix("Finder acilamadi"),
            "Finder acilamadi",
        )

    def test_recent_output_open_error_detail_text_returns_exception_text(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_output_open_error_detail_text(RuntimeError("boom")),
            "boom",
        )

    def test_set_recent_output_open_error_status_reports_exception(self) -> None:
        recorder = self.make_app()

        recorder.set_recent_output_open_error_status("Finder acilamadi", RuntimeError("boom"))

        self.assertEqual(recorder.status_messages[-1], "Finder acilamadi: boom")

    def test_open_recent_output_target_clears_missing_path(self) -> None:
        recorder = self.make_app()
        recorder.last_export_path = None
        recorder.refresh_recent_exports = mock.Mock()

        recorder.open_recent_output_target(
            attribute_name="last_export_path",
            missing_message="Son export dosyasi bulunamadi; son ciktilar yenilendi.",
            success_prefix="Son export Finder'da gosteriliyor",
            error_prefix="Finder acilamadi",
            reveal_in_finder=True,
        )

        recorder.refresh_recent_exports.assert_called_once()
        self.assertIsNone(recorder.last_export_path)
        self.assertEqual(recorder.open_last_export_button.config_calls[-1], {"state": "disabled"})
        self.assertEqual(recorder.status_messages[-1], "Son export dosyasi bulunamadi; son ciktilar yenilendi.")

    def test_open_recent_output_target_reports_success(self) -> None:
        recorder = self.make_app()
        recorder.refresh_recent_exports = mock.Mock()
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "take.wav"
            export_path.write_text("audio", encoding="utf-8")
            recorder.last_export_path = export_path

            with mock.patch.object(app.subprocess, "run") as run_mock:
                recorder.open_recent_output_target(
                    attribute_name="last_export_path",
                    missing_message="Son export dosyasi bulunamadi; son ciktilar yenilendi.",
                    success_prefix="Son export Finder'da gosteriliyor",
                    error_prefix="Finder acilamadi",
                    reveal_in_finder=True,
                )

        recorder.refresh_recent_exports.assert_called_once()
        run_mock.assert_called_once_with(["open", "-R", str(export_path)], check=False)
        self.assertEqual(recorder.status_messages[-1], "Son export Finder'da gosteriliyor: take.wav")

    def test_empty_recent_exports_status_message_matches_status_copy(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.empty_recent_exports_status_message(),
            "Durum guncel. Yeni kayitlar burada gosterilir.",
        )

    def test_summary_ready_full_status_message_matches_status_copy(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.summary_ready_full_status_message(),
            "Durum guncel. Ozet hazir. Isterseniz acabilirsiniz.",
        )

    def test_recent_exports_empty_status_message_without_summary(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_exports_empty_status_message(has_summary=False),
            "Durum guncel. Yeni kayitlar burada gosterilir.",
        )

    def test_recent_exports_empty_status_message_with_summary(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_exports_empty_status_message(has_summary=True),
            "Durum guncel. Ozet hazir. Isterseniz acabilirsiniz.",
        )

    def test_missing_output_dir_message_matches_empty_view_copy(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.missing_output_dir_message("~/missing-output"),
            "Cikis klasoru bulunamadi: ~/missing-output\nBu cikis klasorune su an ulasilamiyor.\n'Klasoru Ac' ile yeniden olusturabilir ve Finder'da acabilirsiniz.",
        )

    def test_missing_output_dir_status_matches_status_copy(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.missing_output_dir_status("~/Missing"),
            "Durum guncel. Cikis klasoru bulunamadi: ~/Missing. 'Klasoru Ac' ile yeniden olusturabilir ve Finder'da acabilirsiniz.",
        )

    def test_show_missing_recent_exports_clears_recent_paths_and_updates_text(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "take.wav"
            summary_path = Path(tmpdir) / "session_summary.json"
            export_path.write_text("audio", encoding="utf-8")
            summary_path.write_text("{}", encoding="utf-8")
            recorder.last_export_path = export_path
            recorder.last_session_summary_path = summary_path
            missing_dir = Path(tmpdir) / "missing"

            recorder.show_missing_recent_exports(missing_dir)

        self.assertIsNone(recorder.last_export_path)
        self.assertIsNone(recorder.last_session_summary_path)
        self.assertEqual(
            recorder.recent_exports_text.get(),
            f"Cikis klasoru bulunamadi: {missing_dir}\n"
            "Bu cikis klasorune su an ulasilamiyor.\n"
            "'Klasoru Ac' ile yeniden olusturabilir ve Finder'da acabilirsiniz.",
        )
        self.assertEqual(recorder.open_last_export_button.config_calls[-1], {"state": "disabled"})
        self.assertEqual(recorder.open_last_summary_button.config_calls[-1], {"state": "disabled"})

    def test_clear_recent_output_paths_clears_export_and_summary(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "take.wav"
            summary_path = Path(tmpdir) / "session_summary.json"
            export_path.write_text("audio", encoding="utf-8")
            summary_path.write_text("{}", encoding="utf-8")
            recorder.last_export_path = export_path
            recorder.last_session_summary_path = summary_path

            recorder.clear_recent_output_paths()

        self.assertIsNone(recorder.last_export_path)
        self.assertIsNone(recorder.last_session_summary_path)

    def test_recent_output_dir_text_uses_format_display_path(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        output_dir = Path("/tmp/demo-output")
        recorder.format_display_path = mock.Mock(return_value="~/Demo")

        output_dir_text = recorder.recent_output_dir_text(output_dir)

        self.assertEqual(output_dir_text, "~/Demo")
        recorder.format_display_path.assert_called_once_with(output_dir)

    def test_show_recent_exports_for_output_dir_uses_display_context(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        output_dir = Path("/tmp/demo-output")
        display_context = {
            "summary_line": "",
            "recent_files": [],
            "count_line": "Top 0",
            "hidden_count": 0,
        }
        recorder.recent_output_dir_text = mock.Mock(return_value="~/Demo")
        recorder.restore_session_summary_from_output_dir = mock.Mock()
        recorder.recent_exports_display_context = mock.Mock(return_value=display_context)
        recorder.show_recent_exports_from_context = mock.Mock()

        recorder.show_recent_exports_for_output_dir(output_dir)

        recorder.recent_output_dir_text.assert_called_once_with(output_dir)
        recorder.restore_session_summary_from_output_dir.assert_called_once_with(output_dir)
        recorder.recent_exports_display_context.assert_called_once_with(output_dir)
        recorder.show_recent_exports_from_context.assert_called_once_with(output_dir, "~/Demo", display_context)

    def test_recent_exports_display_payload_restores_summary_and_returns_context(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        output_dir = Path("/tmp/demo-output")
        display_context = {
            "summary_line": "",
            "recent_files": [],
            "count_line": "Top 0",
            "hidden_count": 0,
        }
        recorder.recent_output_dir_text = mock.Mock(return_value="~/Demo")
        recorder.restore_session_summary_from_output_dir = mock.Mock()
        recorder.recent_exports_display_context = mock.Mock(return_value=display_context)

        output_dir_text, payload = recorder.recent_exports_display_payload(output_dir)

        self.assertEqual(output_dir_text, "~/Demo")
        self.assertEqual(payload, display_context)
        recorder.recent_output_dir_text.assert_called_once_with(output_dir)
        recorder.restore_session_summary_from_output_dir.assert_called_once_with(output_dir)
        recorder.recent_exports_display_context.assert_called_once_with(output_dir)

    def test_show_recent_exports_for_resolved_output_dir_uses_missing_helper(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        missing_dir = Path("/tmp/does-not-exist-gar")
        recorder.show_missing_recent_exports = mock.Mock()
        recorder.show_recent_exports_for_output_dir = mock.Mock()

        recorder.show_recent_exports_for_resolved_output_dir(missing_dir)

        recorder.show_missing_recent_exports.assert_called_once_with(missing_dir)
        recorder.show_recent_exports_for_output_dir.assert_not_called()

    def test_show_recent_exports_for_resolved_output_dir_uses_existing_dir_helper(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            recorder.show_missing_recent_exports = mock.Mock()
            recorder.show_recent_exports_for_output_dir = mock.Mock()

            recorder.show_recent_exports_for_resolved_output_dir(output_dir)

        recorder.show_missing_recent_exports.assert_not_called()
        recorder.show_recent_exports_for_output_dir.assert_called_once_with(output_dir)

    def test_refresh_recent_exports_for_current_output_dir_returns_resolved_dir(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        output_dir = Path("/tmp/demo-output")
        recorder.current_recent_output_dir = mock.Mock(return_value=output_dir)
        recorder.refresh_recent_exports_for_resolved_output_dir = mock.Mock(return_value=output_dir)

        resolved = recorder.refresh_recent_exports_for_current_output_dir()

        self.assertEqual(resolved, output_dir)
        recorder.current_recent_output_dir.assert_called_once_with()
        recorder.refresh_recent_exports_for_resolved_output_dir.assert_called_once_with(output_dir)

    def test_set_recent_exports_refresh_status_for_current_output_dir_uses_resolved_dir(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        output_dir = Path("/tmp/demo-output")
        recorder.current_recent_output_dir = mock.Mock(return_value=output_dir)
        recorder.set_recent_exports_refresh_status_for_resolved_output_dir = mock.Mock(return_value=output_dir)

        recorder.set_recent_exports_refresh_status_for_current_output_dir()

        recorder.current_recent_output_dir.assert_called_once_with()
        recorder.set_recent_exports_refresh_status_for_resolved_output_dir.assert_called_once_with(output_dir)

    def test_set_recent_exports_refresh_status_for_resolved_output_dir_returns_dir(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        output_dir = Path("/tmp/demo-output")
        recorder.set_recent_exports_refresh_status = mock.Mock()

        resolved = recorder.set_recent_exports_refresh_status_for_resolved_output_dir(output_dir)

        self.assertEqual(resolved, output_dir)
        recorder.set_recent_exports_refresh_status.assert_called_once_with(output_dir)

    def test_refresh_recent_exports_from_action_for_resolved_output_dir_returns_dir(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        output_dir = Path("/tmp/demo-output")
        recorder.refresh_recent_exports_for_resolved_output_dir = mock.Mock(return_value=output_dir)
        recorder.set_recent_exports_refresh_status_for_resolved_output_dir = mock.Mock(return_value=output_dir)

        resolved = recorder.refresh_recent_exports_from_action_for_resolved_output_dir(output_dir)

        self.assertEqual(resolved, output_dir)
        recorder.refresh_recent_exports_for_resolved_output_dir.assert_called_once_with(output_dir)
        recorder.set_recent_exports_refresh_status_for_resolved_output_dir.assert_called_once_with(output_dir)

    def test_current_recent_output_dir_uses_resolve_output_dir(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        output_dir = Path("/tmp/current-recent-output")
        recorder.resolve_output_dir = mock.Mock(return_value=output_dir)

        resolved = recorder.current_recent_output_dir()

        self.assertEqual(resolved, output_dir)
        recorder.resolve_output_dir.assert_called_once_with()

    def test_recent_exports_count_line_matches_truncated_list_copy(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_exports_count_line(total_audio_count=7, shown_count=6, has_summary=False),
            "Top 7 | Gr son 6 | Yeni",
        )

    def test_recent_exports_count_line_matches_summary_only_copy(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_exports_count_line(total_audio_count=0, shown_count=0, has_summary=True),
            "Top 0 | Ozet",
        )

    def test_recent_exports_shown_count_limits_to_six(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(recorder.recent_exports_shown_count(7), 6)
        self.assertEqual(recorder.recent_exports_shown_count(2), 2)

    def test_recent_exports_hidden_count_returns_remaining_total(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(recorder.recent_exports_hidden_count(total_audio_count=7, shown_count=6), 1)
        self.assertEqual(recorder.recent_exports_hidden_count(total_audio_count=2, shown_count=2), 0)

    def test_recent_exports_status_context_without_summary(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        recorder.last_session_summary_path = None
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            (output_dir / "take.wav").write_text("audio", encoding="utf-8")
            (output_dir / "notes.txt").write_text("skip", encoding="utf-8")

            context = recorder.recent_exports_status_context(output_dir)

        self.assertEqual(context, {"total_audio_count": 1, "has_summary": False})

    def test_recent_exports_status_context_with_summary(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            summary_path = output_dir / "session_summary.json"
            summary_path.write_text("{}", encoding="utf-8")
            recorder.last_session_summary_path = summary_path

            context = recorder.recent_exports_status_context(output_dir)

        self.assertEqual(context, {"total_audio_count": 0, "has_summary": True})

    def test_recent_exports_action_status_inputs_extracts_count_and_summary_flag(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        output_dir = Path("/tmp/demo-output")
        recorder.recent_exports_status_context = mock.Mock(return_value={"total_audio_count": 2, "has_summary": True})

        inputs = recorder.recent_exports_action_status_inputs(output_dir)

        self.assertEqual(inputs, (2, True))
        recorder.recent_exports_status_context.assert_called_once_with(output_dir)

    def test_recent_exports_display_inputs_collects_summary_and_counts(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        output_dir = Path("/tmp/demo-output")
        recent_files = [Path("/tmp/demo-output/take.wav")]
        recorder.recent_session_summary_line = mock.Mock(return_value="- session_summary.json (Ozet)")
        recorder.list_recent_export_audio_files = mock.Mock(return_value=recent_files)
        recorder.limit_recent_export_audio_files = mock.Mock(return_value=recent_files)
        recorder.recent_exports_shown_count = mock.Mock(return_value=1)

        inputs = recorder.recent_exports_display_inputs(output_dir)

        self.assertEqual(
            inputs,
            {
                "summary_line": "- session_summary.json (Ozet)",
                "recent_files": recent_files,
                "total_audio_count": 1,
                "shown_count": 1,
            },
        )
        recorder.recent_session_summary_line.assert_called_once_with(output_dir)
        recorder.list_recent_export_audio_files.assert_called_once_with(output_dir)
        recorder.limit_recent_export_audio_files.assert_called_once_with(recent_files)
        recorder.recent_exports_shown_count.assert_called_once_with(1)

    def test_recent_exports_display_metrics_builds_count_line_and_hidden_count(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        recorder.recent_exports_count_line = mock.Mock(return_value="Top 7 | Gr son 6 | Yeni")
        recorder.recent_exports_hidden_count = mock.Mock(return_value=1)

        metrics = recorder.recent_exports_display_metrics(
            total_audio_count=7,
            shown_count=6,
            has_summary=False,
            has_recent_files=True,
        )

        self.assertEqual(metrics, ("Top 7 | Gr son 6 | Yeni", 1))
        recorder.recent_exports_count_line.assert_called_once_with(
            total_audio_count=7,
            shown_count=6,
            has_summary=False,
        )
        recorder.recent_exports_hidden_count.assert_called_once_with(
            total_audio_count=7,
            shown_count=6,
        )

    def test_recent_exports_display_input_payload_builds_render_dict(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        export_path = Path("/tmp/demo-output/take.wav")

        payload = recorder.recent_exports_display_input_payload(
            summary_line="- session_summary.json (Ozet)",
            recent_files=[export_path],
            total_audio_count=1,
            shown_count=1,
        )

        self.assertEqual(
            payload,
            {
                "summary_line": "- session_summary.json (Ozet)",
                "recent_files": [export_path],
                "total_audio_count": 1,
                "shown_count": 1,
            },
        )

    def test_recent_exports_display_input_counts_extracts_total_and_shown(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        export_path = Path("/tmp/demo-output/take.wav")
        recorder.recent_exports_shown_count = mock.Mock(return_value=1)

        counts = recorder.recent_exports_display_input_counts([export_path])

        self.assertEqual(counts, (1, 1))
        recorder.recent_exports_shown_count.assert_called_once_with(1)

    def test_recent_exports_display_input_files_collects_render_sources(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        output_dir = Path("/tmp/demo-output")
        export_path = output_dir / "take.wav"
        recorder.recent_session_summary_line = mock.Mock(return_value="- session_summary.json (Ozet)")
        recorder.list_recent_export_audio_files = mock.Mock(return_value=[export_path])
        recorder.limit_recent_export_audio_files = mock.Mock(return_value=[export_path])

        files = recorder.recent_exports_display_input_files(output_dir)

        self.assertEqual(files, ("- session_summary.json (Ozet)", [export_path], [export_path]))
        recorder.recent_session_summary_line.assert_called_once_with(output_dir)
        recorder.list_recent_export_audio_files.assert_called_once_with(output_dir)
        recorder.limit_recent_export_audio_files.assert_called_once_with([export_path])

    def test_recent_exports_display_input_components_collects_payload_values(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        output_dir = Path("/tmp/demo-output")
        export_path = output_dir / "take.wav"
        recorder.recent_exports_display_input_files = mock.Mock(
            return_value=("- session_summary.json (Ozet)", [export_path], [export_path])
        )
        recorder.recent_exports_display_input_counts = mock.Mock(return_value=(1, 1))

        components = recorder.recent_exports_display_input_components(output_dir)

        self.assertEqual(components, ("- session_summary.json (Ozet)", [export_path], 1, 1))
        recorder.recent_exports_display_input_files.assert_called_once_with(output_dir)
        recorder.recent_exports_display_input_counts.assert_called_once_with([export_path])

    def test_recent_exports_display_context_inputs_extracts_render_values(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        export_path = Path("/tmp/demo-output/take.wav")

        inputs = recorder.recent_exports_display_context_inputs(
            {
                "summary_line": "- session_summary.json (Ozet)",
                "recent_files": [export_path],
                "total_audio_count": 1,
                "shown_count": 1,
            }
        )

        self.assertEqual(
            inputs,
            ("- session_summary.json (Ozet)", [export_path], 1, 1),
        )

    def test_recent_exports_display_metric_flags_extracts_boolean_state(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        export_path = Path("/tmp/demo-output/take.wav")

        flags = recorder.recent_exports_display_metric_flags(
            summary_line="- session_summary.json (Ozet)",
            recent_files=[export_path],
        )

        self.assertEqual(flags, (True, True))

    def test_recent_exports_display_context_metrics_collects_metric_values(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        export_path = Path("/tmp/demo-output/take.wav")
        recorder.recent_exports_display_metric_flags = mock.Mock(return_value=(True, True))
        recorder.recent_exports_display_metrics = mock.Mock(return_value=("Top 1 | Gr 1 | Ozet", 0))

        metrics = recorder.recent_exports_display_context_metrics(
            summary_line="- session_summary.json (Ozet)",
            recent_files=[export_path],
            total_audio_count=1,
            shown_count=1,
        )

        self.assertEqual(metrics, ("Top 1 | Gr 1 | Ozet", 0))
        recorder.recent_exports_display_metric_flags.assert_called_once_with(
            "- session_summary.json (Ozet)",
            [export_path],
        )
        recorder.recent_exports_display_metrics.assert_called_once_with(
            total_audio_count=1,
            shown_count=1,
            has_summary=True,
            has_recent_files=True,
        )

    def test_recent_exports_display_context_source_collects_render_inputs(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        output_dir = Path("/tmp/demo-output")
        export_path = output_dir / "take.wav"
        recorder.recent_exports_display_inputs = mock.Mock(
            return_value={
                "summary_line": "- session_summary.json (Ozet)",
                "recent_files": [export_path],
                "total_audio_count": 1,
                "shown_count": 1,
            }
        )
        recorder.recent_exports_display_context_inputs = mock.Mock(
            return_value=("- session_summary.json (Ozet)", [export_path], 1, 1)
        )

        source = recorder.recent_exports_display_context_source(output_dir)

        self.assertEqual(source, ("- session_summary.json (Ozet)", [export_path], 1, 1))
        recorder.recent_exports_display_inputs.assert_called_once_with(output_dir)
        recorder.recent_exports_display_context_inputs.assert_called_once_with(
            {
                "summary_line": "- session_summary.json (Ozet)",
                "recent_files": [export_path],
                "total_audio_count": 1,
                "shown_count": 1,
            }
        )

    def test_recent_exports_display_context_components_collects_render_values(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        output_dir = Path("/tmp/demo-output")
        export_path = output_dir / "take.wav"
        recorder.recent_exports_display_context_source = mock.Mock(
            return_value=("- session_summary.json (Ozet)", [export_path], 1, 1)
        )
        recorder.recent_exports_display_context_metrics = mock.Mock(return_value=("Top 1 | Gr 1 | Ozet", 0))

        components = recorder.recent_exports_display_context_components(output_dir)

        self.assertEqual(components, ("- session_summary.json (Ozet)", [export_path], "Top 1 | Gr 1 | Ozet", 0))
        recorder.recent_exports_display_context_source.assert_called_once_with(output_dir)
        recorder.recent_exports_display_context_metrics.assert_called_once_with(
            summary_line="- session_summary.json (Ozet)",
            recent_files=[export_path],
            total_audio_count=1,
            shown_count=1,
        )

    def test_recent_exports_display_context_payload_builds_render_dict(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        export_path = Path("/tmp/demo-output/take.wav")

        payload = recorder.recent_exports_display_context_payload(
            summary_line="- session_summary.json (Ozet)",
            recent_files=[export_path],
            count_line="Top 1 | Gr 1",
            hidden_count=0,
        )

        self.assertEqual(
            payload,
            {
                "summary_line": "- session_summary.json (Ozet)",
                "recent_files": [export_path],
                "count_line": "Top 1 | Gr 1",
                "hidden_count": 0,
            },
        )

    def test_recent_exports_display_context_matches_summary_only_state(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            summary_path = output_dir / "session_summary.json"
            summary_path.write_text("{}", encoding="utf-8")
            recorder.last_session_summary_path = summary_path

            context = recorder.recent_exports_display_context(output_dir)

        self.assertEqual(context["summary_line"], "- session_summary.json (Ozet)")
        self.assertEqual(context["recent_files"], [])
        self.assertEqual(context["count_line"], "Top 0 | Ozet")
        self.assertEqual(context["hidden_count"], 0)

    def test_recent_exports_display_context_matches_audio_file_state(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            for index in range(7):
                path = output_dir / f"take_{index}.wav"
                path.write_text("audio", encoding="utf-8")
                os.utime(path, (time.time() + index, time.time() + index))
            recorder.last_session_summary_path = None

            context = recorder.recent_exports_display_context(output_dir)

        self.assertEqual(len(context["recent_files"]), 6)
        self.assertEqual(context["count_line"], "Top 7 | Gr son 6 | Yeni")
        self.assertEqual(context["hidden_count"], 1)

    def test_recent_exports_visibility_label_matches_truncated_list_copy(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_exports_visibility_label(total_audio_count=7, shown_count=6, has_summary=False),
            "Gr son 6",
        )

    def test_recent_exports_visibility_label_matches_summary_only_copy(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_exports_visibility_label(total_audio_count=0, shown_count=0, has_summary=True),
            "Ozet",
        )

    def test_recent_exports_visibility_label_is_empty_without_audio_or_summary(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_exports_visibility_label(total_audio_count=0, shown_count=0, has_summary=False),
            "",
        )

    def test_recent_exports_status_suffix_matches_multi_file_copy(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_exports_status_suffix(total_audio_count=2, shown_count=2),
            " Gr tumu. Yeni.",
        )

    def test_recent_exports_status_suffix_matches_single_file_copy(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_exports_status_suffix(total_audio_count=1, shown_count=1),
            " Gr 1.",
        )

    def test_recent_exports_status_visibility_suffix_matches_single_file_copy(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_exports_status_visibility_suffix(total_audio_count=1, shown_count=1),
            " Gr 1.",
        )

    def test_recent_exports_status_newest_suffix_matches_multi_file_copy(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(recorder.recent_exports_status_newest_suffix(2), " Yeni.")
        self.assertEqual(recorder.recent_exports_status_newest_suffix(1), "")

    def test_recent_exports_audio_status_summary_suffix_matches_summary_copy(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_exports_audio_status_summary_suffix(True),
            " Ozet hazir. Isterseniz acabilirsiniz.",
        )
        self.assertEqual(recorder.recent_exports_audio_status_summary_suffix(False), "")

    def test_recent_exports_audio_status_intro_matches_audio_count_copy(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_exports_audio_status_intro(2),
            "Durum guncel. 2 ses dosyasi.",
        )

    def test_recent_exports_audio_status_message_matches_multi_file_copy(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_exports_audio_status_message(total_audio_count=2, shown_count=2, has_summary=False),
            "Durum guncel. 2 ses dosyasi. Gr tumu. Yeni.",
        )

    def test_recent_exports_audio_status_message_matches_summary_copy(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_exports_audio_status_message(total_audio_count=1, shown_count=1, has_summary=True),
            "Durum guncel. 1 ses dosyasi. Gr 1. Ozet hazir. Isterseniz acabilirsiniz.",
        )

    def test_recent_exports_existing_dir_status_inputs_extracts_shown_count(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        recorder.recent_exports_shown_count = mock.Mock(return_value=2)

        inputs = recorder.recent_exports_existing_dir_status_inputs(total_audio_count=2, has_summary=True)

        self.assertEqual(inputs, (2, 2, True))
        recorder.recent_exports_shown_count.assert_called_once_with(2)

    def test_recent_exports_existing_dir_audio_status_message_uses_inputs(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        recorder.recent_exports_existing_dir_status_inputs = mock.Mock(return_value=(2, 2, True))
        recorder.recent_exports_audio_status_message = mock.Mock(
            return_value="Durum guncel. 2 ses dosyasi. Gr tumu. Yeni. Ozet hazir. Isterseniz acabilirsiniz."
        )

        status_message = recorder.recent_exports_existing_dir_audio_status_message(total_audio_count=2, has_summary=True)

        self.assertEqual(
            status_message,
            "Durum guncel. 2 ses dosyasi. Gr tumu. Yeni. Ozet hazir. Isterseniz acabilirsiniz.",
        )
        recorder.recent_exports_existing_dir_status_inputs.assert_called_once_with(
            total_audio_count=2,
            has_summary=True,
        )
        recorder.recent_exports_audio_status_message.assert_called_once_with(
            total_audio_count=2,
            shown_count=2,
            has_summary=True,
        )

    def test_recent_exports_existing_dir_empty_status_message_uses_empty_status_copy(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        recorder.recent_exports_empty_status_message = mock.Mock(
            return_value="Durum guncel. Ozet hazir. Isterseniz acabilirsiniz."
        )

        status_message = recorder.recent_exports_existing_dir_empty_status_message(has_summary=True)

        self.assertEqual(status_message, "Durum guncel. Ozet hazir. Isterseniz acabilirsiniz.")
        recorder.recent_exports_empty_status_message.assert_called_once_with(has_summary=True)

    def test_recent_exports_existing_dir_status_message_for_empty_dir(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_exports_existing_dir_status_message(total_audio_count=0, has_summary=False),
            "Durum guncel. Yeni kayitlar burada gosterilir.",
        )

    def test_recent_exports_existing_dir_status_message_for_summary_only_dir(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_exports_existing_dir_status_message(total_audio_count=0, has_summary=True),
            "Durum guncel. Ozet hazir. Isterseniz acabilirsiniz.",
        )

    def test_recent_exports_existing_dir_status_message_for_audio_files(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_exports_existing_dir_status_message(total_audio_count=2, has_summary=True),
            "Durum guncel. 2 ses dosyasi. Gr tumu. Yeni. Ozet hazir. Isterseniz acabilirsiniz.",
        )

    def test_recent_exports_missing_dir_status_message_uses_output_dir_text(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        missing_dir = Path("/tmp/does-not-exist-gar")
        recorder.recent_output_dir_text = mock.Mock(return_value="~/Missing")
        recorder.missing_output_dir_status = mock.Mock(
            return_value="Durum guncel. Cikis klasoru bulunamadi: ~/Missing. 'Klasoru Ac' ile yeniden olusturabilir ve Finder'da acabilirsiniz."
        )

        status_message = recorder.recent_exports_missing_dir_status_message(missing_dir)

        self.assertEqual(
            status_message,
            "Durum guncel. Cikis klasoru bulunamadi: ~/Missing. 'Klasoru Ac' ile yeniden olusturabilir ve Finder'da acabilirsiniz.",
        )
        recorder.recent_output_dir_text.assert_called_once_with(missing_dir)
        recorder.missing_output_dir_status.assert_called_once_with("~/Missing")

    def test_recent_exports_action_status_for_existing_dir_uses_existing_dir_copy(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        recorder.recent_exports_existing_dir_status_message = mock.Mock(
            return_value="Durum guncel. 2 ses dosyasi. Gr tumu. Yeni. Ozet hazir. Isterseniz acabilirsiniz."
        )

        status_message = recorder.recent_exports_action_status_for_existing_dir(
            total_audio_count=2,
            has_summary=True,
        )

        self.assertEqual(
            status_message,
            "Durum guncel. 2 ses dosyasi. Gr tumu. Yeni. Ozet hazir. Isterseniz acabilirsiniz.",
        )
        recorder.recent_exports_existing_dir_status_message.assert_called_once_with(
            total_audio_count=2,
            has_summary=True,
        )

    def test_recent_exports_action_status_for_missing_dir_uses_missing_dir_copy(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        missing_dir = Path("/tmp/does-not-exist-gar")
        recorder.recent_exports_missing_dir_status_message = mock.Mock(
            return_value="Durum guncel. Cikis klasoru bulunamadi: ~/Missing. 'Klasoru Ac' ile yeniden olusturabilir ve Finder'da acabilirsiniz."
        )

        status_message = recorder.recent_exports_action_status_for_missing_dir(missing_dir)

        self.assertEqual(
            status_message,
            "Durum guncel. Cikis klasoru bulunamadi: ~/Missing. 'Klasoru Ac' ile yeniden olusturabilir ve Finder'da acabilirsiniz.",
        )
        recorder.recent_exports_missing_dir_status_message.assert_called_once_with(missing_dir)

    def test_recent_exports_action_status_has_output_dir_checks_path(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            self.assertTrue(recorder.recent_exports_action_status_has_output_dir(output_dir))

        self.assertFalse(recorder.recent_exports_action_status_has_output_dir(output_dir))

    def test_recent_exports_action_status_message_for_missing_dir(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        missing_dir = Path("/tmp/does-not-exist-gar")
        recorder.recent_output_dir_text = mock.Mock(return_value="~/Missing")

        self.assertEqual(
            recorder.recent_exports_action_status_message(
                output_dir=missing_dir,
                total_audio_count=0,
                has_summary=False,
            ),
            "Durum guncel. Cikis klasoru bulunamadi: ~/Missing. 'Klasoru Ac' ile yeniden olusturabilir ve Finder'da acabilirsiniz.",
        )
        recorder.recent_output_dir_text.assert_called_once_with(missing_dir)

    def test_recent_exports_action_status_message_for_empty_dir(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            recorder.format_display_path = mock.Mock(return_value="~/Demo")

            self.assertEqual(
                recorder.recent_exports_action_status_message(
                    output_dir=output_dir,
                    total_audio_count=0,
                    has_summary=False,
                ),
                "Durum guncel. Yeni kayitlar burada gosterilir.",
            )

    def test_recent_exports_action_status_message_for_audio_files(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            recorder.format_display_path = mock.Mock(return_value="~/Demo")

            self.assertEqual(
                recorder.recent_exports_action_status_message(
                    output_dir=output_dir,
                    total_audio_count=2,
                    has_summary=True,
                ),
                "Durum guncel. 2 ses dosyasi. Gr tumu. Yeni. Ozet hazir. Isterseniz acabilirsiniz.",
            )

    def test_recent_exports_action_status_input_values_extracts_context_values(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        values = recorder.recent_exports_action_status_input_values(
            {
                "total_audio_count": 2,
                "has_summary": True,
            }
        )

        self.assertEqual(values, (2, True))

    def test_recent_exports_refresh_status_message_for_missing_dir(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        missing_dir = Path("/tmp/does-not-exist-gar")
        recorder.last_session_summary_path = None
        recorder.format_display_path = mock.Mock(return_value="~/Missing")

        self.assertEqual(
            recorder.recent_exports_refresh_status_message(missing_dir),
            "Durum guncel. Cikis klasoru bulunamadi: ~/Missing. 'Klasoru Ac' ile yeniden olusturabilir ve Finder'da acabilirsiniz.",
        )

    def test_recent_exports_refresh_status_message_for_audio_files(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        recorder.last_session_summary_path = None
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            (output_dir / "take.wav").write_text("audio", encoding="utf-8")
            self.assertEqual(
                recorder.recent_exports_refresh_status_message(output_dir),
                "Durum guncel. 1 ses dosyasi. Gr 1.",
            )

    def test_recent_exports_refresh_status_from_inputs_uses_action_status_message(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        output_dir = Path("/tmp/demo-output")
        recorder.recent_exports_action_status_message = mock.Mock(return_value="Durum guncel. Test.")

        status_message = recorder.recent_exports_refresh_status_from_inputs(
            output_dir=output_dir,
            total_audio_count=1,
            has_summary=False,
        )

        self.assertEqual(status_message, "Durum guncel. Test.")
        recorder.recent_exports_action_status_message.assert_called_once_with(
            output_dir=output_dir,
            total_audio_count=1,
            has_summary=False,
        )

    def test_set_recent_exports_refresh_status_message_uses_set_status(self) -> None:
        recorder = self.make_app()

        recorder.set_recent_exports_refresh_status_message("Durum guncel. Test.")

        self.assertEqual(recorder.status_messages[-1], "Durum guncel. Test.")

    def test_set_recent_exports_refresh_status_uses_refresh_status_message(self) -> None:
        recorder = self.make_app()
        output_dir = Path("/tmp/demo-output")
        recorder.recent_exports_refresh_status_message = mock.Mock(return_value="Durum guncel. Test.")

        recorder.set_recent_exports_refresh_status(output_dir)

        recorder.recent_exports_refresh_status_message.assert_called_once_with(output_dir)
        self.assertEqual(recorder.status_messages[-1], "Durum guncel. Test.")

    def test_recent_export_line_marks_latest_export(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_export_line("take_001.wav", is_latest=True),
            "- take_001.wav (Export)",
        )

    def test_recent_export_label_matches_export_copy(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(recorder.recent_export_label(), "Export")

    def test_recent_export_line_label_matches_latest_copy(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(recorder.recent_export_line_label(True), "Export")

    def test_recent_export_has_label_detects_latest_item(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertTrue(recorder.recent_export_has_label(True))

    def test_recent_export_line_text_formats_latest_copy(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_export_line_text("take_001.wav", True),
            "- take_001.wav (Export)",
        )

    def test_recent_output_line_prefix_matches_list_copy(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(recorder.recent_output_line_prefix(), "- ")

    def test_recent_output_has_label_detects_non_empty_label(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertTrue(recorder.recent_output_has_label("Ozet"))

    def test_recent_output_label_suffix_wraps_label_copy(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(recorder.recent_output_label_suffix("Ozet"), " (Ozet)")

    def test_recent_output_line_content_formats_filename_copy(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(recorder.recent_output_line_content("take_001.wav"), "- take_001.wav")

    def test_recent_output_line_without_label(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_output_line("take_001.wav"),
            "- take_001.wav",
        )

    def test_recent_output_line_with_label(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_output_line("session_summary.json", label="Ozet"),
            "- session_summary.json (Ozet)",
        )

    def test_recent_summary_line_marks_summary_item(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_summary_line("session_summary.json"),
            "- session_summary.json (Ozet)",
        )

    def test_recent_summary_label_matches_summary_copy(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(recorder.recent_summary_label(), "Ozet")

    def test_recent_summary_has_label_defaults_true(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertTrue(recorder.recent_summary_has_label())

    def test_recent_summary_line_label_matches_summary_copy(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(recorder.recent_summary_line_label(), "Ozet")

    def test_recent_summary_line_text_formats_summary_copy(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_summary_line_text("session_summary.json"),
            "- session_summary.json (Ozet)",
        )

    def test_recent_exports_header_line_formats_folder_label(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_exports_header_line("~/Demo"),
            "Klasor ~/Demo",
        )

    def test_recent_exports_header_label_matches_folder_copy(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(recorder.recent_exports_header_label(), "Klasor")

    def test_recent_exports_header_separator_matches_copy_spacing(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(recorder.recent_exports_header_separator(), " ")

    def test_recent_exports_header_content_formats_folder_copy(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(recorder.recent_exports_header_content("~/Demo"), "Klasor ~/Demo")

    def test_recent_hidden_count_content_formats_numeric_copy(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(recorder.recent_hidden_count_content(2), "2")

    def test_recent_hidden_count_text_formats_full_copy(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(recorder.recent_hidden_count_text(2), "+2")

    def test_recent_hidden_count_line_formats_hidden_total(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_hidden_count_line(2),
            "+2",
        )

    def test_recent_hidden_count_prefix_matches_hidden_count_copy(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(recorder.recent_hidden_count_prefix(), "+")

    def test_recent_exports_intro_lines_formats_shared_intro(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_exports_intro_lines("~/Demo", "Top 2 | Gr son 2"),
            ["Klasor ~/Demo", "Top 2 | Gr son 2"],
        )

    def test_recent_exports_empty_summary_lines_formats_summary_block(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_exports_empty_summary_lines("- session_summary.json (Ozet)"),
            [
                "Henuz ses kaydi yok. Alttaki ozeti acabilirsiniz.",
                "- session_summary.json (Ozet)",
            ],
        )

    def test_recent_exports_empty_message_lines_formats_empty_block(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_exports_empty_message_lines(),
            ["Henuz ses kaydi yok. Yeni kayitlar burada gosterilir."],
        )

    def test_recent_exports_empty_lines_with_summary_formats_summary_block(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_exports_empty_lines_with_summary("- session_summary.json (Ozet)"),
            [
                "Henuz ses kaydi yok. Alttaki ozeti acabilirsiniz.",
                "- session_summary.json (Ozet)",
            ],
        )

    def test_recent_exports_empty_lines_without_summary_formats_empty_block(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_exports_empty_lines_without_summary(),
            ["Henuz ses kaydi yok. Yeni kayitlar burada gosterilir."],
        )

    def test_recent_exports_has_optional_line_detects_non_empty_line(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertTrue(recorder.recent_exports_has_optional_line("- session_summary.json (Ozet)"))

    def test_recent_exports_has_count_detects_non_zero_count(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertTrue(recorder.recent_exports_has_count(1))

    def test_recent_exports_has_summary_line_detects_non_empty_summary(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertTrue(recorder.recent_exports_has_summary_line("- session_summary.json (Ozet)"))

    def test_recent_exports_content_lines_with_intro_combines_intro_and_content(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_exports_content_lines_with_intro(
                output_dir_text="~/Demo",
                count_line="Top 2 | Gr son 2",
                content_lines=["- take_002.mp3 (Export)", "+1"],
            ),
            [
                "Klasor ~/Demo",
                "Top 2 | Gr son 2",
                "- take_002.mp3 (Export)",
                "+1",
            ],
        )

    def test_recent_exports_empty_body_lines_uses_summary_block_when_present(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_exports_empty_body_lines("- session_summary.json (Ozet)"),
            [
                "Henuz ses kaydi yok. Alttaki ozeti acabilirsiniz.",
                "- session_summary.json (Ozet)",
            ],
        )

    def test_recent_exports_empty_content_lines_combines_intro_and_body(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_exports_empty_content_lines(
                output_dir_text="~/Demo",
                count_line="Top 0 | Ozet",
                summary_line="- session_summary.json (Ozet)",
            ),
            [
                "Klasor ~/Demo",
                "Top 0 | Ozet",
                "Henuz ses kaydi yok. Alttaki ozeti acabilirsiniz.",
                "- session_summary.json (Ozet)",
            ],
        )

    def test_build_recent_exports_empty_lines_with_summary(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.build_recent_exports_empty_lines(
                output_dir_text="~/Demo",
                count_line="Top 0 | Ozet",
                summary_line="- session_summary.json (Ozet)",
            ),
            [
                "Klasor ~/Demo",
                "Top 0 | Ozet",
                "Henuz ses kaydi yok. Alttaki ozeti acabilirsiniz.",
                "- session_summary.json (Ozet)",
            ],
        )

    def test_recent_exports_has_hidden_count_detects_extra_files(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertTrue(recorder.recent_exports_has_hidden_count(1))

    def test_recent_exports_has_file_summary_line_detects_summary(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertTrue(recorder.recent_exports_has_file_summary_line("- session_summary.json (Ozet)"))

    def test_recent_exports_file_tail_hidden_line_formats_hidden_count(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(recorder.recent_exports_file_tail_hidden_line(1), "+1")

    def test_recent_exports_file_tail_hidden_lines_wrap_hidden_count(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_exports_file_tail_hidden_lines(1),
            ["+1"],
        )

    def test_recent_exports_file_tail_hidden_lines_if_present_skips_zero_count(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_exports_file_tail_hidden_lines_if_present(0),
            [],
        )

    def test_recent_exports_file_tail_summary_line_returns_summary(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_exports_file_tail_summary_line("- session_summary.json (Ozet)"),
            "- session_summary.json (Ozet)",
        )

    def test_recent_exports_file_tail_summary_lines_wrap_summary(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_exports_file_tail_summary_lines("- session_summary.json (Ozet)"),
            ["- session_summary.json (Ozet)"],
        )

    def test_recent_exports_file_tail_summary_lines_if_present_skips_empty_summary(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_exports_file_tail_summary_lines_if_present(""),
            [],
        )

    def test_recent_exports_file_tail_optional_lines_combines_hidden_and_summary(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_exports_file_tail_optional_lines(1, "- session_summary.json (Ozet)"),
            ["+1", "- session_summary.json (Ozet)"],
        )

    def test_recent_exports_file_tail_lines_formats_hidden_count_and_summary(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_exports_file_tail_lines(1, "- session_summary.json (Ozet)"),
            ["+1", "- session_summary.json (Ozet)"],
        )

    def test_recent_exports_file_body_is_latest_detects_first_item(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertTrue(recorder.recent_exports_file_body_is_latest(0))

    def test_recent_exports_file_body_filename_extracts_name(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_exports_file_body_filename(Path("/tmp/demo/take_002.mp3")),
            "take_002.mp3",
        )

    def test_recent_exports_file_body_line_formats_latest_item(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_exports_file_body_line(Path("take_002.mp3"), 0),
            "- take_002.mp3 (Export)",
        )

    def test_recent_exports_file_body_lines_if_present_skips_empty_files(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_exports_file_body_lines_if_present([]),
            [],
        )

    def test_recent_exports_file_body_lines_formats_recent_files(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        recent_files = [Path("take_002.mp3"), Path("take_001.wav")]

        self.assertEqual(
            recorder.recent_exports_file_body_lines(recent_files),
            ["- take_002.mp3 (Export)", "- take_001.wav"],
        )

    def test_recent_exports_file_content_lines_combines_body_and_tail(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        recent_files = [Path("take_002.mp3"), Path("take_001.wav")]

        self.assertEqual(
            recorder.recent_exports_file_content_lines(
                recent_files,
                hidden_count=1,
                summary_line="- session_summary.json (Ozet)",
            ),
            [
                "- take_002.mp3 (Export)",
                "- take_001.wav",
                "+1",
                "- session_summary.json (Ozet)",
            ],
        )

    def test_build_recent_exports_file_lines_with_hidden_count(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        recent_files = [Path("take_002.mp3"), Path("take_001.wav")]

        self.assertEqual(
            recorder.build_recent_exports_file_lines(
                output_dir_text="~/Demo",
                count_line="Top 3 | Gr son 6 | Yeni",
                recent_files=recent_files,
                hidden_count=1,
                summary_line="- session_summary.json (Ozet)",
            ),
            [
                "Klasor ~/Demo",
                "Top 3 | Gr son 6 | Yeni",
                "- take_002.mp3 (Export)",
                "- take_001.wav",
                "+1",
                "- session_summary.json (Ozet)",
            ],
        )

    def test_recent_exports_file_count_counts_recent_files(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(recorder.recent_exports_file_count([Path("take_001.wav")]), 1)

    def test_recent_exports_has_files_detects_non_empty_recent_files(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertTrue(recorder.recent_exports_has_files([Path("take_001.wav")]))

    def test_recent_exports_lines_without_files_uses_empty_builder(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_exports_lines_without_files(
                output_dir_text="~/Demo",
                count_line="Top 0 | Ozet",
                summary_line="- session_summary.json (Ozet)",
            ),
            [
                "Klasor ~/Demo",
                "Top 0 | Ozet",
                "Henuz ses kaydi yok. Alttaki ozeti acabilirsiniz.",
                "- session_summary.json (Ozet)",
            ],
        )

    def test_recent_exports_lines_with_files_uses_file_builder(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_exports_lines_with_files(
                output_dir_text="~/Demo",
                count_line="Top 3 | Gr son 6 | Yeni",
                recent_files=[Path("take_002.mp3"), Path("take_001.wav")],
                hidden_count=1,
                summary_line="- session_summary.json (Ozet)",
            ),
            [
                "Klasor ~/Demo",
                "Top 3 | Gr son 6 | Yeni",
                "- take_002.mp3 (Export)",
                "- take_001.wav",
                "+1",
                "- session_summary.json (Ozet)",
            ],
        )

    def test_recent_exports_content_lines_for_files_presence_uses_file_branch(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_exports_content_lines_for_files_presence(
                has_files=True,
                output_dir_text="~/Demo",
                count_line="Top 3 | Gr son 6 | Yeni",
                recent_files=[Path("take_002.mp3"), Path("take_001.wav")],
                hidden_count=1,
                summary_line="- session_summary.json (Ozet)",
            ),
            [
                "Klasor ~/Demo",
                "Top 3 | Gr son 6 | Yeni",
                "- take_002.mp3 (Export)",
                "- take_001.wav",
                "+1",
                "- session_summary.json (Ozet)",
            ],
        )

    def test_build_recent_exports_lines_uses_empty_builder_when_no_files(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.build_recent_exports_lines(
                output_dir_text="~/Demo",
                count_line="Top 0 | Ozet",
                recent_files=[],
                hidden_count=0,
                summary_line="- session_summary.json (Ozet)",
            ),
            [
                "Klasor ~/Demo",
                "Top 0 | Ozet",
                "Henuz ses kaydi yok. Alttaki ozeti acabilirsiniz.",
                "- session_summary.json (Ozet)",
            ],
        )

    def test_build_recent_exports_lines_uses_file_builder_when_files_exist(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        recent_files = [Path("take_002.mp3"), Path("take_001.wav")]

        self.assertEqual(
            recorder.build_recent_exports_lines(
                output_dir_text="~/Demo",
                count_line="Top 3 | Gr son 6 | Yeni",
                recent_files=recent_files,
                hidden_count=1,
                summary_line="- session_summary.json (Ozet)",
            ),
            [
                "Klasor ~/Demo",
                "Top 3 | Gr son 6 | Yeni",
                "- take_002.mp3 (Export)",
                "- take_001.wav",
                "+1",
                "- session_summary.json (Ozet)",
            ],
        )

    def test_recent_exports_text_content_lines_uses_line_builder(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        recent_files = [Path("take_002.mp3"), Path("take_001.wav")]

        self.assertEqual(
            recorder.recent_exports_text_content_lines(
                output_dir_text="~/Demo",
                count_line="Top 3 | Gr son 6 | Yeni",
                recent_files=recent_files,
                hidden_count=1,
                summary_line="- session_summary.json (Ozet)",
            ),
            [
                "Klasor ~/Demo",
                "Top 3 | Gr son 6 | Yeni",
                "- take_002.mp3 (Export)",
                "- take_001.wav",
                "+1",
                "- session_summary.json (Ozet)",
            ],
        )

    def test_recent_exports_text_lines_uses_line_builder(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        recent_files = [Path("take_002.mp3"), Path("take_001.wav")]

        self.assertEqual(
            recorder.recent_exports_text_lines(
                output_dir_text="~/Demo",
                count_line="Top 3 | Gr son 6 | Yeni",
                recent_files=recent_files,
                hidden_count=1,
                summary_line="- session_summary.json (Ozet)",
            ),
            [
                "Klasor ~/Demo",
                "Top 3 | Gr son 6 | Yeni",
                "- take_002.mp3 (Export)",
                "- take_001.wav",
                "+1",
                "- session_summary.json (Ozet)",
            ],
        )

    def test_recent_exports_render_lines_uses_text_lines(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        recent_files = [Path("take_002.mp3"), Path("take_001.wav")]

        self.assertEqual(
            recorder.recent_exports_render_lines(
                output_dir_text="~/Demo",
                count_line="Top 3 | Gr son 6 | Yeni",
                recent_files=recent_files,
                hidden_count=1,
                summary_line="- session_summary.json (Ozet)",
            ),
            [
                "Klasor ~/Demo",
                "Top 3 | Gr son 6 | Yeni",
                "- take_002.mp3 (Export)",
                "- take_001.wav",
                "+1",
                "- session_summary.json (Ozet)",
            ],
        )

    def test_recent_exports_text_separator_matches_line_break_copy(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(recorder.recent_exports_text_separator(), "\n")

    def test_recent_exports_text_content_joins_lines(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_exports_text_content(["Klasor ~/Demo", "Top 2 | Gr son 2"]),
            "Klasor ~/Demo\nTop 2 | Gr son 2",
        )

    def test_recent_exports_render_content_joins_render_lines(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        recent_files = [Path("take_002.mp3"), Path("take_001.wav")]

        self.assertEqual(
            recorder.recent_exports_render_content(
                output_dir_text="~/Demo",
                count_line="Top 3 | Gr son 6 | Yeni",
                recent_files=recent_files,
                hidden_count=1,
                summary_line="- session_summary.json (Ozet)",
            ),
            "Klasor ~/Demo\nTop 3 | Gr son 6 | Yeni\n- take_002.mp3 (Export)\n- take_001.wav\n+1\n- session_summary.json (Ozet)",
        )

    def test_render_recent_exports_text_joins_empty_lines(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.render_recent_exports_text(
                output_dir_text="~/Demo",
                count_line="Top 0 | Ozet",
                recent_files=[],
                hidden_count=0,
                summary_line="- session_summary.json (Ozet)",
            ),
            "Klasor ~/Demo\nTop 0 | Ozet\nHenuz ses kaydi yok. Alttaki ozeti acabilirsiniz.\n- session_summary.json (Ozet)",
        )

    def test_render_recent_exports_text_joins_file_lines(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        recent_files = [Path("take_002.mp3"), Path("take_001.wav")]

        self.assertEqual(
            recorder.render_recent_exports_text(
                output_dir_text="~/Demo",
                count_line="Top 3 | Gr son 6 | Yeni",
                recent_files=recent_files,
                hidden_count=1,
                summary_line="- session_summary.json (Ozet)",
            ),
                "Klasor ~/Demo\nTop 3 | Gr son 6 | Yeni\n- take_002.mp3 (Export)\n- take_001.wav\n+1\n- session_summary.json (Ozet)",
        )

    def test_recent_exports_view_content_uses_rendered_copy(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_exports_view_content(
                output_dir_text="~/Demo",
                count_line="Top 0 | Ozet",
                recent_files=[],
                hidden_count=0,
                summary_line="- session_summary.json (Ozet)",
            ),
            "Klasor ~/Demo\nTop 0 | Ozet\nHenuz ses kaydi yok. Alttaki ozeti acabilirsiniz.\n- session_summary.json (Ozet)",
        )

    def test_recent_exports_view_text_uses_rendered_copy(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_exports_view_text(
                output_dir_text="~/Demo",
                count_line="Top 0 | Ozet",
                recent_files=[],
                hidden_count=0,
                summary_line="- session_summary.json (Ozet)",
            ),
            "Klasor ~/Demo\nTop 0 | Ozet\nHenuz ses kaydi yok. Alttaki ozeti acabilirsiniz.\n- session_summary.json (Ozet)",
        )

    def test_recent_exports_shown_text_uses_view_copy(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_exports_shown_text(
                output_dir_text="~/Demo",
                count_line="Top 0 | Ozet",
                recent_files=[],
                hidden_count=0,
                summary_line="- session_summary.json (Ozet)",
            ),
            "Klasor ~/Demo\nTop 0 | Ozet\nHenuz ses kaydi yok. Alttaki ozeti acabilirsiniz.\n- session_summary.json (Ozet)",
        )

    def test_set_shown_recent_exports_view_sets_text_and_refreshes_buttons(self) -> None:
        recorder = self.make_app()

        recorder.set_shown_recent_exports_view(
            output_dir_text="~/Demo",
            count_line="Top 0 | Ozet",
            recent_files=[],
            hidden_count=0,
            summary_line="- session_summary.json (Ozet)",
        )

        self.assertEqual(
            recorder.recent_exports_text.get(),
            "Klasor ~/Demo\nTop 0 | Ozet\nHenuz ses kaydi yok. Alttaki ozeti acabilirsiniz.\n- session_summary.json (Ozet)",
        )
        self.assertEqual(recorder.open_last_export_button.config_calls[-1], {"state": "disabled"})
        self.assertEqual(recorder.open_last_summary_button.config_calls[-1], {"state": "disabled"})

    def test_show_recent_exports_sets_text_and_disables_buttons_without_paths(self) -> None:
        recorder = self.make_app()

        recorder.show_recent_exports(
            output_dir_text="~/Demo",
            count_line="Top 0 | Ozet",
            recent_files=[],
            hidden_count=0,
            summary_line="- session_summary.json (Ozet)",
        )

        self.assertEqual(
            recorder.recent_exports_text.get(),
            "Klasor ~/Demo\nTop 0 | Ozet\nHenuz ses kaydi yok. Alttaki ozeti acabilirsiniz.\n- session_summary.json (Ozet)",
        )
        self.assertEqual(recorder.open_last_export_button.config_calls[-1], {"state": "disabled"})
        self.assertEqual(recorder.open_last_summary_button.config_calls[-1], {"state": "disabled"})

    def test_update_recent_exports_text_sets_text(self) -> None:
        recorder = self.make_app()

        recorder.update_recent_exports_text("Demo metni")

        self.assertEqual(recorder.recent_exports_text.get(), "Demo metni")

    def test_refresh_recent_exports_view_buttons_refreshes_button_states(self) -> None:
        recorder = self.make_app()

        recorder.refresh_recent_exports_view_buttons()

        self.assertEqual(recorder.open_last_export_button.config_calls[-1], {"state": "disabled"})
        self.assertEqual(recorder.open_last_summary_button.config_calls[-1], {"state": "disabled"})

    def test_apply_recent_exports_view_updates_sets_text_and_refreshes_buttons(self) -> None:
        recorder = self.make_app()

        recorder.apply_recent_exports_view_updates("Demo metni")

        self.assertEqual(recorder.recent_exports_text.get(), "Demo metni")
        self.assertEqual(recorder.open_last_export_button.config_calls[-1], {"state": "disabled"})
        self.assertEqual(recorder.open_last_summary_button.config_calls[-1], {"state": "disabled"})

    def test_set_recent_exports_view_sets_text_and_refreshes_buttons(self) -> None:
        recorder = self.make_app()

        recorder.set_recent_exports_view("Demo metni")

        self.assertEqual(recorder.recent_exports_text.get(), "Demo metni")
        self.assertEqual(recorder.open_last_export_button.config_calls[-1], {"state": "disabled"})
        self.assertEqual(recorder.open_last_summary_button.config_calls[-1], {"state": "disabled"})

    def test_show_recent_exports_refreshes_buttons_with_existing_paths(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "take.wav"
            summary_path = Path(tmpdir) / "session_summary.json"
            export_path.write_text("audio", encoding="utf-8")
            summary_path.write_text("{}", encoding="utf-8")
            recorder.last_export_path = export_path
            recorder.last_session_summary_path = summary_path

            recorder.show_recent_exports(
                output_dir_text="~/Demo",
                count_line="Top 1 | Gr 1",
                recent_files=[export_path],
                hidden_count=0,
                summary_line="- session_summary.json (Ozet)",
            )

        self.assertEqual(recorder.open_last_export_button.config_calls[-1], {"state": "normal"})
        self.assertEqual(recorder.open_last_summary_button.config_calls[-1], {"state": "normal"})

    def test_sync_last_export_from_recent_files_clears_path_when_empty(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            export_path = output_dir / "take.wav"
            export_path.write_text("audio", encoding="utf-8")
            recorder.last_export_path = export_path

            recorder.sync_last_export_from_recent_files(output_dir, [])

        self.assertIsNone(recorder.last_export_path)

    def test_sync_last_export_from_recent_files_refreshes_newest_path(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            newest_path = output_dir / "take.wav"
            newest_path.write_text("audio", encoding="utf-8")

            recorder.sync_last_export_from_recent_files(output_dir, [newest_path])

        self.assertEqual(recorder.last_export_path, newest_path)

    def test_recent_exports_context_view_inputs_extracts_render_values(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        export_path = Path("/tmp/demo-output/take.wav")
        inputs = recorder.recent_exports_context_view_inputs(
            {
                "summary_line": "- session_summary.json (Ozet)",
                "recent_files": [export_path],
                "count_line": "Top 1 | Gr 1",
                "hidden_count": 0,
            }
        )

        self.assertEqual(
            inputs,
            ("- session_summary.json (Ozet)", [export_path], "Top 1 | Gr 1", 0),
        )

    def test_recent_exports_context_view_source_collects_render_values(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        export_path = Path("/tmp/demo-output/take.wav")
        display_context = {
            "summary_line": "- session_summary.json (Ozet)",
            "recent_files": [export_path],
            "count_line": "Top 1 | Gr 1",
            "hidden_count": 0,
        }
        recorder.recent_exports_context_view_inputs = mock.Mock(
            return_value=("- session_summary.json (Ozet)", [export_path], "Top 1 | Gr 1", 0)
        )

        source = recorder.recent_exports_context_view_source(display_context)

        self.assertEqual(source, ("- session_summary.json (Ozet)", [export_path], "Top 1 | Gr 1", 0))
        recorder.recent_exports_context_view_inputs.assert_called_once_with(display_context)

    def test_recent_exports_context_view_render_args_builds_show_args(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        export_path = Path("/tmp/demo-output/take.wav")

        render_args = recorder.recent_exports_context_view_render_args(
            output_dir_text="~/Demo",
            count_line="Top 1 | Gr 1",
            recent_files=[export_path],
            hidden_count=0,
            summary_line="- session_summary.json (Ozet)",
        )

        self.assertEqual(
            render_args,
            {
                "output_dir_text": "~/Demo",
                "count_line": "Top 1 | Gr 1",
                "recent_files": [export_path],
                "hidden_count": 0,
                "summary_line": "- session_summary.json (Ozet)",
            },
        )

    def test_show_recent_exports_context_view_applies_render_values(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        output_dir = Path("/tmp/demo-output")
        export_path = output_dir / "take.wav"
        recorder.sync_last_export_from_recent_files = mock.Mock()
        recorder.show_recent_exports = mock.Mock()

        recorder.show_recent_exports_context_view(
            output_dir=output_dir,
            output_dir_text="~/Demo",
            summary_line="- session_summary.json (Ozet)",
            recent_files=[export_path],
            count_line="Top 1 | Gr 1",
            hidden_count=0,
        )

        recorder.sync_last_export_from_recent_files.assert_called_once_with(output_dir, [export_path])
        recorder.show_recent_exports.assert_called_once_with(
            output_dir_text="~/Demo",
            count_line="Top 1 | Gr 1",
            recent_files=[export_path],
            hidden_count=0,
            summary_line="- session_summary.json (Ozet)",
        )

    def test_recent_exports_primary_file_returns_first_recent_file(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        first_path = Path("/tmp/demo-output/take_1.wav")
        second_path = Path("/tmp/demo-output/take_2.wav")

        primary = recorder.recent_exports_primary_file([first_path, second_path])

        self.assertEqual(primary, first_path)

    def test_clear_last_export_path_resets_last_export(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        recorder.last_export_path = Path("/tmp/demo-output/take.wav")

        recorder.clear_last_export_path()

        self.assertIsNone(recorder.last_export_path)

    def test_refresh_last_export_from_recent_files_uses_primary_file(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        output_dir = Path("/tmp/demo-output")
        first_path = output_dir / "take_1.wav"
        second_path = output_dir / "take_2.wav"
        recorder.recent_exports_primary_file = mock.Mock(return_value=first_path)
        recorder.refresh_last_export_path = mock.Mock()

        recorder.refresh_last_export_from_recent_files(output_dir, [first_path, second_path])

        recorder.recent_exports_primary_file.assert_called_once_with([first_path, second_path])
        recorder.refresh_last_export_path.assert_called_once_with(output_dir, first_path)

    def test_show_recent_exports_from_context_clears_last_export_when_empty(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            export_path = output_dir / "take.wav"
            export_path.write_text("audio", encoding="utf-8")
            recorder.last_export_path = export_path

            recorder.show_recent_exports_from_context(
                output_dir=output_dir,
                output_dir_text="~/Demo",
                display_context={
                    "summary_line": "",
                    "recent_files": [],
                    "count_line": "Top 0",
                    "hidden_count": 0,
                },
            )

        self.assertIsNone(recorder.last_export_path)
        self.assertEqual(
            recorder.recent_exports_text.get(),
            "Klasor ~/Demo\nTop 0\nHenuz ses kaydi yok. Yeni kayitlar burada gosterilir.",
        )

    def test_show_recent_exports_from_context_refreshes_last_export_for_files(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            newest_path = output_dir / "take.wav"
            newest_path.write_text("audio", encoding="utf-8")

            recorder.show_recent_exports_from_context(
                output_dir=output_dir,
                output_dir_text="~/Demo",
                display_context={
                    "summary_line": "",
                    "recent_files": [newest_path],
                    "count_line": "Top 1 | Gr 1",
                    "hidden_count": 0,
                },
            )

        self.assertEqual(recorder.last_export_path, newest_path)
        self.assertEqual(
            recorder.recent_exports_text.get(),
            "Klasor ~/Demo\nTop 1 | Gr 1\n- take.wav (Export)",
        )

    def test_refresh_recent_exports_uses_existing_dir_helper(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        recorder.refresh_recent_exports_for_current_output_dir = mock.Mock()

        recorder.refresh_recent_exports()

        recorder.refresh_recent_exports_for_current_output_dir.assert_called_once_with()

    def test_refresh_recent_exports_from_action_uses_current_output_dir_action_helper(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        recorder.refresh_recent_exports_from_action_for_current_output_dir = mock.Mock()

        recorder.refresh_recent_exports_from_action()

        recorder.refresh_recent_exports_from_action_for_current_output_dir.assert_called_once_with()

    def test_refresh_recent_exports_from_action_for_current_output_dir_reuses_resolved_dir(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        output_dir = Path("/tmp/current-session-folder")
        recorder.current_recent_output_dir = mock.Mock(return_value=output_dir)
        recorder.refresh_recent_exports_from_action_for_resolved_output_dir = mock.Mock(return_value=output_dir)

        resolved_output_dir = recorder.refresh_recent_exports_from_action_for_current_output_dir()

        self.assertEqual(resolved_output_dir, output_dir)
        recorder.current_recent_output_dir.assert_called_once_with()
        recorder.refresh_recent_exports_from_action_for_resolved_output_dir.assert_called_once_with(output_dir)

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
            recorder.format_display_path = mock.Mock(return_value="~/Demo")
            recorder.refresh_recent_exports()
            expected = ["Klasor ~/Demo", "Top 7 | Gr son 6 | Yeni"]
            recent = sorted(files, key=lambda path: path.stat().st_mtime, reverse=True)[:6]
            expected.append(f"- {recent[0].name} (Export)")
            expected.extend(f"- {path.name}" for path in recent[1:])
            expected.append("+1")

        self.assertEqual(recorder.recent_exports_text.get(), "\n".join(expected))

    def test_refresh_recent_exports_pluralizes_hidden_audio_line(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            files = []
            for index in range(8):
                path = output_dir / f"take_{index}.wav"
                path.write_text("audio", encoding="utf-8")
                os.utime(path, (time.time() + index, time.time() + index))
                files.append(path)

            recorder.resolve_output_dir = mock.Mock(return_value=output_dir)
            recorder.format_display_path = mock.Mock(return_value="~/Demo")

            recorder.refresh_recent_exports()

            recent = sorted(files, key=lambda path: path.stat().st_mtime, reverse=True)[:6]
            expected = [
                "Klasor ~/Demo",
                "Top 8 | Gr son 6 | Yeni",
                f"- {recent[0].name} (Export)",
            ]
            expected.extend(f"- {path.name}" for path in recent[1:])
            expected.append("+2")

        self.assertEqual(recorder.recent_exports_text.get(), "\n".join(expected))

    def test_refresh_recent_exports_handles_missing_dir(self) -> None:
        recorder = self.make_app()
        missing_dir = Path("/tmp/does-not-exist-gar")
        recorder.last_export_path = Path("/tmp/old_take.wav")
        recorder.last_session_summary_path = Path("/tmp/session_summary.json")
        recorder.resolve_output_dir = mock.Mock(return_value=missing_dir)
        recorder.format_display_path = mock.Mock(return_value="~/missing-output")

        recorder.refresh_recent_exports()

        self.assertIsNone(recorder.last_export_path)
        self.assertIsNone(recorder.last_session_summary_path)
        self.assertEqual(
            recorder.recent_exports_text.get(),
            "Cikis klasoru bulunamadi: ~/missing-output\nBu cikis klasorune su an ulasilamiyor.\n'Klasoru Ac' ile yeniden olusturabilir ve Finder'da acabilirsiniz.",
        )
        self.assertEqual(recorder.open_last_export_button.config_calls[-1], {"state": "disabled"})
        self.assertEqual(recorder.open_last_summary_button.config_calls[-1], {"state": "disabled"})

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
            recorder.format_display_path = mock.Mock(return_value="~/Demo")

            recorder.refresh_recent_exports()

        self.assertIn("Klasor ~/Demo", recorder.recent_exports_text.get())
        self.assertIn("Top 1 | Gr 1", recorder.recent_exports_text.get())
        self.assertIn(
            "- take_001.wav (Export)",
            recorder.recent_exports_text.get(),
        )
        self.assertIn(
            "- session_summary.json (Ozet)",
            recorder.recent_exports_text.get(),
        )

    def test_refresh_recent_exports_marks_all_audio_listed_when_multiple_files_fit(self) -> None:
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
            recorder.format_display_path = mock.Mock(return_value="~/Demo")

            recorder.refresh_recent_exports()

        self.assertIn(
            "Top 2 | Gr tumu | Yeni",
            recorder.recent_exports_text.get(),
        )

    def test_refresh_recent_exports_explains_summary_when_audio_missing(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            summary_path = output_dir / "session_summary.json"
            summary_path.write_text("{}", encoding="utf-8")
            recorder.last_session_summary_path = summary_path
            recorder.resolve_output_dir = mock.Mock(return_value=output_dir)
            recorder.format_display_path = mock.Mock(return_value="~/Demo")

            recorder.refresh_recent_exports()

        self.assertEqual(
            recorder.recent_exports_text.get(),
            "\n".join(
                [
                    "Klasor ~/Demo",
                    "Top 0 | Ozet",
                    "Henuz ses kaydi yok. Alttaki ozeti acabilirsiniz.",
                    "- session_summary.json (Ozet)",
                ]
            ),
        )

    def test_refresh_recent_exports_clears_stale_export_when_only_summary_exists(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir, tempfile.TemporaryDirectory() as olddir:
            output_dir = Path(tmpdir)
            summary_path = output_dir / "session_summary.json"
            summary_path.write_text("{}", encoding="utf-8")
            old_export = Path(olddir) / "old_take.wav"
            old_export.write_text("audio", encoding="utf-8")
            recorder.last_export_path = old_export
            recorder.last_session_summary_path = summary_path
            recorder.resolve_output_dir = mock.Mock(return_value=output_dir)
            recorder.format_display_path = mock.Mock(return_value="~/Demo")

            recorder.refresh_recent_exports()

        self.assertIsNone(recorder.last_export_path)
        self.assertEqual(recorder.open_last_export_button.config_calls[-1], {"state": "disabled"})
        self.assertEqual(recorder.open_last_summary_button.config_calls[-1], {"state": "normal"})

    def test_refresh_recent_exports_restores_summary_button_from_output_dir(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            (output_dir / "session_summary.json").write_text("{}", encoding="utf-8")
            recorder.resolve_output_dir = mock.Mock(return_value=output_dir)

            recorder.refresh_recent_exports()

        self.assertEqual(recorder.last_session_summary_path, output_dir / "session_summary.json")
        self.assertEqual(recorder.open_last_summary_button.config_calls[-1], {"state": "normal"})

    def test_refresh_recent_exports_clears_stale_summary_from_other_folder(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir, tempfile.TemporaryDirectory() as olddir:
            output_dir = Path(tmpdir)
            old_summary = Path(olddir) / "session_summary.json"
            old_summary.write_text("{}", encoding="utf-8")
            recorder.last_session_summary_path = old_summary
            recorder.resolve_output_dir = mock.Mock(return_value=output_dir)
            recorder.format_display_path = mock.Mock(return_value="~/Demo")

            recorder.refresh_recent_exports()

        self.assertIsNone(recorder.last_session_summary_path)
        self.assertEqual(recorder.open_last_summary_button.config_calls[-1], {"state": "disabled"})
        self.assertEqual(
            recorder.recent_exports_text.get(),
            "\n".join(
                [
                    "Klasor ~/Demo",
                    "Top 0",
                    "Henuz ses kaydi yok. Yeni kayitlar burada gosterilir.",
                ]
            ),
        )

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

    def test_refresh_recent_exports_scopes_last_export_to_active_folder(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir, tempfile.TemporaryDirectory() as olddir:
            output_dir = Path(tmpdir)
            first = output_dir / "take_001.wav"
            second = output_dir / "take_002.mp3"
            first.write_text("audio", encoding="utf-8")
            second.write_text("audio", encoding="utf-8")
            os.utime(first, (time.time(), time.time()))
            os.utime(second, (time.time() + 10, time.time() + 10))
            old_export = Path(olddir) / "old_take.wav"
            old_export.write_text("audio", encoding="utf-8")
            recorder.last_export_path = old_export
            recorder.resolve_output_dir = mock.Mock(return_value=output_dir)

            recorder.refresh_recent_exports()

        self.assertEqual(recorder.last_export_path, second)
        self.assertEqual(recorder.open_last_export_button.config_calls[-1], {"state": "normal"})

    def test_refresh_recent_exports_updates_last_export_to_newest_file(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            first = output_dir / "take_001.wav"
            second = output_dir / "take_002.mp3"
            first.write_text("audio", encoding="utf-8")
            second.write_text("audio", encoding="utf-8")
            os.utime(first, (time.time(), time.time()))
            os.utime(second, (time.time() + 10, time.time() + 10))
            recorder.last_export_path = first
            recorder.resolve_output_dir = mock.Mock(return_value=output_dir)

            recorder.refresh_recent_exports()

        self.assertEqual(recorder.last_export_path, second)
        self.assertEqual(recorder.open_last_export_button.config_calls[-1], {"state": "normal"})

    def test_refresh_recent_exports_from_action_reports_audio_count(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            (output_dir / "take_001.wav").write_text("audio", encoding="utf-8")
            (output_dir / "take_002.mp3").write_text("audio", encoding="utf-8")
            recorder.resolve_output_dir = mock.Mock(return_value=output_dir)
            recorder.format_display_path = mock.Mock(return_value="~/Demo")

            recorder.refresh_recent_exports_from_action()

        self.assertEqual(
            recorder.status_messages[-1],
            "Durum guncel. 2 ses dosyasi. Gr tumu. Yeni.",
        )

    def test_refresh_recent_exports_from_action_reports_audio_count_with_summary(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            (output_dir / "take_001.wav").write_text("audio", encoding="utf-8")
            (output_dir / "session_summary.json").write_text("{}", encoding="utf-8")
            recorder.resolve_output_dir = mock.Mock(return_value=output_dir)
            recorder.format_display_path = mock.Mock(return_value="~/Demo")

            recorder.refresh_recent_exports_from_action()

        self.assertEqual(
            recorder.status_messages[-1],
            "Durum guncel. 1 ses dosyasi. Gr 1. Ozet hazir. Isterseniz acabilirsiniz.",
        )

    def test_refresh_recent_exports_from_action_reports_truncated_audio_list(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            for index in range(7):
                suffix = ".mp3" if index % 2 == 0 else ".wav"
                (output_dir / f"take_{index}{suffix}").write_text("audio", encoding="utf-8")
            recorder.resolve_output_dir = mock.Mock(return_value=output_dir)
            recorder.format_display_path = mock.Mock(return_value="~/Demo")

            recorder.refresh_recent_exports_from_action()

        self.assertEqual(
            recorder.status_messages[-1],
            "Durum guncel. 7 ses dosyasi. Gr son 6. Yeni.",
        )

    def test_refresh_recent_exports_from_action_reports_missing_dir(self) -> None:
        recorder = self.make_app()
        missing_dir = Path("/tmp/does-not-exist-gar")
        recorder.resolve_output_dir = mock.Mock(return_value=missing_dir)
        recorder.format_display_path = mock.Mock(return_value="~/Missing")

        recorder.refresh_recent_exports_from_action()

        self.assertEqual(
            recorder.status_messages[-1],
            "Durum guncel. Cikis klasoru bulunamadi: ~/Missing. 'Klasoru Ac' ile yeniden olusturabilir ve Finder'da acabilirsiniz.",
        )

    def test_refresh_recent_exports_from_action_reports_empty_state_hint(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            recorder.resolve_output_dir = mock.Mock(return_value=output_dir)
            recorder.format_display_path = mock.Mock(return_value="~/Demo")

            recorder.refresh_recent_exports_from_action()

        self.assertEqual(
            recorder.status_messages[-1],
            "Durum guncel. Yeni kayitlar burada gosterilir.",
        )

    def test_refresh_recent_exports_from_action_reports_summary_only_state(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            (output_dir / "session_summary.json").write_text("{}", encoding="utf-8")
            recorder.resolve_output_dir = mock.Mock(return_value=output_dir)
            recorder.format_display_path = mock.Mock(return_value="~/Demo")

            recorder.refresh_recent_exports_from_action()

        self.assertEqual(
            recorder.status_messages[-1],
            "Durum guncel. Ozet hazir. Isterseniz acabilirsiniz.",
        )

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
        recorder.refresh_recent_exports = mock.Mock()

        recorder.open_last_export_in_finder()

        self.assertIsNone(recorder.last_export_path)
        recorder.refresh_recent_exports.assert_called_once()
        self.assertEqual(recorder.open_last_export_button.config_calls[-1], {"state": "disabled"})
        self.assertEqual(recorder.status_messages[-1], "Son export dosyasi bulunamadi; son ciktilar yenilendi.")

    def test_open_last_export_in_finder_reports_success(self) -> None:
        recorder = self.make_app()
        recorder.refresh_recent_exports = mock.Mock()
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "take_001.wav"
            export_path.write_text("audio", encoding="utf-8")
            recorder.last_export_path = export_path

            with mock.patch.object(app.subprocess, "run") as run_mock:
                recorder.open_last_export_in_finder()

        recorder.refresh_recent_exports.assert_called_once()
        run_mock.assert_called_once_with(["open", "-R", str(export_path)], check=False)
        self.assertEqual(recorder.status_messages[-1], "Son export Finder'da gosteriliyor: take_001.wav")

    def test_open_output_dir_in_finder_creates_missing_directory(self) -> None:
        recorder = self.make_app()
        recorder.show_recent_exports_for_resolved_output_dir = mock.Mock()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "new-session-folder"
            recorder.resolve_output_dir = mock.Mock(return_value=output_dir)
            recorder.format_display_path = mock.Mock(return_value="~/new-session-folder")

            with mock.patch.object(app.subprocess, "run") as run_mock:
                recorder.open_output_dir_in_finder()
                self.assertTrue(output_dir.exists())
                run_mock.assert_called_once_with(["open", str(output_dir)], check=False)
                recorder.show_recent_exports_for_resolved_output_dir.assert_called_once_with(output_dir)
                self.assertEqual(recorder.status_messages[-1], "Klasor hazirlandi ve acildi: ~/new-session-folder")

    def test_open_output_dir_in_finder_reports_existing_directory(self) -> None:
        recorder = self.make_app()
        recorder.show_recent_exports_for_resolved_output_dir = mock.Mock()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            recorder.resolve_output_dir = mock.Mock(return_value=output_dir)
            recorder.format_display_path = mock.Mock(return_value="~/existing-session-folder")

            with mock.patch.object(app.subprocess, "run") as run_mock:
                recorder.open_output_dir_in_finder()

        run_mock.assert_called_once_with(["open", str(output_dir)], check=False)
        recorder.show_recent_exports_for_resolved_output_dir.assert_called_once_with(output_dir)
        self.assertEqual(recorder.status_messages[-1], "Klasor acildi: ~/existing-session-folder")

    def test_open_output_dir_in_finder_resolves_and_delegates(self) -> None:
        recorder = self.make_app()
        recorder.open_current_output_dir_in_finder = mock.Mock()

        recorder.open_output_dir_in_finder()

        recorder.open_current_output_dir_in_finder.assert_called_once_with()

    def test_open_last_session_summary_handles_missing_summary(self) -> None:
        recorder = self.make_app()
        recorder.last_session_summary_path = None
        recorder.refresh_recent_exports = mock.Mock()

        recorder.open_last_session_summary()

        self.assertIsNone(recorder.last_session_summary_path)
        recorder.refresh_recent_exports.assert_called_once()
        self.assertEqual(recorder.open_last_summary_button.config_calls[-1], {"state": "disabled"})
        self.assertEqual(recorder.status_messages[-1], "Son oturum ozeti bulunamadi; son ciktilar yenilendi.")

    def test_open_last_session_summary_reports_success(self) -> None:
        recorder = self.make_app()
        recorder.refresh_recent_exports = mock.Mock()
        with tempfile.TemporaryDirectory() as tmpdir:
            summary_path = Path(tmpdir) / "session_summary.json"
            summary_path.write_text("{}", encoding="utf-8")
            recorder.last_session_summary_path = summary_path

            with mock.patch.object(app.subprocess, "run") as run_mock:
                recorder.open_last_session_summary()

        recorder.refresh_recent_exports.assert_called_once()
        run_mock.assert_called_once_with(["open", str(summary_path)], check=False)
        self.assertEqual(recorder.status_messages[-1], "Oturum ozeti aciliyor: session_summary.json")


if __name__ == "__main__":
    unittest.main()
