"""The picture of the moment, 1200×630: what a pasted link shows (og:image) and what "Podeli presek dana" shares.
Who is on and since when, or the day so far; under it the day's time by list in the lists' colours. Drawn with Pillow
and the DejaVu fonts of the image (Latin and Cyrillic in one file)."""
from __future__ import annotations

import io
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont

from .names import cyrillic, given_first
from .page import (_WD, HEX, TEXT, _clock, _date, _dur, _name, _said_on, _shades, _short_item, _t, _when, announcement,
                   headline, leaders, next_item)
from .texts import MONTHS

W, H, P = 1200, 630, 64
FG, MUTED, ZA, PROTIV, LINE = "#111111", "#555555", "#1f5fa8", "#c2410c", "#d9d9d9"
# the colours of the page's dark card that offers the mail (live.css, .ml-box), for the announcement
DARK, ON_DARK, SOFT, SOFT_LINE = "#111318", "#ffffff", "#c9ccd3", "#3a3f4a"
ZA_D, PROTIV_D, LIVE = "#7cc0f5", "#ff9a52", "#f87171"
# the site's own letters, Latin and Cyrillic in one file: in the image, or in the repository when run from it
OWN = (Path(__file__).parent / "static" / "og", Path(__file__).parents[1].parent / "src" / "zailiprotiv" / "og")
DIRS = (Path("/usr/share/fonts/truetype/dejavu"), Path("/usr/share/fonts/dejavu"), Path("/usr/share/fonts/TTF"))


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    for d in DIRS:
        if (d / name).is_file():
            return ImageFont.truetype(str(d / name), size)
    return ImageFont.load_default(size)


def icon(size: int, maskable: bool = False) -> bytes:
    """The page's icon for a phone's home screen: the site's own mark (favicon.svg, apple-touch-icon.png), two arcs
    of one circle, "za" blue and "protiv" orange, on white (22 Nov 2026, the maintainer: the microphone looked too
    like another's logo). A maskable icon keeps it inside the middle 60%, which every launcher's shape leaves whole.
    Drawn four times larger and scaled down, for smooth edges."""
    k = 4 * size
    img = Image.new("RGB", (k, k), "#ffffff")
    g = ImageDraw.Draw(img)
    # favicon.svg's frame (64x64): a circle of radius 23 about (32, 46), stroke 11; the mark spans x 3.5-60.5 and
    # y 17.5-51.5, set in the middle of the icon
    u = k * (0.56 if maskable else 0.74) / 57
    cx, cy = k / 2, k / 2 + (46 - 34.5) * u
    r, w = 23 * u, round(11 * u)
    box = [cx - r - w / 2, cy - r - w / 2, cx + r + w / 2, cy + r + w / 2]
    g.arc(box, start=180, end=300, fill=ZA, width=w)  # "M 9 46 A 23 23 0 0 1 43.5 26.1"
    g.arc(box, start=314, end=360, fill=PROTIV, width=w)  # "M 48 29.5 A 23 23 0 0 1 55 46"
    buf = io.BytesIO()
    img.resize((size, size), Image.LANCZOS).save(buf, "PNG", optimize=True)
    return buf.getvalue()


serif = lambda size: _font("DejaVuSerif-Bold.ttf", size)
sans = lambda size: _font("DejaVuSans.ttf", size)
bold = lambda size: _font("DejaVuSans-Bold.ttf", size)


def _literata(weight: str, size: int) -> ImageFont.FreeTypeFont:
    for d in OWN:
        if (d / f"Literata-{weight}.ttf").is_file():
            return ImageFont.truetype(str(d / f"Literata-{weight}.ttf"), size)
    return serif(size) if weight == "Bold" else sans(size)


lit = lambda size: _literata("Bold", size)
lit_text = lambda size: _literata("Regular", size)


def _fit(d: ImageDraw.ImageDraw, text: str, make, size: int, width: int, least: int = 22):
    f = make(size)
    while size > least and d.textlength(text, font=f) > width:
        size -= 2
        f = make(size)
    return f


