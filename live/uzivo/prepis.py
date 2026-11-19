"""An automatic transcript of what is being said, a piece at a time (19 Nov 2026, the maintainer's decision).

The broadcast's segments carry its sound. Each segment read for its frame leaves its sound here as well (`keep`:
16 kHz, one channel, a small file named by when it was read). A thread (`Writer`) gives each file to the turn it
falls in, by the same clock the tracker keeps turns by, and has Whisper (faster-whisper on the CPU) write the sound
down: about a minute at a time while a speaker is on, the rest when the turn ends. The text goes to the tracker
(`Tracker.say`) and is shown as an automatic transcript that may err, never as a quote (AGENTS.md, principle 6: the
site quotes the notes); nothing is summed up or reworded by a model. Sound not in any turn (the chair, a break) is
thrown away unread, and every file is deleted once written down.

Off unless the packages are there and WHISPER_MODEL names a model: the service runs the same without it.
"""
from __future__ import annotations

import logging
import os
import subprocess
import threading
import time
from pathlib import Path

from . import config
from .names import latin
from .state import SAID_LEAD, Tracker

log = logging.getLogger("prepis")
RATE = 16000
PIECE = 50  # seconds of unwritten sound of the speaker now on before a piece is written down
LONGEST = 120  # seconds: the most sound written down at once
SHORTEST = 20  # seconds: a shorter turn (a reply, a point of order) is not written down
TAIL = 3  # seconds after a turn's last frame that still count as its sound
LOST = 180  # seconds: sound this old in no turn is thrown away
MOST = 45 * 60  # seconds of sound kept waiting; beyond it the oldest is dropped (the computer can't keep up)


def on() -> bool:
    return bool(config.WHISPER_MODEL)


def keep(segment: str, read_at: float, seconds: float) -> None:
    """A segment's sound → a file of raw samples, named by the second the segment ends at and its length. Never
    raises: the frame matters more than the sound."""
    if not on():
        return
    try:
        folder = Path(config.SOUND_PATH)
        folder.mkdir(parents=True, exist_ok=True)
        out = folder / f"{int(read_at * 1000)}-{int(seconds * 1000)}.tmp"
        done = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-i", segment, "-vn",
                               "-ac", "1", "-ar", str(RATE), "-f", "s16le", str(out)], capture_output=True, timeout=20)
        if done.returncode == 0 and out.exists() and out.stat().st_size > 2000:
            out.replace(out.with_suffix(".pcm"))
        else:
            out.unlink(missing_ok=True)
    except Exception:
        log.debug("sound not kept", exc_info=True)


def waiting() -> list[tuple[float, float, Path]]:
    """The kept files, oldest first: (the second the sound begins at, its length, the file)."""
    out = []
    for f in Path(config.SOUND_PATH).glob("*.pcm"):
        try:
            end, length = (int(x) / 1000 for x in f.stem.split("-"))
        except ValueError:
            continue
        out.append((end - length, length, f))
    return sorted(out)


def choose(files: list[tuple[float, float, Path]], turns: list[dict], current: dict | None, now: float):
    """What to do with the kept sound: (files to write down as one piece, files to throw away). A file belongs to
    the turn its middle falls in; the oldest turn with sound is written first, a finished one whole, the one now on
    once a piece's worth has gathered. Pure, for tests."""
    spans = [(d["od"] - SAID_LEAD, d["do"] + TAIL, d["sekundi"], False) for d in turns]
    if current:
        spans.append((current["od"] - SAID_LEAD, now + TAIL, current["sekundi"], True))
    spans.sort()
    drop, by = [], {}
    for start, length, f in files:
        mid = start + length / 2
        span = next((s for s in spans if s[0] <= mid <= s[1]), None)
        if span is None:
            if now - start > LOST:
                drop.append(f)
        elif span[2] < SHORTEST and not span[3]:
            drop.append(f)
        else:
            by.setdefault(span, []).append((start, length, f))
    for span in sorted(by):
        mine = by[span]
        if not span[3] or (sum(x[1] for x in mine) >= PIECE and span[2] >= SHORTEST):
            piece, total = [], 0.0
            for x in mine:  # a long wait (a finished turn, or the computer behind) goes in pieces, so text keeps coming
                piece.append(x)
                total += x[1]
                if total >= LONGEST:
                    break
            return piece, drop
    return [], drop


class Writer(threading.Thread):
    """Writes the kept sound down, turn by turn. `write(samples) -> text` is for tests; otherwise Whisper."""

    def __init__(self, tracker: Tracker, stop: threading.Event, write=None) -> None:
        super().__init__(daemon=True)
        self.tracker, self.halt, self.write = tracker, stop, write

    def _model(self):
        from faster_whisper import WhisperModel
        import numpy as np
        model = WhisperModel(config.WHISPER_MODEL, device=config.WHISPER_DEVICE, compute_type=config.WHISPER_COMPUTE,
                             cpu_threads=config.WHISPER_THREADS)

        def write(raw: bytes) -> str:
            samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            segments, _ = model.transcribe(samples, language="sr", beam_size=config.WHISPER_BEAM, vad_filter=True,
                                           condition_on_previous_text=False)
            return " ".join(s.text.strip() for s in segments).strip()
        return write

    def step(self, now: float | None = None) -> bool:
        """One look at the kept sound; True when a piece was written down."""
        now = time.time() if now is None else now
        files = waiting()
        if not files:
            return False
        while sum(x[1] for x in files) > MOST:  # behind by more than the computer will catch up with
            files.pop(0)[2].unlink(missing_ok=True)
        snap = self.tracker.snapshot()
        live = not snap.get("ranije") and not snap.get("snimak")
        current = snap.get("sada") if snap["stanje"] == "govori" else None
        piece, drop = choose(files, snap["danas"] if live else [], current, now)
        for f in drop:
            f.unlink(missing_ok=True)
        if not piece:
            return False
        raw = b"".join(f.read_bytes() for _, _, f in piece)
        started = time.time()
        text = latin(self.write(raw))
        self.tracker.say(piece[0][0], text)
        for _, _, f in piece:
            f.unlink(missing_ok=True)
        log.info("%.0f s of sound written down in %.0f s (%d words)", sum(x[1] for x in piece),
                 time.time() - started, len(text.split()))
        return True

    def run(self) -> None:
        if self.write is None:
            try:
                self.write = self._model()
                log.info("transcript on: %s, %d threads", config.WHISPER_MODEL, config.WHISPER_THREADS)
            except Exception as exc:  # no packages or no model: the service goes on without the transcript
                log.warning("transcript off (%s)", exc)
                config.WHISPER_MODEL = ""
                return
        while not self.halt.is_set():
            try:
                busy = self.step()
            except Exception:
                log.exception("a piece not written down")
                busy = False
            self.halt.wait(0.5 if busy else 3.0)
