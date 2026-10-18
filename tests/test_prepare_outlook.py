"""Draft payloads retain the exact portable export, including head styles."""
from pathlib import Path
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from prepare_outlook import prepare
from test_email_browser import BASE, HELPER


class OutlookPayloadTests(unittest.TestCase):
    def test_full_document_survives_json_roundtrip(self):
        html = BASE.format(script="<style>@media(prefers-color-scheme:dark){body{color:white}}</style>")
        html = html.replace("Welcome!</p>", 'Welcome! – dancers</p><!--[if mso]><table role="presentation"></table><![endif]-->')
        with tempfile.TemporaryDirectory() as tmp:
            source, destination = Path(tmp) / "email", Path(tmp) / "site"
            issue = source / "emails/fall26/week5.html"
            issue.parent.mkdir(parents=True)
            issue.write_text(html, encoding="utf-8")
            (issue.parent / "index.html").write_text("<p>Archive</p>")
            self.assertEqual(prepare(source, destination), 1)
            payload = json.loads((destination / "outlook/issues/fall26/week5.json").read_text())
            self.assertEqual(payload, {"schemaVersion": 1, "subject": "Welcome", "html": html})

    def test_no_payload_from_scripted_or_nonportable_email(self):
        for html in [BASE.format(script=HELPER), BASE.format(script="<script>bad()</script>"),
                     BASE.format(script="").replace("Welcome!</p>", '<a href="/schedule/">Schedule</a></p>')]:
            with self.subTest(html=html), tempfile.TemporaryDirectory() as tmp:
                source = Path(tmp) / "source"
                issue = source / "emails/fall26/week5.html"
                issue.parent.mkdir(parents=True)
                issue.write_text(html)
                with self.assertRaises(ValueError):
                    prepare(source, Path(tmp) / "destination")

    def test_missing_build_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "No built email"):
                prepare(Path(tmp) / "missing", Path(tmp) / "destination")

    @unittest.skipUnless(os.environ.get("EMAIL_TEST_SITE") and os.environ.get("EMAIL_EXPORT_SITE"), "Requires CI builds")
    def test_built_payloads_equal_script_free_exports(self):
        website = Path(os.environ["EMAIL_TEST_SITE"])
        exports = Path(os.environ["EMAIL_EXPORT_SITE"])
        payloads = list((website / "outlook/issues").rglob("*.json"))
        self.assertGreater(len(payloads), 0)
        for path in payloads:
            with self.subTest(path=path):
                issue = path.relative_to(website / "outlook/issues").with_suffix(".html")
                html = (exports / "emails" / issue).read_text(encoding="utf-8")
                self.assertEqual(json.loads(path.read_text())["html"], html)


if __name__ == "__main__":
    unittest.main()
