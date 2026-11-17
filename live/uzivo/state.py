"""Who is speaking now, and today's turns, from one reading per frame. Only the standard library.

The same rule for every speaker: a turn starts with the first frame whose caption names them, lasts while frames go
on naming them (frames with no readable name in between do not end it for HOLD_SECONDS), and ends when another name
is read, when two frames in a row name someone else even if unreadably, when nothing is read for HOLD_SECONDS, or
when the broadcast stops. A name not on the site's list of MPs
(a minister, a guest) must be read in two frames in a row first: OCR noise can look like a name once.
"""
from __future__ import annotations

import json
import threading
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from . import config
from .names import Person

SPEAKING, UNKNOWN, NO_STREAM = "govori", "nepoznato", "nema_prenosa"


class Tracker:
    def __init__(self, path: str | None = None, tz: str | None = None) -> None:
        self._lock = threading.Lock()
        self.path = Path(path) if path else None
        self.tz = ZoneInfo(tz or config.TZ)
        self.status = NO_STREAM
        self.last_frame = 0.0
        self.turns: list[dict] = []  # oldest first; the last may be open
        self.open = False
        self._pending = ""  # a name not on the list, read once
        self._others = 0  # frames in a row naming someone other than the current speaker
        self._load()

    # --- keeping today's turns across restarts ---
    def _day(self, ts: float) -> str:
        return datetime.fromtimestamp(ts, self.tz).date().isoformat()

    def _load(self) -> None:
        if not self.path or not self.path.exists():
            return
        try:
            turns = json.loads(self.path.read_text(encoding="utf-8")).get("turns", [])
        except (OSError, ValueError):
            return
        today = self._day(time.time())
        self.turns = [t for t in turns if self._day(t["start"]) == today]

    def _save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"turns": self.turns}, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)

    # --- readings ---
    def _close(self) -> None:
        if self.open:
            self.open = False
            self._save()

    def current(self) -> str:
        with self._lock:
            return self.turns[-1]["name"] if self.open and self.turns else ""

    def observe(self, person: Person | None, role: str = "", now: float | None = None, other: bool = False) -> None:
        """One frame read: who its caption names (or None), the line under the name if read cleanly, and whether
        the caption names someone else than the current speaker without saying clearly whom (`caption.differs`)."""
        now = time.time() if now is None else now
        with self._lock:
            self.last_frame = now
            if self.turns and self._day(self.turns[0]["start"]) != self._day(now):
                self.turns, self.open = [t for t in self.turns if self._day(t["start"]) == self._day(now)], False
            if self.status == NO_STREAM:
                self.status = UNKNOWN
            cur = self.turns[-1] if self.turns else None
            if person and not person.slug and not (self.open and cur["key"] == person.key):
                if self._pending != person.key:
                    self._pending, person = person.key, None  # wait for a second frame
            self._others = self._others + 1 if (other and not person) else 0
            if person:
                self._pending = ""
                if self.open and cur["key"] == person.key:
                    cur["seen"], cur["n"] = now, cur["n"] + 1
                    cur["role"] = role or cur["role"]
                else:
                    self._close()
                    if cur and cur["key"] == person.key and now - cur["seen"] <= config.MERGE_SECONDS:
                        cur["seen"], cur["n"] = now, cur["n"] + 1  # the same speaker after a short break
                    else:
                        self.turns.append({"key": person.key, "name": person.name, "slug": person.slug,
                                           "group": person.group, "role": role, "start": now, "seen": now, "n": 1})
                    self.open = True
                    self._save()
                self.status = SPEAKING
            elif self.open and (self._others >= 2 or now - cur["seen"] > config.HOLD_SECONDS):
                self._close()
                self.status = UNKNOWN
            elif not self.open:
                self.status = UNKNOWN

    def tick(self, now: float | None = None) -> None:
        """Called each second, frame or not: a broadcast that stopped ends the turn."""
        now = time.time() if now is None else now
        with self._lock:
            if self.status != NO_STREAM and now - self.last_frame > config.STALE_SECONDS:
                self._close()
                self.status = NO_STREAM

    def snapshot(self) -> dict:
        with self._lock:
            def out(t: dict) -> dict:
                return {"ime": t["name"], "adresa": t["slug"], "grupa": t["group"], "uloga": t["role"],
                        "od": int(t["start"]), "do": int(t["seen"]), "sekundi": int(t["seen"] - t["start"])}
            current = out(self.turns[-1]) if self.open and self.turns else None
            # A turn read in a single frame is shown while it lasts, and left out of the day's list after.
            done = [out(t) for t in self.turns if t["n"] >= 2 and not (self.open and t is self.turns[-1])]
            return {"stanje": self.status, "provereno": int(self.last_frame), "sada": current,
                    "danas": done[::-1]}
