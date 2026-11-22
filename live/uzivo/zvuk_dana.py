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

On the graphics card when its server answers (22 Nov 2026, the maintainer: "možeš prebaciti na karticu ako ima
mesta"; live/whisper-gpu.ps1, WHISPER_URL or host.docker.internal:8178), some five times faster; otherwise on the CPU
as before. The card's words come as tokens ("ć", "e"): a token without a space before it is the same word's.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

from . import config
from .prepis import Writer, over_http

PIECE = 600.0  # seconds of sound written down at a time: a whole file at once takes more memory than the computer has


def hint(out: Path) -> str:
    path = out / "imena.txt"
    names = [n.strip() for n in path.read_text(encoding="utf-8").splitlines() if n.strip()] if path.exists() else []
    return (Writer.TERMS + (" Govore: " + ", ".join(names) + "." if names else ""))[:900]


def card() -> str:
    """The graphics card's Whisper server, when it answers; "" otherwise."""
    url = config.WHISPER_URL or "http://host.docker.internal:8178"
    try:
        urllib.request.urlopen(url + "/", timeout=3).close()
        return url
    except Exception:
        return ""


def words(tokens: list[dict], at: float, span: tuple[float, float] | None = None) -> list[list]:
    """The card's tokens as words, each [from, to, word], seconds into the file: a token that does not begin with a
    space goes on the word before it; the server's own marks ("[_BEG_]") are left out. The server cuts the silence
    out before it writes (VAD) and gives the segment's times back in the whole sound but the tokens' in the shortened
    one (22 Nov 2026: a minute off): with the segment's own `span`, the words are laid over it in proportion."""
    kept = [x for x in tokens if str(x.get("word", "")).strip() and not str(x.get("word", "")).strip().startswith("[_")]
    if not kept:
        return []
    a0, b0 = float(kept[0].get("start", 0)), float(kept[-1].get("end", 0))
    def place(t: float) -> float:
        if span is None:
            return round(at + t, 2)
        if b0 <= a0:
            return round(at + span[0], 2)
        return round(at + span[0] + (t - a0) * (span[1] - span[0]) / (b0 - a0), 2)
    out: list[list] = []
    for x in kept:
        text = str(x.get("word", ""))
        a, b = place(float(x.get("start", 0))), place(float(x.get("end", 0)))
        if out and not text.startswith(" "):
            out[-1][1], out[-1][2] = b, out[-1][2] + text
        else:
            out.append([a, b, text.strip()])
    return out


def on_card(url: str, audio: bytes, at: float, prompt: str) -> list[dict]:
    """A piece written down on the card: its lines, as the CPU's."""
    got = over_http(url, audio, prompt, timeout=900, whole=True)
    return [{"od": round(at + float(s.get("start", 0)), 2), "do": round(at + float(s.get("end", 0)), 2),
             "tekst": " ".join(str(s.get("text", "")).split()), "reci": words(s.get("words") or [], at, (float(s.get("start", 0)), float(s.get("end", 0))))}
            for s in got.get("segments") or [] if str(s.get("text", "")).strip()]


def main() -> None:
    out, urls = Path(sys.argv[1]), sys.argv[2:]
    out.mkdir(parents=True, exist_ok=True)
    import wave

    import numpy as np
    gpu, model = card(), None
    if not gpu:
        from faster_whisper import WhisperModel
        model = WhisperModel(config.WHISPER_MODEL, device="cpu", compute_type="int8",
                             cpu_threads=int(os.environ.get("THREADS", "4")))
    print("na kartici:", gpu if gpu else "ne, na procesoru", flush=True)
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
                raw = w.readframes(int(PIECE * 16000))
                if gpu:
                    got = on_card(gpu, raw, last, prompt)
                else:
                    audio = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
                    segments, _ = model.transcribe(audio, language="sr", beam_size=5, vad_filter=True, word_timestamps=True,
                                                   condition_on_previous_text=False, initial_prompt=prompt)
                    got = [{"od": round(last + s.start, 2), "do": round(last + s.end, 2), "tekst": s.text.strip(),
                            "reci": [[round(last + x.start, 2), round(last + x.end, 2), x.word.strip()] for x in (s.words or [])]}
                           for s in segments]
                with open(lines, "a", encoding="utf-8") as f:
                    for line in got:
                        f.write(json.dumps(line, ensure_ascii=False) + "\n")
                last += PIECE
                pos.write_text(str(last))
        (out / f"{name}.done").write_text("")
        print(name, "done", flush=True)


if __name__ == "__main__":
    main()
