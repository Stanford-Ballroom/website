# Weekly announcements in Hugo

Each issue is a Markdown file. Hugo produces the complete, standalone HTML email
at a permanent address such as `/emails/spring26/week1.html`. The page at that
address is also the email body: it has no website navigation, theme scripts, or
external stylesheet. `/emails/` and `/emails/spring26/` provide normal website
archive pages.

## Weekly workflow

Use the same **Hugo 0.150.0 extended** installation as the rest of the site. The
export/check scripts need **Python 3.9+**, with no extra Python or npm packages.

1. Create a draft:

   ```sh
   hugo new content emails/autumn26/week1.md
   ```

   Or copy last week's Markdown file. When copying, immediately change `url`,
   `title`, `date`, `preheader`, and `draft: true`, then review every event date,
   room, instructor, and deadline. Each issue must have a unique `.html` URL.

2. Edit the front matter and the Markdown underneath. `title` is the visible
   heading; `subject` optionally overrides the email subject (otherwise the
   heading is used). `preheader` is the short summary shown above the logo. It is
   the first body text, so it can supply the inbox preview and survive copying
   the rendered email. `date` is the intended
   send date; write an explicit offset such as `2026-09-28T09:00:00-07:00`.
   Future-dated issues are omitted by Hugo unless `--buildFuture` is used.

3. Preview drafts locally:

   ```sh
   hugo server --buildDrafts --disableFastRender
   ```

   Open `/emails/autumn26/week1.html` at Hugo's local address. For a new quarter,
   optionally add `content/emails/autumn26/_index.md` with `title: Autumn 2026` in
   front matter to give it its own archive page. The parent email section supplies
   the layout and output defaults.

4. Export a test draft:

   ```sh
   python3 scripts/export_email.py autumn26/week1 --draft
   ```

   This builds into a temporary directory and writes:

   ```text
   email-dist/autumn26/week1.html
   email-dist/autumn26/week1.txt
   email-dist/autumn26/week1.eml
   ```

   The `.txt` alternative comes from the rendered email, including link targets
   and image descriptions. The `.eml` is multipart plain text + HTML, with the
   subject and an `X-Unsent` hint. It intentionally has no sender or recipients.
   Some mail clients open EMLs as messages rather than editable drafts; use their
   “edit as new” function if available, or use your existing HTML insertion tool
   with the `.html` file. Ordinary paste of HTML source does not render it.
   If copying the rendered page, select the entire email including the summary
   above the logo. The summary is visible specifically so it travels with the
   selection; it also starts the plain-text alternative. Copy/paste can still
   lose head styles such as the dark-mode logo switch, so importing the full HTML
   or EML is preferable when the client supports it. Inbox previews remain under
   the recipient client's control, including any AI-generated summaries.

5. Send yourself a test through your normal mail client. Confirm the subject,
   inbox preview, links, images, timetable, phone layout, and dark mode. New local
   images have production URLs and will not load remotely until deployed. A local
   browser preview can therefore show a missing new image before publication.

6. Set `draft: false`, commit/review/merge using the existing website workflow, and
   wait for deployment. Open the public issue and its new images. Then export
   without `--draft`, choose your sender and mailing list in your mail client, and
   send. The scripts never send mail or modify the mailing list.

To use a non-default Hugo binary, set `HUGO=/path/to/hugo`. To change where exports
are written, use `--output /path/to/folder`. Generated exports are ignored by git.

## Writing an issue

Use Markdown for paragraphs, bullets, emphasis, links, headings, and ordinary
tables. Shortcodes are only needed for the recurring structured elements.

```markdown
Happy Week 8!

- Congratulations to everyone who competed this weekend!
- Our social is next Friday; details below.

{{< email-notice title="No lessons next Monday" tone="warning" >}}
There are no lessons on Memorial Day. We still have the room for practice.
{{< /email-notice >}}

{{< email-lessons >}}

{{< email-event title="Saturday, May 23" when="12 – 2 pm" where="Roble 115" >}}
Mentored practice! Please note the unusual afternoon time.
{{< /email-event >}}

{{< email-signoff closing="Thanks, and see you all soon!" >}}
```

Shortcode blocks can be reordered, repeated, or omitted. Bodies support Markdown
and nested shortcodes. Keep blank lines around blocks and use the `{{< ... >}}`
syntax shown here. There is no required “announcements / lessons / practice” order:
Week 9 omits the lesson table entirely; photo recaps can go after the sign-off.
Use `##` for headings instead of inventing a shortcode for every section.

