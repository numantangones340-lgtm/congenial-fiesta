#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
CHANGELOG_PATH = ROOT_DIR / "CHANGELOG.md"
VERSION_PATH = ROOT_DIR / "VERSION"


def read_version(explicit_version: str | None) -> str:
    if explicit_version:
        return explicit_version.strip()
    return VERSION_PATH.read_text(encoding="utf-8").strip()


def extract_release_section(changelog_text: str, version: str) -> str:
    pattern = re.compile(
        rf"^## \[{re.escape(version)}\][^\n]*\n(?P<body>.*?)(?=^## \[|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(changelog_text)
    if not match:
        raise ValueError(f"CHANGELOG.md icinde [{version}] bolumu bulunamadi.")
    return match.group("body").strip()


def build_release_notes(version: str, body: str) -> str:
    lines = [
        f"# Release Notes {version}",
        "",
        "Bu surumun detaylari `CHANGELOG.md` kaynagindan otomatik uretildi.",
        "",
        body,
    ]
    return "\n".join(lines).strip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate GitHub release notes from CHANGELOG.md.")
    parser.add_argument("--version", help="Version to render. Defaults to VERSION file.")
    parser.add_argument(
        "--output",
        help="Destination file path. Defaults to stdout when omitted.",
    )
    args = parser.parse_args()

    version = read_version(args.version)
    changelog_text = CHANGELOG_PATH.read_text(encoding="utf-8")
    body = extract_release_section(changelog_text, version)
    rendered = build_release_notes(version, body)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
