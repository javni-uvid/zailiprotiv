"""What a caption says, from the words OCR read in it (no OCR here: the repository's tests run this).

The broadcast's caption has two lines: the speaker's name ("Милена Јовановић"), and under it their list or office
("Србија побеђује", "министар финансија"). A list's name often holds its leader's name, so a name is only ever
looked for on the name line.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import difflib

from .names import Person, Roster, latin, normalize, person_key, words

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
    if mp and not cap.role_line and any(set(words(mp.name)) <= set(words(g)) for g in roster.groups):
        return None  # one line, and the name is in a list's name ("Aleksandar Vučić - Srbija …"): the list, not a speaker
    if mp:
        return mp
    if cap.name_clean:
        # only the words of three letters or more: OCR's specks of the picture around the caption ("KE Mo Jugoslav
        # Gašić 2", 18 Nov 2026) are read too, unsurely, and a clean line lets them through
        given_surname = [w for w in tidy(cap.name_line).split() if all(_REAL.fullmatch(x) for x in w.split("-"))]
        name = " ".join(given_surname[-1:] + given_surname[:-1])  # "Surname Given", as the site lists names
        return Person(person_key(name), name)
    return None


def sure(cap: Caption, roster: Roster, threshold: float) -> Person | None:
    """The sitting MP a caption names, only when the line under the name is their own list: two lines read apart that
    agree, so noise read as a name is none."""
    mp = roster.match(cap.name_line, threshold) if cap.name_line and cap.role_line else None
    if not mp or not mp.group or (roster.current and mp.slug not in roster.current):
        return None
    line = normalize(tidy(cap.role_line))
    like = {g: difflib.SequenceMatcher(None, line, normalize(g)).ratio() for g in roster.groups}
    best = max(like, key=like.get, default="")
    return mp if best == mp.group and like[best] >= 0.65 else None


def _found(want: list[str], got: list[str], threshold: float) -> float:
    """The share of the words wanted that are on the line, each read closely enough."""
    if not want or not got:
        return 0.0
    return sum(max(difflib.SequenceMatcher(None, w, g).ratio() for g in got) >= threshold for w in want) / len(want)


def role(line: str, person: Person | None, roster: Roster, threshold: float) -> str:
    """The line under the name, as read; when it is close to the speaker's list on the site's list of MPs, or to
    any list there, that list's name as the site writes it: OCR drops a word and reads specks of the picture
    beside it ("RA Aleksandar Vučić Srbija" for "Aleksandar Vučić - Srbija pobeđuje", 18 Nov 2026)."""
    text = tidy(line)
    got = words(text)
    if not got:
        return text
    lists = ([person.group] if person and person.group else []) + roster.groups
    for name in lists:
        want = words(name)
        if _found(want, got, threshold) >= 0.6 and _found(got, want, threshold) >= 0.6:
            return name
    return text


def differs(cap: Caption, current: str, threshold: float) -> bool:
    """The caption names someone, unreadably perhaps, and it is not the current speaker: two or more words on the
    name line, none of them close to a word of the current speaker's name."""
    got = words(cap.name_line)
    if len(got) < 2 or not current:
        return False
    mine = words(current)
    return not any(difflib.SequenceMatcher(None, g, m).ratio() >= threshold for g in got for m in mine)
