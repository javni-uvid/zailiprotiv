"""Names: the two scripts, and matching what the caption says to the site's list of MPs.

Only the standard library, so the repository's tests run it without the service's packages.
"""
from __future__ import annotations

import difflib
import json
import re
import unicodedata
from dataclasses import dataclass

_CYR = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "ђ": "đ", "е": "e", "ж": "ž", "з": "z", "и": "i", "ј": "j",
    "к": "k", "л": "l", "љ": "lj", "м": "m", "н": "n", "њ": "nj", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t",
    "ћ": "ć", "у": "u", "ф": "f", "х": "h", "ц": "c", "ч": "č", "џ": "dž", "ш": "š",
}
_LAT = {v: k for k, v in _CYR.items()}


def latin(text: str) -> str:
    """Serbian Cyrillic to Latin, letter by letter (Љ before a small letter is Lj)."""
    out = []
    for ch in text:
        low = ch.lower()
        if low in _CYR:
            m = _CYR[low]
            out.append(m if ch == low else m[:1].upper() + m[1:])
        else:
            out.append(ch)
    return "".join(out)


def cyrillic(text: str) -> str:
    """Latin to Serbian Cyrillic for names: lj, nj, dž are one letter each (names like "Injac" are rare enough)."""
    out, i = [], 0
    while i < len(text):
        two = text[i:i + 2]
        if two.lower() in _LAT:
            c = _LAT[two.lower()]
            out.append(c.upper() if two[0].isupper() else c)
            i += 2
            continue
        ch = text[i]
        c = _LAT.get(ch.lower())
        out.append((c.upper() if ch.isupper() else c) if c else ch)
        i += 1
    return "".join(out)


def normalize(text: str) -> str:
    """Either script, any case, with or without marks → plain small Latin letters and spaces."""
    text = latin(text).lower().replace("đ", "dj")
    text = "".join(ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch))
    return re.sub(r"[^a-z]+", " ", text).strip()


def words(text: str) -> list[str]:
    """The words of a name worth comparing (OCR leaves short bits of noise around)."""
    return [w for w in normalize(text).split() if len(w) >= 3]


def given_first(name: str) -> str:
    """"Jovanov Milenko" → "Milenko Jovanov": the site lists surnames first, people say names the other way round."""
    parts = name.split()
    return " ".join(parts[-1:] + parts[:-1])


@dataclass(frozen=True)
class Person:
    key: str      # the words of the name, sorted: one key for any order and either script
    name: str     # as the site writes it in lists ("Surname Given"), Latin
    slug: str = ""   # the MP's page on the site, if on the list
    group: str = ""  # the latest group the site knows


def person_key(name: str) -> str:
    return " ".join(sorted(words(name)))


class Roster:
    """The site's MPs (podaci.json: {"mps": [{"n": name, "s": slug, "g": group}]})."""

    def __init__(self, people: list[Person] | None = None):
        self.people = people or []
        # the lists and groups the site names, most MPs first ("Studentska lista", "Aleksandar Vučić - Srbija pobeđuje")
        count: dict[str, int] = {}
        for p in self.people:
            if p.group:
                count[p.group] = count.get(p.group, 0) + 1
        self.groups = sorted(count, key=lambda g: -count[g])
        self._by_len: dict[int, list[tuple[list[str], Person]]] = {}
        for p in self.people:
            ws = sorted(words(p.name))
            self._by_len.setdefault(len(ws), []).append((ws, p))

    @classmethod
    def from_json(cls, text: str) -> "Roster":
        data = json.loads(text)
        return cls([Person(person_key(m["n"]), m["n"], m.get("s", ""), m.get("g", "")) for m in data.get("mps", [])
                    if words(m.get("n", ""))])

    def match(self, line: str, threshold: float) -> Person | None:
        """The one MP whose every name word is on the line, each read closely enough; at most one word of noise
        beside them. Two MPs equally close: none (a guess would put words in someone's mouth)."""
        got = words(line)
        best: list[tuple[float, Person]] = []
        for n in (len(got), len(got) - 1):
            for want, p in self._by_len.get(n, []):
                scores = [max(difflib.SequenceMatcher(None, w, g).ratio() for g in got) for w in want]
                if min(scores) >= threshold:
                    best.append((sum(scores) / len(scores), p))
        if not best:
            return None
        best.sort(key=lambda b: -b[0])
        if len(best) > 1 and best[1][0] >= best[0][0] - 0.02 and best[1][1].key != best[0][1].key:
            return None
        return best[0][1]
