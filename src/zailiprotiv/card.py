"""The picture shown when a law's page is shared (og:image): its name, the day and the final vote. Drawn at build
time with the site's own typeface, so nothing comes from another server."""
from __future__ import annotations

from pathlib import Path

W, H, PAD = 1200, 630, 72
FG, MUTED, ZA, PROTIV, PROTIV_BAR, REST = "#111111", "#555555", "#1f5fa8", "#c2410c", "#e0782f", "#e8e8e8"
FONTS = Path(__file__).parent / "og"


def wrap(draw, text: str, font, width: int, lines: int) -> list[str]:
    out, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=font) <= width:
            line = trial
            continue
        out.append(line)
        line = word
        if len(out) == lines:
            break
    else:
        out.append(line)
        return out
    out[-1] = out[-1].rstrip(" ,:;") + " …"
    return out


def draw(path: Path, title: str, when: str, counts: dict, note: str = "") -> None:
    from PIL import Image, ImageDraw, ImageFont
    bold = lambda size: ImageFont.truetype(str(FONTS / "SourceSerif4-Bold.ttf"), size)
    regular = lambda size: ImageFont.truetype(str(FONTS / "SourceSerif4-Regular.ttf"), size)
    im = Image.new("RGB", (W, H), "#ffffff")
    d = ImageDraw.Draw(im)
    x = PAD
    for word, color in (("Za", ZA), (" ili ", FG), ("Protiv", PROTIV)):  # the masthead
        d.text((x, 52), word, font=bold(40), fill=color)
        x += d.textlength(word, font=bold(40))
    d.line((PAD, 116, W - PAD, 116), fill=FG, width=4)
    d.text((PAD, 140), when + (f" · {note}" if note else ""), font=regular(30), fill=MUTED)
    size = 68 if len(title) <= 60 else 54
    y = 190
    for line in wrap(d, title, bold(size), W - 2 * PAD, 3):
        d.text((PAD, y), line, font=bold(size), fill=FG)
        y += int(size * 1.16)
    za, protiv, total = counts["za"], counts["protiv"], sum(counts.values()) or 1
    x = PAD
    for text, font, color in ((str(za), bold(84), ZA), (" za", regular(40), ZA), ("   ", regular(40), FG),
                              (str(protiv), bold(84), PROTIV), (" protiv", regular(40), PROTIV)):
        d.text((x, 520), text, font=font, fill=color, anchor="ls")
        x += d.textlength(text, font=font)
    bar_y, full = 548, W - 2 * PAD
    d.rectangle((PAD, bar_y, W - PAD, bar_y + 22), fill=REST)
    a = round(full * za / total)
    d.rectangle((PAD, bar_y, PAD + a, bar_y + 22), fill=ZA)
    d.rectangle((PAD + a, bar_y, PAD + a + round(full * protiv / total), bar_y + 22), fill=PROTIV_BAR)
    im.quantize(48).save(path)  # a few flat colours: a fifth of the size
