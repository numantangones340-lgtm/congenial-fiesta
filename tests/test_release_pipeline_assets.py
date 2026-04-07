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
        self.assertTrue((ROOT_DIR / "CONTRIBUTING.md").exists(), "CONTRIBUTING.md")
        for name in (
            "DELIVERY_SUMMARY.md",
            "MACOS_RELEASE_CHECKLIST.md",
            "WINDOWS_RELEASE_CHECKLIST.md",
            "FIRST_RUN_GUIDE.md",
            "LAUNCH_COPY.md",
            "SUPPORT_FAQ.md",
            "PRODUCT_ROADMAP.md",
        ):
            self.assertTrue((ROOT_DIR / "docs" / name).exists(), name)

    def test_macos_release_checklist_mentions_checksum_assets(self) -> None:
        content = (ROOT_DIR / "docs" / "MACOS_RELEASE_CHECKLIST.md").read_text(encoding="utf-8")
        self.assertIn("dist/GuitarAmpRecorder-macOS.zip.sha256", content)
        self.assertIn("~/Desktop/GuitarAmpRecorder-macOS.zip.sha256", content)
        self.assertIn("bash -n install_macos_professional.sh", content)
        self.assertIn("./install_macos_professional.sh", content)

    def test_release_scripts_have_valid_bash_syntax(self) -> None:
        for name in (
            "build_macos_app.sh",
            "sign_macos_app.sh",
            "notarize_macos_app.sh",
            "package_macos_release.sh",
            "release_macos_desktop.sh",
            "install_macos_professional.sh",
        ):
            result = subprocess.run(
                ["bash", "-n", str(ROOT_DIR / name)],
                cwd=ROOT_DIR,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, f"{name}: {result.stderr}")

    def test_issue_templates_exist(self) -> None:
        for name in (
            "bug_report.yml",
            "feature_request.yml",
            "config.yml",
        ):
            self.assertTrue((ROOT_DIR / ".github" / "ISSUE_TEMPLATE" / name).exists(), name)

    def test_security_policy_is_project_specific(self) -> None:
        content = (ROOT_DIR / "SECURITY.md").read_text(encoding="utf-8")
        self.assertIn("1.1.x", content)
        self.assertIn("public issue olarak paylasmayin", content)
        self.assertNotIn("5.1.x", content)

    def test_build_script_writes_spec_outside_repo_root(self) -> None:
        content = (ROOT_DIR / "build_macos_app.sh").read_text(encoding="utf-8")
        self.assertIn('SPEC_DIR="build/spec"', content)
        self.assertIn('SPEC_PATH="${SPEC_DIR}/${APP_NAME}.spec"', content)
        self.assertIn('cp "${SPEC_TEMPLATE}" "${SPEC_PATH}"', content)
        self.assertIn('.venv/bin/pyinstaller --noconfirm --clean', content)
        self.assertIn('"${SPEC_PATH}"', content)
        self.assertNotIn('rm -rf build dist "${APP_NAME}.spec"', content)

    def test_package_script_copies_checksum_to_desktop_when_zip_copy_succeeds(self) -> None:
        content = (ROOT_DIR / "package_macos_release.sh").read_text(encoding="utf-8")
        self.assertIn('ZIP_SHA_PATH="${ZIP_PATH}.sha256"', content)
        self.assertIn('DESKTOP_ZIP_SHA="${DESKTOP_ZIP}.sha256"', content)
        self.assertIn('cp "$ZIP_SHA_PATH" "$DESKTOP_ZIP_SHA"', content)
        self.assertIn("SHA256 de masaustune kopyalandi", content)

    def test_notarize_script_cleans_temporary_zip_on_exit(self) -> None:
        content = (ROOT_DIR / "notarize_macos_app.sh").read_text(encoding="utf-8")
        self.assertIn('TMP_ZIP="$ROOT_DIR/dist/$(basename "$APP_PATH" .app)-notarize.zip"', content)
        self.assertIn("cleanup() {", content)
        self.assertIn('rm -f "$TMP_ZIP"', content)
        self.assertIn("trap cleanup EXIT", content)

    def test_release_script_reports_desktop_assets_only_when_present(self) -> None:
        content = (ROOT_DIR / "release_macos_desktop.sh").read_text(encoding="utf-8")
        self.assertIn('DESKTOP_ZIP="$HOME/Desktop/GuitarAmpRecorder-macOS.zip"', content)
        self.assertIn('if [ -f "$DESKTOP_ZIP" ]; then', content)
        self.assertIn('echo "- Masaustu kopyasi: $DESKTOP_ZIP"', content)
        self.assertIn('echo "- Masaustu kopyasi: olusturulamadi, dist zip hazir"', content)
        self.assertIn('if [ -f "$DESKTOP_ZIP_SHA" ]; then', content)
        self.assertIn('echo "- Masaustu SHA256: $DESKTOP_ZIP_SHA"', content)
        self.assertIn('echo "- Masaustu SHA256: olusturulamadi, dist checksum hazir"', content)

    def test_professional_install_script_copies_and_reports_desktop_checksum(self) -> None:
        content = (ROOT_DIR / "install_macos_professional.sh").read_text(encoding="utf-8")
        self.assertIn('ZIP_SHA_DIST="${ZIP_DIST}.sha256"', content)
        self.assertIn('if [ ! -f "${ZIP_DIST}" ]; then', content)
        self.assertIn('echo "HATA: Build sonrasi zip bulunamadi: ${ZIP_DIST}"', content)
        self.assertIn('python3 "${SCRIPT_DIR}/scripts/write_sha256.py" "${ZIP_DIST}"', content)
        self.assertIn('DESKTOP_ZIP_SHA="${DESKTOP_ZIP}.sha256"', content)
        self.assertIn('cp -f "${ZIP_DIST}" "${DESKTOP_ZIP}"', content)
        self.assertIn('if [ -f "${ZIP_SHA_DIST}" ]; then', content)
        self.assertIn('cp -f "${ZIP_SHA_DIST}" "${DESKTOP_ZIP_SHA}"', content)
        self.assertIn('if [ -f "${DESKTOP_ZIP_SHA}" ]; then', content)
        self.assertIn('echo "Masaustu SHA256: ${DESKTOP_ZIP_SHA}"', content)
        self.assertIn('ARCHIVE_PATHS=(', content)
        self.assertIn('"${HOME}/Downloads/${APP_NAME}-macOS.zip.sha256"', content)
        self.assertIn('if [ "${ARCHIVED_ANY}" -eq 0 ]; then', content)
        self.assertIn('mkdir -p "${ARCHIVE_DIR}"', content)
        self.assertIn('echo "Arsivlenen eski dosyalar: yok"', content)

    def test_spec_declares_microphone_usage_description(self) -> None:
        content = (ROOT_DIR / "GuitarAmpRecorder.spec").read_text(encoding="utf-8")
        self.assertIn("NSMicrophoneUsageDescription", content)

    def test_download_page_has_direct_platform_download_links(self) -> None:
        content = (ROOT_DIR / "docs" / "index.html").read_text(encoding="utf-8")
        self.assertIn("v1.1.10", content)
        self.assertIn("GuitarAmpRecorder-macOS.zip", content)
        self.assertIn("GuitarAmpRecorder-Windows.zip", content)
        self.assertIn("GuitarAmpRecorder-macOS.zip.sha256", content)
        self.assertIn("GuitarAmpRecorder-Windows.zip.sha256", content)
        self.assertIn("/releases/latest/download/GuitarAmpRecorder-macOS.zip", content)
        self.assertIn("/releases/latest/download/GuitarAmpRecorder-Windows.zip", content)
        self.assertIn("Mikrofon/Ses Karti Testi (5 sn)", content)
        self.assertIn("Windows Ilk Acilis", content)
        self.assertIn("FIRST_RUN_GUIDE.md", content)
        self.assertIn("WINDOWS_RELEASE_CHECKLIST.md", content)
        self.assertIn("SUPPORT_FAQ.md", content)
        self.assertIn("SHA256", content)


if __name__ == "__main__":
    unittest.main()
