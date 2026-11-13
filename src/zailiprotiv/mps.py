"""Who an MP is across roll calls.

The report layout writes "SURNAME Given" in capitals, the listinzi "Given Surname", both with academic titles
(проф. др, мр, доц. др, прим.) wherever they fall. An MP's key is the words of the name without titles, lowercased
and sorted, so the word order and the titles don't matter: "АТЛАГИЋ проф. др МАРКО" and "проф. др Марко
Атлагић" are one key. Two MPs whose names have the same words would share a key; `clashes` finds that.
"""

from __future__ import annotations

import re
from collections import defaultdict

from zailiprotiv.rollcall import cyrillic

# Titles, lowercased, without their dot.
TITLES = {"проф", "др", "мр", "доц", "прим", "сц", "сци", "мед", "дипл", "инж", "академик", "ванр", "вет", "спец"}


# One person under two spellings (data/mp_aliases.json, entered by hand with the reason): the key of the one spelling
# → the key of the other. Empty until `load_aliases` is called; the site build calls it.
ALIASES: dict[str, str] = {}


def base_key(name: str) -> str:
    words = re.split(r"[\s.]+", cyrillic(name).lower().replace("і", "и"))
    return " ".join(sorted(w for w in words if w and w not in TITLES))


def key(name: str) -> str:
    k = base_key(name)
    return ALIASES.get(k, k)


def load_aliases(path) -> None:
    import json
    ALIASES.clear()
    if path.exists():
        for name, to in json.loads(path.read_text(encoding="utf-8")).items():
            ALIASES[base_key(name)] = base_key(to["is"])


def clashes(votes) -> dict[str, set[str]]:
    """Keys that stand for two rows in one vote: two MPs with the same name words (or a row read twice)."""
    out: dict[str, set[str]] = defaultdict(set)
    for v in votes:
        seen: dict[str, str] = {}
        for row in v["rows"]:
            k = key(row[1])
            if k in seen:
                out[k] |= {seen[k], row[1]}
            seen[k] = row[1]
    return dict(out)
