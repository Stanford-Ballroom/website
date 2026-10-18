#!/usr/bin/env python3
"""Compile an editable Figma email snapshot into the existing Hugo components.

No mail is sent. Run design/figma/read-email.js through the connected Figma tool
to capture the selected issue, then pass its JSON to this command. Keeping the
snapshot in git makes published issues reproducible without Figma credentials.
"""
import argparse
from datetime import datetime
import html
import json
from pathlib import Path
import re
import sys
import tempfile
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = 1
KNOWN = {"Settings", "Header", "Title", "Heading", "Prose", "Lessons", "Notice", "Event",
         "Button", "Photo", "Signoff", "Footer"}
REQUIRED = ("Settings", "Header", "Title", "Footer")
LIGHT = {"background", "card", "text", "muted", "heading", "link", "notice",
         "table_header", "table_border", "warning", "celebrate"}
DARK = {"background", "card", "text", "muted", "heading", "link", "notice", "table_header"}
TYPE_RANGES = {"body_size": (14, 20), "body_line": (20, 32), "title_size": (24, 40),
               "title_line": (30, 48), "heading_size": (20, 28), "heading_line": (26, 36)}


class DesignError(ValueError):
    pass


def children(node):
    return node.get("children", [])


def kind(node):
    name = node.get("componentName") or node.get("name", "")
    if name.startswith("Email/"):
        return name.split("/", 1)[1]
    return ""


def descendants(node, *, include_hidden=False):
    for child in children(node):
        if not include_hidden and not child.get("visible", True):
            continue
        yield child
        yield from descendants(child, include_hidden=include_hidden)


def field_node(node, name, *, required=False):
    metadata = kind(node) == "Settings" or name in {"src", "alt", "href", "width"}
    found = [n for n in descendants(node, include_hidden=metadata) if n.get("type") == "TEXT" and n.get("name") == name]
    if len(found) > 1:
        raise DesignError(f"{kind(node) or node.get('name')}: duplicate field {name!r}")
    if not found:
        if required:
            raise DesignError(f"{kind(node) or node.get('name')}: missing field {name!r}")
        return None
    return found[0]


def field(node, name, *, required=False):
    found = field_node(node, name, required=required)
    text = found.get("characters", "").strip() if found else ""
    if required and not text:
        raise DesignError(f"{kind(node)}: empty required field {name!r}")
    if any(c in text for c in "\x00\r"):
        raise DesignError(f"Invalid control character in {name}")
    return text


def container(node, name, *, required=False):
    found = [n for n in descendants(node) if n.get("name") == name and n.get("type") != "TEXT"]
    if len(found) != 1:
        if not found and not required:
            return None
        raise DesignError(f"{kind(node)} needs exactly one {name!r} container")
    return found[0]


def escape_text(text):
    # Goldmark has unsafe HTML enabled for the existing shortcodes. Source text
    # is data: escape HTML, Hugo delimiters, and Markdown metacharacters.
    text = html.escape(re.sub(r"([\\`*_\[\]#!|~])", r"\\\1", text), quote=True)
    return text.replace("{", "&#123;").replace("}", "&#125;")


def public_url(value, *, image=False):
    from export_email import _url_error
    error = _url_error(value, image=image)
    if error:
        raise DesignError(error)
    if not image and value.startswith("/") and not value.startswith("//"):
        return value
    return value


def link_url(value):
    if value.startswith("/") and not value.startswith("//") and "\\" not in value:
        # Site-relative links are made absolute by the existing Hugo URL hook.
        if any(c in value for c in "\r\n\t"):
            raise DesignError("Control character in site link")
        return value
    return public_url(value)


