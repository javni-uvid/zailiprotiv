"""What a caption says, from the words OCR read in it (no OCR here: the repository's tests run this).

The broadcast's caption has two lines: the speaker's name ("Милена Јовановић"), and under it their list or office
("Србија побеђује", "министар финансија"). A list's name often holds its leader's name, so a name is only ever
looked for on the name line.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import difflib

from .names import Person, Roster, latin, person_key, words

Word = tuple[str, float]  # a word and how sure OCR was of it (0-100)

_REAL = re.compile(r"[^\W\d_]{3,}")  # a line with no word of three letters is noise
_NAME_WORD = re.compile(r"[^\W\d_]{2,}[.,]?")


@dataclass
class Caption:
    name_line: str = ""
    role_line: str = ""
    name_clean: bool = False  # 2-3 capitalised words, each read surely
    role_clean: bool = False


def _text(line: list[Word]) -> str:
    return " ".join(w for w, _ in line)


def _clean(line: list[Word], conf: float, names: bool) -> bool:
    if not line:
        return False
    ok = [w for w, c in line if _NAME_WORD.fullmatch(w) and c >= conf]
    junk = [w for w, c in line if not (_NAME_WORD.fullmatch(w) and c >= conf) and len(w) > 2]
    if junk:
        return False
    if names:
        return 2 <= len(ok) <= 3 and all(w[0].isupper() for w in ok)
    return len(ok) >= 1


def read(lines: list[list[Word]], conf: float) -> Caption:
    """Lines top to bottom. The caption is the last two lines with real words: name above, list or office below."""
    real = [ln for ln in lines if _REAL.search(_text(ln))]
    if not real:
        return Caption()
    if len(real) == 1:
        return Caption(name_line=_text(real[0]), name_clean=_clean(real[0], conf, True))
    name, role = real[-2], real[-1]
    return Caption(_text(name), _text(role), _clean(name, conf, True), _clean(role, conf, False))


_EDGE = "·•\"'“”„«».,;:!|~_*°()[]{}<>"


def tidy(text: str) -> str:
    """A line as read, for showing: Latin, each word as read, without the specks OCR leaves around it; a dash between
    words stays ("Ime Prezime - Lista"), bits with no letter or a single letter at either end of the line go."""
    parts = [w.strip(_EDGE) for w in latin(text).split()]
    parts = [w for w in parts if w]
    speck = lambda w: not any(ch.isalpha() for ch in w) or len(w) == 1  # "2", "c" before "Studentska lista"
    while parts and speck(parts[0]):
        parts.pop(0)
    while parts and speck(parts[-1]):
        parts.pop()
    return " ".join(parts)


def who(cap: Caption, roster: Roster, threshold: float) -> Person | None:
    """The speaker a caption names. On the list: that MP. Not on the list but cleanly read: the name as read (a
    minister or a guest, or an MP the list does not have yet). Otherwise nobody: a name half read is not shown."""
    if not cap.name_line:
        return None
    mp = roster.match(cap.name_line, threshold)
    if mp:
        return mp
    if cap.name_clean:
        # only the words of three letters or more: OCR's specks of the picture around the caption ("KE Mo Jugoslav
        # Gašić 2", 18 Nov 2026) are read too, unsurely, and a clean line lets them through
        given_surname = [w for w in tidy(cap.name_line).split() if all(_REAL.fullmatch(x) for x in w.split("-"))]
        name = " ".join(given_surname[-1:] + given_surname[:-1])  # "Surname Given", as the site lists names
        return Person(person_key(name), name)
    return None


def differs(cap: Caption, current: str, threshold: float) -> bool:
    """The caption names someone, unreadably perhaps, and it is not the current speaker: two or more words on the
    name line, none of them close to a word of the current speaker's name."""
    got = words(cap.name_line)
    if len(got) < 2 or not current:
        return False
    mine = words(current)
    return not any(difflib.SequenceMatcher(None, g, m).ratio() >= threshold for g in got for m in mine)
