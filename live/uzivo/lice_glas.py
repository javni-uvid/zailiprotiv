"""Faces and voices of a recording, so the speaker can be known where the broadcast shows no caption (20 Nov 2026, the
maintainer's decision: the recordings are public and MPs are public officials; faces and voices may be used to tell
who is speaking). Run in the analysis image (live/Dockerfile.analiza), never in the live service.

    python -m uzivo.lice_glas lica <out dir> <file url>...   a frame every STEP s: each face found, its place and size,
                                                            and SFace's 128 numbers → <out dir>/<file>.lica.npz
    python -m uzivo.lice_glas glas <out dir> <file url>...   the sound (<file>.wav, as zvuk_dana.py leaves it, or taken
                                                            anew) in windows of WIN s every HOP s with some voice in
                                                            them: 512 numbers each → <out dir>/<file>.glas.npz
    python -m uzivo.lice_glas portreti <photos dir> <out>    the faces of the MPs' portraits (data/photos/) → <out>.npz

Only numbers are kept, no picture of anyone; what they are matched to is in the site's code (zailiprotiv.ko).
"""
from __future__ import annotations

import io
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

STEP = 2.0             # seconds between frames
WIN, HOP = 3.0, 1.5    # seconds of sound in a window, and between windows
MIN_FACE = 40          # pixels: a smaller face is someone in the back
MODELS = Path("/modeli")


def _face_tools(size):
    import cv2
    det = cv2.FaceDetectorYN.create(str(MODELS / "yunet.onnx"), "", size, 0.8, 0.3, 50)
    rec = cv2.FaceRecognizerSF.create(str(MODELS / "sface.onnx"), "")
    return cv2, det, rec


def faces_in(img, det, rec) -> list[tuple[list[float], np.ndarray]]:
    det.setInputSize((img.shape[1], img.shape[0]))
    _, found = det.detect(img)
    out = []
    for f in found if found is not None else []:
        if min(f[2], f[3]) < MIN_FACE:
            continue
        feat = rec.feature(rec.alignCrop(img, f)).flatten()
        out.append(([float(x) for x in f[:4]] + [float(f[-1])], feat / (np.linalg.norm(feat) + 1e-9)))
    return out


def lica(out: Path, url: str) -> None:
    name = url.rsplit("/", 1)[1].removesuffix(".mp4")
    dest = out / f"{name}.lica.npz"
    if dest.exists():
        return
    import cv2
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", url, "-vf", f"fps=1/{STEP}", "-q:v", "3",
                          "-f", "image2pipe", "-c:v", "mjpeg", "-"], stdout=subprocess.PIPE)
    det = rec = None
    ts, boxes, feats, frame_size = [], [], [], None
    buf, n = b"", 0
    while True:
        chunk = p.stdout.read(1 << 16)
        if not chunk:
            break
        buf += chunk
        while True:
            a = buf.find(b"\xff\xd8")
            b = buf.find(b"\xff\xd9", a + 2)
            if a < 0 or b < 0:
                break
            img = cv2.imdecode(np.frombuffer(buf[a:b + 2], np.uint8), cv2.IMREAD_COLOR)
            buf = buf[b + 2:]
            if img is not None:
                if det is None:
                    frame_size = img.shape[:2]
                    _, det, rec = _face_tools((img.shape[1], img.shape[0]))
                for box, feat in faces_in(img, det, rec):
                    ts.append(n * STEP)
                    boxes.append(box)
                    feats.append(feat)
            n += 1
    p.wait()
    np.savez_compressed(str(dest) + ".tmp.npz", t=np.array(ts, np.float32), box=np.array(boxes, np.float32).reshape(-1, 5),
                        feat=np.array(feats, np.float32).reshape(-1, 128), frames=n,
                        size=np.array(frame_size or (0, 0)))
    Path(str(dest) + ".tmp.npz").replace(dest)
    print(name, "faces:", len(ts), "in", n, "frames", flush=True)


def glas(out: Path, url: str) -> None:
    import sherpa_onnx
    name = url.rsplit("/", 1)[1].removesuffix(".mp4")
    dest = out / f"{name}.glas.npz"
    if dest.exists():
        return
    wav = out / f"{name}.wav"
    if not wav.exists():
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", url, "-vn", "-ac", "1", "-ar", "16000",
                        str(wav) + ".part.wav"], check=True)
        Path(str(wav) + ".part.wav").replace(wav)
    ex = sherpa_onnx.SpeakerEmbeddingExtractor(sherpa_onnx.SpeakerEmbeddingExtractorConfig(
        model=str(MODELS / "glas.onnx"), num_threads=4))
    with wave.open(str(wav)) as w:
        sound = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    sr, ts, feats = 16000, [], []
    loud = np.sqrt(np.convolve(sound ** 2, np.ones(sr // 10) / (sr // 10), mode="same"))
    floor = np.percentile(loud, 20)
    for start in np.arange(0, len(sound) / sr - WIN, HOP):
        a, b = int(start * sr), int((start + WIN) * sr)
        if (loud[a:b] > 4 * floor).mean() < 0.5:  # mostly silence or the hall's noise
            continue
        s = ex.create_stream()
        s.accept_waveform(sr, sound[a:b])
        s.input_finished()
        e = np.array(ex.compute(s), np.float32)
        ts.append(start)
        feats.append(e / (np.linalg.norm(e) + 1e-9))
    np.savez_compressed(str(dest) + ".tmp.npz", t=np.array(ts, np.float32),
                        feat=np.array(feats, np.float32).reshape(-1, ex.dim))
    Path(str(dest) + ".tmp.npz").replace(dest)
    print(name, "voice windows:", len(ts), flush=True)


def portreti(folder: Path, dest: Path) -> None:
    import cv2
    det = rec = None
    names, feats = [], []
    for f in sorted(folder.glob("*.jpg")):
        img = cv2.imread(str(f))
        if img is None:
            continue
        if det is None:
            _, det, rec = _face_tools((img.shape[1], img.shape[0]))
        got = faces_in(img, det, rec)
        if got:
            names.append(f.name)
            feats.append(max(got, key=lambda g: g[0][2] * g[0][3])[1])
    np.savez_compressed(dest, files=np.array(names), feat=np.array(feats, np.float32).reshape(-1, 128))
    print("portraits with a face:", len(names), flush=True)


if __name__ == "__main__":
    what = sys.argv[1]
    if what == "portreti":
        portreti(Path(sys.argv[2]), Path(sys.argv[3]))
    else:
        out = Path(sys.argv[2])
        out.mkdir(parents=True, exist_ok=True)
        for u in sys.argv[3:]:
            (lica if what == "lica" else glas)(out, u)
