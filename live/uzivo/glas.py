"""Who speaks, by the voice, while the broadcast shows no caption (22 Nov 2026, the maintainer: voices live, and the
time so found counted, labelled). The same model and rule as the recordings read afterwards (lice_glas.py, the site's
ko.py): 3D-Speaker's ERes2Net through sherpa-onnx gives a window of three seconds 512 numbers; a stretch of windows
nearest one MP's voice, clearly nearer than the next, for MIN_RUN seconds on average STRETCH_MIN alike, names them.

The samples: each MP's mean voice (`/data/glasovi.npz`: numbers only, no sound; first from 17-18 Nov, placed by the
notes) and, as the service runs, the windows of every turn the caption names, so an MP is known by voice once the
picture has named them once. The presiding officers (VOICE_SKIP) are never named by voice: they speak from the chair
far more than from the floor. Only the numbers are kept, on the maintainer's computer; nothing of this is published.
"""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

import numpy as np

from . import config, prepis

log = logging.getLogger("glas")
RATE = 16000
WIN, HOP = 3.0, 1.5  # seconds of sound in a window, and between windows (lice_glas)
# The rule of the recordings read afterwards (the site's ko.py, checked on 18 Nov 2026: from 0.68 every stretch named
# was the speaker): keep them the same.
VOICE_MIN, MARGIN, STRETCH_MIN, MIN_RUN, GAP = 0.55, 0.05, 0.68, 20.0, 8.0
KEEP = 600  # seconds of windows kept in memory
# A turn found by the chair's words, of someone whose voice is not known: its first seconds (3-15 s) are its voice, and
# a later 15 s on average less alike than CHANGE is someone else's. Set on 18 Nov 2026 against the notes: a speech's
# own later 15 s fall below 0.45 in 10% of cases (an interruption: the turn ends early, nobody is named), the next
# speaker's stay above in 4% (the turn goes on wrongly).
CHANGE, OWN_FROM, OWN_TO, CHANGE_SPAN = 0.45, 3.0, 15.0, 15.0
LEARN_ON = 40.0  # seconds after a caption that stands for seconds whose sound is taken as its speaker's voice
LEARN_EDGE = 5.0  # seconds at a turn's start and end not taken as its voice (the chair may still be speaking)


def stretches(t: np.ndarray, f: np.ndarray, refs: dict[str, np.ndarray]) -> list[tuple[str, float, float, float]]:
    """(speaker, from, to, mean likeness): windows given to their nearest voice when clearly nearest, joined while the
    same speaker goes on (GAP), kept from MIN_RUN seconds at STRETCH_MIN. The site's ko.stretches, the same rule."""
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


class Voices:
    """The MPs' mean voices, by their address on the site: kept as sums, so a new turn adds to them."""

    def __init__(self, path: Path | None) -> None:
        self.path, self.sums, self.n, self.changed = path, {}, {}, False
        if path and path.exists():
            d = np.load(path)
            for slug, v, c in zip(d["slugs"], d["vecs"], d["counts"]):
                self.sums[str(slug)], self.n[str(slug)] = v.astype(np.float64) * int(c), int(c)

    def refs(self) -> dict[str, np.ndarray]:
        return {s: (v / (np.linalg.norm(v) + 1e-9)).astype(np.float32) for s, v in self.sums.items()}

    def add(self, slug: str, f: np.ndarray) -> None:
        if not len(f):
            return
        self.sums[slug] = self.sums.get(slug, 0) + f.sum(0).astype(np.float64)
        self.n[slug] = self.n.get(slug, 0) + len(f)
        self.changed = True

    def save(self) -> None:
        if not self.path or not self.changed or not self.sums:
            return
        slugs = sorted(self.sums)
        tmp = self.path.with_suffix(".tmp.npz")
        np.savez_compressed(tmp, slugs=np.array(slugs), vecs=np.stack([self.sums[s] / self.n[s] for s in slugs]).astype(np.float32),
                            counts=np.array([self.n[s] for s in slugs]))
        tmp.replace(self.path)
        self.changed = False


