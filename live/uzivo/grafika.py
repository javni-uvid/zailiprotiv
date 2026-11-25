"""The broadcast's own graphic over the picture (25 Nov 2026): a blue oval with the Assembly's building, and its address. It
stands in a break, before a sitting and after its end, always the same and with no word of which, so it says nothing by
itself (state.Tracker.screen). Told by how much of the picture's middle is blue; nothing is read in it."""
from __future__ import annotations

from PIL import Image

BOX = (30, 10, 130, 70)  # the middle of the frame made 160 x 90


def blue(frame: Image.Image) -> float:
    """The share of the frame's middle that is blue. In 4,226 frames of 24 and 25 Nov 2026 (one each ten seconds): 0.34 to
    0.45 with the graphic, at most 0.13 without; a frame of the stream's size takes about a millisecond."""
    small = frame.convert("RGB").resize((160, 90), Image.BOX).crop(BOX)
    p = small.tobytes()
    n = sum(1 for i in range(0, len(p), 3) if p[i + 2] > p[i] + 35 and p[i + 2] > p[i + 1] + 25)
    return n / (small.width * small.height)