def _wrap(d: ImageDraw.ImageDraw, text: str, font, width: int, lines: int) -> list[str]:
    out, cur = [], ""
    for word in text.split():
        if d.textlength((cur + " " + word).strip(), font=font) <= width:
            cur = (cur + " " + word).strip()
        else:
            out.append(cur)
            cur = word
    out.append(cur)
    if len(out) > lines:
        out = out[:lines]
        out[-1] = out[-1].rstrip(",.") + "…"
    return out


def _announcement(snap: dict, start, *, cyr: bool, host: str) -> bytes:
    """Before a sitting: the day as a leaf of a calendar, when, what is next and what the page gives then, with a mark
    each (23 Nov 2026, the maintainer: the link's picture to look better on Reddit). The day by its name and never
    "sutra": a service keeps a picture past midnight. Nothing looks like a button, and the top right corner is left
    empty, where Reddit puts its own. All of it in the middle, for the small pictures. Drawn twice as large and scaled down, for smooth edges."""
    k = 2
    im = Image.new("RGB", (W * k, H * k), DARK)
    d = ImageDraw.Draw(im)

    def text(x, y, s, f, size, fill, anchor="ls"):
        d.text((x * k, y * k), s, font=f(size * k), fill=fill, anchor=anchor)

    def wide(s, f, size):
        return d.textlength(s, font=f(size * k)) / k

    def box(x0, y0, x1, y1):
        return [x0 * k, y0 * k, x1 * k, y1 * k]

    def fit(s, f, size, width, least=24):
        while size > least and wide(s, f, size) > width:
            size -= 2
        return size

    # Everything stands between x = M0 and M1: Reddit's app and others show a small picture cut to its middle (4:3,
    # 840 of the 1200), with their own mark over its bottom right corner
    M0, M1 = 196, 1004
    # the mark (favicon.svg's two arcs), the name
    d.arc(box(M0, 46, M0 + 72, 118), start=180, end=300, fill=ZA_D, width=17 * k)
    d.arc(box(M0, 46, M0 + 72, 118), start=314, end=360, fill=PROTIV_D, width=17 * k)
    x = M0 + 92
    for word, color in ((("За", ZA_D), (" или ", ON_DARK), ("Против", PROTIV_D)) if cyr else
                        (("Za", ZA_D), (" ili ", ON_DARK), ("Protiv", PROTIV_D))):
        text(x, 82, word, lit, 48, color)
        x += wide(word, lit, 48)
    if host:
        text(x + 24, 82, host, lit_text, fit(host, lit_text, 28, M1 - x - 24, 18), SOFT)
    # the leaf
    x0, y0, x1, y1 = M0, 136, M0 + 236, 444
    d.rounded_rectangle(box(x0, y0, x1, y1), radius=24 * k, fill="#ffffff")
    d.rounded_rectangle(box(x0, y0, x1, y0 + 84), radius=24 * k, fill=ZA_D)
    d.rectangle(box(x0, y0 + 48, x1, y0 + 84), fill=ZA_D)
    mid = (x0 + x1) / 2
    text(mid, y0 + 43, _name(_WD[start.weekday()], cyr).upper(), lit, 50, DARK, "mm")
    text(mid, y0 + 164, str(start.day), lit, 142, DARK, "mm")
    text(mid, y0 + 264, _name(MONTHS[start.month - 1][:3], cyr).upper(), lit, 44, MUTED, "mm")
    # when ("u utorak u 10 h", never broken inside), and what is next
    left = x1 + 40
    room = M1 - left
    head, when = _t("og_sitting", cyr), _said_on(start, cyr).split(" ", 1)[1]
    text(left, 222, head, lit, fit(head, lit, 104, room), ON_DARK)
    text(left, 312, when, lit, fit(when, lit, 72, room), ON_DARK)
    nxt = next_item(snap)
    if nxt:
        rows = _wrap(d, _short_item(nxt, cyr), lit_text(34 * k), room * k, 2)
        y = 386 if len(rows) > 1 else 408
        for row in rows:
            text(left, y, row, lit_text, 34, SOFT)
            y += 44
    # what the page gives, with a mark each
    d.rectangle(box(M0, 480, M1, 482), fill=SOFT_LINE)
    size, x, cy = 46, M0, 550
    for n, key in enumerate(("og_follow", "og_listen", "og_mail")):
        b = _t(key, cyr)
        if n == 0:  # on the air
            d.ellipse(box(x, cy - 18, x + 36, cy + 18), fill=LIVE)
        elif n == 1:  # headphones
            d.arc(box(x + 2, cy - 24, x + 46, cy + 24), start=180, end=360, fill=ZA_D, width=6 * k)
            for ex in (x, x + 35):
                d.rounded_rectangle(box(ex, cy - 3, ex + 13, cy + 22), radius=5 * k, fill=ZA_D)
        else:  # an envelope
            d.rounded_rectangle(box(x, cy - 18, x + 50, cy + 18), radius=4 * k, outline=PROTIV_D, width=5 * k)
            d.line([(q * k, c * k) for q, c in ((x + 3, cy - 14), (x + 25, cy + 5), (x + 47, cy - 14))],
                   fill=PROTIV_D, width=5 * k)
        x += (36, 48, 50)[n] + 14
        text(x, cy, b, lit, size, ON_DARK, "lm")
        x += wide(b, lit, size) + 40
    out = io.BytesIO()
    im.resize((W, H), Image.LANCZOS).save(out, "PNG", optimize=True)
    return out.getvalue()


