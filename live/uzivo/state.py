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
from .names import Person, Roster
from .state_base import CLOCK_JOIN, LONGEST_CLOCK, SURE_FRAMES, NO_STREAM, SPEAKING, UNKNOWN, _write, counted, CHAIRS, REJOIN, REJOIN_WORDS
from .state_chronicle import Chronicle
from .state_said import Said
from .state_view import View


def _kept(folder: Path | None, day: str) -> Path | None:
    """The file of a day a request named: one of the folder's own files, so no path is built from what was asked
    (the address is checked to be a date before this; here that no longer matters)."""
    if not folder or not folder.is_dir():
        return None
    return next((p for p in folder.glob("*.json") if p.stem == day), None)


class Tracker(Said, Chronicle, View):
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
        self._pending = ""  # a name not on the list, or with nothing under it, read once
        self._held: dict = {}  # when and where that one frame was
        self.presiding: dict = {}  # who presides, by the voice (glas.py): name, address, from, to
        self.captions: list[dict] = []  # the line under the picture, its last lines (prepis.Captions); not kept
        self._forms: tuple = (None, {})  # the sitting MPs' names in their cases, for the transcript's corrections
        self._others = 0  # frames in a row naming someone other than the current speaker
        self.recording_file = Path(path).with_name("snimak.json") if path else None
        self.recording: dict = {}  # the last sitting day read from the recording (the site's mikrofon-dan.json)
        self.waiting_file = Path(path).with_name("cekanje.json") if path else None
        self.waiting: dict = {}  # "Dok čekate": the site's quiz and facts (mikrofon-cekanje.json)
        self.facts_file = Path(path).with_name("poslanici.json") if path else None
        self.facts: dict = {}  # the speaker's votes and facts from their page (mikrofon-poslanici.json)
        self.roster: Roster | None = None  # the site's list of MPs, to name turns read before it knew them
        self.events: list[dict] = []  # the day's steps, a line each (hronika.py)
        self.item: dict = {}  # the agenda item the chair last moved to, as heard: {"n", "t"}
        self.lines: tuple[str, list] = ("", [])  # the line on each speech of the day (rezimei.py): (day, as kept)
        self.summary: tuple[str, dict] = ("", {})  # the model's summaries of the day (sudija.py): (day, as kept)
        try:
            kept_item = Path(path).parent / "tacka.json" if path else None
            if kept_item and kept_item.exists():
                self.item = json.loads(kept_item.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.item = {}
        self.said: dict[str, str] = {}  # the day's automatic transcript in pieces, by each piece's first second (prepis.py)
        self._said_other: tuple[str, dict] = ("", {})  # an earlier day's, read when the page shows that day
        self._snap: tuple[float, dict] | None = None  # the last snapshot and when: every visitor asks every few seconds
        self._snapping = threading.Lock()  # one thread computes a snapshot at a time
        self._frames = 0  # frames read so far: a snapshot begun before the latest is not kept
        self._memo: dict = {}  # names and lines already matched to the list, by the list they were matched to
        self.place: dict = {}  # the newest frame's place in the broadcast: {"t", "video", "sq", "seg"}
        self._resumed = 0.0  # when this run took up the last one's open turn (a restart; RESUME_SECONDS)
        self._migrate()
        self._load()
        self._resume()
        for f, attr in ((self.recording_file, "recording"), (self.waiting_file, "waiting"), (self.facts_file, "facts")):
            try:
                if f and f.exists():
                    setattr(self, attr, json.loads(f.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                pass

    def use_waiting(self, w: dict) -> None:
        """The site's "Dok čekate"; anything not shaped like it is ignored."""
        if not isinstance(w, dict) or not isinstance(w.get("kviz"), list) or not isinstance(w.get("cinjenice"), list):
            return
        self.waiting = w
        self._snap = None
        if self.waiting_file:
            try:
                _write(self.waiting_file, w)
            except OSError:
                pass

    def use_summary(self, day: str, kept: dict) -> None:
        """The model's summaries of a day (sudija.py): its stretches and the day, as kept in /data/sazetak/."""
        with self._lock:
            self.summary = (day, kept)
            self._snap = None

    def use_lines(self, day: str, kept: list) -> None:
        """The line on each speech of a day (rezimei.py)."""
        with self._lock:
            self.lines = (day, kept)
            self._snap = None

    def summary_of(self, day: str) -> dict:
        """The model's summaries of a day: today's as the model keeps them, an earlier day's from its file."""
        if self.summary[0] == day:
            return self.summary[1]
        f = _kept(Path(config.STATE_PATH).parent / "sazetak" if config.STATE_PATH else None, day)
        try:
            return json.loads(f.read_text(encoding="utf-8")) if f else {}
        except (OSError, ValueError):
            return {}

    def use_facts(self, facts: dict) -> None:
        """The site's facts per MP's page (mikrofon-poslanici.json): {slug: {"za", "protiv", "uzdrzan", "f", "novi"}}."""
        if isinstance(facts, dict):
            with self._lock:
                self.facts = facts
                self._snap = None
            if self.facts_file:
                try:
                    _write(self.facts_file, facts)
                except OSError:
                    pass

    def use_recording(self, day: dict) -> None:
        """The site's last sitting day read from the recording; anything not shaped like one is ignored."""
        if not isinstance(day, dict) or not isinstance(day.get("dan"), str) or not isinstance(day.get("govori"), list):
            return
        with self._lock:
            self.recording = day
            self._snap = None
        if self.recording_file:
            try:
                _write(self.recording_file, day)
            except OSError:
                pass

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
                _write(f, {"day": day, "turns": ts, "cover": []})

    def _load(self, day: str | None = None) -> None:
        self.day = day or self._day(time.time())
        self.turns, self.cover, self.open = [], [], False
        self.said = self._said_load(self.day)
        self.events = self._events_load(self.day)
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

    def _resume(self, now: float | None = None) -> None:
        """After a restart (a new image put live, 20 Nov 2026): when today's file says a broadcast was on and its last
        frame is under RESUME_SECONDS old, the page goes on showing it (the speaker still on, if one was) instead of
        "no sitting" until the stream is found again, and the waits for a frame (HOLD_SECONDS, STALE_SECONDS) count
        from the restart. The same speaker read again is the same turn, as after any short gap (MERGE_SECONDS)."""
        now = time.time() if now is None else now
        f = self._file(self.day)
        try:
            kept = json.loads(f.read_text(encoding="utf-8")) if f and f.exists() else {}
        except (OSError, ValueError):
            return
        last = float(kept.get("last_frame") or 0)
        if kept.get("status") not in (SPEAKING, UNKNOWN) or not 0 <= now - last <= config.RESUME_SECONDS:
            return
        self.status, self.last_frame, self._resumed = kept["status"], last, now
        self.open = bool(kept.get("open")) and bool(self.turns)
        if self.status == SPEAKING and not self.open:
            self.status = UNKNOWN

    def _save(self) -> None:
        f = self._file(self.day)
        if not f:
            return
        _write(f, {"day": self.day, "turns": self.turns, "cover": self.cover, "open": self.open,
                   "status": self.status, "last_frame": self.last_frame})

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
        self._snap = None
        self._frames += 1
        with self._lock:
            if self._day(now) != self.day:
                self._close()
                self._load(self._day(now))  # a new day, a new file
            if self.cover and now - self.cover[-1][1] <= config.STALE_SECONDS:
                self.cover[-1][1] = now
            else:
                self.cover.append([now, now])
            self.last_frame = now
            if at.get("video") and at.get("sq") is not None and at.get("seg"):
                self.place = {"t": now, "video": at["video"], "sq": at["sq"], "seg": at["seg"]}
            if self.status == NO_STREAM:
                self.status = UNKNOWN
            cur = self.turns[-1] if self.turns else None
            first = None  # the first of two frames that named this person, when the name had to be read twice
            back = cur and person and cur["key"] == person.key and now - cur["seen"] <= config.MERGE_SECONDS
            if person and not (self.open and cur["key"] == person.key) and not back and (not person.slug or not role):
                # A name not on the list, or with no line read under it (every real caption has one), is taken on
                # its second frame in a row: during a break something on the screen was read as an MP's name, one
                # frame at a time, and each time the page showed that MP as speaking (19 Nov 2026).
                held = self._held if isinstance(self._held, dict) else {}
                if self._pending == person.key and now - held.get("t", 0) <= config.HOLD_SECONDS:
                    first = held
                else:
                    self._pending, self._held, person = person.key, {"t": now, "at": dict(at)}, None
            self._others = self._others + 1 if (other and not person) else 0
            if person:
                self._pending = ""
                if self.open and cur["key"] == person.key:
                    cur["seen"], cur["n"] = now, cur["n"] + 1
                    cur["role"] = role or cur["role"]
                    cur.pop("izvor", None)  # found before the caption came up: the caption now says it
                    cur.pop("po_glasu", None)
                    if at.get("sq") is not None and cur.get("video") == at.get("video"):
                        cur["sq_seen"] = at["sq"]
                else:
                    self._close()
                    prev = self.turns[-2] if len(self.turns) > 1 else None
                    if (cur and cur["key"] != person.key and cur["n"] == 1 and prev and prev["key"] == person.key
                            and now - prev["seen"] <= config.MERGE_SECONDS):
                        # one frame of another name inside a speech (a caption misread, 18 Nov 2026): not a turn
                        self.turns.pop()
                        cur = prev
                    if cur and cur["key"] == person.key and now - cur["seen"] <= config.MERGE_SECONDS:
                        cur["seen"], cur["n"] = now, cur["n"] + 1  # the same speaker after a short break
                        if at.get("sq") is not None and cur.get("video") == at.get("video"):
                            cur["sq_seen"] = at["sq"]
                    else:
                        began, at0 = (first["t"], first["at"]) if first else (now, at)  # from the first frame that named them
                        self.turns.append({"key": person.key, "name": person.name, "slug": person.slug,
                                           "group": person.group, "role": role, "start": began, "seen": now,
                                           "n": 2 if first else 1,
                                           "video": at.get("video", ""), "sq_start": at0.get("sq"),
                                           "sq_seen": at.get("sq"), "seg": at.get("seg")})
                    self.open = True
                    self._save()
                self.status = SPEAKING
            elif self.open and cur.get("izvor"):
                # found without a caption (the chair's words, the voice): no caption is what it lives on; one found by
                # the chair's words alone goes on while nothing else is heard, HEARD_LONGEST at the most
                if not cur.get("po_glasu"):
                    cur["seen"] = now
                if now - cur["start"] > config.HEARD_LONGEST:
                    self._close()
                    self.status = UNKNOWN
            elif self.open and (self._others >= 2 or now - max(cur["seen"], self._resumed) > config.HOLD_SECONDS):
                self._close()
                self.status = UNKNOWN
            elif not self.open:
                self.status = UNKNOWN
            self._save()

    # --- who speaks without a caption (22 Nov 2026, the maintainer) ---
    def turns_now(self) -> list[dict]:
        with self._lock:
            return [dict(t) for t in self.turns]

    def open_turn(self) -> dict | None:
        with self._lock:
            return dict(self.turns[-1]) if self.open and self.turns else None

    def presides(self, person: Person, start: float, seen: float) -> None:
        """The chair's voice heard: a presiding officer's (config.VOICE_SKIP), from `start` to `seen`."""
        with self._lock:
            p = self.presiding
            if p.get("adresa") == person.slug and start - p.get("do", 0) < 1800:
                p["do"] = max(p["do"], seen)
            else:
                self.presiding = {"ime": person.name, "adresa": person.slug, "od": int(start), "do": int(seen)}
            self._snap = None

    def caption_on(self) -> bool:
        """Whether a caption names the speaker now (a turn open that was not found by voice or the chair's words)."""
        with self._lock:
            return bool(self.open and self.turns and not self.turns[-1].get("izvor"))

    def heard(self, person: Person, how: str, start: float, seen: float, tracked: set | None = None) -> None:
        """Someone found speaking without a caption: by the chair's words giving them the floor ("prepis") or by
        their voice ("glas"), or a caption that stands only for seconds ("potpis", 24 Nov 2026). A caption on rules; the same speaker goes on; another one ends the turn before (not
        before its own start) and begins theirs. `tracked`: whose voices are known, so that a turn of theirs lasts as
        long as the voice does, and one of someone else's as long as nothing else is heard."""
        with self._lock:
            if self.status == NO_STREAM or (self.open and self.turns and not self.turns[-1].get("izvor")):
                return
            cur = self.turns[-1] if self.turns else None
            if (how == "glas" and self.open and cur and cur["key"] != person.key and cur.get("izvor") in ("prepis", "potpis")
                    and seen <= cur["start"] + 3):
                # the last seconds of the speaker before, heard only now (the windows lag): the floor has passed on.
                # 24 Nov 2026, 12:18:54: they ended Jovo Bakić's reply in the second it began, and it went to the
                # speaker before
                before = next((x for x in reversed(self.turns[:-1]) if x["key"] == person.key), None)
                if before and before.get("izvor") and cur["start"] - before["seen"] <= 30:
                    before["seen"] = max(before["seen"], min(seen, cur["start"]))
                    self._save()
                return
            if self.open and cur and cur["key"] == person.key:
                cur["seen"] = max(cur["seen"], seen)
                if how == "potpis":  # a caption of ten seconds (ocr.outlined) said who it is: surer than the words
                    cur["izvor"] = "potpis"
                    cur.setdefault("natpis", start)
                if how == "glas":
                    cur["po_glasu"] = True
                    cur["start"] = min(cur["start"], start) if start > cur["start"] - 30 else cur["start"]
            elif not self.open and cur and cur["key"] == person.key and self._went_on(cur, start):
                # a turn ended by a voice not recognised (or the chair's), the speaker going on: the same turn
                # (24 Nov 2026, 15:47: 139 s of Aleksandra Ilić's stood as nobody's, her speech cut in two)
                cur["seen"] = max(cur["seen"], seen)
                if how == "glas":
                    cur["po_glasu"] = True
                if how == "potpis":
                    cur["izvor"] = "potpis"
                    cur.setdefault("natpis", start)
                self.open = True
            else:
                if self.open and cur:
                    cur["seen"] = min(cur["seen"], max(cur["start"], start))
                    self.open = False
                begin = max(start, cur["seen"] if cur else start)
                self.turns.append({"key": person.key, "name": person.name, "slug": person.slug, "group": person.group,
                                   "role": "", "start": begin, "seen": max(seen, begin), "n": SURE_FRAMES, "izvor": how,
                                   "video": "", "sq_start": None, "sq_seen": None, "seg": None})
                if how == "potpis":
                    self.turns[-1]["natpis"] = start
                if how == "glas" or (tracked and person.slug in tracked and how != "prepis"):
                    self.turns[-1]["po_glasu"] = True
                self.open = True
            self.status = SPEAKING
            self._snap = None
            self._save()

    def clocked(self, person: Person, now: float, seconds: int) -> None:
        """The broadcast's own clock beside a caption ("0:15"): the turn of who it names began that long ago. Taken when
        two readings of the same speaker agree within 3 s, for a turn begun up to two minutes before: one reading may
        err. The turn before ends where this one begins, if it ran past it."""
        with self._lock:
            began = now - seconds
            was, self._clock = getattr(self, "_clock", None), (person.key, began)
            if not was or was[0] != person.key or abs(was[1] - began) > 3:
                return
            began = (was[1] + began) / 2
            cur = self.turns[-1] if self.turns else None
            if not (self.open and cur and cur["key"] == person.key and cur.get("izvor")):
                return
            before = self.turns[-2] if len(self.turns) > 1 else None
            if before and before["key"] == person.key and before["start"] - CLOCK_JOIN <= began <= before["seen"] + 5 \
                    and seconds <= LONGEST_CLOCK:
                # the speech began in the turn before: one speech, cut in two where nothing named the speaker
                # (24 Nov 2026, 16:57: Milena Đorđijević's, 646 s of it nobody's; the clock said 11:15 and more than
                # two minutes were not believed)
                before["start"] = max(before["start"], began)
                self._join(before, cur)
                before["izvor"] = "potpis"
                self._save()
                return
            if abs(cur["start"] - began) > 120:
                return
            if before and before["seen"] > began:
                before["seen"] = max(before["start"], began)
            cur["start"] = min(began, cur["seen"])
            self._snap = None
            self._save()

    def _join(self, before: dict, cur: dict) -> None:
        """The last turn made part of the same speaker's turn before it. Called with the lock held."""
        self.turns.pop()
        before["seen"] = max(before["seen"], cur["seen"])
        before["n"] += cur["n"]
        for k in ("natpis", "po_glasu"):
            if cur.get(k) and not before.get(k):
                before[k] = cur[k]
        for k in ("sq_seen", "seg"):
            if cur.get(k) is not None:
                before[k] = cur[k]
        self._snap = None

    def _mend(self) -> None:
        """The same speaker named again, joined once the words between are written down: they come half a minute after the
        turn begins, when `_went_on` could not yet say that speech had gone on (24 Nov 2026, 17:32: Vjerica Radeta's,
        14 s of it nobody's). Called with the lock held, after each piece."""
        if len(self.turns) < 2:
            return
        before, cur = self.turns[-2], self.turns[-1]
        if before["key"] == cur["key"] and cur.get("izvor") and before["seen"] < cur["start"] and self._went_on(before, cur["start"]):
            self._join(before, cur)
            self._save()

    def _went_on(self, turn: dict, start: float) -> bool:
        """Whether speech went on from a turn's end to `start` (the words written down between), no floor given to
        anyone else: then the same speaker named again is the same turn. Called with the lock held."""
        gap = start - turn["seen"]
        if not (turn.get("izvor") and 8 <= gap <= REJOIN):
            return False
        between = [v for k, v in self.said.items()
                   if k.lstrip("p").isdigit() and turn["seen"] - 5 <= int(k.lstrip("p")) < start]
        if sum(len(v.split()) for v in between) < REJOIN_WORDS * gap or any(CHAIRS.search(v) for v in between):
            return False
        return not any(e.get("vrsta") == "Reč ima" and turn["seen"] - 5 < e["t"] < start and e.get("url") != turn["slug"]
                       for e in self.events[-60:])

    def unheard(self, at: float) -> None:
        """Another voice (the chair's) has the floor from `at`: a turn found without a caption ends there."""
        with self._lock:
            cur = self.turns[-1] if self.turns else None
            if self.open and cur and cur.get("izvor") and at > cur["start"]:
                cur["seen"] = min(cur["seen"], at) if cur.get("po_glasu") else at
                self._close()
                self.status = UNKNOWN
                self._snap = None

    def voice_gone(self, last: float, newest: float, tracked: set) -> None:
        """No voice heard for GAP: a turn whose speaker's voice was recognised in it ends with the last voice heard.
        Not one whose voice is only on the list: a voice not recognised does not say that nobody speaks (24 Nov 2026,
        14:02: 80 s of Miroslav Andrić's stood as 0 s)."""
        with self._lock:
            cur = self.turns[-1] if self.turns else None
            if not (self.open and cur and cur.get("izvor")):
                return
            if cur.get("po_glasu") and newest - cur["start"] > 30 and newest - cur["seen"] > 8:
                cur["seen"] = max(cur["start"], min(cur["seen"], last))
                self._close()
                self.status = UNKNOWN
                self._snap = None

    def tick(self, now: float | None = None) -> None:
        """Called each second, frame or not: a broadcast that stopped ends the turn."""
        now = time.time() if now is None else now
        with self._lock:
            if self.status != NO_STREAM and now - max(self.last_frame, self._resumed) > config.STALE_SECONDS:
                self._close()
                self.status = NO_STREAM
                self._snap = None
                self._save()  # so that a restart after the broadcast ended takes up nothing (_resume)

    def record(self, day: str) -> dict | None:
        """A day's record, as published at /dan/<date>.json: every turn (with how many frames named the speaker,
        so a reader can leave out one-frame readings), where each is in the broadcast, and when the broadcast was
        seen at all."""
        with self._lock:
            if day == self.day:
                turns, cover = list(self.turns), list(self.cover)
            else:
                f = _kept(self.days, day)
                if not f:
                    return None
                kept = json.loads(f.read_text(encoding="utf-8"))
                turns, cover = kept.get("turns", []), kept.get("cover", [])
        return {
            "dan": day,
            "napomena": "Pročitano automatski iz potpisa u prenosu Skupštine; može da sadrži greške. Van 'pokriveno' "
                        "servis prenos nije video.",
            "pokriveno": [{"od": int(a), "do": int(b)} for a, b in cover],
            "govori": [{"ime": t["name"], "adresa": t["slug"], "grupa": t["group"], "uloga": t["role"],
                        "od": int(t["start"]), "do": int(t["seen"]), "okvira": t["n"] if counted(t) or t["n"] < 2 else 1,  # a turn not kept reads as a single frame to the site, which drops those
                        "video": t.get("video", ""),
                        "sq_od": t.get("sq_start"), "sq_do": t.get("sq_seen"), "segment": t.get("seg"),
                        **({"izvor": t["izvor"]} if t.get("izvor") else {})}
                       for t in (self._named(turns, merge=False) if self.roster else turns)],
        }

    def days_kept(self) -> list[str]:
        if not self.days or not self.days.exists():
            return [self.day] if self.turns or self.cover else []
        return sorted({p.stem for p in self.days.glob("*.json")} | ({self.day} if self.turns or self.cover else set()))
