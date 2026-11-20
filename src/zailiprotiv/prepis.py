"""An automatic transcript of each speech of a sitting day, from the archive's recording (Whisper), until the notes.

The Assembly's stenographic notes come days after a sitting. For a day read from the recording
(`data/<N>/snimak/<date>.json`), each turn with its place in an archive file is cut out of it as sound (ffmpeg reads
only those bytes over the network) and written down by Whisper (faster-whisper, run on the CPU), into
`data/<N>/prepis/<date>.json`: {"model", "govori": {"<turn's first second>": {"ime", "od", "do", "tekst"}}}. The site
shows it under the turn as an automatic transcript that may err, never as a quote, and not once the notes of the day
are read (the notes are what the site quotes; principle 6).

Slow: a model reads sound at about real time on two cores, so a run stops after `minutes` and the next goes on where
it stopped (each turn is saved as soon as it is written).
"""
from __future__ import annotations

import json
import subprocess
import tempfile
import time
from pathlib import Path

LEAD = 5  # the turn's place in the file is this many seconds before its first frame (as everywhere on the site)
TAIL = 10  # and the caption may go a little before the speaker stops
SHORTEST = 30  # seconds: shorter turns (a reply, a point of order) are not written down


def sound(url: str, start: float, seconds: float, path: Path) -> bool:
    out = subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.1f}", "-t", f"{seconds:.1f}", "-i", url,
                          "-vn", "-ac", "1", "-ar", "16000", str(path)], capture_output=True, timeout=1800)
    return out.returncode == 0 and path.exists() and path.stat().st_size > 1000


def run(root: Path, conv: str, day: str, *, model: str = "large-v3-turbo", minutes: float = 300, transcribe=None) -> int:
    """Write down the turns of `day` not yet written; returns how many were. transcribe(path) → text is for tests."""
    src = root / conv / "snimak" / f"{day}.json"
    if not src.exists():
        print(f"prepis: no day {day}")
        return 0
    turns = json.loads(src.read_text(encoding="utf-8"))["govori"]
    path = root / conv / "prepis" / f"{day}.json"
    out = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"model": model, "govori": {}}
    if transcribe is None:
        from faster_whisper import WhisperModel
        whisper = WhisperModel(model, device="cpu", compute_type="int8")

        def transcribe(wav: Path) -> str:
            segments, _ = whisper.transcribe(str(wav), language="sr", beam_size=5, vad_filter=True,
                                             condition_on_previous_text=False)
            return " ".join(s.text.strip() for s in segments).strip()
    stop, done = time.time() + minutes * 60, 0
    for t in turns:
        key = str(t["od"])
        if key in out["govori"] or not t.get("datoteka") or t.get("okvira", 0) < 2 or t["do"] - t["od"] < SHORTEST:
            continue
        if time.time() > stop:
            break
        with tempfile.TemporaryDirectory() as tmp:
            wav = Path(tmp) / "govor.wav"
            if not sound(t["datoteka"], t.get("snimak") or 0, t["do"] - t["od"] + LEAD + TAIL, wav):
                print(f"prepis: no sound for {t['ime']} {key}")
                continue
            text = transcribe(wav)
        out["govori"][key] = {"ime": t["ime"], "od": t["od"], "do": t["do"], "tekst": text}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        done += 1
        print(f"prepis: {t['ime']} ({(t['do'] - t['od']) // 60} min) written", flush=True)
    left = sum(1 for t in turns if t.get("datoteka") and t.get("okvira", 0) >= 2 and t["do"] - t["od"] >= SHORTEST
               and str(t["od"]) not in out["govori"])
    print(f"prepis {day}: {done} written, {left} left")
    return done
