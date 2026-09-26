#!/usr/bin/env python3
"""Validate already-built announcements. Does not fetch URLs or send mail."""
import sys
from pathlib import Path
from export_email import inspect_email


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "public")
    files = sorted((root / "emails").rglob("*.html"))
    issues = [path for path in files if path.name != "index.html"]
    if not issues:
        raise SystemExit("No email issues found. Build with --buildDrafts to validate the example issues.")
    failed = False
    for path in issues:
        try:
            parsed = inspect_email(path.read_text(encoding="utf-8"))
            if not parsed.plain_text().strip():
                raise ValueError("Empty plain-text alternative")
            print(f"OK {path.relative_to(root)}")
        except ValueError as error:
            failed = True
            print(f"FAIL {path}: {error}", file=sys.stderr)
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