def rich(node, name, *, required=False):
    text_node = field_node(node, name, required=required)
    if text_node is None:
        return ""
    text = text_node.get("characters", "")
    if required and not text.strip():
        raise DesignError(f"Empty {name} in {kind(node)}")
    segments = text_node.get("segments", [])
    if not segments:
        return "\n\n".join(escape_text(line) for line in text.splitlines()).strip()
    if "".join(s.get("characters", "") for s in segments) != text:
        raise DesignError(f"Stale rich-text segments in {kind(node)}.{name}")
    lines = [{"parts": [], "list": "NONE"}]
    for segment in segments:
        font_style = segment.get("fontName", {}).get("style", "").lower()
        weight = segment.get("fontWeight", 700 if "bold" in font_style else 400)
        hyperlink = segment.get("hyperlink")
        if hyperlink:
            if hyperlink.get("type") != "URL":
                raise DesignError("Figma node links cannot be used as email links")
            href = link_url(hyperlink.get("value", ""))
        for index, part in enumerate(segment.get("characters", "").split("\n")):
            if index:
                lines.append({"parts": [], "list": "NONE"})
            if not part:
                continue
            value = escape_text(part)
            if weight >= 600:
                value = "<strong>" + value + "</strong>"
            if "italic" in font_style:
                value = "<em>" + value + "</em>"
            if segment.get("textDecoration") == "STRIKETHROUGH":
                value = "<s>" + value + "</s>"
            if hyperlink:
                # The existing hook applies absolute site URLs + inline theme.
                value = "[" + value + "](<" + quote(href, safe="/:?#[]@!$&'()*+,;=%") + ">)"
            lines[-1]["parts"].append(value)
            options = segment.get("listOptions", {})
            if options.get("type") in {"ORDERED", "UNORDERED"}:
                lines[-1]["list"] = options["type"]
    result = ""
    previous = "NONE"
    for line in lines:
        value = "".join(line["parts"]).strip()
        if not value:
            continue
        current = line["list"]
        separator = "\n" if current != "NONE" and previous == current else "\n\n"
        prefix = {"ORDERED": "1. ", "UNORDERED": "- "}.get(current, "")
        result += (separator if result else "") + prefix + value
        previous = current
    return result


def attr(value):
    if "{{" in value or "}}" in value or any(c in value for c in "\x00\n\r"):
        raise DesignError("Shortcode fields must be single-line text without Hugo delimiters")
    return json.dumps(value, ensure_ascii=False)


def shortcode(name, attrs=None, body=None):
    args = " ".join(f"{key}={attr(str(value))}" for key, value in (attrs or {}).items() if value != "")
    opening = "{{< email-" + name + (" " + args if args else "") + " >}}"
    return opening if body is None else opening + "\n" + body.strip() + "\n{{< /email-" + name + " >}}"


def variant(node, name, default, allowed):
    value = node.get("variants", {}).get(name, default)
    if value not in allowed:
        raise DesignError(f"Unknown {name}: {value!r}")
    return value


def theme(source):
    result = source.get("theme", {})
    if not isinstance(result, dict):
        raise DesignError("theme must be an object")
    for group, values in result.items():
        if group not in {"light", "dark", "type", "layout"} or not isinstance(values, dict):
            raise DesignError(f"Unsupported theme group: {group}")
        allowed = LIGHT if group == "light" else DARK if group == "dark" else TYPE_RANGES if group == "type" else {"content_padding"}
        for name, value in values.items():
            if name not in allowed:
                raise DesignError(f"Unsupported theme token: {group}.{name}")
            if group in {"light", "dark"}:
                if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
                    raise DesignError(f"Theme color {name} must be a six-digit hex color")
            else:
                lower, upper = TYPE_RANGES[name] if group == "type" else (16, 32)
                if isinstance(value, bool) or not isinstance(value, int) or not lower <= value <= upper:
                    raise DesignError(f"Theme token {name} must be between {lower} and {upper}")
    typography = result.get("type", {})
    for role, default_size in (("body", 17), ("title", 30), ("heading", 23)):
        if typography.get(role + "_line", {"body": 26, "title": 37, "heading": 30}[role]) < typography.get(role + "_size", default_size):
            raise DesignError(f"{role} line height must be at least the font size")
    return result


