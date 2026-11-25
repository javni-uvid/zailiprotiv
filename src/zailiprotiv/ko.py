"""Who is at the rostrum when, read from a day's recording while the day has no notes yet (20 Nov 2026, the maintainer's
decision: the recordings are public, MPs are public officials, and voices may be used to tell who speaks).

Only the fallback: a day whose notes are published is read from the notes (govor.py), which replace this.

The numbers come from live/uzivo/lice_glas.py (a voice window's 512, with its second in a file of the archive), the
words from live/uzivo/zvuk_dana.py. The sound is cut where the voice changes and each piece named by the best sign of
it (live/uzivo/komadi.py, the rule and its bars): the caption the live service read then; the chair giving the floor by
name just before it; a voice known from the turns of other days (placed by the notes or the caption), or from a piece of
this day a caption or the chair's words named. A caption or a name heard is not taken where the voice says otherwise,
and a piece no sign is clear of is nobody's. Nobody is named from a face: until 25 Nov 2026 a face seen mostly another's
dropped a voice's stretch (check_faces), and on 19 Nov that was 1184 right seconds of 1242.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

LIVE = Path(__file__).resolve().parents[2] / "live"  # the rule is the live service's own, as arhiva.py's reading is
if str(LIVE) not in sys.path:
    sys.path.insert(0, str(LIVE))
from uzivo.komadi import LEARN, SHORT, WIN, against, alike, pieces, stretches, unit, voice, whose  # noqa: E402, F401

BEFORE, AFTER = 45.0, 12.0  # seconds before a piece's start and after it, in which the chair's words give it its speaker
SEEN = 4.0  # seconds of a caption inside a piece, at the least, for it to be a sign
SHIFTS, SHIFT_TURNS, SHIFT_GAIN = range(-60, 61, 2), 5, 0.01  # see `clock_shift`


def load(folder: Path, url: str, kind: str):
    path = folder / (url.rsplit("/", 1)[1].removesuffix(".mp4") + f".{kind}.npz")
    if not path.exists():
        return None
    d = np.load(path)
    return d["t"].astype(np.float64), d["feat"]  # kept as float32, which an epoch added to makes 128 s coarse


def known_spans(day: dict) -> list[tuple[str, str, float, float]]:
    """(speaker's address, file, from, to) in seconds of the file, for a day's turns that have a place in a file."""
    out = []
    for t in day.get("govori", []):
        if t.get("datoteka") and t.get("adresa") and t.get("snimak") is not None and t.get("okvira", 0) >= 2:
            a = t["snimak"] + 5
            out.append((t["adresa"], t["datoteka"], a, a + (t["do"] - t["od"])))
    return out


def voices(spans, folder_of) -> dict[str, np.ndarray]:
    """Each speaker's voice: the mean of the windows inside their known turns (the first 5 s and last 5 s left out,
    where the chair may still be speaking)."""
    acc: dict[str, list] = {}
    for who, url, a, b in spans:
        got = load(folder_of(url), url, "glas")
        if got is None:
            continue
        t, f = got
        m = (t >= a + 5) & (t + 3 <= b - 5)
        if m.any():
            acc.setdefault(who, []).append(f[m])
    return {who: unit(np.concatenate(parts).mean(0)) for who, parts in acc.items()}


def clock_shift(captions, files) -> int:
    """How many seconds the captions' clock is off the files' (a file placed by hand, 19 Nov 2026: 36 s): the shift at
    which each caption's turn is most one voice. 0 unless SHIFT_TURNS turns of 20 s say so, by SHIFT_GAIN."""
    long = [(a, b) for _, a, b in captions if b - a >= 20]
    if len(long) < SHIFT_TURNS:
        return 0
    got = {}
    for s in SHIFTS:
        whole, n = 0.0, 0
        for a, b in long:
            for x in files:
                t = x["t"] + x["od"]
                m = (t >= a + s) & (t + WIN <= b + s)
                if m.sum() >= 3:
                    whole, n = whole + float(np.linalg.norm(x["f"][m].sum(0))), n + int(m.sum())
        got[s] = whole / max(n, 1)
    best = max(got, key=lambda s: (got[s], -abs(s)))
    return best if got[best] - got[0] >= SHIFT_GAIN else 0


def named(files: list[dict], refs: dict, captions, floor, skip=frozenset()) -> list[dict]:
    """A day's pieces with a speaker, in order: {"adresa", "datoteka", "od", "do" (seconds in the file), "po" (what named
    it: "potpis", "prepis", "glas")}. files: [{"url", "od" (its start on the clock), "t", "f" (the voice's windows)}];
    captions: [(address, from, to)] on the clock; floor(url, from, to) → the address the chair's words there give the
    floor to, or ""; skip: never named by voice (the presiding officers)."""
    shift, learned, out = clock_shift(captions, files), {}, []
    for x in files:
        t, f = x["t"], x["f"]
        for a, b in pieces(t, f):
            v = voice(t, f, a, b)
            if b - a < SHORT or v is None:
                continue
            known = {k: unit(np.mean(learned.get(k, []) + ([refs[k]] if k in refs else []), axis=0)) for k in {*refs, *learned}}
            sims = alike(v, known)
            seen: dict[str, float] = {}
            for who, c, d in captions:
                both = min(d + shift - x["od"], b) - max(c + shift - x["od"], a)
                if both >= 0:
                    seen[who] = seen.get(who, 0) + both
            who, how = next((k for k in sorted(seen, key=lambda k: -seen[k])
                             if seen[k] >= SEEN and not against(k, sims, b - a)), ""), "potpis"
            if not who:
                who, how = floor(x["url"], a - BEFORE, a + AFTER), "prepis"
                if who and against(who, sims, b - a):
                    who = ""
            if who and b - a >= LEARN:
                learned.setdefault(who, []).append(v)
            if not who:
                who, how = whose(sims), "glas"
                if who in skip:
                    who = ""
            if who:
                out.append({"adresa": who, "datoteka": x["url"], "od": a, "do": b, "po": how})
    return out
