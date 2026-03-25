import io
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from scripts import tag_release


class TagReleaseTests(unittest.TestCase):
    def test_read_version_rejects_empty_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "VERSION").write_text("\n", encoding="utf-8")
            with mock.patch.object(tag_release, "ROOT", root):
                with self.assertRaisesRegex(RuntimeError, "VERSION file is empty"):
                    tag_release.read_version()

    def test_ensure_clean_worktree_rejects_changes(self) -> None:
        dirty = subprocess.CompletedProcess(
            args=["git", "status", "--short"],
            returncode=0,
            stdout=" M README.md\n",
            stderr="",
        )
        with mock.patch.object(tag_release, "git", return_value=dirty):
            with self.assertRaisesRegex(RuntimeError, "Git worktree is not clean"):
                tag_release.ensure_clean_worktree()

    def test_ensure_on_main_rejects_other_branch(self) -> None:
        branch = subprocess.CompletedProcess(
            args=["git", "branch", "--show-current"],
            returncode=0,
            stdout="codex/next-task\n",
            stderr="",
        )
        with mock.patch.object(tag_release, "git", return_value=branch):
            with self.assertRaisesRegex(RuntimeError, "Expected branch 'main'"):
                tag_release.ensure_on_main()

    def test_ensure_head_matches_origin_main_rejects_mismatch(self) -> None:
        responses = {
            ("rev-parse", "HEAD"): subprocess.CompletedProcess(
                args=["git", "rev-parse", "HEAD"],
                returncode=0,
                stdout="abc123\n",
                stderr="",
            ),
            ("rev-parse", "origin/main"): subprocess.CompletedProcess(
                args=["git", "rev-parse", "origin/main"],
                returncode=0,
                stdout="def456\n",
                stderr="",
            ),
        }

        def fake_git(*args: str) -> subprocess.CompletedProcess[str]:
            return responses[args]

        with mock.patch.object(tag_release, "git", side_effect=fake_git):
            with self.assertRaisesRegex(RuntimeError, "not aligned with origin/main"):
                tag_release.ensure_head_matches_origin_main()

    def test_refresh_origin_state_fetches_pruned_origin(self) -> None:
        fetch = subprocess.CompletedProcess(
            args=["git", "fetch", "--prune", "origin"],
            returncode=0,
            stdout="",
            stderr="",
        )
        with mock.patch.object(tag_release, "git", return_value=fetch) as git_mock:
            tag_release.refresh_origin_state()

        git_mock.assert_called_once_with("fetch", "--prune", "origin")

    def test_ensure_changelog_has_rejects_missing_heading(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "CHANGELOG.md").write_text("## [1.1.2] - 2026-03-20\n", encoding="utf-8")
            with mock.patch.object(tag_release, "ROOT", root):
                with self.assertRaisesRegex(RuntimeError, r"CHANGELOG\.md does not contain ## \[1\.1\.3\]"):
                    tag_release.ensure_changelog_has("1.1.3")

    def test_ensure_tag_absent_rejects_existing_local_tag(self) -> None:
        existing = subprocess.CompletedProcess(
            args=["git", "tag", "--list", "v1.1.3"],
            returncode=0,
            stdout="v1.1.3\n",
            stderr="",
        )
        with mock.patch.object(tag_release, "git", return_value=existing):
            with self.assertRaisesRegex(RuntimeError, "Tag v1.1.3 already exists locally"):
                tag_release.ensure_tag_absent("v1.1.3")

    def test_ensure_tag_absent_rejects_existing_origin_tag(self) -> None:
        responses = {
            ("tag", "--list", "v1.1.3"): subprocess.CompletedProcess(
                args=["git", "tag", "--list", "v1.1.3"],
                returncode=0,
                stdout="",
                stderr="",
            ),
            ("ls-remote", "--tags", "origin", "refs/tags/v1.1.3"): subprocess.CompletedProcess(
                args=["git", "ls-remote", "--tags", "origin", "refs/tags/v1.1.3"],
                returncode=0,
                stdout="abc123\trefs/tags/v1.1.3\n",
                stderr="",
            ),
        }

        def fake_git(*args: str) -> subprocess.CompletedProcess[str]:
            return responses[args]

        with mock.patch.object(tag_release, "git", side_effect=fake_git):
            with self.assertRaisesRegex(RuntimeError, "Tag v1.1.3 already exists on origin"):
                tag_release.ensure_tag_absent("v1.1.3")

    def test_main_creates_tag_and_prints_push_hint(self) -> None:
        calls: list[tuple[str, ...]] = []

        def fake_git(*args: str) -> subprocess.CompletedProcess[str]:
            calls.append(args)
            if args == ("status", "--short"):
                return subprocess.CompletedProcess(args=list(args), returncode=0, stdout="", stderr="")
            if args == ("branch", "--show-current"):
                return subprocess.CompletedProcess(args=list(args), returncode=0, stdout="main\n", stderr="")
            if args == ("fetch", "--prune", "origin"):
                return subprocess.CompletedProcess(args=list(args), returncode=0, stdout="", stderr="")
            if args == ("rev-parse", "HEAD"):
                return subprocess.CompletedProcess(args=list(args), returncode=0, stdout="abc123\n", stderr="")
            if args == ("rev-parse", "origin/main"):
                return subprocess.CompletedProcess(args=list(args), returncode=0, stdout="abc123\n", stderr="")
            if args == ("tag", "--list", "v1.1.3"):
                return subprocess.CompletedProcess(args=list(args), returncode=0, stdout="", stderr="")
            if args == ("ls-remote", "--tags", "origin", "refs/tags/v1.1.3"):
                return subprocess.CompletedProcess(args=list(args), returncode=0, stdout="", stderr="")
            if args == ("tag", "v1.1.3"):
                return subprocess.CompletedProcess(args=list(args), returncode=0, stdout="", stderr="")
            raise AssertionError(f"Unexpected git call: {args}")

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "VERSION").write_text("1.1.3\n", encoding="utf-8")
            (root / "CHANGELOG.md").write_text("## [1.1.3] - 2026-03-21\n", encoding="utf-8")
            stdout = io.StringIO()
            with (
                mock.patch.object(tag_release, "ROOT", root),
                mock.patch.object(tag_release, "git", side_effect=fake_git),
                redirect_stdout(stdout),
            ):
                result = tag_release.main()

        self.assertEqual(result, 0)
        self.assertIn("v1.1.3", stdout.getvalue())
        self.assertIn("git push origin v1.1.3", stdout.getvalue())
        self.assertEqual(
            calls,
            [
                ("status", "--short"),
                ("branch", "--show-current"),
                ("fetch", "--prune", "origin"),
                ("rev-parse", "HEAD"),
                ("rev-parse", "origin/main"),
                ("tag", "--list", "v1.1.3"),
                ("ls-remote", "--tags", "origin", "refs/tags/v1.1.3"),
                ("tag", "v1.1.3"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
