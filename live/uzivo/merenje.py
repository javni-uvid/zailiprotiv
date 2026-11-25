"""The measuring: the frames, the sound, the voices, the transcript, the steps, the model, the bell, and every write of
what the service keeps but what went by mail. In the same process as the page (main.py) or in its own, with no web
server (`ULOGA=merenje`, `python -m uzivo.merenje`; 25 Nov 2026). `python -m uzivo.merenje zdravo` is Docker's check."""
from __future__ import annotations

import logging
import signal
import sys
import threading
from pathlib import Path

from . import config, sada
from .state import Tracker

log = logging.getLogger("merenje")


def tracker() -> Tracker:
    """The tracker, once this is the only service that writes in its folder."""
    sada.prepare(config.STATE_PATH)  # before anything is read: the run before may still be writing
    t = Tracker(config.STATE_PATH)
    folder = Path(config.STATE_PATH).parent
    if config.KEEP_INPUTS and folder.is_dir():  # what it is told, kept to go through a day again
        from . import dnevnik
        dnevnik.attach(t, folder / "ulazi")
    return t


def start(t: Tracker, stop: threading.Event, bell) -> None:
    """Every thread of the measuring."""
    from . import hronika, prepis, sudija, worker
    threading.Thread(target=worker.run, args=(t, stop, bell), daemon=True).start()
    if Path(config.STATE_PATH).parent.is_dir():  # the moment, for the page's own process (citac.py)
        sada.Pulse(t, stop).start()
        from . import prenosi
        prenosi.Keeper(t, stop).start()  # where the day is on YouTube, for when the broadcast is over
    if prepis.on():
        prepis.Writer(t, stop).start()
        if config.WHISPER_URL and config.SHOW_CAPTIONS:  # the line under the picture, on the graphics card only
            prepis.Captions(t, stop).start()
        if config.VOICES:  # who speaks by the voice, while no caption names anyone (glas.py)
            from . import glas
            glas.Listener(t, stop).start()
    hronika.Watcher(t, stop).start()
    if sudija.on():  # the model tells the day's steps and sums the day up (sudija.py); no key, no calls
        sudija.Judge(t, stop, bell=bell).start()
        if config.SPEECH_LINES:  # a line on each speech when it ends (rezimei.py)
            from . import rezimei
            rezimei.Writer(t, stop).start()


def healthy() -> bool:
    """Whether the measuring beside this process is there and its loop turns (citac.Reader.alive, the page's own rule)."""
    from .citac import alive
    return alive(sada.read(config.STATE_PATH))


def main() -> int:
    if sys.argv[1:] == ["zdravo"]:
        return 0 if healthy() else 1
    from .obavesti import Bell
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    stop = threading.Event()
    for s in (signal.SIGTERM, signal.SIGINT):
        signal.signal(s, lambda *_: stop.set())
    start(tracker(), stop, Bell())
    stop.wait()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
