#!/usr/bin/env python3
"""Publish validated, inline-only copy pages beside built email webpages.

Build Hugo once with --environment email, then pass that output as --email-dir.
Only issues also present in --site-dir are published, so an inclusive test build
cannot accidentally publish drafts or future issues in the production site.
"""
import argparse
from html.parser import HTMLParser
from pathlib import Path
import sys

from export_email import inspect_email, make_copy_html


class AnnouncementMarker(HTMLParser):
    def __init__(self):
        super().__init__()
        self.found = False

    def handle_starttag(self, tag, attrs):
        if dict(attrs).get("id") == "email-announcement":
            self.found = True


def is_announcement(html):
    marker = AnnouncementMarker()
    marker.feed(html)
    return marker.found


def build_copy_pages(email_dir, site_dir):
    """Preflight every selected issue before writing any copy pages."""
    email_dir, site_dir = Path(email_dir), Path(site_dir)
    if not (email_dir / "emails").is_dir():
        raise ValueError(f"No built email directory: {email_dir / 'emails'}")
    if not site_dir.is_dir():
        raise ValueError(f"No built website directory: {site_dir}")
    pending = []
    issues = 0
    for source in sorted((email_dir / "emails").rglob("*.html")):
        if source.name.endswith(".copy.html"):
            continue
        html = source.read_text(encoding="utf-8")
        if not is_announcement(html):
            continue
        issues += 1
        relative = source.relative_to(email_dir)
        hosted = site_dir / relative
        if not hosted.is_file():
            continue
        if not is_announcement(hosted.read_text(encoding="utf-8")):
            raise ValueError(f"Hosted path is not an announcement: {relative}")
        # Reject scripts, private/relative asset URLs, and malformed shells
        # before any copy page can become part of a deployment artifact.
        inspect_email(html, require_shell=True)
        copy = make_copy_html(html)
        inspect_email(copy, require_shell=True)
        pending.append((hosted.with_suffix(".copy.html"), copy))
    if not issues:
        raise ValueError("No standalone announcements found in the email build")
    for target, html in pending:
        target.write_text(html, encoding="utf-8")
    return [target for target, _ in pending]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email-dir", required=True, type=Path,
                        help="Hugo output built with --environment email")
    parser.add_argument("--site-dir", required=True, type=Path,
                        help="Website output that will be deployed")
    args = parser.parse_args()
    try:
        paths = build_copy_pages(args.email_dir, args.site_dir)
        for path in paths:
            print(f"OK {path}")
        print(f"Published {len(paths)} copy page(s).")
    except (OSError, ValueError) as error:
        print(f"Copy-page build failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
