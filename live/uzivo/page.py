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
    "from_recording": "Pročitano posle sednice sa celog snimka prenosa, istim pravilom za svakog govornika: govor "
                      "traje od prvog do poslednjeg kadra s imenom. Predsedavajući nema potpis i nije u spisku.",
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
    "play_live": "Pusti prenos uživo",
    "play_day": "Pusti snimak dana",
    "part": "Deo",
    "yt_note": "Klik učitava plejer sa YouTube-a (Google). Dok ne kliknete, sa YouTube-a se ništa ne učitava.",
    "archive_note": "Snimak iz arhive Skupštine (videonet.co.rs), pušta se tek na klik. Klik na „▶ snimak“ kod "
                    "govora pušta ga od tog mesta.",
    "wait_title": "Dok čekate",
    "quiz_lead": "Pitanja iz brojki sajta Za ili Protiv. Pogodite, pa proverite.",
    "answer": "Odgovor",
    "yes": "Tačno!",
    "no": "Nije.",
    "how_counted": "Kako je izračunato",
    "score": "Pogođeno",
    "of": "od",
    "q_all": "Sve tačno! Skupštinu pratite pažljivije od većine.",
    "q_some": "Brojke iznenade i one koji prate sednice. Svaka je na sajtu, s pravilom kako je izračunata.",
    "q_none": "Ništa? Zato i postoji ovaj sajt: sve brojke su tamo, s pravilom kako su izračunate.",
    "know": "Da li ste znali",
    "facts_note": "Brojevi su iz dokumenata Skupštine, izračunati istim pravilom kao na stranicama na koje vode.",
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
        if snap.get("snimak"):
            out.append(f'<p class="meta">{t("from_recording")}</p>')
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
.player { margin: 1.4rem 0 .4rem; }
.screen { position: relative; aspect-ratio: 16 / 9; background: #000; border-radius: 6px; overflow: hidden; display: grid; place-items: center; }
.screen iframe, .screen video { position: absolute; inset: 0; width: 100%; height: 100%; border: 0; background: #000; }
.play { font: inherit; font-weight: 700; font-size: 1.1rem; padding: .8rem 1.4rem; border: 0; border-radius: 999px; background: #fff; color: #111; cursor: pointer; }
.play:hover { transform: scale(1.04); }
.parts { display: flex; flex-wrap: wrap; gap: .4rem; margin: .5rem 0 .2rem; padding: 0; list-style: none; }
.part { font: inherit; font-size: .85rem; font-variant-numeric: tabular-nums; padding: .3rem .8rem; border: 1px solid var(--line); border-radius: 999px; background: transparent; color: inherit; cursor: pointer; }
.part.on { border-color: currentColor; font-weight: 700; }
h3 { font-family: var(--serif); font-size: 1.1rem; margin: 1.8rem 0 .4rem; }
.mq { list-style: none; counter-reset: mq; padding: 0; margin: 1rem 0; }
.mq-q { counter-increment: mq; border-top: 1px solid var(--line); padding: .9rem 0 .6rem; }
.mq-ask { font-family: var(--serif); font-size: 1.15rem; font-weight: 700; line-height: 1.3; margin: 0 0 .6rem; }
.mq-ask::before { content: counter(mq) ". "; color: var(--muted); }
.mq-opts { display: flex; flex-wrap: wrap; gap: .5rem; margin: 0 0 .5rem; }
.mq-o { font: inherit; font-weight: 600; font-variant-numeric: tabular-nums; min-width: 5.5rem; padding: .55rem 1rem;
  border: 2px solid var(--fg); border-radius: 999px; background: transparent; color: var(--fg); cursor: pointer;
  transition: transform .12s ease; }
.mq-o:hover { transform: translateY(-2px); }
.mq-q.done .mq-o { cursor: default; transform: none; opacity: .55; }
.mq-q.done .mq-o.right { opacity: 1; background: var(--fg); color: var(--bg); }
.mq-q.done .mq-o.right::before { content: "✓ "; }
.mq-q.done .mq-o.wrong { opacity: 1; border-style: dashed; text-decoration: line-through; }
.mq-why summary { cursor: pointer; color: var(--muted); font-size: .9rem; }
.mq-why p { margin: .4rem 0 0; }
.mq-yes, .mq-no { display: none; } .mq-q.ok .mq-yes, .mq-q.miss .mq-no { display: inline; }
.mq-score { font-family: var(--serif); font-size: 1.3rem; margin: .4rem 0 1.4rem; }
.mq-score span { display: block; font-size: 1rem; margin-top: .2rem; }
.mq-score span[hidden] { display: none; }
.facts { padding-left: 1.1rem; } .facts li { margin: .35rem 0; }
@media (prefers-reduced-motion: reduce) { .mq-o { transition: none; } .mq-o:hover { transform: none; } }
footer { max-width: 760px; margin: 0 auto; padding: 1.2rem 20px 3rem; border-top: 1px solid var(--line); color: var(--muted); font-size: .9rem; }
"""

SCRIPT = """
(function () {
  // The player (AGENTS.md, principle 5): nothing from YouTube or the archive loads until a click asks for it.
  var screen = document.getElementById("screen");
  if (!screen) return;
  var ARCHIVE = /^https:\\/\\/arhiva\\.videonet\\.co\\.rs\\//, ID = /^[\\w-]{6,20}$/;
  function put(el) { screen.textContent = ""; screen.appendChild(el); }
  function yt(id, t) {
    var f = document.createElement("iframe");
    f.src = "https://www.youtube-nocookie.com/embed/" + id + "?autoplay=1" + (t > 0 ? "&start=" + t : "");
    f.allow = "autoplay; encrypted-media; picture-in-picture; fullscreen";
    f.allowFullscreen = true;
    f.title = "YouTube";
    put(f);
  }
  function file(url, t) {
    var v = screen.querySelector("video");
    if (!v || v.getAttribute("src") !== url) {
      v = document.createElement("video");
      v.controls = true; v.playsInline = true; v.preload = "metadata";
      v.setAttribute("src", url);
      v.addEventListener("ended", function () {  // a day in several files: on to the next one
        var parts = document.querySelectorAll(".part[data-file]");
        for (var i = 0; i < parts.length - 1; i++) if (parts[i].getAttribute("data-file") === url) { file(parts[i + 1].getAttribute("data-file"), 0); break; }
      });
      put(v);
    }
    var parts = document.querySelectorAll(".part[data-file]");
    for (var j = 0; j < parts.length; j++) parts[j].classList.toggle("on", parts[j].getAttribute("data-file") === url);
    var go = function () { v.currentTime = t || 0; var p = v.play(); if (p && p.catch) p.catch(function () {}); };
    if (v.readyState >= 1) go(); else v.addEventListener("loadedmetadata", go, { once: true });
  }
  document.addEventListener("click", function (e) {
    var a = e.target.closest ? e.target.closest("[data-file], [data-yt]") : null;
    if (!a) return;
    var url = a.getAttribute("data-file"), id = a.getAttribute("data-yt"), t = +a.getAttribute("data-t") || 0;
    if (url ? !ARCHIVE.test(url) : !ID.test(id || "")) return;
    e.preventDefault();
    if (url) file(url, t); else yt(id, t);
    if (!screen.contains(a)) screen.scrollIntoView({ behavior: "smooth", block: "center" });
  });
})();

(function () {
  var base = document.body.getAttribute("data-base");
  function tick() {
    var d = document.getElementById("deo"), c = document.querySelector("#checked span");
    if (d && c) c.textContent = Math.max(0, Math.round(Date.now() / 1000 - (+d.getAttribute("data-checked"))));
  }
  // Every five seconds, as the caption is read once a segment (five seconds); not while the tab is out of sight,
  // and once at once when it comes back. Each ask is a request through Cloudflare and to the computer it runs on.
  function load() {
    if (document.hidden) return;
    fetch(base + "deo", { cache: "no-store" }).then(function (r) { return r.ok ? r.text() : null; })
      .then(function (html) { if (html) { document.getElementById("deo").outerHTML = html; tick(); } })
      .catch(function () {});
  }
  setInterval(load, 5000); setInterval(tick, 1000); tick();
  document.addEventListener("visibilitychange", function () { if (!document.hidden) load(); });
  var list = document.getElementById("mq"), score = document.getElementById("mq-score");
  if (!list || !score) return;
  var got = 0, done = 0, n = list.querySelectorAll(".mq-q").length;
  list.addEventListener("click", function (e) {
    var b = e.target.closest ? e.target.closest(".mq-o") : null;
    if (!b) return;
    var q = b.closest(".mq-q");
    if (q.classList.contains("done")) return;
    var a = +q.getAttribute("data-a"), i = +b.getAttribute("data-i");
    q.querySelectorAll(".mq-o")[a].classList.add("right");
    if (i !== a) b.classList.add("wrong"); else got++;
    q.classList.add("done", i === a ? "ok" : "miss");
    q.querySelector("details").open = true;
    done++;
    score.hidden = false;
    score.querySelector("b").textContent = got;
    if (done === n) score.querySelector('[data-k="' + (got === n ? "all" : got ? "some" : "none") + '"]').hidden = false;
  });
})();
"""


def player(snap: dict, *, cyr: bool, live: str = "", tz: ZoneInfo | None = None) -> str:
    """The player: while the broadcast is on, the YouTube video of it; between sittings, the last day's recording in
    the broadcaster's archive, from its first turn. Only a button until clicked (AGENTS.md, principle 5)."""
    t = lambda k: escape(_t(k, cyr))
    if snap["stanje"] != "nema_prenosa" and live:
        button, note = f'<button type="button" class="play" data-yt="{escape(live)}">▶ {t("play_live")}</button>', t("yt_note")
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
    """"Dok čekate": the site's short quiz and facts (pages_mikrofon), shown between sittings. The quiz works by the
    page's one script; without it each answer is under "Odgovor"."""
    w = w or {}
    quiz, facts = w.get("kviz") or [], w.get("cinjenice") or []
    if not quiz and not facts:
        return ""
    t = lambda k: escape(_t(k, cyr))
    s = lambda text: escape(cyrillic(text) if cyr else text)
    home = site + ("cir/" if cyr else "")
    out = [f'<h2>{t("wait_title")}</h2>']
    if quiz:
        out.append(f'<p>{t("quiz_lead")}</p><ol class="mq" id="mq">')
        for q in quiz:
            opts = "".join(f'<button type="button" class="mq-o" data-i="{i}">{s(o)}</button>'
                           for i, o in enumerate(q["options"]))
            out.append(f'<li class="mq-q" data-a="{int(q["answer"])}"><p class="mq-ask">{s(q["q"])}</p>'
                       f'<p class="mq-opts">{opts}</p><details class="mq-why"><summary>{t("answer")}</summary>'
                       f'<p><b class="mq-yes">{t("yes")} </b><b class="mq-no">{t("no")} </b>{s(q["why"])} '
                       f'<a href="{escape(home + q["href"])}">{t("how_counted")}</a></p></details></li>')
        out.append("</ol>")
        out.append(f'<p class="mq-score" id="mq-score" hidden>{t("score")} <b>0</b> {t("of")} {len(quiz)}.'
                   + "".join(f'<span data-k="{k}" hidden>{t("q_" + k)}</span>' for k in ("all", "some", "none")) + "</p>")
    if facts:
        out.append(f'<h3>{t("know")}</h3><ul class="facts">')
        out += [f'<li><a href="{escape(home + f["href"])}">{s(f["text"])}</a></li>' for f in facts]
        out.append(f'</ul><p class="meta">{t("facts_note")}</p>')
    return "\n".join(out)


def page(snap: dict, *, cyr: bool, site: str, tz: ZoneInfo, url: str = "", waiting: dict | None = None,
         live: str = "") -> str:
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
{player(snap, cyr=cyr, live=live, tz=tz)}
{fragment(snap, cyr=cyr, site=site, tz=tz)}
{waiting_part(waiting, cyr=cyr, site=site) if snap["stanje"] == "nema_prenosa" else ""}
<h2>{t("how_title")}</h2>
<p>{t("how")}</p>
<p><a href="{LIVE}">{t("live")}</a> · <a href="{escape(home)}">{t("home")}</a></p>
</main>
<footer>{"За или Против" if cyr else "Za ili Protiv"}: zailiprotiv.rs</footer>
<script>{SCRIPT}</script>
</body>
</html>
"""
