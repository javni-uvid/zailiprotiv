"""The page, in Latin and in Cyrillic, from the tracker's snapshot. Only the standard library: the repository's tests
render it. The page loads nothing from elsewhere: the fonts are served with it, the one script is inline."""
from __future__ import annotations

import json
import time
from datetime import datetime
from html import escape
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

from . import config
from .names import cyrillic, given_first
from .steps import steps_shown
from .texts import MONTHS, TEXT, WEEKDAYS, _fill, _name, _t  # noqa: F401

LIVE = "https://www.parlament.gov.rs/prenosi/sednice-narodne-skupstine.2083.html"

ARC = ('<svg class="brand-mark" viewBox="0 0 120 76" aria-hidden="true"><path class="m-za" d="M 14 66 A 46 46 0 0 1 83 26.2"/>'
       '<path class="m-protiv" d="M 89.6 30.8 A 46 46 0 0 1 106 66"/></svg>')
MIC = ('<svg class="mic-mark" viewBox="0 0 76 84" role="img" aria-label="Mikrofon"><rect class="m-za" x="26" y="6" width="24" height="40" rx="12"/>'
       '<path class="m-protiv" d="M 12 36 A 26 26 0 0 0 64 36"/><path class="m-protiv" d="M 38 62 V 78"/></svg>')


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


TURNS_SHOWN = 8  # of a day's turns, the latest this many are listed open; the earlier ones are folded under them


