"""The live service's own rule for who speaks, run again over a kept day and scored (25 Nov 2026; `tacnost`). Until then
only a finished record could be scored, so the service's rules (glas.py, state.py) were set on one to three examples.

    PYTHONUTF8=1 uv run --with numpy python tools/uzivo_ponovo.py <day>=<folder> [<day>=<folder> ...] [--deset]

Each folder holds a day's voices (.glas.npz, live/uzivo/lice_glas.py) and words (.jsonl, zvuk_dana.py) by file of the
archive. The service's `Tracker` and `Listener` are told, at the second each would have come: the captions of the
day's live record (data/15/uzivo), set beside the files' clock by the sound (ko.clock_shift); the voice's windows as they
would be made; and the words in pieces of PIECE seconds, LAG late, with the chair's floor-giving found in them as the
transcript's thread finds it. The voices known are those of the days given before that day (by the notes), as at the time.
`--deset`: every caption stands ten seconds only, as on 24 Nov 2026.

What it is not: the words are those written down from the recording afterwards, better than the live ones; the
pictures and the model's steps are not in it; a sitting's hall is as it was on the kept days. The replay of the rules of
24 Nov gave 18 Nov 88.9% and 308 s under a wrong name, the live record of that day 89.0% and 293 s. Nothing is written
but the scores; the notes' places are data/15/snimak."""
from __future__ import annotations

import json
import logging
import sys
import threading
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "src"), str(REPO / "live")]
from zailiprotiv import ko, tacnost, translit  # noqa: E402
from zailiprotiv.site import slug as site_slug  # noqa: E402
from uzivo import glas, hronika, state, state_base, state_view  # noqa: E402
from uzivo.names import Person, Roster, person_key  # noqa: E402

PIECE, LAG = 25.0, 12.0
CONV = REPO / "data" / "15"


class Clock:
    """`time` at the second gone through."""
    now = 0.0

    def time(self) -> float:
        return self.now

    def __getattr__(self, name):
        return getattr(time, name)


def people() -> list[Person]:
    out = []
    for m in json.loads((CONV / "members.json").read_text(encoding="utf-8"))["members"]:
        name = " ".join(w for w in translit.latin(m["name"]).split() if w.lower().rstrip(".") not in {"mr", "dr", "prof"}).title()
        out.append(Person(person_key(name), name, site_slug(name, 60), translit.latin(m.get("group") or "")))
    return out


def day_of(day: str, folder: Path) -> dict:
    truth = json.loads((CONV / "snimak" / f"{day}.json").read_text(encoding="utf-8"))
    files = []
    for f in truth["datoteke"]:
        got = ko.load(folder, f["url"], "glas")
        if got is None:
            continue
        p = folder / (f["url"].rsplit("/", 1)[1].removesuffix(".mp4") + ".jsonl")
        words = [w for x in p.read_text(encoding="utf-8").splitlines() if x.strip() for w in json.loads(x).get("reci") or []]
        files.append({"url": f["url"], "od": f["od"], "trajanje": f["trajanje"], "t": got[0], "f": got[1], "reci": words})
    live = json.loads((CONV / "uzivo" / f"{day}.json").read_text(encoding="utf-8"))["govori"]
    caps = [(t["adresa"], t["od"], t["do"]) for t in live if t.get("okvira", 0) >= 2 and t.get("adresa") and not t.get("izvor")]
    return {"truth": truth, "files": files, "caps": caps}


def run(day: str, d: dict, before: list[tuple[dict, Path]], folder: Path, sitting: list[Person], ten: bool) -> list[dict]:
    """The turns the service comes to, as it counts them."""
    clock, kept = Clock(), (state.time, state_view.time, glas.time)
    state.time = state_view.time = glas.time = clock
    try:
        t = state.Tracker(None, "Europe/Belgrade")
        t._day = lambda ts: day  # a sitting over midnight is one day here
        t.day = day
        t.roster = Roster(list(sitting))
        t.roster.current = frozenset(p.slug for p in sitting)
        by = {p.slug: p for p in sitting}
        L = glas.Listener(t, threading.Event(), embed=lambda s: None, path=Path("nema.npz"))
        for other, where in before:
            for who, url, a, b in ko.known_spans(other["truth"]):
                got = ko.load(where, url, "glas")
                if got is not None:
                    m = (got[0] >= a + 5) & (got[0] + 3 <= b - 5)
                    if m.any():
                        L.voices.add(who, got[1][m].astype(np.float64))
        shift = ko.clock_shift(d["caps"], d["files"])
        caps = [(w, a + shift, b + shift) for w, a, b in d["caps"]]
        for x in d["files"]:
            at, i, end = x["t"] + x["od"], 0, float(x["t"][-1]) + 3
            said = [(p0, " ".join(w for s, _, w in x["reci"] if p0 <= s < p0 + PIECE)) for p0 in np.arange(0, end, PIECE)]
            said = [s for s in said if s[1]]
            for now in np.arange(x["od"] + 1, x["od"] + end + 60, 1.0):
                clock.now = now
                t.tick()
                if int(now) % 5 == 0:
                    who = next((w for w, a, b in caps if a <= now < (min(b, a + 10) if ten else b)), None)
                    p = by.get(who) or (Person(person_key(who), who, who) if who else None)
                    if ten:
                        if who in by:  # such a caption counts only for a sitting MP (caption.sure)
                            t.heard(p, "potpis", now, now)
                        t.observe(None, "", now=now)
                    else:
                        t.observe(p, (p.group or "lista") if p else "", now=now)
                while said and x["od"] + said[0][0] + PIECE + LAG <= now:
                    p0, text = said.pop(0)
                    ts = x["od"] + p0
                    cur = t.open_turn()
                    chair = not any(q["start"] <= ts + PIECE / 2 <= q["seen"] + 1 for q in t.turns)
                    t.say(ts, text, chair=chair)
                    if chair or (cur and cur.get("izvor")):
                        for q in hronika.floor(text, sitting):
                            t.note(ts, "Reč ima", q.name, "prepis", q.slug)
                        given = hronika.floor(text, sitting, now_only=True)
                        if given:
                            t.heard(given[-1], "prepis", ts + PIECE, ts + PIECE)
                if int(now) % 3 == 0:
                    while i < len(at) and at[i] + 3 <= now - 4:
                        L.t.append(float(at[i]))
                        L.f.append(x["f"][i])
                        i += 1
                    while L.t and L.t[-1] - L.t[0] > glas.KEEP:
                        L.t.pop(0)
                        L.f.pop(0)
                    L.learn(t.turns_now())
                    if not t.caption_on():
                        L.judge()
                        L.changed()
        return [q for q in t.turns if state_base.counted(q)]
    finally:
        state.time, state_view.time, glas.time = kept


def main(args: list[str]) -> int:
    logging.disable(logging.CRITICAL)
    ten = "--deset" in args
    days = [(a.split("=", 1)[0], Path(a.split("=", 1)[1]).expanduser()) for a in args if "=" in a]
    if not days:
        print(__doc__)
        return 2
    sitting, read = people(), {d: day_of(d, f) for d, f in days}
    for n, (day, folder) in enumerate(days):
        d = read[day]
        before = [(read[e], f) for e, f in days[:n]]
        turns = run(day, d, before, folder, sitting, ten)
        record = {"cover": [[f["od"], f["od"] + f["trajanje"]] for f in d["files"]], "turns": turns}
        print(tacnost.told(day, tacnost.score(d["truth"], record)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
