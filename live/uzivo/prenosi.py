"""The day's broadcasts on YouTube, so that its speeches can be played between the broadcast's end and the archive's file
(25 Nov 2026, the maintainer's decision; until then the links went with the broadcast, as its video goes private).

Kept per day by the measuring alone, `/data/prenosi/<day>.json`: `prenosi`, each {"video", "pocetak": the second the
video's first second is at, "od", "do": from when to when it was read}, a new one when the video is another or its
clock has moved; and `javni`, per video when it was last asked about and whether it is public. Asked at most once in
INTERVAL, only while there is no broadcast and no file of the archive for the day the page shows, in a thread of its own.
Anything but a clear yes drops the links. The page's process has the answer from sada.json (citac.py). Only the standard
library."""
from __future__ import annotations

import json
import logging
import re
import threading
import time
from pathlib import Path

from . import config
from .state_base import NO_STREAM, _write

log = logging.getLogger("prenosi")
INTERVAL = 600.0  # seconds between two questions, whatever is asked about
GRACE = 900.0  # an answer older than its turn to be asked again by this much is no answer
SAME = 20.0  # seconds: the video's beginning as two frames say it; further apart, its clock stood or it is another
EVERY = 30.0  # the end of what was read is written this often
LOOK = 30.0  # seconds between two looks while no broadcast is on (the file may have been put there by hand)
EDGE = 60.0  # a turn begins this much outside what was read at most
AGENT = "zailiprotiv-mikrofon (+https://zailiprotiv.rs)"
ID = re.compile(r"[\w-]{6,20}", re.ASCII)


