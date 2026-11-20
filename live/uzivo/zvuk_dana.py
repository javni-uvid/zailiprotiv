"""A sitting day's recording written down whole, word by word with its second, so the day's speeches can be found in it
(20 Nov 2026: on 19 Nov the broadcast stopped showing the speaker's caption, so who spoke when has to come from what
was said: the chair's words giving the floor, and the Assembly's notes lined up with these words).

    python -m uzivo.zvuk_dana <out dir> <file url>...

For each file of the archive: ffmpeg takes its sound (16 kHz, mono) into <out dir>/<file>.wav, Whisper (config.
WHISPER_MODEL, large-v3-turbo: the one model, the maintainer's decision of 20 Nov 2026) writes it down, and every
segment is a line of <out dir>/<file>.jsonl: {"od", "do", "tekst", "reci": [[from, to, word], ...]}, seconds into the
file. Whisper is told the Assembly's set terms and, from <out dir>/imena.txt when there is one (one name a line), the
names it is likeliest to hear, so that names come out as written. A file read to its end (<file>.done) is skipped;
one read in part goes on from the piece where it stopped (<file>.pos).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from . import config
from .prepis import Writer

PIECE = 600.0  # seconds of sound written down at a time: a whole file at once takes more memory than the computer has


def hint(out: Path) -> str:
    path = out / "imena.txt"
    names = [n.strip() for n in path.read_text(encoding="utf-8").splitlines() if n.strip()] if path.exists() else []
    return (Writer.TERMS + (" Govore: " + ", ".join(names) + "." if names else ""))[:900]


def main() -> None:
    out, urls = Path(sys.argv[1]), sys.argv[2:]
    out.mkdir(parents=True, exist_ok=True)
    import wave

    import numpy as np
    from faster_whisper import WhisperModel
    model = WhisperModel(config.WHISPER_MODEL, device="cpu", compute_type="int8",
                         cpu_threads=int(os.environ.get("THREADS", "4")))
    prompt = hint(out)
    for url in urls:
        name = url.rsplit("/", 1)[1].removesuffix(".mp4")
        if (out / f"{name}.done").exists():
            continue
        wav = out / f"{name}.wav"
        if not wav.exists():
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", url, "-vn", "-ac", "1", "-ar", "16000",
                            str(wav) + ".part.wav"], check=True)
            os.replace(str(wav) + ".part.wav", wav)
        lines, pos = out / f"{name}.jsonl", out / f"{name}.pos"
        last = float(pos.read_text()) if pos.exists() else 0.0
        if lines.exists():  # what a stopped piece had written is written again with that piece
            keep = [ln for ln in lines.read_text(encoding="utf-8").splitlines() if json.loads(ln)["od"] < last]
            lines.write_text("".join(ln + "\n" for ln in keep), encoding="utf-8")
        with wave.open(str(wav)) as w:  # not faster_whisper.decode_audio: the image's PyAV is newer than it expects
            total = w.getnframes() / 16000
            while last < total:
                w.setpos(int(last * 16000))
                audio = np.frombuffer(w.readframes(int(PIECE * 16000)), np.int16).astype(np.float32) / 32768
                segments, _ = model.transcribe(audio, language="sr", beam_size=5, vad_filter=True, word_timestamps=True,
                                               condition_on_previous_text=False, initial_prompt=prompt)
                with open(lines, "a", encoding="utf-8") as f:
                    for s in segments:
                        f.write(json.dumps({"od": round(last + s.start, 2), "do": round(last + s.end, 2),
                                            "tekst": s.text.strip(),
                                            "reci": [[round(last + x.start, 2), round(last + x.end, 2), x.word.strip()]
                                                     for x in (s.words or [])]}, ensure_ascii=False) + "\n")
                last += PIECE
                pos.write_text(str(last))
        (out / f"{name}.done").write_text("")
        print(name, "done", flush=True)


if __name__ == "__main__":
    main()
