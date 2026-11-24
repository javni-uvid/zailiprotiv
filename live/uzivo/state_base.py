"""What the tracker's parts (state.py and state_*.py) share: the states, the rule for a turn counted, the
transcript's margins, and writing a file whole."""
from __future__ import annotations

import re

import json
from pathlib import Path


def write_text(f: Path, text: str) -> None:
    """A file written whole or not at all: beside it first, then put in its place (a crash mid-write used to
    leave half a file, read back as nothing, and the next write kept only what came after)."""
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(f)


def _write(f: Path, data) -> None:
    """The same for data kept as JSON. Every file the service keeps is written by one of the two."""
    write_text(f, json.dumps(data, ensure_ascii=False))


SPEAKING, UNKNOWN, NO_STREAM = "govori", "nepoznato", "nema_prenosa"
# words only the chair says: with one of them between, the same speaker named again begins anew (24 Nov 2026: 104 s of the
# chair's before a reply were about to be the next speaker's)
CHAIRS = re.compile(r"\breč ima|ima(te)? reč|dajem reč|po kom osnovu|\brepli[kc]|povred\w* poslovnik|izvolite|da li želite|"
                    r"poslaničk\w* grup\w* žel|\bmolim vas|\bmolim (da|bez)|\bupozor|izričem|prijavite se|zahvaljujem|hvala na|idemo dalje", re.I)
REJOIN = 200  # seconds: the same speaker named again this soon, with speech going on between and no floor given to another
REJOIN_WORDS = 1.2  # words a second of it, for speech to have gone on (a speaker's pace is some two)
HEARD_SHORT = 12  # seconds: a turn found by the chair's words alone and as short as this is no turn (24 Nov 2026: 2 s, 8 s)
SURE_FRAMES = 4  # a turn with no line under the name read in any frame is kept only from this many frames on


def counted(t: dict) -> bool:
    """Whether a turn goes into the day's list: read in two frames or more, and either with the line under the name
    (the list or office, which every real caption has) read at least once, or long enough to be no chance reading.
    19 Nov 2026: two turns of two frames each, no second line, named an MP who had not spoken; something else on the
    screen had been read as a name. The same rule for every name."""
    if t.get("izvor") == "prepis" and t.get("seen", 0) - t.get("start", 0) < HEARD_SHORT:
        return False  # only the chair's words, and nobody heard after them: the floor was taken back or passed on at once
    return t.get("n", 0) >= 2 and bool(t.get("role") or t.get("n", 0) >= SURE_FRAMES)


SAID_LEAD = 6  # seconds: a turn's sound begins this long before its first frame (the caption comes up late)
SAID_TAIL = 420  # characters of the newest transcript shown with the speaker
