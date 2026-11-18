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

    current: frozenset = frozenset()  # the slugs of the sitting convocation's MPs (mikrofon-poslanici.json)

    def match(self, line: str, threshold: float) -> Person | None:
        """The MP the line names. First among the sitting convocation's MPs, then among all: every word of the MP's
        name on the line, each read closely enough, at most one word of noise beside them; failing that, among the
        sitting convocation's MPs only, the clearly nearest name (OCR drops or blurs letters: "Blagoj Milica
        Vasiljević" for Milica Vasiljević Blagojević, 18 Nov 2026). Two MPs equally close: none (a guess would put
        words in someone's mouth)."""
        got = words(line)
        if not got:
            return None
        now = [p for p in self.people if p.slug in self.current] if self.current else []
        for pool in ([now] if now else []) + [self.people]:
            hit = self._strict(got, pool, threshold)
            if hit:
                return hit
        return self._nearest(got, now) if now else None

    @staticmethod
    def _score(want: list[str], got: list[str]) -> list[float]:
        def one(w: str, g: str) -> float:
            if len(g) >= 4 and (w.startswith(g) or g.startswith(w)):  # a word cut short at the caption's edge
                return 0.9
            return difflib.SequenceMatcher(None, w, g).ratio()
        return [max(one(w, g) for g in got) for w in want]

    def _strict(self, got: list[str], pool: list[Person], threshold: float) -> Person | None:
        best: list[tuple[float, Person]] = []
        for p in pool:
            want = sorted(words(p.name))
            if len(want) not in (len(got), len(got) - 1):
                continue
            scores = [max(difflib.SequenceMatcher(None, w, g).ratio() for g in got) for w in want]
            if min(scores) >= threshold:
                best.append((sum(scores) / len(scores), p))
        return self._one(best, 0.02)

    def _nearest(self, got: list[str], pool: list[Person]) -> Person | None:
        best: list[tuple[float, Person]] = []
        for p in pool:
            want = sorted(words(p.name))
            if abs(len(want) - len(got)) > 1:
                continue
            scores = self._score(want, got)
            if min(scores) >= 0.6 and sum(scores) / len(scores) >= 0.75:
                best.append((sum(scores) / len(scores), p))
        return self._one(best, 0.08)

    @staticmethod
    def _one(best: list[tuple[float, Person]], margin: float) -> Person | None:
        if not best:
            return None
        best.sort(key=lambda b: -b[0])
        if len(best) > 1 and best[1][0] >= best[0][0] - margin and best[1][1].key != best[0][1].key:
            return None
        return best[0][1]
