"""What the measuring tells the page: the moment, in one small file beside the day's files (25 Nov 2026).

The service is to become two containers (docs/decisions/live-service.md): the measuring, which must not stop while
somebody speaks, and the page, which may be replaced at any minute. The page reads the files the service keeps anyway,
each written whole at every change. This one holds what was in memory only (the line under the picture, the place in
the broadcast, who presides, the video, the live sound) and two clocks: that the measuring is there at all (`t`), and
when its loop of frames last turned (`petlja`). `citac.Reader` reads it.

And the lock that keeps the writing to one: two measurings on the same volume would write over each other's files."""
from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path

from . import config, slusaj
from .state_base import _write
from .stream import VIDEO

try:
    import fcntl
except ImportError:  # Windows: the tests, and a trial by hand; nothing to guard there
    fcntl = None

log = logging.getLogger("sada")
FORMAT = 1  # what the page must be able to read; raised when a field it needs changes its meaning
BEAT = 5.0  # seconds: written this often though nothing changed
LOOK = 1.0  # seconds between looks for a change


def file(state_path: str | Path) -> Path:
    return Path(state_path).with_name("sada.json")


def read(state_path: str | Path) -> dict:
    try:
        m = json.loads(file(state_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return m if isinstance(m, dict) else {}


def moment(tracker, now: float) -> dict:
    """The moment as the page needs it, beside the day's files."""
    with tracker._lock:
        out = {"dan": tracker.day, "stanje": tracker.status, "okvir": tracker.last_frame, "nastavljeno": tracker._resumed,
               "titl": list(tracker.captions), "mesto": dict(tracker.place), "predsedava": dict(tracker.presiding),
               "prenosi": tracker.broadcasts}
    return {"format": FORMAT, "verzija": config.VERSION, "t": now, "petlja": tracker.looped, **out,
            "video": VIDEO.get("id", ""),
            "zvuk": {"t": slusaj.PLAYLIST.seen if slusaj.PLAYLIST.items else 0, "url": slusaj.address()}}


class Pulse(threading.Thread):
    """Writes the moment when it has changed, once a second at most, and every BEAT seconds though it has not."""

    def __init__(self, tracker, stop: threading.Event, path: str | Path | None = None) -> None:
        super().__init__(daemon=True)
        self.tracker, self.halt = tracker, stop
        self.path = file(path or config.STATE_PATH)
        self.last, self.at = None, 0.0

    def step(self, now: float | None = None) -> bool:
        """One look; whether the file was written."""
        now = time.time() if now is None else now
        m = moment(self.tracker, now)
        same = {k: v for k, v in m.items() if k not in ("t", "petlja")}
        if same == self.last and now - self.at < BEAT:
            return False
        _write(self.path, m)
        self.last, self.at = same, now
        return True

    def run(self) -> None:
        while not self.halt.is_set():
            try:
                self.step()
            except Exception:  # a full disk, say: the measuring goes on, and the page will say nobody looks
                log.exception("the moment not written")
            self.halt.wait(LOOK)


_held: list = []  # the lock's open file: the lock lasts as long as it is open, so to the end of the process


def only_writer(folder: Path, said_every: float = 30.0) -> bool:
    """Waits until no other service writes in `folder`, then holds it to the process's end (the system lets it go
    however the process ends, killed too). Whether there was anything to hold."""
    if fcntl is None or not folder.is_dir():
        return False
    f = open(folder / ".pisac", "a")  # closed by the system alone; not inherited by ffmpeg and the others started here
    began = time.monotonic()
    said = 0.0
    while True:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except BlockingIOError:
            now = time.monotonic()
            if not said or now - said >= said_every:
                log.warning("another service writes in %s: waiting for it to end (%.0f s)", folder, now - began)
                said = now
            time.sleep(0.5)
    _held.append(f)
    return True


def prepare(state_path: str | Path) -> None:
    """Before the service reads or writes what it keeps: the only writer, and the folder the page alone will write
    (a container's mount of it needs it there)."""
    folder = Path(state_path).parent
    if folder.is_dir():
        only_writer(folder)
        (folder / "mejl").mkdir(exist_ok=True)
