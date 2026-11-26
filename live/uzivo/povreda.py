"""A point of order live: the Rules' articles the speaker names (26 Nov 2026, the maintainer: "Trebamo promeniti i kad
detektujemo povredu poslovnika isto"; of the day pages' label, "1 u 10 je okej, mozemo i uzivo").

The site labels a turn of the notes by `notes_site.point_of_order` and the articles by `poslovnik.cited`, over the
notes' Cyrillic. Live there is only the automatic transcript, in Latin, so the same rules are written here in Latin
(the image has no `zailiprotiv`; a test holds the two to the same answers over the notes). Two things the transcript
needs that the notes do not: a number said in words ("član sto sedam"), and the window: the speaker's own words, cut
after the chair's giving the floor (`split`), whose numbers are taken out (the chair's "Ne može 15" is not the speaker's).
Measured on 24-25 Nov against the notes' labels: docs/decisions/live-page.md.
"""
from __future__ import annotations

import re

LAST = 298  # the Rules' last article (poslovnik.cited's `last`)
CITE_HEAD = 400  # characters of a point of order whose articles count (poslovnik.CITE_HEAD)

# poslovnik._CITE, _OF_RULES, _OTHER in Latin
_CITE = re.compile(r"\b(?:član\w*|čl\.)\s+(?:je\s+)?(\d{1,3})\b\.?(?:\s*(?:stav|st\.)\s*\d+\.?)?(?=(?P<after>[^.;:]{0,25}))", re.I)
_OF_RULES = re.compile(r"^\s*(?:,\s*)?Poslovnik", re.I)
_OTHER = re.compile(r"Ustav|[Zz]akon", re.I)
# notes_site._POINT_NOT in Latin: a point of order denied or in passing
NOT = re.compile(r"(?:nije|nisam|ako smatrate|jedino ako je)[^.?!]{0,40}?(?:povred|po Poslovniku)|pravo po Poslovniku", re.I)

_ONES = {"nula": 0, "jedan": 1, "jedna": 1, "jedno": 1, "dva": 2, "dve": 2, "tri": 3, "četiri": 4, "pet": 5, "šest": 6,
         "sedam": 7, "osam": 8, "devet": 9, "prvi": 1, "drugi": 2, "treći": 3, "četvrti": 4, "peti": 5, "šesti": 6,
         "sedmi": 7, "osmi": 8, "deveti": 9}
_TEENS = {"deset": 10, "jedanaest": 11, "dvanaest": 12, "trinaest": 13, "četrnaest": 14, "petnaest": 15, "šesnaest": 16,
          "sedamnaest": 17, "osamnaest": 18, "devetnaest": 19, "deseti": 10, "jedanaesti": 11, "dvanaesti": 12,
          "trinaesti": 13, "četrnaesti": 14, "petnaesti": 15, "šesnaesti": 16, "sedamnaesti": 17, "osamnaesti": 18,
          "devetnaesti": 19}
_TENS = {"dvadeset": 20, "trideset": 30, "četrdeset": 40, "pedeset": 50, "šezdeset": 60, "sedamdeset": 70,
         "osamdeset": 80, "devedeset": 90, "dvadeseti": 20, "trideseti": 30, "četrdeseti": 40, "pedeseti": 50,
         "šezdeseti": 60, "sedamdeseti": 70, "osamdeseti": 80, "devedeseti": 90}
_HUNDREDS = {"sto": 100, "stoti": 100, "dvesta": 200, "dvesto": 200, "dvestoti": 200}
_WORD = "|".join(sorted({*_ONES, *_TEENS, *_TENS, *_HUNDREDS}, key=len, reverse=True))
_SAID = re.compile(rf"\b(?:{_WORD})(?:\s+(?:i\s+)?(?:{_WORD}))*\b", re.I)


