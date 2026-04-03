import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

DEPENDENCY_IMPORT_ERROR = None
try:
    import numpy as np
    import app
    import cli_app
except ModuleNotFoundError as exc:
    DEPENDENCY_IMPORT_ERROR = exc
    np = None
    app = None
    cli_app = None


ROOT_DIR = Path(__file__).resolve().parents[1]


@unittest.skipIf(DEPENDENCY_IMPORT_ERROR is not None, f"runtime deps missing: {DEPENDENCY_IMPORT_ERROR}")
class ModuleSmokeTests(unittest.TestCase):
    def test_version_is_readable(self) -> None:
        version = app.read_app_version()
        self.assertTrue(version)
        self.assertEqual(version, cli_app.read_app_version())

    def test_audio_helpers_return_expected_shapes(self) -> None:
        mono = np.array([0.0, 0.25, -0.25, 0.5], dtype=np.float32)
        stereo = app.ensure_stereo(mono)
        self.assertEqual(stereo.shape, (4, 2))

        resampled = app.resample_linear(stereo, 4, 8)
        self.assertEqual(resampled.shape, (8, 2))

        sped = cli_app.change_speed(mono, 0.5)
        self.assertGreater(len(sped), len(mono))

    def test_amp_chain_output_is_bounded(self) -> None:
        voice = np.linspace(-0.5, 0.5, 128, dtype=np.float32)
        processed = app.apply_amp_chain(
            voice,
            sample_rate=44100,
            gain_db=6.0,
            boost_db=3.0,
            bass_db=2.0,
            treble_db=2.0,
            distortion=20.0,
        )
        self.assertEqual(processed.shape, voice.shape)
        self.assertTrue(np.all(processed <= 1.0))
        self.assertTrue(np.all(processed >= -1.0))

    def test_resolve_ffmpeg_binary_prefers_path_lookup(self) -> None:
        with mock.patch.object(app.shutil, "which", return_value="/tmp/ffmpeg"):
            self.assertEqual(app.resolve_ffmpeg_binary(), "/tmp/ffmpeg")

    def test_resolve_ffmpeg_binary_falls_back_to_known_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            candidate = Path(tmpdir) / "ffmpeg"
            candidate.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            candidate.chmod(0o755)
            with (
                mock.patch.object(app.shutil, "which", return_value=None),
                mock.patch.object(app, "ffmpeg_binary_candidates", return_value=[candidate]),
            ):
                self.assertEqual(app.resolve_ffmpeg_binary(), str(candidate))

    def test_record_input_stream_collects_frames_from_callback(self) -> None:
        callback_stop = app.sd.CallbackStop

        class FakeInputStream:
            def __init__(self, **kwargs):
                self.callback = kwargs["callback"]

            def __enter__(self):
                for chunk in (
                    np.array([[0.1], [0.2]], dtype=np.float32),
                    np.array([[0.3], [0.4]], dtype=np.float32),
                ):
                    try:
                        self.callback(chunk, len(chunk), None, None)
                    except callback_stop:
                        break
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with mock.patch.object(app.sd, "InputStream", FakeInputStream):
            recorded = app.record_input_stream(sample_rate=44100, frames=3, channels=1, device=1, blocksize=2)

        self.assertEqual(recorded.shape, (3, 1))
        np.testing.assert_allclose(recorded[:, 0], np.array([0.1, 0.2, 0.3], dtype=np.float32))

    def test_device_default_samplerate_uses_query_result(self) -> None:
        with mock.patch.object(app.sd, "query_devices", return_value={"default_samplerate": 48000.0}):
            self.assertEqual(app.device_default_samplerate(1, "input"), 48000)

    def test_next_timestamped_take_name_for_dir_uses_clock_stamp(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            directory = Path(tmpdir)
            with mock.patch.object(app.time, "strftime", return_value="20260403_190000"):
                name = app.next_timestamped_take_name_for_dir(directory, "quick_take")

        self.assertEqual(name, "quick_take_20260403_190000")


@unittest.skipIf(DEPENDENCY_IMPORT_ERROR is not None, f"runtime deps missing: {DEPENDENCY_IMPORT_ERROR}")
class CliSmokeTests(unittest.TestCase):
    def test_cli_help_exits_cleanly(self) -> None:
        result = subprocess.run(
            [sys.executable, "cli_app.py", "--help"],
            cwd=ROOT_DIR,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("Kullanim:", result.stdout)

    def test_cli_version_matches_file(self) -> None:
        result = subprocess.run(
            [sys.executable, "cli_app.py", "--version"],
            cwd=ROOT_DIR,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), app.read_app_version())


if __name__ == "__main__":
    unittest.main()
