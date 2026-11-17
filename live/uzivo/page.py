"""The page, in Latin and in Cyrillic, from the tracker's snapshot. Only the standard library: the repository's tests
render it. The page loads nothing from elsewhere: the fonts are served with it, the one script is inline."""
from __future__ import annotations

from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

from .names import cyrillic, given_first

LIVE = "https://www.parlament.gov.rs/prenosi/sednice-narodne-skupstine.2083.html"

TEXT = {
    "title": "Ko sada govori u Skupštini",
    "lead": "Govornik u Narodnoj skupštini u ovom trenutku, pročitan iz potpisa u prenosu uživo.",
    "since": "govori od",
    "min": "min",
    "unknown": "Prenos je u toku, ali se ime govornika sada ne vidi u potpisu.",
    "none": "Skupština sada ne zaseda ili prenos nije dostupan.",
    "not_listed": "ime iz potpisa; nije na spisku poslanika ovog sajta",
    "today": "Danas su govorili",
    "today_none": "Danas još niko nije prepoznat u prenosu.",
    "last_day": "Poslednji dan sednice",
    "recording": "snimak",
    "recording_title": "Na snimku prenosa, od mesta gde je govor počeo",
    "checked": "provereno pre",
    "s": "s",
    "how_title": "Kako ovo radi",
    "how": "Ime čitamo automatski iz potpisa ispod govornika u prenosu Skupštine, s jednim kadrom na oko pet "
           "sekundi, isto za svakog govornika. Ime poredimo sa spiskom poslanika ovog sajta; ime kog na spisku "
           "nema prikazujemo samo kad je jasno pročitano. Govor traje dok se u potpisu vidi isto ime, a završava "
           "se kad se pojavi drugo ime ili kad se 25 sekundi ne vidi nijedno. Prenos kasni za salom 15 do 25 "
           "sekundi, a automatsko čitanje može da pogreši. Mesto na snimku je mesto gde se ime prvi put pojavilo, "
           "oko pet sekundi ranije. Spisak poslednjeg dana sednice ostaje dok sledeće zasedanje ne počne.",
    "live": "Prenos uživo na sajtu Skupštine",
    "home": "Svi zakoni i glasanja poslanika",
    "script": "Ћирилица",
}


def _t(key: str, cyr: bool) -> str:
    return cyrillic(TEXT[key]) if cyr else TEXT[key]


def _name(s: str, cyr: bool) -> str:
    return cyrillic(s) if cyr else s


def _clock(ts: int, tz: ZoneInfo) -> str:
    return datetime.fromtimestamp(ts, tz).strftime("%H:%M")


def _minutes(sec: int) -> str:
    return str(max(1, round(sec / 60)))


MONTHS = ("januar", "februar", "mart", "april", "maj", "jun", "jul", "avgust", "septembar", "oktobar", "novembar",
          "decembar")


def _date(day: str) -> str:
    y, m, d = (int(x) for x in day.split("-"))
    return f"{d}. {MONTHS[m - 1]} {y}."


def _hms(sec: int) -> str:
    h, m, s = sec // 3600, sec % 3600 // 60, sec % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _recording(d: dict, cyr: bool) -> str:
    """A link to the turn's place in the YouTube recording, where the record knows it."""
    if not d.get("video") or d.get("snimak") is None:
        return ""
    href = escape(f'https://www.youtube.com/watch?v={d["video"]}&t={d["snimak"]}s')
    return (f' <a class="rec" href="{href}" title="{escape(_t("recording_title", cyr))}">▶ '
            f'{escape(_t("recording", cyr))} {_hms(d["snimak"])}</a>')


