"""The record of who spoke when, kept by the live page (live/, mikrofon.zailiprotiv.rs), taken into the data.

The live page reads the caption under the speaker in the Assembly's broadcast and keeps a record per day: each turn,
when it began and ended, where it is in the broadcast. `pull` copies the records into `data/<N>/uzivo/<date>.json`.
The service runs on the maintainer's computer, so it may be off: a run that cannot reach it changes nothing.
"""
from __future__ import annotations

import datetime as dt
import json
import urllib.request
from pathlib import Path

from zailiprotiv import skupstina
from zailiprotiv.config import CONVOCATIONS, USER_AGENT


def convocation(day: str) -> str | None:
    """The convocation a day belongs to, by the convocations' own dates."""
    found = [n for n, conf in CONVOCATIONS.items() if skupstina.within(day, conf)]
    return max(found, key=int) if found else None


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def pull(root: Path, base: str, today: str | None = None, get=_get) -> list[str]:
    """Copy the live page's day records not kept yet, and those of today and yesterday (still growing or just
    finished), into data/<N>/uzivo/. Returns the days written."""
    base = base.rstrip("/") + "/"
    today = today or dt.date.today().isoformat()
    recent = {today, (dt.date.fromisoformat(today) - dt.timedelta(days=1)).isoformat()}
    written = []
    for day in get(base + "dani.json").get("dani", []):
        conv = convocation(day)
        if not conv:
            continue
        path = root / conv / "uzivo" / f"{day}.json"
        if path.exists() and day not in recent:
            continue
        text = json.dumps(get(f"{base}dan/{day}.json"), ensure_ascii=False, indent=1) + "\n"
        if path.exists() and path.read_text(encoding="utf-8") == text:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        written.append(day)
    return written


# --- the notes' speeches matched to the record ---------------------------------------------------------------------

def _key(name: str) -> str:
    """A name in either script, any order, without marks → its words, plain and sorted."""
    import re
    import unicodedata
    from zailiprotiv.translit import latin
    text = latin(name).lower().replace("đ", "dj").replace("-", " ")
    text = "".join(ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch))
    return " ".join(sorted(w for w in re.split(r"[^a-z]+", text) if len(w) >= 2))


LEAD = 1  # segments before the first frame that named the speaker: the caption comes up as they begin


def minutes(notes: dict, records: dict[str, dict]) -> dict[str, dict]:
    """Where each speech of a sitting's notes begins in the broadcast, from the live page's record of its day:
    {speech key: {"video", "t" (seconds into the video), "at" (time of day, unix)}}.

    The same rule for every speaker. A day's speeches, the chair's left out and one speaker's in a row taken as one,
    are lined up with the day's turns (those named in two frames or more, the same way taken as one) by the order of
    the speakers' names (difflib's matching blocks: the longest runs in the same order first); a speech gets the
    place of the turn it lines up with, and only the first of a speaker's speeches in a row gets one (the rest are
    within the turn). Where the record has a gap, or the order disagrees, a speech gets nothing rather than a guess."""
    import difflib
    out: dict[str, dict] = {}
    by_day: dict[int, list[str]] = {}
    for k in sorted(notes.get("speeches", {})):
        by_day.setdefault(notes["speeches"][k]["day"], []).append(k)
    dates = {d["day"]: d.get("listed_date") for d in notes.get("days", [])}
    for day, keys in by_day.items():
        rec = records.get(dates.get(day) or "")
        if not rec:
            continue
        said: list[tuple[str, str]] = []  # (name key, first speech key) for each run of one speaker
        for k in keys:
            s = notes["speeches"][k]
            if s.get("chair"):
                continue
            nk = _key(s["speaker"])
            if not said or said[-1][0] != nk:
                said.append((nk, k))
        turns: list[tuple[str, dict]] = []
        for t in rec.get("govori", []):
            if t.get("okvira", 0) < 2 or t.get("sq_od") is None or not t.get("video"):
                continue
            tk = _key(t["ime"])
            if not turns or turns[-1][0] != tk:
                turns.append((tk, t))
        match = difflib.SequenceMatcher(None, [a for a, _ in said], [b for b, _ in turns], autojunk=False)
        for block in match.get_matching_blocks():
            for i in range(block.size):
                t = turns[block.b + i][1]
                out[said[block.a + i][1]] = {"video": t["video"], "at": t["od"],
                                             "t": max(0, int((t["sq_od"] - LEAD) * (t.get("segment") or 5)))}
    return out


def load(conv_dir: Path) -> dict[str, dict]:
    """A convocation's day records: {date: record}."""
    folder = conv_dir / "uzivo"
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(folder.glob("*.json"))} if folder.is_dir() else {}
