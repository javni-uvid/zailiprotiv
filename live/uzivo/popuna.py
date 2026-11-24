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
from .state_base import BREAK, CHAIRS, REJOIN, REJOIN_WORDS, SURE_FRAMES, _write, write_text

MISSING = 0.4  # a turn is missing when less than this share of it is there: the chair's own words before the next floor
SHORT_OF = 45  # and at least these seconds of a turn that is there, for it to be lengthened
NEW = 25  # seconds a turn not there must come to, to be written
AT_SEAM, ALIKE, UNNAMED = 5, 60, 90  # seconds: see `_alike`
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


def _alike(a: dict, v: dict, said: dict[str, str]) -> bool:
    """Whether turn `v`, found by voice alone right at the end of another's turn `a`, is `a` going on, a voice merely alike
    (24 Nov 2026, 17:26: 24 s of Nikola Selaković's under Miroslav Petrašinović's name): short, no word of the chair's at the
    seam, and nobody having named its speaker in the minute and a half before. Words alone do not tell: of the 14
    such turns of that day the other 13 were real, and one of them had no word of the chair's at the seam."""
    if (v.get("izvor") != "glas" or v.get("natpis") or a["key"] == v["key"] or a.get("izvor") not in ("prepis", "potpis")
            or a.get("po_glasu") or not -1 <= v["start"] - a["seen"] <= AT_SEAM or v["seen"] - v["start"] > ALIKE):
        return False
    near = [(int(k.lstrip("p")), k, t) for k, t in said.items() if k.lstrip("p").isdigit()]
    if any(a["seen"] - 35 <= at <= v["start"] + 8 and (k[0] == "p" or CHAIRS.search(t)) for at, k, t in near):
        return False
    spoken = [t for at, k, t in near if a["seen"] - 35 <= at <= v["start"] + 8]
    return bool(spoken) and not any(hronika.named(t, v["name"]) for at, k, t in near if a["seen"] - UNNAMED <= at <= v["start"] + 10)


def fill(turns: list[dict], said: dict[str, str], people: list) -> tuple[list[dict], list[str]]:
    """The turns with what is missing, oldest first, and what was done, a line each."""
    given = floors(said, people)
    out = [dict(t) for t in turns if not (t.get("izvor") and t["seen"] - t["start"] < 1)]
    done: list[str] = []
    breaks = sorted(int(k.lstrip("p")) for k, v in said.items() if k.lstrip("p").isdigit() and BREAK.search(v))
    for t in out:  # no turn found without a caption goes over a break the chair declared
        at = next((b for b in breaks if t["start"] <= b < t["seen"] - 1), None)
        if t.get("izvor") and at is not None:
            done.append(f'{t["name"]}: kraj {t["seen"] - at:.0f} s ranije, pauza')
            t["seen"] = float(max(t["start"], at))
    for a, v in zip(out[:-1], out[1:]):
        if _alike(a, v, said):
            done.append(f'{v["name"]}: {v["seen"] - v["start"]:.0f} s po sličnom glasu -> {a["name"]}')
            a["seen"], v["start"] = v["seen"], v["seen"] - 0.5  # of no length: dropped below
    out = [t for t in out if not (t.get("izvor") and t["seen"] - t["start"] < 1)]
    for i, (began, t0, who) in enumerate(given):
        nxt = given[i + 1][0] if i + 1 < len(given) else None
        others = [t["start"] for t in out if t["start"] > t0 and t["key"] != who.key]
        end = min([x for x in (nxt, min(others, default=None)) if x is not None], default=None)
        # the chair named whoever comes next before they began: the floor passed on there ("Reč ima doktor Milica Jovanović …
        # Narodna poslanica, Ana Brnabić", 24 Nov 2026)
        follows = min((t for t in out if t["start"] > t0 and t["key"] != who.key), key=lambda t: t["start"], default=None)
        if end is not None and follows is not None:
            for k, v in said.items():
                at = int(k.lstrip("p")) if k.lstrip("p").isdigit() else 0
                if began < at < end and hronika.named(v, follows["name"]):
                    end = min(end, at)
        pause = next((b for b in breaks if b >= began), None)
        if end is not None and pause is not None:
            end = min(end, pause)
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
    kept: list[dict] = []  # the same speaker, speech going on between and no floor to another: one turn (as Tracker._went_on)
    for t in out:
        a = kept[-1] if kept else None
        gap = t["start"] - a["seen"] if a else 0
        if a and a["key"] == t["key"] and a.get("izvor") and 8 <= gap <= REJOIN:
            between = [v for k, v in said.items() if k.lstrip("p").isdigit() and a["seen"] - 5 <= int(k.lstrip("p")) < t["start"]]
            if sum(len(v.split()) for v in between) >= REJOIN_WORDS * gap and not any(CHAIRS.search(v) for v in between) and not any(a["seen"] - 5 < f[0] < t["start"] and f[2].key != t["key"] for f in given):
                done.append(f'{t["name"]}: dva dela u jedan, {gap:.0f} s izmedju')
                a["seen"] = max(a["seen"], t["seen"])
                continue
        kept.append(t)
    out = kept
    for a, b in zip(out, out[1:]):  # no turn runs into the next
        if a["seen"] > b["start"] and a["key"] != b["key"]:
            done.append(f'{a["name"]}: kraj {a["seen"] - b["start"]:.0f} s ranije')
            a["seen"] = max(a["start"], b["start"])
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
    if "--reci" in args:  # words a restart of the service missed, as Whisper wrote them from the broadcast: a piece
        at, text = args[args.index("--reci") + 1:args.index("--reci") + 3]
        key = "p" + str(int(at))
        print("reci:", key, text)
        if "--pisi" in args:
            _write(base / "prepis" / f"{day}.json", {**said, key: text})
    print(len(data["turns"]), "->", len(turns))
    print("\n".join(done))
    if "--pisi" in args and done:
        kept = base / f"dan-{day}-pre-popune.json"  # not in dani/, where each file is a day
        if not kept.exists():
            write_text(kept, f.read_text(encoding="utf-8"))
        _write(f, {**data, "turns": turns})
        print("upisano")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
