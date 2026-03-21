import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT_DIR / "scripts" / "generate_release_notes.py"


class ReleaseNotesGenerationTests(unittest.TestCase):
    def test_stdout_generation_uses_current_version(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            cwd=ROOT_DIR,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("# Release Notes 1.1.2", result.stdout)
        self.assertIn("Canli giris metre sistemi", result.stdout)

    def test_output_file_is_written(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "release-notes.md"
            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), "--output", str(output_path)],
                cwd=ROOT_DIR,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0)
            self.assertTrue(output_path.exists())
            content = output_path.read_text(encoding="utf-8")
            self.assertIn("## [1.1.2]", ROOT_DIR.joinpath("CHANGELOG.md").read_text(encoding="utf-8"))
            self.assertIn("# Release Notes 1.1.2", content)


if __name__ == "__main__":
    unittest.main()