def fragment(snap: dict, *, cyr: bool, site: str, tz: ZoneInfo) -> str:
    """The part of the page that changes: who speaks now, and today's turns."""
    t = lambda k: escape(_t(k, cyr))
    if not config.SHOW_TRANSCRIPT:  # the transcript is written down but not shown (config.SHOW_TRANSCRIPT)
        bare = lambda d: {k: v for k, v in d.items() if k not in ("prepis", "reci", "prepis_ceo")}
        snap = {**snap, "bez_potpisa": None, "sada": bare(snap["sada"]) if snap.get("sada") else snap.get("sada"),
                "danas": [bare(d) for d in snap.get("danas") or []]}
    out = [f'<div id="deo" data-checked="{snap["provereno"]}" data-stanje="{escape(snap.get("stanje", ""))}">']
    cur = snap.get("sada")
    # On the page in this order (the styles' `order`): who is on, the broadcast, the box about the speaker, what is
    # being said, the day. The name and the picture come first on a phone, 86% of the visits (19 Nov 2026).
    for n in sorted(snap.get("obavestenja") or [], key=lambda n: str(n.get("od", "")))[-1:]:  # the newest of what the Assembly has decided, as its own site says it (the site's data/obavestenja.json)
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
        head, box, said = _speaker(cur, cyr=cyr, site=site, tz=tz)
        out.append(head + '</section><section class="sp">' + box)
    else:
        out.append(f'<p class="state">{t("unknown" if snap["stanje"] == "nepoznato" else "none")}</p>')
        if snap["stanje"] == "nema_prenosa":
            out.append(countdown(snap, cyr=cyr, tz=tz))
        out.append('</section><section class="sp">' + _pause(snap, cyr=cyr, tz=tz))
    if snap["provereno"]:
        out.append(f'<p class="meta" id="checked">{t("checked")} <span>0</span> {t("s")}</p>')
    if not said and snap.get("bez_potpisa"):  # nobody's caption on: the chair's words (or the hall's), named as no one's
        u = snap["bez_potpisa"]
        tail = u["tekst"]
        tail = ("… " + tail.split(" ", 1)[-1]) if len(tail) >= 400 else tail
        said = (f'<div class="said-now"><p class="src">{t("said_unsigned")}</p><p>{escape(_name(tail, cyr))}</p>'
                f'<p class="meta"><a href="{"/cir" if cyr else ""}/prepis">{t("said_all")} →</a></p></div>')
    out.append(f'</section><section class="said-sec">{said}</section>{_steps(snap, cyr=cyr, tz=tz, site=site)}<section class="day">')
    if snap.get("ranije") and snap["danas"]:
        when = _date(snap["dan"])
        out.append(f'<h2>{t("last_day")}, {escape(cyrillic(when) if cyr else when)}</h2>')
        if snap.get("snimak"):
            out.append(f'<p class="meta">{t("from_recording")}</p>')
    else:
        out.append(f'<h2>{t("today")}</h2>')
    if snap["danas"]:
        every = snap["danas"] + ([cur] if snap["stanje"] == "govori" and cur else [])
        shade = _shades(every)
        line = headline(every, cyr=cyr, when=_when(snap, cyr))
        out.append(_tiles(every, cyr=cyr))
        if line and (snap["stanje"] == "govori" and cur):  # otherwise the summary above already says it
            out.append(f'<p class="hl">{escape(line)}</p>')
        out.append(_cards(snap, every, shade, cyr=cyr, site=site, tz=tz))
        out.append(_lists(every, shade, cyr=cyr))
        out.append(_timeline(every, shade, cur if snap["stanje"] == "govori" else None, cyr=cyr, tz=tz))
        out.append(_totals(every, cyr=cyr, site=site, shade=shade))
        where = f'{site}{"cir/" if cyr else ""}'
        more = [f'<a href="{escape(where)}govornici">{t("conv_page")} →</a>']
        if snap.get("snimak") and snap.get("dan"):  # a day read from the recording has its page on the site
            more.insert(0, f'<a href="{escape(where)}govornici/{escape(snap["dan"])}">{t("day_page")} →</a>')
        out.append('<p class="more">' + " · ".join(more) + "</p>")
        out.append(f'<h3 class="sub">{t("all_turns")}</h3>')
        rows = []
        for d in snap["danas"]:
            nm = escape(_name(given_first(d["ime"]), cyr))
            if d["adresa"]:
                nm = f'<a href="{escape(site + ("cir/" if cyr else "") + "poslanik/" + d["adresa"])}">{nm}</a>'
            side = d["uloga"] or d["grupa"]
            side = f' <span class="meta">{escape(_name(side, cyr))}</span>' if side else ""
            if d.get("reci"):
                side += (f' <a class="meta said" href="{"/cir" if cyr else ""}/prepis#t{int(d["od"])}">{t("said_link")}</a>')
            rows.append(f'<li id="t{int(d["od"])}"><span class="time">{_clock(d["od"], tz)}–{_clock(d["do"], tz)}</span> {nm}{side}'
                        f' <span class="meta">· {_minutes(d["sekundi"])} {t("min")}</span>{_recording(d, cyr)}</li>')
        # A long day's list was half the page on a phone: the latest turns stand (the list is newest first), the
        # earlier ones open on a tap, and by themselves when the day's strip or an address leads to one of them
        # (the script's `unfold`).
        fold = len(rows) > TURNS_SHOWN + 4
        out.append('<ol class="turns">' + "".join(rows[:TURNS_SHOWN] if fold else rows) + "</ol>")
        if fold:
            out.append(f'<details class="turns-more" id="raniji-govori"><summary>{t("turns_earlier")} ({len(rows) - TURNS_SHOWN})</summary>'
                       f'<ol class="turns">{"".join(rows[TURNS_SHOWN:])}</ol></details>')
    else:
        out.append(f'<p class="meta">{t("today_none")}</p>')
    out.append("</section></div>")
    return "\n".join(out)



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
    on = next((x for x in items if x["stanje"] in ("u_toku", "na_redu")), None)
    head = f'<b>{t("ag")}</b> <span>{escape(_fill(_t("ag_done", cyr), done, len(items)))}</span>'
    if on:
        head += f'<span class="ag-on">{t("ag_now" if on["stanje"] == "u_toku" else "ag_next")}: {s(on["tekst"])}</span>'
    rows = []
    for x in items:
        mark = {"gotova": "✓", "u_toku": "●", "na_redu": "→"}.get(x["stanje"], "")
        state = ""
        if x["stanje"] == "gotova":
            when = _date(x["kada"]).rsplit(" ", 1)[0] if x.get("kada") else ""
            src = t("ag_site" if x["izvor"] == "sajt" else "ag_said")
            state = f'<span class="src">{t("ag_gotova")}{", " + escape(cyrillic(when) if cyr else when) if when else ""} · {src}</span>'
            if x.get("sta"):
                state += f'<span class="ag-what">{s(x["sta"])}</span>'
        elif x["stanje"] == "u_toku":
            state = f'<span class="src">{t("ag_now")} · {t("ag_said")}</span>'
        elif x["stanje"] == "na_redu":
            state = f'<span class="src">{t("ag_next")}</span>'
        rows.append(f'<li class="ag-{x["stanje"] or "ceka"}"><i aria-hidden="true">{mark}</i><span><b>{x["n"]}.</b> {s(x["tekst"])}{state}</span></li>')
    title = s(a.get("naslov", ""))
    if str(a.get("url", "")).startswith("https://"):
        title = f'<a href="{escape(a["url"])}">{title}</a>'
    return (f'<details class="agenda" id="dnevni-red"><summary>{head}</summary><p class="meta">{title}</p>'
            f'<ol>{"".join(rows)}</ol><p class="meta">{t("ag_note")}</p></details>')


