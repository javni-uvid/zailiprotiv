"""The picture shown when the page of the Rules is shared (og:image; 25 Nov 2026, the maintainer's choice of three):
the Rules as an open book at the article on the reply, our retelling of it beside the book. Every word of the two is the
page's own (data/poslovnik/), as much as fits, going out of sight; no number but the articles'. Drawn at build time, in
each script, by the site's own typeface."""
from __future__ import annotations

import re
from pathlib import Path

from zailiprotiv.card import FONTS, H, W
from zailiprotiv.cyrillic import cyr
from zailiprotiv.translit import latin

VERSION = 1  # raise when the drawing changes, so cached pictures are drawn again
LAT, CIR = "poslovnik.png", "poslovnik-cir.png"  # beside the site's own picture, one for each edition
TERM = "replika"
QUESTION = "Replika: ko na nju ima pravo?"
OURS = "Kratko prepričavanje"
ADDRESS = "zailiprotiv.rs/{cir}poslovnik-clanovi"
GROUND, PAPER, EDGE, LINE, INK, SOFT, COVER, WHITE, QUIET = (
    "#16181d", "#faf7ef", "#e4dfd0", "#b9b2a0", "#141414", "#5d584d", "#454a55", "#ffffff", "#c6c8ce")
ZA, PROTIV = "#8db8ea", "#f0a06a"  # the mark's two colours, lightened for the dark ground
# The book: the spine, the pages' outer edges, their top and bottom at the spine; how far a page bows.
MID, HALF, TOP, BOTTOM, BOW = 826, 318, 86, 500, 26
K = 2  # drawn twice as large, then made smaller: smooth edges


def _bow(x: float) -> float:
    """How far up a page's edge is at x: none at the spine, a hump, a little down to the outer edge."""
    t = min(1.0, abs(x - MID) / HALF)
    return BOW * (1.9 * t ** .55 * (1 - .52 * t)) - 4


def _path(d: str, steps: int = 14) -> list[list[tuple[float, float]]]:
    """The lines of a drawn mark (rules_icons.html) as points: M, L, H, V, C and their relative forms."""
    out, at, i = [], (0.0, 0.0), 0
    tok = re.findall(r"[MmLlHhVvCc]|-?\d*\.?\d+", d)
    cmd = ""
    while i < len(tok):
        if tok[i].isalpha():
            cmd, i = tok[i], i + 1
        n = {"m": 2, "l": 2, "h": 1, "v": 1, "c": 6}[cmd.lower()]
        v, i = [float(x) for x in tok[i:i + n]], i + n
        rel = cmd.islower()
        ox, oy = at if rel else (0.0, 0.0)
        if cmd in "Mm":
            at = (ox + v[0], oy + v[1])
            out.append([at])
            cmd = "l" if rel else "L"  # a pair more after M is a line
            continue
        if cmd in "Hh":
            pts = [(ox + v[0], at[1])]
        elif cmd in "Vv":
            pts = [(at[0], oy + v[0])]
        elif cmd in "Ll":
            pts = [(ox + v[0], oy + v[1])]
        else:
            (x0, y0), p = at, [(ox + v[j], oy + v[j + 1]) for j in (0, 2, 4)]
            pts = []
            for s in range(1, steps + 1):
                t, u = s / steps, 1 - s / steps
                pts.append(tuple(u ** 3 * a + 3 * u * u * t * b + 3 * u * t * t * c + t ** 3 * e for a, b, c, e in (
                    (x0, p[0][0], p[1][0], p[2][0]), (y0, p[0][1], p[1][1], p[2][1]))))
        out[-1] += pts
        at = pts[-1]
    return out


def parts(terms: list[dict], rules: dict | None) -> tuple | None:
    """What the picture shows, from the Rules as they now read (poslovnik.terms, poslovnik.load), in Latin script: our
    retelling, the two pages of the book (the term's first article and the one before it), the term's mark. None when
    an article the retelling rests on has changed or either is gone: the page then has the site's own picture."""
    term = next((t for t in terms if t["id"] == TERM and not t["changed"] and t["articles"]), None)
    if not term or not rules:
        return None
    at = {a["n"]: a for a in rules["clanovi"]}
    two = [at.get(n) for n in (term["articles"][0]["n"] - 1, term["articles"][0]["n"])]
    icons = (Path(__file__).parent / "templates" / "rules_icons.html").read_text(encoding="utf-8")
    mark = re.search(rf'"{TERM}": \'(.*?)\'', icons)
    if not all(two) or not mark:
        return None
    return term["objasnjenje"], tuple((f"Član {a['oznaka']}", latin(" ".join(a["stavovi"]))) for a in two), mark.group(1)


