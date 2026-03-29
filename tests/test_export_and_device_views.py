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

    def test_recent_exports_action_status_message_for_missing_dir(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        missing_dir = Path("/tmp/does-not-exist-gar")
        recorder.format_display_path = mock.Mock(return_value="~/Missing")

        self.assertEqual(
            recorder.recent_exports_action_status_message(
                output_dir=missing_dir,
                total_audio_count=0,
                has_summary=False,
            ),
            "Durum guncel. Cikis klasoru bulunamadi: ~/Missing. 'Klasoru Ac' ile yeniden olusturabilir ve Finder'da acabilirsiniz.",
        )

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

    def test_recent_export_line_marks_latest_export(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_export_line("take_001.wav", is_latest=True),
            "- take_001.wav (Export)",
        )

    def test_recent_summary_line_marks_summary_item(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_summary_line("session_summary.json"),
            "- session_summary.json (Ozet)",
        )

    def test_recent_exports_header_line_formats_folder_label(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_exports_header_line("~/Demo"),
            "Klasor ~/Demo",
        )

    def test_recent_hidden_count_line_formats_hidden_total(self) -> None:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)

        self.assertEqual(
            recorder.recent_hidden_count_line(2),
            "+2",
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
        recorder.refresh_recent_exports = mock.Mock()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "new-session-folder"
            recorder.resolve_output_dir = mock.Mock(return_value=output_dir)
            recorder.format_display_path = mock.Mock(return_value="~/new-session-folder")

            with mock.patch.object(app.subprocess, "run") as run_mock:
                recorder.open_output_dir_in_finder()
                self.assertTrue(output_dir.exists())
                run_mock.assert_called_once_with(["open", str(output_dir)], check=False)
                recorder.refresh_recent_exports.assert_called_once()
                self.assertEqual(recorder.status_messages[-1], "Klasor hazirlandi ve acildi: ~/new-session-folder")

    def test_open_output_dir_in_finder_reports_existing_directory(self) -> None:
        recorder = self.make_app()
        recorder.refresh_recent_exports = mock.Mock()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            recorder.resolve_output_dir = mock.Mock(return_value=output_dir)
            recorder.format_display_path = mock.Mock(return_value="~/existing-session-folder")

            with mock.patch.object(app.subprocess, "run") as run_mock:
                recorder.open_output_dir_in_finder()

        run_mock.assert_called_once_with(["open", str(output_dir)], check=False)
        recorder.refresh_recent_exports.assert_called_once()
        self.assertEqual(recorder.status_messages[-1], "Klasor acildi: ~/existing-session-folder")

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
