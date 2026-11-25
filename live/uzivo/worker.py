"""The background loop: keep a frame source running, read each new frame's caption, and tell the tracker."""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path

from PIL import Image

from . import config, mreza
from .caption import differs, role, sure, who
from .names import Roster
from .ocr import caption, clock, outlined
from .state import Tracker
from .state_base import write_text
from .stream import VIDEO, NotLive, resolve_input, start_ffmpeg

log = logging.getLogger("worker")


class RosterKeeper:
    """The site's list of MPs: fetched at start and every few hours, with the last good copy kept on disk. With it,
    the last sitting day read from the recording and "Dok čekate", handed to the tracker."""

    def __init__(self, tracker: Tracker | None = None) -> None:
        self.tracker = tracker
        self.cache = Path(config.STATE_PATH).with_name("podaci.json")
        self.roster = Roster()
        self.fetched = 0.0
        if self.cache.exists():
            self.roster = Roster.from_json(self.cache.read_text(encoding="utf-8"))

    def get(self) -> Roster:
        if time.time() - self.fetched > config.ROSTER_HOURS * 3600:
            self.fetched = time.time()
            try:
                text = mreza.site(config.ROSTER_URL)
                self.roster = Roster.from_json(text)
                write_text(self.cache, text)
                log.info("roster: %d MPs", len(self.roster.people))
            except Exception as exc:  # the last good list stays
                log.warning("roster not fetched (%s); keeping %d MPs", exc, len(self.roster.people))
            if self.tracker:
                for url, use in ((config.DAY_URL, self.tracker.use_recording), (config.WAIT_URL, self.tracker.use_waiting),
                                 (config.FACTS_URL, self.tracker.use_facts)):
                    try:
                        use(json.loads(mreza.site(url)))
                    except Exception as exc:  # the last good copy stays
                        log.warning("%s not fetched (%s)", url, exc)
            if self.tracker:
                self.tracker.roster = self.roster
        if self.tracker and self.tracker.facts:  # the sitting convocation's MPs first, when a caption is matched
            self.roster.current = frozenset(self.tracker.facts)
        return self.roster


def _mtime(path: str) -> float:
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0


WAIT = 60.0  # between sittings, how often to look for a broadcast: a sitting is read within a minute of going live


def run(tracker: Tracker, stop: threading.Event, bell=None) -> None:
    roster = RosterKeeper(tracker)
    roster.get()  # the list, and the last day from the recording, before any broadcast
    backoff = 5.0
    waiting = False  # said once in the log, not on every look
    while not stop.is_set():
        proc = None
        tracker.looped = time.time()
        try:
            source, headers = resolve_input()
            proc = start_ffmpeg(source, headers)
            log.info("frames started: %s", VIDEO.get("id", "") or source[:60])
            if bell:
                bell.restart()
            waiting = False
            seen = _mtime(config.FRAME_PATH)
            last_new = time.time()
            while not stop.is_set():
                stop.wait(1.0)
                tracker.looped = time.time()
                tracker.tick()
                m = _mtime(config.FRAME_PATH)
                if m > seen:
                    seen, last_new, backoff = m, time.time(), 5.0
                    if bell:  # a sitting's broadcast has begun: the day's notification (obavesti.py)
                        bell.frame()
                        try:
                            bell.heard(tracker)  # … and one when it goes on after a long break
                        except Exception:
                            log.exception("the end of a break not looked for")
                    at = {"video": VIDEO.get("id", ""), "sq": getattr(proc, "frame_seq", None),
                          "seg": getattr(proc, "seg_dur", None)}
                    try:
                        frame = Image.open(config.FRAME_PATH).convert("RGB")
                        cap = caption(frame)
                    except Exception:  # a broken frame or an OCR error: skip it
                        log.exception("frame not read")
                        continue
                    person = who(cap, roster.get(), config.MATCH)
                    under = role(cap.role_line, person, roster.get(), config.MATCH) if cap.role_clean else ""
                    if not person:  # the caption as it looked on 24 Nov 2026 (ocr.outlined)
                        try:
                            found = ((c, sure(c, roster.get(), config.MATCH)) for c in outlined(frame))
                            hit = next(((c, p) for c, p in found if p), None)
                        except Exception:
                            log.exception("the outlined caption not read")
                            hit = None
                        if hit:  # it stands about ten seconds at a turn's start: found, not a caption that stays on
                            at_ = time.time()
                            tracker.heard(hit[1], "potpis", at_, at_)
                            try:
                                sec = clock(frame)  # "0:15" beside it: when the turn began
                                if sec is not None:
                                    tracker.clocked(hit[1], at_, sec)
                            except Exception:
                                log.exception("the clock not read")
                    tracker.observe(person, under,
                                    other=differs(cap, tracker.current(), config.MATCH), at=at)
                    log.info("%s | %s | %s -> %s", person.name if person else "-", cap.name_line[:40],
                             cap.role_line[:40], tracker.status)
                if proc.poll() is not None:
                    err = (proc.stderr.read() or b"").decode("utf-8", "replace")[-300:]
                    raise RuntimeError(f"frames stopped: {err.strip() or 'end of broadcast'}")
                if time.time() - last_new > max(config.STALE_SECONDS, 4 * config.FRAME_INTERVAL):
                    raise RuntimeError("no new frames")
        except NotLive as exc:
            if not waiting:
                log.info("no broadcast now (%s); looking again every %.0f s", exc, WAIT)
                waiting = True
            backoff = WAIT
        except Exception as exc:
            log.warning("no broadcast (%s); trying again in %.0f s", exc, backoff)
        finally:
            if proc and proc.poll() is None:
                proc.kill()
        tracker.looped = time.time()
        tracker.tick()
        stop.wait(backoff)
        if not waiting:
            backoff = min(backoff * 2, WAIT)