def _steps(snap: dict, *, cyr: bool, tz: ZoneInfo, site: str = "") -> str:
    """The day's steps as a line of time, newest first (steps_shown): the hour and the line, for what was heard in
    the chair's words; the first eight shown, the rest folded. What the Assembly wrote on the sitting's page is not
    on the line of time (20 Nov 2026, the maintainer: it mixed with the steps; its hour is when we read it, hours
    after the event): its sentences stand whole under the line, folded, in the same box."""
    every = steps_shown(snap)
    if not every:
        return ""
    rows = [e for e in every if e["izvor"] != "sajt"]
    written = [e for e in every if e["izvor"] == "sajt"]
    t = lambda k: escape(_t(k, cyr))
    s = lambda x: escape(_name(x, cyr))

    def line(e: dict) -> str:
        if e.get("rec"):
            head, _, who = e["naslov"].partition(": ")
            who = s(who)
            if e.get("adresa") and str(e["adresa"]).replace("-", "").isalnum():
                who = f'<a href="{escape(site + ("cir/" if cyr else "") + "poslanik/" + e["adresa"])}">{who}</a>'
            body = f'<p class="st-floor">{s(head)}: <b>{who}</b></p>'
        else:
            title = s(e["naslov"])
            if e.get("pojam") and site:  # what the Rules say of this kind of step, on the site (steps.STEP_TERM)
                href = site + ("cir/" if cyr else "") + "poslovnik-clanovi#pojam-" + e["pojam"]
                title = f'<a href="{escape(href)}" title="{t("steps_rules")}">{title}</a>'
            body = f'<p class="st-title">{title}</p>' + (f'<p class="st-what">{s(e["opis"])}</p>' if e["opis"] else "")
        return (f'<li class="st-{e["izvor"]}{" st-rec" if e.get("rec") else ""}"><span class="time">{_clock(e["t"], tz)}</span><i aria-hidden="true"></i>'
                f'<div>{body}</div></li>')
    first, rest = rows[:8], rows[8:]
    more = (f'<details><summary>{t("steps_more")} ({len(rows)})</summary><ol class="steps">{"".join(line(e) for e in rest)}</ol></details>'
            if rest else "")
    said_key = "steps_model" if any(e.get("model") for e in rows) else "steps_said"
    key = f'<p class="st-key"><span class="st-prepis"><i aria-hidden="true"></i>{t(said_key)}</span></p>' if rows else ""
    official = ""
    if written:  # the Assembly's sentences whole, in the order they stood; one line says where from and when read
        links = "".join(f' <a href="{escape(u)}">{t("steps_site")} ↗</a>' for u in dict.fromkeys(
            str(e["url"]) for e in written) if u.startswith("https://")) or " " + t("steps_site")
        read = escape(_fill(_t("steps_published", cyr), _clock(max(e["t"] for e in written), tz)))
        sentences = "".join("<p>" + s(e["opis"]) + "</p>" for e in written)
        official = (f'<details class="st-written"{"" if rows else " open"}><summary>{t("steps_written")} ({len(written)})</summary>'
                    f'{sentences}<p class="st-src">{read}{links}</p></details>')
    # between sittings, the last sitting day's steps, under its date (20 Nov 2026: after midnight the list was gone)
    head = t("steps")
    if snap.get("ranije") and snap.get("dan"):
        when = _date(snap["dan"])
        head = f'{t("steps_then")}, {escape(cyrillic(when) if cyr else when)}'
    line_ = f'<p class="meta">{t("steps_lead")}</p><ol class="steps">{"".join(line(e) for e in first)}</ol>{more}{key}' if rows else ""
    return f'<section class="steps-sec"><h2>{head}</h2>{line_}{official}</section>'


def _tiles(turns: list[dict], *, cyr: bool) -> str:
    """The day in four numbers: time on the floor, turns, speakers, and the words written down so far (when the
    transcript is on)."""
    t = lambda k: escape(_t(k, cyr))
    if len(turns) < 2:
        return ""
    words = sum(d.get("reci", 0) for d in turns)
    cells = [(_dur(sum(max(0, d["sekundi"]) for d in turns), cyr), t("n_time")), (len(turns), t("n_turns")),
             (len({d["ime"] for d in turns}), t("n_people"))]
    if words:
        cells.append((f"{words:,}".replace(",", "."), t("n_words")))
    return '<dl class="tiles">' + "".join(f'<div><dd>{escape(str(v))}</dd><dt>{k}</dt></div>' for v, k in cells) + "</dl>"