class Listener(threading.Thread):
    """Reads the kept sound's segments as they come (prepis.keep's files, before the transcript takes them), and every
    few seconds: learns the voices of the turns the caption names, and tells the tracker who is speaking by voice when
    no caption names anyone (`Tracker.heard`), or that the voice of the one it had found is gone (`Tracker.unheard`)."""

    def __init__(self, tracker, stop: threading.Event, embed=None, path: Path | None = None) -> None:
        super().__init__(daemon=True)
        self.tracker, self.halt = tracker, stop
        self.embed = embed  # samples (float32) → 512 numbers; for tests; otherwise the model
        self.voices = Voices(path if path is not None else Path(config.VOICES_PATH))
        self.seen: set[str] = set()
        self.buf, self.buf_t = np.zeros(0, np.float32), 0.0  # sound not yet in a window, and when it begins
        self.t: list[float] = []
        self.f: list[np.ndarray] = []
        self.loud: list[float] = []
        self.learned: dict[str, float] = {}  # a caption turn's start → up to when its windows were learned
        self.saved = time.time()

    def _model(self):
        import sherpa_onnx
        ex = sherpa_onnx.SpeakerEmbeddingExtractor(sherpa_onnx.SpeakerEmbeddingExtractorConfig(
            model=config.VOICE_MODEL, num_threads=1))

        def embed(samples: np.ndarray) -> np.ndarray:
            s = ex.create_stream()
            s.accept_waveform(RATE, samples)
            s.input_finished()
            return np.array(ex.compute(s), np.float32)
        return embed

    def take(self) -> int:
        """The new segments' sound into windows; how many windows were made."""
        made = 0
        for start, length, f in prepis.waiting():
            if f.name in self.seen:
                continue
            self.seen.add(f.name)
            try:
                raw = np.frombuffer(f.read_bytes(), np.int16).astype(np.float32) / 32768
            except OSError:
                continue
            if not len(self.buf) or abs(start - (self.buf_t + len(self.buf) / RATE)) > 1.0:
                self.buf, self.buf_t = raw, start  # a gap: start afresh
            else:
                self.buf = np.concatenate([self.buf, raw])
            # the loudness of every tenth of a second, the last ten minutes: its quietest fifth is the hall's floor
            tenth = RATE // 10
            n = len(raw) // tenth
            if n:
                self.loud = (self.loud + list(np.sqrt((raw[:n * tenth].reshape(n, tenth) ** 2).mean(1))))[-6000:]
            floor = float(np.percentile(self.loud, 20)) if len(self.loud) >= 50 else 0.0
            w, h = int(WIN * RATE), int(HOP * RATE)
            while len(self.buf) >= w:
                piece = self.buf[:w]
                level = np.sqrt((piece[:30 * tenth].reshape(30, tenth) ** 2).mean(1))
                if (level > 4 * floor).mean() >= 0.5:  # as lice_glas: not mostly silence or the hall's noise
                    e = self.embed(piece)
                    self.t.append(self.buf_t)
                    self.f.append(e / (np.linalg.norm(e) + 1e-9))
                    made += 1
                self.buf, self.buf_t = self.buf[h:], self.buf_t + HOP
        if len(self.seen) > 2000:
            self.seen = {f.name for _, _, f in prepis.waiting()}
        while self.t and self.t[-1] - self.t[0] > KEEP:
            self.t.pop(0)
            self.f.pop(0)
        return made

    def learn(self, turns: list[dict]) -> None:
        """The windows inside the turns the caption named (not those found by voice or by the chair's words), and of a
        turn whose caption stood for seconds (24 Nov 2026), from when it stood to LEARN_ON seconds on, while the turn
        goes on: whoever it named is surely the speaker then, and an interruption comes later."""
        t = np.array(self.t)
        for d in turns:
            if not d.get("slug") or (d.get("izvor") and d["izvor"] != "potpis"):
                continue
            key = str(d["start"])
            a, b = max(d["start"] + LEARN_EDGE, self.learned.get(key, 0)), d["seen"] - LEARN_EDGE
            if d.get("izvor") == "potpis":
                a = max(d.get("natpis", d["start"]), self.learned.get(key, 0))
                b = min(d["seen"] - LEARN_EDGE, d.get("natpis", d["start"]) + LEARN_ON)
            if b <= a or not len(t):
                continue
            m = (t >= a) & (t + WIN <= b)
            if m.any():
                self.voices.add(d["slug"], np.stack([self.f[i] for i in np.flatnonzero(m)]))
            self.learned[key] = b

    def judge(self) -> None:
        """Who the newest stretch of voice is, told to the tracker."""
        if not self.t:
            return
        refs = self.voices.refs()
        runs = stretches(np.array(self.t), np.stack(self.f), refs)
        newest = self.t[-1] + WIN
        if not runs or newest - runs[-1][2] > GAP:  # nobody's voice goes on: one found by voice has stopped
            self.tracker.voice_gone((runs[-1][2] if runs else newest - GAP), newest, set(refs))
            return
        who, a, b, _ = runs[-1]
        roster = self.tracker.roster
        person = next((p for p in roster.people if p.slug == who), None) if roster else None
        cur = self.tracker.open_turn()
        if person and who in config.VOICE_SKIP and not (cur and cur.get("slug") == who):
            # a presiding officer's voice, not at the rostrum: the chair; it ends a turn found without a caption
            self.tracker.presides(person, a, b)
            self.tracker.unheard(a)
        elif person:
            self.tracker.heard(person, "glas", a, b, tracked=set(refs))
        else:
            self.tracker.unheard(a)

    def changed(self) -> None:
        """A turn found by the chair's words, of someone whose voice is not known: ended when its voice changes."""
        cur = self.tracker.open_turn()
        if not cur or cur.get("izvor") not in ("prepis", "potpis") or cur.get("po_glasu") or not self.t:
            return
        t = np.array(self.t)
        own = (t >= cur["start"] + OWN_FROM) & (t + WIN <= cur["start"] + OWN_TO)
        newest = t[-1]
        late = (t > newest - CHANGE_SPAN) & (t >= cur["start"] + OWN_TO)
        if own.sum() < 5 or late.sum() < 6:
            return
        f = np.stack(self.f)
        ref = f[own].mean(0)
        ref /= np.linalg.norm(ref) + 1e-9
        if float((f[late] @ ref).mean()) < CHANGE:
            # it ends after the last window still alike its first seconds, before the 15 s that were not
            after = np.flatnonzero((t >= cur["start"] + OWN_TO) & (t < t[late][0]) & (f @ ref >= CHANGE))
            self.tracker.unheard(float(t[after[-1]] + HOP) if len(after) else cur["start"] + OWN_TO)

    def step(self) -> None:
        self.take()
        snap_turns = self.tracker.turns_now()
        self.learn(snap_turns)
        if not self.tracker.caption_on():
            self.judge()
            self.changed()
        if time.time() - self.saved > 300:
            self.voices.save()
            self.saved = time.time()

    def run(self) -> None:
        if self.embed is None:
            try:
                self.embed = self._model()
            except Exception as exc:  # no package or no model: the service goes on without voices
                log.warning("voices off (%s)", exc)
                return
        log.info("voices on: %d MPs known by voice", len(self.voices.sums))
        while not self.halt.is_set():
            try:
                self.step()
            except Exception:
                log.exception("voices: a step failed")
            self.halt.wait(2.0)
        self.voices.save()
