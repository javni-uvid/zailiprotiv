"""The last steps on a built site: addresses without ".html", and the check that every page keeps the project's
rules (nothing loaded from another site, no page too heavy). Moved out of `site.py` (13 Nov 2026)."""
from __future__ import annotations

import os
import posixpath
import re
from pathlib import Path

_HREF = re.compile(r'((?:href|content)=")([^":?#]*?)\.html((?:[#?][^"]*)?")')


_TITLE = re.compile(r"<title>([^<]*)</title>")
_SAID = re.compile(r'(<meta (?:name="description"|property="og:description") content=")([^"]*)(")')
_BRAND = (" — Za ili Protiv", " — За или Против")


def fit_head(text: str) -> str:
    """A page's title and description cut to what search engines show (about 65 and 160 characters, Bing's advice):
    a long title loses the site's name at its end, a long description is cut between words."""
    def title(m):
        t = m.group(1)
        for brand in _BRAND:
            if len(t) > 65 and t.endswith(brand):
                t = t[: -len(brand)]
        return f"<title>{t}</title>"

    def said(m):
        d = m.group(2)
        if len(d) > 160:
            d = d[:157].rsplit(" ", 1)[0].rstrip(" ,;:–—") + "…"
        return m.group(1) + d + m.group(3)
    return _SAID.sub(said, _TITLE.sub(title, text, 1))


_CRUMBS = re.compile(r'<p class="crumbs">(.*?)</p>', re.S)
_CRUMB = re.compile(r'<a href="([^"#]*)">([^<]+)</a>')
_H1 = re.compile(r"<h1\b[^>]*>(.*?)</h1>", re.S)


def structured(text: str, site: str, here: str, address: str) -> str:
    """Schema.org data for search engines, made from what the page already shows: the site's name on the home page
    (Google shows it above the results), and the page's place in the site (its crumbs, then the page itself)."""
    import html as html_
    import json
    import posixpath
    data = None
    if address == "":  # the site's name: on the home page only (the Cyrillic one is a page of the site, not its home)
        data = {"@context": "https://schema.org", "@graph": [
            {"@type": "WebSite", "@id": site + "#site", "name": "Za ili Protiv", "alternateName": "zailiprotiv.rs",
             "url": site, "inLanguage": "sr", "publisher": {"@id": site + "#org"}},
            {"@type": "Organization", "@id": site + "#org", "name": "Za ili Protiv", "alternateName": "zailiprotiv.rs",
             "url": site, "logo": site + "logo.png", "email": "kontakt@zailiprotiv.rs",
             "description": "Nezavisan sajt koji iz primarnih izvora Narodne skupštine Srbije pokazuje zakone i kako je glasao "
                            "svaki poslanik, od 2012. Ista pravila za sve, bez ocena.",
             "sameAs": ["https://github.com/javni-uvid/zailiprotiv"]}]}
    else:
        crumbs, h1 = _CRUMBS.search(text), _H1.search(text)
        if crumbs and h1:
            items = []
            for href, name in _CRUMB.findall(crumbs.group(1)):
                if not href or href.startswith("http"):
                    continue
                path = posixpath.normpath(posixpath.join(here, href))
                path = "" if path in (".", "index") else path[:-5] if path.endswith("/index") else path + ("/" if href.endswith("/") and path != "." else "")
                url = site + path
                items.append((html_.unescape(name).strip(), url))
            items.append((html_.unescape(re.sub(r"<[^>]+>", "", h1.group(1))).strip(), site + address))
            if len(items) > 1:
                data = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
                    {"@type": "ListItem", "position": i + 1, "name": n, "item": u} for i, (n, u) in enumerate(items)]}
    if not data:
        return text
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return text.replace("</head>", f'<script type="application/ld+json">{blob}</script>\n</head>', 1)


# What a worker of clean_urls needs, set once per process (the folders are many: sent once, not with every file).
_CLEAN: dict = {}


def _clean_init(out: str, site: str | None, folders: set[str]) -> None:
    _CLEAN.update(out=Path(out), site=site, folders=folders)


