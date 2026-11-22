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

import io
import json
import logging
import re
import subprocess
import threading
import time
import urllib.request
import uuid
import wave
from pathlib import Path

from . import config
from .names import latin
from .state import Tracker
from .state_base import SAID_LEAD

log = logging.getLogger("prepis")
RATE = 16000
PIECE = 30  # seconds of unwritten sound of the speaker now on before a piece is written down
LONGEST = 120  # seconds: the most sound written down at once
SHORTEST = 20  # seconds: a shorter turn (a reply, a point of order) is not written down
TAIL = 3  # seconds after a turn's last frame that still count as its sound
LOST = 180  # seconds: sound this old in no turn is thrown away
MOST = 45 * 60  # seconds of sound kept waiting; beyond it the oldest is dropped (the computer can't keep up)


RETRY = 300  # seconds the CPU writes after the graphics card's server did not answer, before it is asked again


def calm(text: str) -> str:
    """A word Whisper repeats more than three times in a row is its own loop, not speech (22 Nov 2026: "znaju" nine
    times over a noisy stretch): kept three times. Nothing else is touched."""
    out: list[str] = []
    for w in text.split():
        key = re.sub(r"\W", "", w.lower())
        if key and len(out) >= 3 and all(re.sub(r"\W", "", x.lower()) == key for x in out[-3:]):
            end = re.search(r"[.!?…]+$", w)
            if end:  # the sentence's end stays
                out[-1] = out[-1].rstrip(",;:.!?…") + end.group(0)
            continue
        out.append(w)
    return " ".join(out)


def program(f: Path) -> float | None:
    """When a kept file's sound begins by the broadcast's own clock (stream.program_of), or None."""
    parts = f.stem.split("-")
    return int(parts[2]) / 1000 if len(parts) > 2 and parts[2].isdigit() else None


