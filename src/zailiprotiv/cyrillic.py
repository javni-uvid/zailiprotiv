"""The Cyrillic edition: every page of the built site again under cir/, its text in Cyrillic.

The Assembly's documents are in Cyrillic and the site shows them in Latin (`translit.latin`); this goes back, with
the site's own Latin text. Letter by letter, except: Latin that is Latin by nature stays (addresses, file names,
model names, abbreviations like PDF and RSS, Roman numerals), and a few words where "nj", "lj" or "dž" are two
sounds (injekcija, nadživeti) are not read as one letter. Pages keep their names and links; files that are not pages
(styles, scripts, pictures, downloads, feeds) are not copied: the Cyrillic pages point to the one copy.
"""
from __future__ import annotations

import posixpath
import re
from pathlib import Path

_PAIRS = [("Lj", "Љ"), ("LJ", "Љ"), ("lj", "љ"), ("Nj", "Њ"), ("NJ", "Њ"), ("nj", "њ"), ("Dž", "Џ"), ("DŽ", "Џ"), ("dž", "џ")]
_TABLE = str.maketrans("ABVGDĐEŽZIJKLMNOPRSTĆUFHCČŠabvgdđežzijklmnoprstćufhcčš",
                       "АБВГДЂЕЖЗИЈКЛМНОПРСТЋУФХЦЧШабвгдђежзијклмнопрстћуфхцчш")
# Words in which the two letters are two sounds: kept apart with a mark the table drops.
_APART = re.compile(r"(?i)\b(i)(n)(j)(ekc|unkc)|\b(ko)(n)(j)(unk|ug)|\b(ta)(n)(j)(ug)|\b(va)(n)(j)(ezič)|"
                    r"\b(na)(d)(ž)(iv|nj)|\b(po)(d)(ž)(up)|\b(o)(d)(ž)(iv)")
# Latin by nature. Kept as written.
KEEP = {"PDF", "RSS", "CSV", "JSON", "HTML", "URL", "API", "AI", "GitHub", "Claude", "Anthropic", "Cloudflare", "Atom",
        "EXPO", "UniCredit", "NLB", "II", "III", "IV", "VI", "VII", "VIII", "IX", "XI", "XII", "XIII", "XIV", "XV",
        "XVI", "XVII", "XVIII", "XIX", "XX", "XXI", "Wikipedia", "Viber", "WhatsApp", "Instagram", "Google", "Worker"}
_PROTECT = re.compile(
    r"https?://\S+|[\w.+-]+@[\w-]+\.[\w.-]+"                                   # addresses, e-mail
    r"|\b[\w-]+(?:\.[\w-]+)*\.(?:rs|com|org|eu|si|fr|de|ca|uk|dev|json|csv|xml|html|js|pdf|png|md)\b(?:/[\w./#-]*)?"  # domains, files
    r"|\b[a-z]+(?:-[a-z0-9]+)*-\d[\w.-]*"                                      # claude-sonnet-5-5
    r"|&[a-zA-Z]+;|&#\d+;"                                                     # HTML entities
    r"|\b(?:" + "|".join(sorted(KEEP, key=len, reverse=True)) + r")\b")
_LATIN = re.compile(r"[A-Za-zČĆŽŠĐčćžšđ]")


def _plain(text: str) -> str:
    text = _APART.sub(lambda m: "".join(g + ("‌" if i % 4 == 1 else "") for i, g in
                                        enumerate(x for x in m.groups() if x is not None)), text)
    for a, b in _PAIRS:
        text = text.replace(a, b)
    return text.translate(_TABLE).replace("‌", "")


def cyr(text: str) -> str:
    """Latin Serbian text in Cyrillic."""
    if not _LATIN.search(text):
        return text
    out, last = [], 0
    for m in _PROTECT.finditer(text):
        out += [_plain(text[last:m.start()]), m.group()]
        last = m.end()
    out.append(_plain(text[last:]))
    return "".join(out)


_TAG = re.compile(r"(<!--.*?-->|<[^>]+>)", re.S)
_ATTR = re.compile(r'\b(alt|title|placeholder|aria-label)="([^"]*)"')
_LINK = re.compile(r'\b(href|src)="([^"#?:][^":]*?)([#?][^"]*)?"')
_PAGE = (".html", "/")
_SAID = re.compile(r'<meta (?:name="description"|property="og:(?:title|description|site_name)") content="([^"]*)"')


def page(html: str, rel: str) -> str:
    """One page in Cyrillic. `rel` is its path in the site ("zakon/x.html")."""
    here, up = posixpath.dirname(rel), "../" * (rel.count("/") + 1)

    def link(m):
        attr, path, rest = m.group(1), m.group(2), m.group(3) or ""
        if path.endswith(_PAGE) or path in (".", ".."):
            return m.group(0)  # a page: its Cyrillic twin has the same relative address
        return f'{attr}="{up}{posixpath.normpath(posixpath.join(here, path))}{rest}"'

    out, skip = [], None
    for part in _TAG.split(html):
        if part.startswith("<"):
            name = re.match(r"</?([a-zA-Z0-9]+)", part)
            tag = name.group(1).lower() if name else ""
            if skip:
                if part.startswith("</") and tag == skip:
                    skip = None
            elif tag in ("script", "style", "code") and not part.startswith("</") and not part.endswith("/>"):
                skip = tag
            if tag == "meta" and _SAID.match(part):
                part = part.replace(_SAID.match(part).group(1), cyr(_SAID.match(part).group(1)))
            elif tag == "html":
                part = part.replace('lang="sr-Latn"', 'lang="sr-Cyrl"')
            elif tag == "body":
                part = part.replace("<body", f'<body data-data="{up}"', 1)
            elif tag not in ("meta", "link") or "stylesheet" in part or "alternate" in part or "icon" in part:
                part = _ATTR.sub(lambda m: f'{m.group(1)}="{cyr(m.group(2))}"', part)
                part = _LINK.sub(link, part)
            out.append(part)
        else:
            out.append(part if skip else cyr(part))
    return "".join(out)


def edition(out: Path) -> int:
    """Write cir/<page> for every page of the site at `out`, and point each page and its twin at each other."""
    pages = [p for p in out.rglob("*.html") if "cir" not in p.relative_to(out).parts[:1]]
    for p in pages:
        rel = p.relative_to(out).as_posix()
        html = p.read_text(encoding="utf-8")
        up = "../" * rel.count("/")
        twin = out / "cir" / rel
        twin.parent.mkdir(parents=True, exist_ok=True)
        twin.write_text(page(html, rel).replace('href="#pismo"', f'href="../{up}{rel}"')
                        .replace(">Ћирилица</a>", ">Latinica</a>"), encoding="utf-8")
        p.write_text(html.replace('href="#pismo"', f'href="{up}cir/{rel}"'), encoding="utf-8")
    sitemap = out / "sitemap.xml"
    if sitemap.exists():  # the Cyrillic pages are pages too
        text = sitemap.read_text(encoding="utf-8")
        base = re.search(r"<loc>(https://[^/]+/)", text)
        if base:
            more = "".join(f"<url><loc>{base.group(1)}cir/{p.relative_to(out).as_posix()}</loc></url>\n" for p in sorted(pages))
            sitemap.write_text(text.replace("</urlset>", more + "</urlset>"), encoding="utf-8")
    return len(pages)
