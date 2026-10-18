"""Copy pages publish only reviewed website issues and pass mail validation."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from build_email_copy import build_copy_pages
from export_email import inspect_email


EMAIL = '''<!doctype html><html><head><title>Week 5</title>
<meta name="description" content="Classes Monday; practice Friday.">
<link rel="canonical" href="https://ballroom.stanford.edu/emails/fall26/week5.html">
<style>@media (prefers-color-scheme:dark) {{ .email-logo-light {{ display:none }} }}</style>
</head><body style="margin:0;background:#f2f1ee">
<!--[if mso]><table role="presentation" width="600"><tr><td><![endif]-->
<table role="presentation" style="width:100%;max-width:600px;font-family:Arial,Helvetica,sans-serif">
<tr><td><p class="email-summary">Classes Monday; practice Friday.</p>
<div class="email-logo-light"><img src="https://example.com/logo.png" alt="Stanford Ballroom" width="320" style="display:block;max-width:320px;height:auto"></div>
<!--[if !mso]><!--><div class="email-logo-dark" style="display:none"><img src="https://example.com/dark.png" alt="Stanford Ballroom" width="320" style="display:block;max-width:320px;height:auto"></div><!--<![endif]-->
</td></tr><tr><td class="email-content" id="email-announcement"><h1>Week 5</h1>
<p>Friday practice is <strong>6–9 pm</strong> in Roble 113.</p>{extra}</td></tr>
<tr><td><a href="https://mailman.stanford.edu/mailman/listinfo/ballroom-at-stanford">Mailing list settings</a></td></tr>
</table><!--[if mso]></td></tr></table><![endif]--></body></html>'''


class CopyBuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.email = Path(self.tmp.name) / "email"
        self.site = Path(self.tmp.name) / "site"
        (self.email / "emails/fall26").mkdir(parents=True)
        (self.site / "emails/fall26").mkdir(parents=True)

    def add_issue(self, name, *, hosted=True, extra=""):
        path = Path("emails/fall26") / name
        html = EMAIL.format(extra=extra)
        (self.email / path).write_text(html, encoding="utf-8")
        if hosted:
            # A hosted page can contain its allowed web helper; copies must
            # always come from the separately validated email build.
            hosted_html = html.replace("</head>", '<script src="/web-helper.js"></script></head>')
            (self.site / path).write_text(hosted_html, encoding="utf-8")

    def test_publishes_same_text_with_inline_baseline_and_single_logo(self):
        self.add_issue("week5.html")
        paths = build_copy_pages(self.email, self.site)
        self.assertEqual(paths, [self.site / "emails/fall26/week5.copy.html"])
        copy = paths[0].read_text(encoding="utf-8")
        parsed = inspect_email(copy, require_shell=True)
        self.assertIn("Friday practice is 6–9 pm in Roble 113.", parsed.plain_text())
        self.assertEqual(parsed.images, ["https://example.com/logo.png"])
        self.assertNotIn("<style", copy)
        self.assertNotIn("<script", copy)
        self.assertIn("<!--[if mso]>", copy)
        self.assertIn("max-width:600px", copy)

    def test_draft_or_future_issue_missing_from_site_is_not_exposed(self):
        self.add_issue("published.html")
        self.add_issue("draft.html", hosted=False)
        paths = build_copy_pages(self.email, self.site)
        self.assertEqual([p.name for p in paths], ["published.copy.html"])
        self.assertFalse((self.site / "emails/fall26/draft.copy.html").exists())

    def test_archive_pages_and_existing_copies_are_ignored(self):
        self.add_issue("week5.html")
        for name in ("index.html", "week5.copy.html"):
            (self.email / "emails/fall26" / name).write_text("<html>Archive or old copy</html>")
        paths = build_copy_pages(self.email, self.site)
        self.assertEqual(len(paths), 1)
        self.assertFalse((self.site / "emails/fall26/index.copy.html").exists())
        self.assertFalse((self.site / "emails/fall26/week5.copy.copy.html").exists())

    def test_unsafe_issue_aborts_before_any_output_is_written(self):
        self.add_issue("a.html")
        self.add_issue("b.html", extra='<script>alert("unsafe")</script>')
        with self.assertRaisesRegex(ValueError, "Unexpected script"):
            build_copy_pages(self.email, self.site)
        self.assertEqual(list(self.site.rglob("*.copy.html")), [])

    def test_missing_shell_or_nonannouncement_hosted_path_fails(self):
        self.add_issue("week5.html")
        (self.site / "emails/fall26/week5.html").write_text("<html>Archive</html>")
        with self.assertRaisesRegex(ValueError, "not an announcement"):
            build_copy_pages(self.email, self.site)


if __name__ == "__main__":
    unittest.main()
