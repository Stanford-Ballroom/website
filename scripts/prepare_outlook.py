#!/usr/bin/env python3
"""Publish validated HTML draft payloads from a script-free Hugo email build."""
import argparse
import json
from pathlib import Path
from export_email import inspect_email


def prepare(source: Path, destination: Path):
    emails = source / "emails"
    paths = sorted(path for path in emails.rglob("*.html") if path.name != "index.html")
    if not paths:
        raise ValueError("No built email issues found in " + str(emails))
    count = 0
    for path in paths:
        html = path.read_text(encoding="utf-8")
        parsed = inspect_email(html)
        target = destination / "outlook" / "issues" / path.relative_to(emails).with_suffix(".json")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({
            "schemaVersion": 1,
            "subject": "".join(parsed.title).strip(),
            "html": html,
        }, ensure_ascii=False), encoding="utf-8")
        count += 1
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    try:
        count = prepare(args.source, args.destination)
    except (OSError, ValueError) as error:
        parser.exit(1, str(error) + "\n")
    print("Prepared " + str(count) + " portable Outlook draft payloads.")


if __name__ == "__main__":
    main()
