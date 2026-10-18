"""Editable Figma content compiles deterministically through the existing Hugo API."""
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from sync_figma_email import DesignError, compile_snapshot
from export_email import inspect_email, make_copy_html


def text(name, characters, **properties):
    return {"type": "TEXT", "name": name, "characters": characters, **properties}


def frame(name, *nodes, **properties):
    return {"type": "FRAME", "name": name, "children": list(nodes), **properties}


def block(role, **fields):
    return {"type": "INSTANCE", "name": "Email/" + role,
            "componentName": "Email/" + role,
            "children": [text(name, value) for name, value in fields.items()]}


def fixture(*body):
    return {"schemaVersion": 1, "fileKey": "example-file", "nodeId": "50:10",
            "document": frame("Email/Issue",
                {**block("Settings", subject="[Stanford Ballroom] Week 5",
                         date="2026-10-18T12:53:00-07:00", url="/emails/fall26/week5.html",
                         quarter="Fall 2026", signer="Ro"), "visible": False},
                block("Header", preheader="Monday lessons; Friday practice."),
                block("Title", title="Week 5"),
                *(body or (block("Prose", body="Happy Week 5!"),)),
                block("Footer"), width=600)}


def timetable(*, class_names=("Beginner", "Intermediate")):
    return {"type": "INSTANCE", "name": "Email/Lessons", "componentName": "Email/Lessons",
            "children": [text("title", "Monday, October 19"), text("caption", "Lesson schedule"),
                text("location", "Roble 113 & 115"),
                frame("tracks",
                    frame("track", text("name", "Standard"), text("teacher", "'Ikaika")),
                    frame("track", text("name", "Latin"), text("teacher", "Stacey, T&T"))),
                frame("rows",
                    frame("row", text("time", "6:30–7:30 pm"),
                          frame("classes", *(text("class", name) for name in class_names))),
                    frame("row", text("time", "8:30–9 pm"),
                          text("note", "Practice, rounds, and office hours.")))]}


def parts(source):
    path, generated = compile_snapshot(source)
    _, frontmatter, body = generated.split("---", 2)
    values = {}
    for line in frontmatter.splitlines():
        if line and not line.startswith("#"):
            key, value = line.split(": ", 1)
            values[key] = json.loads(value)
    return path, values, body.strip(), generated


class FigmaShellTests(unittest.TestCase):
    def test_snapshot_preserves_issue_metadata_and_published_hugo_contract(self):
        source = fixture()
        before = deepcopy(source)
        path, metadata, body, _ = parts(source)
        self.assertEqual(path, Path("content/emails/fall26/week5.md"))
        self.assertFalse(metadata["draft"])
        self.assertEqual(metadata["subject"], "[Stanford Ballroom] Week 5")
        self.assertEqual(metadata["preheader"], "Monday lessons; Friday practice.")
        self.assertEqual(metadata["date"], "2026-10-18T12:53:00-07:00")
        self.assertEqual(metadata["figma_source"], {"file_key": "example-file", "node_id": "50:10", "schema_version": 1})
        self.assertIn("Happy Week 5", body)
        self.assertEqual(source, before, "Compilation mutated the captured design")

    def test_every_required_shell_component_must_exist_exactly_once(self):
        for role in ("Settings", "Header", "Title", "Footer"):
            for duplicate in (False, True):
                with self.subTest(role=role, duplicate=duplicate):
                    source = fixture()
                    nodes = source["document"]["children"]
                    node = next(n for n in nodes if n["name"] == "Email/" + role)
                    if duplicate:
                        nodes.append(deepcopy(node))
                    else:
                        nodes.remove(node)
                    with self.assertRaisesRegex(DesignError, "exactly one"):
                        compile_snapshot(source)

    def test_unknown_or_unmapped_blocks_fail_instead_of_being_silently_omitted(self):
        for node in (block("Unmapped", body="Important announcement"),
                     frame("New section", text("body", "Important announcement"))):
            with self.subTest(name=node["name"]), self.assertRaisesRegex(DesignError, "Unmapped direct child"):
                compile_snapshot(fixture(node))

    def test_issue_width_shell_order_and_empty_body_are_checked(self):
        source = fixture()
        source["document"]["width"] = 800
        with self.assertRaisesRegex(DesignError, "600px"):
            compile_snapshot(source)
        source = fixture()
        source["document"]["children"][1:3] = reversed(source["document"]["children"][1:3])
        with self.assertRaisesRegex(DesignError, "Header and Title"):
            compile_snapshot(source)
        source = fixture()
        del source["document"]["children"][3]
        with self.assertRaisesRegex(DesignError, "no announcement content"):
            compile_snapshot(source)

    def test_unsupported_visual_edits_are_errors(self):
        source = fixture()
        source["unsupportedEdits"] = ["Photo rotated 12 degrees"]
        with self.assertRaisesRegex(DesignError, "Photo rotated"):
            compile_snapshot(source)