def _clean_file(name: str) -> None:
    """One file of clean_urls."""
    out, site, folders = _CLEAN["out"], _CLEAN["site"], _CLEAN["folders"]
    f = Path(name)

    def absolute(m):
        rel = m.group(2)
        if m.group(1).startswith("https://beleske."):  # the notes' pages live in a bucket, which serves files by their full name
            return m.group(0)
        if rel == "index" or rel.endswith("/index"):
            return m.group(1) + rel[:-5]
        return m.group(0) if os.path.normpath(os.path.join(out, rel)) in folders else m.group(1) + rel
    if f.suffix == ".html":
        def link(m, here=str(f.parent)):
            path = m.group(2)
            if path == "index" or path.endswith("/index"):
                path = path[:-5] or "./"
            elif os.path.normpath(os.path.join(here, path)) in folders:
                return m.group(0)
            return m.group(1) + path + m.group(3)
        text = fit_head(_HREF.sub(link, f.read_text(encoding="utf-8")))  # relative links: no scheme, so no colon
        if site:  # the page's one address, as the old ones with ".html" still open, and its twin in the other script
            def address(file: str) -> str:
                rel = file[:-5]
                return rel[:-5] if rel == "index" or rel.endswith("/index") else rel + (".html" if os.path.normpath(os.path.join(out, rel)) in folders else "")
            file = f.relative_to(out).as_posix()
            if f.name == "404.html":  # served at any address: not a page of its own
                f.write_text(_OWN.sub(absolute, text.replace("</head>", '<meta name="robots" content="noindex">\n</head>', 1)), encoding="utf-8")
                return
            here = posixpath.dirname(file)
            text = structured(text, site, here, address(file))
            # A page that names its own canonical address (one that sends on to another) keeps it.
            head = "" if 'rel="canonical"' in text else f'<link rel="canonical" href="{site}{address(file)}">\n'
            twin = file[4:] if file.startswith("cir/") else "cir/" + file
            if (out / twin).exists():
                lat, cyr = (twin, file) if file.startswith("cir/") else (file, twin)
                head += (f'<link rel="alternate" hreflang="sr-Latn" href="{site}{address(lat)}">\n'
                         f'<link rel="alternate" hreflang="sr-Cyrl" href="{site}{address(cyr)}">\n'
                         f'<link rel="alternate" hreflang="x-default" href="{site}{address(lat)}">\n')
            text = text.replace("</head>", head + "</head>", 1)
        f.write_text(_OWN.sub(absolute, text), encoding="utf-8")
    elif f.suffix == ".xml":
        f.write_text(_OWN.sub(absolute, f.read_text(encoding="utf-8")), encoding="utf-8")
    elif f.suffix == ".js":
        text = f.read_text(encoding="utf-8")
        f.write_text(text.replace(' + ".html"', "").replace('glasaj.html"', 'glasaj"'), encoding="utf-8")


_OWN = re.compile(r"(https://[^\s\"<>/]*zailiprotiv[^\s\"<>/]*/)([^\s\"<>?#]*?)\.html")


def _pool_map(fn, items: list, init=None, initargs=()) -> list:
    """fn over items on the machine's processors (a GitHub runner has four), or here when there are few. Each item
    is a file of its own, so the result is the same either way, in the same order."""
    from concurrent.futures import ProcessPoolExecutor
    workers = min(os.cpu_count() or 1, 8)
    if workers > 1 and len(items) > 200:
        with ProcessPoolExecutor(workers, initializer=init, initargs=initargs) as pool:
            return list(pool.map(fn, items, chunksize=64))
    if init:
        init(*initargs)
    return [fn(x) for x in items]


def clean_urls(out: Path) -> None:
    """Addresses without ".html" (the maintainer, 13 Nov 2026): GitHub Pages serves page.html at /page, so the files
    keep their names and only the links change, in pages, feeds, the sitemap and the site's own scripts. "index"
    becomes the folder itself. A page that shares its name with a folder ("podaci.html" beside "podaci/") keeps its
    ending, as the short address would open the folder. Links to other sites are left as they are. Each file is
    changed on its own, so the files are shared among the machine's processors."""
    site = None
    cname = out / "CNAME"
    if cname.exists():
        site = "https://" + cname.read_text(encoding="utf-8").strip() + "/"
    # The site's folders, listed once: asking the disk about each of two million links took a minute.
    folders = {os.path.normpath(d) for d, _, _ in os.walk(out)}
    files = [str(f) for f in out.rglob("*") if f.suffix in (".html", ".xml", ".js")]
    _pool_map(_clean_file, files, _clean_init, (str(out), site, folders))


# What every built page must keep to (project principles): nothing loaded from another site, and pages light enough
# for a phone. The largest page now is under 0.6 MB.
PAGE_LIMIT = 1_000_000
# The one script from another server the pages may load: the visit counter (AGENTS.md, principle 5, second exception).
ANALYTICS = '<script type="module" src="https://static.cloudflareinsights.com/beacon.min.js"'
EXTERNAL = re.compile(r"<(?:script|iframe|img|source|video|audio|embed|object)\b[^>]*\bsrc=[\"'](?:https?:)?//"
                      r"|<link\b[^>]*\bhref=[\"'](?:https?:)?//[^\"']*[\"'][^>]*\brel=[\"'](?:stylesheet|preload|icon|modulepreload)"
                      r"|<link\b[^>]*\brel=[\"'](?:stylesheet|preload|icon|modulepreload)[\"'][^>]*\bhref=[\"'](?:https?:)?//"
                      r"|@import\s+url\(\s*[\"']?(?:https?:)?//|url\(\s*[\"']?(?:https?:)?//", re.I)


def _check_file(job: tuple[str, str]) -> list[str]:
    out, name = Path(job[0]), job[1]
    f, bad = out / name, []
    text = f.read_text(encoding="utf-8")
    if f.suffix == ".html" and len(text.encode()) > PAGE_LIMIT:
        bad.append(f"{name}: {len(text.encode()) / 1e6:.1f} MB")
    m = EXTERNAL.search(text.replace(ANALYTICS, ""))
    if m:
        bad.append(f"{name}: spoljni resurs: {m.group(0)[:80]}")
    return bad


def check(out: Path) -> list[str]:
    """What is wrong with a built site: pages over the limit, anything loaded from another site."""
    jobs = [(str(out), f.relative_to(out).as_posix()) for f in sorted(out.rglob("*")) if f.suffix in (".html", ".css", ".js")]
    return [b for found in _pool_map(_check_file, jobs) for b in found]
