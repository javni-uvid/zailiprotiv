"""The MPs of a convocation before its first roll call (18 Nov 2026, the maintainer's request).

The site knows MPs from the roll calls, so a new convocation has none until its first vote. The Assembly's list of the
sitting MPs ("Aktuelni saziv", the page photos.py reads the portraits from) gives every one at once, with the party
that put them forward, place and year of birth: the table the archive of convocations has (mp_years.parse). It is
read into data/<N>/members.json for the newest convocation, and the site lists them (pages_members.py): an MP already
on the site by the roll calls of earlier convocations links to their page, a new one gets a page of their own.

The parliamentary groups (18 Nov 2026) are not in the table: the page's form filters it by group ("group" in the
query, with "submitted=true"), so each group's MPs are read from the page filtered by it, the group named as the
form's list names it ("Посланичка група „Студентска листа“"), the MPs in none as "" (the form's "not members").

The occupation (19 Nov 2026, for the live page's lines about the speaker) is on each MP's own page at the Assembly,
linked from the list: read once per MP ("occupation", "" when the Assembly gives none) and kept from run to run.
"""
from __future__ import annotations

import re

from html.parser import HTMLParser

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


class _Groups(HTMLParser):
    def __init__(self):
        super().__init__()
        self.found, self._in, self._value, self._text = [], False, None, []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "select":
            self._in = a.get("name") == "group"
        elif tag == "option" and self._in:
            self._value, self._text = a.get("value"), []

    def handle_data(self, data):
        if self._value is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == "option" and self._value is not None:
            if self._value not in ("", "0"):
                self.found.append((self._value, re.sub(r"\s+", " ", "".join(self._text)).strip()))
            self._value = None
        elif tag == "select":
            self._in = False


NOT_IN_A_GROUP = re.compile(r"нису чланови|nisu članovi", re.I)


def groups(html: str) -> list[tuple[str, str]]:
    """The parliamentary groups the page's form offers: (its value, its name), the MPs in none ("Народни посланици
    који нису чланови посланичких група") among them."""
    p = _Groups()
    p.feed(html)
    return p.found


def group_url(value: str) -> str:
    return f"{URL}?submitted=true&group={value}"


def group_name(label: str) -> str:
    """"Посланичка група „Студентска листа“" → "Студентска листа"; the MPs in no group → ""."""
    if NOT_IN_A_GROUP.search(label):
        return ""
    return re.sub(r"^Посланичка група\s*", "", label).strip().strip("„“\"").strip()


def with_groups(found: list[dict], by_group: dict[str, list[dict]]) -> list[dict]:
    """Each MP with their group ("group": the name, "" for none; absent when no group's page lists them)."""
    of = {}
    for label, rows in by_group.items():
        for r in rows:
            of[clean(r["name"])] = group_name(label)
    return [{**m, **({"group": of[m["name"]]} if m["name"] in of else {})} for m in found]


_MP_PAGE = re.compile(r'<a\s+href="(/[^"]+\.\d+\.245\.html)"[^>]*>\s*([^<]+?)\s*</a>')
_OCCUPATION = re.compile(r"<h4>\s*Занимање\s*</h4>\s*<p>(.*?)</p>", re.S)


def pages(html: str) -> dict[str, str]:
    """Each MP's own page at the Assembly, by the name as the list writes it (cleaned as `read` cleans it)."""
    return {clean(name): BASE + href for href, name in _MP_PAGE.findall(html)}


def occupation(html: str) -> str:
    """The occupation the Assembly gives on an MP's page ("Занимање": "лекар"); "" when it gives none."""
    m = _OCCUPATION.search(html)
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m.group(1))).strip() if m else ""
    return "" if text in ("", "-", "–") else text


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
