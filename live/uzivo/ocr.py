"""Reading the caption off a frame: cut out its place, keep the white letters, and let Tesseract read them."""
from __future__ import annotations

import numpy as np
import pytesseract
from PIL import Image, ImageFilter

from . import config
from .caption import Caption, Word, read


def crop(frame: Image.Image) -> Image.Image:
    w, h = frame.size
    return frame.crop((
        int(w * config.CROP_LEFT), int(h * config.CROP_TOP),
        int(w * min(1.0, config.CROP_LEFT + config.CROP_WIDTH)), int(h * min(1.0, config.CROP_TOP + config.CROP_HEIGHT)),
    ))


def letters(part: Image.Image) -> Image.Image:
    """The caption is thin white text over the picture. Keep the pixels that are near white and stand out from what
    is right around them (a white top-hat), so white shirts and papers behind the text drop out. Black on white."""
    gray = part.convert("L")
    scale = max(1, round(1400 / max(1, gray.width)))
    if scale > 1:
        gray = gray.resize((gray.width * scale, gray.height * scale), Image.LANCZOS)
    k = max(5, gray.height // 14) | 1  # a little wider than a letter's stroke
    opened = gray.filter(ImageFilter.MinFilter(k)).filter(ImageFilter.MaxFilter(k))
    arr = np.asarray(gray).astype(np.int16)
    mask = (arr >= config.WHITE_THRESHOLD) & (arr - np.asarray(opened).astype(np.int16) >= config.TOPHAT_MIN)
    return Image.fromarray(np.where(mask, 0, 255).astype(np.uint8))


def lines(img: Image.Image) -> list[list[Word]]:
    """Tesseract's words grouped into lines, top to bottom."""
    d = pytesseract.image_to_data(img, lang=config.OCR_LANG, config="--psm 6", output_type=pytesseract.Output.DICT)
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
