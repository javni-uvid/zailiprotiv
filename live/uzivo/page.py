"""The page, in Latin and in Cyrillic, from the tracker's snapshot. Only the standard library: the repository's tests
render it. The page loads nothing from elsewhere: the fonts are served with it, the one script is inline."""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timedelta
from html import escape
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

from . import config
from .deljenje import turn_at
from .names import cyrillic, given_first, latin
from .prenosi import place
from .steps import STEP_TITLES, steps_shown
from .texts import MONTHS, MONTHS_OF, TEXT, WEEKDAYS, _fill, _name, _t  # noqa: F401


# A bell, and the mark Safari's "Podeli" has (a box with an arrow up), drawn as lines in the text's colour.
BELL = ('<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 16.5V11a6 6 0 0 1 12 0v5.5l1.6 2H4.4z"/><path d="M10 21h4"/>'
        '<path d="M12 5V3"/></svg>')
BOOK = ('<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 4h10a4 4 0 0 1 4 4v12H8a3 3 0 0 1-3-3z"/><path d="M5 17a3 3 0 0 1 3-3h11"/></svg>')
SHARE = ('<svg class="ic-share" viewBox="0 0 24 24" aria-hidden="true"><path d="M8 9H6v12h12V9h-2"/><path d="M12 15V3"/>'
         '<path d="M8.5 6.5 12 3l3.5 3.5"/></svg>')
ARC = ('<svg class="brand-mark" viewBox="0 0 120 76" aria-hidden="true"><path class="m-za" d="M 14 66 A 46 46 0 0 1 83 26.2"/>'
       '<path class="m-protiv" d="M 89.6 30.8 A 46 46 0 0 1 106 66"/></svg>')


def _brand(cyr: bool) -> str:
    words = ('<span class="w-za">За</span> или <span class="w-protiv">Против</span>' if cyr
             else '<span class="w-za">Za</span> ili <span class="w-protiv">Protiv</span>')
    return ARC + f"<span>{words}</span>"


def _clock(ts: int, tz: ZoneInfo) -> str:
    return datetime.fromtimestamp(ts, tz).strftime("%H:%M")


def _minutes(sec: int) -> str:
    return str(max(1, round(sec / 60)))


def _date(day: str) -> str:
    y, m, d = (int(x) for x in day.split("-"))
    return f"{d}. {MONTHS[m - 1]} {y}."


def _hms(sec: int) -> str:
    h, m, s = sec // 3600, sec % 3600 // 60, sec % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _turn(d: dict, snap: dict, *, cyr: bool, site: str, tz: ZoneInfo, share: str = "", more: str = "",
          anchor: str = "") -> str:
    """A turn in the day's list (24 Nov 2026, the maintainer's choice of three): the portrait, the name, how long, the line
    on its topic, and the moment it began as a button that plays it. The site's day pages draw theirs with it too
    (pages_govornici, 27 Nov 2026): `share` the speech's own link there ("#govor-<second>"), `more` what they add under
    the line (a point of order, the automatic transcript), `anchor` the row's id ("g<second>" there, "t<second>" here)."""
    t = lambda k: escape(_t(k, cyr))
    name = escape(_name(given_first(d["ime"]), cyr))
    nm = f'<a href="{escape(site + ("cir/" if cyr else "") + "poslanik/" + d["adresa"])}">{name}</a>' if d["adresa"] else name
    side = d["uloga"] or d["grupa"] or d.get("lista") or ""
    side = side if side != "*" else ""
    foto = d.get("foto") or ""
    if foto and str(foto).replace(".", "").replace("-", "").isalnum():
        face = f'<img class="tf" src="{escape(site)}foto/{escape(foto)}" width="44" height="44" alt="" loading="lazy">'
    else:
        face = f'<span class="tf" aria-hidden="true">{escape(cyrillic("".join(w[:1] for w in given_first(d["ime"]).split()[:2])) if cyr else "".join(w[:1] for w in given_first(d["ime"]).split()[:2]))}</span>'
    if d.get("snimak") is not None and (d.get("datoteka") or d.get("video")):  # its own place, in its own video or file
        href = f'{d["datoteka"]}#t={d["snimak"]}' if d.get("datoteka") else f'https://www.youtube.com/watch?v={d["video"]}&t={d["snimak"]}s'
        data = f'data-file="{escape(d["datoteka"])}"' if d.get("datoteka") else f'data-yt="{escape(d["video"])}"'
        play = (f'<a class="time" href="{escape(href)}" {data} data-t="{int(d["snimak"])}" title="{escape(_t("recording_title", cyr))}">'
                f'{_clock(d["od"], tz)}</a>')
    else:
        play = _moment(snap, d["od"], _clock(d["od"], tz), cyr)
    play = play.replace('class="time"', 'class="time tp"', 1).replace(">" + _clock(d["od"], tz) + "<", f">▶ {_clock(d['od'], tz)}<", 1) if "href" in play else f'<span class="time tp">{_clock(d["od"], tz)}</span>'
    how = f' · {t("by_short_" + d["izvor"])}' if d.get("izvor") in ("glas", "prepis") else ""
    said = f' · <a class="said" href="{"/cir" if cyr else ""}/prepis#t{int(d["od"])}">{t("said_link")}</a>' if d.get("reci") else ""
    topic = f'<p class="rz">{escape(_name(d["rezime"], cyr))}</p>' if d.get("rezime") else ""
    shade = LIST_COLOURS.get(d.get("lista") or "", "l1")
    # the speech's own link (25 Nov 2026, the maintainer; deljenje.py): the same beside every finished speech
    share = (f'<button type="button" class="share-turn" data-share="{escape(share or ("/cir" if cyr else "") + "/govor/" + str(int(d["od"])))}">'
             f'{SHARE}<span>{t("sp_share")}</span></button>')
    # what the card needs while the turn's recording plays (mikrofon.js, 26 Nov 2026): the MP's address, the list's
    # colour, a point of order's articles ("" for one with none; no attribute for none)
    point = d.get("povreda")
    card = (f' data-adresa="{escape(d["adresa"])}"' if d["adresa"] else "") + f' data-lc="{shade}"' + (
        f' data-povreda="{",".join(str(int(n)) for n in point if str(n).isdigit())}"' if isinstance(point, list) else "")
    return (f'<li id="{escape(anchor) if anchor else "t" + str(int(d["od"]))}" data-od="{int(d["od"])}" data-do="{int(d["do"])}" data-ime="{escape(d["ime"])}" data-strana="{escape(_name(side, cyr))}"{card}>'
            f'<span class="tf-w {shade}">{face}</span>'
            f'<div class="tm"><p class="tn"><span class="ko">{nm}</span> <span class="meta">{_minutes(d["sekundi"])} {t("min")}</span></p>{topic}'
            f'<p class="ts meta">{escape(_name(side, cyr))}{how}{said} {share}</p>{more}</div>{play}</li>')


def _by_hour(turns: list[dict], rows: list[str], a: int, b: int, tz: ZoneInfo, cyr: bool) -> str:
    """The rows `a` to `b` under the hour each began in ("16 h"), in the list's own order."""
    out, last = ['<ol class="turns">'], None
    for d, row in list(zip(turns, rows))[a:b]:
        hour = datetime.fromtimestamp(d["od"], tz).hour
        if hour != last:
            out.append(f'<li class="th">{hour} {"ч" if cyr else "h"}</li>')
            last = hour
        out.append(row)
    return "".join(out) + "</ol>"


def _recording(d: dict, cyr: bool) -> str:
    """A link to the turn's place in the recording, where the record knows it: in a file of the broadcaster's archive
    (`datoteka`, a day read from the recording) or in the YouTube video of the live broadcast."""
    if d.get("snimak") is None or not (d.get("datoteka") or d.get("video")):
        return ""
    href = escape(f'{d["datoteka"]}#t={d["snimak"]}' if d.get("datoteka") else
                  f'https://www.youtube.com/watch?v={d["video"]}&t={d["snimak"]}s')
    # The page's player opens it in place on a click (data-*); without the script the link opens the recording.
    data = (f'data-file="{escape(d["datoteka"])}"' if d.get("datoteka") else f'data-yt="{escape(d["video"])}"')
    data += f' data-t="{int(d["snimak"])}"' 
    return (f' <a class="rec" href="{href}" {data}title="{escape(_t("recording_title", cyr))}">▶ '
            f'{escape(_t("recording", cyr))} {_hms(d["snimak"])}</a>')


def _moment(snap: dict, at: float, text: str, cyr: bool) -> str:
    """A time of the day as a link to that moment: of the broadcast on now (YouTube's video) or of the day's recording
    in the archive; the time alone when neither holds it."""
    on = snap.get("prenos") or {}
    if on.get("video") and snap.get("stanje") != "nema_prenosa" and at >= on.get("od", 0):
        sec = int(at - on["od"])
        href, data = f'https://www.youtube.com/watch?v={on["video"]}&t={sec}s', f'data-yt="{escape(on["video"])}"'
    else:
        part = next((p for p in snap.get("datoteke") or [] if p["od"] <= at < p["od"] + p["trajanje"]), None)
        still = None if part else place(snap.get("otvoreno") or [], at)  # the broadcast over, its video still public
        if still:
            sec = still["snimak"]
            href, data = f'https://www.youtube.com/watch?v={still["video"]}&t={sec}s', f'data-yt="{escape(still["video"])}"'
        elif not part:
            return f'<span class="time">{escape(text)}</span>'
        else:
            sec = int(at - part["od"])
            href, data = f'{part["url"]}#t={sec}', f'data-file="{escape(part["url"])}"'
    return f'<a class="time" href="{escape(href)}" {data} data-t="{sec}" title="{escape(_t("recording_title", cyr))}">{escape(text)}</a>'


TURNS_SHOWN = 8  # of a day's turns, the latest this many are listed open; the earlier ones are folded under them


def fragment(snap: dict, *, cyr: bool, site: str, tz: ZoneInfo, sent: bool = False, off: bool = False) -> str:
    """The part of the page that changes: who speaks now, and today's turns. `off`: the site's copy shown while this
    service is down (page's `off`)."""
    t = lambda k: escape(_t(k, cyr))
    if not config.SHOW_TRANSCRIPT:  # the transcript is written down but not shown (config.SHOW_TRANSCRIPT)
        bare = lambda d: {k: v for k, v in d.items() if k not in ("prepis", "reci")}
        snap = {**snap, "bez_potpisa": None, "sada": bare(snap["sada"]) if snap.get("sada") else snap.get("sada"),
                "danas": [bare(d) for d in snap.get("danas") or []]}
    cur = snap.get("sada")
    # The speaker's list's colour on the speaker, the line on top and the dot (22 Nov 2026, the maintainer's choice:
    # more colour, where it means something): the same shade as in the day's bars, a key (the list's name) beside it.
    lc = ""
    if snap["stanje"] == "govori" and cur:
        lc = f' class="lc-{_shades((snap.get("danas") or []) + [cur]).get(cur.get("lista") or "", "lx")}"'
    shown_day = ""
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(snap.get("dan", ""))):  # the day of the list, for the card of a recording
        y_, m_, d_ = (int(x) for x in snap["dan"].split("-"))
        shown_day = f' data-dan-ime="{escape(_name(f"{d_}. {MONTHS_OF[m_ - 1]}", cyr))}"'
    out = [f'<div id="deo"{lc} data-checked="{snap["provereno"]}" data-stanje="{escape(snap.get("stanje", ""))}"{shown_day}{_mail_attrs(snap, sent, tz)}>', _status(snap, cyr=cyr, off=off)]
    # On the page in this order (the styles' `order`): who is on, the broadcast, the box about the speaker, what is
    # being said, the day. The name and the picture come first on a phone, 86% of the visits (19 Nov 2026).
    for n in sorted(snap.get("obavestenja") or [], key=lambda n: str(n.get("od", "")))[-1:]:
        start = _resume_start(n)
        if _resumes(n.get("tekst", "")) and (snap["stanje"] == "nema_prenosa" or (start and _now() >= start)):
            continue  # said by the card on top (_status), or its hour has come: no news while the sitting is on  # the newest of what the Assembly has decided, as its own site says it (the site's data/obavestenja.json)
        text = escape(_name(n["tekst"], cyr))
        more = ""
        if str(n.get("url", "")).startswith("https://"):
            more += f' <a href="{escape(n["url"])}">{escape(_name(n.get("izvor") or "izvor", cyr))}</a>'
        if n.get("adresa") and str(n["adresa"]).replace("-", "").isalnum():
            more += f' · <a href="{escape(site + ("cir/" if cyr else "") + "poslanik/" + n["adresa"])}">{t("news_page")}</a>'
        out.append(f'<p class="news"><b>{t("news")}</b> {text}{more}</p>')
    out.append(_agenda(snap, cyr=cyr))
    out.append('<section class="sp-top">')
    said = ""
    if snap["stanje"] == "govori" and cur:
        under_way = next((x for x in (snap.get("dnevni_red") or {}).get("tacke") or [] if x.get("stanje") == "u_toku"), None)
        head, box, said = _speaker(cur, cyr=cyr, site=site, tz=tz, item=under_way)
        out.append(head + '</section><section class="sp">' + box)
        above = head + box
    else:
        above = ""
        if snap["stanje"] == "nema_prenosa":  # the line on top says so ("Ne zaseda")
            # the card on top says when; the countdown stands where it lists a sitting's agenda, or no hour is known
            top = announcement(snap)[1].get("sazvano")
            above = "" if top and not top.get("tacke") else countdown(snap, cyr=cyr, tz=tz)
        elif snap["stanje"] != "nepoznato":
            above = f'<p class="state">{t("none")}</p>'
        out.append(above)
        pause = _break(snap, cyr=cyr, tz=tz) + _pause(snap, cyr=cyr, tz=tz, site=site)
        out.append('</section><section class="sp">' + pause)
        above += pause
    if snap["provereno"] and above:  # when it was checked, of what stands above it; with nothing there it says nothing
        out.append(f'<p class="meta" id="checked">{t("checked")} <span>0</span> {t("s")}</p>')
    if not said and snap.get("bez_potpisa"):  # nobody's caption on: the chair's words (or the hall's), named as no one's
        u = snap["bez_potpisa"]
        tail = u["tekst"]
        tail = ("… " + tail.split(" ", 1)[-1]) if len(tail) >= 400 else tail
        said = (f'<div class="said-now"><p class="src">{t("said_unsigned")}</p><p>{escape(_name(tail, cyr))}</p>'
                f'<p class="meta"><a href="{"/cir" if cyr else ""}/prepis">{t("said_all")} →</a></p></div>')
    if snap.get("titl"):  # the line under the picture: its newest lines, for the script (prepis.Captions)
        out.append('<ol class="cc-src" hidden>' + "".join(
            f'<li data-od="{c["od"]}"{f' data-pt="{c["pt"]}"' if c.get("pt") else ""}>{escape(_name(c["tekst"], cyr))}</li>'
            for c in snap["titl"]) + "</ol>")
    out.append("</section>" + (_group_time(snap, cyr=cyr, tz=tz) if config.SHOW_GROUP_TIME else ""))
    out.append(f'<section class="said-sec">{said}</section>{_steps(snap, cyr=cyr, tz=tz, site=site)}<section class="day">')
    if snap.get("ranije") and snap["danas"]:
        when = _date(snap["dan"])
        chip = _chip(t("dl_recording"), t("from_recording")) if snap.get("snimak") else ""
        out.append(f'<div class="sec-h"><h2>{t("last_day")}, {escape(cyrillic(when) if cyr else when)}</h2>{chip}</div>')
    elif not snap["danas"]:  # with turns the list says itself (24 Nov 2026, the maintainer: no "Danas su govorili" over three tiles)
        out.append(f'<h2>{t("today")}</h2>')
    if snap["danas"]:
        every = snap["danas"] + ([cur] if snap["stanje"] == "govori" and cur else [])
        shade = _shades(every)  # the headline, the day in cards and its strip are off (24 Nov 2026, the maintainer)
        chip_ = _chip(t("dl_src"), t("rz_src")) if any(d.get("rezime") for d in snap["danas"]) else ""
        out.append(f'<div class="sec-h"><h2>{t("all_turns")}</h2>{chip_}</div>')
        rows = [_turn(d, snap, cyr=cyr, site=site, tz=tz) for d in snap["danas"]]
        # A long day's list was half the page on a phone: the latest turns stand (the list is newest first), the
        # earlier ones open on a tap, and by themselves when an address leads to one of them (the script's `unfold`).
        fold = len(rows) > TURNS_SHOWN + 4
        out.append(_by_hour(snap["danas"], rows, 0, TURNS_SHOWN if fold else len(rows), tz, cyr))
        if fold:
            out.append(f'<details class="turns-more" id="raniji-govori"><summary>{t("turns_earlier")} ({len(rows) - TURNS_SHOWN})</summary>'
                       f'{_by_hour(snap["danas"], rows, TURNS_SHOWN, len(rows), tz, cyr)}</details>')
        out.append(_totals(every, cyr=cyr, site=site, shade=shade))
        where = f'{site}{"cir/" if cyr else ""}'
        more = [f'<a href="{escape(where)}govornici">{t("conv_page")} →</a>']
        if snap.get("snimak") and snap.get("dan"):  # a day read from the recording has its page on the site
            more.insert(0, f'<a href="{escape(where)}govornici/{escape(snap["dan"])}">{t("day_page")} →</a>')
        out.append('<p class="more">' + " · ".join(more) + "</p>")
    else:
        out.append(f'<p class="meta">{t("today_none")}</p>')
    out.append("</section></div>")
    return "\n".join(out)