class FigmaLessonTests(unittest.TestCase):
    def test_each_timetable_row_requires_one_class_per_visible_track(self):
        for class_names in (("Beginner",), ("Beginner", "Intermediate", "Advanced")):
            with self.subTest(classes=class_names), self.assertRaisesRegex(DesignError, "one class per track"):
                compile_snapshot(fixture(timetable(class_names=class_names)))
        _, metadata, body, _ = parts(fixture(timetable()))
        self.assertEqual(metadata["lessons"]["rows"][0]["classes"], ["Beginner", "Intermediate"])
        self.assertEqual(metadata["lessons"]["tracks"][0]["teacher"], "'Ikaika")
        self.assertEqual(metadata["lessons"]["rows"][1]["note"], "Practice, rounds, and office hours.")
        self.assertIn('{{< email-lessons key="lessons" >}}', body)

    def test_hidden_class_cells_do_not_count_as_visible_timetable_entries(self):
        lesson = timetable(class_names=("Beginner", "Intermediate", "Unused"))
        cells = lesson["children"][-1]["children"][0]["children"][-1]
        cells["children"][-1]["visible"] = False
        _, metadata, _, _ = parts(fixture(lesson))
        self.assertEqual(metadata["lessons"]["rows"][0]["classes"], ["Beginner", "Intermediate"])

    def test_hidden_intro_after_and_note_content_is_omitted(self):
        lesson = timetable()
        lesson["children"].extend([
            text("intro", "Hidden introduction", visible=False),
            frame("optional copy", text("after", "Hidden follow-up"), visible=False),
        ])
        first_row = lesson["children"][4]["children"][0]
        first_row["children"].append(text("note", "Hidden note must not replace classes", visible=False))
        _, metadata, _, generated = parts(fixture(lesson))
        self.assertNotIn("intro", metadata["lessons"])
        self.assertNotIn("after", metadata["lessons"])
        self.assertEqual(metadata["lessons"]["rows"][0]["classes"], ["Beginner", "Intermediate"])
        self.assertNotIn("Hidden", generated)

    def test_visible_shared_note_and_class_cells_cannot_silently_discard_classes(self):
        lesson = timetable()
        row = lesson["children"][-1]["children"][0]
        row["children"].append(text("note", "Shared practice"))
        with self.assertRaisesRegex(DesignError, "either a shared note or class cells"):
            compile_snapshot(fixture(lesson))
        row["children"][1]["visible"] = False
        _, metadata, _, _ = parts(fixture(lesson))
        self.assertEqual(metadata["lessons"]["rows"][0], {"time": "6:30–7:30 pm", "note": "Shared practice"})

    def test_repeated_lesson_components_receive_distinct_snapshot_keys(self):
        second = timetable()
        second["children"][0]["characters"] = "Saturday workshop"
        _, metadata, body, _ = parts(fixture(timetable(), second))
        self.assertEqual(metadata["lessons"]["title"], "Monday, October 19")
        self.assertEqual(metadata["lessons_2"]["title"], "Saturday workshop")
        self.assertEqual(body.count('{{< email-lessons key="lessons" >}}'), 1)
        self.assertEqual(body.count('{{< email-lessons key="lessons_2" >}}'), 1)


