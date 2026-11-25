"""The state as the page's own process has it: read from the files the measuring keeps, never written (25 Nov 2026).

A Tracker that is told nothing: before each look it takes up the files that have changed since the last one (each is
written whole, so one is never read half), and `state_view` draws the snapshot from it as from the measuring's own.
Two clocks say how far it may be believed (`sada.py`):
- the measuring's heartbeat: without one for BEAT_OLD seconds, or with its loop of frames standing for LOOP_OLD, the
  page is not to be served (`alive`), as when the service is down;
- the last frame: with none for config.STALE_SECONDS nobody is shown as speaking, whatever the files say. The
  measuring's own loop says that too (`Tracker.tick`), but a loop that stands (yt-dlp or a frame's reading hung while
  the heartbeat's thread goes on) says nothing, and the page must not go on naming a speaker for it.
Nothing heavy is imported here or below (a test asks): no model, no stream's reader, no OCR."""
from __future__ import annotations

import json
import time
from pathlib import Path

from . import config
from .names import Roster
from .state import Tracker, _kept
from .state_base import NO_STREAM, SPEAKING, UNKNOWN

BEAT_OLD = 30.0  # seconds with no heartbeat (one comes every 5): the measuring is not there
LOOP_OLD = 300.0  # seconds its loop may stand: between sittings a look for a broadcast asks yt-dlp up to four times


def alive(m: dict, now: float | None = None) -> bool:
    """Whether the measuring that wrote the moment `m` is there and looking."""
    now = time.time() if now is None else now
    try:
        return now - float(m["t"]) <= BEAT_OLD and now - float(m["petlja"]) <= LOOP_OLD
    except (KeyError, TypeError, ValueError):
        return False


class Files:
    """JSON files read again only when they have changed."""

    def __init__(self) -> None:
        self._kept: dict[Path, tuple] = {}

    def get(self, f: Path, empty):
        """(the file's content or `empty`, whether it is another than the last time). A file of another kind than
        `empty`, or one that cannot be read, leaves what was read of it before."""
        try:
            st = f.stat()
            mark = (st.st_mtime_ns, st.st_ino, st.st_size)
        except OSError:
            mark = None
        kept = self._kept.get(f)
        if kept and kept[0] == mark:
            return kept[1], False
        data = empty
        if mark is not None:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return (kept[1] if kept else empty), False
            if not isinstance(data, type(empty)):
                data = kept[1] if kept else empty
        self._kept[f] = (mark, data)
        return data, True


class Reader(Tracker):
    def __init__(self, path: str, tz: str | None = None) -> None:
        self.base = Path(path).parent
        self.files = Files()
        self.sada: dict = {}
        super().__init__(path, tz)
        self.refresh()

    # what a Tracker does at its start and after each reading, and a reader does not
    def _migrate(self) -> None:
        pass

    def _resume(self, now: float | None = None) -> None:
        pass

    def _save(self) -> None:
        pass

    def alive(self, now: float | None = None) -> bool:
        """Whether the measuring is there and looking: what the page says of this moment may be believed."""
        with self._lock:
            return alive(self.files.get(self.base / "sada.json", {})[0], now)

    def refresh(self, now: float | None = None) -> None:
        """The files that have changed, taken up."""
        now = time.time() if now is None else now
        with self._lock:
            self._refresh(now)

    def _refresh(self, now: float) -> None:
        get = self.files.get
        self.sada = m = get(self.base / "sada.json", {})[0]
        self.day = str(m.get("dan") or self._day(now))
        d = get(self.days / f"{self.day}.json", {})[0]
        self.turns, self.cover = d.get("turns") or [], d.get("cover") or []
        self.said = get(self._said_file(self.day), {})[0]
        self.events = get(self._events_file(self.day), [])[0]
        self.item = get(self.base / "tacka.json", {})[0]
        self.waiting = get(self.waiting_file, {})[0]
        self.recording = get(self.recording_file, {})[0]
        self.facts, new_facts = get(self.facts_file, {})
        listed, new_list = get(self.base / "podaci.json", {})
        if listed and (new_list or new_facts):  # a new object: what was matched to the last one is matched again
            self.roster = Roster.from_json(json.dumps(listed))
            if self.facts:
                self.roster.current = frozenset(self.facts)
        self.captions = m.get("titl") or []
        self.place, self.presiding = m.get("mesto") or {}, m.get("predsedava") or {}
        self._resumed = float(m.get("nastavljeno") or 0)
        self.last_frame = float(m.get("okvir") or 0)
        # The turns and whether one is open come from the same file, so a speaker is never shown for another's turn;
        # the moment's file, up to a second behind it, may only say that there is no broadcast (after a restart the
        # day's file still says what the run before left in it).
        self.open, self.status = False, NO_STREAM
        if m.get("stanje") in (SPEAKING, UNKNOWN) and d.get("status") in (SPEAKING, UNKNOWN):
            self.last_frame = max(self.last_frame, float(d.get("last_frame") or 0))
            if now - max(self.last_frame, self._resumed) <= config.STALE_SECONDS:
                self.open = bool(d.get("open")) and bool(self.turns)
                self.status = SPEAKING if self.open else UNKNOWN

    # --- the same questions as the measuring's tracker answers ---
    def _snapshot(self, now: float | None) -> dict:
        self.refresh(now)
        return super()._snapshot(now)

    def summary_of(self, day: str) -> dict:
        f = _kept(self.base / "sazetak", day)  # one of the folder's own files: the day may come from a request
        return self.files.get(f, {})[0] if f else {}

    def lines_of(self, day: str) -> list:
        return self.files.get(self.base / "rezimei" / f"{day}.json", [])[0] if config.SPEECH_LINES else []

    def record(self, day: str) -> dict | None:
        self.refresh()
        return super().record(day)

    def days_kept(self) -> list[str]:
        self.refresh()
        return super().days_kept()
