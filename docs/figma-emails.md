# Drafting Ballroom emails in Figma

The [Ballroom email kit](https://www.figma.com/design/UaIeCFn2H4Z65ByxNCg0pP?node-id=8-307)
provides editable components and a Week 5 sample based on the existing
announcements. Figma holds the issue being edited. A versioned JSON snapshot in
the repository records each exported issue, and the bridge generates the normal
Hugo Markdown source from it. Hugo continues to supply the HTML email shell,
archive pages, and Stanford-hosted webpages.

## Weekly workflow

1. Duplicate the [weekly template](https://www.figma.com/design/UaIeCFn2H4Z65ByxNCg0pP?node-id=8-124) in Figma. Edit its subject, title, send date,
   quarter, visible preview summary, and announcement components. Review dates,
   times, rooms, instructors, and links for the new week. Keep the component
   identities and named content fields so the bridge can recognize them.
   Select the hidden `Email/Settings` instance in Layers to edit subject, date,
   archive URL, quarter, and signer in its component properties. Edit the title
   and visible summary directly in their components. The
   [Week 5 sample](https://www.figma.com/design/UaIeCFn2H4Z65ByxNCg0pP?node-id=8-216)
   and its [dark preview](https://www.figma.com/design/UaIeCFn2H4Z65ByxNCg0pP?node-id=11-213)
   are separate from the reusable template.
2. With `Email/Issue` selected, run `design/figma/refresh-issue.js` through Figma
   after changing metadata. It refreshes the generated date eyebrow and browser
   link while preserving announcement copy. Then export using
   `design/figma/read-email.js` through the connected
   Figma MCP tool. This workflow needs no `FIGMA_TOKEN`. Save the resulting
   snapshot under `design/emails/`, using a new
   name for each issue. The Week 5 example is
   `design/emails/fall26-week5.json`.
3. Generate or check the Hugo issue:

   ```sh
   python3 scripts/sync_figma_email.py design/emails/fall26-week5.json
   python3 scripts/sync_figma_email.py design/emails/fall26-week5.json --check
   ```

   The generator writes `content/emails/fall26/week5.md` for this snapshot,
   with `draft: false`. Keep the snapshot and generated Markdown together in the
   same pull request. The check command catches edits that have not been
   regenerated. CI uses committed snapshots and generated content, so publishing
   needs no Figma token.
   The read script includes intentionally hidden metadata, checks protected
   logos and footer, and reports unsupported visual edits. Set its
   `ISSUE_NODE_ID` to an exact node ID when selection is unavailable. IDs,
   original logo hashes, and font mappings are recorded in `design/figma/kit.json`.
4. Open the PR's email preview and **Copy to Outlook** link. After review and
   merge, both pages are deployed at their permanent addresses. For Week 5:

   - Webpage: `https://ballroom.stanford.edu/emails/fall26/week5.html`
   - Copy page: `https://ballroom.stanford.edu/emails/fall26/week5.copy.html`

5. Open the copy page in a browser. Select the rendered email, including the
   summary above the logo and the mailing-list footer, and copy it. Paste into
   an Outlook message using **Keep Source Formatting**. Copy the subject from
   the issue metadata. Review the pasted message, then send a test to yourself
   through Outlook before mailing the list.

New photographs and posters must be committed and publicly deployed before
sending: the copy page deliberately uses the final public image URLs. The normal
PR webpage can show unpublished local assets; that preview does not establish
that their final public URLs are available yet.

## What survives the bridge

The kit maps supported Figma content to the existing email components rather
than exporting arbitrary canvas HTML. Component order determines announcement
order. The renderer remains responsible for client-specific HTML.

| Editable content | Hugo representation |
| --- | --- |
| Subject, title, send date, quarter, preview summary | Issue front matter and existing email header |
| Paragraphs, headings, emphasis, lists, text links | Markdown and email-specific render hooks |
| Lesson tracks, teachers, times, classes, shared notes | Per-issue schedule data and `email-lessons` |
| Practice and other events, including tentative or cancelled status | `email-event` |
| Information, warnings, and celebrations | `email-notice` |
| Registration and other action links | `email-button` |
| Photographs/posters with descriptions, captions, links, and widths | `email-photo` |
| Closing and signer | `email-signoff` |
| Supported Figma color, typography, and spacing variables | Per-issue `email_theme` tokens |
| Logo, browser link, list settings, and archive link | Existing email shell and site email configuration |

Use the kit's component properties, content fields, and supported Figma variables
for changes that should reach the email. The `email_theme` supports light/dark
colors, body/title/heading sizes and line heights, and content padding. Paragraphs
and lists remain editable rich text; the bridge translates them to Markdown
without accepting raw source HTML. Adding a new visual component requires an
explicit bridge mapping and email renderer support. Freeform positions, fonts,
effects, and decorative canvas elements do not define new HTML behavior.

## Email compatibility is part of the template

The reusable kit represents the same constraints as the existing email renderer:

- A 600-pixel maximum message width, proportional images, presentation tables,
  and an Outlook conditional width wrapper.
- Inline baseline colors, fonts, spacing, and table styling, plus system-font
  fallbacks. Content remains readable when head styles are discarded.
- A visible preview summary as the first body text, so it remains present when
  the rendered page is copied.
- A descriptive alt text and numeric width for each image. PNG, JPEG, and GIF
  are supported; Hugo processes committed local image assets as before.
- Absolute public image and link URLs, the browser-version link, and the
  mailing-list settings/unsubscribe footer.
- Per-issue schedule snapshots, so later timetable changes cannot rewrite past
  announcements.

The regular email HTML retains its optional mobile and dark-mode enhancements,
including the light/dark logo switch. The `.copy.html` variant uses one light-mode
logo and inline baseline styles, with no stylesheet or script, because Outlook
may discard head styles during paste. Outlook and recipient clients can still
apply their own dark-mode or paste transformations. An Outlook test message is
the final check for the chosen sending path.

The Figma body uses Arimo as the editable counterpart to the email's Arial /
Helvetica stack, and Gelasio for its Georgia headings. HTML keeps the existing
system fonts, so line wrapping can differ slightly. The two original PNG logos
are preserved exactly and swap with the preview's light/dark mode.

## Build and validation

Both the production deployment and PR-preview workflow build Hugo once in its
normal mode and once with `--environment email`. The latter omits the hosted
WhatsApp helper. The copy-page builder validates the script-free output and
creates `.copy.html` only for standalone email issues also present in the site
being deployed. Drafts and future issues from an inclusive test build therefore
cannot appear in production through the copy step. Archives keep their normal
website layout.

To build locally with Hugo 0.150.0 extended:

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
hugo --minify
hugo --environment email --minify --destination .email-build
python3 scripts/check_emails.py --email-only .email-build
python3 scripts/build_email_copy.py --email-dir .email-build --site-dir public
```

Use a temporary output directory outside the repository when preferred. To
review draft/future content locally, add `--buildDrafts --buildFuture` to both
Hugo commands. The normal published build omits those flags.

For a single local export with HTML, text, EML, and a copy page:

```sh
python3 scripts/export_email.py fall26/week5 --copy-paste
```

CI checks every committed Figma snapshot against its generated Markdown before
either a PR preview or a production build. The checks reject active content,
scripts in exported mail, external/dynamic
CSS, unsupported image formats, missing descriptions, temporary Figma asset
URLs, local/private URLs, missing email-shell fallbacks, and unresolved template
output. The copy conversion also verifies that the visible text, links,
preheader, and footer remain unchanged. They do not prove how a particular
Outlook version transforms clipboard HTML, or verify that event details and
external URLs are current.

For the original Markdown authoring, image processing, WhatsApp copy view, and
export details, see [emails.md](emails.md).
