"""Who is at the rostrum by face and voice, where the broadcast shows no caption (20 Nov 2026, the maintainer's
decision: the recordings are public, MPs are public officials, and faces and voices may be used to tell who speaks).

Only the fallback: a day whose notes are published is read from the notes (govor.py), which replace this.

The numbers come from live/uzivo/lice_glas.py (a face's 128, a voice window's 512, each with its second in a file of
the archive). What they are matched to, for every speaker by the same rule:
- **voices** of the speakers whose turns are known (read from the caption on any day of the convocation, or placed
  by the notes): the mean of their windows inside those turns;
- **faces**: the MPs' portraits from the Assembly (data/photos/), and the faces seen during each known turn.
A stretch of sound gets a speaker when its windows' nearest voice is that speaker's, clearly nearer than the next
(MARGIN), over at least MIN_RUN seconds; a face seen then that is nearest another speaker's takes the place from
it, so a stretch where face and voice disagree gets nobody. Nobody is named from a guess below these bars.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

VOICE_MIN = 0.55   # cosine: a voice window this alike its speaker's mean at the least
MARGIN = 0.05      # and this far ahead of the next speaker's
FACE_MIN = 0.42    # SFace's cosine for "the same person"
MIN_RUN = 20.0     # seconds: a shorter stretch is a replica's start or noise, not a turn
# A stretch is named only when its windows are on average this alike its speaker's voice. Checked on 18 Nov 2026,
# each file left out of the samples in turn and compared with the captions: from 0.68 every stretch named was the
# speaker (11,313 s, 88 % of the time of speakers with a sample); at 0.65, 99 %; at 0.60, 93 %. A speaker with no
# sample is nearest someone else at 0.58-0.65 on 19 Nov, so below the bar.
STRETCH_MIN = 0.68
GAP = 8.0          # seconds of no window or another speaker's that do not end a stretch


def load(folder: Path, url: str, kind: str):
    path = folder / (url.rsplit("/", 1)[1].removesuffix(".mp4") + f".{kind}.npz")
    if not path.exists():
        return None
    d = np.load(path)
    return d["t"], d["feat"]


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
    out = {}
    for who, parts in acc.items():
        v = np.concatenate(parts).mean(0)
        out[who] = v / (np.linalg.norm(v) + 1e-9)
    return out


def faces(spans, folder_of, portraits: dict[str, np.ndarray]) -> dict[str, list[np.ndarray]]:
    """Each speaker's faces: the portrait, and the largest face of each frame inside a known turn when most such
    faces of the turn are alike (the camera on the speaker), their mean."""
    out = {k: [v] for k, v in portraits.items()}
    for who, url, a, b in spans:
        got = load(folder_of(url), url, "lica")
        if got is None:
            continue
        d = np.load(folder_of(url) / (url.rsplit("/", 1)[1].removesuffix(".mp4") + ".lica.npz"))
        t, box, f = d["t"], d["box"], d["feat"]
        m = (t >= a) & (t <= b)
        if m.sum() < 3:
            continue
        idx = np.where(m)[0]
        biggest = {}
        for i in idx:
            if t[i] not in biggest or box[i][2] * box[i][3] > box[biggest[t[i]]][2] * box[biggest[t[i]]][3]:
                biggest[t[i]] = i
        fs = f[list(biggest.values())]
        centre = fs.mean(0)
        centre /= np.linalg.norm(centre) + 1e-9
        alike = fs @ centre > FACE_MIN
        if alike.mean() >= 0.6:
            v = fs[alike].mean(0)
            out.setdefault(who, []).append(v / (np.linalg.norm(v) + 1e-9))
    return out


def stretches(t: np.ndarray, f: np.ndarray, refs: dict[str, np.ndarray]) -> list[tuple[str, float, float, float]]:
    """(speaker, from, to, mean likeness) of a file's sound: windows given to their nearest voice when clearly
    nearest, joined while the same speaker goes on (GAP), kept from MIN_RUN seconds."""
    if not refs or not len(t):
        return []
    names = list(refs)
    sims = f @ np.stack([refs[n] for n in names]).T
    order = np.argsort(-sims, axis=1)
    out, cur = [], None
    for i in range(len(t)):
        best, second = order[i, 0], order[i, 1] if len(names) > 1 else None
        s = sims[i, best]
        ok = s >= VOICE_MIN and (second is None or s - sims[i, second] >= MARGIN)
        who = names[best] if ok else None
        if cur and who == cur[0] and t[i] - cur[2] <= GAP:
            cur[2], cur[3] = t[i] + 3, cur[3] + [s]
        elif cur and who is None and t[i] - cur[2] <= GAP:
            continue
        else:
            if cur:
                out.append(cur)
            cur = [who, t[i], t[i] + 3, [s]] if who else None
    if cur:
        out.append(cur)
    return [(w, a, b, float(np.mean(s))) for w, a, b, s in out if b - a >= MIN_RUN and np.mean(s) >= STRETCH_MIN]


def check_faces(runs, lica, face_refs: dict[str, list[np.ndarray]]):
    """Each stretch with "lice": the speaker most faces in it are nearest to (above FACE_MIN), or None; a stretch
    whose faces are mostly another's is dropped."""
    if lica is None:
        return [(w, a, b, s, None) for w, a, b, s in runs]
    t, f = lica
    stacked = [(n, v) for n in face_refs for v in face_refs[n]]
    if not stacked:
        return [(w, a, b, s, None) for w, a, b, s in runs]
    M = np.stack([v for _, v in stacked])
    out = []
    for w, a, b, s in runs:
        m = (t >= a) & (t <= b)
        if not m.any():
            out.append((w, a, b, s, None))
            continue
        sims = f[m] @ M.T
        top = sims.argmax(1)
        votes: dict[str, int] = {}
        for i, j in enumerate(top):
            if sims[i, j] >= FACE_MIN:
                votes[stacked[j][0]] = votes.get(stacked[j][0], 0) + 1
        face = max(votes, key=votes.get) if votes else None
        if face and face != w and votes[face] > 2 * votes.get(w, 0):
            continue  # the picture shows someone else most of the time: nobody, rather than a guess
        out.append((w, a, b, s, face))
    return out