def both(shown: tuple, lat: Path, cir: Path) -> None:
    """The picture for each edition."""
    retelling, two, mark = shown
    draw(lat, retelling, two, mark)
    draw(cir, cyr(retelling), [(cyr(a), cyr(b)) for a, b in two], mark, cyr, "cir/")


def draw(path: Path, retelling: str, articles: list[tuple[str, str]], mark: str, say=lambda s: s, cir: str = "") -> None:
    """`articles`: the two pages' heading and text, the left one's and the right one's; `mark`: the term's drawn mark;
    `say`: the words of this module in the picture's script (the two texts come in it already)."""
    from PIL import Image, ImageDraw, ImageFont
    fonts: dict = {}

    def font(size: float, bold: bool = False):
        return fonts.setdefault((size, bold), ImageFont.truetype(str(FONTS / f"Literata-{'Bold' if bold else 'Regular'}.ttf"), round(size * K)))

    k = lambda *xy: tuple(round(v * K) for v in xy)
    im = Image.new("RGB", (W * K, H * K), GROUND)
    d = ImageDraw.Draw(im)
    width = lambda text, f: d.textlength(text, font=f) / K

    def lines(text: str, f, wide: float) -> list[list[str]]:
        out, row = [], []
        for w in text.split():
            if row and width(" ".join(row + [w]), f) > wide:
                out.append(row)
                row = []
            row.append(w)
        return out + [row]

    def fade(box: tuple, top: float, color: str) -> None:
        """Within the box, what is under `top` goes out of sight into the colour."""
        x0, y0, x1, y1 = k(*box)
        part = Image.new("L", (1, y1 - y0))
        for y in range(y1 - y0):
            part.putpixel((0, y), max(0, min(255, round(255 * (y - (top - box[1]) * K) / max(1, (box[3] - top) * K)))))
        im.paste(Image.new("RGB", (x1 - x0, y1 - y0), color), (x0, y0), part.resize((x1 - x0, y1 - y0)))

    # The mark and the name, top left.
    d.arc(k(64, 46, 140, 122), 180, 302, fill=ZA, width=13 * K)
    d.arc(k(64, 46, 140, 122), 311, 360, fill=PROTIV, width=13 * K)
    x = 156
    for word, color in (("Za", ZA), (" ili ", WHITE), ("Protiv", PROTIV)):
        d.text(k(x, 48), say(word), font=font(40, True), fill=color)
        x += width(say(word), font(40, True))

    # Ours, beside the book: the question, then the retelling.
    y = 122
    size = next(s for s in (54, 50, 46, 42) if len(lines(say(QUESTION), font(s, True), 396)) <= 3 and max(
        width(w, font(s, True)) for w in say(QUESTION).split()) <= 396)
    for row in lines(say(QUESTION), font(size, True), 396):
        d.text(k(64, y), " ".join(row), font=font(size, True), fill=WHITE)
        y += size * 1.1
    y += 30
    d.ellipse(k(64, y, 110, y + 46), fill=WHITE)
    for sub in re.findall(r'd="([^"]+)"', mark):
        for pts in _path(sub):
            d.line([k(64 + 9 + px * 28 / 24, y + 9 + py * 28 / 24) for px, py in pts], fill=GROUND, width=round(2.4 * K), joint="curve")
    d.text(k(124, y + 23), say(OURS), font=font(27, True), fill=WHITE, anchor="lm")
    y += 56
    for row in lines(retelling, font(28), 400):
        if y > 480:
            break
        d.text(k(64, y), " ".join(row), font=font(28), fill=QUIET)
        y += 37
    fade((60, 420, 480, 560), 450, GROUND)
    d.rectangle(k(0, 516, 480, H), fill=GROUND)

    # The book: the cover, the edges of the pages under, the two pages.
    xs = [MID - HALF + i for i in range(2 * HALF + 1)]
    d.polygon([k(x, TOP - _bow(x) * .5 - 2) for x in (MID - HALF - 24, MID, MID + HALF + 24)]
              + [k(x, BOTTOM + 20 - _bow(x) * .5 + 8) for x in (MID + HALF + 24, MID, MID - HALF - 24)], fill=COVER)
    for n in range(6, 0, -1):  # the leaves under the open ones, at the sides and below
        side = [x for x in (MID - HALF - 2 * n, *xs[::6], MID + HALF + 2 * n)]
        ys = lambda x: _bow(max(MID - HALF, min(MID + HALF, x)))
        d.polygon([k(x, TOP - ys(x) + 1.5 * n) for x in side] + [k(x, BOTTOM - ys(x) + 2.2 * n) for x in reversed(side)],
                  fill=EDGE if n % 2 else PAPER, outline=LINE)
    d.polygon([k(x, TOP - _bow(x)) for x in xs] + [k(x, BOTTOM - _bow(x)) for x in reversed(xs)], fill=PAPER)
    for x2 in range(-70 * K, 70 * K):  # the shade of the gutter, between the pages
        x = MID + x2 / K
        a = max(0.0, 1 - abs(x - MID) / 70) ** 2 * .42
        paper = tuple(round(int(PAPER[i:i + 2], 16) * (1 - a) + 30 * a) for i in (1, 3, 5))
        d.line([(round(x * K), round((TOP - _bow(x)) * K)), (round(x * K), round((BOTTOM - _bow(x)) * K))], fill=paper)
    d.line(k(MID, TOP - _bow(MID), MID, BOTTOM - _bow(MID)), fill="#6e6a60", width=K)

    page = Image.new("RGBA", im.size, (0, 0, 0, 0))
    p = ImageDraw.Draw(page)

    def put(text: str, x: float, y: float, f, color: str) -> None:
        """A word on the bowed page: each letter at its own height, so that the line bends with the paper."""
        for i, c in enumerate(text):
            at = x + width(text[:i], f)
            p.text(k(at, y - _bow(at + 4)), c, font=f, fill=color)

    heads = (say("Poslovnik"), say("Narodne skupštine"))
    top = next(s for s in (28, 27, 26, 25, 24, 23, 22) if max(width(h, font(s, True)) for h in heads) <= HALF - 64)
    for side, (head, (title, text)) in enumerate(zip(heads, articles)):
        left = MID - HALF + 30 if not side else MID + 34
        wide = HALF - 64
        middle = left + wide / 2
        f = font(top, True)
        put(head, middle - width(head, f) / 2, TOP + 20, f, INK)
        for i in range(round(wide)):
            p.line([k(left + i, TOP + 60 - _bow(left + i)), k(left + i + 1, TOP + 60 - _bow(left + i + 1))], fill=LINE, width=2 * K)
        f = font(25, True)
        put(title, middle - width(title, f) / 2, TOP + 74, f, SOFT)
        f, y = font(21), TOP + 114
        for row in lines(text, f, wide):
            if y > BOTTOM - 40:
                break
            put(" ".join(row), left, y, f, INK if side else SOFT)
            y += 28
    im.paste(page, (0, 0), page)
    for x in range(MID - HALF + 4, MID + HALF - 3):  # the text goes out of sight at the foot of the page
        if abs(x - MID) < 34:
            continue
        for s in range(0, 64):
            a = min(1.0, s / 52)
            yy = BOTTOM - 66 + s - _bow(x)
            for dx in range(K):
                for dy in range(K):
                    px = (round(x * K) + dx, round(yy * K) + dy)
                    was = im.getpixel(px)
                    g = max(0.0, 1 - abs(x - MID) / 70) ** 2 * .42
                    to = tuple(int(PAPER[i:i + 2], 16) * (1 - g) + 30 * g for i in (1, 3, 5))
                    im.putpixel(px, tuple(round(w * (1 - a) + t * a) for w, t in zip(was, to)))

    d = ImageDraw.Draw(im)
    address = ADDRESS.format(cir=cir)
    d.text(k(64, 594), address, font=font(54, True), fill=WHITE, anchor="ls")
    im.resize((W, H), Image.LANCZOS).quantize(256, kmeans=1).save(path, optimize=True)