class FigmaRichTextTests(unittest.TestCase):
    def test_bold_italic_links_and_lists_survive_the_bridge(self):
        segments = [
            {"characters": "Welcome "},
            {"characters": "team!", "fontName": {"style": "Bold"}, "fontWeight": 700},
            {"characters": "\nView schedule", "fontName": {"style": "Italic"},
             "hyperlink": {"type": "URL", "value": "/schedule/"}},
            {"characters": "\nBring shoes\nFind a partner", "listOptions": {"type": "UNORDERED"}},
            {"characters": "\nPractice\nReview", "listOptions": {"type": "ORDERED"}},
            {"characters": "\nOld time", "textDecoration": "STRIKETHROUGH"},
        ]
        prose = block("Prose")
        prose["children"] = [text("body", "".join(s["characters"] for s in segments), segments=segments)]
        _, _, body, _ = parts(fixture(prose))
        self.assertIn(r"Welcome <strong>team\!</strong>", body)
        self.assertIn("[<em>View schedule</em>](</schedule/>)", body)
        self.assertIn("- Bring shoes\n- Find a partner", body)
        self.assertIn("1. Practice\n1. Review", body)
        self.assertIn("<s>Old time</s>", body)

    def test_text_html_and_hugo_are_literal_data(self):
        payload = '<b>literal</b> {{< email-event title="oops" >}} **literal**'
        _, _, body, _ = parts(fixture(block("Prose", body=payload)))
        self.assertIn("&lt;b&gt;literal&lt;/b&gt;", body)
        self.assertIn("&#123;&#123;", body)
        self.assertNotIn("<b>", body)
        self.assertNotIn("{{< email-event", body)
        self.assertIn(r"\*\*literal\*\*", body)

    def test_photo_captions_escape_raw_html_like_prose(self):
        photo = block("Photo", src="emails/fall26/team.png", alt="The team",
                      caption='<img src="https://example.test/extra.png" onerror="alert(1)">')
        _, _, body, _ = parts(fixture(photo))
        self.assertIn("&lt;img", body)
        self.assertNotIn("caption=\"<img", body)

    def test_hidden_photo_metadata_remains_readable_while_hidden_caption_is_omitted(self):
        photo = block("Photo")
        photo["children"] = [
            frame("metadata", text("src", "emails/fall26/team.png", visible=False),
                  text("alt", "The team", visible=False), text("href", "/schedule/", visible=False),
                  text("width", "400", visible=False), visible=False),
            text("caption", "Hidden caption", visible=False),
        ]
        source = fixture(photo)
        for node in source["document"]["children"][0]["children"]:
            node["visible"] = False
        _, metadata, body, _ = parts(source)
        self.assertEqual(metadata["subject"], "[Stanford Ballroom] Week 5")
        self.assertIn('src="emails/fall26/team.png"', body)
        self.assertIn('alt="The team"', body)
        self.assertIn('href="/schedule/"', body)
        self.assertIn('width="400"', body)
        self.assertNotIn("caption=", body)
        self.assertNotIn("Hidden caption", body)

    def test_stale_segments_and_figma_node_links_fail_loudly(self):
        for properties in ({"segments": [{"characters": "Stale"}]},
                           {"segments": [{"characters": "Current", "hyperlink": {"type": "NODE", "value": "1:2"}}]}):
            prose = block("Prose")
            prose["children"] = [text("body", "Current", **properties)]
            with self.subTest(properties=properties), self.assertRaises(DesignError):
                compile_snapshot(fixture(prose))


