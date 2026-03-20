#!/usr/bin/env python3
"""Generate a GitHub release body from VERSION and CHANGELOG.md."""

from __future__ import annotations

import argparse
import pathlib
import re
import sys


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate docs/RELEASE_BODY.md from VERSION and CHANGELOG.md."
    )
    parser.add_argument(
        "--version-file",
        default="VERSION",
        help="Path to the VERSION file. Default: VERSION",
    )
    parser.add_argument(
        "--changelog",
        default="CHANGELOG.md",
        help="Path to the changelog file. Default: CHANGELOG.md",
    )
    parser.add_argument(
        "--output",
        default="docs/RELEASE_BODY.md",
        help="Path to the generated release body. Default: docs/RELEASE_BODY.md",
    )
    return parser.parse_args()


def load_version(version_path: pathlib.Path) -> str:
    version = version_path.read_text(encoding="utf-8").strip()
    if not version:
        raise ValueError(f"{version_path} is empty")
    return version


def extract_changelog_section(changelog_text: str, version: str) -> str:
    pattern = re.compile(
        rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## \[|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(changelog_text)
    if not match:
        raise ValueError(f"Could not find changelog section for version {version}")
    return match.group(1).strip()


def build_release_body(version: str, section: str) -> str:
    return (
        f"# Release {version}\n\n"
        "Bu release body `CHANGELOG.md` kaynagindan otomatik uretilmistir.\n\n"
        f"{section}\n"
    )


def main() -> int:
    args = parse_args()
    root = pathlib.Path.cwd()
    version_path = root / args.version_file
    changelog_path = root / args.changelog
    output_path = root / args.output

    version = load_version(version_path)
    changelog_text = changelog_path.read_text(encoding="utf-8")
    section = extract_changelog_section(changelog_text, version)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_release_body(version, section), encoding="utf-8")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
