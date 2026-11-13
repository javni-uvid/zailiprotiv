"""The last steps on a built site: addresses without ".html", and the check that every page keeps the project's
rules (nothing loaded from another site, no page too heavy). Moved out of `site.py` (13 Nov 2026)."""
from __future__ import annotations

import re
from pathlib import Path

_HREF = re.compile(r'((?:href|content)=")([^":?#]*?)\.html((?:[#?][^"]*)?")')


def clean_urls(out: Path) -> None:
    """Addresses without ".html" (the maintainer, 13 Nov 2026): GitHub Pages serves page.html at /page, so the files
    keep their names and only the links change, in pages, feeds, the sitemap and the site's own scripts. "index"
    becomes the folder itself. A page that shares its name with a folder ("podaci.html" beside "podaci/") keeps its
    ending, as the short address would open the folder. Links to other sites are left as they are."""
    site = None
    cname = out / "CNAME"
    if cname.exists():
        site = "https://" + cname.read_text(encoding="utf-8").strip() + "/"

    def absolute(m):
        rel = m.group(2)
        if m.group(1).startswith("https://beleske."):  # the notes' pages live in a bucket, which serves files by their full name
            return m.group(0)
        if rel == "index" or rel.endswith("/index"):
            return m.group(1) + rel[:-5]
        return m.group(0) if (out / rel).is_dir() else m.group(1) + rel
    own = re.compile(r"(https://[^\s\"<>/]*zailiprotiv[^\s\"<>/]*/)([^\s\"<>?#]*?)\.html")
    for f in out.rglob("*"):
        if f.suffix == ".html":
            def link(m, here=f.parent):
                path = m.group(2)
                if path == "index" or path.endswith("/index"):
                    path = path[:-5] or "./"
                elif (here / path).is_dir():
                    return m.group(0)
                return m.group(1) + path + m.group(3)
            text = _HREF.sub(link, f.read_text(encoding="utf-8"))  # relative links: no scheme, so no colon
            if site:  # the page's one address, as the old ones with ".html" still open
                rel = f.relative_to(out).as_posix()[:-5]
                rel = rel[:-5] if rel == "index" or rel.endswith("/index") else rel + (".html" if (out / rel).is_dir() else "")
                text = text.replace("</head>", f'<link rel="canonical" href="{site}{rel}">\n</head>', 1)
            f.write_text(own.sub(absolute, text), encoding="utf-8")
        elif f.suffix == ".xml":
            f.write_text(own.sub(absolute, f.read_text(encoding="utf-8")), encoding="utf-8")
        elif f.suffix == ".js":
            text = f.read_text(encoding="utf-8")
            f.write_text(text.replace(' + ".html"', "").replace('glasaj.html"', 'glasaj"'), encoding="utf-8")


# What every built page must keep to (project principles): nothing loaded from another site, and pages light enough
# for a phone. The largest page now is under 0.6 MB.
PAGE_LIMIT = 1_000_000
# The one script from another server the pages may load: the visit counter (AGENTS.md, principle 5, second exception).
ANALYTICS = '<script type="module" src="https://static.cloudflareinsights.com/beacon.min.js"'
EXTERNAL = re.compile(r"<(?:script|iframe|img|source|video|audio|embed|object)\b[^>]*\bsrc=[\"'](?:https?:)?//"
                      r"|<link\b[^>]*\bhref=[\"'](?:https?:)?//[^\"']*[\"'][^>]*\brel=[\"'](?:stylesheet|preload|icon|modulepreload)"
                      r"|<link\b[^>]*\brel=[\"'](?:stylesheet|preload|icon|modulepreload)[\"'][^>]*\bhref=[\"'](?:https?:)?//"
                      r"|@import\s+url\(\s*[\"']?(?:https?:)?//|url\(\s*[\"']?(?:https?:)?//", re.I)


def check(out: Path) -> list[str]:
    """What is wrong with a built site: pages over the limit, anything loaded from another site."""
    bad = []
    for f in sorted(out.rglob("*")):
        if f.suffix not in (".html", ".css", ".js"):
            continue
        text = f.read_text(encoding="utf-8")
        if f.suffix == ".html" and len(text.encode()) > PAGE_LIMIT:
            bad.append(f"{f.relative_to(out)}: {len(text.encode()) / 1e6:.1f} MB")
        m = EXTERNAL.search(text.replace(ANALYTICS, ""))
        if m:
            bad.append(f"{f.relative_to(out)}: spoljni resurs: {m.group(0)[:80]}")
    return bad
