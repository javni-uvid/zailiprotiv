"""The measuring ends itself when its loop stands still (25 Nov 2026).

Docker starts a container again whose process has ended, not one its check calls unhealthy, so a loop that hung stood
until somebody looked. Here a thread of its own looks at the loop's clock (`Tracker.looped`), and ends the process when
it has not moved for STANDS seconds; Docker's restart policy starts it again and the day goes on from the kept files. In the
one-container form the page goes down with it for a second or two. A test container has no such policy, and stays ended.

The rule is on the loop's own turn, at any hour: a second apart while a broadcast is read, at most 70 s between sittings (on
24 and 25 Nov 2026 never over 11 s and 70 s). No frames, in a break or with the broadcast over, is not standing. It
takes no lock of the tracker's (one held for ever is among the things that make the loop stand). It ends nothing:
- while something is being made that a restart would cut (`making`: the day's summary, the mail, a notification; all in
  threads of their own, which a loop that stands does not stop);
- more than MOST times in WITHIN seconds (kept on disk, as each run starts with nothing in memory): a cause outside, which
  a restart does not cure, then leaves the loop standing as before this rule (as two, the page answers 503 and the
  maintainer is told by the counter's watch).

Time is counted by looks, not by the clock: a computer that slept, or a clock moved, is not a loop that stands. Only the
standard library."""
from __future__ import annotations

import json
import logging
import os
import sys
import threading
import time
import traceback
from contextlib import contextmanager
from pathlib import Path

from . import config
from .state_base import _write

log = logging.getLogger("cuvar")
STANDS = 180.0  # seconds the loop may stand: one ask of YouTube with the net gone takes 80 (stream.NET)
LOOK = 5.0  # seconds between looks
MOST, WITHIN = 3, 3600.0  # at most this many ends in so many seconds
MADE_MOST = 3600.0  # what is made longer than this hangs too (the model's and the mail's calls have limits of their own)

_lock = threading.Lock()
_making: dict[object, tuple[str, float]] = {}


@contextmanager
def making(what: str):
    """What is made inside is not cut by this module."""
    key = object()
    with _lock:
        _making[key] = (what, time.monotonic())
    try:
        yield
    finally:
        with _lock:
            _making.pop(key, None)


def _made(now: float) -> str:
    return ", ".join(what for what, since in _making.values() if now - since < MADE_MOST)


def _leave() -> None:
    os._exit(1)  # not sys.exit: the thread that stands would hold the process


class Guard(threading.Thread):
    def __init__(self, tracker, stop: threading.Event, loop: threading.Thread | None = None, leave=_leave,
                 path: Path | None = None) -> None:
        super().__init__(daemon=True)
        self.tracker, self.halt, self.loop, self.leave = tracker, stop, loop, leave
        self.path = path or Path(config.STATE_PATH).with_name("cuvar.json")
        self.seen, self.stood, self.said = None, 0.0, ""

    def _ends(self, now: float) -> list[float]:
        """When this rule ended the process of late. Raises when what is kept cannot be read: then it ends nothing."""
        if not self.path.exists():
            return []
        return [float(t) for t in json.loads(self.path.read_text(encoding="utf-8"))["izlasci"] if 0 <= now - float(t) < WITHIN]

    def _where(self) -> str:
        """Where in the code the loop stands, for the log."""
        frame = sys._current_frames().get(self.loop.ident) if self.loop and self.loop.ident else None
        if frame is None:
            return "the loop's thread is not there"
        return " < ".join(f"{Path(f.filename).name}:{f.lineno} {f.name}" for f in reversed(traceback.extract_stack(frame)[-6:]))

    def _say(self, why: str) -> None:
        if why != self.said:  # said once, not on every look
            self.said = why
            log.error("the loop has stood %.0f s; %s; it is at: %s", self.stood, why, self._where())

    def step(self, passed: float, now: float | None = None) -> bool:
        """One look, `passed` seconds after the last; whether the process is ended."""
        now = time.time() if now is None else now
        looped = self.tracker.looped
        if looped != self.seen:
            self.seen, self.stood, self.said = looped, 0.0, ""
            return False
        self.stood += min(passed, 2 * LOOK)
        if self.stood < STANDS:
            return False
        with _lock:  # held to the end: what would begin to be made now waits, and is made by the next run
            made = _made(time.monotonic())
            if made:
                self._say(f"not ended while this is made: {made}")
                return False
            try:
                ends = self._ends(now)
                if len(ends) >= MOST:
                    self._say(f"not ended: {len(ends)} times it was within {WITHIN / 60:.0f} minutes")
                    return False
                _write(self.path, {"izlasci": ends + [now]})  # first: an end that cannot be counted would be without limit
            except (OSError, ValueError, KeyError, TypeError) as exc:
                self._say(f"not ended: the count of the ends is not kept ({exc})")
                return False
            self._say(f"this process ends, {len(ends) + 1}. of at most {MOST} in {WITHIN / 60:.0f} minutes, for Docker to start it again")
            self.leave()
            return True

    def run(self) -> None:
        last = time.monotonic()
        while not self.halt.wait(LOOK):
            was, last = last, time.monotonic()
            try:
                if self.step(last - was):
                    return
            except Exception:
                log.exception("not looked at")
