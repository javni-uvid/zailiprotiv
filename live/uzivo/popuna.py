"""The day's turns filled from the transcript, by one rule for every speaker: where the chair gave the floor by name and
the record has no turn of theirs, or less than MISSING of one, the turn runs from the chair's words to
the next floor given or the next turn of another. For what the service did not see when it ran (24 Nov 2026: a caption
not read, a voice that ended a turn at once); run by hand, with the service stopped, and the file kept beside as it was.

    python -m uzivo.popuna 2026-11-24 [--pisi]"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from . import hronika
from .state_base import SURE_FRAMES, _write, write_text

MISSING = 0.4  # a turn is missing when less than this share of it is there: the chair's own words before the next floor
SHORT_OF = 45  # and at least these seconds of a turn that is there, for it to be lengthened
NEW = 25  # seconds a turn not there must come to, to be written
LONGEST = 1500  # no turn longer than this comes of the chair's words alone


def floors(said: dict[str, str], people: list) -> list[tuple[float, float, object]]:
    """(when the chair's piece began, when it ended, whom the chair gave the floor)."""
    keys = sorted((int(k.lstrip("p")), k) for k in said if k.lstrip("p").isdigit())
    out = []
    for i, (at, key) in enumerate(keys):
        given = hronika.floor(said[key], people, now_only=True)
        if given:
            end = min(keys[i + 1][0], at + 30) if i + 1 < len(keys) else at + 20
            out.append((float(at), float(end), given[-1]))
    return out


def fill(turns: list[dict], said: dict[str, str], people: list) -> tuple[list[dict], list[str]]:
    """The turns with what is missing, oldest first, and what was done, a line each."""
    given = floors(said, people)
    out = [dict(t) for t in turns if not (t.get("izvor") and t["seen"] - t["start"] < 1)]
    done: list[str] = []
    for i, (began, t0, who) in enumerate(given):
        nxt = given[i + 1][0] if i + 1 < len(given) else None
        others = [t["start"] for t in out if t["start"] > t0 and t["key"] != who.key]
        end = min([x for x in (nxt, min(others, default=None)) if x is not None], default=None)
        if end is None or not 0 < end - t0 <= LONGEST:
            continue
        mine = [t for t in out if t["key"] == who.key and t["start"] <= end and t["seen"] >= began - 5]
        have = sum(max(0.0, min(t["seen"], end) - max(t["start"], t0)) for t in mine)
        gap = end - t0
        if have > MISSING * gap or gap - have < (SHORT_OF if mine else NEW):
            continue
        if mine:
            first = min(mine, key=lambda t: t["start"])
            first["start"], first["seen"] = min(first["start"], t0), max(end, max(t["seen"] for t in mine))
            out = [t for t in out if t is first or t not in mine]
        else:
            out.append({"key": who.key, "name": who.name, "slug": who.slug, "group": who.group, "role": "", "start": t0,
                        "seen": end, "n": SURE_FRAMES, "izvor": "prepis", "video": "", "sq_start": None, "sq_seen": None,
                        "seg": None})
        done.append(f"{who.name}: {int(have)} s -> {int(gap)} s")
    out.sort(key=lambda t: t["start"])
    return out, done


def main(args: list[str]) -> int:
    from . import config
    from .names import Roster
    day, base = args[0], Path(config.STATE_PATH).parent
    f = base / "dani" / f"{day}.json"
    data = json.loads(f.read_text(encoding="utf-8"))
    said = json.loads((base / "prepis" / f"{day}.json").read_text(encoding="utf-8"))
    roster = Roster.from_json((base / "podaci.json").read_text(encoding="utf-8"))
    current = set(json.loads((base / "poslanici.json").read_text(encoding="utf-8")))
    turns, done = fill(data["turns"], said, [p for p in roster.people if p.slug in current])
    print(len(data["turns"]), "->", len(turns))
    print("\n".join(done))
    if "--pisi" in args and done:
        kept = f.with_suffix(".pre-popune.json")
        if not kept.exists():
            write_text(kept, f.read_text(encoding="utf-8"))
        _write(f, {**data, "turns": turns})
        print("upisano")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
