import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT_DIR / "scripts" / "generate_release_notes.py"
VERSION = ROOT_DIR.joinpath("VERSION").read_text(encoding="utf-8").strip()


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
        self.assertIn(f"# Release Notes {VERSION}", result.stdout)
        self.assertIn("Bu surumun detaylari `CHANGELOG.md` kaynagindan otomatik uretildi.", result.stdout)

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
            self.assertIn(f"## [{VERSION}]", ROOT_DIR.joinpath("CHANGELOG.md").read_text(encoding="utf-8"))
            self.assertIn(f"# Release Notes {VERSION}", content)

    def test_backward_compatible_version_file_and_changelog_args_work(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            version_path = tmp / "VERSION"
            changelog_path = tmp / "CHANGELOG.md"
            output_path = tmp / "release-notes.md"
            version_path.write_text("9.9.9\n", encoding="utf-8")
            changelog_path.write_text(
                "## [9.9.9] - 2026-03-22\n- otomatik test girdisi\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--version-file",
                    str(version_path),
                    "--changelog",
                    str(changelog_path),
                    "--output",
                    str(output_path),
                ],
                cwd=ROOT_DIR,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0)
            self.assertIn("# Release Notes 9.9.9", output_path.read_text(encoding="utf-8"))

    def test_fails_when_both_version_flags_are_given(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            version_path = Path(tmpdir) / "VERSION"
            version_path.write_text("9.9.9\n", encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--version",
                    VERSION,
                    "--version-file",
                    str(version_path),
                ],
                cwd=ROOT_DIR,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--version and --version-file cannot be used together", result.stderr)

    def test_fails_when_changelog_section_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            version_path = tmp / "VERSION"
            changelog_path = tmp / "CHANGELOG.md"
            version_path.write_text("9.9.9\n", encoding="utf-8")
            changelog_path.write_text("## [1.2.3] - 2026-03-22\n- baska surum\n", encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--version-file",
                    str(version_path),
                    "--changelog",
                    str(changelog_path),
                ],
                cwd=ROOT_DIR,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("CHANGELOG.md icinde [9.9.9] bolumu bulunamadi.", result.stderr)


if __name__ == "__main__":
    unittest.main()
