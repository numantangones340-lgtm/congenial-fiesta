import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT_DIR / "scripts" / "write_sha256.py"


class WriteSha256Tests(unittest.TestCase):
    def test_cli_writes_checksum_file_with_expected_format(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            asset_path = Path(tmpdir) / "asset.zip"
            asset_path.write_bytes(b"guitar-amp-recorder")

            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), str(asset_path)],
                cwd=ROOT_DIR,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            checksum_path = Path(f"{asset_path}.sha256")
            self.assertTrue(checksum_path.exists())
            expected_digest = hashlib.sha256(b"guitar-amp-recorder").hexdigest()
            self.assertEqual(
                checksum_path.read_text(encoding="utf-8"),
                f"{expected_digest}  asset.zip\n",
            )
            self.assertEqual(result.stdout.strip(), str(checksum_path))

    def test_cli_writes_multiple_checksum_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            first = Path(tmpdir) / "mac.zip"
            second = Path(tmpdir) / "windows.zip"
            first.write_bytes(b"mac-build")
            second.write_bytes(b"windows-build")

            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), str(first), str(second)],
                cwd=ROOT_DIR,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(Path(f"{first}.sha256").exists())
            self.assertTrue(Path(f"{second}.sha256").exists())
            self.assertEqual(
                result.stdout.strip().splitlines(),
                [str(Path(f"{first}.sha256")), str(Path(f"{second}.sha256"))],
            )

    def test_cli_reports_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            missing = Path(tmpdir) / "missing.zip"

            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), str(missing)],
                cwd=ROOT_DIR,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(f"Dosya bulunamadi: {missing}", result.stderr)


if __name__ == "__main__":
    unittest.main()
