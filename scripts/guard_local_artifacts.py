#!/usr/bin/env python3
"""Pre-commit guard: refuse to stage secrets, personal uploads, or local artifacts.

pre-commit passes the staged file paths as arguments. Exits non-zero with an
explicit reason when a path must never enter the repository.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

FORBIDDEN = [
    (r"(^|/)\.jwt_secret$", "JWT signing secret"),
    (r"(^|/)user_registry\.json$", "user registry (API keys, password hashes)"),
    (r"(^|/)cookies?\d*\.txt$", "browser cookies"),
    (r"(^|/)\.env(\.[^/]*)?$", "environment file"),
    (r"^\.venv/", "virtualenv"),
    (r"(^|/)node_modules/", "node_modules"),
    (r"(^|/)uploads/", "uploaded user content"),
    (r"(^|/)graphify-out/", "tool cache"),
    (r"(^|/)\.DS_Store$", "macOS metadata"),
]

MAX_MB = 5


def main(argv: list[str]) -> int:
    failures: list[str] = []

    for path in argv:
        for pattern, reason in FORBIDDEN:
            if re.search(pattern, path):
                failures.append(f"  {path} — {reason}")
                break
        else:
            file = Path(path)
            if file.is_file() and file.stat().st_size > MAX_MB * 1024 * 1024:
                size_mb = file.stat().st_size / (1024 * 1024)
                failures.append(f"  {path} — {size_mb:.1f} MB exceeds {MAX_MB} MB limit")

    if failures:
        print("Refusing to commit (see .gitignore and remove these from the index):", file=sys.stderr)
        print("\n".join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