| Shortcode | Purpose and fields |
| --- | --- |
| `email-lessons` | Reads the issue's `lessons` object. Optional `key="workshop"` selects another front-matter object with the same structure. |
| `email-event` | Heading, optional `when` and `where`, and a Markdown body. Required `title`. `status` is `confirmed` (default), `tentative`, `cancelled`, or `tbd`. |
| `email-notice` | Highlighted Markdown, optional `title`. `tone` is `info` (default), `warning`, or `celebrate`; write the important fact in words as well. |
| `email-button` | Form, registration, volunteer, or event link. Required `href` and `label`. |
| `email-photo` | Required `src` and descriptive `alt`; optional Markdown `caption`, linked `href`, and maximum `width` from 1–552 pixels. |
| `email-snippet` | Includes a named versioned Markdown snippet, e.g. `"beginners-v1"` or `"schedule-v1"`. |
| `email-signoff` | Optional `closing` and `name`. Name falls back to the issue's `signer`, then “Stanford Ballroom.” |

### Lessons, substitutions, and exceptions

Keep the schedule in the issue's front matter, rather than reading the live
calendar or mutable global defaults. Copying it each week is intentional: later
schedule changes must not silently rewrite the historical announcements.

```yaml
lessons:
  title: Monday, May 18
  intro: "'Ikaika is traveling, so Standard will be taught by Dasha and mentors :)."
  location: "Roble 115 (375 Santa Teresa St.)"
  tracks:
    - name: Standard
      teacher: Dasha & Mentors
    - name: Latin
      teacher: Stacey, T&T
  rows:
    - time: "6:30 – 7:30 pm"
      classes: [Beginner, Intermediate]
    - time: "7:30 – 8:30 pm"
      classes: [Intermediate, Beginner]
    - time: "8:30 – 9 pm"
      note: "Practice, rounds, and office hours. **Social afterwards!**"
  after: "Bring your team jacket for a group photo."
```

`classes` must contain one entry per track. `note` creates a shared row spanning
all tracks. Any number of rows/tracks is supported, though two tracks are easiest
to read on a phone; split larger schedules into separate tables. `intro`, `after`,
class entries, and shared notes support Markdown. `caption` optionally overrides
“Lesson schedule.” Time, venue, instructors, and duration are all issue-specific.

For cancellations, omit `email-lessons` and write a notice/event. For multiple
lesson days, add a second object such as `workshop` and call
`{{< email-lessons key="workshop" >}}` where it belongs. TBD is explicit text,
never a fabricated time. Write “TODAY” or “tomorrow” relative to the send date;
the archive does not recalculate these labels as time passes.

### Forms and images

```markdown
{{< email-button href="https://forms.gle/EXAMPLE" label="Register by Tuesday" >}}

{{< email-photo src="emails/spring26/team.jpg" alt="The team after Standard finals" caption="Nationals 2026 · Photo: photographer's name" >}}
```

The image example resolves to `assets/emails/spring26/team.jpg`. Images can also
come from a page bundle or an absolute HTTPS URL, as in the Spring examples.
Root-relative image paths refer to `static/`. Local assets are resized to at most
1200 pixels wide; local WebP/AVIF images are converted to JPEG for email. Use
PNG/JPEG/GIF for remote or static images, and avoid SVG. Photographs keep their
aspect ratios. Prefer committed local assets or immutable remote URLs for a
durable archive; a remote repository's `main` branch can change after sending.

The header uses the already-public PNGs from the original spring emails, configured
as `logo_url` (black text) and `logo_dark_url` (white text) in `data/emails.yaml`.
Light mode shows black text on white; supported dark-mode clients switch to white
text on the same dark background as the email card. Clients without dark-mode CSS
support retain the light version. Both images load in drafts and exports before
any site deployment. When replacing them, use publicly reachable HTTPS image URLs;
do not point them at unpublished Hugo-generated images.

Normal Markdown images work too, with the optional title used as a caption:

```markdown
![The team after finals](emails/spring26/team.jpg "Nationals 2026")
```

Use absolute URLs for external links and root-relative paths for site links, such
as `[schedule](/schedule/)`. Links are converted to the public origin from
`data/emails.yaml`, even during a local or preview build. Bare relative links are
rejected to prevent broken email links. `mailto:`, `tel:`, and heading anchors are
supported. Keep private event details in the same private channel used in the
original message; the website archive is public when an issue is published.

