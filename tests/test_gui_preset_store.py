import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from runtime_stubs import load_module, runtime_stubs

with runtime_stubs():
    app = load_module("app_test_gui_presets", "app.py")


class FakeVar:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value) -> None:
        self.value = value


class FakeMenu:
    def __init__(self) -> None:
        self.labels = []

    def delete(self, _start, _end=None) -> None:
        self.labels = []

    def add_command(self, label, command) -> None:
        self.labels.append(label)


class FakeOptionMenu:
    def __init__(self) -> None:
        self.menu = FakeMenu()

    def __getitem__(self, key):
        if key != "menu":
            raise KeyError(key)
        return self.menu


class GuiPresetStoreTests(unittest.TestCase):
    def make_app(self) -> app.GuitarAmpRecorderApp:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        recorder.app_version = "0.1.0-test"
        recorder.preset_name = FakeVar("Temiz Gitar")
        recorder.preset_note = FakeVar("")
        recorder.preset_filter = FakeVar("")
        recorder.preset_filter_meta_text = FakeVar("Preset filtresi kapalı.")
        recorder.preset_scope_text = FakeVar("Yerleşik preset seçili.")
        recorder.preset_summary_text = FakeVar("Preset özeti hazırlanıyor...")
        recorder.input_device_choice = FakeVar("Built-in Mic")
        recorder.output_device_choice = FakeVar("Built-in Output")
        recorder.input_device_id = FakeVar("1")
        recorder.output_device_id = FakeVar("2")
        recorder.output_name = FakeVar("take")
        recorder.output_dir = FakeVar("/tmp/out")
        recorder.session_mode = FakeVar("Tek Klasör")
        recorder.session_name = FakeVar("session")
        recorder.mp3_quality = FakeVar("Yüksek VBR")
        recorder.wav_export_mode = FakeVar("Sadece Vokal WAV")
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
        recorder.limiter_enabled = FakeVar("Açık")
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
        self.assertEqual(store["selected"], "Varsayilan")
        self.assertEqual(store["presets"]["Varsayilan"]["gain"], 9)

    def test_load_preset_store_data_filters_user_overrides_of_builtin_names(self) -> None:
        recorder = self.make_app()
        builtin_gain = app.builtin_preset_store()["presets"]["Temiz Gitar"]["gain"]
        with tempfile.TemporaryDirectory() as tmpdir:
            preset_path = Path(tmpdir) / ".gui_saved_preset.json"
            preset_path.write_text(
                json.dumps(
                    {
                        "selected": "Temiz Gitar",
                        "presets": {
                            "Temiz Gitar": {"gain": 99},
                            "Kullanici": {"gain": 7},
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with mock.patch.object(app, "GUI_PRESET_PATH", preset_path):
                store = recorder.load_preset_store_data()

        self.assertEqual(store["selected"], "Temiz Gitar")
        self.assertEqual(store["presets"]["Temiz Gitar"]["gain"], builtin_gain)
        self.assertEqual(store["presets"]["Kullanici"]["gain"], 7)

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
        self.assertEqual(raw["presets"]["Aksam"]["preset_note"], "")
        recorder.refresh_preset_menu.assert_called_once_with("Aksam")
        self.assertEqual(recorder.status_messages[-1], "Preset kaydedildi: Aksam")

    def test_save_current_preset_uses_existing_selected_name_when_entry_blank(self) -> None:
        recorder = self.make_app()
        recorder.preset_name.set("")
        recorder.gain.set(7)
        with tempfile.TemporaryDirectory() as tmpdir:
            preset_path = Path(tmpdir) / ".gui_saved_preset.json"
            preset_path.write_text(
                json.dumps(
                    {
                        "selected": "Aksam",
                        "presets": {"Aksam": {"gain": 4}},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with mock.patch.object(app, "GUI_PRESET_PATH", preset_path):
                recorder.save_current_preset()
                raw = json.loads(preset_path.read_text(encoding="utf-8"))

        self.assertEqual(raw["selected"], "Aksam")
        self.assertEqual(raw["presets"]["Aksam"]["gain"], 7)
        recorder.refresh_preset_menu.assert_called_once_with("Aksam")
        self.assertEqual(recorder.status_messages[-1], "Preset kaydedildi: Aksam")

    def test_save_current_preset_persists_note(self) -> None:
        recorder = self.make_app()
        recorder.preset_name.set("Aksam")
        recorder.preset_note.set("Akşam için yumuşak ton")
        with tempfile.TemporaryDirectory() as tmpdir:
            preset_path = Path(tmpdir) / ".gui_saved_preset.json"
            with mock.patch.object(app, "GUI_PRESET_PATH", preset_path):
                recorder.save_current_preset()
                raw = json.loads(preset_path.read_text(encoding="utf-8"))

        self.assertEqual(raw["presets"]["Aksam"]["preset_note"], "Akşam için yumuşak ton")

    def test_save_current_preset_rejects_builtin_names(self) -> None:
        recorder = self.make_app()
        recorder.preset_name.set("Temiz Gitar")
        with tempfile.TemporaryDirectory() as tmpdir:
            preset_path = Path(tmpdir) / ".gui_saved_preset.json"
            with mock.patch.object(app, "GUI_PRESET_PATH", preset_path):
                recorder.save_current_preset()
                self.assertFalse(preset_path.exists())

        recorder.refresh_preset_menu.assert_not_called()
        self.assertEqual(recorder.status_messages[-1], "Hazır preset üzerine kaydedilemez: Temiz Gitar")

    def test_save_current_preset_requires_name_when_builtin_is_selected_and_entry_blank(self) -> None:
        recorder = self.make_app()
        recorder.preset_name.set("")
        with tempfile.TemporaryDirectory() as tmpdir:
            preset_path = Path(tmpdir) / ".gui_saved_preset.json"
            with mock.patch.object(app, "GUI_PRESET_PATH", preset_path):
                recorder.save_current_preset()
                self.assertFalse(preset_path.exists())

        recorder.refresh_preset_menu.assert_not_called()
        self.assertEqual(recorder.status_messages[-1], "Yeni bir preset adı girin.")

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
        recorder.last_export_path = None
        recorder.last_take_notes_path = None
        recorder.last_recovery_note_path = None
        recorder.last_preparation_summary_path = None
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

    def test_delete_selected_preset_rejects_builtin_presets(self) -> None:
        recorder = self.make_app()
        recorder.preset_name.set("Temiz Gitar")
        with tempfile.TemporaryDirectory() as tmpdir:
            preset_path = Path(tmpdir) / ".gui_saved_preset.json"
            preset_path.write_text(
                json.dumps({"selected": "Temiz Gitar", "presets": {"Kullanici": {"gain": 4}}}, ensure_ascii=False),
                encoding="utf-8",
            )
            with mock.patch.object(app, "GUI_PRESET_PATH", preset_path):
                recorder.delete_selected_preset()
                raw = json.loads(preset_path.read_text(encoding="utf-8"))

        self.assertIn("Kullanici", raw["presets"])
        self.assertEqual(raw["selected"], "Temiz Gitar")
        self.assertEqual(recorder.status_messages[-1], "Hazır preset silinemez: Temiz Gitar")

    def test_filtered_preset_names_matches_case_insensitive_filter(self) -> None:
        recorder = self.make_app()
        store = {
            "selected": "Temiz Gitar",
            "presets": {
                "Temiz Gitar": {"gain": 4},
                "MacBook Mikrofon Hizli Kayit": {"gain": 8},
                "Aksam": {"gain": 5},
            },
        }

        names = recorder.filtered_preset_names(store, "macbook")

        self.assertEqual(names, ["MacBook Mikrofon Hizli Kayit"])

    def test_refresh_preset_menu_uses_filter_and_updates_meta(self) -> None:
        recorder = self.make_app()
        recorder.refresh_preset_menu = app.GuitarAmpRecorderApp.refresh_preset_menu.__get__(recorder, app.GuitarAmpRecorderApp)
        recorder.preset_menu = FakeOptionMenu()
        recorder.preset_filter.set("macbook")
        recorder.load_preset_store_data = mock.Mock(
            return_value={
                "selected": "Temiz Gitar",
                "presets": {
                    "Temiz Gitar": {"gain": 4},
                    "MacBook Mikrofon Hizli Kayit": {"gain": 8},
                    "Aksam": {"gain": 5},
                },
            }
        )

        recorder.refresh_preset_menu()

        self.assertEqual(recorder.preset_names, ["MacBook Mikrofon Hizli Kayit"])
        self.assertEqual(recorder.preset_name.get(), "MacBook Mikrofon Hizli Kayit")
        self.assertEqual(recorder.preset_menu.menu.labels, ["MacBook Mikrofon Hizli Kayit"])
        self.assertEqual(recorder.preset_filter_meta_text.get(), 'Filtre "macbook" için eşleşme: 1/3')

    def test_clear_preset_filter_resets_value_and_refreshes_menu(self) -> None:
        recorder = self.make_app()
        recorder.preset_filter.set("aksam")

        recorder.clear_preset_filter()

        self.assertEqual(recorder.preset_filter.get(), "")
        recorder.refresh_preset_menu.assert_called_once_with()
        self.assertEqual(recorder.status_messages[-1], "Preset filtresi temizlendi.")

    def test_refresh_preset_menu_marks_builtin_selected_preset_scope(self) -> None:
        recorder = self.make_app()
        recorder.refresh_preset_menu = app.GuitarAmpRecorderApp.refresh_preset_menu.__get__(recorder, app.GuitarAmpRecorderApp)
        recorder.preset_menu = FakeOptionMenu()
        recorder.load_preset_store_data = mock.Mock(
            return_value={
                "selected": "Temiz Gitar",
                "presets": {
                    "Temiz Gitar": {"gain": 4},
                    "Aksam": {"gain": 5},
                },
            }
        )

        recorder.refresh_preset_menu("Temiz Gitar")

        self.assertEqual(recorder.preset_scope_text.get(), "Yerleşik preset seçili: Temiz Gitar")
        self.assertEqual(recorder.preset_summary_text.get(), "Gain: 4 | Vokal: -% | Çıkış Kazancı: - dB")

    def test_refresh_preset_menu_marks_user_selected_preset_scope(self) -> None:
        recorder = self.make_app()
        recorder.refresh_preset_menu = app.GuitarAmpRecorderApp.refresh_preset_menu.__get__(recorder, app.GuitarAmpRecorderApp)
        recorder.preset_menu = FakeOptionMenu()
        recorder.load_preset_store_data = mock.Mock(
            return_value={
                "selected": "Aksam",
                "presets": {
                    "Temiz Gitar": {"gain": 4},
                    "Aksam": {"gain": 5},
                },
            }
        )

        recorder.refresh_preset_menu("Aksam")

        self.assertEqual(recorder.preset_scope_text.get(), "Kullanıcı preset seçili: Aksam")
        self.assertEqual(recorder.preset_summary_text.get(), "Gain: 5 | Vokal: -% | Çıkış Kazancı: - dB")

    def test_on_preset_selected_updates_scope_and_summary(self) -> None:
        recorder = self.make_app()
        recorder.load_preset_store_data = mock.Mock(
            return_value={
                "selected": "Aksam",
                "presets": {
                    "Temiz Gitar": {"gain": 4, "vocal_level": 85, "output_gain": 0},
                    "Aksam": {"gain": 6, "vocal_level": 92, "output_gain": 3},
                },
            }
        )

        recorder.on_preset_selected("Aksam")

        self.assertEqual(recorder.preset_name.get(), "Aksam")
        self.assertEqual(recorder.preset_scope_text.get(), "Kullanıcı preset seçili: Aksam")
        self.assertEqual(recorder.preset_summary_text.get(), "Gain: 6 | Vokal: 92% | Çıkış Kazancı: 3 dB")

    def test_on_preset_selected_restores_note_and_summary(self) -> None:
        recorder = self.make_app()
        recorder.load_preset_store_data = mock.Mock(
            return_value={
                "selected": "Aksam",
                "presets": {
                    "Aksam": {"gain": 6, "vocal_level": 92, "output_gain": 3, "preset_note": "Sakin vokal kayıt"},
                },
            }
        )

        recorder.on_preset_selected("Aksam")

        self.assertEqual(recorder.preset_note.get(), "Sakin vokal kayıt")
        self.assertEqual(recorder.preset_summary_text.get(), "Gain: 6 | Vokal: 92% | Çıkış Kazancı: 3 dB | Not: Sakin vokal kayıt")

    def test_duplicate_selected_preset_creates_copy_of_builtin_preset(self) -> None:
        recorder = self.make_app()
        recorder.preset_name.set("Temiz Gitar")
        with tempfile.TemporaryDirectory() as tmpdir:
            preset_path = Path(tmpdir) / ".gui_saved_preset.json"
            with mock.patch.object(app, "GUI_PRESET_PATH", preset_path):
                recorder.duplicate_selected_preset()
                raw = json.loads(preset_path.read_text(encoding="utf-8"))

        self.assertIn("Temiz Gitar Kopya", raw["presets"])
        self.assertEqual(raw["selected"], "Temiz Gitar Kopya")
        self.assertEqual(
            raw["presets"]["Temiz Gitar Kopya"]["gain"],
            app.builtin_preset_store()["presets"]["Temiz Gitar"]["gain"],
        )
        recorder.refresh_preset_menu.assert_called_once_with("Temiz Gitar Kopya")
        self.assertEqual(recorder.status_messages[-1], "Preset çoğaltıldı: Temiz Gitar -> Temiz Gitar Kopya")

    def test_duplicate_selected_preset_increments_copy_name_when_needed(self) -> None:
        recorder = self.make_app()
        recorder.preset_name.set("Aksam")
        with tempfile.TemporaryDirectory() as tmpdir:
            preset_path = Path(tmpdir) / ".gui_saved_preset.json"
            preset_path.write_text(
                json.dumps(
                    {
                        "selected": "Aksam",
                        "presets": {
                            "Aksam": {"gain": 4},
                            "Aksam Kopya": {"gain": 5},
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with mock.patch.object(app, "GUI_PRESET_PATH", preset_path):
                recorder.duplicate_selected_preset()
                raw = json.loads(preset_path.read_text(encoding="utf-8"))

        self.assertIn("Aksam Kopya 2", raw["presets"])
        self.assertEqual(raw["selected"], "Aksam Kopya 2")
        self.assertEqual(raw["presets"]["Aksam Kopya 2"]["gain"], 4)
        recorder.refresh_preset_menu.assert_called_once_with("Aksam Kopya 2")
        self.assertEqual(recorder.status_messages[-1], "Preset çoğaltıldı: Aksam -> Aksam Kopya 2")

    def test_export_selected_preset_json_writes_builtin_preset_to_output_dir(self) -> None:
        recorder = self.make_app()
        recorder.preset_name.set("Temiz Gitar")
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "Presets"
            recorder.output_dir.set(str(output_dir))
            recorder.resolve_output_dir = mock.Mock(return_value=output_dir)

            recorder.export_selected_preset_json()

            export_path = output_dir / "Temiz_Gitar.preset.json"
            raw = json.loads(export_path.read_text(encoding="utf-8"))

        self.assertEqual(raw["name"], "Temiz Gitar")
        self.assertEqual(raw["preset"]["gain"], app.builtin_preset_store()["presets"]["Temiz Gitar"]["gain"])
        self.assertEqual(recorder.status_messages[-1], f"Preset JSON yazıldı: {export_path}")

    def test_export_selected_preset_json_requires_output_dir(self) -> None:
        recorder = self.make_app()
        recorder.output_dir.set("")

        recorder.export_selected_preset_json()

        self.assertEqual(recorder.status_messages[-1], "Preset JSON için önce kayıt klasörünü seçin.")

    def test_export_selected_preset_json_reports_missing_preset(self) -> None:
        recorder = self.make_app()
        recorder.preset_name.set("Bulunamayan")
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            recorder.output_dir.set(str(output_dir))
            recorder.resolve_output_dir = mock.Mock(return_value=output_dir)

            recorder.export_selected_preset_json()

        self.assertEqual(recorder.status_messages[-1], "Preset bulunamadı: Bulunamayan")

    def test_import_preset_json_imports_export_format_and_selects_name(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            preset_json = Path(tmpdir) / "Aksam.preset.json"
            preset_json.write_text(
                json.dumps({"name": "Aksam", "preset": {"gain": 9, "output_gain": 2}}, ensure_ascii=False),
                encoding="utf-8",
            )
            preset_path = Path(tmpdir) / ".gui_saved_preset.json"
            with mock.patch.object(app, "GUI_PRESET_PATH", preset_path), mock.patch.object(
                app, "filedialog", mock.Mock(askopenfilename=mock.Mock(return_value=str(preset_json)))
            ):
                recorder.import_preset_json()
                raw = json.loads(preset_path.read_text(encoding="utf-8"))

        self.assertIn("Aksam", raw["presets"])
        self.assertEqual(raw["selected"], "Aksam")
        self.assertEqual(raw["presets"]["Aksam"]["gain"], 9)
        recorder.refresh_preset_menu.assert_called_once_with("Aksam")
        self.assertEqual(recorder.status_messages[-1], "Preset içe aktarıldı: Aksam")

    def test_import_preset_json_renames_when_name_conflicts(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            preset_json = Path(tmpdir) / "Temiz_Gitar.preset.json"
            preset_json.write_text(
                json.dumps({"name": "Temiz Gitar", "preset": {"gain": 9}}, ensure_ascii=False),
                encoding="utf-8",
            )
            preset_path = Path(tmpdir) / ".gui_saved_preset.json"
            with mock.patch.object(app, "GUI_PRESET_PATH", preset_path), mock.patch.object(
                app, "filedialog", mock.Mock(askopenfilename=mock.Mock(return_value=str(preset_json)))
            ):
                recorder.import_preset_json()
                raw = json.loads(preset_path.read_text(encoding="utf-8"))

        self.assertIn("Temiz Gitar Kopya", raw["presets"])
        self.assertEqual(raw["selected"], "Temiz Gitar Kopya")
        recorder.refresh_preset_menu.assert_called_once_with("Temiz Gitar Kopya")
        self.assertEqual(recorder.status_messages[-1], "Preset içe aktarıldı: Temiz Gitar Kopya")

    def test_import_preset_json_reports_cancelled_selection(self) -> None:
        recorder = self.make_app()

        with mock.patch.object(app, "filedialog", mock.Mock(askopenfilename=mock.Mock(return_value=""))):
            recorder.import_preset_json()

        self.assertEqual(recorder.status_messages[-1], "Preset JSON seçilmedi.")

    def test_import_preset_json_reports_invalid_payload(self) -> None:
        recorder = self.make_app()
        with tempfile.TemporaryDirectory() as tmpdir:
            preset_json = Path(tmpdir) / "broken.preset.json"
            preset_json.write_text(json.dumps(["invalid"], ensure_ascii=False), encoding="utf-8")
            with mock.patch.object(
                app, "filedialog", mock.Mock(askopenfilename=mock.Mock(return_value=str(preset_json)))
            ):
                recorder.import_preset_json()

        self.assertEqual(recorder.status_messages[-1], "Preset JSON geçersiz: broken.preset.json")


if __name__ == "__main__":
    unittest.main()