def fragment(snap: dict, *, cyr: bool, site: str, tz: ZoneInfo) -> str:
    """The part of the page that changes: who speaks now, and today's turns."""
    t = lambda k: escape(_t(k, cyr))
    out = [f'<div id="deo" data-checked="{snap["provereno"]}">']
    cur = snap.get("sada")
    if snap["stanje"] == "govori" and cur:
        name = escape(_name(given_first(cur["ime"]), cyr))
        if cur["adresa"]:
            href = escape(f'{site}{"cir/" if cyr else ""}poslanik/{cur["adresa"]}')
            name = f'<a href="{href}">{name}</a>'
        side = cur["uloga"] or cur["grupa"]
        out.append(f'<p class="now"><span class="dot" aria-hidden="true"></span><span class="who">{name}</span></p>')
        if side:
            out.append(f'<p class="side">{escape(_name(side, cyr))}</p>')
        if not cur["adresa"]:
            out.append(f'<p class="meta">({t("not_listed")})</p>')
        out.append(f'<p class="meta">{t("since")} {_clock(cur["od"], tz)}, {_minutes(cur["sekundi"])} {t("min")}</p>')
    else:
        out.append(f'<p class="state">{t("unknown" if snap["stanje"] == "nepoznato" else "none")}</p>')
    if snap["provereno"]:
        out.append(f'<p class="meta" id="checked">{t("checked")} <span>0</span> {t("s")}</p>')
    if snap.get("ranije") and snap["danas"]:
        when = _date(snap["dan"])
        out.append(f'<h2>{t("last_day")}, {escape(cyrillic(when) if cyr else when)}</h2>')
    else:
        out.append(f'<h2>{t("today")}</h2>')
    if snap["danas"]:
        out.append('<ol class="turns">')
        for d in snap["danas"]:
            nm = escape(_name(given_first(d["ime"]), cyr))
            if d["adresa"]:
                nm = f'<a href="{escape(site + ("cir/" if cyr else "") + "poslanik/" + d["adresa"])}">{nm}</a>'
            side = d["uloga"] or d["grupa"]
            side = f' <span class="meta">{escape(_name(side, cyr))}</span>' if side else ""
            out.append(f'<li><span class="time">{_clock(d["od"], tz)}–{_clock(d["do"], tz)}</span> {nm}{side}'
                       f' <span class="meta">· {_minutes(d["sekundi"])} {t("min")}</span>{_recording(d, cyr)}</li>')
        out.append("</ol>")
    else:
        out.append(f'<p class="meta">{t("today_none")}</p>')
    out.append("</div>")
    return "\n".join(out)


CSS = """
@font-face { font-family: "Literata"; font-style: normal; font-display: swap; font-weight: 200 900;
  src: url(/fonts/literata-latin-ext-wght-normal.woff2) format("woff2");
  unicode-range: U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C4,U+2113,U+2C60-2C7F,U+A720-A7FF; }
@font-face { font-family: "Literata"; font-style: normal; font-display: swap; font-weight: 200 900;
  src: url(/fonts/literata-cyrillic-wght-normal.woff2) format("woff2"); unicode-range: U+0301,U+0400-045F,U+0490-0491,U+04B0-04B1,U+2116; }
@font-face { font-family: "Literata"; font-style: normal; font-display: swap; font-weight: 200 900;
  src: url(/fonts/literata-latin-wght-normal.woff2) format("woff2");
  unicode-range: U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD; }
:root { --bg: #fff; --fg: #111; --muted: #555; --line: #d9d9d9; --za: #1f5fa8; --protiv: #c2410c;
  --serif: "Literata", Georgia, "Times New Roman", serif; }
@media (prefers-color-scheme: dark) { :root { --bg: #111318; --fg: #f1f1ee; --muted: #a8adb8; --line: #30343c; --za: #7cc0f5; --protiv: #ff9a52; } }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--fg); font: 16px/1.55 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
a { color: var(--fg); text-underline-offset: 2px; } a:hover { color: var(--za); }
.top { display: flex; flex-wrap: wrap; gap: 0 2rem; align-items: baseline; justify-content: space-between; max-width: 760px; margin: 0 auto; padding: 1rem 20px .6rem; border-bottom: 3px solid var(--fg); }
.brand { font-family: var(--serif); font-weight: 700; font-size: 1.5rem; text-decoration: none; letter-spacing: -.01em; }
.brand .w-za { color: var(--za); } .brand .w-protiv { color: var(--protiv); }
main { max-width: 760px; margin: 0 auto; padding: 0 20px 3rem; }
h1, h2 { font-family: var(--serif); font-weight: 700; letter-spacing: -.015em; }
h1 { font-size: clamp(1.7rem, 4.5vw, 2.4rem); line-height: 1.12; margin: 1.4rem 0 .4rem; }
h2 { font-size: 1.35rem; margin: 2.4rem 0 .6rem; }
.lead, .meta { color: var(--muted); } .meta { font-size: .9rem; margin: .2rem 0; }
.now { display: flex; gap: .8rem; align-items: baseline; margin: 2rem 0 .3rem; }
.dot { flex: none; width: .8rem; height: .8rem; border-radius: 50%; background: var(--protiv); }
.who { font-family: var(--serif); font-weight: 700; font-size: clamp(2rem, 7vw, 3.4rem); line-height: 1.05; }
.who a { text-decoration: none; }
.side { font-size: 1.15rem; margin: .2rem 0 .3rem 1.6rem; }
.now ~ .meta { margin-left: 1.6rem; }
.state { font-family: var(--serif); font-size: 1.5rem; margin: 2rem 0 .4rem; }
.turns { list-style: none; padding: 0; margin: 0; }
.turns li { padding: .5rem 0; border-bottom: 1px solid var(--line); }
.rec { font-size: .9rem; color: var(--muted); white-space: nowrap; margin-left: .3rem; font-variant-numeric: tabular-nums; }
.time { font-variant-numeric: tabular-nums; color: var(--muted); margin-right: .4rem; }
footer { max-width: 760px; margin: 0 auto; padding: 1.2rem 20px 3rem; border-top: 1px solid var(--line); color: var(--muted); font-size: .9rem; }
"""

