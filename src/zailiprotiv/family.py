"""The family's look and links (Javni uvid): what this site takes from `osnova/design/`, the copy of
javni-uvid/osnova's `shared/design/`.

The stylesheet the site serves is the family's (`osnova.css`: the font, the base colours, the scale of sizes, the
bar and the footer block) followed by the site's own, as one file, so a page asks for one stylesheet as before.
The bar and the footer block are written here from `sites.json`, the same markup on every site of the family
(`osnova/design/family.html`), for the pages made from templates and for the notes' pages alike."""

import html
import json
from functools import cache
from pathlib import Path

HERE = Path(__file__).parent
DESIGN = HERE.parents[1] / "osnova" / "design"
ME = "zailiprotiv"  # this site's id in sites.json
MARK = (
    '<svg class="ju-mark" viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="3" '
    'fill="none" stroke="currentColor" stroke-width="2.4"/><circle cx="12" cy="12" r="3.4" fill="currentColor"/></svg>'
)


def stylesheet() -> bytes:
    """The one stylesheet the site serves: the family's, then the site's own."""
    return (DESIGN / "osnova.css").read_bytes() + b"\n" + (HERE / "static" / "style.css").read_bytes()


def write_stylesheet(out: Path) -> None:
    (out / "style.css").write_bytes(stylesheet())


@cache
def sites() -> dict:
    return json.loads((DESIGN / "sites.json").read_text(encoding="utf-8"))


def _a(target: dict, script: str, home: str, text: str, attrs: str = "", twin: bool = True) -> str:
    """A link to the family's page or to one of its sites, in `script`. On a Latin page made from a template the
    Cyrillic address rides along (data-cir-href), for the Cyrillic twin the build makes of it (cyrillic.page)."""
    if target.get("id") == ME:
        href, other = home, ""
    else:
        href = target["url"][script]
        other = f' data-cir-href="{html.escape(target["url"]["cyr"])}"' if twin and script == "lat" else ""
    return f'<a{attrs} href="{html.escape(href)}"{other}>{text}</a>'


def bar(script: str = "lat", home: str = "index.html", twin: bool = True) -> str:
    """The family's bar, first in the page: the family's name, then its sites, this one marked. `home` is the
    address of this site's first page as seen from the page the bar is on; `twin` is off for a page written in
    its own script, with no Cyrillic twin made of it (the notes' pages)."""
    data = sites()
    fam = data["family"]
    name = html.escape(fam["name"][script])
    links = "".join(
        "\n    " + _a(s, script, home, html.escape(s["name"][script]), ' aria-current="page"' if s["id"] == ME else "", twin)
        for s in data["sites"]
    )
    return (
        f'<nav class="ju-bar" aria-label="{name}">\n  <div class="ju-bar-in">\n'
        f'    {_a(fam, script, home, MARK + name, " class=\"ju-name\"", twin)}{links}\n  </div>\n</nav>'
    )


def foot(script: str = "lat", home: str = "index.html") -> str:
    """The family's block in the footer: what the family promises, and its sites with a line on each."""
    data = sites()
    fam = data["family"]
    name = html.escape(fam["name"][script])
    items = "".join(
        f'\n    <li>{_a(s, script, home, html.escape(s["name"][script]))}<span>{html.escape(s["about"][script])}</span></li>'
        for s in data["sites"]
    )
    principles = {"url": {k: v + "#nacela" for k, v in fam["url"].items()}}
    return (
        f'<section class="ju-foot" aria-label="{name}">\n  <h2>{_a(fam, script, home, MARK + name)}</h2>\n'
        f'  <p>{html.escape(fam["promise"][script])} {_a(principles, script, home, html.escape(fam["principles"][script]))}</p>\n'
        f"  <ul>{items}\n  </ul>\n</section>"
    )