def _value(words: list[str]) -> int | None:
    """A number said in words, hundreds, tens, ones in that order ("sto sedam", "dvadeset i sedam"); None otherwise."""
    n, last = 0, 1000
    for w in words:
        for table, size in ((_HUNDREDS, 100), (_TENS, 10), (_TEENS, 10), (_ONES, 1)):
            if w in table:
                v = table[w]
                if size >= last or (n and v >= last):
                    return None
                n, last = n + v, size if table is not _TEENS else 1
                break
        else:
            return None
    return n or None


def digits(text: str) -> str:
    """The numbers said in words written in figures, after "član" only (an article is what is looked for)."""
    def put(m: re.Match) -> str:
        v = _value([w for w in m.group(0).lower().split() if w != "i"])
        return str(v) if v else m.group(0)
    return re.sub(r"(\b(?:član\w*|čl\.)\s+(?:je\s+)?)(" + _SAID.pattern + ")",
                  lambda m: m.group(1) + put(re.match(_SAID.pattern, m.group(2), re.I)), text, flags=re.I)


def cited(text: str, point: bool, last: int = LAST) -> list[tuple[int, int, int]]:
    """poslovnik.cited in Latin: [(article, start, end)] of the Rules' articles a speech invokes."""
    out = []
    for m in _CITE.finditer(text):
        n, after = int(m.group(1)), m.group("after") or ""
        if not 1 <= n <= last or _OTHER.search(after[:20]):
            continue
        if _OF_RULES.match(after) or (point and m.start() < CITE_HEAD):
            out.append((n, m.start(), m.end()))
    return out


# The chair giving the floor: what is said after the last of these before the turn is the speaker's. The caption comes
# seconds after the speaker begins, so their first words are often among the pieces with no caption, after the chair's.
FLOOR = re.compile(r"\bizvolite\b|\breč ima\b|\bima reč\b|\bdajem reč\b|\breč dajem\b", re.I)
BEFORE, AFTER = 45, 30  # seconds around the turn's beginning whose pieces count


def split(said: dict[str, str], start: float) -> tuple[str, str]:
    """(the chair's, the speaker's) of what was written down around a turn's beginning: the pieces from BEFORE seconds
    before it to AFTER seconds into it, cut after the chair's last words giving the floor before the turn began; with
    none heard, all of it is taken as the speaker's."""
    keys = sorted((k for k in said if k.lstrip("p").isdigit() and start - BEFORE <= int(k.lstrip("p")) <= start + AFTER),
                  key=lambda k: int(k.lstrip("p")))
    head = " ".join(said[k] for k in keys if int(k.lstrip("p")) <= start + 2)
    rest = " ".join(said[k] for k in keys if int(k.lstrip("p")) > start + 2)
    cuts = list(FLOOR.finditer(head))
    if cuts:
        return head[:cuts[-1].end()], (head[cuts[-1].end():] + " " + rest).strip()
    return "", (head + " " + rest).strip()


def opens_with_article(said: dict[str, str], start: float) -> bool:
    """The site's second sign of a point of order: the speaker names a Rules' article at once (notes_site.POINT_ARTICLE,
    the first 200 characters)."""
    return any(a < 200 for _, a, _ in cited(digits(split(said, start)[1]), True))


def articles(said: dict[str, str], start: float) -> list[int]:
    """The articles the speaker names at the opening of a point of order, by the site's rule, sorted. A number in the
    chair's words before the cut is not taken (19 Nov: the chair's "Ne može 15")."""
    chair, own = split(said, start)
    taken = {int(x) for x in re.findall(r"\b(\d{1,3})\b", digits("član " + chair))}
    return sorted({n for n, a, _ in cited(digits(own), True) if a < CITE_HEAD and n not in taken})


def denied(text: str, at: int) -> bool:
    """notes_site's test: the words up to 40 characters past the mark of a point of order deny it or say it in passing."""
    return bool(NOT.search(text[:at + 40]))


__all__ = ["articles", "cited", "denied", "digits", "opens_with_article", "split", "FLOOR", "NOT", "LAST"]
