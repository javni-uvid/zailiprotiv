"""A finished speech as a link of its own, /govor/<second> (25 Nov 2026, the maintainer): the moment it began, and nothing
else. No name (one found by voice may be mended later) and no place in a recording (it moves from YouTube to the
archive): both are looked up when the link is opened. The same rule is in mikrofon.js (`turnAt`), which the site's page
of the day uses too. Only the standard library."""
from __future__ import annotations

import re
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from . import config

FIRST = 1794870000  # the midnight of 17 Nov 2026, the first day kept
NEAR = 10  # seconds a beginning may have moved in a day written again (45 until 25 Nov 2026: four links led to another)


def moment(text: str, now: float | None = None) -> int | None:
    """The second an address names; None when it is not a number, or not of a day that can have been kept."""
    if not re.fullmatch(r"[0-9]{10}", text or ""):
        return None
    at = int(text)
    return at if FIRST <= at <= (time.time() if now is None else now) + 86400 else None


def turn_at(turns: list[dict], at: int) -> dict | None:
    """The turn a link means: the one beginning nearest within NEAR, else the one that holds that second; else none, as
    another speaker under a link would be a false statement about a person."""
    near = [d for d in turns if abs(int(d["od"]) - at) <= NEAR]
    if near:
        return min(near, key=lambda d: (abs(int(d["od"]) - at), d["od"]))
    return next((d for d in sorted(turns, key=lambda d: d["od"]) if d["od"] <= at <= d["do"]), None)


def elsewhere(at: int, waiting: dict | None, *, cyr: bool, tz: ZoneInfo) -> str:
    """The site's own page of that day, at the speech, when the site lists the day as one it has ("dani"); "" otherwise.
    The address is made of the listed day and of a number, never of what was asked for."""
    listed = waiting.get("dani") if isinstance(waiting, dict) else None
    mine = datetime.fromtimestamp(at, tz).date().isoformat()
    day = next((d for d in listed if d == mine), "") if isinstance(listed, list) else ""
    return f'{config.SITE}{"cir/" if cyr else ""}govornici/{day}#govor-{at:d}' if day else ""
