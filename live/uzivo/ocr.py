"""Reading the caption off a frame: cut out its place, keep the white letters, and let Tesseract read them."""
from __future__ import annotations

import re

import numpy as np
import pytesseract
from PIL import Image, ImageFilter

from . import config
from .caption import Caption, Word, read


# Seconds for one reading by tesseract, which has no limit of its own (a frame with all its readings takes about one; the longest
# turn of the loop on 24 and 25 Nov 2026 was 11 s). Past it tesseract is killed and RuntimeError raised: the frame is not
# read (worker.run), and with none read for STALE_SECONDS nobody is shown as speaking.
LIMIT = 10


def crop(frame: Image.Image) -> Image.Image:
    w, h = frame.size
    return frame.crop((
        int(w * config.CROP_LEFT), int(h * config.CROP_TOP),
        int(w * min(1.0, config.CROP_LEFT + config.CROP_WIDTH)), int(h * min(1.0, config.CROP_TOP + config.CROP_HEIGHT)),
    ))


def letters(part: Image.Image, scale: int = 0) -> Image.Image:
    """The caption is thin white text over the picture. Keep the pixels that are near white and stand out from what
    is right around them (a white top-hat), so white shirts and papers behind the text drop out. Black on white."""
    gray = part.convert("L")
    scale = scale or max(1, round(1400 / max(1, gray.width)))
    if scale > 1:
        gray = gray.resize((gray.width * scale, gray.height * scale), Image.LANCZOS)
    k = max(5, gray.height // 14) | 1  # a little wider than a letter's stroke
    opened = gray.filter(ImageFilter.MinFilter(k)).filter(ImageFilter.MaxFilter(k))
    arr = np.asarray(gray).astype(np.int16)
    mask = (arr >= config.WHITE_THRESHOLD) & (arr - np.asarray(opened).astype(np.int16) >= config.TOPHAT_MIN)
    return Image.fromarray(np.where(mask, 0, 255).astype(np.uint8))


def lines(img: Image.Image) -> list[list[Word]]:
    """Tesseract's words grouped into lines, top to bottom."""
    d = pytesseract.image_to_data(img, lang=config.OCR_LANG, config="--psm 6", output_type=pytesseract.Output.DICT,
                                  timeout=LIMIT)
    rows: dict[tuple, list[tuple[str, float, int]]] = {}
    for i, w in enumerate(d["text"]):
        w = w.strip()
        if w:
            rows.setdefault((d["block_num"][i], d["par_num"][i], d["line_num"][i]), []).append(
                (w, float(d["conf"][i]), d["top"][i]))
    ordered = sorted(rows.values(), key=lambda ws: min(t for _, _, t in ws))
    return [[(w, c) for w, c, _ in ws] for ws in ordered]


def caption(frame: Image.Image) -> Caption:
    return read(lines(letters(crop(frame))), config.CLEAN_CONF)


def outlined(frame: Image.Image) -> list[Caption]:
    """The caption of 24 Nov 2026, where it stands then (higher, and its letters ringed): the light ring is thinner
    than a letter's stroke, so an opening of the mask takes it off. Read at two sizes, as Tesseract errs apart at
    each; the caller keeps only a sitting MP whose list is under the name (`caption.sure`)."""
    w, h = frame.size
    part = frame.crop((int(w * config.CROP_LEFT), int(h * config.OUTLINED_TOP),
                       int(w * min(1.0, config.CROP_LEFT + config.OUTLINED_WIDTH)),
                       int(h * min(1.0, config.OUTLINED_TOP + config.OUTLINED_HEIGHT))))
    mask = letters(part, max(1, round(3 * 480 / max(1, h)))).filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MinFilter(5))
    half = mask.resize((mask.width // 2, mask.height // 2), Image.LANCZOS)
    return [read(lines(m), config.CLEAN_CONF) for m in (half, mask)]


def clock(frame: Image.Image) -> int | None:
    """The seconds the broadcast's clock shows beside the caption ("0:15", 24 Nov 2026): the same in two readings of
    the four (two thresholds, two sizes), else None. Checked on 120 frames: 36 readings, none wrong."""
    w, h = frame.size
    x0, y0, x1, y1 = config.CLOCK_BOX
    part = frame.crop((int(w * x0), int(h * y0), int(w * x1), int(h * y1))).convert("L")
    part = part.resize((part.width * 4, part.height * 4), Image.LANCZOS)
    arr = np.asarray(part)
    seen: dict[int, int] = {}
    for low in (215, 235):
        mask = Image.fromarray(np.where(arr >= low, 0, 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MinFilter(5))
        for img in (mask, mask.resize((mask.width // 2, mask.height // 2), Image.LANCZOS)):
            text = pytesseract.image_to_string(img, lang="eng", config="--psm 7 -c tessedit_char_whitelist=0123456789:",
                                               timeout=LIMIT).strip()
            m = re.fullmatch(r"(\d{1,2}):([0-5]\d)", text)
            if m:
                sec = int(m.group(1)) * 60 + int(m.group(2))
                seen[sec] = seen.get(sec, 0) + 1
    best = max(seen, key=seen.get, default=None)
    return best if best is not None and seen[best] >= 2 else None

