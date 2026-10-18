#!/usr/bin/env python3
"""Build a Hugo announcement and export HTML, plain text, and an unsent EML.

Uses Python's standard library and the site's existing Hugo installation.
Never contacts a mail server or chooses recipients.
"""
import argparse
from email.message import EmailMessage
from email.policy import SMTP
from html.parser import HTMLParser
import ipaddress
from pathlib import Path
import os
import re
import subprocess
import tempfile
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
BLOCK = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "table", "tr", "ul", "ol"}
ACTIVE = {"base", "iframe", "object", "embed", "form", "input", "button", "textarea", "select", "video", "audio", "canvas", "svg", "picture", "source"}
UNSUPPORTED_IMAGES = {".svg", ".svgz", ".webp", ".avif", ".heic", ".heif"}


def _url_error(value, *, image=False, allow_preview_images=False):
    """Validate durable public URLs without making network requests."""
    value = value or ""
    if any(char in value for char in "\r\n\t"):
        return "Control character in email URL"
    try:
        url = urlsplit(value)
        # Accessing these properties also checks malformed ports and IPv6 hosts.
        hostname, port = url.hostname, url.port
    except ValueError:
        return f"Malformed email URL: {value}"
    if image and allow_preview_images and value.startswith("/") and not value.startswith("//"):
        return None
    allowed = {"https"} if image else {"https", "http", "mailto", "tel"}
    if url.scheme.lower() not in allowed or (url.scheme in {"https", "http"} and not hostname):
        kind = "image URL (requires absolute HTTPS)" if image else "URL"
        return f"Non-absolute or unsupported {kind}: {value}"
    if url.username or url.password:
        return f"Credentials in email URL: {value}"
    if hostname:
        host = hostname.lower().rstrip(".")
        if host in {"localhost", "localhost.localdomain"} or host.endswith((".localhost", ".local", ".internal")):
            return f"Local URL in email: {value}"
        try:
            if not ipaddress.ip_address(host).is_global:
                return f"Local/private address in email: {value}"
        except ValueError:
            # Browsers also interpret decimal, octal and hexadecimal IPv4 forms.
            # Require canonical IP literals so loopback cannot use those aliases.
            if re.fullmatch(r"(?:0[xX][0-9a-fA-F]+|[0-9]+)(?:\.(?:0[xX][0-9a-fA-F]+|[0-9]+)){0,3}", host):
                return f"Non-canonical numeric host in email: {value}"
        if image and (host == "figma.com" or host.endswith((".figma.com", ".figmausercontent.com"))
                      or ("figma" in host and host.endswith(".amazonaws.com"))):
            return f"Temporary Figma image URL; commit the image and publish it first: {value}"
    if image and Path(unquote(url.path).lower()).suffix in UNSUPPORTED_IMAGES:
        return f"Unsupported email image format; use PNG/JPEG/GIF: {value}"
    return None


def _style_error(css):
    # CSS images and remote fonts do not reliably survive Outlook copy/paste.
    # Images must use the checked <img> path, with an alt and inline dimensions.
    if re.search(r"url\s*\(|@import\b|@font-face\b|expression\s*\(|javascript\s*:", css, re.I):
        return "External/dynamic CSS or CSS images in email; use inline styles and <img>"
    if re.search(r"(?:^|[;{])\s*(?:display\s*:\s*(?:inline-)?(?:flex|grid)\b|position\s*:\s*(?:absolute|fixed)\b)", css, re.I):
        return "Unsupported email layout CSS; use the table-based email components"
    return None


class EmailHTML(HTMLParser):
    """Check mail portability while deriving text from the exact rendered HTML."""

    def __init__(self, allow_browser_script=False, allow_preview_images=False):
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
        self.allow_preview_images = allow_preview_images
        self.classes = set()
        self.image_attrs = []
        self.anchor_labels = []
        self.presentation_tables = []
        self.css = []

    @property
    def hidden(self):
        return bool(self.stack and self.stack[-1][1])

    def handle_starttag(self, tag, attrs):
        attrs = {key: value or "" for key, value in attrs}
        self.classes.update(attrs.get("class", "").split())
        if tag in ACTIVE:
            self.errors.append(f"Unexpected {tag}: active or unsupported content in email")
        if tag == "meta" and attrs.get("http-equiv", "").lower() == "refresh":
            self.errors.append("Unexpected redirect meta tag in email")
        if "srcset" in attrs or "background" in attrs:
            self.errors.append("Unchecked alternate/CSS image source; use a single <img src> with inline styles")
        if attrs.get("style"):
            error = _style_error(attrs["style"])
            if error:
                self.errors.append(error)
        if tag == "table" and attrs.get("role") == "presentation":
            self.presentation_tables.append(attrs)
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
                error = _url_error(attrs[key], image=key == "src",
                                   allow_preview_images=self.allow_preview_images)
                if error:
                    self.errors.append(error)
        if tag == "link" and attrs.get("rel") == "canonical":
            self.canonical = attrs.get("href", "")
        if tag == "meta" and attrs.get("name") == "description":
            self.preheader = attrs.get("content", "")
        if tag == "img":
            self.images.append(attrs.get("src", ""))
            self.image_attrs.append(attrs)
            if not attrs.get("src"):
                self.errors.append("Image missing src")
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

    def handle_comment(self, data):
        # Outlook renders HTML inside MSO conditionals, so inspect that payload
        # for URL/active-content problems even though it is a comment elsewhere.
        if re.match(r"\[if\s", data, re.I) and "]>" in data:
            conditional = EmailHTML(allow_preview_images=self.allow_preview_images)
            conditional.feed(data.split("]>", 1)[1].split("<![endif]", 1)[0])
            self.errors.extend(conditional.errors)
            error = _style_error("".join(conditional.css))
            if error:
                self.errors.append(error)
            self.image_attrs.extend(conditional.image_attrs)

    def handle_endtag(self, tag):
        if not self.hidden:
            if tag == "a" and self.links:
                url, start = self.links.pop()
                label = "".join(self.parts[start:]).strip()
                self.anchor_labels.append((label, url))
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
        if self.stack and self.stack[-1][0] == "style":
            self.css.append(text)
        if self.stack and self.stack[-1][0] == "title":
            self.title.append(text)
        if not self.hidden:
            self.parts.append(re.sub(r"\s+", " ", text))

    def plain_text(self):
        lines = [re.sub(r"[ \t]+", " ", line).strip().strip("|").strip()
                 for line in "".join(self.parts).splitlines()]
        return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip() + "\n"


