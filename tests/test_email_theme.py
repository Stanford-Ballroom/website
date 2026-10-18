"""Figma semantic tokens must survive into portable email HTML safely."""
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HUGO = os.environ.get("HUGO", "hugo")


class Elements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.nodes = []

    def handle_starttag(self, tag, attrs):
        self.nodes.append((tag, dict(attrs)))

    def styles(self, tag=None, css_class=None):
        return [attrs.get("style", "") for name, attrs in self.nodes
                if (tag is None or name == tag)
                and (css_class is None or css_class in attrs.get("class", "").split())]


@unittest.skipUnless(shutil.which(HUGO), "Hugo is required for rendered-theme checks")
class EmailThemeTests(unittest.TestCase):
    def build(self, theme=None):
        with tempfile.TemporaryDirectory(prefix="ballroom-theme-") as tmp:
            content = Path(tmp) / "content" / "emails"
            content.mkdir(parents=True)
            params = {
                "title": "Theme fixture", "subject": "Theme fixture",
                "date": "2026-10-18T12:00:00-07:00", "draft": False,
                "url": "/emails/theme-fixture.html", "preheader": "Inline token check",
                "lessons": {"title": "Lessons", "tracks": [{"name": "Latin"}],
                            "rows": [{"time": "7:30 pm", "classes": ["Beginner"]}]},
            }
            if theme is not None:
                params["email_theme"] = theme
            body = '''
A [club link](https://www.stanfordballroom.com/).

## Section heading

> A useful reminder.

---

{{< email-lessons >}}

{{< email-notice tone="warning" title="Reminder" >}}
Bring comfortable shoes.
{{< /email-notice >}}

{{< email-event title="Practice" when="6 pm" where="Roble" >}}
Come practice.
{{< /email-event >}}

{{< email-button href="https://www.stanfordballroom.com/" label="Schedule" >}}

{{< email-photo src="https://raw.githubusercontent.com/entrohpy/stanford-ballroom/refs/heads/main/Text%20on%20Side%20Logo%20Black.png" alt="Club mark" width="552" >}}

{{< email-signoff >}}
'''
            (content / "theme-fixture.md").write_text(
                "---\n" + json.dumps(params) + "\n---\n" + body, encoding="utf-8")
            destination = Path(tmp) / "public"
            result = subprocess.run(
                [HUGO, "--environment", "email", "--contentDir", str(content.parent),
                 "--baseURL", "https://www.stanfordballroom.com/",
                 "--destination", str(destination)],
                cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            output = destination / "emails" / "theme-fixture.html"
            html = output.read_text(encoding="utf-8") if output.exists() else ""
            return result, html

    def test_defaults_keep_inline_email_fallbacks(self):
        result, html = self.build()
        self.assertEqual(result.returncode, 0, result.stdout)
        elements = Elements()
        elements.feed(html)
        self.assertIn("background:#f2f1ee", elements.styles("body")[0])
        self.assertTrue(any("font-size:17px;line-height:26px;color:#242421" in s
                            for s in elements.styles("table")))
        self.assertIn("font-size:30px;line-height:37px;color:#820000", elements.styles("h1")[0])
        self.assertTrue(any("bgcolor" in attrs and attrs["bgcolor"] == "#ffffff"
                            for tag, attrs in elements.nodes if tag == "td"))
        self.assertIn('width="600" align="center"', html)
        self.assertIn("mso-padding-alt:12px 18px", html)

    def test_edits_compile_inline_and_into_both_dark_mode_selectors(self):
        result, html = self.build({
            "light": {"background": "#112233", "card": "#ffffee", "text": "#223344",
                      "heading": "#550011", "link": "#772244", "notice": "#fef0cc",
                      "warning": "#884400", "table_border": "#aabbcc", "table_header": "#eeeecc"},
            "dark": {"card": "#18191a", "text": "#fff1ee", "link": "#ffbbdd"},
            "type": {"body_size": 18, "body_line": 28, "title_size": 32, "title_line": 40,
                     "heading_size": 24, "heading_line": 32},
            "layout": {"content_padding": 28},
        })
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("ZgotmplZ", html)
        self.assertNotIn("var(--", html)
        elements = Elements()
        elements.feed(html)
        self.assertIn("background:#112233", elements.styles("body")[0])
        self.assertTrue(any("font-size:18px;line-height:28px;color:#223344" in s
                            for s in elements.styles("table")))
        self.assertIn("font-size:32px;line-height:40px;color:#550011", elements.styles("h1")[0])
        self.assertTrue(any("padding:0 28px 24px" in s for s in elements.styles(css_class="email-content")))
        self.assertTrue(any("background:#fef0cc" in s and "solid #884400" in s
                            for s in elements.styles(css_class="email-notice")))
        self.assertTrue(any("background:#772244" in s for s in elements.styles(css_class="email-button")))
        self.assertTrue(any("border:1px solid #aabbcc" in s and "background:#eeeecc" in s
                            for s in elements.styles("th")))
        photo = next(attrs for tag, attrs in elements.nodes
                     if tag == "img" and attrs.get("alt") == "Club mark")
        self.assertEqual(photo["width"], "544")
        self.assertIn("max-width:544px", photo["style"])
        self.assertIn("@media (prefers-color-scheme:dark)", html)
        self.assertIn("[data-ogsc] .email-card { background:#18191a !important; color:#fff1ee !important; }", html)
        self.assertIn("[data-ogsc] .email-link { color:#ffbbdd !important; }", html)
        self.assertIn("Mailing list settings", html)
        self.assertIn("Announcement archive", html)

    def test_invalid_tokens_fail_at_hugo_boundary(self):
        for theme in (
            {"light": {"link": "red;background:url(https://example.com/x)"}},
            {"light": {"card": "#fff"}},
            {"layout": {"width": 900}},
            {"type": {"body_size": 99}},
            {"type": {"title_size": 40, "title_line": 30}},
            {"dark": []},
            False,
        ):
            with self.subTest(theme=theme):
                result, _ = self.build(theme)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("email_theme", result.stdout)


if __name__ == "__main__":
    unittest.main()