class FigmaFieldSafetyTests(unittest.TestCase):
    def test_issue_path_cannot_escape_the_content_directory(self):
        for url in ("../../outside.md", "/emails/fall26/../outside.html", "/emails/fall26/%2e%2e.html",
                    "/emails/fall26/week5.md", "https://example.test/emails/fall26/week5.html",
                    "/emails/fall26/week5.copy.html", "/emails/fall26/week5.html\nother"):
            source = fixture()
            source["document"]["children"][0]["children"][2]["characters"] = url
            with self.subTest(url=url), self.assertRaises(DesignError):
                compile_snapshot(source)

    def test_links_allow_public_web_mail_and_site_urls_and_reject_local_or_active_urls(self):
        for href in ("https://example.test/register?a=1&b=2", "/schedule/", "mailto:ballroom@example.test", "tel:+16505551212"):
            with self.subTest(href=href):
                _, _, body, _ = parts(fixture(block("Button", label="Open", href=href)))
                self.assertIn("email-button", body)
        for href in ("javascript:alert(1)", "data:text/html,Hello", "//example.test/register",
                     "https://localhost/register", "https://127.0.0.1/register", "/\\evil.test/register",
                     "https://[bad/register", "https://example.test/a\nb"):
            with self.subTest(href=href), self.assertRaises(DesignError):
                compile_snapshot(fixture(block("Button", label="Open", href=href)))

    def test_photo_urls_and_asset_paths_are_durable_and_bounded(self):
        for src in ("emails/fall26/team.png", "emails/fall26/a poster.jpg", "/images/team.gif",
                    "https://example.test/team.jpeg", "emails/fall26/convert.webp"):
            with self.subTest(src=src):
                compile_snapshot(fixture(block("Photo", src=src, alt="The team", width="552")))
        for src in ("../private.png", "emails/../../private.png", "emails\\private.png", "team.svg",
                    "data:image/png;base64,AAA", "blob:https://figma.com/123", "http://example.test/team.png",
                    "https://s3-alpha.figma.com/img/123.png", "https://example.test/team.webp",
                    "/static/team.webp", "/static/team.avif"):
            with self.subTest(src=src), self.assertRaises(DesignError):
                compile_snapshot(fixture(block("Photo", src=src, alt="The team")))
        for width in ("0", "553", "100%", "52px"):
            with self.subTest(width=width), self.assertRaises(DesignError):
                compile_snapshot(fixture(block("Photo", src="team.png", alt="The team", width=width)))

    def test_shortcode_fields_cannot_inject_newlines_or_hugo(self):
        cases = [("Button", {"label": "Open", "href": "https://example.test/"}, "label"),
                 ("Notice", {"title": "Reminder", "body": "Details"}, "title"),
                 ("Event", {"title": "Practice", "when": "6–9 pm", "where": "Roble 113", "body": "Details"}, "where"),
                 ("Photo", {"src": "team.png", "alt": "The team"}, "alt"),
                 ("Signoff", {"closing": "See you", "name": "Ro"}, "name")]
        for role, values, name in cases:
            for payload in ("first\nsecond", '{{< email-photo src="bad" >}}'):
                fields = {**values, name: payload}
                with self.subTest(role=role, field=name, payload=payload), self.assertRaises(DesignError):
                    compile_snapshot(fixture(block(role, **fields)))

    def test_multiline_subject_is_rejected_before_email_export(self):
        source = fixture()
        source["document"]["children"][0]["children"][0]["characters"] = "Week 5\nAnother header"
        with self.assertRaises(DesignError):
            compile_snapshot(source)

    def test_unknown_variants_and_unsafe_themes_are_rejected(self):
        for node in ({**block("Notice", body="Details"), "variants": {"tone": "custom"}},
                     {**block("Event", title="Practice", body="Details"), "variants": {"status": "maybe"}}):
            with self.subTest(node=node), self.assertRaises(DesignError):
                compile_snapshot(fixture(node))
        for tokens in ({"light": {"text": "red"}}, {"light": {"text": "#fff;display:none"}},
                       {"light": {"unknown": "#112233"}}, {"custom": {"text": "#112233"}},
                       {"type": {"body_size": True}}, {"type": {"body_size": 22}},
                       {"type": {"title_size": 40, "title_line": 30}},
                       {"layout": {"content_padding": 100}}, {"layout": {"card_width": 1200}}):
            source = fixture()
            source["theme"] = tokens
            with self.subTest(theme=tokens), self.assertRaises(DesignError):
                compile_snapshot(source)
        source = fixture()
        source["theme"] = {"light": {"link": "#8c1515"}, "type": {"body_size": 18}, "layout": {"content_padding": 20}}
        self.assertEqual(parts(source)[1]["email_theme"], source["theme"])