def inspect_email(html, *, allow_browser_script=False, allow_preview_images=False, require_shell=False):
    parsed = EmailHTML(allow_browser_script=allow_browser_script,
                       allow_preview_images=allow_preview_images)
    parsed.feed(html)
    parsed.close()
    css_error = _style_error("".join(parsed.css))
    if css_error:
        parsed.errors.append(css_error)
    if require_shell:
        if not any("max-width:600px" in re.sub(r"\s+", "", attrs.get("style", ""))
                   and "font-family:" in attrs.get("style", "")
                   for attrs in parsed.presentation_tables):
            parsed.errors.append("Missing 600px presentation table and inline font fallback")
        if not re.search(r"<!--\[if mso\]>.*?width=[\"']?600", html, re.I | re.S):
            parsed.errors.append("Missing Outlook conditional width wrapper")
        if not {"email-summary", "email-logo-light", "email-content"}.issubset(parsed.classes):
            parsed.errors.append("Missing email summary, logo, or content shell")
        if not any(label == "Mailing list settings" and url.startswith("https://")
                   for label, url in parsed.anchor_labels):
            parsed.errors.append("Missing mailing list settings/unsubscribe footer")
        for attrs in parsed.image_attrs:
            inline = re.sub(r"\s+", "", attrs.get("style", "").lower())
            if not re.fullmatch(r"[1-9][0-9]*", attrs.get("width", "")) or not all(
                    marker in inline for marker in ("display:block", "height:auto", "max-width:")):
                parsed.errors.append("Image missing inline responsive dimensions and Outlook width fallback")
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
        raise ValueError("\n".join(dict.fromkeys(parsed.errors)))
    return parsed


class _CopyHTML(HTMLParser):
    """Preserve the inline baseline, omitting head CSS and its dark-only logo."""

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.output = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if self.skip_depth:
            if tag not in VOID:
                self.skip_depth += 1
            return
        attrs = {key: value or "" for key, value in attrs}
        if tag in {"style", "script"} or "email-logo-dark" in attrs.get("class", "").split():
            self.skip_depth = 1
            return
        if tag == "meta" and attrs.get("name", "").lower() in {"color-scheme", "supported-color-schemes"}:
            return
        self.output.append(self.get_starttag_text())

    def handle_startendtag(self, tag, attrs):
        attrs = {key: value or "" for key, value in attrs}
        if (self.skip_depth or tag in {"style", "script"}
                or "email-logo-dark" in attrs.get("class", "").split()
                or (tag == "meta" and attrs.get("name", "").lower() in {"color-scheme", "supported-color-schemes"})):
            return
        self.output.append(self.get_starttag_text())

    def handle_endtag(self, tag):
        if self.skip_depth:
            self.skip_depth -= 1
        else:
            self.output.append(f"</{tag}>")

    def handle_data(self, data):
        if not self.skip_depth:
            self.output.append(data)

    def handle_entityref(self, name):
        self.handle_data(f"&{name};")

    def handle_charref(self, name):
        self.handle_data(f"&#{name};")

    def handle_comment(self, data):
        if not self.skip_depth:
            self.output.append(f"<!--{data}-->")

    def handle_decl(self, decl):
        if not self.skip_depth:
            self.output.append(f"<!{decl}>")


def make_copy_html(html):
    """Create an inline-only, single-logo browser page for Outlook rich-text paste.

    The input must be the script-free email-environment build. Unsupported HTML
    is rejected before transformation, so this is not a general HTML sanitizer.
    Both versions contain the same summary, body, links and list-settings footer.
    """
    original = inspect_email(html, require_shell=True)
    copier = _CopyHTML()
    copier.feed(html)
    copier.close()
    copied = "".join(copier.output)
    result = inspect_email(copied, require_shell=True)
    if original.plain_text() != result.plain_text():
        raise ValueError("Copy/paste export changed the email text")
    if "email-logo-dark" in result.classes or "<style" in copied.lower():
        raise ValueError("Copy/paste export retains head-dependent styling")
    return copied


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("issue", help="Quarter/issue, e.g. spring26/week1")
    parser.add_argument("--draft", action="store_true", help="Explicitly include drafts for preview/test exports")
    parser.add_argument("--output", type=Path, default=ROOT / "email-dist")
    parser.add_argument("--copy-paste", action="store_true",
                        help="Also create .copy.html with inline baseline styling and one logo for rendered copying into Outlook")
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
            parsed = inspect_email(html, require_shell=True)
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
            if args.copy_paste:
                copy_path = target.with_suffix(".copy.html")
                copy_path.write_text(make_copy_html(html), encoding="utf-8")
                print(copy_path)
            print(f"Subject: {message['Subject']}")
            print(f"HTML size: {len(html.encode()):,} bytes")
            if len(html.encode()) > 90000:
                print("Warning: large email; shorten it to reduce clipping risk.")
            print("Publish the issue and its images before sending. Review the draft in your mail client and send yourself a test.")
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Email export failed: {error}\n")


if __name__ == "__main__":
    main()