def _cards(snap: dict, turns: list[dict], shade: dict[str, str], *, cyr: bool, site: str, tz: ZoneInfo) -> str:
    """The day in a few cards to tap through (19 Nov 2026, the maintainer's choice): the whole time, who had the
    most, the time by list, the longest turn, who came up most often, and the way to the site. Every card by a rule,
    the same whoever it names. The cards wait hidden in the page; the script shows them full screen on a tap."""
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
    card = lambda kicker, body: f'<section class="st-c"><p class="st-k">{kicker}</p>{body}</section>'
    out = [card(escape(when), f'<p class="st-big">{_dur(whole, cyr)}</p><p class="st-s">{t("st_total")}</p>'
                              f'<p class="st-row"><b>{len(turns)}</b> {t("n_turns")} · <b>{len(rows)}</b> {t("n_people")}</p>')]
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
    out.append(card(t("st_end"), f'<p class="st-name">{t("st_site")}</p>'
                                 f'<p><a class="cta" href="{escape(home)}">zailiprotiv.rs →</a></p>'))
    go = (f'<p class="acts st-go"><button type="button" class="share-now st-open">▶ {t("st_open")}</button></p>'
          if snap["stanje"] == "govori" and snap.get("sada") else "")
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
        second = f' · {t("said_second")}' if d.get("ceo") else ""
        rows.append(f'<article id="t{int(d["od"])}"><h2>{nm} <span class="meta">{_clock(d["od"], tz)}–{_clock(d["do"], tz)}'
                    f' · {_minutes(d["sekundi"])} {t("min")}{second}</span></h2><p>{text}</p>'
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
<header class="top"><a class="brand" href="{escape(home)}">{brand}</a><span class="top-r"><a class="mic" href="{base}" title="{t("title")}">{MIC}</a><a href="{base}">{t("said_back")}</a></span></header>
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
    now = time.time() if now is None else now
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
    return (f'<div class="nx"><p class="src">{t("coming")}</p>{big}'
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


def summary_box(snap: dict, *, cyr: bool) -> str:
    """The model's summary of the day so far (sudija.py), while nobody is on: the day's once written (what was
    decided first), else the latest stretch, the earlier ones folded; always with what wrote it and from what."""
    s = snap.get("sazetak")
    if not isinstance(s, dict) or not s.get("ukratko"):
        return ""
    t = lambda k: escape(_t(k, cyr))
    n = lambda x: escape(_name(str(x), cyr))
    def items(rows) -> str:
        """Each step as a line: its time, its words, and a vote's figures under it, told the same way each time
        (`sudija.vote_text`, kept with the summary as `glasovi`; the sum was checked there)."""
        out = ""
        for o in rows or []:
            if isinstance(o, dict) and o.get("sta"):
                votes = f'<span class="sum-v">{n(o["glasovi"])}</span>' if o.get("glasovi") else ""
                out += f'<li><b>{escape(str(o.get("vreme", "")))}</b> {n(o["sta"])}{votes}</li>'
        return f'<ul class="sum-dec">{out}</ul>' if out else ""

    if s.get("vrsta") == "dan":
        head = t("sum_day")
        body = items(s.get("odluke")) + f'<p>{n(s["ukratko"])}</p>'
    else:
        head = escape(_fill(_t("sum_part", cyr), str(s.get("do") or "")))
        body = f'<p>{n(s["ukratko"])}</p>' + items(s.get("tok"))
        if s.get("ranije"):
            body += (f'<details><summary>{t("sum_earlier")}</summary>'
                     + "".join(f"<p>{n(x)}</p>" for x in s["ranije"]) + "</details>")
    return f'<div class="sum"><p class="src">{head}</p>{body}<p class="meta">{t("sum_note")}</p></div>'


def _pause(snap: dict, *, cyr: bool, tz: ZoneInfo) -> str:
    """While nobody is on (a break, or between sittings): the day so far in place of an empty box. The sentence of the
    day, the three with the most time, and the picture of it to share (`picture.py`, the page's link preview too)."""
    turns = snap.get("danas") or []
    line = headline(turns, cyr=cyr, when=_when(snap, cyr))
    if not line:
        return ""
    t = lambda k: escape(_t(k, cyr))
    if snap.get("ranije"):
        when = _date(snap["dan"])
        head = f'{t("last_day")}, {escape(cyrillic(when) if cyr else when)}'
    else:
        head = t("so_far")
    top = "".join(f'<li><b>{escape(_name(given_first(n), cyr))}</b> <span>{_dur(sec, cyr)}</span></li>'
                  for n, sec, _ in leaders(turns)[:3])
    src = ("/cir" if cyr else "") + "/slika.png"
    tall = ("/cir" if cyr else "") + "/prica.png"
    coming = snap.get("sazvano")
    nxt = ""
    if coming and coming.get("pocinje") and snap["stanje"] != "nema_prenosa":  # between sittings: the countdown says it
        day = _date(coming["pocinje"][:10])
        hour = f' {t("at")} {escape(coming["pocinje"][11:16])}' if len(coming["pocinje"]) > 10 else ""
        title = escape(_name(coming.get("naslov", ""), cyr))
        if str(coming.get("url", "")).startswith("https://"):
            title = f'<a href="{escape(coming["url"])}">{title}</a>'
        nxt = f'<p class="pz-next"><b>{t("coming")}:</b> {escape(cyrillic(day) if cyr else day)}{hour}. {title}</p>'
    return (f'<div class="o pz"><p class="src">{head}</p><p class="hl">{escape(line)}</p>{summary_box(snap, cyr=cyr)}'
            f'<ol class="pz-top">{top}</ol>{nxt}'
            f'<p class="acts"><button type="button" class="share-now st-open">▶ {t("st_open")}</button> '
            f'<button type="button" class="share-now share-day" data-src="{src}" '
            f'data-text="{t("sd_text")}" data-done="{t("sh_done")}">{t("share_day")}</button> '
            f'<button type="button" class="share-now share-day tall" data-src="{tall}" '
            f'data-text="{t("sd_text")}" data-done="{t("sh_done")}">{t("share_tall")}</button></p>'
            f'<p class="meta share-said" hidden></p></div>')


def _dur(sec: int, cyr: bool = False) -> str:
    h, m = divmod(max(60, sec) // 60, 60)
    hour, minute = ("ч", "мин") if cyr else ("h", "min")
    return f"{h} {hour} {m} {minute}" if h else f"{m} {minute}"


def _totals(turns: list[dict], *, cyr: bool, site: str, top: int = 8, shade: dict[str, str] | None = None) -> str:
    """The day's time on the floor per speaker, longest first, as bars: the turns summed, by the same rule for all."""
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
    for name, (sec, n, slug, side) in rows[:top]:
        nm = escape(_name(given_first(name), cyr))
        if slug:
            nm = f'<a href="{escape(site + ("cir/" if cyr else "") + "poslanik/" + slug)}">{nm}</a>'
        out.append(line(nm, side, sec, n, cls=tone.get(name, "")))
    rest = rows[top:]
    if rest:
        out.append(line(f'{t("totals_rest")} {len(rest)} {t("speakers_n")}', "", sum(r[0] for _, r in rest),
                        sum(r[1] for _, r in rest), rest=True))
    out.append("</div>")
    return "".join(out)


def _speaker(cur: dict, *, cyr: bool, site: str, tz: ZoneInfo) -> tuple[str, str, str]:
    """The speaker: the portrait (an MP's, from the Assembly, served by the site), the name, the list, a clock that
    runs, and a box: the day so far and the convocation first (there for every speaker), then one line about the MP
    at a time, each saying where it is from, the way to the MP's page and the picture to share. The same for every
    speaker, by rules; a name not on the site's list gets the day's numbers only."""
    t = lambda k: escape(_t(k, cyr))
    s = lambda x: escape(_name(x, cyr))
    o = cur.get("o") or {}
    page_ = f'{site}{"cir/" if cyr else ""}poslanik/{cur["adresa"]}' if cur["adresa"] else ""
    name = s(given_first(cur["ime"]))
    shown = f'<a href="{escape(page_)}">{name}</a>' if page_ else name
    side = cur.get("uloga") or cur.get("lista") or cur.get("grupa") or ""
    out = ['<div class="sp-head">']
    if o.get("foto") and str(o["foto"]).replace(".", "").replace("-", "").isalnum():
        out.append(f'<img class="ph" src="{escape(site)}foto/{escape(o["foto"])}" width="72" height="96" alt="">')
    out.append(f'<div><p class="now"><span class="dot" aria-hidden="true"></span><span class="who">{shown}</span></p>')
    if side:
        out.append(f'<p class="side">{s(side)}</p>')
    if not cur["adresa"]:
        out.append(f'<p class="meta">({t("not_listed")})</p>')
    longer = (" · " + s(TEXT["longest"] if cur["duze"] >= 100 else TEXT["longer"].format(p=cur["duze"]))) if cur.get("duze", 0) >= 50 else ""
    out.append(f'<p class="clock"><b class="clk" data-od="{int(cur["od"])}" data-sek="{int(cur["sekundi"])}">'
               f'{_hms(max(0, cur["sekundi"]))}</b> <span>{t("since")} {_clock(cur["od"], tz)}{longer}</span></p></div></div>')
    head, out = "".join(out), []
    out.append('<div class="o">')
    today, line = cur.get("danas"), ""
    if today:
        bits = [TEXT["d_turn"].format(n=today["n"]), TEXT["d_total"].format(t=_dur(today["sek"], cyr))]
        if today["od"] >= 2:
            bits.append(TEXT["d_rank"].format(m=today["mesto"], n=today["od"]))
        out.append(f'<dl class="nums"><div><dt>{t("d_today")}</dt><dd>{s(" · ".join(bits))}</dd></div>')
        conv = cur.get("saziv")
        if conv:
            words = TEXT["d_conv_line"].format(t=_dur(conv["sek"], cyr), n=conv["n"],
                                               w=TEXT["speeches_1"] if conv["n"] == 1 else TEXT["speeches_n"])
            out.append(f'<div><dt>{escape(str(conv["broj"]))}. {t("d_conv")}</dt><dd>{s(words)}</dd></div>')
        out.append("</dl>")
        line = TEXT["sh_today"].format(t=_dur(today["sek"], cyr), n=today["n"]) if today["n"] > 1 else TEXT["sh_first"]
    lines = [c for c in o.get("c") or [] if c.get("t")]
    if not lines and o.get("f"):  # the site's file as it was before 19 Nov 2026
        lines = [{"t": f, "iz": ""} for f in o["f"]]
    if lines:
        items = "".join(f'<li>{f"""<span class="src">{s(c["iz"])}</span>""" if c.get("iz") else ""}{s(c["t"])}</li>'
                        for c in lines)
        more = (f'<button type="button" class="rot-next" aria-label="{t("next_fact")}"><span class="rot-n">1/{len(lines)}'
                f'</span> ›</button>') if len(lines) > 1 else ""
        out.append(f'<div class="rot-w"><ul class="rot">{items}</ul>{more}</div>')
    said = ""
    if cur.get("prepis"):
        tail = cur["prepis"]
        tail = ("… " + tail.split(" ", 1)[-1]) if len(tail) >= 400 else tail  # cut at a word, not inside one
        said = (f'<div class="said-now"><p class="src">{t("said_now")}</p><p>{s(tail)}</p>'
                f'<p class="meta"><a href="{"/cir" if cyr else ""}/prepis#t{int(cur["od"])}">{t("said_all")} →</a></p></div>')
    when = _date(datetime.fromtimestamp(cur["do"], tz).strftime("%Y-%m-%d")) + f' u {_clock(cur["do"], tz)}'
    data = {"head": _t("sh_head", cyr), "name": _name(given_first(cur["ime"]), cyr), "side": _name(side, cyr),
            "already": _t("sh_already", cyr), "min": _t("min", cyr), "line": _name(line, cyr), "when": _name(when, cyr),
            "note": _t("sh_note", cyr), "text": _t("sh_text", cyr), "done": _t("sh_done", cyr)}
    attrs = " ".join(f'data-{k}="{escape(v)}"' for k, v in data.items())
    cta = f'<a class="cta" href="{escape(page_)}">{t("o_more")} →</a> ' if page_ else ""
    tall = (f' <button type="button" class="share-now share-day tall" data-src="{"/cir" if cyr else ""}/prica.png" '
            f'data-text="{t("sd_text")}" data-done="{t("sh_done")}">{t("share_tall")}</button>')
    out.append(f'<p class="acts">{cta}<button type="button" class="share-now" {attrs}>{t("share_now")}</button>{tall}</p>'
               f'<p class="meta share-said" hidden></p></div>')
    return head, "".join(out), said


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
            f'<div class="tl-ax" aria-hidden="true">{"".join(marks)}</div><p class="meta">{t("timeline_note")}</p>')


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
    k = json.dumps(key)
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
  var key = {json.dumps(push_key)}, k = {k}, said = document.getElementById("said");
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
    """The link preview's title and line: who is on and since when, or the sentence of the day, or what the page is."""
    cur = snap.get("sada")
    turns = (snap.get("danas") or []) + ([cur] if snap["stanje"] == "govori" and cur else [])
    line = headline(turns, cyr=cyr, when=_when(snap, cyr)) or _t("lead", cyr)
    if snap["stanje"] == "govori" and cur:
        side = cur.get("lista", "").strip("*") or cur.get("uloga") or cur.get("grupa") or ""
        title = _fill(_t("og_now", cyr), _name(given_first(cur["ime"]), cyr)) + (f" ({_name(side, cyr)})" if side else "")
        return title, _fill(_t("og_since", cyr), _clock(cur["od"], tz)) + ". " + line
    return _t("title", cyr), line


def _og(snap: dict, *, cyr: bool, url: str, tz: ZoneInfo) -> str:
    """What a pasted link shows (X, Viber, Facebook): the title and line above and the picture of the moment
    (`picture.py`). The picture's address changes with the turn, since some services keep a picture by its address."""
    if not url:
        return ""
    title, line = og_text(snap, cyr=cyr, tz=tz)
    cur = snap.get("sada") if snap["stanje"] == "govori" else None
    mark = int(cur["od"]) if cur else f'{snap.get("dan", "")}-{len(snap.get("danas") or [])}'
    img = f'{url}{"cir/" if cyr else ""}slika.png?v={mark}'
    e = escape
    return (f'<meta property="og:type" content="website"><meta property="og:url" content="{e(url + ("cir/" if cyr else ""))}">'
            f'<meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(line)}">'
            f'<meta property="og:image" content="{e(img)}"><meta property="og:image:width" content="1200">'
            f'<meta property="og:image:height" content="630"><meta name="twitter:card" content="summary_large_image">'
            f'<meta name="twitter:title" content="{e(title)}"><meta name="twitter:description" content="{e(line)}">'
            f'<meta name="twitter:image" content="{e(img)}">')


def _beacon(token: str) -> str:
    """Cloudflare Web Analytics, as on the site (base.html): the page counted, no cookies, nobody followed."""
    if not token or not token.isalnum():
        return ""
    return ('<script type="module" src="https://static.cloudflareinsights.com/beacon.min.js" '
            f'data-cf-beacon=\'{{"token": "{token}"}}\'></script>')


def player(snap: dict, *, cyr: bool, live: str = "", tz: ZoneInfo | None = None) -> str:
    """The player: while the broadcast is on, the YouTube video of it; between sittings, the last day's recording in
    the broadcaster's archive, from its first turn. Only a button until clicked (AGENTS.md, principle 5)."""
    t = lambda k: escape(_t(k, cyr))
    if snap["stanje"] != "nema_prenosa" and live:
        # A facade (19 Nov 2026, the maintainer's decision, in place of YouTube's player on the page from the start):
        # our own picture of the moment (picture.py) with ▶; a press loads the player, playing, and is counted.
        # Nothing from YouTube loads before it: the page opens faster on a phone.
        img = ("/cir" if cyr else "") + "/slika.png"
        button = (f'<button type="button" class="play facade" data-yt="{escape(live)}" data-t="0" data-e="mikrofon.pusti">'
                  f'<img src="{img}" alt="" width="1200" height="630" decoding="async">'
                  f'<span>▶ {t("play_live")}</span></button>')
        note = t("yt_live_note")
    else:
        parts = snap.get("datoteke") or []
        first = next((d for d in reversed(snap["danas"]) if d.get("datoteka") and d.get("snimak") is not None), None)
        if not parts and not first:
            return ""
        url, at = (parts[0]["url"], 0) if parts else (first["datoteka"], int(first["snimak"]))
        button = f'<button type="button" class="play" data-file="{escape(url)}" data-t="{at}">▶ {t("play_day")}</button>'
        note = t("archive_note")
        if len(parts) > 1:  # the day in several files: each one, by the hours it covers
            chips = "".join(f'<li><button type="button" class="part" data-file="{escape(p["url"])}" data-t="0">'
                            f'{t("part")} {i} · {_clock(p["od"], tz)}–{_clock(p["od"] + p["trajanje"], tz)}</button></li>'
                            for i, p in enumerate(parts, 1))
            return (f'<section class="player"><div class="screen" id="screen">{button}</div><ul class="parts">{chips}'
                    f'</ul><p class="meta">{note}</p></section>')
    return f'<section class="player"><div class="screen" id="screen">{button}</div><p class="meta">{note}</p></section>'


def waiting_part(w: dict | None, *, cyr: bool, site: str) -> str:
    """"Dok čekate": the site's quiz, one question at a time like the site's own quiz, and facts (pages_mikrofon),
    shown between sittings; the markup as the site's mikrofon page has it, for the same script and styles."""
    w = w or {}
    quiz, facts = w.get("kviz") or [], w.get("cinjenice") or []
    if not quiz and not facts:
        return ""
    t = lambda k: escape(_t(k, cyr))
    s = lambda text: escape(cyrillic(text) if cyr else text)
    home = site + ("cir/" if cyr else "")
    href = lambda h: escape(h if h.startswith("http") else home + h)
    n = len(quiz)
    out = [f'<h2>{t("wait_title")}</h2>']
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
        out.append(f'<h3>{t("know")}</h3><ul class="facts">')
        out += [f'<li><a href="{href(f["href"])}">{s(f["text"])}</a></li>' for f in facts]
        out.append(f'</ul><p class="meta">{t("facts_note")}</p>')
    return "\n".join(out)


def page(snap: dict, *, cyr: bool, site: str, tz: ZoneInfo, url: str = "", waiting: dict | None = None,
         live: str = "", analytics: str = "", api: str = "", push_key: str = "", version: str = "") -> str:
    t = lambda k: escape(_t(k, cyr))
    lang = "sr-Cyrl" if cyr else "sr-Latn"
    base = "/cir/" if cyr else "/"
    other = "/" if cyr else "/cir/"
    other_label = "Latinica" if cyr else TEXT["script"]
    home = site + ("cir/" if cyr else "")
    alt = (f'<link rel="canonical" href="{escape(url + base[1:])}">'
           f'<link rel="alternate" hreflang="sr-Latn" href="{escape(url)}">'
           f'<link rel="alternate" hreflang="sr-Cyrl" href="{escape(url + "cir/")}">') if url else ""
    brand = _brand(cyr)
    return f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{t("title")} · {"За или Против" if cyr else "Za ili Protiv"}</title>
<meta name="description" content="{t("lead")}">
{alt}
{_og(snap, cyr=cyr, url=url, tz=tz)}
<link rel="icon" type="image/svg+xml" href="{escape(site)}favicon.svg">
<link rel="manifest" href="{base}manifest.webmanifest">
<link rel="apple-touch-icon" href="/ikona-180.png">
<meta name="apple-mobile-web-app-title" content="{t("app_name")}">
<meta name="mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-capable" content="yes">
<meta name="theme-color" content="#ffffff" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#111318" media="(prefers-color-scheme: dark)">
<style>{CSS}</style>
</head>
<body data-base="{base}"{f' data-api="{escape(api)}"' if api.startswith("https://") else ""}>
<header class="top"><a class="brand" href="{escape(home)}">{brand}</a><span class="top-r"><a class="mic" href="{base}" title="{t("title")}">{MIC}</a><a href="{other}" hreflang="{"sr-Latn" if cyr else "sr-Cyrl"}">{other_label}</a></span></header>
<main>
<p class="sr" id="ko" aria-live="polite"></p>
<section class="hero">
<div><h1>{t("title")}</h1><p class="hero-sub">{t("hero_sub")}</p></div>
<a class="hero-cta" href="{escape(home)}"><span>{t("hero_cta")}</span><b>zailiprotiv.rs →</b></a>
</section>
{player(snap, cyr=cyr, live=live, tz=tz)}
{fragment(snap, cyr=cyr, site=site, tz=tz)}
<section class="add-home" hidden{f' data-key="{escape(push_key)}"' if push_key and api.startswith("https://") else ""}>
<p class="nt" hidden><button type="button" class="add-btn nt-on">{t("nt_on")}</button></p>
<p class="nt-done" hidden>{t("nt_done")} <button type="button" class="nt-off">{t("nt_off")}</button></p>
<p class="nt-blocked meta" hidden>{t("nt_blocked")}</p>
<p class="nt-err meta" hidden>{t("nt_err")}</p>
<p class="add" hidden><button type="button" class="add-btn add-go">{t("add_home")}</button> <span class="meta">{t("add_sub")}</span></p>
<p class="add-ios meta" hidden>{t("add_ios")}</p>
<p class="nt-note meta" hidden>{t("nt_note")}</p>
</section>
<p class="rules-cta"><a href="{escape(site + ("cir/" if cyr else "") + "poslovnik-clanovi#pojmovi")}"><b>{t("rules_cta")} →</b><span>{t("rules_sub")}</span></a></p>
<p class="site-cta"><a href="{escape(home)}">{t("site_cta")}: zailiprotiv.rs →</a></p>
{waiting_part(waiting, cyr=cyr, site=site) if snap["stanje"] == "nema_prenosa" else ""}
<h2>{t("how_title")}</h2>
<p>{t("how")}</p>
<p><a href="{LIVE}">{t("live")}</a> · <a href="{escape(home)}">{t("home")}</a></p>
</main>
<footer>{"За или Против" if cyr else "Za ili Protiv"}: <a href="{escape(home)}">zailiprotiv.rs</a>{(". " + t("counted")) if analytics else ""}{(". " + t("uses_counted")) if api.startswith("https://") else ""}.{f' <span class="ver">{t("version")} {escape(version)}</span>' if version else ""}</footer>
<script>{SCRIPT}</script>
{_beacon(analytics)}
</body>
</html>
"""
