"""Local previews load unpublished assets; email exports keep public image URLs."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from export_email import EmailHTML, inspect_email

HUGO = os.environ.get("HUGO", "hugo")


@unittest.skipUnless(shutil.which(HUGO), "Hugo is required for rendered-image checks")
class PreviewImageTests(unittest.TestCase):
    def test_preview_assets_exist_and_exports_use_public_urls(self):
        with tempfile.TemporaryDirectory(prefix="ballroom-images-") as tmp:
            builds = {}
            for environment in ("development", "email"):
                destination = Path(tmp) / environment
                result = subprocess.run(
                    [HUGO, "--environment", environment, "--buildDrafts", "--minify",
                     "--baseURL", "http://localhost:1313/preview/",
                     "--destination", str(destination)],
                    cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                self.assertEqual(result.returncode, 0, result.stdout)
                builds[environment] = destination

            local_images = 0
            for path in sorted((builds["development"] / "emails").rglob("*.html")):
                if path.name == "index.html":
                    continue
                with self.subTest(issue=path.relative_to(builds["development"])):
                    preview = EmailHTML(allow_browser_script=True)
                    preview.feed(path.read_text(encoding="utf-8"))
                    mail_path = builds["email"] / path.relative_to(builds["development"])
                    mail = inspect_email(mail_path.read_text(encoding="utf-8"))
                    self.assertEqual(len(preview.images), len(mail.images))
                    for local, exported in zip(preview.images, mail.images):
                        if not local.startswith("/"):
                            self.assertEqual(local, exported)
                            continue
                        local_images += 1
                        self.assertTrue(local.startswith("/preview/"), local)
                        asset_path = urlsplit(local).path.removeprefix("/preview/")
                        self.assertTrue((builds["development"] / unquote(asset_path)).is_file(), local)
                        expected = urlsplit(mail.canonical)._replace(
                            path="/" + asset_path, query="", fragment="").geturl()
                        self.assertEqual(exported, expected)
            self.assertGreater(local_images, 0, "No local email image was exercised")


if __name__ == "__main__":
    unittest.main()