def _status(snap: dict, *, cyr: bool, off: bool = False) -> str:
    """The first line of the page (22 Nov 2026, the maintainer's choice: the first screen says what is now): whether
    the Assembly sits ("Uživo", while the broadcast is on) or not, and the agenda's item under way or next."""
    t = lambda k: escape(_t(k, cyr))
    if off:  # the site's copy while this service is down: whether the Assembly sits is not known then (27 Nov 2026)
        return f'<div class="status"><p><span class="pill off">{t("status_down")}</span></p></div>'
    items = (snap.get("dnevni_red") or {}).get("tacke") or []
    word = t("status_break" if _paused(snap) else "status_live")  # "Pauza" while a break is known (25 Nov 2026, the maintainer)
    off = snap["stanje"] == "nema_prenosa"  # nothing is under way then, whatever was heard last (25 Nov 2026)
    on = (next((x for x in items if x.get("stanje") == "u_toku" and not off), None)
          or next((x for x in items if x.get("stanje") == "na_redu"), None))
    if off:
        pill = f'<span class="pill off">{t("status_off")}</span>'
    else:
        pill = f'<span class="pill"><i aria-hidden="true"></i>{word}</span>'
    what = ""
    if on:
        what = (f'<span class="status-on">{t("ag_now" if on["stanje"] == "u_toku" else "ag_next")}: '
                f'{on["n"]}. {escape(_name(on["tekst"], cyr))}</span>')
    chair = snap.get("predsedava") if snap["stanje"] != "nema_prenosa" else None
    if chair and chair.get("ime"):  # who presides, by the voice (22 Nov 2026); how is under "Kako ovo radi" (24 Nov)
        what += f'<span class="status-chair">{t("presides")}: {escape(_name(given_first(chair["ime"]), cyr))}</span>'
    words, notice, start = announcement(snap)
    if start:  # the sitting's card: the day as a leaf of a calendar, when, what is next (23 Nov 2026, the maintainer's
        # choice of three); the bell presses the notification's own button (live.js), shown while that one would be
        src = (f'<p class="st-src"><a href="{escape(notice["url"])}">{t("steps_site")} ↗</a></p>'
               if str(notice.get("url", "")).startswith("https://") else "")
        rest = announced_items(snap)[:2]
        lines = "".join(f'<li>{escape(_short_item(x, cyr))}</li>' for x in rest)
        month = MONTHS[start.month - 1][:3]
        return (f'<div class="status st-card"><p class="st-tile" aria-hidden="true"><span>{escape(_name(_WD[start.weekday()], cyr))}</span>'
                f'<b>{start.day}</b><span>{escape(_name(month, cyr))}</span></p><div class="st-in">'
                f'<p class="st-when" title="{escape(_name(_says(words, notice), cyr))}.">{escape(_said_soon(start, cyr))}</p>'
                f'{f"<ul>{lines}</ul>" if lines else ""}{src}</div>'
                f'<button type="button" class="st-bell">{BELL}<span>{t("st_bell")}</span></button></div>')
    if on and snap["stanje"] != "nema_prenosa":  # on the air: the same card, the tile says so
        head = f'{t("ag_now" if on["stanje"] == "u_toku" else "ag_next")}:'
        chair_ = what[what.index('<span class="status-chair">'):] if "status-chair" in what else ""
        return (f'<div class="status st-card st-live"><p class="st-tile"><i aria-hidden="true"></i><span>{word}</span></p>'
                f'<div class="st-in"><p class="st-when"><span class="st-h">{head}</span> {escape(_short_item(on, cyr))}</p>{chair_}</div></div>')
    return f'<div class="status"><p>{pill}{what}</p></div>'


def _agenda(snap: dict, *, cyr: bool) -> str:
    """The sitting's agenda under the broadcast, folded to one line (how many items are done, which is on), the
    items with their state when opened: done by the Assembly's page, done or under way by what the chair said, or
    next in turn (state._agenda). Each state says where it is from."""
    a = snap.get("dnevni_red")
    if not a or not a.get("tacke"):
        return ""
    t = lambda k: escape(_t(k, cyr))
    s = lambda x: escape(_name(x, cyr))
    items = a["tacke"]
    done = sum(1 for x in items if x["stanje"] == "gotova")
    head = f'<b>{t("ag")}</b> <span>{escape(_fill(_t("ag_done", cyr), done, len(items)))}</span>'  # what is on: the line on top
    rows = []
    for x in items:
        if x["stanje"] == "u_toku" and snap["stanje"] == "nema_prenosa":  # not under way while the Assembly is not sitting
            x = {**x, "stanje": ""}
        mark = {"gotova": "✓", "u_toku": "●", "na_redu": "→"}.get(x["stanje"], "")
        state = ""
        if x["stanje"] == "gotova":  # the ✓ says done; the label under the list says by whose word (22 Nov 2026: shorter)
            when = _date(x["kada"]).rsplit(" ", 1)[0] if x.get("kada") else ""
            told = [escape(cyrillic(when) if cyr else when)] if when else []
            if x["izvor"] != "sajt":
                told.append(t("ag_said_short"))
            state = f'<span class="src">{" · ".join(told)}</span>' if told else ""
            if x.get("sta"):
                state += f'<span class="ag-what">{s(x["sta"])}</span>'
        elif x["stanje"] == "u_toku":
            state = f'<span class="src">{t("ag_now")} · {t("ag_said_short")}</span>'
        elif x["stanje"] == "na_redu":
            state = f'<span class="src">{t("ag_next")}</span>'
        rows.append(f'<li class="ag-{x["stanje"] or "ceka"}"><i aria-hidden="true">{mark}</i><span><b>{x["n"]}.</b> {s(x["tekst"])}{state}</span></li>')
    title = s(a.get("naslov", ""))
    if str(a.get("url", "")).startswith("https://"):
        title = f'<a href="{escape(a["url"])}">{title}</a>'
    return (f'<details class="agenda" id="dnevni-red"><summary>{head}</summary><p class="meta">{title}</p>'
            f'<ol>{"".join(rows)}</ol>{_chip(t("ag_src"), t("ag_note"))}</details>')


def _chip(label: str, full: str) -> str:
    """Where something is from, as a small label beside a heading that opens to the whole sentence on a tap
    (22 Nov 2026, the maintainer: fewer long notes on how things are computed, on the content itself)."""
    return f'<details class="chip"><summary>{label}</summary><p>{full}</p></details>'


def _measures(steps: list[dict]) -> dict[str, int]:
    """The chair's measures among the shown steps, counted by kind (the kind the model read, or "other")."""
    kinds: dict[str, int] = {}
    for e in steps:
        if e.get("naslov") == "Mera predsedavajućeg":
            kind = (e.get("opis") or "").split(" · ")[0].strip() or _t("st_measure_other", False)
            kinds[kind] = kinds.get(kind, 0) + 1
    return kinds


def _votes(told: str, v: dict | None, cyr: bool) -> str:
    """A vote's figures as the summary tells them (`sudija.vote_text`, checked to add up), "za" and "protiv" in their
    colours as everywhere on the site, and a bar of the present (or of those who voted) when the vote has "za"
    (22 Nov 2026, the maintainer's choice: colour where it means a vote)."""
    parts = []
    for x in str(told).split(", "):
        cls = "v-za" if x.startswith("za ") else "v-protiv" if x.startswith("protiv ") else ""
        x = escape(_name(x, cyr))
        parts.append(f'<b class="{cls}">{x}</b>' if cls else x)
    bar = ""
    if isinstance(v, dict) and isinstance(v.get("za"), int):
        n = lambda k: v.get(k) if isinstance(v.get(k), int) and v.get(k) > 0 else 0
        whole = n("prisutno") or n("glasalo") or (n("za") + n("protiv") + n("uzdrzano"))
        if whole:
            w = lambda k: f"{100 * min(n(k), whole) / whole:.1f}%"
            bar = (f'<span class="dl-bar" aria-hidden="true"><i class="z" style="width:{w("za")}"></i>'
                   f'<i class="p" style="width:{w("protiv")}"></i><i class="u" style="width:{w("uzdrzano")}"></i></span>')
    return bar + ", ".join(parts)


def _minute(hhmm: str) -> int:
    """A clock's "HH:MM" as minutes of the sitting day (a day goes on past midnight: before 6 is the night after)."""
    try:
        h, m = (int(x) for x in str(hhmm).split(":")[:2])
    except ValueError:
        return -1
    return (h + 24 if h < 6 else h) * 60 + m


def _at_clock(day: str, hhmm: str, tz: ZoneInfo) -> float:
    """The moment of a clock's "HH:MM" on a sitting day (before 6 is the night after, as in _minute); 0 when it has none."""
    m = _minute(hhmm)
    try:
        start = datetime.strptime(str(day)[:10], "%Y-%m-%d")
    except ValueError:
        return 0
    return (start + timedelta(minutes=m)).replace(tzinfo=tz).timestamp() if m >= 0 else 0


def _step_mark(e: dict) -> tuple[str, str]:
    """The mark of a step on the line of time, by its kind (22 Nov 2026, the maintainer: a symbol for each kind of
    thing, a warning a red square): the class and what stands inside the mark."""
    title = e.get("naslov", "")
    if e.get("rec"):
        return "mk-rec", ""
    if title.startswith("Prelazak na "):
        return "mk-tacka", escape(title.split()[2].rstrip("."))
    if title in ("Izbor", "Rezultat glasanja"):
        return "mk-odluka", ""
    if title == "Mera predsedavajućeg":
        kind = (e.get("opis") or "").split(" · ")[0].strip().lower()
        return ("mk-mera-teska" if ("oduzim" in kind or "udalj" in kind) else "mk-mera"), ""
    if title in ("Pauza", "Kraj rada za danas"):
        return "mk-pauza", ""
    return "mk-korak", ""


