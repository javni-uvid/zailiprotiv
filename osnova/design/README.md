# The family's look

What makes the sites of javni-uvid look like one family (20 Nov 2026, the maintainer's decision: the same fonts
and base colours on every site, and every site links the others). A site's own colours stay where they carry its
data (a vote, a warning, a list).

This folder is a copy. It is written in `javni-uvid/osnova` (`shared/design/`): change it there, never here.

| File | What |
|---|---|
| `osnova.css` | The font (Literata for headings, the system font for text), the page's base colours in both themes, the scale of letter sizes, the bar and the footer block. Values are `--ju-*`. |
| `fonts/` | Literata (OFL), served by the site itself. |
| `sites.json` | The family and its sites: address, name and a line on each, in both scripts. |
| `family.html` | The bar's and the footer block's markup, to be written the same on every site. |

## How a site uses it

1. Its build copies `osnova.css` and `fonts/` beside its own stylesheet, and every page loads `osnova.css` first.
2. Its own stylesheet takes the page's colours, the fonts and the sizes from the `--ju-*` values and declares no
   font or base colour of its own. `--ju-wide` is set to the width of the site's header.
3. Every page begins with the bar and ends with the footer block, as in `family.html`, filled from `sites.json`
   in the page's script, the site itself marked `aria-current="page"` in the bar.
4. A site's own dark switch sets `data-theme` on the root; without one the reader's system decides.

A new site is added to `sites.json` here; the others show it after their next copy and build.
