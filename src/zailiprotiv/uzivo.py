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
