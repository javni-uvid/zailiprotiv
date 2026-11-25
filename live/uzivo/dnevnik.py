"""What the tracker was told, kept as it came, so that a day can be gone through again by the rules as they are now
(24 Nov 2026, the maintainer: "uzmi najbolji pristup": a rule for who speaks is to be scored on a whole kept day before
it runs live, zailiprotiv tacnost; until now only a finished record could be scored, for nothing the rules decide
from was kept).

`attach` wraps the tracker's methods that take something in (a frame read, a floor given by the chair's words, a
voice, the broadcast's clock, a piece of the transcript, a step) and writes each call, with its second, as a line of
<folder>/<day>.jsonl before it runs. Nothing else in the service changes. Only on the service's own computer, never
served; days older than KEEP are removed. A line is appended, not the file written whole (state_base._write is for
files read back whole): a line torn by a stop is skipped when read.

    python -m uzivo.dnevnik <day> [<out.json>]

goes through the day's lines with a new tracker, the clock set to each line's second, and writes the record it comes
to (the service's shape: "turns", "cover"), to be scored (`zailiprotiv tacnost <day> --zapis <out.json>`). What it
cannot show: the voices and the chair's words were found beside the tracker as it then was (glas.py and prepis.py
ask it who has the floor), so a rule that would have made them find something else is not seen here."""
from __future__ import annotations

import json
import logging
import sys
import threading
import time
from pathlib import Path

from . import config
from .names import Person

log = logging.getLogger("dnevnik")
METHODS = ("observe", "heard", "clocked", "say", "note", "caption", "presides", "unheard", "voice_gone", "taken_back", "tick")
KEEP = 30  # days of lines kept


def _out(x):
    if isinstance(x, Person):
        return {"__p": [x.key, x.name, x.slug, x.group]}
    if isinstance(x, (set, frozenset)):
        return {"__s": sorted(_out(v) if isinstance(v, Person) else v for v in x) if all(isinstance(v, str) for v in x)
                else [_out(v) for v in x]}
    if isinstance(x, dict):
        return {str(k): _out(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_out(v) for v in x]
    return x if isinstance(x, (str, int, float, bool)) or x is None else str(x)


def _in(x):
    if isinstance(x, dict):
        if "__p" in x:
            return Person(*x["__p"])
        if "__s" in x:
            return {_in(v) for v in x["__s"]}
        return {k: _in(v) for k, v in x.items()}
    return [_in(v) for v in x] if isinstance(x, list) else x


def attach(tracker, folder: Path, clock=time.time) -> None:
    """From now on every call of the tracker's taking-in methods is a line of the day's file in `folder`."""
    folder.mkdir(parents=True, exist_ok=True)
    lock = threading.Lock()
    for old in sorted(folder.glob("*.jsonl"))[:-KEEP]:
        try:
            old.unlink()
        except OSError:
            pass

    def wrap(name: str, inner):
        def told(*args, **more):
            try:
                now = clock()
                line = json.dumps({"t": round(now, 2), "m": name, "a": _out(args), "k": _out(more)}, ensure_ascii=False)
                with lock, open(folder / f"{tracker._day(now)}.jsonl", "a", encoding="utf-8") as f:
                    f.write(line + "\n")
            except Exception:  # the line is for afterwards: never in the way of the call
                log.exception("a line not kept")
            return inner(*args, **more)
        return told

    for name in METHODS:
        if hasattr(tracker, name):
            setattr(tracker, name, wrap(name, getattr(tracker, name)))


def lines(f: Path) -> list[dict]:
    out = []
    for raw in f.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(raw))
        except ValueError:
            continue  # torn by a stop
    return out


class _Clock:
    """`time`, with `time()` the second of the line being gone through."""

    def __init__(self) -> None:
        self.now = 0.0

    def time(self) -> float:
        return self.now

    def __getattr__(self, name):
        return getattr(time, name)


def again(told: list[dict], tracker=None):
    """A tracker that has been told `told` over again, in order, each at its own second. A new one keeps nothing on
    disk; give one (with a list of MPs, say) to have it told instead."""
    from . import state, state_view
    from .state import Tracker
    tracker = tracker or Tracker(None, config.TZ)
    clock, kept = _Clock(), (state.time, state_view.time)
    state.time = state_view.time = clock
    try:
        for row in told:
            clock.now = float(row["t"])
            method = getattr(tracker, row["m"], None)
            if method:
                method(*_in(row["a"]), **_in(row["k"]))
    finally:
        state.time, state_view.time = kept
    return tracker


def main(args: list[str]) -> int:
    day = args[0]
    f = Path(config.STATE_PATH).parent / "ulazi" / f"{day}.jsonl"
    if not f.exists():
        print(f"{f}: no lines kept of that day")
        return 1
    told = lines(f)
    tracker = again(told)
    record = {"day": day, "turns": tracker.turns, "cover": tracker.cover}
    print(f"{day}: {len(told)} lines, {len(tracker.turns)} turns")
    if len(args) > 1:
        from .state_base import _write
        _write(Path(args[1]), record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