SCRIPT = """
(function () {
  var base = document.body.getAttribute("data-base");
  function tick() {
    var d = document.getElementById("deo"), c = document.querySelector("#checked span");
    if (d && c) c.textContent = Math.max(0, Math.round(Date.now() / 1000 - (+d.getAttribute("data-checked"))));
  }
  function load() {
    fetch(base + "deo", { cache: "no-store" }).then(function (r) { return r.ok ? r.text() : null; })
      .then(function (html) { if (html) { document.getElementById("deo").outerHTML = html; tick(); } })
      .catch(function () {});
  }
  setInterval(load, 2000); setInterval(tick, 1000); tick();
})();
"""


def page(snap: dict, *, cyr: bool, site: str, tz: ZoneInfo, url: str = "") -> str:
    t = lambda k: escape(_t(k, cyr))
    lang = "sr-Cyrl" if cyr else "sr-Latn"
    base = "/cir/" if cyr else "/"
    other = "/" if cyr else "/cir/"
    other_label = "Latinica" if cyr else TEXT["script"]
    home = site + ("cir/" if cyr else "")
    alt = (f'<link rel="canonical" href="{escape(url + base[1:])}">'
           f'<link rel="alternate" hreflang="sr-Latn" href="{escape(url)}">'
           f'<link rel="alternate" hreflang="sr-Cyrl" href="{escape(url + "cir/")}">') if url else ""
    brand = ('<span class="w-za">За</span> или <span class="w-protiv">Против</span>' if cyr
             else '<span class="w-za">Za</span> ili <span class="w-protiv">Protiv</span>')
    return f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{t("title")} · {"За или Против" if cyr else "Za ili Protiv"}</title>
<meta name="description" content="{t("lead")}">
{alt}
<link rel="icon" type="image/svg+xml" href="{escape(site)}favicon.svg">
<style>{CSS}</style>
</head>
<body data-base="{base}">
<header class="top"><a class="brand" href="{escape(home)}">{brand}</a><a href="{other}" hreflang="{"sr-Latn" if cyr else "sr-Cyrl"}">{other_label}</a></header>
<main>
<h1>{t("title")}</h1>
<p class="lead">{t("lead")}</p>
{fragment(snap, cyr=cyr, site=site, tz=tz)}
<h2>{t("how_title")}</h2>
<p>{t("how")}</p>
<p><a href="{LIVE}">{t("live")}</a> · <a href="{escape(home)}">{t("home")}</a></p>
</main>
<footer>{"За или Против" if cyr else "Za ili Protiv"}: zailiprotiv.rs</footer>
<script>{SCRIPT}</script>
</body>
</html>
"""
