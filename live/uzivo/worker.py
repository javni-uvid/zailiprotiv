"""The background loop: keep a frame source running, read each new frame's caption, and tell the tracker."""
from __future__ import annotations

import logging
import os
import threading
import time
import urllib.request
from pathlib import Path

from PIL import Image

from . import config
from .caption import differs, tidy, who
from .names import Roster
from .ocr import caption
from .state import Tracker
from .stream import VIDEO, NotLive, resolve_input, start_ffmpeg

log = logging.getLogger("worker")


class RosterKeeper:
    """The site's list of MPs: fetched at start and every few hours, with the last good copy kept on disk."""

    def __init__(self) -> None:
        self.cache = Path(config.STATE_PATH).with_name("podaci.json")
        self.roster = Roster()
        self.fetched = 0.0
        if self.cache.exists():
            self.roster = Roster.from_json(self.cache.read_text(encoding="utf-8"))

    def get(self) -> Roster:
        if time.time() - self.fetched > config.ROSTER_HOURS * 3600:
            self.fetched = time.time()
            try:
                req = urllib.request.Request(config.ROSTER_URL, headers={"User-Agent": "zailiprotiv-uzivo"})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    text = resp.read().decode("utf-8")
                self.roster = Roster.from_json(text)
                self.cache.parent.mkdir(parents=True, exist_ok=True)
                self.cache.write_text(text, encoding="utf-8")
                log.info("roster: %d MPs", len(self.roster.people))
            except Exception as exc:  # the last good list stays
                log.warning("roster not fetched (%s); keeping %d MPs", exc, len(self.roster.people))
        return self.roster


def _mtime(path: str) -> float:
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0


WAIT = 60.0  # between sittings, how often to look for a broadcast: a sitting is read within a minute of going live


def run(tracker: Tracker, stop: threading.Event) -> None:
    roster = RosterKeeper()
    backoff = 5.0
    waiting = False  # said once in the log, not on every look
    while not stop.is_set():
        proc = None
        try:
            source, headers = resolve_input()
            proc = start_ffmpeg(source, headers)
            log.info("frames started: %s", VIDEO.get("id", "") or source[:60])
            waiting = False
            seen = _mtime(config.FRAME_PATH)
            last_new = time.time()
            while not stop.is_set():
                stop.wait(1.0)
                tracker.tick()
                m = _mtime(config.FRAME_PATH)
                if m > seen:
                    seen, last_new, backoff = m, time.time(), 5.0
                    at = {"video": VIDEO.get("id", ""), "sq": getattr(proc, "frame_seq", None),
                          "seg": getattr(proc, "seg_dur", None)}
                    try:
                        cap = caption(Image.open(config.FRAME_PATH).convert("RGB"))
                    except Exception:  # a broken frame or an OCR error: skip it
                        log.exception("frame not read")
                        continue
                    person = who(cap, roster.get(), config.MATCH)
                    tracker.observe(person, tidy(cap.role_line) if cap.role_clean else "",
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
        tracker.tick()
        stop.wait(backoff)
        if not waiting:
            backoff = min(backoff * 2, WAIT)