def _steps(snap: dict, *, cyr: bool, tz: ZoneInfo, site: str = "") -> str:
    """"Šta se desilo": the day's line of time, newest first, every step on it with a mark by its kind (22 Nov 2026,
    the maintainer: everything in the steps, the line with its marks, a symbol for each kind). On it: the day
    summary's decisions with their votes once it is written (the steps reporting an election or a result then
    left out, the summary having told them, checked), and every step heard: an agenda item (its number in the mark),
    a debate, a vote, a break, each measure of the chair (a red square). The first eight stand, the rest fold.
    What the Assembly writes about the day is not told a second time: its sentence per finished item is in the
    agenda (`tacke.json`), whose title leads to its page of the sitting; only when nothing was heard are its sentences
    the line. Where it is from is one label beside the heading."""
    every = steps_shown(snap)
    heard = [e for e in every if e["izvor"] != "sajt"]
    written = [e for e in every if e["izvor"] == "sajt"]
    summary = snap.get("sazetak") if isinstance(snap.get("sazetak"), dict) else {}
    decisions = [o for o in summary.get("odluke") or [] if isinstance(o, dict) and o.get("sta")] if summary.get("vrsta") == "dan" else []
    if not heard and not written and not decisions:
        return ""
    t = lambda k: escape(_t(k, cyr))
    s = lambda x: escape(_name(str(x), cyr))

    def rules(e: dict, text: str = "") -> str:
        title = text or s(e["naslov"])
        if e.get("pojam") and site:  # what the Rules say of this kind of step, on the site (steps.STEP_TERM)
            href = site + ("cir/" if cyr else "") + "poslovnik-clanovi#pojam-" + e["pojam"]
            title += f' <a class="rk-l" href="{escape(href)}" title="{t("steps_rules")}">{BOOK}{t("rules_word")}</a>'
        return title

    def quote(who: str, what: str, shade: str = "", side: str = "", tag: bool = True) -> str:
        """Words said, as the automatic transcript has them: the speaker, the list's colour, a whole sentence. Without
        quotation marks: the transcript is not a quote (live/AGENTS.md), and says it is automatic."""
        dot = f'<i class="qd {shade}" aria-hidden="true"></i>' if shade else '<i class="qd q-ch" aria-hidden="true"></i>'
        return (f'<div class="q{" q-c" if not shade else ""}"><p class="qw">{dot}<b>{s(given_first(who) if shade else who)}</b>{f" <span>{s(side)}</span>" if side else ""}{f'<span class="qp">{t("qt_auto")}</span>' if tag else ""}</p>'
                f'<p class="qt">{s(what)}</p></div>')

    def li(when: str, mark: tuple[str, str], body: str, cls: str = "", at: float = 0) -> str:
        time_ = _moment(snap, at, when, cyr) if at else f'<span class="time">{escape(when)}</span>'
        return (f'<li class="{mark[0]}{" " + cls if cls else ""}">{time_}'
                f'<i aria-hidden="true">{mark[1]}</i><div>{body}</div></li>')

    def step(e: dict) -> str:
        if e.get("rec"):
            head, _, who = e["naslov"].partition(": ")
            who = s(who)
            if e.get("adresa") and str(e["adresa"]).replace("-", "").isalnum():
                who = f'<a href="{escape(site + ("cir/" if cyr else "") + "poslanik/" + e["adresa"])}">{who}</a>'
            return li(_clock(e["t"], tz), _step_mark(e), f'<p class="st-floor">{s(head)}: <b>{who}</b></p>', "st-rec", e["t"])
        title, what = rules(e), s(e["opis"]) if e["opis"] else ""
        if e.get("naslov") == "Mera predsedavajućeg":  # the kind as the title ("Opomena"), to whom under it
            kind, _, whom = (e.get("opis") or "").partition(" · ")
            if kind.strip():
                # to whom, and why where the chair's sentence said one of the Rules' reasons (mere.reason)
                title = rules(e, s(kind.strip()[:1].upper() + kind.strip()[1:]))
                what = " · ".join(s(x) for x in (whom.strip(), e.get("razlog") or "") if x)
        said = quote(t("chair_word"), e["recenica"]) if e.get("recenica") and config.SHOW_QUOTES else ""
        return li(_clock(e["t"], tz), _step_mark(e),
                  f'<p class="st-title">{title}</p>' + (f'<p class="st-what">{what}</p>' if what else "") + said, at=e["t"])

    def exchange(x: dict) -> str:
        a, b = x["prvi"], x["odgovor"]
        return li(_clock(x["t"], tz), ("mk-korak", ""), f'<p class="st-title">{t("reply_word")}</p>'
                  + quote(a["ime"], a["tekst"], LIST_COLOURS.get(a["lista"], "l1"), a["lista"], False)
                  + quote(b["ime"], b["tekst"], LIST_COLOURS.get(b["lista"], "l1"), b["lista"]), at=x["t"])

    rows: list[tuple[int, str]] = []  # (minute of the sitting day, the line)
    for o in decisions:
        votes = f'<p class="st-v">{_votes(o["glasovi"], o.get("glasanje"), cyr)}</p>' if o.get("glasovi") else ""
        rows.append((_minute(o.get("vreme", "")), li(str(o.get("vreme", "")), ("mk-odluka", ""),
                     f'<p class="st-title">{t("dl_decision")}</p><p class="st-what st-said">{s(o["sta"])}</p>{votes}',
                     at=_at_clock(snap.get("dan") or "", o.get("vreme", ""), tz))))
    for e in heard:
        if decisions and e.get("naslov") in ("Izbor", "Rezultat glasanja"):
            continue  # the day's summary has told them, checked (sudija.settle_votes)
        rows.append((_minute(_clock(e["t"], tz)), step(e)))
    if config.SHOW_QUOTES:
        rows += [(_minute(_clock(x["t"], tz)), exchange(x)) for x in snap.get("razmene") or []]
    rows.sort(key=lambda r: -r[0])
    if not rows and written:  # nothing heard: the Assembly's sentences, whole, in the order they stood
        body = '<ol class="steps">' + "".join(li("", ("mk-odluka", ""), f'<p class="st-said">{s(e["opis"])}</p>') for e in written) + "</ol>"
        chip = _chip(t("steps_site"), escape(_fill(_t("steps_published", cyr), _clock(max(e["t"] for e in written), tz))))
    else:
        first, rest = rows[:8], rows[8:]
        body = '<ol class="steps">' + "".join(r[1] for r in first) + "</ol>"
        if rest:
            body += (f'<details class="dl-more"><summary>{t("dl_more")} ({len(rest)})</summary>'
                     f'<ol class="steps">{"".join(r[1] for r in rest)}</ol></details>')
        full = t("steps_model" if any(e.get("model") for e in heard) else "steps_said")
        if decisions:
            full = full.rstrip(".") + ". " + escape(_fill(_t("sum_note", cyr), _model(summary)))
        chip = _chip(t("dl_src"), full)
        if site:
            body += (f'<p class="dl-foot rk-f"><a class="rk-l" href="{escape(site + ("cir/" if cyr else "") + "poslovnik-clanovi#pojmovi")}">'
                     f'{BOOK}{t("rules_word")}</a></p>')
    # between sittings, the last sitting day's steps, under its date (20 Nov 2026: after midnight the list was gone)
    head = t("steps")
    if snap.get("ranije") and snap.get("dan"):
        head = f'{t("steps_then")} {escape(_name(_on_day(snap["dan"]), cyr))}'
    return f'<section class="steps-sec"><div class="sec-h"><h2>{head}</h2>{chip}</div>{body}</section>'


def _on_day(day: str) -> str:
    """A date as "19. novembra" (on which day)."""
    try:
        d = datetime.strptime(str(day)[:10], "%Y-%m-%d")
    except ValueError:
        return ""
    return f"{d.day}. {MONTHS_OF[d.month - 1]}"


_WEEKDAYS_ON = {"ponedeljak": "u ponedeljak", "utorak": "u utorak", "sreda": "u sredu", "sredu": "u sredu",
                "četvrtak": "u četvrtak", "petak": "u petak", "subota": "u subotu", "subotu": "u subotu", "nedelja": "u nedelju"}


def _resumes(text: str) -> str:
    """The Assembly's notice that it goes on, said short: "Skupština nastavlja sa radom u utorak, 24. novembra, u
    10.00" (22 Nov 2026, the maintainer: say that part as when it goes on). Only when the notice says it in the
    Assembly's set words with a day and an hour; otherwise nothing, and the notice stands as it is."""
    m = re.search(r"nastavlja (?:sa radom|rad),? u (\w+),? (\d{1,2})\. (\w+)(?: \d{4}\.?)?(?: godine)?,?(?: sa početkom)? u (\d{1,2})[.:](\d{2})", str(text))
    if not m or m.group(1).lower() not in _WEEKDAYS_ON or m.group(3).lower() not in MONTHS_OF:
        return ""
    return f"{_WEEKDAYS_ON[m.group(1).lower()]}, {int(m.group(2))}. {m.group(3).lower()}, u {int(m.group(4))}.{m.group(5)}"


def _now() -> datetime:
    return datetime.now(ZoneInfo("Europe/Belgrade"))


def _resume_start(notice: dict) -> datetime | None:
    """The moment the Assembly's notice says it goes on: the first such day from the notice's own on (a notice in
    December may speak of January); None when the notice says no day and hour."""
    m = re.search(r", (\d{1,2})\. (\w+), u (\d{1,2})\.(\d{2})$", _resumes(notice.get("tekst", "")))
    if not m:
        return None
    try:
        day0 = datetime.strptime(str(notice.get("od", ""))[:10], "%Y-%m-%d").replace(tzinfo=_now().tzinfo)
        start = day0.replace(month=MONTHS_OF.index(m[2]) + 1, day=int(m[1]), hour=int(m[3]), minute=int(m[4]))
        return start.replace(year=start.year + 1) if start.date() < day0.date() else start
    except ValueError:
        return None


def announcement(snap: dict) -> tuple[str, dict, datetime | None]:
    """When the Assembly sits next (in words, and the moment) and where it says so, while nobody is on the air and that
    hour has not come ("", {}, None otherwise): the card on top, and what a pasted link shows. From the notice written
    by hand in the Assembly's words, and since 25 Nov 2026 from the Assembly's own listing ("sazvano"): a sitting
    convened, or one begun that goes on, by the same rule; the nearest. Past the hour it is no news: the evening of a
    sitting would say it goes on that morning (23 Nov 2026)."""
    if snap.get("stanje") != "nema_prenosa":
        return "", {}, None
    found = []
    for n in sorted(snap.get("obavestenja") or [], key=lambda n: str(n.get("od", "")))[-1:]:
        found.append((_resume_start(n), _resumes(n.get("tekst", "")), n))
    c = snap.get("sazvano") or {}
    p = str(c.get("pocinje") or "")[:16]
    try:
        at = datetime.strptime(p, "%Y-%m-%dT%H:%M").replace(tzinfo=_now().tzinfo)
    except ValueError:  # none, or a day with no hour: the countdown says it by days
        at = None
    if at:
        words = f"{_WD_ON[at.weekday()]}, {at.day}. {MONTHS_OF[at.month - 1]}, u {at.hour}.{at.minute:02d}"
        found.append((at, words, {"url": c.get("url", ""), "od": p.replace(":", ""), "sazvano": c}))
    found = [f for f in found if f[0] and _now() < f[0]]
    start, words, notice = min(found, key=lambda f: f[0], default=(None, "", {}))
    return words, notice, start


def announced(snap: dict) -> tuple[str, dict]:
    return announcement(snap)[:2]


def _says(words: str, notice: dict) -> str:
    """What is announced as a sentence: "Skupština nastavlja sa radom u utorak, …"; a sitting convened goes on with
    nothing, so "Skupština u utorak, …" (the words of the link's picture)."""
    c = notice.get("sazvano")
    return f'{TEXT["og_sitting"]} {words}' if c and not c.get("nastavak") else _fill(TEXT["og_goes_on"], words)


def announced_items(snap: dict) -> list[dict]:
    """What is next on what is announced: a convened sitting's own items; else those of the agenda shown not done yet."""
    c = announcement(snap)[1].get("sazvano")
    if c and not c.get("nastavak"):
        return [{"n": i, "tekst": x} for i, x in enumerate(c.get("tacke") or [], 1)]
    a = snap.get("dnevni_red") or {}
    if c and a.get("url") != c.get("url"):
        return []  # the agenda shown is another sitting's
    return [x for x in a.get("tacke") or [] if x.get("stanje") != "gotova"]


_WD = ("pon", "uto", "sre", "čet", "pet", "sub", "ned")
_WD_ON = ("u ponedeljak", "u utorak", "u sredu", "u četvrtak", "u petak", "u subotu", "u nedelju")


def _said_soon(start: datetime, cyr: bool) -> str:
    """"Sednica sutra u 10 h": danas, sutra, within a week by its day, later by its date. The hour kept on one line."""
    hour = f"{start.hour}\u00a0h" if not start.minute else f"{start.hour}.{start.minute:02d}\u00a0h"
    days = (start.date() - _now().date()).days
    if days <= 1:
        return _name(_fill(TEXT["st_today" if days <= 0 else "st_tomorrow"], hour), cyr)
    return _said_on(start, cyr)


def _said_on(start: datetime, cyr: bool) -> str:
    """The same by the day's name or date alone, for what is kept past midnight (the link's picture)."""
    hour = f"{start.hour}\u00a0h" if not start.minute else f"{start.hour}.{start.minute:02d}\u00a0h"
    days = (start.date() - _now().date()).days
    on = _WD_ON[start.weekday()] if days < 7 else f"{start.day}. {MONTHS_OF[start.month - 1]}"
    return _name(_fill(TEXT["st_day"], on, hour), cyr)


def _short_item(x: dict, cyr: bool) -> str:
    """An item as the card has room for: without the Assembly's name at its end."""
    return f'{x["n"]}. {_name(re.sub(r"\s+Narodne skupštine$", "", x["tekst"]), cyr)}'


def next_item(snap: dict) -> dict | None:
    """The item of the agenda that is next ("na redu"), when the Assembly's page says it; the first one
    of what is announced, when the Assembly's listing announces it."""
    if announcement(snap)[1].get("sazvano"):
        return next(iter(announced_items(snap)), None)
    return next((x for x in ((snap.get("dnevni_red") or {}).get("tacke") or []) if x.get("stanje") == "na_redu"), None)


def _left(sec: int, cyr: bool) -> str:
    """Minutes and seconds as the chair says them ("23 min 21 s")."""
    m, s = divmod(max(0, sec), 60)
    minute, second = ("мин", "с") if cyr else ("min", "s")
    return f"{m} {minute}" + (f" {s} {second}" if s else "")


def _group_time(snap: dict, *, cyr: bool, tz: ZoneInfo | None = None) -> str:
    """The groups' time left in the debate of the item under way (vreme.py), an estimate: a line and a thin bar a group
    (24 Nov 2026, the maintainer: smaller, under the speaker, no other words; how it is counted is under "Kako ovo
    radi"). None once the chair has closed the debate."""
    g = snap.get("vreme_grupa")
    if not g or not g.get("grupe") or g.get("zakljucen"):
        return ""
    t = lambda k: escape(_t(k, cyr))
    rows = []
    for r in g["grupe"]:
        left = r["ima"] - r["potroseno"]
        share = max(0.0, min(100.0, 100 * left / r["ima"])) if r["ima"] else 0.0
        rest = _dur(left, cyr) if left >= 60 else f'{t("gt_over")} {_dur(-left, cyr)}' if left <= -60 else t("gt_none")
        said = r.get("receno") or {}  # the Assembly's own figure, when the chair said one: when, and how much
        told = (f'<small class="gt-said">{escape(_fill(_t("gt_said", cyr), _clock(int(said["t"]), tz), _left(int(said["sek"]), cyr)))}</small>'
                if tz and said.get("t") and said.get("sek") is not None else "")
        rows.append(f'<li><span>{escape(_name(r["lista"], cyr))}</span><b>{rest}</b>'
                    f'<div class="gt-bar"><i class="{LIST_COLOURS.get(r["lista"], "l1")}" style="width:{share:.1f}%"></i></div>{told}</li>')
    return (f'<section class="gt-sec"><h2>{t("gt_head")} <span>{t("gt_estimate")}</span></h2>'
            f'<ul class="gt">{"".join(rows)}</ul></section>')


