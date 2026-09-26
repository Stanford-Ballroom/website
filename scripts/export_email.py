#!/usr/bin/env python3
"""Build a Hugo announcement and export HTML, plain text, and an unsent EML.

Uses Python's standard library and the site's existing Hugo installation.
Never contacts a mail server or chooses recipients.
"""
import argparse
from email.message import EmailMessage
from email.policy import SMTP
from html.parser import HTMLParser
from pathlib import Path
import os
import re
import subprocess
import tempfile
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
BLOCK = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "table", "tr", "ul", "ol"}


class EmailHTML(HTMLParser):
    """Check mail portability while deriving text from the exact rendered HTML."""

    def __init__(self, allow_browser_script=False):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.parts = []
        self.title = []
        self.links = []
        self.errors = []
        self.canonical = ""
        self.preheader = ""
        self.images = []
        self.allow_browser_script = allow_browser_script
        self.browser_scripts = []

    @property
    def hidden(self):
        return bool(self.stack and self.stack[-1][1])

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        hidden = self.hidden or tag in {"head", "style", "script"} or bool({"email-preheader", "email-logo-dark"}.intersection(attrs.get("class", "").split()))
        browser_script = (self.allow_browser_script and tag == "script"
                          and set(attrs) == {"src", "defer", "data-email-browser"}
                          and re.fullmatch(r"/(?:[^/?#]+/)*emails/whatsapp\.[0-9a-f]{64}\.js", attrs.get("src") or ""))
        if browser_script:
            self.browser_scripts.append(attrs["src"])
        if (tag == "script" and not browser_script) or (tag == "link" and attrs.get("rel") == "stylesheet"):
            self.errors.append(f"Unexpected {tag}: email must not depend on JavaScript or external CSS")
        if any(key.startswith("on") for key in attrs):
            self.errors.append("Unexpected JavaScript event handler")
        for key in ("href", "src"):
            if browser_script and key == "src":
                continue
            if key in attrs:
                url = urlsplit(attrs[key])
                allowed = {"https", "http", "mailto", "tel"} if key == "href" else {"https", "http"}
                if url.scheme not in allowed or (url.scheme in {"https", "http"} and not url.netloc):
                    self.errors.append(f"Non-absolute or unsupported {key}: {attrs[key]}")
                if url.hostname in {"localhost", "127.0.0.1", "0.0.0.0"}:
                    self.errors.append(f"Local URL in email: {attrs[key]}")
        if tag == "link" and attrs.get("rel") == "canonical":
            self.canonical = attrs.get("href", "")
        if tag == "meta" and attrs.get("name") == "description":
            self.preheader = attrs.get("content", "")
        if tag == "img":
            self.images.append(attrs.get("src", ""))
            if not attrs.get("alt", "").strip():
                self.errors.append("Image missing descriptive alt text")
            if not hidden:
                self.parts.append(f"\n[Image: {attrs.get('alt', '')}] {attrs.get('src', '')}\n")
        if not hidden:
            if tag in BLOCK or tag in {"br", "hr", "li"}:
                # Keep instructor names on the same line as their table header.
                in_cell = any(name in {"td", "th"} for name, _ in self.stack)
                self.parts.append(" " if tag == "br" and in_cell and any(name == "thead" for name, _ in self.stack) else "\n")
            if tag == "li":
                self.parts.append("• ")
            if tag == "a":
                self.links.append((attrs.get("href", ""), len(self.parts)))
        if tag not in VOID:
            self.stack.append((tag, hidden))

    def handle_endtag(self, tag):
        if not self.hidden:
            if tag == "a" and self.links:
                url, start = self.links.pop()
                label = "".join(self.parts[start:]).strip()
                if url and label != url and label != url.removeprefix("mailto:"):
                    self.parts.append(f" <{url}>")
            if tag in BLOCK or tag == "li":
                self.parts.append("\n")
            if tag in {"td", "th"}:
                self.parts.append(" | ")
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break

    def handle_data(self, text):
        if self.stack and self.stack[-1][0] == "title":
            self.title.append(text)
        if not self.hidden:
            self.parts.append(re.sub(r"\s+", " ", text))

    def plain_text(self):
        lines = [re.sub(r"[ \t]+", " ", line).strip().strip("|").strip()
                 for line in "".join(self.parts).splitlines()]
        return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip() + "\n"


def inspect_email(html, *, allow_browser_script=False):
    parsed = EmailHTML(allow_browser_script=allow_browser_script)
    parsed.feed(html)
    if not "".join(parsed.title).strip():
        parsed.errors.append("Missing subject/title")
    if not parsed.preheader.strip():
        parsed.errors.append("Missing preheader")
    elif not parsed.plain_text().startswith(re.sub(r"\s+", " ", parsed.preheader).strip()):
        parsed.errors.append("Summary must be the first visible body text, so it survives rendered copy/paste")
    if not parsed.canonical.endswith(".html"):
        parsed.errors.append("Missing canonical .html URL")
    if any(marker in html for marker in ("ZgotmplZ", "HAHAHUGOSHORTCODE", "{{<", "{{%")):
        parsed.errors.append("Unresolved template/shortcode output")
    if parsed.errors:
        raise ValueError("\n".join(parsed.errors))
    return parsed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("issue", help="Quarter/issue, e.g. spring26/week1")
    parser.add_argument("--draft", action="store_true", help="Explicitly include drafts for preview/test exports")
    parser.add_argument("--output", type=Path, default=ROOT / "email-dist")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9-]+/[a-z0-9-]+", args.issue):
        parser.error("Use quarter/issue with lowercase letters, numbers, and hyphens")
    try:
        with tempfile.TemporaryDirectory(prefix="ballroom-email-") as build:
            # The hosted page has a browser-only WhatsApp helper. Email exports
            # must not contain that script, its UI, or any other JavaScript.
            command = [os.environ.get("HUGO", "hugo"), "--environment", "email", "--minify", "--destination", build]
            if args.draft:
                command.append("--buildDrafts")
            subprocess.run(command, cwd=ROOT, check=True)
            rendered = Path(build) / "emails" / f"{args.issue}.html"
            if not rendered.is_file():
                parser.error("Issue was not built. Check its path, .html URL, date, and draft flag; use --draft to preview drafts.")
            html = rendered.read_text(encoding="utf-8")
            parsed = inspect_email(html)
            text = parsed.plain_text()
            # X-Unsent asks clients that support it to open a draft. No To/From:
            # the sender must select their account and recipients in their client.
            message = EmailMessage(policy=SMTP)
            message["Subject"] = "".join(parsed.title).strip()
            message["X-Unsent"] = "1"
            message.set_content(text)
            message.add_alternative(html, subtype="html")
            target = args.output / args.issue
            target.parent.mkdir(parents=True, exist_ok=True)
            for suffix, content in (("html", html.encode()), ("txt", text.encode()), ("eml", message.as_bytes())):
                path = target.with_suffix(f".{suffix}")
                path.write_bytes(content)
                print(path)
            print(f"Subject: {message['Subject']}")
            print(f"HTML size: {len(html.encode()):,} bytes")
            if len(html.encode()) > 90000:
                print("Warning: large email; shorten it to reduce clipping risk.")
            print("Publish the issue and its images before sending. Review the draft in your mail client and send yourself a test.")
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Email export failed: {error}\n")


if __name__ == "__main__":
    main()