def lessons(node):
    lesson = {name: rich(node, name) if name in {"intro", "after"} else field(node, name)
              for name in ("title", "intro", "caption", "location", "after")}
    tracks = container(node, "tracks", required=True)
    rows = container(node, "rows", required=True)
    lesson["tracks"] = [{"name": field(t, "name", required=True), "teacher": field(t, "teacher")}
                        for t in children(tracks) if t.get("visible", True)]
    if not 1 <= len(lesson["tracks"]) <= 3:
        raise DesignError("Lessons need one to three tracks; split larger timetables")
    lesson["rows"] = []
    for row in children(rows):
        if not row.get("visible", True):
            continue
        entry = {"time": field(row, "time", required=True)}
        note = rich(row, "note")
        if note:
            cells = container(row, "classes")
            if cells and any(c.get("characters", "").strip() for c in descendants(cells) if c.get("type") == "TEXT"):
                raise DesignError("A lesson row must show either a shared note or class cells")
            entry["note"] = note
        else:
            cells = container(row, "classes", required=True)
            entry["classes"] = [rich({"children": [c]}, "class", required=True) for c in children(cells) if c.get("visible", True)]
            if len(entry["classes"]) != len(lesson["tracks"]):
                raise DesignError("Each lesson row needs one class per track")
        lesson["rows"].append(entry)
    if not lesson["rows"]:
        raise DesignError("Lessons need at least one row")
    return {k: v for k, v in lesson.items() if v}


