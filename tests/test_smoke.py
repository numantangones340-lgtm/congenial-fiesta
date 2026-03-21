import subprocess
import sys
import unittest
from pathlib import Path

import numpy as np

import app
import cli_app


ROOT_DIR = Path(__file__).resolve().parents[1]


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