def render(snap: dict, *, cyr: bool, tz: ZoneInfo, host: str = "") -> bytes:
    when, _, start = announcement(snap)
    if when:  # before a sitting: the announcement alone, no figures of the last day (23 Nov 2026)
        return _announcement(snap, start, cyr=cyr, host=host)
    im = Image.new("RGB", (W, H), "#ffffff")
    d = ImageDraw.Draw(im)
    x = P
    for word, color in ((("За", ZA), (" или ", FG), ("Против", PROTIV)) if cyr else (("Za", ZA), (" ili ", FG), ("Protiv", PROTIV))):
        d.text((x, 40), word, font=serif(40), fill=color)
        x += d.textlength(word, font=serif(40))
    if host:
        d.text((W - P, 64), host, font=sans(26), fill=MUTED, anchor="rm")
    d.rectangle((P, 104, W - P, 107), fill=FG)
    cur = snap.get("sada") if snap.get("stanje") == "govori" else None
    turns = (snap.get("danas") or []) + ([cur] if cur else [])
    line = headline(turns, cyr=cyr, when=_when(snap, cyr))
    y = 150
    if cur:
        d.ellipse((P, y - 2, P + 22, y + 20), fill=PROTIV)
        d.text((P + 36, y + 9), _t("sh_head", cyr).upper(), font=bold(24), fill=MUTED, anchor="lm")
        name = _name(given_first(cur["ime"]), cyr)
        d.text((P, y + 44), name, font=_fit(d, name, serif, 84, W - 2 * P), fill=FG)
        side = cur.get("lista", "").strip("*") or cur.get("uloga") or cur.get("grupa") or ""
        since = f'{_t("since", cyr)} {_clock(cur["od"], tz)}'
        sub = f'{_name(side, cyr)} · {since}' if side else since
        d.text((P, y + 156), sub, font=_fit(d, sub, sans, 32, W - 2 * P), fill=MUTED)
        today = cur.get("danas")
        if today:
            bits = [_name(TEXT["d_turn"].format(n=today["n"]), cyr),
                    _name(TEXT["d_total"].format(t="%1"), cyr).replace("%1", _dur(today["sek"], cyr))]
            text = _t("h_today", cyr) + ": " + " · ".join(bits)
            d.text((P, y + 214), text, font=_fit(d, text, bold, 32, W - 2 * P), fill=FG)
    elif line:
        if snap.get("ranije") and snap.get("dan"):
            when = _date(snap["dan"])
            head = f'{_t("last_day", cyr)}, {cyrillic(when) if cyr else when}'
        else:
            head = _t("so_far", cyr)
        d.text((P, y + 9), head.upper(), font=bold(24), fill=MUTED, anchor="lm")
        f = serif(44)
        for i, row in enumerate(_wrap(d, line, f, W - 2 * P, 4)):
            d.text((P, y + 40 + i * 58), row, font=f, fill=FG)
    else:
        f = serif(64)
        for i, row in enumerate(_wrap(d, _t("title", cyr), f, W - 2 * P, 2)):
            d.text((P, y + 30 + i * 80), row, font=f, fill=FG)
        f = sans(30)
        for i, row in enumerate(_wrap(d, _t("lead", cyr), f, W - 2 * P, 3)):
            d.text((P, y + 220 + i * 42), row, font=f, fill=MUTED)
    # the day's time by list: one bar and its key
    shade = _shades(turns)
    per: dict[str, int] = {}
    for t in turns:
        per[t.get("lista") or ""] = per.get(t.get("lista") or "", 0) + max(0, t["sekundi"])
    whole = sum(per.values())
    if whole and len(turns) >= 2:
        rows = sorted(per.items(), key=lambda kv: (("*", "").index(kv[0]) + 1 if kv[0] in ("*", "") else 0, -kv[1], kv[0]))
        top, x0, x1, x = 468, P, W - P, P
        d.text((P, top - 34), _t("lists", cyr), font=bold(22), fill=MUTED)
        for k, v in rows:
            w = (x1 - x0) * v / whole
            d.rectangle((round(x), top, round(x + w) - 3, top + 36), fill=HEX.get(shade.get(k, "lx"), "#999999"))
            x += w
        x, y2 = P, top + 56
        label = lambda k: _t("no_list", cyr) if not k else _t("other_lists", cyr) if k == "*" else _name(k, cyr)
        f = sans(22)
        for k, v in rows[:4]:
            text = f"{label(k)} {round(100 * v / whole)}%"
            w = 30 + d.textlength(text, font=f) + 28
            if x + w > W - P and x > P:
                x, y2 = P, y2 + 34
            d.rectangle((x, y2 + 3, x + 20, y2 + 23), fill=HEX.get(shade.get(k, "lx"), "#999999"))
            d.text((x + 30, y2), text, font=f, fill=FG)
            x += w
    out = io.BytesIO()
    im.save(out, "PNG", optimize=True)
    return out.getvalue()