### Repeated copy

`{{< email-snippet "beginners-v1" >}}` loads
`assets/emails/snippets/beginners-v1.md`. Snippets are plain Markdown; they do not
expand shortcodes. When recurring copy changes, add a `v2` file and use it in new
issues; leave `v1` untouched so old emails retain their wording. Alternatively,
paste the copy directly into the issue when it needs a one-off variation.

## What came from the supplied spring emails

| Pattern | Where it appeared | Template support |
| --- | --- | --- |
| Two simultaneous tracks, swapping beginner/intermediate | Most weeks | `email-lessons` with per-issue rows |
| Different class lengths, changed start time and room | Weeks 1 and 10 | No hard-coded schedule defaults in the renderer |
| Substitute coaches | Week 8 | Per-track teacher fields and an introductory note |
| No lessons, practice instead | Week 9 | Omit the timetable; use a notice and event |
| Practice at unusual times or not yet scheduled | Weeks 2, 6, 8, 10 | Independent events and explicit status |
| Volunteer, registration, and nomination requests | Weeks 1, 3, 9 | Free Markdown and linked buttons |
| Long results/leadership announcements | Weeks 6 and 9 | Ordinary prose, lists, and headings |
| Posters, one-photo recaps, multi-photo recaps | Weeks 1, 2, 3, 6, 8, 10 | Repeatable photos with alt text and captions |
| Recurring welcome, schedule link, and signature | Most weeks | Versioned snippets and sign-off |

Four representative issues are converted under `content/emails/spring26/`:
Weeks **1, 6, 9, and 10**. They are **drafts**, so merging this implementation does
not automatically publish the old messages. The remaining Ballroom uploads were
analyzed for requirements, not migrated in full.

Migration notes:

- `4.html` actually contains Week 5; its filename is not the issue number.
- `2 3.html` is unrelated to Ballroom and is excluded.
- Week 6 contains stale Week 5 text after the closing HTML; that is excluded.
- Several preview texts and alt descriptions were stale; the converted versions
  match their issue/photo. The Week 1 spelling error “havily” is corrected.
- Send dates for Weeks 1, 6, and 9 are inferred from “tomorrow” and the event
  dates; example send times are placeholders, not recovered mail metadata.
- Forms, photo URLs, and event details are historical. Review them and the
  inferred dates before publishing the migrated issues as an archive.

## Template structure and validation

| File or directory | Responsibility |
| --- | --- |
| `archetypes/emails.md` | New-issue starter, including a schedule to review |
| `data/emails.yaml` | Public origin, club name, public logo URL, mailing-list settings URL |
| `layouts/emails/single.html` | Complete email document, visible summary, header, footer |
| `layouts/emails/list.html` | Archive pages within the existing website |
| `layouts/emails/_markup/` | Email-specific Markdown links, headings, images, tables |
| `layouts/partials/email/` | URL resolution, inline prose styles, photos, dark/mobile CSS |
| `layouts/shortcodes/email-*.html` | Author-facing components, separate from theme shortcodes |
| `scripts/export_email.py` | Fresh build, portability validation, HTML/text/EML export |
| `scripts/check_emails.py` | Validate a directory of built email issues |

The email shell uses presentation tables, system fonts, inline baseline styles,
and an Outlook conditional width wrapper. The container has both `align="center"`
and inline automatic side margins; logo/photo images also have automatic margins
so they do not rely on parent-cell alignment in Apple Mail. Body text remains
explicitly left-aligned. Media queries enhance mobile/dark
rendering; content and layout do not depend on them. The logo and its background
switch together in dark mode. This implementation does not guarantee identical
rendering across mail clients, and an actual recipient-client test is still part
of the workflow.

```sh
hugo --minify
hugo --minify --buildDrafts --destination /tmp/ballroom-email-check
python3 scripts/check_emails.py /tmp/ballroom-email-check
```

Pull requests run both builds and the email checker, and attach a separate
`ballroom-emails-preview` site artifact including drafts. The checker rejects missing
subjects/preheaders/alt text, relative or localhost URLs, scripts, external
stylesheets, and unresolved template output. Hugo also rejects missing snippets,
bad component options, and mismatched timetable rows. The export command reports
HTML size and warns on large messages. These checks do not verify whether remote
links still work or whether the prose accurately describes the current week.