def compile_snapshot(source):
    if source.get("schemaVersion") != SCHEMA_VERSION:
        raise DesignError(f"Expected snapshot schemaVersion {SCHEMA_VERSION}")
    if source.get("unsupportedEdits"):
        raise DesignError("Unsupported visual edits: " + "; ".join(source["unsupportedEdits"]))
    root = source.get("document", {})
    if root.get("name") != "Email/Issue" or root.get("type") != "FRAME":
        raise DesignError("Select the Email/Issue frame, not a screenshot or a component library")
    if root.get("width", 600) != 600:
        raise DesignError("Email/Issue must use the supported 600px responsive shell")
    blocks = [b for b in children(root) if b.get("visible", True) or kind(b) == "Settings"]
    grouped = {}
    for block in blocks:
        role = kind(block)
        if role not in KNOWN:
            raise DesignError(f"Unmapped direct child {block.get('name')!r}; use a reusable Email component")
        grouped.setdefault(role, []).append(block)
    for role in REQUIRED:
        if len(grouped.get(role, [])) != 1:
            raise DesignError(f"Issue needs exactly one Email/{role}")
    visible_roles = [kind(b) for b in blocks if kind(b) != "Settings"]
    if visible_roles[:2] != ["Header", "Title"] or visible_roles[-1] != "Footer":
        raise DesignError("Keep Header and Title first and Footer last; reorder the body blocks freely")
    settings, header, title = (grouped[k][0] for k in ("Settings", "Header", "Title"))
    meta = {k: field(settings, k, required=k in {"subject", "date", "url", "quarter"})
            for k in ("subject", "date", "url", "quarter", "signer")}
    if not re.fullmatch(r"/emails/[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+\.html", meta["url"]):
        raise DesignError("Issue URL must be /emails/<quarter>/<issue>.html")
    try:
        sent = datetime.fromisoformat(meta["date"])
        if sent.utcoffset() is None:
            raise ValueError()
    except ValueError:
        raise DesignError("Send date needs an explicit timezone, e.g. 2026-10-18T12:53:00-07:00") from None
    metadata = {"title": field(title, "title", required=True), "subject": meta["subject"],
                "date": meta["date"], "draft": False, "url": meta["url"],
                "quarter": meta["quarter"], "preheader": field(header, "preheader", required=True),
                "signer": meta["signer"] or "Stanford Ballroom",
                "figma_source": {"file_key": source.get("fileKey", ""), "node_id": source.get("nodeId", root.get("id", "")), "schema_version": SCHEMA_VERSION}}
    for name, value in metadata.items():
        if isinstance(value, str) and any(c in value for c in "\r\n\x00"):
            raise DesignError(f"Issue {name} must be single-line text")
    tokens = theme(source)
    if tokens:
        metadata["email_theme"] = tokens
    body = []
    count = 0
    for block in blocks:
        role = kind(block)
        if role in REQUIRED:
            continue
        if role == "Prose":
            body.append(rich(block, "body", required=True))
        elif role == "Heading":
            body.append("## " + escape_text(field(block, "title", required=True)))
        elif role == "Lessons":
            count += 1
            key = "lessons" if count == 1 else f"lessons_{count}"
            metadata[key] = lessons(block)
            body.append(shortcode("lessons", {"key": key}))
        elif role == "Notice":
            tone = variant(block, "tone", "info", {"info", "warning", "celebrate"})
            body.append(shortcode("notice", {"title": field(block, "title"), "tone": tone}, rich(block, "body", required=True)))
        elif role == "Event":
            values = {k: field(block, k, required=k == "title") for k in ("title", "when", "where")}
            values["status"] = variant(block, "status", "confirmed", {"confirmed", "tentative", "cancelled", "tbd"})
            body.append(shortcode("event", values, rich(block, "body", required=True)))
        elif role == "Button":
            body.append(shortcode("button", {"label": field(block, "label", required=True), "href": link_url(field(block, "href", required=True))}))
        elif role == "Photo":
            values = {k: field(block, k, required=k in {"src", "alt"}) for k in ("src", "alt", "caption", "href", "width")}
            values["caption"] = rich(block, "caption")
            # Local committed Hugo asset paths stay supported; hosted sources
            # must be durable absolute HTTPS. Temporary Figma assets are rejected.
            src = values["src"]
            if ":" in src or src.startswith("//"):
                public_url(src, image=True)
            elif ".." in Path(src).parts or "\\" in src or not re.fullmatch(r"/?[a-zA-Z0-9_./ -]+\.(?:png|jpe?g|gif|webp|avif)", src, re.I):
                raise DesignError("Photo src must identify a committed asset or public PNG/JPEG/GIF")
            elif src.startswith("/") and Path(src).suffix.lower() in {".webp", ".avif"}:
                raise DesignError("Root-relative images bypass conversion; use PNG/JPEG/GIF or a processed assets path")
            if values["href"]:
                values["href"] = link_url(values["href"])
            if values["width"] and (not values["width"].isdigit() or not 1 <= int(values["width"]) <= 552):
                raise DesignError("Photo width must be between 1 and 552")
            body.append(shortcode("photo", values))
        elif role == "Signoff":
            body.append(shortcode("signoff", {"closing": field(block, "closing"), "name": field(block, "name")}))
    if not body:
        raise DesignError("Email has no announcement content")
    fm = ["---", "# Generated from the Figma snapshot. Edit the Figma issue, then sync again."]
    fm.extend(key + ": " + json.dumps(value, ensure_ascii=False) for key, value in metadata.items())
    markdown = "\n".join(fm) + "\n---\n" + "\n\n".join(body) + "\n"
    relative = Path("content") / meta["url"].lstrip("/")
    return relative.with_suffix(".md"), markdown


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--check", action="store_true", help="fail if the generated Hugo source differs; do not write")
    parser.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        source = json.loads(args.snapshot.read_text(encoding="utf-8"))
        relative, text = compile_snapshot(source)
        target = args.root / relative
        if args.check:
            if not target.is_file() or target.read_text(encoding="utf-8") != text:
                raise DesignError(f"Figma snapshot drift: run python3 scripts/sync_figma_email.py {args.snapshot}")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile("w", dir=target.parent, encoding="utf-8", delete=False) as stream:
                stream.write(text)
                temporary = Path(stream.name)
            temporary.replace(target)
        print(f"{'Checked' if args.check else 'Generated'} {relative}")
    except (DesignError, OSError, json.JSONDecodeError) as exc:
        parser.exit(1, f"Figma email: {exc}\n")


if __name__ == "__main__":
    main()
