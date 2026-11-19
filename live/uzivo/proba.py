"""Try another Whisper model beside the running one, on the same sound: `python -m uzivo.proba large-v3-turbo [seconds]`
inside the service's container. Listens to the broadcast's kept sound for a while (60 s unless said), then writes it
down with each model and prints how long each took and what it wrote. Changes nothing in the service; while it runs
both share the processor, so the times here are the worse case."""
import sys
import time

from . import config, prepis


def collect(seconds: float, sleep=time.sleep) -> tuple[bytes, float]:
    """The sound kept in the next `seconds`, joined: (raw samples, their length in seconds)."""
    seen: dict[str, tuple[float, bytes]] = {}
    until = time.time() + seconds
    while True:
        for start, _length, f in prepis.waiting():
            if f.name not in seen:
                try:
                    seen[f.name] = (start, f.read_bytes())
                except OSError:
                    pass
        if time.time() >= until:
            break
        sleep(1)
    raw = b"".join(b for _, b in sorted(seen.values()))
    return raw, len(raw) / 2 / prepis.RATE


def main(argv: list[str]) -> int:
    models = [m for m in argv if not m.isdigit()] or ["large-v3-turbo"]
    seconds = next((int(m) for m in argv if m.isdigit()), 60)
    print(f"slušam {seconds} s…", flush=True)
    raw, length = collect(seconds)
    if length < 10:
        print("nema zvuka: prenos ne ide ili je prepis isključen")
        return 1
    import numpy as np
    from faster_whisper import WhisperModel
    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    for name in [config.WHISPER_MODEL] + [m for m in models if m != config.WHISPER_MODEL]:
        t0 = time.time()
        model = WhisperModel(name, device=config.WHISPER_DEVICE, compute_type=config.WHISPER_COMPUTE,
                             cpu_threads=config.WHISPER_THREADS)
        loaded = time.time() - t0
        t0 = time.time()
        segments, _ = model.transcribe(samples, language="sr", beam_size=config.WHISPER_BEAM, vad_filter=True,
                                       condition_on_previous_text=False)
        text = " ".join(s.text.strip() for s in segments).strip()
        took = time.time() - t0
        print(f"\n=== {name}: {length:.0f} s zvuka za {took:.0f} s ({took / length:.2f}×), učitavanje {loaded:.0f} s\n{text}", flush=True)
        del model
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