def render_tall(snap: dict, *, cyr: bool, tz: ZoneInfo, host: str = "") -> bytes:
    """The same moment upright, 1080×1920, for a phone's story (19 Nov 2026: Instagram brings visits, and the wide
    picture sits small in a story): who is on or the day's sentence, the time by list, the three with the most time."""
    TW, TH, M = 1080, 1920, 84
    im = Image.new("RGB", (TW, TH), "#ffffff")
    d = ImageDraw.Draw(im)
    x = M
    for word, color in ((("За", ZA), (" или ", FG), ("Против", PROTIV)) if cyr else (("Za", ZA), (" ili ", FG), ("Protiv", PROTIV))):
        d.text((x, 150), word, font=serif(56), fill=color)
        x += d.textlength(word, font=serif(56))
    d.rectangle((M, 240, TW - M, 245), fill=FG)
    cur = snap.get("sada") if snap.get("stanje") == "govori" else None
    turns = (snap.get("danas") or []) + ([cur] if cur else [])
    line = headline(turns, cyr=cyr, when=_when(snap, cyr))
    y = 330
    if cur:
        d.ellipse((M, y, M + 30, y + 30), fill=PROTIV)
        d.text((M + 48, y + 15), _t("sh_head", cyr).upper(), font=bold(32), fill=MUTED, anchor="lm")
        y += 80
        name = _name(given_first(cur["ime"]), cyr)
        f = serif(110)
        for row in _wrap(d, name, f, TW - 2 * M, 3):
            d.text((M, y), row, font=f, fill=FG)
            y += 128
        side = cur.get("lista", "").strip("*") or cur.get("uloga") or cur.get("grupa") or ""
        if side:
            for row in _wrap(d, _name(side, cyr), sans(40), TW - 2 * M, 2):
                d.text((M, y + 10), row, font=sans(40), fill=MUTED)
                y += 54
        y += 40
        d.text((M, y), f'{_t("since", cyr)} {_clock(cur["od"], tz)}', font=bold(52), fill=FG)
        y += 90
        today = cur.get("danas")
        if today:
            text = _t("h_today", cyr) + ": " + _name(TEXT["d_total"].format(t="%1"), cyr).replace("%1", _dur(today["sek"], cyr))
            d.text((M, y), text, font=sans(42), fill=FG)
            y += 70
    elif line:
        if snap.get("ranije") and snap.get("dan"):
            when = _date(snap["dan"])
            head = f'{_t("last_day", cyr)}, {cyrillic(when) if cyr else when}'
        else:
            head = _t("so_far", cyr)
        d.text((M, y), head.upper(), font=_fit(d, head.upper(), bold, 32, TW - 2 * M), fill=MUTED)
        y += 80
        f = serif(62)
        for row in _wrap(d, line, f, TW - 2 * M, 8):
            d.text((M, y), row, font=f, fill=FG)
            y += 80
    else:
        f = serif(84)
        for row in _wrap(d, _t("title", cyr), f, TW - 2 * M, 3):
            d.text((M, y), row, font=f, fill=FG)
            y += 104
    # the time by list
    shade = _shades(turns)
    per: dict[str, int] = {}
    for t in turns:
        per[t.get("lista") or ""] = per.get(t.get("lista") or "", 0) + max(0, t["sekundi"])
    whole = sum(per.values())
    y = max(y + 60, 1040)
    if whole and len(turns) >= 2:
        rows = sorted(per.items(), key=lambda kv: (("*", "").index(kv[0]) + 1 if kv[0] in ("*", "") else 0, -kv[1], kv[0]))
        d.text((M, y), _t("lists", cyr), font=bold(30), fill=MUTED)
        y += 56
        x = float(M)
        for k, v in rows:
            w = (TW - 2 * M) * v / whole
            d.rectangle((round(x), y, round(x + w) - 4, y + 56), fill=HEX.get(shade.get(k, "lx"), "#999999"))
            x += w
        y += 86
        label = lambda k: _t("no_list", cyr) if not k else _t("other_lists", cyr) if k == "*" else _name(k, cyr)
        for k, v in rows[:4]:
            d.rectangle((M, y + 6, M + 30, y + 36), fill=HEX.get(shade.get(k, "lx"), "#999999"))
            text = label(k)
            d.text((M + 48, y), text, font=_fit(d, text, sans, 34, TW - 2 * M - 180), fill=FG)
            d.text((TW - M, y), f"{round(100 * v / whole)}%", font=bold(34), fill=FG, anchor="ra")
            y += 56
        y += 40
        d.text((M, y), _t("totals", cyr), font=bold(30), fill=MUTED)
        y += 56
        for name, sec, _ in leaders(turns)[:3]:
            nm = _name(given_first(name), cyr)
            d.text((M, y), nm, font=_fit(d, nm, bold, 40, TW - 2 * M - 260), fill=FG)
            d.text((TW - M, y), _dur(sec, cyr), font=bold(40), fill=FG, anchor="ra")
            y += 64
    d.text((M, TH - 190), host or "zailiprotiv.rs", font=bold(40), fill=FG)
    note = _t("sh_note", cyr)
    d.text((M, TH - 130), note, font=_fit(d, note, sans, 26, TW - 2 * M), fill=MUTED)
    out = io.BytesIO()
    im.save(out, "PNG", optimize=True)
    return out.getvalue()
