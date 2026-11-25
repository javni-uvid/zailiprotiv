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
from .komadi import (GAP, LEARN, MARGIN, MIN_RUN, STRETCH_MIN, SURE, VOICE_MIN, against, alike, pieces,  # noqa: F401
                     stretches, unit, voice)  # the one rule, the recordings' too

log = logging.getLogger("glas")
RATE = 16000
WIN, HOP = 3.0, 1.5  # seconds of sound in a window, and between windows (lice_glas)
KEEP = 600  # seconds of windows kept in memory
# A turn found by the chair's words or a caption of seconds (25 Nov 2026, scored on 17-19 Nov against the notes through
# the service's own code): its own voice from OWN_FROM on.
OWN_FROM = 3.0
# It ends where its sound is cut (komadi.pieces) into two pieces less alike than APART, from OWN_TO on. Until 25 Nov its
# first 12 s against a later 15 s (0.45) told: on 17 Nov that ended a speech of 97 minutes at its 20th second.
OWN_TO, APART = 15.0, 0.5
# It is taken back when the voice of its first FIRST seconds is against it (komadi.against): a name misheard or a caption misread.
FIRST = 60.0
# A turn the chair's words gave, LEARN seconds on and its halves this alike, is that MP's voice for the rest of the day.
HALVES = 0.65
# Another's voice heard in a turn whose own voice is not known: taken only when it is liker that voice than the turn's
# sound before it was, by this much; a speaker merely alike another is as alike all along. On 17-19 Nov 2026: no change
# of 83 refused, the one false change (0.04) refused.
JUMP = 0.12
AGAIN = 4  # windows (some 8 s) in a row that tell the speaker of a held turn goes on
LEARN_ON = 40.0  # seconds after a caption that stands for seconds whose sound is taken as its speaker's voice
LEAST = 20  # windows a voice is known from before it names anyone or ends a turn: a few are only those seconds' own sound
LEARN_EDGE = 5.0  # seconds at a turn's start and end not taken as its voice (the chair may still be speaking)