def over_http(url: str, raw: bytes, hint: str = "", timeout: float = 90, phrases: bool = False):
    """The sound written down by whisper.cpp's server (`/inference`): a wav of the raw samples, Serbian, the hint as
    its prompt. Raises when it does not answer."""
    b = io.BytesIO()
    with wave.open(b, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(raw)
    k = uuid.uuid4().hex
    parts = [(f'--{k}\r\nContent-Disposition: form-data; name="file"; filename="a.wav"\r\n'
              "Content-Type: audio/wav\r\n\r\n").encode(), b.getvalue(), b"\r\n"]
    for name, value in (("response_format", "verbose_json" if phrases else "json"), ("language", "sr"),
                        ("temperature", "0.0"), ("prompt", hint)):
        if value:
            parts.append(f'--{k}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    parts.append(f"--{k}--\r\n".encode())
    req = urllib.request.Request(url + "/inference", data=b"".join(parts),
                                 headers={"Content-Type": f"multipart/form-data; boundary={k}"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        got = json.loads(r.read())
    if phrases:  # each phrase with its seconds in the sound: [(start, end, text)]
        return [(float(x.get("start", 0)), float(x.get("end", 0)), " ".join(str(x.get("text", "")).split()))
                for x in got.get("segments") or [] if str(x.get("text", "")).strip()]
    return " ".join(str(got.get("text", "")).split())


def on() -> bool:
    return bool(config.WHISPER_MODEL)


def keep(segment: str, read_at: float, seconds: float, program: float | None = None) -> None:
    """A segment's sound → a file of raw samples, named by the second the segment ends at and its length. Never
    raises: the frame matters more than the sound."""
    if not on():
        return
    try:
        folder = Path(config.SOUND_PATH)
        folder.mkdir(parents=True, exist_ok=True)
        # named by the second the segment ends at, its length, and when it begins by the broadcast's clock
        out = folder / (f"{int(read_at * 1000)}-{int(seconds * 1000)}" + (f"-{int(program * 1000)}" if program else "") + ".tmp")
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
            end, length = (int(x) / 1000 for x in f.stem.split("-")[:2])
        except ValueError:
            continue
        out.append((end - length, length, f))
    return sorted(out)


CHAIR_WAIT = 25  # seconds: sound in no turn this old will not turn out to be a turn's beginning; it is the chair's
CHAIR_PIECE = 20  # seconds of the chair's sound before it is written down (shorter than a speaker's: the chair speaks briefly)
CHAIR_LEAST = 8  # seconds: less sound than this between two turns is not written down


def choose(files: list[tuple[float, float, Path]], turns: list[dict], current: dict | None, now: float,
           chair_only: bool = False):
    """What to do with the kept sound: (files to write down as one piece, files to throw away, whether the piece is
    the chair's). A file belongs to the turn its middle falls in; the oldest turn with sound is written first, a
    finished one whole, the one now on once a piece's worth has gathered. Sound in no turn is the chair's (who has no
    caption) or the hall's: once it is clear no turn begins there it is written down too, for the day's steps
    (hronika.py), never shown as anyone's speech. Pure, for tests."""
    spans = [(d["od"] - SAID_LEAD, d["do"] + TAIL, d["sekundi"], False) for d in turns]
    if current:
        spans.append((current["od"] - SAID_LEAD, now + TAIL, current["sekundi"], True))
    spans.sort()
    drop, by, free = [], {}, []
    for start, length, f in files:
        mid = start + length / 2
        span = next((s for s in spans if s[0] <= mid <= s[1]), None)
        if span is None:
            free.append((start, length, f))
        elif chair_only or (span[2] < SHORTEST and not span[3]):  # chair_only: a speaker's sound is let go unwritten
            drop.append(f)
        else:
            by.setdefault(span, []).append((start, length, f))
    # the chair's first, so the day's steps keep up while the speakers' sound waits: the oldest run of sound in no
    # turn, files one after another, old enough to be no turn's beginning
    run: list = []
    for x in free:
        if now - x[0] <= CHAIR_WAIT:
            break
        if run and (x[0] - (run[-1][0] + run[-1][1]) > 3 or sum(y[1] for y in run) >= LONGEST):
            break
        run.append(x)
    if run:
        ended = len(run) < len([x for x in free if now - x[0] > CHAIR_WAIT]) or now - (run[-1][0] + run[-1][1]) > CHAIR_WAIT
        total = sum(y[1] for y in run)
        if total >= CHAIR_PIECE or (ended and total >= CHAIR_LEAST):
            return run, drop, True
        if ended or now - run[0][0] > LOST:
            drop += [y[2] for y in run]
    for span in sorted(by):
        mine = by[span]
        if not span[3] or (sum(x[1] for x in mine) >= PIECE and span[2] >= SHORTEST):
            piece, total = [], 0.0
            for x in mine:  # a long wait (a finished turn, or the computer behind) goes in pieces, so text keeps coming
                piece.append(x)
                total += x[1]
                if total >= LONGEST:
                    break
            return piece, drop, False
    return [], drop, False


class Writer(threading.Thread):
    """Writes the kept sound down, turn by turn. `write(samples) -> text` is for tests; otherwise Whisper."""

    def __init__(self, tracker: Tracker, stop: threading.Event, write=None) -> None:
        super().__init__(daemon=True)
        self.tracker, self.halt, self.write = tracker, stop, write
        self.hint = ""  # the names and terms Whisper is told to expect in the piece it is given (hint())
        self.write_whole = None  # the better model's reading, for finished turns (WHISPER_FINAL_MODEL)
        self._whole: dict[int, list[str]] = {}  # a long turn's second reading so far, by the turn's first second

    def _model(self):
        """The writer: the graphics card's server when one is named (config.WHISPER_URL), the CPU while it does not
        answer (for RETRY seconds, then it is asked again) or when none is; the CPU's model is loaded only when it is
        first needed. Either way a word's loop is cut (`calm`)."""
        if not config.WHISPER_URL:
            cpu = self._cpu()
            return lambda raw: calm(cpu(raw))
        local: list = []
        state = {"cpu_until": 0.0}

        def write(raw: bytes) -> str:
            if time.time() >= state["cpu_until"]:
                try:
                    return calm(over_http(config.WHISPER_URL, raw, self.hint, timeout=max(30.0, len(raw) / 2 / RATE)))
                except Exception as exc:
                    state["cpu_until"] = time.time() + RETRY
                    log.warning("Whisper on the graphics card did not answer (%s): the CPU writes for %d s", exc, RETRY)
            if not local:
                local.append(self._cpu())
            return calm(local[0](raw))
        return write

    def _cpu(self):
        from faster_whisper import WhisperModel
        import numpy as np
        model = WhisperModel(config.WHISPER_MODEL, device=config.WHISPER_DEVICE, compute_type=config.WHISPER_COMPUTE,
                             cpu_threads=config.WHISPER_THREADS)

        def write(raw: bytes) -> str:
            samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            segments, _ = model.transcribe(samples, language="sr", beam_size=config.WHISPER_BEAM, vad_filter=True,
                                           condition_on_previous_text=False, initial_prompt=self.hint or None)
            return " ".join(s.text.strip() for s in segments).strip()
        return write

    def _final_model(self):
        """The better model for the second reading of a finished turn (WHISPER_FINAL_MODEL); None when off."""
        if not config.WHISPER_FINAL_MODEL or config.WHISPER_FINAL_MODEL == config.WHISPER_MODEL or config.CHAIR_ONLY:
            return None
        from faster_whisper import WhisperModel
        import numpy as np
        model = WhisperModel(config.WHISPER_FINAL_MODEL, device=config.WHISPER_DEVICE, compute_type=config.WHISPER_COMPUTE,
                             cpu_threads=config.WHISPER_THREADS)

        def write(raw: bytes) -> str:
            samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            segments, _ = model.transcribe(samples, language="sr", beam_size=5, vad_filter=True,
                                           condition_on_previous_text=False, initial_prompt=self.hint or None)
            return " ".join(s.text.strip() for s in segments).strip()
        return write

    TERMS = ("Narodna skupština Republike Srbije. Predsedavajući, narodni poslanici, poslanička grupa, Poslovnik, "
             "povreda Poslovnika, replika, dnevni red, amandman, pretres, glasanje.")

    def hint_for(self, snap: dict) -> str:
        """What Whisper is told before a piece (19 Nov 2026): the Assembly's set terms and the names it is likeliest
        to hear, today's speakers, newest first, as many as fit (the model reads only so much of a hint). It makes
        "Vučić" and "Poslovnik" come out as written; it puts no words in anyone's mouth."""
        names, seen = [], set()
        cur = snap.get("sada") if snap.get("stanje") == "govori" else None
        for d in ([cur] if cur else []) + list(snap.get("danas") or []):
            n = " ".join(d["ime"].split()[-1:] + d["ime"].split()[:-1])
            if n not in seen:
                seen.add(n)
                names.append(n)
        return (self.TERMS + (" Govore: " + ", ".join(names[:28]) + "." if names else ""))[:900]

    def step_whole(self, snap: dict, now: float) -> bool:
        """The second reading: a finished turn's kept sound written down again by the better model, two minutes at a
        time, and shown in place of the first reading once the whole turn is done. Only when the first reading has
        nothing to do, so what is being said now is never kept waiting by it."""
        kept = sorted((int(f.stem.split("-")[0]) / 1000 - int(f.stem.split("-")[1]) / 1000, int(f.stem.split("-")[1]) / 1000, f)
                      for f in (Path(config.SOUND_PATH) / "kraj").glob("*.pcm"))
        if not kept:
            return False
        cur = snap.get("sada") if snap["stanje"] == "govori" else None
        for d in sorted(snap["danas"], key=lambda d: d["od"]):
            if d.get("prepis_ceo"):
                continue
            mine = [x for x in kept if d["od"] - SAID_LEAD <= x[0] + x[1] / 2 <= d["do"] + TAIL]
            if not mine or (cur and cur["ime"] == d["ime"] and cur["od"] - d["do"] < 150):
                continue  # nothing kept, or the same speaker is on again and the two may yet be one turn
            piece, total = [], 0.0
            for x in mine:
                piece.append(x)
                total += x[1]
                if total >= LONGEST:
                    break
            started = time.time()
            text = latin(self.write_whole(b"".join(f.read_bytes() for _, _, f in piece)))
            for _, _, f in piece:
                f.unlink(missing_ok=True)
            self._whole.setdefault(d["od"], []).append(text)
            if len(piece) == len(mine):  # the turn's last piece: its second reading takes the first one's place
                self.tracker.say_whole(d["od"], " ".join(self._whole.pop(d["od"])))
            log.info("second reading: %.0f s of %s in %.0f s", total, d["ime"], time.time() - started)
            return True
        for start, length, f in kept:  # sound of no turn left to read again, or too old to matter
            if now - start > 6 * 3600 or not any(d["od"] - SAID_LEAD <= start + length / 2 <= d["do"] + TAIL for d in snap["danas"] + ([cur] if cur else [])):
                if now - start > LOST:
                    f.unlink(missing_ok=True)
        return False

    def step(self, now: float | None = None) -> bool:
        """One look at the kept sound; True when a piece was written down. A `now` given (the tests' clock) is also
        the day the state is read for, so that a fixed day is not taken for an earlier one after midnight."""
        given, now = now, time.time() if now is None else now
        files = waiting()
        if not files:
            if self.write_whole:
                snap = self.tracker.snapshot(given)
                if not snap.get("ranije") and not snap.get("snimak"):
                    self.hint = self.hint_for(snap)
                    return self.step_whole(snap, now)
            return False
        while sum(x[1] for x in files) > MOST:  # behind by more than the computer will catch up with
            files.pop(0)[2].unlink(missing_ok=True)
        snap = self.tracker.snapshot(given)
        live = not snap.get("ranije") and not snap.get("snimak")
        current = snap.get("sada") if snap["stanje"] == "govori" else None
        piece, drop, chair = choose(files, snap["danas"] if live else [], current, now, chair_only=config.CHAIR_ONLY)
        for f in drop:
            f.unlink(missing_ok=True)
        if not piece:
            return False
        raw = b"".join(f.read_bytes() for _, _, f in piece)
        started = time.time()
        self.hint = self.hint_for(snap)
        text = latin(self.write(raw))
        self.tracker.say(piece[0][0], text, chair=chair)
        from . import hronika  # the steps said in the piece, the chair's or a speaker's, by the same rules
        for what, sentence in hronika.find(text):
            self.tracker.note(piece[0][0], what, sentence, "prepis")
        roster = self.tracker.roster
        if chair and roster:  # no caption on the picture: whom the chair gave the floor to, by name (hronika.floor)
            sitting = [p for p in roster.people if not roster.current or p.slug in roster.current]
            for person in hronika.floor(text, sitting):
                self.tracker.note(piece[0][0], "Reč ima", person.name, "prepis", person.slug)
        for _, _, f in piece:
            if self.write_whole and not chair:  # kept for the second reading, once the turn is over
                (f.parent / "kraj").mkdir(exist_ok=True)
                f.replace(f.parent / "kraj" / f.name)
            else:
                f.unlink(missing_ok=True)
        log.info("%.0f s of %s written down in %.0f s (%d words)", sum(x[1] for x in piece), "the chair's sound" if chair else "sound",
                 time.time() - started, len(text.split()))
        return True

    def run(self) -> None:
        if self.write is None:
            try:
                self.write = self._model()
                log.info("transcript on: %s, %s%s", config.WHISPER_MODEL,
                         config.WHISPER_URL or f"{config.WHISPER_THREADS} threads",
                         ", the chair's sound only" if config.CHAIR_ONLY else "")
                try:
                    self.write_whole = self._final_model()
                    if self.write_whole:
                        log.info("second reading on: %s", config.WHISPER_FINAL_MODEL)
                except Exception as exc:
                    log.warning("second reading off (%s)", exc)
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


CAPTION = 4  # seconds of new sound for a line under the picture: one segment (5 s), so a phrase waits little
CAPTION_LATE = 30  # seconds: sound older than this is not written for the line any more (it would come too late)


class Captions(threading.Thread):
    """The line under the broadcast's picture (22 Nov 2026, the maintainer): the newest sound, some eight seconds at a
    time, written down by the graphics card's Whisper (config.WHISPER_URL) for the page only. Not kept, not read for
    the day's steps, nobody's words by name: the transcript above (`Writer`) goes on as it was, and reads the same
    files after this has. While the card does not answer, there is no line."""

    def __init__(self, tracker: Tracker, stop: threading.Event, write=None) -> None:
        super().__init__(daemon=True)
        self.tracker, self.halt = tracker, stop
        self.write = write or (lambda raw, hint: over_http(config.WHISPER_URL, raw, hint, timeout=15, phrases=True))
        self.until = 0.0  # the end of the sound already written for the line

    def step(self, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        fresh = [x for x in waiting() if x[0] >= self.until - 0.5 and now - x[0] < CAPTION_LATE]
        if sum(x[1] for x in fresh) < CAPTION:
            return False
        piece, total = [], 0.0
        for x in fresh:
            piece.append(x)
            total += x[1]
            if total >= CAPTION:
                break
        self.until = piece[-1][0] + piece[-1][1]
        try:
            raw = b"".join(f.read_bytes() for _, _, f in piece)
        except OSError:  # the transcript has just taken it
            return False
        cur = (self.tracker.snapshot().get("sada") or {}).get("ime", "")
        hint = Writer.TERMS + (f" Govori: {' '.join(cur.split()[-1:] + cur.split()[:-1])}." if cur else "")
        # each phrase a line, at its own second: by the broadcast's clock when the files carry it, so the page shows it
        # when the viewer's player reaches it (22 Nov 2026, the maintainer: "da titl bude istovremen sa zvukom")
        start, clock = piece[0][0], program(piece[0][2])
        for a, b, text in self.write(raw, hint):
            text = calm(latin(text))
            if text:
                self.tracker.caption(start + a, start + b, text, None if clock is None else clock + a)
        return True

    def run(self) -> None:
        log.info("the line under the picture on: %s", config.WHISPER_URL)
        while not self.halt.is_set():
            try:
                busy = self.step()
            except Exception as exc:
                log.debug("a line under the picture not written (%s)", exc)
                self.halt.wait(10.0)
                continue
            self.halt.wait(0.3 if busy else 1.0)
