"""The sound of a sitting cut where the voice changes, and each piece's one speaker named by the best sign there is of
them (25 Nov 2026, the maintainer: "izaberi najtačniji metod"). One rule for every speaker, and one place for it: the
recordings read afterwards (the site's ko.py) use it from here. Only numpy.

A window of three seconds (glas.WIN) says little of whose voice it is; a whole piece of one voice says it well: of
pieces of 60 s or more on 17-19 Nov 2026 a speaker's own was 0.94 alike their sample from other days (half of them;
one in twenty under 0.71), and no MP without a sample was over 0.80 alike another's. The signs, the strongest first:
a caption seen in the piece, the chair's words just before it, the voice. A caption or the chair's words are not taken
where the voice says otherwise (`against`), which is what keeps a misread caption and a misheard name from a speech."""
from __future__ import annotations

import numpy as np

WIN = 3.0  # seconds in a window (glas.WIN)
# A window's voice and a stretch of windows (stretches): checked on 18 Nov 2026, each file left out of the samples in turn and
# compared with the captions: from 0.68 every stretch named was the speaker (11,313 s, 88 % of the time of speakers with
# a sample); at 0.65, 99 %; at 0.60, 93 %. A speaker with no sample is nearest someone else at 0.58-0.65 on 19 Nov.
VOICE_MIN, MARGIN, STRETCH_MIN = 0.55, 0.05, 0.68
MIN_RUN = 20.0  # seconds: a shorter stretch is a replica's start or noise, not a turn
GAP = 8.0  # seconds of no window or another speaker's that do not end a stretch
# A piece, and whose it is
SIDE, STEP = 20.0, 3.0  # seconds of sound compared on each side of a place, and between the places tried
CUT = 0.65  # two sides less alike than this, the least of the places near: the voice changed there
NEAR = 4  # places (some 12 s) on each side among which a cut is the least alike
SILENCE = 30.0  # seconds with no voice: the piece ends there (a break, a vote)
SHORT = 12.0  # seconds: a shorter piece is nobody's (an interjection, the chair's two words)
LIKE, CLEAR = 0.80, 0.10  # a piece is a known voice's when this alike it and this far ahead of the next
UNLIKE = 0.60  # a piece less alike the named MP's known voice than this is not theirs ...
SURE = 30.0  # ... when it is at least this long: a shorter one is too little of a voice to say so
LEARN = 60.0  # a piece a caption or the chair's words named is a sample of that MP's voice from this long on


def unit(x: np.ndarray) -> np.ndarray:
    return x / (np.linalg.norm(x) + 1e-9)


def pieces(t: np.ndarray, f: np.ndarray) -> list[tuple[float, float]]:
    """(from, to): the sound cut where the voice changes and where no voice is heard for SILENCE."""
    out: list[tuple[float, float]] = []
    if not len(t):
        return out
    t = np.asarray(t, np.float64)
    breaks = np.flatnonzero(np.diff(t) > SILENCE + WIN) + 1
    for part in np.split(np.arange(len(t)), breaks):
        tt, ff = t[part], f[part]
        at = np.arange(tt[0] + SIDE, tt[-1] - SIDE, STEP)
        like = []
        for x in at:
            a, b = ff[(tt >= x - SIDE) & (tt < x)], ff[(tt >= x) & (tt < x + SIDE)]
            like.append(float(unit(a.mean(0)) @ unit(b.mean(0))) if len(a) >= 3 and len(b) >= 3 else 1.0)
        like = np.array(like)
        cuts = [float(at[i]) for i in range(1, len(at) - 1)
                if like[i] < CUT and like[i] <= like[max(0, i - NEAR):i + NEAR + 1].min()]
        edges = [float(tt[0])] + cuts + [float(tt[-1]) + WIN]
        out += list(zip(edges, edges[1:]))
    return out


def voice(t: np.ndarray, f: np.ndarray, a: float, b: float) -> np.ndarray | None:
    """The voice of a piece: the mean of its windows, or None of too few."""
    m = (t >= a) & (t < b)
    return unit(f[m].mean(0)) if m.sum() >= 3 else None


def alike(v: np.ndarray, refs: dict[str, np.ndarray]) -> dict[str, float]:
    return {k: float(v @ r) for k, r in refs.items()}


def whose(sims: dict[str, float]) -> str:
    """Whose known voice a piece is: LIKE alike at the least and CLEAR ahead of the next; nobody's otherwise."""
    order = sorted(sims.items(), key=lambda x: -x[1])
    if not order or order[0][1] < LIKE or (len(order) > 1 and order[0][1] - order[1][1] < CLEAR):
        return ""
    return order[0][0]


def against(who: str, sims: dict[str, float], seconds: float) -> bool:
    """Whether the voice says a piece a caption or the chair's words give `who` is not theirs: it is surely another's
    known voice, or, in a piece long enough to tell, unlike the known voice of `who`."""
    other = whose(sims)
    return bool(other and other != who) or (who in sims and sims[who] < UNLIKE and seconds >= SURE)


def stretches(t: np.ndarray, f: np.ndarray, refs: dict[str, np.ndarray]) -> list[tuple[str, float, float, float]]:
    """(speaker, from, to, mean likeness): windows given to their nearest voice when clearly nearest, joined while the
    same speaker goes on (GAP), kept from MIN_RUN seconds at STRETCH_MIN."""
    if not refs or not len(t):
        return []
    names = list(refs)
    sims = f @ np.stack([refs[n] for n in names]).T
    order = np.argsort(-sims, axis=1)
    out, cur = [], None
    for i in range(len(t)):
        best, second = order[i, 0], order[i, 1] if len(names) > 1 else None
        s = sims[i, best]
        who = names[best] if s >= VOICE_MIN and (second is None or s - sims[i, second] >= MARGIN) else None
        if cur and who == cur[0] and t[i] - cur[2] <= GAP:
            cur[2], cur[3] = t[i] + WIN, cur[3] + [s]
        elif cur and who is None and t[i] - cur[2] <= GAP:
            continue
        else:
            if cur:
                out.append(cur)
            cur = [who, t[i], t[i] + WIN, [s]] if who else None
    if cur:
        out.append(cur)
    return [(w, a, b, float(np.mean(s))) for w, a, b, s in out if b - a >= MIN_RUN and np.mean(s) >= STRETCH_MIN]