def _cards(snap: dict, turns: list[dict], shade: dict[str, str], *, cyr: bool, site: str, tz: ZoneInfo) -> str:
    """The day in a few cards to tap through (19 Nov 2026, the maintainer's choice): the whole time, who had the
    most, the time by list, the longest turn, who came up most often, and the way to the site. Every card by a rule,
    the same whoever it names. The cards wait hidden in the page; the script shows them full screen on a tap.
    What happened comes before who spoke (20 Nov 2026, the maintainer: the cards told only the rostrum's time),
    each card from one source and saying which: the model's sentence of the day, the agenda's items finished that
    day as the sitting's page has them, the chair's measures counted from the day's steps (kinds, no names: heard
    automatically), and what comes next by the Assembly's notice and the agenda. A card with more to read stays
    longer (`data-t`)."""
    rows = leaders(turns)
    if len(rows) < 2:
        return ""
    t = lambda k: escape(_t(k, cyr))
    n = lambda x: escape(_name(x, cyr))
    if snap.get("ranije") and snap.get("dan"):
        when = _date(snap["dan"])
        when = cyrillic(when) if cyr else when
    else:
        when = _t("h_today", cyr).capitalize() + ", " + (cyrillic(_date(snap["dan"])) if cyr else _date(snap["dan"]))
    whole = sum(r[1] for r in rows)
    def card(kicker: str, body: str, read: str = "") -> str:
        """A card; one with a text to read stays six seconds and one more for every 22 letters, 16 at most."""
        secs = min(16, 6 + len(read) // 22)
        stay = f' data-t="{secs}"' if secs > 6 else ""
        return f'<section class="st-c"{stay}><p class="st-k">{kicker}</p>{body}</section>'
    out = [card(escape(when), f'<p class="st-big">{_dur(whole, cyr)}</p><p class="st-s">{t("st_total")}</p>'
                              f'<p class="st-row"><b>{len(turns)}</b> {t("n_turns")} · <b>{len(rows)}</b> {t("n_people")}</p>')]
    out += _cards_of_the_day(snap, card, cyr=cyr)
    name, sec, _ = rows[0]
    out.append(card(t("st_most"), f'<p class="st-name">{n(given_first(name))}</p><p class="st-big">{_dur(sec, cyr)}</p>'
                                  f'<p class="st-s">{escape(headline(turns, cyr=cyr, when=_when(snap, cyr)))}</p>'))
    lists = _lists(turns, shade, cyr=cyr)
    if lists:
        out.append(f'<section class="st-c">{lists.replace("<h3 class=\"sub\">", "<p class=\"st-k\">").replace("</h3>", "</p>")}</section>')
    longest = max(turns, key=lambda d: (d["sekundi"], -d["od"]))
    out.append(card(t("st_longest"), f'<p class="st-name">{n(given_first(longest["ime"]))}</p>'
                                     f'<p class="st-big">{_dur(longest["sekundi"], cyr)}</p>'
                                     f'<p class="st-s">{_clock(longest["od"], tz)}–{_clock(longest["do"], tz)}</p>'))
    count: dict[str, int] = {}
    for d in turns:
        count[d["ime"]] = count.get(d["ime"], 0) + 1
    often = max(count, key=lambda k: (count[k], k))
    if count[often] >= 3:
        out.append(card(t("st_often"), f'<p class="st-name">{n(given_first(often))}</p>'
                                       f'<p class="st-big">{count[often]} <small>{t("st_times")}</small></p>'))
    home = site + ("cir/" if cyr else "")
    nxt = _card_next(snap, cyr=cyr)
    if nxt:
        out.append(card(t("st_next"), nxt[0], nxt[1]))
    # once the day is over the site has its page: every turn with its recording and the automatic transcript
    day_page = (f'<p class="st-s"><a href="{escape(home)}govornici/{escape(str(snap["dan"]))}">{t("st_day_page")} →</a></p>'
                if snap.get("ranije") and snap.get("dan") else "")
    out.append(card(t("st_end"), f'<p class="st-name">{t("st_site")}</p>'
                                 f'<p><a class="cta" href="{escape(home)}">zailiprotiv.rs →</a></p>{day_page}'))
    go = (f'<p class="acts st-go"><button type="button" class="share-now st-open">▶ {t("st_open")}</button></p>'
          if snap["stanje"] == "govori" and snap.get("sada") else "")
    if not go:  # the way to them otherwise stood in the box of the day, gone since 22 Nov 2026 (the maintainer)
        return ""
    return (go +
            f'<div class="st-data" hidden data-close="{t("st_close")}" data-hint="{t("st_hint")}">{"".join(out)}</div>')


def transcript_page(data: dict, *, cyr: bool, site: str, tz: ZoneInfo, url: str = "") -> str:
    """The day's automatic transcript, turn by turn, newest first: a page of its own, so that the part of the main
    page every visitor asks for every few seconds stays small."""
    t = lambda k: escape(_t(k, cyr))
    base = "/cir/" if cyr else "/"
    home = site + ("cir/" if cyr else "")
    when = _date(data["dan"]) if data.get("dan") else ""
    rows = []
    for d in data["govori"]:
        nm = escape(_name(given_first(d["ime"]), cyr)) if not d.get("bez") else f'<i>{t("said_nobody")}</i>'
        if d["adresa"]:
            nm = f'<a href="{escape(home + "poslanik/" + d["adresa"])}">{nm}</a>'
        text = escape(cyrillic(d["tekst"]) if cyr else d["tekst"])
        subject = f'Ispravka prepisa: {given_first(d["ime"]) or "bez potpisa"}, {data.get("dan", "")} {_clock(d["od"], tz)}'
        body = "Pogrešno napisano:\n\nTreba da piše:\n\n(Ispravljamo pravopis i imena, ne ono što je rečeno.)"
        mail = f'mailto:kontakt@zailiprotiv.rs?subject={quote(subject)}&body={quote(body)}'
        rows.append(f'<article id="t{int(d["od"])}"><h2>{nm} <span class="meta">{_clock(d["od"], tz)}–{_clock(d["do"], tz)}'
                    f' · {_minutes(d["sekundi"])} {t("min")}</span></h2><p>{text}</p>'
                    f'<p class="meta"><a href="{escape(mail)}">{t("said_report")}</a></p></article>')
    body = "".join(rows) or f'<p class="meta">{t("said_none")}</p>'
    brand = _brand(cyr)
    return f"""<!doctype html>
<html lang="{"sr-Cyrl" if cyr else "sr-Latn"}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{t("said_title")}{", " + escape(cyrillic(when) if cyr else when) if when else ""} · {"За или Против" if cyr else "Za ili Protiv"}</title>
<meta name="robots" content="noindex">
<link rel="icon" type="image/svg+xml" href="{escape(site)}favicon.svg">
<style>{CSS}</style>
</head>
<body>
<header class="top"><a class="brand" href="{escape(home)}">{brand}</a><span class="top-r"><a href="{base}">{t("said_back")}</a></span></header>
<main class="said-page">
<h1>{t("said_title")}{", " + escape(cyrillic(when) if cyr else when) if when else ""}</h1>
<p class="lead">{t("said_lead")}</p>
<p class="meta">{t("said_fix")}</p>
{body}
<p><a href="{base}">← {t("said_back")}</a></p>
</main>
<script>
// The page as it is now, asked for again every twenty seconds while it is looked at; what is read stays in place.
setInterval(function () {{
  if (document.hidden) return;
  fetch(location.pathname + location.search, {{ cache: "no-store" }}).then(function (r) {{ return r.ok ? r.text() : null; }}).then(function (html) {{
    if (!html) return;
    var now = new DOMParser().parseFromString(html, "text/html").querySelector("main");
    var main = document.querySelector("main");
    if (now && main && now.innerHTML !== main.innerHTML) main.innerHTML = now.innerHTML;
  }}).catch(function () {{}});
}}, 20000);
</script>
</body>
</html>"""


def _when(snap: dict, cyr: bool) -> str:
    """"danas", or the date of the earlier day shown."""
    if snap.get("ranije") and snap.get("dan"):
        day = _date(snap["dan"]).rstrip(".")
        return day.rsplit(" ", 1)[0]  # "18. novembar": the year is in the heading
    return ""


STALE = 12 * 3600  # a sitting convened this long ago with no broadcast seen is no longer counted down to


def _units(cyr: bool) -> dict[str, str]:
    """The countdown's words; hours as "ч" in Cyrillic, as _dur writes them (letter by letter "h" would be "х")."""
    return {"d1": _t("nx_day1", cyr), "dn": _t("nx_days", cyr), "h": "ч" if cyr else "h", "m": "мин" if cyr else "min",
            "soon": _t("nx_soon", cyr)}


def left(sec: int, u: dict[str, str]) -> str:
    """Time left as the countdown writes it (the page's script writes it the same way each second): days and hours,
    or hours and minutes, or minutes."""
    if sec <= 0:
        return u["soon"]
    d, rest = divmod(int(sec), 86400)
    h, m = rest // 3600, rest % 3600 // 60
    if d:
        return f'{d} {u["d1"] if d % 10 == 1 and d % 100 != 11 else u["dn"]}' + (f' {h} {u["h"]}' if h else "")
    if h:
        return f'{h} {u["h"]} {m} {u["m"]}'
    return f'{max(1, m)} {u["m"]}'


def countdown(snap: dict, *, cyr: bool, tz: ZoneInfo, now: float | None = None) -> str:
    """Between sittings, the next one convened (20 Nov 2026, the maintainer's choice, for visitors to know when to come
    back): when it begins, counted down each second by the page's script (by days when the Assembly gives no hour),
    its title and agenda as the Assembly lists them. Nothing when none is convened, or one convened has long begun."""
    c = snap.get("sazvano") or {}
    p = str(c.get("pocinje") or "")
    try:
        day = datetime.strptime(p[:10], "%Y-%m-%d").date()
    except ValueError:
        return ""
    now = _now().timestamp() if now is None else now
    t = lambda k: escape(_t(k, cyr))
    hour = p[11:16] if len(p) >= 16 else ""
    when = f'{WEEKDAYS[day.weekday()].capitalize()}, {_date(p[:10])}' + (f' {TEXT["at"]} {hour}' if hour else "")
    if hour:
        at = int(datetime.strptime(p[:16], "%Y-%m-%dT%H:%M").replace(tzinfo=tz).timestamp())
        if now - at > STALE:
            return ""
        u = _units(cyr)
        data = " ".join(f'data-{k}="{escape(v)}"' for k, v in u.items())
        big = (f'<p class="nx-big"><span{" hidden" if now >= at else ""}>{t("nx_in")}</span> '
               f'<b class="nx-in" data-at="{at}" {data}>{escape(left(at - int(now), u))}</b></p>')
    else:
        days = (day - datetime.fromtimestamp(now, tz).date()).days
        if days < 0:
            return ""
        if days < 2:
            big = f'<p class="nx-big"><b>{t("nx_today" if days == 0 else "nx_tomorrow")}</b></p>'
        else:
            word = t("nx_day1" if days % 10 == 1 and days % 100 != 11 else "nx_days")
            big = f'<p class="nx-big"><span>{t("nx_in")}</span> <b>{days} {word}</b></p>'
    title = escape(_name(c.get("naslov", ""), cyr))
    if str(c.get("url", "")).startswith("https://"):
        title = f'<a href="{escape(c["url"])}">{title}</a>'
    items = [x for x in c.get("tacke") or [] if x]
    agenda = (f'<details class="nx-ag" id="nx-ag"><summary>{t("nx_agenda")} ({len(items)})</summary><ol>'
              + "".join(f'<li>{escape(_name(x, cyr))}</li>' for x in items) + "</ol></details>") if items else ""
    return (f'<div class="nx"><p class="src">{t("coming_on" if c.get("nastavak") else "coming")}</p>{big}'
            f'<p class="nx-when">{escape(_name(when, cyr))}</p><p class="nx-title">{title}</p>{agenda}'
            f'<p class="meta">{t("nx_note")}</p></div>')


def manifest(cyr: bool) -> dict:
    """The page as an app on a phone's home screen (20 Nov 2026): its name, where it opens, its icons (picture.icon)."""
    base = "/cir/" if cyr else "/"
    icon = lambda src, size, purpose: {"src": src, "sizes": f"{size}x{size}", "type": "image/png", "purpose": purpose}
    return {"id": base, "name": _t("title", cyr), "short_name": _t("app_name", cyr), "description": _t("lead", cyr),
            "lang": "sr-Cyrl" if cyr else "sr-Latn", "start_url": base, "scope": base, "display": "standalone",
            "background_color": "#ffffff", "theme_color": "#ffffff",
            "icons": [icon("/ikona-192.png", 192, "any"), icon("/ikona-512.png", 512, "any"),
                      icon("/ikona-maskable-512.png", 512, "maskable")]}


def _model(summary: dict) -> str:
    """Who wrote the day's summary, as the page names it: "claude-opus-5-5" → "Claude Opus"."""
    parts = str(summary.get("model") or config.MODEL).split("-")
    return f"Claude {parts[1].capitalize()}" if len(parts) > 1 else "Claude Haiku"


def _cards_of_the_day(snap: dict, card, *, cyr: bool) -> list[str]:
    """What happened, as cards: the model's sentence of the day (said to be the model's); each agenda item the
    sitting's page has as finished that day, with the sentence of fact kept with it (three at most, the rest as a
    list); the chair's measures among the day's shown steps, counted by kind."""
    t = lambda k: escape(_t(k, cyr))
    n = lambda x: escape(_name(str(x), cyr))
    out = []
    s = snap.get("sazetak")
    if isinstance(s, dict) and s.get("vrsta") == "dan" and s.get("kratko"):
        out.append(card(t("st_brief"), f'<p class="st-text">{n(s["kratko"])}</p><p class="st-src">{escape(_fill(_t("st_brief_src", cyr), _model(s)))}</p>', s["kratko"]))
    done = [x for x in (snap.get("dnevni_red") or {}).get("tacke") or []
            if x.get("stanje") == "gotova" and x.get("izvor") == "sajt" and x.get("kada") == snap.get("dan")]
    for x in done[:3]:
        what = f'<p class="st-text">{n(x["sta"])}</p>' if x.get("sta") else ""
        out.append(card(escape(_fill(_t("st_item", cyr), str(x["n"]))),
                        f'<p class="st-item">{n(x["tekst"])}</p>{what}<p class="st-src">{t("st_item_src")}</p>',
                        x["tekst"] + (x.get("sta") or "")))
    if len(done) > 3:
        rest = "".join(f'<li>{x["n"]}. {n(x["tekst"])}</li>' for x in done[3:])
        out.append(card(t("st_items_more"), f'<ul class="st-list">{rest}</ul><p class="st-src">{t("st_item_src")}</p>',
                        "".join(x["tekst"] for x in done[3:])))
    kinds = _measures(steps_shown(snap))
    if kinds:
        total = sum(kinds.values())
        rows = "".join(f'<li><b>{c}</b> {n(k)}</li>' for k, c in sorted(kinds.items(), key=lambda kv: (-kv[1], kv[0])))
        out.append(card(t("st_measures"), f'<p class="st-big">{total}</p><ul class="st-list">{rows}</ul>'
                                          f'<p class="st-src">{t("st_measures_src")}</p>', "x" * 90))
    return out


def _card_next(snap: dict, *, cyr: bool) -> tuple[str, str] | None:
    """What comes next: the Assembly's newest notice (as its site says it) and the agenda's item next in turn."""
    t = lambda k: escape(_t(k, cyr))
    n = lambda x: escape(_name(str(x), cyr))
    notice = next(iter(sorted((x for x in snap.get("obavestenja") or [] if x.get("tekst")),
                              key=lambda x: str(x.get("od", "")))[-1:]), None)
    item = next((x for x in (snap.get("dnevni_red") or {}).get("tacke") or [] if x.get("stanje") in ("u_toku", "na_redu")), None)
    if not notice and not item:
        return None
    body = read = ""
    if notice:
        body += f'<p class="st-text">{n(notice["tekst"])}</p><p class="st-src">{t("steps_site")}</p>'
        read += notice["tekst"]
    if item:
        label = t("ag_now") if item["stanje"] == "u_toku" else t("ag_next")
        body += f'<p class="st-item"><small>{label}:</small> {item["n"]}. {n(item["tekst"])}</p>'
        read += item["tekst"]
    return body, read


def _resumes_at(text: str, after: float, tz: ZoneInfo) -> str:
    """The hour a break ends at, as the chair said it ("do 15 sati i 10 minuta" → "15:10"): only a clock after "do" or
    "u", later than the break and within six hours of it. A length ("jednog sata") is no hour: "" then."""
    m = re.search(r"\b(?:do|u)\s+(\d{1,2})(?:[.:](\d{2})|\s+(?:sati|sata|sat|časova|časa|čas|h)(?:\s+i\s+(\d{1,2})\s+minut\w*)?)", text.lower())
    if not m:
        return ""
    h, mi = int(m.group(1)), int(m.group(2) or m.group(3) or 0)
    if h > 23 or mi > 59:
        return ""
    start = datetime.fromtimestamp(after, tz)
    end = start.replace(hour=h, minute=mi, second=0, microsecond=0)
    return f"{h}:{mi:02d}" if 0 < (end - start).total_seconds() <= 6 * 3600 else ""


def _break(snap: dict, *, cyr: bool, tz: ZoneInfo) -> str:
    """The stretch just ended, while its break lasts (24 Nov 2026, the maintainer's request): the model's paragraph,
    as its own; what the code counts beside it, not the model (the chair's measures of the stretch, the votes that
    add up), and the hour the chair said the break ends. Gone once anyone speaks or a step is heard after the break;
    the day's summary never stands here. What a speaker spoke about is not here: those lines are not checked against
    what was said."""
    s = snap.get("sazetak")
    if not (isinstance(s, dict) and s.get("vrsta") == "deo" and s.get("ukratko") and s.get("t_do")):
        return ""
    if snap.get("ranije") or snap["stanje"] == "govori" or snap.get("sada"):
        return ""
    a, b = s.get("t_od") or 0, s["t_do"]
    steps = [e for e in steps_shown(snap) if e.get("izvor") != "sajt"]
    if any(d["do"] > b + 30 for d in snap.get("danas") or []) or any(e["t"] > b + 60 for e in steps):
        return ""  # the sitting went on
    t = lambda k: escape(_t(k, cyr))
    n = lambda x: escape(_name(str(x), cyr))
    rows = ""
    for e in s.get("tok") or []:
        if isinstance(e, dict) and e.get("glasovi"):
            rows += f'<li>{n(e.get("vreme", ""))} {n(e["sta"])}<p class="st-v">{_votes(e["glasovi"], e.get("glasanje"), cyr)}</p></li>'
    kinds: dict[str, list] = {}
    for e in sorted(steps, key=lambda e: e["t"]):
        if e.get("naslov") == "Mera predsedavajućeg" and a <= e["t"] < b:
            kind = (e.get("opis") or "").split(" · ")[0].strip() or _t("st_measure_other", False)
            kinds.setdefault(kind, []).append(_clock(e["t"], tz))
    if kinds:
        told = "; ".join(f"{len(v)} × {n(k)} ({', '.join(v)})" for k, v in sorted(kinds.items(), key=lambda kv: (-len(kv[1]), kv[0])))
        rows += f'<li><b>{t("br_measures")}:</b> {told}</li>'
    said = next((e for e in reversed(snap.get("hronika") or []) if e.get("vrsta") == "Pauza" and e.get("izvor") == "model"
                 and abs(e["t"] - b) <= 2), None)
    hour = _resumes_at(said.get("tekst", ""), said["t"], tz) if said else ""
    when = f'<p class="br-when">{escape(_fill(_t("br_resume", cyr), hour))}</p>' if hour else ""
    return (f'<section class="br"><div class="sec-h"><h2>{t("br_h")} ({_clock(b, tz)})</h2>{_chip(t("dl_src"), t("br_src"))}</div>'
            f'{when}<p class="br-text">{n(s["ukratko"])}</p>{f"<ul>{rows}</ul>" if rows else ""}</section>')


def _paused(snap: dict) -> int:
    """When the break on now was said, or 0: a break shown among the day's steps while a broadcast is on and nobody is
    at the rostrum, and since then nobody spoke and no step was heard."""
    if snap.get("stanje") in ("govori", "nema_prenosa") or snap.get("ranije") or snap.get("sada"):
        return 0
    steps = [e for e in steps_shown(snap) if e.get("izvor") != "sajt"]
    b = max((e["t"] for e in steps if e.get("naslov") == STEP_TITLES["Pauza"]), default=0)
    if not b or any(d["do"] > b + 30 for d in snap.get("danas") or []) or any(e["t"] > b + 60 for e in steps):
        return 0
    return b


def mail_line(snap: dict, sent: bool, *, speech: bool = False) -> str:
    """Which words stand under "Sažetak dana na mejl" (25 Nov 2026, the maintainer's): what comes next to who signs up
    now, so never more than is sure. `sent`: the day's mail went to all, so who signs up now does not get that day."""
    today = not snap.get("ranije")
    off = snap.get("stanje") == "nema_prenosa"
    if sent or (speech and not today):
        return "sledeci"
    if today and off and snap.get("danas"):
        return "gotov"
    if today and not off and (speech or _paused(snap)):
        return "danas"
    return "svake"


NOTIFY_FROM = 20 * 60  # a break shorter than this is told to nobody (obavesti.PAUSE)


def _mail_attrs(snap: dict, sent: bool, tz: ZoneInfo) -> str:
    """What the page's script needs for the row of the mail, as attributes of the part: its words, its words on a
    speech's own link, whether the row stands under the player for everybody (a break, the day over), and whether the
    bell may say that the sitting's going on will be told of: the chair named the hour, and it is over 20 minutes away."""
    b = _paused(snap)
    up = "pauza" if b else ""
    if snap.get("stanje") == "nema_prenosa" and not snap.get("ranije") and snap.get("danas"):
        up = "kraj"
    out = f' data-ml="{mail_line(snap, sent)}" data-ml-govor="{mail_line(snap, sent, speech=True)}"'
    if up:
        out += f' data-gore="{up}"'
    if b:
        said = next((e for e in snap.get("hronika") or [] if e.get("vrsta") == "Pauza" and abs(e["t"] - b) <= 2), {})
        hour = _resumes_at(said.get("tekst", ""), b, tz)
        if hour:
            h, m = hour.split(":")
            end = datetime.fromtimestamp(b, tz).replace(hour=int(h), minute=int(m), second=0, microsecond=0)
            if (end - _now()).total_seconds() > NOTIFY_FROM:
                out += ' data-nastavak="1"'
    return out


def _pause(snap: dict, *, cyr: bool, tz: ZoneInfo, site: str = "") -> str:
    """While nobody is on during a sitting's break: the next sitting convened, if any. The box of the day's sentence,
    its three with the most time and the pictures to share stood here until 22 Nov 2026 (the maintainer: "sklonio bi
    ceo ovaj segment … sa sve tim za deljenje"); the day's tiles, totals and cards below say the same."""
    t = lambda k: escape(_t(k, cyr))
    coming = snap.get("sazvano")
    if not (coming and coming.get("pocinje") and snap["stanje"] != "nema_prenosa"):  # between sittings: the countdown
        return ""
    day = _date(coming["pocinje"][:10])
    hour = f' {t("at")} {escape(coming["pocinje"][11:16])}' if len(coming["pocinje"]) > 10 else ""
    title = escape(_name(coming.get("naslov", ""), cyr))
    if str(coming.get("url", "")).startswith("https://"):
        title = f'<a href="{escape(coming["url"])}">{title}</a>'
    return f'<p class="pz-next"><b>{t("coming_on" if coming.get("nastavak") else "coming")}:</b> {escape(cyrillic(day) if cyr else day)}{hour}. {title}</p>'


def _dur(sec: int, cyr: bool = False) -> str:
    h, m = divmod(max(60, sec) // 60, 60)
    hour, minute = ("ч", "мин") if cyr else ("h", "min")
    return f"{h} {hour} {m} {minute}" if h else f"{m} {minute}"


def _totals(turns: list[dict], *, cyr: bool, site: str, top: int = 5, shade: dict[str, str] | None = None) -> str:
    """The day's time on the floor per speaker, longest first, as bars: the turns summed, by the same rule for all.
    The first five stand, the others open under them (22 Nov 2026, the maintainer: "skrati na top 5")."""
    t = lambda k: escape(_t(k, cyr))
    by: dict[str, list] = {}
    tone: dict[str, str] = {}
    for d in turns:
        tone.setdefault(d["ime"], (shade or {}).get(d.get("lista") or "", ""))
        row = by.setdefault(d["ime"], [0, 0, d.get("adresa", ""),
                                       (d.get("lista") or "").strip("*") or d.get("uloga") or d.get("grupa") or ""])
        row[0] += max(0, d["sekundi"])
        row[1] += 1
    rows = sorted(by.items(), key=lambda kv: -kv[1][0])
    if len(rows) < 2:
        return ""
    whole = sum(r[0] for _, r in rows) or 1
    most = rows[0][1][0] or 1
    out = [f'<h3 class="sub">{t("totals")}</h3><div class="tot">']
    def line(name_html: str, side: str, sec: int, n: int, rest: bool = False, cls: str = "") -> str:
        share = f"{100 * sec / whole:.0f}".replace(".", ",")
        word = t("speeches_1") if n == 1 else t("speeches_n")
        under = f'<span>{escape(_name(side, cyr))}</span>' if side else ""
        return (f'<div class="tr{" rest" if rest else ""}"><div class="tn">{name_html}{under}</div>'
                f'<div class="tb"><i{f' class="{cls}"' if cls else ""} style="width:{max(1.5, 100 * sec / most):.1f}%"></i></div>'
                f'<div class="tv"><b>{_dur(sec, cyr)}</b><span>{share}% · {n} {word}</span></div></div>')
    def row(name: str, sec: int, n: int, slug: str, side: str) -> str:
        nm = escape(_name(given_first(name), cyr))
        if slug:
            nm = f'<a href="{escape(site + ("cir/" if cyr else "") + "poslanik/" + slug)}">{nm}</a>'
        return line(nm, side, sec, n, cls=tone.get(name, ""))
    out += [row(name, *r) for name, r in rows[:top]]
    out.append("</div>")
    rest = rows[top:]
    if rest:
        out.append(f'<details class="tot-more"><summary>{t("totals_more")} ({len(rest)})</summary><div class="tot">'
                   + "".join(row(name, *r) for name, r in rest) + "</div></details>")
    return "".join(out)


# "O govorniku" (26 Nov 2026, the maintainer's choice of variant C, with D as an addition): nothing is added to the
# speaker's block; the portrait (or, with none, a small "i" after the name) opens a sheet of the MP's offices in the
# convocation, from the site's file (pages_mikrofon.office, "fn"), in the one order the site uses for everyone
# (offices.order). It is a <template> in the part; the script puts it in the page's one <dialog> (live.js), which
# stays open while the part is replaced every five seconds. Without the script the portrait leads to the MP's
# offices on the site. "U Skupštini", "Odbori", "Delegacije": the kinds of offices.json, each heading only when held.
_OG_KINDS = (("og_assembly", ("speaker", "vice", "group")), ("og_committees", ("committee",)),
             ("og_delegations", ("delegation",)))


def rec_card(*, cyr: bool, site: str) -> str:
    """The place of the speaker's card while a recording plays (mikrofon.js draws it; 26 Nov 2026, the maintainer: "Da
    li mozemo povezati karticu govornika sa timelineom"), and its words in the page's script, apart, as the script
    redraws the card. Hidden until a recording plays; nothing without the script."""
    t = lambda k: escape(_t(k, cyr))
    words = "".join(f'<span data-w="{w}">{t(k)}</span>' for w, k in (
        ("na", "rc_na"), ("izmedju", "rc_between"), ("u", "rc_at"), ("pov", "rk_povreda"), ("cl", "rk_art"),
        ("i", "rk_and"), ("og", "og_title")))
    base = "/cir/" if cyr else "/"
    return (f'<section class="rc" id="rc" hidden data-o="{base}o/" '
            f'data-clan="{escape(site)}{"cir/" if cyr else ""}poslovnik-clanovi#clan-"></section>'
            f'<div id="rc-w" hidden>{words}</div>')


def _og_day(day: str) -> str:
    y, m, d = (int(x) for x in day.split("-"))
    return f"{d}. {MONTHS_OF[m - 1]} {y}."


def about(cur: dict, *, cyr: bool, site: str) -> str:
    """The sheet "O govorniku" of the speaker, as a <template> for the script; empty for one whose offices the site's
    file does not say (not an MP of the list, or a name two MPs share): nothing is said rather than "none"."""
    o = cur.get("o") or {}
    fn = o.get("fn")
    if not cur.get("adresa") or not isinstance(fn, list) or not o.get("fn_dan"):
        return ""
    t = lambda k: escape(_t(k, cyr))
    s = lambda x: escape(_name(x, cyr))
    page_ = f'{site}{"cir/" if cyr else ""}poslanik/{cur["adresa"]}'
    side = cur.get("uloga") or cur.get("lista") or cur.get("grupa") or ""
    out = [f'<p class="og-k">{t("og_title")}</p><h2 class="og-name" id="og-h">{s(given_first(cur["ime"]))}</h2>']
    if side:
        out.append(f'<p class="og-side"><i aria-hidden="true"></i>{s(side)}</p>')
    for head, kinds in _OG_KINDS:
        rows = [f for f in fn if isinstance(f, dict) and f.get("v") in kinds]
        if rows:
            out.append(f'<h3 class="og-g">{t(head)}</h3><ul class="og-l">' + "".join(
                f'<li>{s(f.get("u", ""))}</li>' if not f.get("t") else
                f'<li>{s(f["t"])} <span>· {s(f.get("u", ""))}</span></li>' for f in rows) + "</ul>")
    if not fn:
        out.append(f'<p class="og-none">{t("og_none")}</p>')
    out.append(f'<p class="og-src">{s(_fill(TEXT["og_source"], _og_day(o["fn_dan"])))} '
               f'<a href="{escape(page_)}">{t("og_page")} →</a></p>')
    return f'<template id="og-t" data-adresa="{escape(cur["adresa"])}">{"".join(out)}</template>'


def sheet(facts: dict, adresa: str, *, cyr: bool, site: str) -> str:
    """The sheet "O govorniku" of an MP of the site's list by address, as the dialog's content (about's, no
    <template>), for the card of a recording's speaker (/o/<adresa>, 26 Nov 2026); "" for an address it does not know."""
    o = facts.get(adresa) if re.fullmatch(r"[a-z0-9-]{1,80}", adresa or "") else None
    if not isinstance(o, dict) or not o.get("ime"):
        return ""
    html = about({"adresa": adresa, "ime": o["ime"], "lista": o.get("lista", ""), "o": o}, cyr=cyr, site=site)
    return html[html.index(">") + 1:html.rindex("</template>")] if html else ""


def named(cur: dict, item: dict | None) -> list[dict]:
    """D (26 Nov 2026): the speaker's committees and delegations that the agenda item under way names itself, word
    for word, the body's first word ("Odbor", "Delegacija") in any grammatical case and the rest as the Assembly
    writes it; never one guessed from what the item is about. In the speaker's order of offices."""
    fn = (cur.get("o") or {}).get("fn")
    if not item or not isinstance(fn, list):
        return []
    text = " ".join(latin(str(item.get("tekst", ""))).lower().split())
    out = []
    for f in fn:
        if not isinstance(f, dict) or f.get("v") not in ("committee", "delegation") or " " not in f.get("t", "").strip():
            continue
        head, rest = " ".join(f["t"].lower().split()).split(" ", 1)
        stem = head.rstrip("aeiou") or head
        if re.search(r"(?<!\w)" + re.escape(stem) + r"\w*\s" + re.escape(rest) + r"(?!\w)", text):
            out.append(f)
    return out


def _named_line(cur: dict, item: dict | None, *, cyr: bool) -> str:
    """One line under the speaker, only when the item under way names their committee or delegation (`named`): the
    first in their order, a committee by its name up to the first comma, a delegation whole, the item's number and
    the seat. No line, and no room kept for one, otherwise."""
    hit = named(cur, item)
    if not hit:
        return ""
    f = hit[0]
    body = f["t"].split(",")[0] if f["v"] == "committee" else f["t"]
    text = f'{body} ({_fill(TEXT["og_item"], item.get("n", ""))}) · {f.get("u", "")}'
    return f'<p class="sp-item">{escape(_name(text, cyr))}</p>'


def _speaker(cur: dict, *, cyr: bool, site: str, tz: ZoneInfo, item: dict | None = None) -> tuple[str, str, str]:
    """The speaker: the portrait (an MP's, from the Assembly, served by the site), the name (the way to the MP's page),
    the list and a clock that runs, with how long the turn may last where that is heard (rok.py). The same for every
    speaker, by rules. The box under it (the day's numbers, lines about the MP, the pictures to share) is off since
    24 Nov 2026, the maintainer. `item` is the agenda's item under way (D, `_named_line`). Returns the head, the box
    (empty) and the words now."""
    t = lambda k: escape(_t(k, cyr))
    s = lambda x: escape(_name(x, cyr))
    o = cur.get("o") or {}
    page_ = f'{site}{"cir/" if cyr else ""}poslanik/{cur["adresa"]}' if cur["adresa"] else ""
    name = s(given_first(cur["ime"]))
    shown = f'<a href="{escape(page_)}">{name}</a>' if page_ else name
    side = cur.get("uloga") or cur.get("lista") or cur.get("grupa") or ""
    sheet = about(cur, cyr=cyr, site=site)
    opens = (f'href="{escape(page_)}#funkcije" data-og aria-haspopup="dialog" aria-controls="og" '
             f'aria-label="{t("og_title")}: {name}"')
    out = ['<div class="sp-head">']
    photo = o.get("foto") and str(o["foto"]).replace(".", "").replace("-", "").isalnum()
    if photo:
        img = f'<img class="ph" src="{escape(site)}foto/{escape(o["foto"])}" width="72" height="96" alt="">'
        out.append(f'<a class="ph-a" {opens}>{img}<span class="ph-i" aria-hidden="true">{t("og_i")}</span></a>'
                   if sheet else img)
    i = f' <a class="og-i" {opens}><span aria-hidden="true">{t("og_i")}</span></a>' if sheet and not photo else ""
    # The name smaller on a phone by its longest word (26 Nov 2026, seen by the designer: at 360 px a long surname
    # broke inside the word; at 320 px in Cyrillic every sitting MP's did): its letters in the script shown, the same
    # rule for everyone; live.css gives each count its size, measured over the sitting MPs' names.
    longest = max((len(w) for w in re.split(r"[\s-]+", _name(given_first(cur["ime"]), cyr)) if w), default=0)
    size = f" who-{min(longest, 13)}" if longest >= 6 else ""
    out.append(f'<div><p class="now"><span class="dot" aria-hidden="true"></span><span class="who{size}">{shown}{i}</span></p>')
    if side:
        out.append(f'<p class="side">{s(side)}</p>')
    if not cur["adresa"]:
        out.append(f'<p class="meta">({t("not_listed")})</p>')
    if cur.get("izvor") in ("glas", "prepis"):  # found without a caption (22 Nov 2026): said how, and that it may err
        out.append(f'<p class="meta how-found">{t("by_found")}</p>')
    rok = cur.get("rok") or {}  # a reply's or a point of order's two minutes, where heard (rok.py)
    of = ""
    if rok:
        # each part kept whole, the line breaking only between them: "/ 2 min", "· Povreda Poslovnika", "· čl. 27 i 107"
        kind = t("rk_" + rok["vrsta"]) if rok.get("vrsta") else ""
        parts = [f'<span>/ {rok["sek"] // 60} {t("min")}</span>'] + ([f'<span>· {kind}</span>'] if kind else [])
        named = [int(n) for n in rok.get("clanovi") or [] if str(n).isdigit() and 1 <= int(n) <= 298]
        if named and rok.get("vrsta") == "povreda":  # each article leads to it on the site's page of the Rules
            links = [f'<a href="{escape(site)}{"cir/" if cyr else ""}poslovnik-clanovi#clan-{n}">{n}</a>' for n in named]
            joined = links[0] if len(links) == 1 else ", ".join(links[:-1]) + f' {t("rk_and")} ' + links[-1]
            parts.append(f'<span>· {t("rk_art")} {joined}</span>')
        of = f' <span class="rk">{" ".join(parts)}</span>'
    # "govori od HH:MM" off the line (26 Nov 2026, the maintainer: "Čak možda i govori od bih izbacio"): the clock and a
    # reply's limit stay; the start stays in data-od, which the script counts from.
    out.append(f'<p class="clock"><b class="clk" data-od="{int(cur["od"])}" data-sek="{int(cur["sekundi"])}">'
               f'{_hms(max(0, cur["sekundi"]))}</b>{of}</p></div></div>')
    out.append(_named_line(cur, item, cyr=cyr) + sheet)
    said = ""
    if cur.get("prepis"):
        tail = cur["prepis"]
        tail = ("… " + tail.split(" ", 1)[-1]) if len(tail) >= 400 else tail  # cut at a word, not inside one
        said = (f'<div class="said-now"><p class="src">{t("said_now")}</p><p>{s(tail)}</p>'
                f'<p class="meta"><a href="{"/cir" if cyr else ""}/prepis#t{int(cur["od"])}">{t("said_all")} →</a></p></div>')
    return "".join(out), "", said


def leaders(turns: list[dict]) -> list[tuple[str, int, str]]:
    """Today's speakers by time, longest first: (name, seconds, list)."""
    by: dict[str, list] = {}
    for d in turns:
        x = by.setdefault(d["ime"], [0, d.get("lista") or ""])
        x[0] += max(0, d["sekundi"])
    return sorted(((k, v[0], v[1]) for k, v in by.items()), key=lambda r: (-r[1], r[0]))


def headline(turns: list[dict], *, cyr: bool, when: str = "") -> str:
    """The day in one sentence, by one rule whoever leads: the speaker with the most time, their time, and either the
    largest other list whose speakers together had less, or their share of all the time. With two speakers or more."""
    rows = leaders(turns)
    whole = sum(r[1] for r in rows)
    if len(rows) < 2 or not whole:
        return ""
    name, sec, own = rows[0]
    per: dict[str, int] = {}
    for _, v, l in rows:
        if l and l != "*" and l != own:
            per[l] = per.get(l, 0) + v
    less = sorted((l for l in per if per[l] < sec), key=lambda l: (-per[l], l))
    n = lambda x: _name(x, cyr)
    tail = (_fill(_t("h_more", cyr), n(less[0]), _dur(per[less[0]], cyr)) if less
            else _fill(_t("h_share", cyr), round(100 * sec / whole)))
    return _fill(_t("h_most", cyr), n(when or TEXT["h_today"]), n(given_first(name)), _dur(sec, cyr)) + ", " + tail + "."


# The colour of a list in the day's bars (19 Nov 2026, the maintainer's decision; an exception to "colour only for
# za and protiv", kept to this page). Hues apart from those two, checked for colour-blind readers; a list not named
# here keeps a shade of grey, and the key beside the bar always names each.
LIST_COLOURS = {"Aleksandar Vučić - Srbija pobeđuje": "c-av", "Studentska lista": "c-sl"}
HEX = {"c-av": "#3730a3", "c-sl": "#e11d48", "c-mn": "#0f9d8a", "l1": "#5c5c5c", "l2": "#9a9a9a", "l3": "#c4c4c4",
       "lx": "#d8d8d8"}  # the same colours for the picture (picture.py), which has no stylesheet


def _shades(turns: list[dict]) -> dict[str, str]:
    """The class of each list with time today: its colour (LIST_COLOURS), one colour for sitting MPs of smaller lists
    or no group together, a shade of grey for a list with no colour of its own, hatched grey for the rest."""
    by: dict[str, int] = {}
    for d in turns:
        by[d.get("lista") or ""] = by.get(d.get("lista") or "", 0) + max(0, d["sekundi"])
    named = sorted((k for k in by if k and k != "*" and k not in LIST_COLOURS), key=lambda k: (-by[k], k))
    return {**{k: f"l{min(i + 1, 3)}" for i, k in enumerate(named)}, **LIST_COLOURS, "*": "c-mn", "": "lx"}


def _lists(turns: list[dict], shade: dict[str, str], *, cyr: bool) -> str:
    """The day's time by list as one bar and its key: the turns summed, by the same rule for every list."""
    t = lambda k: escape(_t(k, cyr))
    by: dict[str, list[int]] = {}
    for d in turns:
        x = by.setdefault(d.get("lista") or "", [0, 0])
        x[0] += max(0, d["sekundi"])
        x[1] += 1
    whole = sum(x[0] for x in by.values())
    if not whole or len(turns) < 2:
        return ""
    rows = sorted(by.items(), key=lambda kv: (("*", "").index(kv[0]) + 1 if kv[0] in ("*", "") else 0, -kv[1][0], kv[0]))
    label = lambda k: t("no_list") if not k else t("other_lists") if k == "*" else escape(_name(k, cyr))
    bar = "".join(f'<i class="{shade[k]}" style="width:{100 * v[0] / whole:.2f}%"></i>' for k, v in rows if v[0])
    key = "".join(f'<li><i class="{shade[k]}"></i><span>{label(k)}</span>'
                  f'<b>{_dur(v[0], cyr)}</b><em>{100 * v[0] / whole:.0f}%</em></li>' for k, v in rows if v[0])
    return f'<h3 class="sub">{t("lists")}</h3><div class="lb">{bar}</div><ul class="lk">{key}</ul>'


def _timeline(turns: list[dict], shade: dict[str, str], cur: dict | None, *, cyr: bool, tz: ZoneInfo) -> str:
    """The day as a strip from its first turn to its last: a block a turn, in its list's shade, the one now on marked;
    a click leads to the turn in the list below. Breaks show as gaps."""
    if len(turns) < 3:
        return ""
    t = lambda k: escape(_t(k, cyr))
    start, end = min(d["od"] for d in turns), max(d["do"] for d in turns)
    span = max(60, end - start)
    blocks = []
    for d in sorted(turns, key=lambda d: d["od"]):
        on = cur is not None and d is cur
        tip = f'{_clock(d["od"], tz)} {_name(given_first(d["ime"]), cyr)} · {_minutes(d["sekundi"])} {_t("min", cyr)}'
        blocks.append(f'<a class="{shade.get(d.get("lista") or "", "lx")}{" on" if on else ""}" '
                      f'href="#{"deo" if on else "t" + str(int(d["od"]))}" title="{escape(tip)}" '
                      f'style="left:{100 * (d["od"] - start) / span:.2f}%;width:{max(0.35, 100 * (d["do"] - d["od"]) / span):.2f}%"></a>')
    first = datetime.fromtimestamp(start, tz)
    marks = [f'<span style="left:0">{first.strftime("%H:%M")}</span>']
    hour = first.replace(minute=0, second=0, microsecond=0)
    while True:
        hour = datetime.fromtimestamp(hour.timestamp() + 3600, tz)
        at = 100 * (hour.timestamp() - start) / span
        if at > 97:
            break
        if at > 13:
            marks.append(f'<span style="left:{at:.2f}%">{hour.strftime("%H")}</span>')
    return (f'<h3 class="sub">{t("timeline")}</h3><div class="tl">{"".join(blocks)}</div>'
            f'<div class="tl-ax" aria-hidden="true">{"".join(marks)}</div>')


def _own(name: str) -> str:
    """The page's own styles or script (static/live.css, live.js), beside this module in the repository and the image."""
    return (Path(__file__).parent / "static" / name).read_text(encoding="utf-8")


def _shared(name: str) -> str:
    """A file the page shares with the site's mikrofon page (src/zailiprotiv/templates): copied into the image beside
    this module, read from the repository when run from it (the tests)."""
    for path in (Path(__file__).parent / "static" / name,
                 Path(__file__).resolve().parents[2] / "src" / "zailiprotiv" / "templates" / name):
        if path.is_file():
            return path.read_text(encoding="utf-8")
    return ""


CSS = _own("live.css") + _shared("mikrofon.css")

SCRIPT = _shared("mikrofon.js") + _own("live.js")


def admin_page(key: str, push_key: str) -> str:
    """/upozorenja?k=…: the maintainer turns on, on this device, a notification when this service is down while a
    sitting is on (the counter's watch, worker/). Shown to the key only; the device's push address goes to the
    service, which hands it to the counter with its token."""
    def js(s: str) -> str:  # inside <script>: "</" would end it
        return json.dumps(s).replace("</", r"<\/")

    k = js(key)
    return f"""<!doctype html>
<html lang="sr-Latn"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex">
<title>Upozorenja · Mikrofon</title><style>{CSS}</style></head>
<body><main><h1>Upozorenja za održavanje</h1>
<p class="lead">Ovaj uređaj dobija obaveštenje kad mikrofon.zailiprotiv.rs ne odgovara dve provere zaredom (oko pet minuta),
radnim danom od 7 do 20 h, dok Skupština na svom sajtu piše da je sednica u toku; i još jedno kad ponovo proradi.</p>
<p><button type="button" class="add-btn" id="on">Uključi na ovom uređaju</button>
<button type="button" class="add-btn" id="off">Isključi</button></p>
<p class="meta" id="said"></p><p><a href="/">← Ko sada govori</a></p></main>
<script>
(function () {{
  var key = {js(push_key)}, k = {k}, said = document.getElementById("said");
  function bytes(s) {{ var b = atob(s.replace(/-/g, "+").replace(/_/g, "/")), o = new Uint8Array(b.length);
    for (var i = 0; i < b.length; i++) o[i] = b.charCodeAt(i); return o; }}
  function tell(endpoint, on) {{
    return fetch("/upozorenja?k=" + encodeURIComponent(k), {{ method: "POST", headers: {{ "content-type": "application/json" }},
      body: JSON.stringify({{ endpoint: endpoint, on: on }}) }}).then(function (r) {{ if (!r.ok) throw new Error(r.status); }});
  }}
  document.getElementById("on").onclick = function () {{
    Notification.requestPermission().then(function (p) {{
      if (p !== "granted") throw new Error("dozvola: " + p);
      return navigator.serviceWorker.register("/sw.js", {{ scope: "/" }}).then(function () {{ return navigator.serviceWorker.ready; }});
    }}).then(function (r) {{ return r.pushManager.getSubscription().then(function (s) {{
      return s || r.pushManager.subscribe({{ userVisibleOnly: true, applicationServerKey: bytes(key) }}); }}); }})
      .then(function (s) {{ return tell(s.endpoint, true); }})
      .then(function () {{ said.textContent = "Uključeno na ovom uređaju."; }})
      .catch(function (e) {{ said.textContent = "Nije uspelo: " + e.message; }});
  }};
  document.getElementById("off").onclick = function () {{
    navigator.serviceWorker.getRegistration("/").then(function (r) {{ return r ? r.pushManager.getSubscription() : null; }})
      .then(function (s) {{ if (!s) throw new Error("ovaj uređaj nema prijavu"); return tell(s.endpoint, false); }})
      .then(function () {{ said.textContent = "Isključeno na ovom uređaju."; }})
      .catch(function (e) {{ said.textContent = "Nije uspelo: " + e.message; }});
  }};
}})();
</script></body></html>"""


def service_worker(cyr: bool, key: str, api: str) -> str:
    """The page's service worker (/sw.js; ?j=cir for the Cyrillic page): it only shows the notification when a push
    comes (a push carries nothing: the words are here) and opens the page on a tap. It handles no requests, so the
    page loads as it would without it."""
    words = json.dumps({"title": _t("nt_title", cyr), "body": _t("nt_body", cyr), "url": "/cir/" if cyr else "/",
                        "lang": "sr-Cyrl" if cyr else "sr-Latn", "key": key, "api": api.rstrip("/"), "cir": cyr,
                        "down": _t("al_down", cyr), "down_body": _t("al_down_body", cyr),
                        "back": _t("al_back", cyr), "back_body": _t("al_back_body", cyr),
                        "res": _t("nt_res", cyr), "res_body": _t("nt_res_body", cyr),
                        "sum": _t("nt_sum", cyr), "sum_body": _t("nt_sum_body", cyr)},
                       ensure_ascii=False)
    return f"""const W = {words};
self.addEventListener("install", function () {{ self.skipWaiting(); }});
self.addEventListener("activate", function (e) {{ e.waitUntil(self.clients.claim()); }});
// A push carries nothing: the counter says which it was (the sitting's, or for the maintainer's devices the watch's).
self.addEventListener("push", function (e) {{
  var which = self.registration.pushManager.getSubscription().then(function (s) {{
    return fetch(W.api + "/p/vrsta", {{ method: "POST", headers: {{ "content-type": "text/plain" }},
                                        body: JSON.stringify({{ endpoint: s ? s.endpoint : "" }}) }});
  }}).then(function (r) {{ return r.json(); }}).catch(function () {{ return {{ vrsta: "sednica" }}; }});
  e.waitUntil(which.then(function (k) {{
    var t = W.title, b = W.body, tag = "sednica", n = String(k.min || 0);
    if (k.vrsta === "kvar") {{ t = W.down; b = W.down_body.replace("%1", n); tag = "kvar"; }}
    else if (k.vrsta === "oporavak") {{ t = W.back; b = W.back_body.replace("%1", n); tag = "kvar"; }}
    else if (k.vrsta === "sazetak") {{ t = W.sum; b = W.sum_body; tag = "sazetak"; }}
    else if (k.vrsta === "nastavak") {{ t = W.res; b = W.res_body; }}
    return self.registration.showNotification(t, {{ body: b, icon: "/ikona-192.png", tag: tag, lang: W.lang,
                                                    data: {{ url: W.url }} }});
  }}));
}});
self.addEventListener("notificationclick", function (e) {{
  e.notification.close();
  e.waitUntil(self.clients.matchAll({{ type: "window", includeUncontrolled: true }}).then(function (list) {{
    for (var i = 0; i < list.length; i++) if (new URL(list[i].url).pathname === W.url && list[i].focus) return list[i].focus();
    return self.clients.openWindow(W.url);
  }}));
}});
// A push address the browser renewed: the counter is told the new one.
self.addEventListener("pushsubscriptionchange", function (e) {{
  if (!W.key || !W.api) return;
  var raw = atob(W.key.replace(/-/g, "+").replace(/_/g, "/")), key = new Uint8Array(raw.length);
  for (var i = 0; i < raw.length; i++) key[i] = raw.charCodeAt(i);
  e.waitUntil(self.registration.pushManager.subscribe({{ userVisibleOnly: true, applicationServerKey: key }})
    .then(function (s) {{ return fetch(W.api + "/p", {{ method: "POST", headers: {{ "content-type": "text/plain" }},
      body: JSON.stringify({{ endpoint: s.endpoint, cir: W.cir }}) }}); }}));
}});
"""


def og_text(snap: dict, *, cyr: bool, tz: ZoneInfo) -> tuple[str, str]:
    """The link preview's title and line: what the page is, always the same (24 Nov 2026, the maintainer: a service keeps
    a link's card, so who speaks goes stale), and before a sitting when it goes on."""
    when, notice = announced(snap)
    if when:  # before a sitting: when it goes on, what is next and what is here then (23 Nov 2026, the maintainer: not
        # who spoke how long on the last day, which is what a link pasted before a sitting had been saying)
        nxt = next_item(snap)
        what = f'{_t("ag_next", cyr).capitalize()}: {_name(nxt["tekst"], cyr)}. ' if nxt else ""
        return _name(_says(when, notice), cyr), f'{what}{_t("og_live", cyr)}.'
    return _t("title", cyr), f'{_t("og_live", cyr)}.'


def speech_title(snap: dict, at: int, *, cyr: bool, tz: ZoneInfo) -> str:
    """What a link to a speech says (25 Nov 2026): whose it is (config.SHARE_NAME), as the record has the name now, and
    when; the same form for everyone, and nothing of what was said."""
    d = turn_at(snap.get("danas") or [], at)
    at = int(d["od"]) if d else at
    when = f'{_on_day(datetime.fromtimestamp(at, tz).date().isoformat())} {TEXT["at"]} {_clock(at, tz)}'
    if config.SHARE_NAME and d:
        return _name(_fill(TEXT["sp_title_name"], given_first(d["ime"]), when), cyr)
    return _name(_fill(TEXT["sp_title"], when), cyr)


def _og(snap: dict, *, cyr: bool, url: str, tz: ZoneInfo, speech: int | None = None) -> str:
    """What a pasted link shows (X, Viber, Facebook): the title and line above and the picture of the moment
    (`picture.py`). Nothing in it goes stale; the picture's address changes only with what is drawn on it. A link to a
    speech (`speech`, its second) says that, with the still picture, before a sitting too."""
    if not url:
        return ""
    own = "cir/" if cyr else ""
    title, line = og_text(snap, cyr=cyr, tz=tz)
    mark = "s4"  # the still picture is always the same (picture.render)
    if announced(snap)[0]:  # another picture, so another address: a service keeps a picture by its address
        mark = f'najava3-{announced(snap)[1].get("od", "")}'
    img = f'{url}{own}slika.png?v={mark}'
    if speech:
        title, line = speech_title(snap, speech, cyr=cyr, tz=tz), _t("og_still_line", cyr)
        own, img = f"{own}govor/{int(speech)}", f"{url}{own}govor.png?v=s4"
    e = escape
    return (f'<meta property="og:type" content="website"><meta property="og:url" content="{e(url + own)}">'
            f'<meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(line)}">'
            f'<meta property="og:image" content="{e(img)}"><meta property="og:image:width" content="1200">'
            f'<meta property="og:image:height" content="630"><meta name="twitter:card" content="summary_large_image">'
            f'<meta name="twitter:title" content="{e(title)}"><meta name="twitter:description" content="{e(line)}">'
            f'<meta name="twitter:image" content="{e(img)}">')


def _beacon(token: str) -> str:
    """Cloudflare Web Analytics, as on the site (base.html, the same form): the page counted, no cookies, nobody
    followed; only on the project's own hosts, so a page opened at 127.0.0.1, a test's or the service's own, is not."""
    if not token or not token.isalnum():
        return ""
    return (r'<script>if (/^(mikrofon\.)?zailiprotiv\.rs$/.test(location.hostname)) { let b = document.createElement("script"); b.type = "module"; '
            'b.src = "https://static.cloudflareinsights.com/beacon.min.js"; '
            f'b.setAttribute("data-cf-beacon", \'{{"token": "{token}"}}\'); document.body.appendChild(b); }}</script>')


def player(snap: dict, *, cyr: bool, live: str = "", tz: ZoneInfo | None = None, speech: int | None = None) -> str:
    """The player: while the broadcast is on, the YouTube video of it; between sittings, the last day's recording in
    the broadcaster's archive, from its first turn. Only a button until clicked (AGENTS.md, principle 5)."""
    t = lambda k: escape(_t(k, cyr))
    if snap["stanje"] != "nema_prenosa" and live:
        # A facade (19 Nov 2026, the maintainer's decision, in place of YouTube's player on the page from the start):
        # our own picture of the moment (picture.py) with ▶; a press loads the player, playing, and is counted.
        # Nothing from YouTube loads before it: the page opens faster on a phone.
        # What it shows (24 Nov 2026, the maintainer's choice, in place of the picture for a shared link): our mark and
        # name, always (the speaker stood here for minutes: the maintainer, the same day, "skloni to ko govori").
        word = ('<b class="fx-word"><span class="m-z">За</span> или <span class="m-p">Против</span></b>' if cyr else
                '<b class="fx-word"><span class="m-z">Za</span> ili <span class="m-p">Protiv</span></b>')
        text = t("play_live")
        button = (f'<button type="button" class="play facade" data-yt="{escape(live)}" data-t="0" data-e="mikrofon.pusti" '
                  f'data-text="▶ {text}" aria-label="{text}">'
                  f'<span class="fx fx-calm" aria-hidden="true"><span class="fx-brand">{ARC}{word}</span><span class="fx-live"><i></i>{t("status_live")} · {t("fx_where")}</span></span>'
                  f'<span class="fx-pill" aria-hidden="true">▶ {text}</span></button>')
        note = ""  # what loads and when is told under "Kako ovo radi" (24 Nov 2026, the maintainer: fewer texts)
        # the speaker on the picture, written by the script from the part while the broadcast plays (22 Nov 2026)
        onair = '<p class="on-air" hidden aria-hidden="true"><b></b><span class="oa-side"></span><span class="oa-clk"></span><span class="oa-rk"></span></p>'
        # the line under the picture (22 Nov 2026): the script writes the part's newest lines in, after the delay
        onair += (f'<div class="cc" hidden aria-hidden="true" data-delay="{int(config.CAPTION_DELAY)}"><p class="cc-t"><span></span></p>'
                  f'<p class="cc-n">{t("cc_note")}</p></div>')
    else:
        onair = ""
        parts = snap.get("datoteke") or []
        first = next((d for d in reversed(snap["danas"]) if d.get("datoteka") and d.get("snimak") is not None), None)
        still = next((d for d in reversed(snap["danas"]) if d.get("video") and d.get("snimak") is not None), None)
        if not parts and not first and still and snap.get("otvoreno"):
            # the broadcast is over and the archive has no file yet: its video, from the day's first turn (25 Nov 2026)
            button = (f'<button type="button" class="play" data-yt="{escape(still["video"])}" data-t="{int(still["snimak"])}">'
                      f'▶ {t("play_day")}</button>')
            note = "" if speech else t("yt_note")
            return (f'<section class="player">{_stage(button, onair, cyr)}'
                    + (f'<p class="meta" data-nosnippet>{note}</p>' if note else "") + "</section>")
        if not parts and not first:
            return ""
        url, at = (parts[0]["url"], 0) if parts else (first["datoteka"], int(first["snimak"]))
        button = (f'<button type="button" class="play" data-file="{escape(url)}" data-t="{at}">▶ {t("play_day")}</button>'
                  f'<button type="button" class="play listen" data-zvuk data-file="{escape(url)}" data-t="{at}">🎧 {t("listen_day")}</button>')
        note = escape(_fill(_t("archive_from" if speech else "archive_note", cyr), _name(_on_day(snap.get("dan", "")), cyr))) + " " + t("listen_note")
        if len(parts) > 1:  # the day in several files: each one, by the hours it covers
            chips = "".join(f'<li><button type="button" class="part" data-file="{escape(p["url"])}" data-t="0">'
                            f'{t("part")} {i} · {_clock(p["od"], tz)}–{_clock(p["od"] + p["trajanje"], tz)}</button></li>'
                            for i, p in enumerate(parts, 1))
            return (f'<section class="player">{_stage(button, onair, cyr)}<p class="meta" data-nosnippet>{note}</p>'
                    f'<details class="parts-more"><summary>{t("parts")} ({len(parts)})</summary><ul class="parts">{chips}</ul></details></section>')
    return (f'<section class="player">{_stage(button, onair, cyr)}'
            + (f'<p class="meta" data-nosnippet>{note}</p>' if note else "") + "</section>")


def _stage(button: str, onair: str, cyr: bool) -> str:
    """The screen, the speaker's line over it, and the button that puts the picture back in its place when the
    script has kept it on top while the page is read (22 Nov 2026, the maintainer: watch and read at once)."""
    return (f'<div class="stage"><div class="screen" id="screen">{button}</div>{onair}'
            f'<button type="button" class="mini-x" hidden aria-label="{escape(_t("mini_x", cyr))}">×</button></div>')


def _shared_words(snap: dict, *, cyr: bool, live: bool) -> str:
    """The words of a speech whose link was opened, for the shared script (mikrofon.js), which writes it here and on
    the site's page of the day alike; under the player, where the script says when there is no recording yet."""
    t = lambda k: escape(_t(k, cyr))
    day = escape(_name(f'{_on_day(snap.get("dan", ""))} {TEXT["at"]}', cyr))
    back = f'<a data-w="l" href="{"/cir/" if cyr else "/"}" hidden>{t("sp_live")} →</a>' if live else ""
    return (f'<div id="deljen" hidden><span data-w="p">{t("sp_go")}</span><span data-w="d">{day}</span>'
            f'<span data-w="s">{t("sp_where")}</span><span data-w="c">{t("sp_copied")}</span><span data-w="n">{t("sp_none")}</span>{back}</div>')


def waiting_part(w: dict | None, *, cyr: bool, site: str) -> str:
    """"Dok čekate": the site's quiz, one question at a time like the site's own quiz, and facts (pages_mikrofon),
    shown between sittings; the markup as the site's mikrofon page has it, for the same script and styles."""
    w = w or {}
    quiz, facts = [], w.get("cinjenice") or []  # the quiz no longer shown (22 Nov 2026, the maintainer)
    if not facts:
        return ""
    t = lambda k: escape(_t(k, cyr))
    s = lambda text: escape(cyrillic(text) if cyr else text)
    home = site + ("cir/" if cyr else "")
    href = lambda h: escape(h if h.startswith("http") else home + h)
    n = len(quiz)
    out = []
    if quiz:
        marks = "".join(f'<button type="button" aria-label="{t("question")} {i}">{i}</button>' for i in range(1, n + 1))
        out.append(f'<p>{s(_t("quiz_lead", False).format(n=n))}</p><div class="mq" id="mq">'
                   f'<nav class="mq-strip" hidden aria-label="{t("questions")}">{marks}</nav><ol class="mq-list">')
        for i, q in enumerate(quiz, 1):
            opts = "".join(f'<button type="button" class="mq-o" data-i="{k}">{s(o)}</button>'
                           for k, o in enumerate(q["options"]))
            more = s(q["more"]) if q.get("more") else t("how_counted")
            out.append(f'<li class="mq-q" data-a="{int(q["answer"])}"><p class="mq-n">{t("question")} {i} {t("of")} {n}</p>'
                       f'<h3 class="mq-ask">{s(q["q"])}</h3><div class="mq-opts" role="group">{opts}</div>'
                       f'<details class="mq-why"><summary>{t("answer")}</summary>'
                       f'<p class="mq-verdict"><span class="mq-yes">{t("yes")}</span><span class="mq-no"><b>{t("no")} </b>'
                       f'{t("right_is")} {s(q["options"][int(q["answer"])])}.</span></p>'
                       f'<p>{s(q["why"])} <a href="{href(q["href"])}">{more}</a></p>'
                       f'<p class="mq-next"><span class="mq-auto"></span><button type="button" class="mq-go">'
                       f'{t("see_result" if i == n else "next_q")}</button></p></details></li>')
        out.append('</ol><section class="mq-end" hidden aria-live="polite">'
                   f'<p class="mq-n">{t("result")}</p><p class="mq-big"><span class="mq-got">0</span> {t("of")} {n}</p>'
                   + "".join(f'<p data-k="{k}" hidden>{t("q_" + k)}</p>' for k in ("all", "some", "none"))
                   + f'<p class="mq-acts"><button type="button" class="mq-share">{t("share")}</button> '
                     f'<button type="button" class="mq-again">{t("again")}</button></p>'
                     f'<p class="meta mq-shared" hidden>{t("copied")}</p>'
                     f'<p class="mq-share-text" hidden>{t("share_text")} <span class="mq-got">0</span> {t("of")} {n}. '
                     f'{t("share_end")}</p></section></div>')
    if facts:
        out.append(f'<h2>{t("know")}</h2><ul class="facts">')
        out += [f'<li><a href="{href(f["href"])}">{s(f["text"])}</a></li>' for f in facts]
        out.append(f'</ul><p class="meta">{t("facts_note")}</p>')
    return "\n".join(out)


def _site_name(url: str) -> str:
    """The page's name for a search engine (schema.org WebSite, on the address's home only): as people search for it."""
    data = {"@context": "https://schema.org", "@type": "WebSite", "name": "Mikrofon Za ili Protiv",
            "alternateName": ["Za ili Protiv uživo", "mikrofon.zailiprotiv.rs"], "url": url, "inLanguage": "sr"}
    return '<script type="application/ld+json">' + json.dumps(data, ensure_ascii=False).replace("<", "\\u003c") + "</script>"


def page(snap: dict, *, cyr: bool, site: str, tz: ZoneInfo, url: str = "", waiting: dict | None = None,
         live: str = "", analytics: str = "", api: str = "", push_key: str = "", version: str = "",
         sample: bool = False, speech: int | None = None, sent: bool = False, off: bool | str = False) -> str:
    """`speech`: the second a shared speech began, when its link was opened (deljenje.py): the same page, with that
    link's preview, and the script's button for it. `off`: the page the site builds from its last day read from the
    recording, shown at this address while this service is down (the site's pages_mikrofon, live/edge; 27 Nov 2026):
    the line on top says the broadcast is not followed, and what needs this service (the notification, the app) is
    left out; not for a search engine. As this service's host name ("mikrofon.zailiprotiv.rs"), the script asks for the part
    only there (under the edge), not on the site's host."""
    t = lambda k: escape(_t(k, cyr))
    lang = "sr-Cyrl" if cyr else "sr-Latn"
    base = "/cir/" if cyr else "/"
    other = ("/" if cyr else "/cir/") + (f"govor/{int(speech)}" if speech else "")
    other_label = "Latinica" if cyr else TEXT["script"]
    home = site + ("cir/" if cyr else "")
    alt = (f'<link rel="canonical" href="{escape(url + base[1:])}">'
           f'<link rel="alternate" hreflang="sr-Latn" href="{escape(url)}">'
           f'<link rel="alternate" hreflang="sr-Cyrl" href="{escape(url + "cir/")}">') if url else ""
    title = t("head_title")
    if speech:  # not a page for a search engine: the speeches are the site's (govornici/<day>)
        alt, title = '<meta name="robots" content="noindex">', escape(speech_title(snap, speech, cyr=cyr, tz=tz)) + " · " + t("title_tail")
    brand = _brand(cyr)
    sup = [escape(w) for w in _t("support_cta", cyr).split(" ", 1)]  # "Podrži", and " sajt" where there is room
    if off:
        alt = '<meta name="robots" content="noindex">'
    day = fragment(snap, cyr=cyr, site=site, tz=tz, sent=sent, off=off)
    # "Obavesti me kad sednica počne": under the speaker's box while a broadcast is on; between sittings above the
    # day, which had put it half a phone's screens down, under the last day's summary (20 Nov 2026: one device asked)
    # each with a tile of its own, the app's as it will stand on the home screen, and what it gives under its name
    # (23 Nov 2026, the maintainer: that the page becomes an app was not said)
    from . import slusaj
    # Pills under the player (24 Nov 2026, the maintainer's choice): the sound only (ours, slusaj.py), the notification, the app
    listen = (f'<button type="button" class="pill-b listen-live" data-uzivo="{escape(slusaj.address())}">🎧 <span>{t("listen_pill")}<small>{t("listen_locked")}</small></span></button>'
              if live and snap["stanje"] != "nema_prenosa" and config.LISTEN_PUBLIC and slusaj.fresh(time.time()) else "")
    pills = f"""<section class="pills">{listen}<div class="add-home" hidden{f' data-key="{escape(push_key)}"' if push_key and api.startswith("https://") else ""}>
<div class="ah-row"><button type="button" class="pill-b nt nt-on" hidden aria-label="{t("nt_on")}">{BELL}<span data-nastavak="{t("nt_resume")}">{t("nt_pill")}</span></button><button type="button" class="pill-b add add-go" hidden><span class="pill-m">{ARC}</span><span>{t("app_pill")}</span></button></div>
<p class="nt-done" hidden><button type="button" class="nt-off">{t("nt_off")}</button></p>
<p class="nt-blocked meta" hidden>{t("nt_blocked")}</p>
<p class="nt-err meta" hidden>{t("nt_err")}</p>
<p class="add-ios meta" hidden>{SHARE} {t("add_ios")}</p>
</div><p class="in-app meta" hidden>{t("in_app")}</p></section>
"""
    if off:  # the notification and the app need this service's own worker (sw.js, the manifest)
        pills = ""
    add = ""
    # "Sažetak dana na mejl" (23 Nov 2026, the maintainer's decision): the address goes to the counter, sealed there for
    # the maintainer's key (worker/mejl.js); the form works without the script, which only keeps the reader on the page
    if api.startswith("https://"):
        # `#mejl` is its address on the page, for a link that leads straight to it; its three lines stand with the
        # mail's own marks (23 Nov 2026, the maintainer: a card that stands out)
        see = f' <a class="ml-see" href="{base}mejl/primer">{t("ml_sample")} →</a>' if sample else ""
        now_ = mail_line(snap, sent, speech=bool(speech))  # the script shows another as the day goes on
        lines = "".join(f'<span class="meta" data-k="{k}"{"" if k == now_ else " hidden"}>{t(w)}</span>' for k, w in
                        (("svake", "ml_slim"), ("danas", "ml_today"), ("gotov", "ml_soon"), ("sledeci", "ml_next")))
        add += f"""<details class="ml" id="mejl"><summary><span class="ml-n"><b>{t("ml_kicker")}</b>{lines}</span><span class="ml-p">{t("ml_button")}</span></summary>
<form class="ml-box" method="post" action="{escape(api)}/m">
<h2>{t("ml_title")}</h2>
<ul class="ml-list"><li>{t("ml_1")}</li><li>{t("ml_2")}</li><li>{t("ml_3")}</li></ul>
<p class="ml-when">{t("ml_when")}{see}</p>
<label for="ml-adresa">{t("ml_label")}</label>
<div class="ml-row"><input type="email" id="ml-adresa" name="adresa" autocomplete="email" inputmode="email" required maxlength="254"><input type="hidden" name="pismo" value="{"cir" if cyr else "lat"}"><button type="submit" class="ml-go">{t("ml_button")}</button></div>
<p class="ml-done" role="status" hidden>{t("ml_done")}</p><p class="ml-err" role="alert" hidden>{t("ml_err")}</p>
<p class="ml-fine">{t("ml_fine")} <a href="{escape(site)}privatnost">{t("ml_privacy")}</a></p>
</form></details><button type="button" class="ml-x" hidden aria-label="{t("ml_hide")}">×</button>
"""
        mail_back = f'<p class="ml-back" hidden><span>{t("ml_off")}</span> <button type="button">{t("ml_show")}</button></p>\n'
    mail_back = mail_back if api.startswith("https://") else ""
    uses = (f'. <a href="{escape(site)}{"cir/" if cyr else ""}kako-racunamo#posetioci">{t("uses_counter")}</a> {t("uses_counted")}'
            if api.startswith("https://") else "")
    how_time = (f'<p>{t("gt_how")} <a href="{escape(site)}{"cir/" if cyr else ""}poslovnik-clanovi#pojam-vreme-rasprave">{t("gt_rules")} →</a></p>'
                if config.SHOW_GROUP_TIME else "")
    return f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{t("lead")}">
{alt}
{_og(snap, cyr=cyr, url=url, tz=tz, speech=speech)}
{_site_name(url) if url and not cyr and not speech else ""}
<link rel="icon" type="image/svg+xml" href="{escape(site)}favicon.svg">
{"" if off else f"""<link rel="manifest" href="{base}manifest.webmanifest">
<link rel="apple-touch-icon" href="/ikona-180.png">
<meta name="apple-mobile-web-app-title" content="{t("app_name")}">
<meta name="mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-capable" content="yes">"""}
<meta name="theme-color" content="#ffffff" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#111318" media="(prefers-color-scheme: dark)">
<style>{CSS}</style>
</head>
<body data-base="{base}"{f' data-api="{escape(api)}"' if api.startswith("https://") else ""}{f' data-uzivo-host="{escape(off)}"' if isinstance(off, str) and off else ""}>
<header class="top"><a class="brand" href="{escape(home)}">{brand}</a><span class="top-r"><a class="top-support" href="{escape(home + "podrzi")}" aria-label="{t("support_cta")}"><img src="{escape(site) + "caslav-srce.webp" if off else "/caslav.webp"}" alt="" width="36" height="33"><span>{sup[0]}<span class="lg"> {sup[1]}</span></span></a><a class="top-script" href="{other}" hreflang="{"sr-Latn" if cyr else "sr-Cyrl"}" aria-label="{other_label}"><span class="lg">{other_label}</span><span class="sm">{"Lat" if cyr else "Ћир"}</span></a></span></header>
<main>
<p class="sr" id="ko" aria-live="polite"></p>
<section class="hero"><h1>{t("h1")}</h1></section>
{player(snap, cyr=cyr, live=live, tz=tz, speech=speech)}
{rec_card(cyr=cyr, site=site)}
{_shared_words(snap, cyr=cyr, live=bool(live) and snap["stanje"] != "nema_prenosa")}
{pills}
{(add + day) if snap["stanje"] == "nema_prenosa" else (day + add)}
<p class="rules-cta"><a href="{escape(home + "podrzi")}"><b>{t("support_cta")} →</b><span>{t("support_sub")}</span></a></p>
<p class="site-cta"><a href="{escape(home)}">{t("site_cta")}: zailiprotiv.rs →</a></p>
{waiting_part(waiting, cyr=cyr, site=site) if snap["stanje"] == "nema_prenosa" else ""}
{mail_back}<details class="how"><summary>{t("how_title")}</summary><p>{t("how")}</p><p>{t("yt_live_note")} {t("sp_how")} {t("listen_live_note")}</p><p>{t("nt_how")}</p><p>{t("pr_how")}</p><p>{t("rk_how")}</p><p>{t("why_how")}</p>{how_time}</details>
</main>
<dialog class="og" id="og" aria-labelledby="og-h"><div class="og-in"><button type="button" class="og-x" aria-label="{t("og_close")}">×</button><div class="og-b"></div></div></dialog>
<footer>{"За или Против" if cyr else "Za ili Protiv"}: <a href="{escape(home)}">zailiprotiv.rs</a> · <a href="{escape(site + ("cir/" if cyr else "") + "poslovnik-clanovi#pojmovi")}">{t("rules_word")}</a> · <a href="https://www.instagram.com/zailiprotiv.rs/" rel="me">{"Инстаграм" if cyr else "Instagram"}</a>{(". " + t("counted")) if analytics else ""}{uses}.{f' <span class="ver">{t("version")} {escape(version)}</span>' if version else ""}</footer>
<script>{SCRIPT}</script>
{_beacon(analytics)}
</body>
</html>
"""


def listen_html() -> str:
    """/slusaj/<key>/: listening live, sound only (slusaj.py), the maintainer's trial. The playlist next to the page
    (z.m3u8), played by the phone's own player (Safari, Chrome on Android); the lock screen's player says who speaks
    now, from /stanje.json every 10 s."""
    return f"""<!doctype html>
<html lang="sr-Latn"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex">
<title>Slušaj uživo (proba) · Mikrofon</title><style>{CSS}
.ls-now b {{ display: block; font-size: var(--t-5); }} .ls-now span {{ color: var(--muted); }} audio {{ width: 100%; margin: 1rem 0; }}</style></head>
<body><main><h1>Slušaj uživo <span class="meta">(proba)</span></h1>
<p class="lead">Zvuk prenosa Skupštine, bez slike: svira i kad je ekran zaključan. Kasni oko pola minuta za prenosom.</p>
<div class="ls-now"><b id="who">…</b><span id="side"></span></div>
<audio id="a" controls preload="none" src="z.m3u8"></audio>
<p class="meta" id="note"></p>
<p><a href="/">← Ko sada govori</a></p></main>
<script>
(function () {{
  var a = document.getElementById("a"), who = document.getElementById("who"), side = document.getElementById("side");
  var note = document.getElementById("note"), shown = "";
  if (!a.canPlayType("application/vnd.apple.mpegurl")) note.textContent = "Ovaj pregledač ne pušta ovakav zvuk sam: otvori stranu na telefonu (Safari ili Chrome na Androidu).";
  a.addEventListener("error", function () {{ note.textContent = "Zvuk sada nije dostupan: prenos možda ne ide. Pokušaj ponovo za minut."; }});
  function now() {{
    fetch("/stanje.json", {{ cache: "no-cache" }}).then(function (r) {{ return r.json(); }}).then(function (s) {{
      var c = s && s.sada, name = c ? c.ime.split(" ").slice(1).concat(c.ime.split(" ")[0]).join(" ") : "Narodna skupština";
      var line = c ? ([c.lista, c.uloga, c.grupa].filter(function (x) {{ return x && x !== "*"; }})[0] || "") : (s && s.stanje === "nema_prenosa" ? "Prenos ne ide" : "");
      who.textContent = name; side.textContent = line;
      if ("mediaSession" in navigator && name + line !== shown) {{
        shown = name + line;
        try {{ navigator.mediaSession.metadata = new MediaMetadata({{ title: name, artist: line || "Narodna skupština",
          album: "Skupština uživo · Za ili Protiv", artwork: [{{ src: "/ikona-512.png", sizes: "512x512", type: "image/png" }}] }}); }} catch (e) {{}}
      }}
    }}).catch(function () {{}});
  }}
  now(); setInterval(now, 10000);
}})();
</script></body></html>"""
