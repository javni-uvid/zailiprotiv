"""Who is speaking now, and today's turns, from one reading per frame. Only the standard library.

The same rule for every speaker: a turn starts with the first frame whose caption names them, lasts while frames go
on naming them (frames with no readable name in between do not end it for HOLD_SECONDS), and ends when another name
is read, when two frames in a row name someone else even if unreadably, when nothing is read for HOLD_SECONDS, or
when the broadcast stops. A name not on the site's list of MPs
(a minister, a guest) must be read in two frames in a row first: OCR noise can look like a name once.

Every day is kept in a file of its own (`dani/<date>.json` beside STATE_PATH): its turns, each with where it is in
the broadcast (the YouTube video and the numbers of its first and last segment), and when the service saw the
broadcast at all (`cover`), so a day's record says where it has gaps.

Between sittings the page lists the last sitting day. When the site has that day (or a later one) read afterwards from
the whole recording (`use_recording`, kept beside STATE_PATH as `snimak.json`), the page lists that instead, said so:
this service may have missed part of the day. Its own record at /dan/<date>.json stays as it was read.
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
        self.days = Path(path).parent / "dani" if path else None
        self.old = Path(path) if path else None  # until 17 Nov 2026 today's turns were kept here
        self.tz = ZoneInfo(tz or config.TZ)
        self.status = NO_STREAM
        self.last_frame = 0.0
        self.turns: list[dict] = []  # oldest first; the last may be open
        self.cover: list[list[float]] = []  # [from, to]: frames kept coming
        self.day = ""
        self.open = False
        self._pending = ""  # a name not on the list, read once
        self._others = 0  # frames in a row naming someone other than the current speaker
        self.recording_file = Path(path).with_name("snimak.json") if path else None
        self.recording: dict = {}  # the last sitting day read from the recording (the site's mikrofon-dan.json)
        self._migrate()
        self._load()
        try:
            if self.recording_file and self.recording_file.exists():
                self.recording = json.loads(self.recording_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass

    def use_recording(self, day: dict) -> None:
        """The site's last sitting day read from the recording; anything not shaped like one is ignored."""
        if not isinstance(day, dict) or not isinstance(day.get("dan"), str) or not isinstance(day.get("govori"), list):
            return
        with self._lock:
            self.recording = day
        if self.recording_file:
            self.recording_file.parent.mkdir(parents=True, exist_ok=True)
            self.recording_file.write_text(json.dumps(day, ensure_ascii=False), encoding="utf-8")

    # --- keeping today's turns across restarts ---
    def _day(self, ts: float) -> str:
        return datetime.fromtimestamp(ts, self.tz).date().isoformat()

    def _file(self, day: str) -> Path | None:
        return self.days / f"{day}.json" if self.days else None

    def _migrate(self) -> None:
        """Days recorded before the day files (until 17 Nov 2026) are only in the old state file: each gets its file,
        so the last sitting day stays on the page and is served at /dan/<date>.json."""
        if not self.days or not self.old or not self.old.exists():
            return
        try:
            turns = json.loads(self.old.read_text(encoding="utf-8")).get("turns", [])
        except (OSError, ValueError):
            return
        by_day: dict[str, list[dict]] = {}
        for t in turns:
            by_day.setdefault(self._day(t["start"]), []).append(t)
        today = self._day(time.time())
        for day, ts in by_day.items():
            f = self._file(day)
            if day < today and f and not f.exists():
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_text(json.dumps({"day": day, "turns": ts, "cover": []}, ensure_ascii=False), encoding="utf-8")

    def _load(self, day: str | None = None) -> None:
        self.day = day or self._day(time.time())
        self.turns, self.cover, self.open = [], [], False
        f = self._file(self.day)
        try:
            if f and f.exists():
                kept = json.loads(f.read_text(encoding="utf-8"))
                self.turns, self.cover = kept.get("turns", []), kept.get("cover", [])
            elif self.old and self.old.exists():
                turns = json.loads(self.old.read_text(encoding="utf-8")).get("turns", [])
                self.turns = [t for t in turns if self._day(t["start"]) == self.day]
        except (OSError, ValueError):
            pass

    def _save(self) -> None:
        f = self._file(self.day)
        if not f:
            return
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_suffix(".tmp")
        tmp.write_text(json.dumps({"day": self.day, "turns": self.turns, "cover": self.cover}, ensure_ascii=False),
                       encoding="utf-8")
        tmp.replace(f)

    # --- readings ---
    def _close(self) -> None:
        if self.open:
            self.open = False
            self._save()

    def current(self) -> str:
        with self._lock:
            return self.turns[-1]["name"] if self.open and self.turns else ""

    def observe(self, person: Person | None, role: str = "", now: float | None = None, other: bool = False,
                at: dict | None = None) -> None:
        """One frame read: who its caption names (or None), the line under the name if read cleanly, whether the
        caption names someone else than the current speaker without saying clearly whom (`caption.differs`), and
        where the frame is in the broadcast (`at`: video, sq, seg)."""
        now = time.time() if now is None else now
        at = at or {}
        with self._lock:
            if self._day(now) != self.day:
                self._close()
                self._load(self._day(now))  # a new day, a new file
            if self.cover and now - self.cover[-1][1] <= config.STALE_SECONDS:
                self.cover[-1][1] = now
            else:
                self.cover.append([now, now])
            self.last_frame = now
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
                    if at.get("sq") is not None and cur.get("video") == at.get("video"):
                        cur["sq_seen"] = at["sq"]
                else:
                    self._close()
                    if cur and cur["key"] == person.key and now - cur["seen"] <= config.MERGE_SECONDS:
                        cur["seen"], cur["n"] = now, cur["n"] + 1  # the same speaker after a short break
                        if at.get("sq") is not None and cur.get("video") == at.get("video"):
                            cur["sq_seen"] = at["sq"]
                    else:
                        self.turns.append({"key": person.key, "name": person.name, "slug": person.slug,
                                           "group": person.group, "role": role, "start": now, "seen": now, "n": 1,
                                           "video": at.get("video", ""), "sq_start": at.get("sq"),
                                           "sq_seen": at.get("sq"), "seg": at.get("seg")})
                    self.open = True
                    self._save()
                self.status = SPEAKING
            elif self.open and (self._others >= 2 or now - cur["seen"] > config.HOLD_SECONDS):
                self._close()
                self.status = UNKNOWN
            elif not self.open:
                self.status = UNKNOWN
            self._save()

    def tick(self, now: float | None = None) -> None:
        """Called each second, frame or not: a broadcast that stopped ends the turn."""
        now = time.time() if now is None else now
        with self._lock:
            if self.status != NO_STREAM and now - self.last_frame > config.STALE_SECONDS:
                self._close()
                self.status = NO_STREAM

    @staticmethod
    def _out(t: dict) -> dict:
        rec = None
        if t.get("video") and t.get("sq_start") is not None and t.get("seg"):
            rec = int(max(0, t["sq_start"] - config.RECORDING_LEAD) * t["seg"])
        return {"ime": t["name"], "adresa": t["slug"], "grupa": t["group"], "uloga": t["role"],
                "od": int(t["start"]), "do": int(t["seen"]), "sekundi": int(t["seen"] - t["start"]),
                "video": t.get("video") or "", "snimak": rec}

    def _last_day(self) -> tuple[str, list[dict]]:
        """The latest earlier day with turns: its list stays on the page until someone is read at the next sitting."""
        if not self.days or not self.days.exists():
            return "", []
        for f in sorted(self.days.glob("*.json"), reverse=True):
            if f.stem >= self.day:
                continue
            try:
                turns = [t for t in json.loads(f.read_text(encoding="utf-8")).get("turns", []) if t["n"] >= 2]
            except (OSError, ValueError, KeyError):
                continue
            if turns:
                return f.stem, turns
        return "", []

    @staticmethod
    def _recorded(t: dict) -> dict:
        return {"ime": t["ime"], "adresa": t.get("adresa", ""), "grupa": t.get("grupa", ""), "uloga": t.get("uloga", ""),
                "od": int(t["od"]), "do": int(t["do"]), "sekundi": int(t["do"] - t["od"]),
                "video": t.get("video") or "", "snimak": t.get("snimak")}

    def snapshot(self, now: float | None = None) -> dict:
        today = self._day(time.time() if now is None else now)
        with self._lock:
            current = self._out(self.turns[-1]) if self.open and self.turns else None
            # A turn read in a single frame is shown while it lasts, and left out of the day's list after.
            done = [self._out(t) for t in self.turns if t["n"] >= 2 and not (self.open and t is self.turns[-1])]
            day = self.day  # the day of the last frame: past midnight with no frame yet, an earlier one
            recorded = False
            if not done and not current:
                day, turns = self._last_day()
                day, done = (day, [self._out(t) for t in turns]) if turns else (self.day, [])
                rec = self.recording
                if rec and rec["dan"] < today and (not done or rec["dan"] >= day):
                    day, recorded = rec["dan"], True
                    done = [self._recorded(t) for t in rec["govori"] if t.get("okvira", 0) >= 2]
            return {"stanje": self.status, "provereno": int(self.last_frame), "sada": current,
                    "dan": day, "ranije": day != today, "snimak": recorded, "danas": done[::-1]}

    def record(self, day: str) -> dict | None:
        """A day's record, as published at /dan/<date>.json: every turn (with how many frames named the speaker,
        so a reader can leave out one-frame readings), where each is in the broadcast, and when the broadcast was
        seen at all."""
        with self._lock:
            if day == self.day:
                turns, cover = list(self.turns), list(self.cover)
            else:
                f = self._file(day)
                if not f or not f.exists():
                    return None
                kept = json.loads(f.read_text(encoding="utf-8"))
                turns, cover = kept.get("turns", []), kept.get("cover", [])
        return {
            "dan": day,
            "napomena": "Pročitano automatski iz potpisa u prenosu Skupštine; može da sadrži greške. Van 'pokriveno' "
                        "servis prenos nije video.",
            "pokriveno": [{"od": int(a), "do": int(b)} for a, b in cover],
            "govori": [{"ime": t["name"], "adresa": t["slug"], "grupa": t["group"], "uloga": t["role"],
                        "od": int(t["start"]), "do": int(t["seen"]), "okvira": t["n"], "video": t.get("video", ""),
                        "sq_od": t.get("sq_start"), "sq_do": t.get("sq_seen"), "segment": t.get("seg")}
                       for t in turns],
        }

    def days_kept(self) -> list[str]:
        if not self.days or not self.days.exists():
            return [self.day] if self.turns or self.cover else []
        return sorted({p.stem for p in self.days.glob("*.json")} | ({self.day} if self.turns or self.cover else set()))
