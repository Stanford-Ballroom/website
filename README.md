# Stanford Ballroom website

A Hugo site with a local Stanford Ballroom design layer over Blowfish. The homepage
uses the club's existing copy and photographs; the Blowfish submodule continues to
provide article layouts, search, image zoom, and the appearance switcher.

## Edit the homepage

Open `content/_index.md` in GitHub and edit the text between shortcode tags. Keep
the opening and closing tags together. You can ask an AI editor to make these edits
in a pull request using the same file.

| Content | Where to edit |
| --- | --- |
| Main headline and photograph | `heading` and `image` in the `hero` shortcode |
| Introduction and contact links | Markdown inside `hero` |
| Lessons announcement | `title` and Markdown inside `announcement` |
| Questions and answers | `question` and Markdown inside each `faq` |
| Competition title, poster, link | Fields in `event-feature` |
| First photo grid | Existing files in `content/homepage-carousel/` |
| Final photo gallery | Existing files in `assets/gallery/` |
| Leadership and coach profiles | `content/about/index.md` |
| Calendar | Keep editing the existing Google Calendar |

To add a question, copy one complete `faq` block inside `faq-list`. To replace the
hero photograph, put the image in `assets/` and use its path relative to that
folder (for example, `gallery/03.png`). `alt` describes the photograph for screen
readers. Keep dates and other announcements up to date in the Markdown file.

The photo grids include every image matching their `images` pattern. Rename files
to control their alphabetical order. Hugo generates responsive WebP copies at
build time; original photographs stay unchanged. The competition poster is shown
in full, including its existing text and credits. Gallery photographs retain their
original proportions and support the theme's image zoom.

## Change the design

- `assets/css/custom.css`: typography, colors, spacing, and responsive layouts.
- `assets/css/schemes/ballroom.css`: matching Blowfish colors for secondary pages.
- `layouts/partials/header/ballroom.html`: navigation using the existing menu config.
- `layouts/partials/home/ballroom.html`: homepage wrapper.
- `layouts/shortcodes/`: homepage sections and profile cards.
- `layouts/partials/ballroom/image.html`: responsive local image rendering.
- `layouts/_default/baseof.html`: full-width shell, keeping Blowfish's head/footer.

The display font is Georgia with system fallbacks, so there are no external font
requests. The homepage has no autoplay, typing animation, or required custom
JavaScript. FAQs are expanded by default and can be collapsed with a keyboard or
touch. The navigation remains visible on small screens. Dark mode and reduced
motion preferences are supported.

Prefer local overrides instead of editing `themes/blowfish/`. After updating the
Blowfish submodule, compare its base template with our local `baseof.html` override.

## Preview and build

Use Hugo **0.150.0 extended**, matching the deployment workflows:

```sh
git clone --recurse-submodules https://github.com/Stanford-Ballroom/website.git
cd website
hugo server --disableFastRender
```

Open the local address printed by Hugo. Check the homepage, About Us, Schedule,
and Cardinal Classic at desktop and phone widths, and try search and dark mode.
For a production build:

```sh
hugo --minify
```

Pull requests run a build check and attach the generated site as an artifact.
Existing production deployment workflows still run on pushes to `main`.
