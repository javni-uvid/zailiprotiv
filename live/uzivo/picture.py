"""The picture of the moment, 1200×630: what a pasted link shows (og:image) and what "Podeli presek dana" shares.
Who is on and since when, or the day so far; under it the day's time by list in the lists' colours. Drawn with Pillow
and the DejaVu fonts of the image (Latin and Cyrillic in one file)."""
from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont

from .names import cyrillic, given_first
from .page import HEX, TEXT, _clock, _date, _dur, _name, _shades, _t, _when, headline, leaders

W, H, P = 1200, 630, 64
FG, MUTED, ZA, PROTIV, LINE = "#111111", "#555555", "#1f5fa8", "#c2410c", "#d9d9d9"
DIRS = (Path("/usr/share/fonts/truetype/dejavu"), Path("/usr/share/fonts/dejavu"), Path("/usr/share/fonts/TTF"))


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    for d in DIRS:
        if (d / name).is_file():
            return ImageFont.truetype(str(d / name), size)
    return ImageFont.load_default(size)


serif = lambda size: _font("DejaVuSerif-Bold.ttf", size)
sans = lambda size: _font("DejaVuSans.ttf", size)
bold = lambda size: _font("DejaVuSans-Bold.ttf", size)


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


def render(snap: dict, *, cyr: bool, tz: ZoneInfo, host: str = "") -> bytes:
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
