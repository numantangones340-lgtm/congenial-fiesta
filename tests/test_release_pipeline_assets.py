import subprocess
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


class ReleasePipelineAssetTests(unittest.TestCase):
    def test_release_scripts_exist(self) -> None:
        for name in (
            "sign_macos_app.sh",
            "notarize_macos_app.sh",
            "release_macos_desktop.sh",
        ):
            self.assertTrue((ROOT_DIR / name).exists(), name)

    def test_release_docs_exist(self) -> None:
        for name in (
            "MACOS_RELEASE_CHECKLIST.md",
            "PRODUCT_ROADMAP.md",
        ):
            self.assertTrue((ROOT_DIR / "docs" / name).exists(), name)

    def test_release_scripts_have_valid_bash_syntax(self) -> None:
        for name in (
            "build_macos_app.sh",
            "sign_macos_app.sh",
            "notarize_macos_app.sh",
            "package_macos_release.sh",
            "release_macos_desktop.sh",
        ):
            result = subprocess.run(
                ["bash", "-n", str(ROOT_DIR / name)],
                cwd=ROOT_DIR,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, f"{name}: {result.stderr}")

    def test_build_script_writes_spec_outside_repo_root(self) -> None:
        content = (ROOT_DIR / "build_macos_app.sh").read_text(encoding="utf-8")
        self.assertIn('SPEC_DIR="build/spec"', content)
        self.assertIn('SPEC_PATH="${SPEC_DIR}/${APP_NAME}.spec"', content)
        self.assertIn('cp "${SPEC_TEMPLATE}" "${SPEC_PATH}"', content)
        self.assertIn('.venv/bin/pyinstaller --noconfirm --clean "${SPEC_PATH}"', content)
        self.assertNotIn('rm -rf build dist "${APP_NAME}.spec"', content)

    def test_spec_declares_microphone_usage_description(self) -> None:
        content = (ROOT_DIR / "GuitarAmpRecorder.spec").read_text(encoding="utf-8")
        self.assertIn("NSMicrophoneUsageDescription", content)


if __name__ == "__main__":
    unittest.main()
