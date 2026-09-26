"""The hosted helper is an explicit exception; exported mail stays script-free."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from export_email import inspect_email


BASE = '''<!doctype html><html><head><title>Welcome</title>
<meta name="description" content="First class Monday">
<link rel="canonical" href="https://stanfordballroom.com/emails/fall26/week1.html">
{script}</head><body><p>First class Monday</p><p>Welcome!</p></body></html>'''
HELPER = '<script src="/emails/whatsapp.' + 'a' * 64 + '.js" defer data-email-browser></script>'


class BrowserHelperTests(unittest.TestCase):
    def test_exports_reject_even_the_known_helper(self):
        with self.assertRaisesRegex(ValueError, "Unexpected script"):
            inspect_email(BASE.format(script=HELPER))

    def test_hosted_helper_does_not_change_plain_text(self):
        normal = inspect_email(BASE.format(script=""))
        hosted = inspect_email(BASE.format(script=HELPER), allow_browser_script=True)
        self.assertEqual(normal.plain_text(), hosted.plain_text())
        self.assertEqual(len(hosted.browser_scripts), 1)

    def test_preview_subdirectory_is_supported(self):
        hosted = inspect_email(BASE.format(script=HELPER.replace('/emails/', '/website/emails/')), allow_browser_script=True)
        self.assertTrue(hosted.browser_scripts[0].startswith('/website/emails/'))

    def test_other_scripts_remain_rejected(self):
        for script in ['<script>alert(1)</script>', '<script src="https://example.test/x.js"></script>',
                       HELPER.replace(' defer', ' onload="alert(1)" defer'),
                       HELPER.replace('/emails/', '//example.test/emails/'),
                       HELPER.replace('data-email-browser', 'data-other'),
                       '<script src defer data-email-browser></script>',
                       HELPER.replace('whatsapp.', 'other.')]:
            with self.subTest(script=script):
                with self.assertRaises(ValueError):
                    inspect_email(BASE.format(script=script), allow_browser_script=True)


if __name__ == "__main__":
    unittest.main()
