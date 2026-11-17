"""The recordings of the plenary sittings, from the Assembly's video archive.

The Assembly's page "Prenosi" leads to an archive kept by its broadcaster (videonet.co.rs): per convocation, a page
of the plenary sittings (config.CONVOCATIONS[n]["videos"]) with, for each sitting day, the recording in parts
(I, II, ...) as MP4 files, newest first:

    <p ...>наставак Десетог ванредног заседања ... у Четрнаестом сазиву 28.08.2026.(II) (<a href="…/zas2026082810a.mp4">MP4 620MB</a> / <a href="…mpg">MPEG …</a>)</p>

The site links to these files by the day of the sitting (17 Nov 2026); it does not play them itself (principle 5).
Older entries give the files by an address of numbers over plain http; the same files are served at
`arhiva.videonet.co.rs` over https (checked 17 Nov 2026), so every file is linked there.
"""
from __future__ import annotations

import html
import re

ARCHIVE = "https://arhiva.videonet.co.rs"
_P = re.compile(r"(?is)<p\b[^>]*>(.*?)</p>")
_MP4 = re.compile(r'(?i)href\s*=\s*["\']([^"\']+?\.mp4)["\']')
_DATE = re.compile(r"(\d{1,2})\.\s?(\d{1,2})\.\s?(\d{4})\.?")
_PART = re.compile(r"\(\s*([IVX]+)\s*\)")
_ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10}


def https(url: str) -> str:
    """A recording's address at the archive's https host (the path from /filesnsrs/ on), else as given."""
    m = re.search(r"/filesnsrs/.+", url)
    return ARCHIVE + m.group(0) if m else url


def parse(page: str) -> list[dict]:
    """Every recording on an archive page: {"date": ISO day, "part": 1.., "title": the entry's words, "url": MP4}."""
    found = []
    for block in _P.findall(page):
        mp4 = _MP4.search(block)
        if not mp4:
            continue
        text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", block))).strip()
        date = _DATE.search(text)
        if not date:
            continue
        d, m, y = (int(x) for x in date.groups())
        part = _PART.search(text, date.end())
        title = text[:date.start()].strip(" -–,")
        found.append({"date": f"{y:04d}-{m:02d}-{d:02d}", "part": _ROMAN.get(part.group(1), 1) if part else 1,
                      "title": title, "url": https(html.unescape(mp4.group(1)))})
    return found


def by_day(entries: list[dict]) -> dict[str, list[dict]]:
    """The recordings of each day, parts in order; the same file listed twice is kept once."""
    days: dict[str, list[dict]] = {}
    seen = set()
    for e in entries:
        if e["url"] in seen:
            continue
        seen.add(e["url"])
        days.setdefault(e["date"], []).append({"part": e["part"], "title": e["title"], "url": e["url"]})
    for parts in days.values():
        parts.sort(key=lambda p: (p["title"], p["part"]))
    return dict(sorted(days.items()))
