#!/usr/bin/env python3
"""Validate already-built announcements. Does not fetch URLs or send mail."""
import sys
import hashlib
import argparse
from pathlib import Path
from export_email import inspect_email


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path("public"))
    parser.add_argument("--email-only", action="store_true", help="Reject all JavaScript, including the hosted WhatsApp helper")
    args = parser.parse_args()
    root = args.root
    files = sorted((root / "emails").rglob("*.html"))
    issues = [path for path in files if path.name != "index.html"]
    if not issues:
        raise SystemExit("No email issues found. Build with --buildDrafts to validate the example issues.")
    failed = False
    for path in issues:
        try:
            parsed = inspect_email(path.read_text(encoding="utf-8"), allow_browser_script=not args.email_only)
            if len(parsed.browser_scripts) > 1:
                raise ValueError("Duplicate browser helper")
            for src in parsed.browser_scripts:
                asset = root / "emails" / Path(src).name
                if not asset.is_file() or hashlib.sha256(asset.read_bytes()).hexdigest() != asset.name.split(".")[-2]:
                    raise ValueError("Missing or mismatched WhatsApp browser asset")
            if not parsed.plain_text().strip():
                raise ValueError("Empty plain-text alternative")
            print(f"OK {path.relative_to(root)}")
        except ValueError as error:
            failed = True
            print(f"FAIL {path}: {error}", file=sys.stderr)
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
