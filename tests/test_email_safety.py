"""Production URL boundaries and the rendered-copy fallback do not send mail."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from export_email import inspect_email, make_copy_html


SHELL = '''<!doctype html><html lang="en"><head><title>Week 5</title>
<meta name="description" content="Monday lessons &amp; Friday practice">
<link rel="canonical" href="https://ballroom.stanford.edu/emails/fall26/week5.html">
<style>@media (prefers-color-scheme:dark) {{
.email-logo-light {{display:none!important}} .email-logo-dark {{display:block!important}}
.email-content {{background:#202327!important;color:#eeeeef!important}}
}}</style></head><body style="background:#f2f1ee">
<!--[if mso]><table role="presentation" width="600"><tr><td><![endif]-->
<table role="presentation" width="100%" style="max-width:600px;font-family:Arial,Helvetica,sans-serif">
<tr><td><p class="email-summary">Monday lessons &amp; Friday practice</p>
<div class="email-logo-light"><a href="https://ballroom.stanford.edu/">
<img src="https://ballroom.stanford.edu/logo.png" width="320" alt="Stanford Ballroom"
style="display:block;width:100%;max-width:320px;height:auto;border:0"></a></div>
<!--[if !mso]><!--><div class="email-logo-dark" style="display:none;mso-hide:all">
<a href="https://ballroom.stanford.edu/"><img src="https://ballroom.stanford.edu/white.png"
width="320" alt="Stanford Ballroom" style="display:block;width:100%;max-width:320px;height:auto;border:0"></a>
</div><!--<![endif]--></td></tr>
<tr><td id="email-announcement" class="email-content" style="background:#ffffff;padding:24px;color:#242421">
<h1 style="font-family:Georgia,serif">Week 5</h1><p>Happy Week 5! &copy; &#169;</p>
<p><a href="https://ballroom.stanford.edu/schedule/">Schedule</a></p>{extra}</td></tr>
<tr><td><a href="https://mailman.stanford.edu/mailman/listinfo/ballroom-at-stanford">Mailing list settings</a>
<a href="https://ballroom.stanford.edu/emails/">Announcement archive</a></td></tr></table>
<!--[if mso]></td></tr></table><![endif]--></body></html>'''


def image(src, **attrs):
    attributes = {"src": src, "alt": "Team photograph", "width": "552",
                  "style": "display:block;width:100%;max-width:552px;height:auto;border:0"}
    attributes.update(attrs)
    return "<img " + " ".join(f'{name}="{value}"' for name, value in attributes.items()) + ">"


class EmailSafetyTests(unittest.TestCase):
    def test_copy_preserves_text_links_footer_and_inline_styles(self):
        original = SHELL.format(extra=image("https://ballroom.stanford.edu/team.jpg"))
        copied = make_copy_html(original)
        before = inspect_email(original, require_shell=True)
        after = inspect_email(copied, require_shell=True)
        self.assertEqual(before.plain_text(), after.plain_text())
        self.assertEqual(before.anchor_labels, after.anchor_labels)
        self.assertEqual(len(after.images), len(before.images) - 1)
        self.assertNotIn("<style", copied)
        self.assertNotIn("email-logo-dark", copied)
        self.assertIn('background:#ffffff;padding:24px;color:#242421', copied)
        self.assertIn("<!--[if mso]>", copied)
        self.assertIn("&copy; &#169;", copied)
        meta_html = original.replace("</head>", '<meta name="color-scheme" content="light dark" /></head>')
        self.assertNotIn('name="color-scheme"', make_copy_html(meta_html))
        self.assertTrue(after.plain_text().startswith("Monday lessons & Friday practice"))

    def test_production_rejects_unpublished_or_incompatible_images(self):
        sources = ["/images/team.png", "images/team.png", "//example.test/team.png",
                   "http://example.test/team.png", "https://localhost/team.png",
                   "https://preview.localhost/team.png", "https://127.0.0.2/team.png",
                   "https://[::1]/team.png", "https://10.0.0.1/team.png",
                   "https://2130706433/team.png", "https://0177.0.0.1/team.png",
                   "https://figma.com/api/mcp/asset/123", "https://s3-alpha-sig.figma.com/img/123.png",
                   "https://figma-alpha-api.s3.us-west-2.amazonaws.com/images/123.png",
                   "data:image/png;base64,AAA", "blob:https://figma.com/123",
                   "https://example.test/team.svg", "https://example.test/team.webp?size=500",
                   "https://example.test/team.AVIF", "https://example.test/team%2Esvg",
                   "https://user:password@example.test/team.png", "https://[bad/team.png"]
        for src in sources:
            with self.subTest(src=src), self.assertRaises(ValueError):
                inspect_email(SHELL.format(extra=image(src)), require_shell=True)

    def test_explicit_preview_mode_allows_only_root_relative_local_images(self):
        html = SHELL.format(extra=image("/pr-preview-10/images/team.png"))
        preview = inspect_email(html, allow_preview_images=True, require_shell=True)
        self.assertIn("/pr-preview-10/images/team.png", preview.images)
        for src in ["images/team.png", "http://localhost:1313/team.png", "//example.test/team.png"]:
            with self.subTest(src=src), self.assertRaises(ValueError):
                inspect_email(SHELL.format(extra=image(src)), allow_preview_images=True)

    def test_rejects_active_content_and_unchecked_sources(self):
        extras = ['<iframe src="https://example.test/"></iframe>', '<form action="https://example.test/"></form>',
                  '<svg><text>logo</text></svg>', '<base href="https://example.test/">',
                  '<script>alert(1)</script>', '<p onclick="alert(1)">Click</p>',
                  '<link rel="stylesheet" href="https://example.test/style.css">',
                  '<p style="background:url(https://example.test/image.png)">Photo</p>',
                  '<style>@import "https://example.test/style.css";</style>',
                  '<style>@font-face {font-family:Custom;src:url(https://example.test/font.woff)}</style>',
                  '<p style="display:grid">Cards</p>', '<p style="position:absolute">Absolute</p>',
                  image("https://example.test/team.png", srcset="https://example.test/team.webp 2x"),
                  '<!--[if mso]><img src="http://localhost/team.png"><![endif]-->']
        for extra in extras:
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                inspect_email(SHELL.format(extra=extra), require_shell=True)

    def test_shell_and_image_fallbacks_are_required_for_sendable_exports(self):
        html = SHELL.format(extra="")
        changes = [('Mailing list settings', 'Settings'),
                   ('max-width:600px', 'max-width:100%'),
                   ('<!--[if mso]><table', '<!--[if other]><table'),
                   ('width="320"', ''), ('height:auto', ''),
                   ('class="email-summary"', ''),
                   ('Monday lessons &amp; Friday practice</p>', 'Later summary</p>')]
        for old, new in changes:
            with self.subTest(change=(old, new)), self.assertRaises(ValueError):
                inspect_email(html.replace(old, new), require_shell=True)

    def test_copy_rejects_browser_javascript_before_transformation(self):
        helper = '<script src="/emails/whatsapp.' + 'a' * 64 + '.js" defer data-email-browser></script>'
        html = SHELL.format(extra="").replace('</head>', helper + '</head>')
        inspect_email(html, allow_browser_script=True, require_shell=True)
        with self.assertRaisesRegex(ValueError, "Unexpected script"):
            make_copy_html(html)


HUGO = os.environ.get("HUGO", "hugo")


@unittest.skipUnless(shutil.which(HUGO), "Hugo is required for rendered-copy checks")
class RenderedCopyTests(unittest.TestCase):
    def test_every_rendered_issue_has_a_copy_safe_equivalent(self):
        with tempfile.TemporaryDirectory(prefix="ballroom-copy-") as tmp:
            build = Path(tmp)
            result = subprocess.run([HUGO, "--environment", "email", "--buildDrafts", "--buildFuture",
                                     "--minify", "--destination", str(build)], cwd=ROOT,
                                    text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertEqual(result.returncode, 0, result.stdout)
            issues = [path for path in (build / "emails").rglob("*.html") if path.name != "index.html"]
            self.assertTrue(issues, "No rendered issues exercised")
            for path in issues:
                with self.subTest(issue=path.relative_to(build)):
                    original = path.read_text(encoding="utf-8")
                    copied = make_copy_html(original)
                    self.assertEqual(inspect_email(original).plain_text(), inspect_email(copied).plain_text())
                    self.assertEqual(len(inspect_email(copied).images), len(inspect_email(original).images) - 1)


if __name__ == "__main__":
    unittest.main()
