"""The MPs of a convocation before its first roll call (18 Nov 2026, the maintainer's request).

The site knows MPs from the roll calls, so a new convocation has none until its first vote. The Assembly's list of the
sitting MPs ("Aktuelni saziv", the page photos.py reads the portraits from) gives every one at once, with the party
that put them forward, place and year of birth: the table the archive of convocations has (mp_years.parse). It is
read into data/<N>/members.json for the newest convocation, and the site lists them (pages_members.py): an MP already
on the site by the roll calls of earlier convocations links to their page, a new one gets a page of their own. The
parliamentary groups are not in this table; they come later.
"""
from __future__ import annotations

import re

from zailiprotiv import mp_years, mps
from zailiprotiv.config import BASE

# The Cyrillic list of the sitting MPs, with the table. The Latin one (photos.PAGE) has the same rows but writes some
# names wrong ("VUCEVIC MILOŠ", a Cyrillic "м" in "DRECUN мr"); the Cyrillic one is the Assembly's own spelling.
URL = BASE + "/народна-скупштина/састав/народни-посланици/актуелни-сазив.11.html"


def clean(name: str) -> str:
    """"ПАСТОР проф. др БАЛИНТ (PÁSZTOR Prof. Dr BÁLINT)" → "ПАСТОР проф. др БАЛИНТ": the name in another language
    after it is left out, as the roll calls leave it out; "ЖИВКОВИЋ - ОБРАДОВИЋ" → "ЖИВКОВИЋ-ОБРАДОВИЋ"."""
    name = re.sub(r"\s*\([^)]*\)\s*", " ", name)
    return re.sub(r"\s*-\s*", "-", re.sub(r"\s+", " ", name)).strip()


def read(html: str) -> list[dict]:
    """The sitting MPs on the list: {"name", "party", "place", "year"}, the name as the Assembly writes it."""
    rows, _ = mp_years.parse(html)
    return [{**r, "name": clean(r["name"])} for r in rows]


def dumps(fetched: str, found: list[dict]) -> str:
    """data/<N>/members.json: one MP to a line, so a change shows as a small diff."""
    import json
    rows = ",\n".join(json.dumps(m, ensure_ascii=False, sort_keys=True) for m in found)
    return (f'{{"fetched": {json.dumps(fetched)}, "source": {json.dumps(URL, ensure_ascii=False)}, '
            f'"members": [\n{rows}\n]}}\n')


def key(name: str, conv: str) -> str:
    """The roll calls' key for a name on the list (mp_years.key), so a member is matched to an MP of the site."""
    return mp_years.key(name, conv)


def years(listed: dict[str, list[dict]], conv: str) -> dict[str, set[int]]:
    """Years of birth by roll-call key from the archive of earlier convocations (data/mp_years.json "listed"), to tell
    a returning MP from a namesake."""
    out: dict[str, set[int]] = {}
    for c, rows in listed.items():
        if c == conv:
            continue
        for r in rows:
            out.setdefault(mp_years.key(r["name"], c), set()).add(int(r["year"]))
    return out


def same_person(k: str, year: int, known: dict[str, set[int]]) -> bool:
    """A name of an earlier convocation is the same person unless the archive gives another year of birth (one year
    off is taken as a typo, as mp_years.check does)."""
    return k not in known or any(abs(y - year) <= 1 for y in known[k])


__all__ = ["URL", "clean", "read", "key", "years", "same_person", "mps"]
