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


class FakeLabel:
    def __init__(self) -> None:
        self.config_calls = []

    def config(self, **kwargs) -> None:
        self.config_calls.append(kwargs)


class RecordingReadinessTests(unittest.TestCase):
    def make_app(self, output_dir: str) -> app.GuitarAmpRecorderApp:
        recorder = app.GuitarAmpRecorderApp.__new__(app.GuitarAmpRecorderApp)
        recorder.output_dir = FakeVar(output_dir)
        recorder.session_mode = FakeVar("Tek Klasor")
        recorder.session_name = FakeVar("session_20260328")
        recorder.output_name = FakeVar("guitar_mix_custom")
        recorder.mp3_quality = FakeVar("Yuksek VBR")
        recorder.wav_export_mode = FakeVar("Sadece Vocal WAV")
        recorder.preset_name = FakeVar("Temiz Gitar")
        recorder.record_limit_hours = FakeVar("1")
        recorder.mic_record_seconds = FakeVar("60")
        recorder.record_progress_text = FakeVar("onceki")
        recorder.recording_active = False
        recorder.last_input_peak = 0.0
        recorder.backing_file = None
        recorder.backing_label = FakeLabel()
        recorder.status_messages = []
        recorder.set_status = recorder.status_messages.append
        return recorder

    def test_build_recording_readiness_summary_for_mic_only_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            recorder = self.make_app(tmpdir)
            with mock.patch.object(app.time, "strftime", return_value="20260403_190000"):
                summary = app.GuitarAmpRecorderApp.build_recording_readiness_summary(recorder)

        self.assertIn("Hazirlik ozeti:", summary)
        self.assertIn("Preset: Temiz Gitar", summary)
        self.assertIn("Kaynak: Sadece mikrofon", summary)
        self.assertIn(f"Hedef klasor: {Path(tmpdir)}", summary)
        self.assertIn("Tam kayit adi: guitar_mix_custom", summary)
        self.assertIn("Quick kayit adi: quick_take_20260403_190000", summary)
        self.assertIn("Ciktilar: MP3 (Yuksek VBR) + Vocal WAV", summary)
        self.assertIn("Sure plani: 60 sn (ust sinir 1 saat)", summary)
        self.assertIn("Durum: Seviye kontrolu bekleniyor.", summary)

    def test_build_recording_readiness_summary_for_named_session_and_wav_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            recorder = self.make_app(tmpdir)
            recorder.session_mode.set("Isimli Oturum")
            recorder.session_name.set("Canli:Deneme?")
            recorder.wav_export_mode.set("Sadece WAV (Mix + Vocal)")
            recorder.preset_name.set("Guclu Performans")
            recorder.backing_file = Path(tmpdir) / "demo_backing.wav"
            recorder.last_input_peak = 0.12

            summary = app.GuitarAmpRecorderApp.build_recording_readiness_summary(recorder)

        self.assertIn("Preset: Guclu Performans", summary)
        self.assertIn("Kaynak: demo_backing.wav + mikrofon", summary)
        self.assertIn(f"Hedef klasor: {Path(tmpdir) / 'Canli_Deneme_'}", summary)
        self.assertIn("Ciktilar: Mix WAV + Vocal WAV", summary)
        self.assertIn("Sure plani: Backing dosyasi boyunca (ust sinir kayit limiti)", summary)
        self.assertIn("Durum: Hazir gorunuyor. Once 5 saniyelik test yapip sonra kayda gecin.", summary)

    def test_refresh_recording_readiness_updates_only_when_idle(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            recorder = self.make_app(tmpdir)

            app.GuitarAmpRecorderApp.refresh_recording_readiness(recorder)
            self.assertIn("Hazirlik ozeti:", recorder.record_progress_text.get())

            recorder.recording_active = True
            recorder.record_progress_text.set("kayit suruyor")
            app.GuitarAmpRecorderApp.refresh_recording_readiness(recorder)

        self.assertEqual(recorder.record_progress_text.get(), "kayit suruyor")

    def test_clear_backing_returns_to_mic_only_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            recorder = self.make_app(tmpdir)
            recorder.backing_file = Path(tmpdir) / "demo_backing.wav"

            app.GuitarAmpRecorderApp.clear_backing(recorder)

        self.assertIsNone(recorder.backing_file)
        self.assertEqual(recorder.backing_label.config_calls[-1], {"text": "Dosya seçilmedi", "fg": "#9aa7b5"})
        self.assertIn("Kaynak: Sadece mikrofon", recorder.record_progress_text.get())
        self.assertEqual(recorder.status_messages[-1], "Arka plan muzigi temizlendi. Sadece mikrofon kaydi hazir.")

    def test_clear_backing_without_selection_reports_noop(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            recorder = self.make_app(tmpdir)

            app.GuitarAmpRecorderApp.clear_backing(recorder)

        self.assertEqual(recorder.status_messages[-1], "Arka plan muzigi zaten secili degil.")
        self.assertEqual(recorder.backing_label.config_calls, [])

    def test_select_backing_updates_label_and_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            recorder = self.make_app(tmpdir)
            backing_path = Path(tmpdir) / "demo_backing.wav"
            backing_path.write_text("audio", encoding="utf-8")

            with mock.patch.object(app.filedialog, "askopenfilename", return_value=str(backing_path)):
                app.GuitarAmpRecorderApp.select_backing(recorder)

        self.assertEqual(recorder.backing_file, backing_path)
        self.assertEqual(recorder.backing_label.config_calls[-1], {"text": "demo_backing.wav", "fg": "#2c3e50"})
        self.assertIn("Kaynak: demo_backing.wav + mikrofon", recorder.record_progress_text.get())
        self.assertEqual(
            recorder.status_messages[-1],
            "Arka plan muzigi secildi: demo_backing.wav. Backing + mikrofon kaydi hazir.",
        )


if __name__ == "__main__":
    unittest.main()
