#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


def sha256_for_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_checksum(path: Path) -> Path:
    checksum_path = Path(f"{path}.sha256")
    checksum_path.write_text(f"{sha256_for_file(path)}  {path.name}\n", encoding="utf-8")
    return checksum_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Write SHA256 checksum files next to release assets.")
    parser.add_argument("paths", nargs="+", help="Files to checksum.")
    args = parser.parse_args()

    for raw_path in args.paths:
        path = Path(raw_path)
        if not path.is_file():
            raise FileNotFoundError(f"Dosya bulunamadi: {path}")
        checksum_path = write_checksum(path)
        print(checksum_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
