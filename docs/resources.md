# Resources page

Edit `content/resources/index.md`. The main navigation entry is in
`config/_default/menus.en.toml`. Music and demonstration links are paired by dance;
Spotify sharing parameters were removed while preserving every playlist ID.

## Upload the original images

The Notion image URLs were not transferred. Each `resource-image` shortcode has a
placeholder `src` path. Upload the matching file to `static/images/resources/`
using the filename below. The next build automatically replaces its labeled
placeholder with the photo. If the file extension differs, update `src` too.
Alternatively, replace `src` with an HTTPS image URL. No image is encoded inline.

The `alt` and `caption` fields remain editable beside each URL. The examples use
`object-fit: contain` so the full clothing or shoe image stays visible. Missing
local files render a labeled panel without requesting a broken image URL.

| Example | Filename in `static/images/resources/` | Original Notion asset ID |
| --- | --- | --- |
| Followers: Latin shoes | `followers-latin-shoes.jpg` | `61b41b7e-b2e7-4072-92ff-b57b01bdd569` |
| Unisex: practice shoes | `practice-shoes.jpg` | `be2cb977-63dc-4972-86f9-0b5fed754355` |
| Followers: Standard shoes | `followers-standard-shoes.jpg` | `35f8bb65-c984-4691-9ae5-5141452be776` |
| Leaders: Latin shoes | `leaders-latin-shoes.jpg` | `04c1a4b8-b310-49d3-8c90-dec4a67a0d49` |
| Leaders: Standard shoes | `leaders-standard-shoes.jpg` | `7163c40d-7337-4619-9ba3-22b8eb9e9be9` |
| Followers: Latin clothes | `followers-latin-clothes.png` | `cd1211d6-932b-40b6-a106-ceefde63f5de` |
| Followers: Latin / Standard clothes | `followers-latin-standard-clothes.png` | `0a4e6ff8-f433-410c-a712-978bb89fcd0d` |
| Followers: Standard clothes, first example | `followers-standard-clothes-1.png` | `34b55249-0270-4a0f-87cf-d1616a611ed5` |
| Followers: Standard clothes, second example | `followers-standard-clothes-2.png` | `84276335-151c-4e26-bb26-fcc3e5997271` |
| Leaders: Latin clothes | `leaders-latin-clothes.png` | `da57bddb-acda-44c1-a1dc-d438ea4f869a` |
| Leaders: Standard clothes | `leaders-standard-clothes.png` | `63b64670-adeb-4465-b0e6-7a346de1b084` |

## Check changes

Build with `hugo --minify` and review `/resources/` in light and dark mode at phone
and desktop widths. Also check a PR preview to confirm internal links and uploaded
image paths retain its `/pr-preview-<number>/` prefix.