def _number(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and 1.7e9 < x < 4e9


def clean(data) -> dict:
    """A day's file as it must be; whatever is not shaped so is left out, and nothing is left of a wrong file."""
    if not isinstance(data, dict):
        return {"prenosi": [], "javni": {}}
    rows = data.get("prenosi") if isinstance(data.get("prenosi"), list) else []
    asked = data.get("javni") if isinstance(data.get("javni"), dict) else {}
    ok = lambda r: (isinstance(r, dict) and isinstance(r.get("video"), str) and ID.fullmatch(r["video"])
                    and all(_number(r.get(k)) for k in ("pocetak", "od", "do")) and r["pocetak"] - EDGE <= r["od"] <= r["do"])
    return {"prenosi": [{k: r[k] for k in ("video", "pocetak", "od", "do")} for r in rows if ok(r)],
            "javni": {v: {"t": a["t"], "da": a["da"] is True} for v, a in asked.items()
                      if isinstance(a, dict) and _number(a.get("t")) and "da" in a}}


def read(f: Path | None) -> dict:
    try:
        return clean(json.loads(f.read_text(encoding="utf-8")) if f else None)
    except (OSError, ValueError):
        return clean(None)


def shown(kept: dict, day: str, now: float) -> list[dict]:
    """The broadcasts of the shown day whose video is known to be public now: `kept` is {"dan", "prenosi"} with each one's
    `vazi`, until when the answer holds."""
    if not isinstance(kept, dict) or kept.get("dan") != day:
        return []
    return [{k: p[k] for k in ("video", "pocetak", "od", "do")} for p in kept.get("prenosi") or [] if now < p.get("vazi", 0)]


def place(open_: list[dict], at: float, video: str = "") -> dict | None:
    """Where a moment is in them: {"video", "snimak"}; None outside what was read."""
    for p in reversed(open_):
        if p["od"] - EDGE <= at <= p["do"] + EDGE and at >= p["pocetak"] and video in ("", p["video"]):
            return {"video": p["video"], "snimak": int(at - p["pocetak"])}
    return None


def public(video: str, timeout: float = 15) -> bool:
    """Whether YouTube says the video may be played by anyone, elsewhere too (its oEmbed: 401, 403 or 404 when not)."""
    import urllib.parse
    import urllib.request
    if not ID.fullmatch(video):
        return False
    url = "https://www.youtube.com/oembed?format=json&url=" + urllib.parse.quote("https://www.youtube.com/watch?v=" + video, safe="")
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": AGENT}), timeout=timeout) as r:
            told = json.loads(r.read(65536).decode("utf-8"))
            return r.status == 200 and isinstance(told, dict) and told.get("type") == "video"
    except Exception as exc:  # refused, unreachable, unreadable: no
        log.info("the video %s is not known to be public (%s)", video, exc)
        return False


class Keeper(threading.Thread):
    """Keeps the day's broadcasts while they are read, and asks about them when they are over."""

    def __init__(self, tracker, stop: threading.Event, folder: Path | None = None, ask=public) -> None:
        super().__init__(daemon=True)
        self.tracker, self.halt, self.ask = tracker, stop, ask
        self.folder = folder or Path(config.STATE_PATH).parent / "prenosi"
        self.noted = self.written = self.asked = 0.0

    def note(self) -> None:
        """The newest frame's place, taken into the day's file."""
        with self.tracker._lock:
            p = dict(self.tracker.place)
        if not p or p["t"] <= self.noted:
            return
        self.noted = p["t"]
        f = self.folder / f"{self.tracker._day(p['t'])}.json"
        kept = read(f)
        begun = p["t"] - (p["sq"] - config.RECORDING_LEAD) * p["seg"]
        last = kept["prenosi"][-1] if kept["prenosi"] else None
        if last and last["video"] == p["video"] and abs(last["pocetak"] - begun) <= SAME:
            if p["t"] - last["do"] < EVERY:
                return
            last["do"] = p["t"]
        elif ID.fullmatch(p["video"]) and begun <= p["t"]:
            kept["prenosi"].append({"video": p["video"], "pocetak": round(begun, 2), "od": p["t"], "do": p["t"]})
        else:
            return
        _write(f, kept)

    def look(self, now: float | None = None) -> None:
        """What may be linked now (`tracker.broadcasts`), asking about one video when its time has come."""
        now = time.time() if now is None else now
        if self.tracker.status != NO_STREAM:  # a broadcast is on: nothing asked, and no snapshot drawn for this alone
            self.say({})
            return
        snap = self.tracker.snapshot()
        day = snap["dan"]
        if snap["stanje"] != NO_STREAM or snap["datoteke"] or any(d.get("datoteka") for d in snap["danas"]):
            self.say({})
            return
        f = self.folder / f"{day}.json"
        kept = read(f)
        videos = list(dict.fromkeys(p["video"] for p in kept["prenosi"]))
        if not videos:
            self.say({})
            return
        told = kept["javni"]
        last = max([self.asked] + [a["t"] for a in told.values() if a["t"] <= now])
        if now - last >= INTERVAL:
            v = min(videos, key=lambda v: told[v]["t"] if v in told else 0.0)  # the one asked about longest ago
            self.asked = now
            told[v] = {"t": now, "da": bool(self.ask(v))}
            again = read(f)  # the answer took a while: what stands in the file now keeps its broadcasts
            again["javni"] = told
            _write(f, again)
            kept = again
        holds = INTERVAL * len(videos) + GRACE
        self.say({"dan": day, "prenosi": [{**p, "vazi": told[p["video"]]["t"] + holds} for p in kept["prenosi"]
                                          if told.get(p["video"], {}).get("da")]})

    def say(self, what: dict) -> None:
        if what != self.tracker.broadcasts:
            with self.tracker._lock:
                self.tracker.broadcasts = what
                self.tracker._snap = None

    def run(self) -> None:
        looked = 0.0
        while not self.halt.is_set():
            try:
                self.note()
                if self.tracker.status != NO_STREAM or time.time() - looked >= LOOK:
                    looked = time.time()
                    self.look()
            except Exception:
                log.exception("the day's broadcasts not kept or not asked about")
                try:
                    self.say({})  # never links nobody looks after
                except Exception:
                    log.exception("the links not dropped")
            self.halt.wait(5.0)
