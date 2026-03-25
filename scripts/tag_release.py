#!/usr/bin/env python3
"""Create the release tag from VERSION on the current main commit."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )


def read_version() -> str:
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if not version:
        raise RuntimeError("VERSION file is empty")
    return version


def ensure_clean_worktree() -> None:
    if git("status", "--short").stdout.strip():
        raise RuntimeError("Git worktree is not clean. Commit or stash changes first.")


def ensure_on_main() -> None:
    branch = git("branch", "--show-current").stdout.strip()
    if branch != "main":
        raise RuntimeError(f"Expected branch 'main', got '{branch}'")


def refresh_origin_state() -> None:
    git("fetch", "--prune", "origin")


def ensure_head_matches_origin_main() -> None:
    head = git("rev-parse", "HEAD").stdout.strip()
    origin_main = git("rev-parse", "origin/main").stdout.strip()
    if head != origin_main:
        raise RuntimeError(
            "Current main branch is not aligned with origin/main. Pull or fast-forward main first."
        )


def ensure_changelog_has(version: str) -> None:
    heading = f"## [{version}]"
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    if heading not in changelog:
        raise RuntimeError(f"CHANGELOG.md does not contain {heading}")


def ensure_tag_absent(tag_name: str) -> None:
    if git("tag", "--list", tag_name).stdout.strip():
        raise RuntimeError(f"Tag {tag_name} already exists locally")
    if git("ls-remote", "--tags", "origin", f"refs/tags/{tag_name}").stdout.strip():
        raise RuntimeError(f"Tag {tag_name} already exists on origin")


def main() -> int:
    version = read_version()
    tag_name = f"v{version}"
    ensure_clean_worktree()
    ensure_on_main()
    refresh_origin_state()
    ensure_head_matches_origin_main()
    ensure_changelog_has(version)
    ensure_tag_absent(tag_name)
    git("tag", tag_name)
    print(tag_name)
    print("Tag created on current main commit. Push with:")
    print(f"git push origin {tag_name}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