class Voices:
    """The MPs' mean voices, by their address on the site: kept as sums, so a new turn adds to them."""

    def __init__(self, path: Path | None) -> None:
        self.path, self.sums, self.n, self.changed = path, {}, {}, False
        if path and path.exists():
            d = np.load(path)
            for slug, v, c in zip(d["slugs"], d["vecs"], d["counts"]):
                self.sums[str(slug)], self.n[str(slug)] = v.astype(np.float64) * int(c), int(c)

    def refs(self) -> dict[str, np.ndarray]:
        """The voices known well enough to be used (LEAST): of one known from fewer, the turn goes on as of a voice not known."""
        return {s: (v / (np.linalg.norm(v) + 1e-9)).astype(np.float32) for s, v in self.sums.items() if self.n[s] >= LEAST}

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
        self.today: dict[str, dict[float, np.ndarray]] = {}  # an MP's voice of the day, from turns the chair's words gave
        self.today_of = ""  # the day they are of
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

    def refs(self) -> dict[str, np.ndarray]:
        """The voices known: those kept, and the day's own, from the turns the chair's words gave. Not the day's own of
        whoever has the floor by such a turn: a turn is not judged by the voice it was itself learnt from."""
        out = self.voices.refs()
        cur = self.tracker.open_turn()
        own = cur["slug"] if cur and cur.get("izvor") in ("prepis", "potpis") and not cur.get("po_glasu") else None
        for slug, turns in self.today.items():
            if slug not in out and slug != own and sum(len(w) for w in turns.values()) >= LEAST:
                out[slug] = unit(np.concatenate(list(turns.values())).mean(0)).astype(np.float32)
        return out

    def judge(self) -> None:
        """Who the newest stretch of voice is, told to the tracker."""
        if not self.t:
            return
        refs = self.refs()
        runs = stretches(np.array(self.t), np.stack(self.f), refs)
        newest = self.t[-1] + WIN
        if not runs or newest - runs[-1][2] > GAP:  # nobody's voice goes on: one found by voice has stopped
            again = self.again(refs)
            if again:  # after applause the speaker is known in a few seconds, not in MIN_RUN
                self.tracker.heard(again[0], "glas", again[1], newest, tracked=set(refs))
                return
            self.tracker.voice_gone((runs[-1][2] if runs else newest - GAP), newest, set(refs))
            return
        who, a, b, _ = runs[-1]
        roster = self.tracker.roster
        person = next((p for p in roster.people if p.slug == who), None) if roster else None
        cur = self.tracker.open_turn()
        if cur and cur.get("slug") != who and not self._another(cur, refs[who], a, b):
            return
        if person and who in config.VOICE_SKIP and not (cur and cur.get("slug") == who):
            # a presiding officer's voice, not at the rostrum: the chair; it ends a turn found without a caption
            self.tracker.presides(person, a, b)
            self.tracker.unheard(a)
        elif person:
            self.tracker.heard(person, "glas", a, b, tracked=set(refs))
        else:
            self.tracker.unheard(a)

    def _another(self, cur: dict, ref: np.ndarray, a: float, b: float) -> bool:
        """Whether the voice `ref` heard from `a` to `b` is another than the open turn's: see JUMP. Of a turn whose voice
        is known, or with too little heard before `a`, it is."""
        if cur.get("izvor") not in ("prepis", "potpis") or cur.get("po_glasu"):
            return True
        t = np.array(self.t)
        own, new = (t >= cur["start"] + OWN_FROM) & (t + WIN <= a), (t >= a) & (t + WIN <= b)
        if own.sum() < 5 or not new.any():
            return True
        f = np.stack(self.f)
        return float((f[new] @ ref).mean() - (f[own] @ ref).mean()) >= JUMP

    def again(self, refs: dict) -> tuple | None:
        """(the MP of the turn on, since when): their voice again after a silence of it, in AGAIN windows in a row nearest to
        theirs and at least VOICE_MIN alike. Only for the one whose turn is still held: anyone else needs MIN_RUN."""
        cur = self.tracker.open_turn()
        if not cur or not cur.get("po_glasu") or cur.get("slug") not in refs or len(self.t) < AGAIN:
            return None
        names = list(refs)
        sims = np.stack(self.f[-AGAIN:]) @ np.stack([refs[n] for n in names]).T
        mine = names.index(cur["slug"])
        if not all(int(np.argmax(row)) == mine and row[mine] >= VOICE_MIN for row in sims):
            return None
        roster = self.tracker.roster
        person = next((p for p in roster.people if p.slug == cur["slug"]), None) if roster else None
        return (person, self.t[-AGAIN]) if person and self.t[-AGAIN] > cur["seen"] else None

    def changed(self) -> None:
        """A turn found by the chair's words or a caption of seconds, whose speaker's voice has not been recognised: taken
        back when the voice says it is not theirs, ended where the voice changes, and its voice learnt for the day."""
        cur = self.tracker.open_turn()
        if not cur or cur.get("izvor") not in ("prepis", "potpis") or cur.get("po_glasu") or not self.t:
            return
        t, f = np.array(self.t), np.stack(self.f)
        a = cur["start"] + OWN_FROM
        heard = t[-1] + WIN - a
        first = (t >= a) & (t + WIN <= a + FIRST)
        if SURE <= heard <= FIRST + 30 and first.sum() >= 8 and cur.get("slug"):
            v = unit(f[first].mean(0))
            if against(cur["slug"], alike(v, self.refs()), min(heard, FIRST)):
                log.info("turn of %s taken back: its voice is against it", cur["slug"])
                self.tracker.taken_back(cur["start"])
                return
        self._teach(cur, t, f)
        mine = t >= a
        if mine.sum() < 20:
            return
        t, f = t[mine], f[mine]
        cuts = pieces(t, f)
        for before, after in zip(cuts, cuts[1:]):
            if after[0] - cur["start"] < OWN_TO:
                continue
            one, two = voice(t, f, *before), voice(t, f, after[0], min(after[1], after[0] + 40))
            if one is not None and two is not None and float(one @ two) < APART:
                self.tracker.unheard(float(before[1]))
                return

    def _teach(self, cur: dict, t: np.ndarray, f: np.ndarray) -> None:
        """The voice of a turn the chair's words gave, for the rest of the day (kept only in memory), of an MP not known by
        voice and never of a presiding officer: up to its first cut, LEARN seconds on, one voice, and not surely another's."""
        slug, day = cur.get("slug"), self.tracker.day
        if day != self.today_of:
            self.today, self.today_of = {}, day
        known = self.voices.refs()
        if cur.get("izvor") != "prepis" or not slug or slug in known or slug in config.VOICE_SKIP:
            return
        a = cur["start"] + OWN_FROM
        mine = (t >= a) & (t + WIN <= cur["seen"] - LEARN_EDGE)
        if t[-1] - a < LEARN or mine.sum() < LEAST:
            return
        t, f = t[mine], f[mine]
        first = pieces(t, f)[0]
        w = f[(t >= first[0]) & (t < first[1])]
        if len(w) < LEAST or float(unit(w[:len(w) // 2].mean(0)) @ unit(w[len(w) // 2:].mean(0))) < HALVES:
            return
        others = {k: v for k, v in self.refs().items() if k != slug}
        if against(slug, alike(unit(w.mean(0)), others), LEARN):
            return
        self.today.setdefault(slug, {})[cur["start"]] = w

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
