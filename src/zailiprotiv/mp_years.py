"""Who an MP is, checked by the year of birth the Assembly gives (17 Nov 2026).

The site knows an MP by the words of the name (mps.key), so two people of one name in different convocations become
one MP (Aleksandar Jovanović of PUPS, 2020, and Aleksandar Jovanović Ćuta, from 2022, were one page). The Assembly's
archive of each convocation's MPs ("Arhiva saziva") lists every MP with party, place and year of birth: one table,
"Ime i prezime narodnog poslanika | Politička stranka … | Mesto | Godište". `check` compares those years across
convocations for every name of the roll calls; a name whose year differs is two people, to be split by hand in
data/mp_splits.json (mps.SPLITS), with the reason.
"""
from __future__ import annotations

import datetime as dt
import re
import urllib.parse
from collections import defaultdict
from html.parser import HTMLParser

from zailiprotiv import mps
from zailiprotiv.config import BASE, CONVOCATIONS
from zailiprotiv.cyrillic import cyr

# One page of the archive; it links the others.
START = BASE + "/narodna-skupstina-/sastav/narodni-poslanici/arhiva-saziva/saziv-od-6-februara-2024-.5175.html"
_ARCHIVE = "/narodni-poslanici/arhiva-saziva/"
_MONTHS = ("januara", "februara", "marta", "aprila", "maja", "juna", "jula", "avgusta", "septembra", "oktobra",
           "novembra", "decembra")
_DATE = re.compile(r"saziv-od-(\d{1,2})-([a-z]+)-(\d{4})")


class _Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.rows = [], []
        self._row, self._cell = None, None

    def handle_starttag(self, tag, attrs):
        if tag == "a" and _ARCHIVE in urllib.parse.unquote(dict(attrs).get("href") or ""):
            self.links.append(urllib.parse.urljoin(BASE, dict(attrs)["href"]))
        elif tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append(re.sub(r"\s+", " ", "".join(self._cell)).strip())
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None


def parse(html: str) -> tuple[list[dict], list[str]]:
    """The MPs in a page of the archive ({"name", "party", "place", "year"}) and the pages of the archive it links."""
    p = _Page()
    p.feed(html)
    mps_ = []
    for row in p.rows:
        if len(row) == 4 and (m := re.fullmatch(r"((?:19|20)\d\d)\.?", row[3])):
            mps_.append({"name": row[0], "party": row[1], "place": row[2], "year": int(m.group(1))})
    return mps_, sorted(set(p.links))


def convocation(url: str) -> str | None:
    """The convocation an archive page is of, by the day in its address ("saziv-od-3-avgusta-2020")."""
    m = _DATE.search(urllib.parse.unquote(url))
    if not m or m.group(2) not in _MONTHS:
        return None
    day = dt.date(int(m.group(3)), _MONTHS.index(m.group(2)) + 1, int(m.group(1))).isoformat()
    return next((c for c, conf in CONVOCATIONS.items() if conf["from"] == day), None)


def key(name: str, conv: str) -> str:
    """The roll calls' key for an archive name ("MARKOVIĆ DRAGAN D.", "ACKOVIĆ dr DRAGOLjUB"), split as they are."""
    return mps.key(mps.split(cyr(name.title()), conv))


def check(listed: dict[str, list[dict]], seated: dict[str, set[str]]) -> dict:
    """Names whose year of birth differs between convocations, names listed twice in one, and MPs of the roll calls
    the archive doesn't list. listed: {convocation: archive rows}; seated: {convocation: roll-call keys}."""
    years: dict[str, dict[str, set[int]]] = defaultdict(lambda: defaultdict(set))
    places: dict[str, set[str]] = defaultdict(set)
    twice, keys_of = [], {}
    for conv, rows in listed.items():
        seen = defaultdict(list)
        for r in rows:
            k = key(r["name"], conv)
            years[k][conv].add(r["year"])
            if not re.match(r"\d", r["place"]):  # an MP who left has the dates of the mandate there instead
                places[k].add(r["place"].split(",")[0].strip())
            seen[k].append(r)
        twice += [{"convocation": conv, "rows": rs} for rs in seen.values() if len(rs) > 1]
        keys_of[conv] = set(seen)
        for k, rs in seen.items():  # two namesakes in one convocation: listed under "twice", not compared here
            if len(rs) > 1:
                del years[k][conv]
    differ = []
    for k, by in years.items():
        all_years = sorted(set().union(*by.values()))
        gap = all_years[-1] - all_years[0]
        # A year off by one may be a typo; with another town too, it is another person (Nataša Jovanović,
        # Mladenovac 1967 and Kragujevac 1966).
        if len(by) > 1 and (gap > 1 or (gap == 1 and len(places[k]) > 1)):
            differ.append({"key": k, "years": {c: sorted(y) for c, y in sorted(by.items(), key=lambda c: int(c[0]))},
                           "places": sorted(places[k])})
    missing = {c: sorted(keys - keys_of[c]) for c, keys in seated.items() if c in keys_of}
    return {"differ": sorted(differ, key=lambda d: d["key"]), "twice": twice,
            "missing": {c: ks for c, ks in missing.items() if ks}}
