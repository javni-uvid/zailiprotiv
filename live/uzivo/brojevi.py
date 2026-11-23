"""The day in figures: light numbers of a sitting day, for the day's mail (23 Nov 2026, the maintainer: "neke druge
random zabavne statistike" in place of how many decisions and speakers).

Counted by the code, never by the model: how long the day was, how many words, how often courtesy was said and the
Rules named, the longest break, how long until the first warning. The same list of words every day, chosen for being
nobody's (courtesy and the Rules of Procedure), and no figure is of a person or a list. Words are counted in the
automatic transcript, which errs, so only when it covers the whole day.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

GAP = 20 * 60        # a silence of the transcript this long is a break of the sitting, or the transcript was off
EDGE = 10 * 60       # how near the day's first and last word the transcript must begin and end
FEW = 5              # a word said fewer times is no figure
PAGE = 1800          # the characters of a page of text, as publishers count it
MATCH = 90           # minutes
WORDS = {"hvala": r"hvala|zahvalj\w+|zahvalim\w*", "izvinite": r"izvin\w+|izvinj\w+", "molim": r"molim\w*", "poslovnik": r"poslovni[kc]\w*"}


def _clock(hhmm: str) -> int | None:
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", str(hhmm))
    return int(m[1]) * 60 + int(m[2]) if m else None


def span(flow: list[dict]) -> tuple[int, int] | None:
    """The day's first and last minute by the summary's steps; past midnight the last is after 24:00."""
    times = [c for c in (_clock(x.get("vreme", "")) for x in flow) if c is not None]
    if len(times) < 2:
        return None
    a, b = times[0], times[-1]
    b += 24 * 60 if b < a else 0
    return (a, b) if b - a >= 30 else None


def count(day: date, flow: list[dict], said: dict[str, str], steps: list[dict], tz: ZoneInfo) -> dict:
    """The day's figures: "traje" (minutes) always; the words' and the break's only from a whole transcript."""
    s = span(flow)
    if not s:
        return {}
    out: dict = {"traje": s[1] - s[0], "od": s[0]}
    rows = sorted((int(k.lstrip("p")), v) for k, v in said.items() if k.lstrip("p").isdigit())
    if not rows:
        return out
    midnight = datetime(day.year, day.month, day.day, tzinfo=tz).timestamp()
    if rows[0][0] > midnight + s[0] * 60 + EDGE or rows[-1][0] < midnight + s[1] * 60 - EDGE:
        return out  # begun late or ended early: part of the day
    gaps = [(b[0] - a[0], a[0]) for a, b in zip(rows, rows[1:]) if b[0] - a[0] >= GAP]
    pauses = [x["t"] for x in steps if x.get("vrsta") == "Pauza"]
    if any(not any(abs(p - at) <= 300 for p in pauses) for _, at in gaps):
        return out  # a silence nobody called a break: the transcript was off
    text = " ".join(v for _, v in rows)
    low = text.lower()
    out["reci"] = len(re.findall(r"\w+", low))
    out["strana"] = round(len(text) / PAGE)
    out["slusano"] = round((rows[-1][0] - rows[0][0] - sum(g for g, _ in gaps)) / 60)
    for k, pat in WORDS.items():
        out[k] = len(re.findall(rf"\b(?:{pat})\b", low))
    if gaps:
        longest, at = max(gaps)
        out["pauza"], out["pauza_od"] = round(longest / 60), datetime.fromtimestamp(at, tz).strftime("%H:%M")
    return out


def kept(base: Path, day: date, flow: list[dict], steps: list[dict], tz: ZoneInfo) -> dict:
    """The day's figures from what the service keeps; a day read from the recording, whose transcript is not here, has
    them in /data/brojevi/<day>.json."""
    def read(folder: str) -> dict:
        try:
            got = json.loads((base / folder / f"{day.isoformat()}.json").read_text(encoding="utf-8"))
            return got if isinstance(got, dict) else {}
        except (OSError, ValueError):
            return {}
    ready = {k: v for k, v in read("brojevi").items() if isinstance(v, (int, str))}
    return ready or count(day, flow, {str(k): str(v) for k, v in read("prepis").items()}, steps, tz)


def hours(m: int) -> str:
    return f"{m} min" if m < 60 else f"{m // 60} h" + (f" {m % 60} min" if m % 60 else "")


def _plural(n: int, one: str, few: str, many: str) -> str:
    return one if n % 10 == 1 and n % 100 != 11 else few if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14) else many


def tiles(n: dict, day: date, first_warning: str = "") -> list[tuple[str, str]]:
    """Up to four: how long and how many words, then two of the rest, others each day by the date alone (never by which
    is the more striking). `first_warning` is the first warning's "HH:MM"."""
    if not n.get("traje"):
        return []
    matches = round(n["traje"] / MATCH)
    out = [(hours(n["traje"]), "od prve do poslednje reči" + (
        f", kao {matches} {_plural(matches, 'fudbalska utakmica', 'fudbalske utakmice', 'fudbalskih utakmica')}" if matches >= 2 else ""))]
    if n.get("reci", 0) >= 5000:
        said, pages = f"{round(n['reci'], -3):,}".replace(",", "."), round(n["strana"], -1)
        out.append((said, f"reči izgovoreno, kao knjiga od {pages} strana"))
    rest: list[tuple[str, str]] = []
    if n.get("poslovnik", 0) >= FEW:
        every = round(n["slusano"] / n["poslovnik"])
        rest.append((f"{n['poslovnik']}×", "pomenut Poslovnik" + (f", jednom na oko {every} min" if every >= 2 else "")))
    at = _clock(first_warning)
    if at is not None:
        wait = at - n["od"] + (24 * 60 if at < n["od"] else 0)
        rest.append((hours(wait), f"do prve opomene, u {first_warning}")) if wait >= 10 else None
    if n.get("hvala", 0) >= FEW:
        rest.append((f"{n['hvala']}×", "rečeno „hvala“ ili „zahvaljujem“"))
    if n.get("pauza"):
        rest.append((hours(n["pauza"]), f"najduža pauza, od {n['pauza_od']}"))
    if n.get("izvinite", 0) >= FEW:
        rest.append((f"{n['izvinite']}×", "pomenuto izvinjenje"))
    if n.get("molim", 0) >= FEW:
        rest.append((f"{n['molim']}×", "rečeno „molim“"))
    if rest:
        i = day.toordinal() * 2 % len(rest)
        turned = rest[i:] + rest[:i]
        out += turned[:4 - len(out)]
    return out if len(out) >= 2 else []