class FigmaCheckTests(unittest.TestCase):
    def test_cli_check_is_deterministic_read_only_and_detects_design_or_source_drift(self):
        with tempfile.TemporaryDirectory(prefix="ballroom-figma-test-") as tmp:
            root = Path(tmp)
            snapshot = root / "issue.json"
            source = fixture()
            snapshot.write_text(json.dumps(source), encoding="utf-8")
            command = [sys.executable, str(ROOT / "scripts/sync_figma_email.py"), str(snapshot), "--root", str(root)]
            def run(*extra):
                return subprocess.run(command + list(extra), text=True, capture_output=True)
            missing = run("--check")
            self.assertNotEqual(missing.returncode, 0)
            self.assertIn("drift", missing.stderr)
            self.assertFalse((root / "content").exists(), "Read-only check created files")
            generated = run()
            self.assertEqual(generated.returncode, 0, generated.stderr)
            output = root / "content/emails/fall26/week5.md"
            original = output.read_bytes()
            for _ in range(2):
                checked = run("--check")
                self.assertEqual(checked.returncode, 0, checked.stderr)
                self.assertEqual(output.read_bytes(), original)
            output.write_bytes(original + b"\nManual source change\n")
            drift = run("--check")
            self.assertNotEqual(drift.returncode, 0)
            self.assertIn("drift", drift.stderr)
            self.assertTrue(output.read_bytes().endswith(b"Manual source change\n"))
            self.assertEqual(run().returncode, 0)
            self.assertEqual(output.read_bytes(), original)
            source["document"]["children"][2]["children"][0]["characters"] = "Week 5 revised"
            snapshot.write_text(json.dumps(source), encoding="utf-8")
            drift = run("--check")
            self.assertNotEqual(drift.returncode, 0)
            self.assertEqual(output.read_bytes(), original, "Check overwrote source with changed Figma content")


HUGO = os.environ.get("HUGO", "hugo")


@unittest.skipUnless(shutil.which(HUGO), "Hugo is required for rendered-bridge checks")
class RenderedFigmaBridgeTests(unittest.TestCase):
    def test_actual_hugo_render_preserves_rich_content_and_treats_injections_as_text(self):
        prose = block("Prose")
        segments = [{"characters": "Bold", "fontWeight": 700},
                    {"characters": " and "}, {"characters": "italic", "fontName": {"style": "Italic"}},
                    {"characters": "\nSchedule", "hyperlink": {"type": "URL", "value": "/schedule/"}},
                    {"characters": "\nBring shoes\nFind a partner", "listOptions": {"type": "UNORDERED"}},
                    {"characters": '\n<b>literal</b> {{< email-event title="oops" >}}'}]
        prose["children"] = [text("body", "".join(s["characters"] for s in segments), segments=segments)]
        photo = block("Photo", src="https://example.test/team.png", alt="The team",
                      caption="<i>literal caption</i>")
        source = fixture(prose, timetable(), timetable(), photo)
        relative, markdown = compile_snapshot(source)
        with tempfile.TemporaryDirectory(prefix="ballroom-figma-render-") as tmp:
            root = Path(tmp)
            output = root / relative
            output.parent.mkdir(parents=True)
            output.write_text(markdown, encoding="utf-8")
            shutil.copyfile(ROOT / "content/emails/_index.md", root / "content/emails/_index.md")
            destination = root / "public"
            result = subprocess.run([HUGO, "--environment", "email", "--buildFuture", "--minify",
                                     "--contentDir", str(root / "content"), "--destination", str(destination)],
                                    cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertEqual(result.returncode, 0, result.stdout)
            rendered = (destination / "emails/fall26/week5.html").read_text(encoding="utf-8")
            parsed = inspect_email(rendered, require_shell=True)
            plain = parsed.plain_text()
            self.assertIn('<b>literal</b> {{< email-event title="oops" >}}', plain)
            self.assertIn("<i>literal caption</i>", plain)
            self.assertNotIn("<b>literal</b>", rendered)
            self.assertNotIn("<i>literal caption</i>", rendered)
            self.assertIn("<strong>Bold</strong>", rendered)
            self.assertIn("<em>italic</em>", rendered)
            self.assertIn("• Bring shoes", plain)
            self.assertIn(("Schedule", "https://ballroom.stanford.edu/schedule/"), parsed.anchor_labels)
            self.assertEqual(rendered.count("<caption"), 2)
            self.assertEqual(inspect_email(make_copy_html(rendered)).plain_text(), plain)


if __name__ == "__main__":
    unittest.main()
