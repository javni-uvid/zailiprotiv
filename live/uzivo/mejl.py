"""The day's summary as an e-mail: the subject, the plain text and the HTML, in Latin or Cyrillic.

Made from the day's summary as `sudija` keeps it (`/data/sazetak/<day>.json`, its "dan"), the chair's measures among
the day's lines (`/data/hronika/<day>.json`) and the speakers' time measured from the broadcast. Short pieces, no
paragraph: the day by the clock on a dark card (the summary's steps, the chair's measures and to whom, the decisions
with their votes), then who spoke, by lists, with what each spoke about. The subject, the counts, the votes' figures
and the measures are the code's words, never the model's; how the summary is made is on the method page, linked at
the foot. The HTML is for mail readers: tables and inline styles, no font, no script, no tracking of any kind; the one
thing loaded is the MPs' portraits from the site, at the same address for every reader (25 Nov 2026).
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

from . import config
from .mere import MP, Measure, Roll
from .names import cyrillic, given_first

SITE = "https://zailiprotiv.rs/"
LIVE = "https://mikrofon.zailiprotiv.rs/"
METHOD = "kako-racunamo#sazetak-dana"
SUPPORT = "podrzi"  # the page "Podrži"; a card in the middle of every mail (23 Nov 2026, the maintainer: a call, never a lock)
SUPPORT_TITLE = "Za ili Protiv pravi jedan čovek, uz nadzor mačka Časlava."
SUPPORT_LINE = "Sajt i ovaj mejl su besplatni i bez reklama. Ako ti koriste, podrži ih."
FROM = "sazetak@zailiprotiv.rs"
CONTACT = "kontakt@zailiprotiv.rs"
BELGRADE = ZoneInfo("Europe/Belgrade")
DAYS = ["ponedeljak", "utorak", "sreda", "četvrtak", "petak", "subota", "nedelja"]
MONTHS = ["januar", "februar", "mart", "april", "maj", "jun", "jul", "avgust", "septembar", "oktobar", "novembar",
          "decembar"]
MONTHS_OF = ["januara", "februara", "marta", "aprila", "maja", "juna", "jula", "avgusta", "septembra", "oktobra",
             "novembra", "decembra"]

# The live page's colours (live.css, light): ink, the muted grey, lines, "za" blue, the stop red of a measure.
# A list's colour, as on the live page (page.LIST_COLOURS): the two big lists their own, every other list teal.
LISTS = {"Aleksandar Vučić - Srbija pobeđuje": "#3730a3", "Studentska lista": "#e11d48"}
OTHER_LIST = "#0f9d8a"
OUTSIDE = "#4b5563"  # the band of MPs in no group
INK, MUTED, LINE, SOFT, ZA, PROTIV, STOP, PAPER, BACK = ("#111111", "#5b616b", "#e3e5e8", "#f6f7f9", "#1f5fa8",
                                                        "#c2410c", "#dc2626", "#ffffff", "#eef0f3")
# The dark top's and the support card's own, as the live page's card that offers the mail; "za" legible on it.
DARK, WARM, PALE, ZA_DARK = "#111318", "#ff9a52", "#c9ced6", "#7cc0f5"
AMBER, DIM = "#f5c26b", "#8d939c"  # on the dark card: a measure's mark, the hour of a plain step
# Above the sentences the maintainer adds by hand (25 Nov 2026): whose choice they are and from where.
QUOTES_NOTE = "Rečenice je iz snimka izabrao i proverio urednik. Stenografske beleške još nisu objavljene."
TITLE_MAX = 100  # a day's title longer than this is no title (the model is asked for 60)
SERIF = "Georgia, 'Times New Roman', serif"
SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"


@dataclass(frozen=True)
class Mail:
    subject: str
    text: str
    html: str


def plural(n: int, one: str, few: str, many: str) -> str:
    return one if n % 10 == 1 and n % 100 != 11 else few if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14) else many


def mixed_words(text: str) -> list[str]:
    """Words written in both scripts at once ("iznео" with a Cyrillic е): a model's slip, never a real word."""
    return [w for w in re.findall(r"\w+", text) if re.search(r"[A-Za-zČĆŽŠĐčćžšđ]", w) and re.search(r"[Ѐ-ӿ]", w)]


def _minutes(seconds: int) -> str:
    m = round(seconds / 60)
    if m < 60:
        return f"{m} min" if m else ""
    return f"{m // 60} h" + (f" {m % 60} min" if m % 60 else "")


def _clock(hhmm: str) -> int:
    h, _, m = str(hhmm).partition(":")
    return int(h) * 60 + int(m) if h.isdigit() and m.isdigit() else -1


def _votes(text_: str) -> dict[str, int]:
    """A vote's figures as the code wrote them ("za 136, protiv 0, ..., prisutno 234")."""
    return {k: int(x) for k, x in re.findall(r"(za|protiv|uzdržano|nevažeći|nije glasalo|glasalo|prisutno) (\d+)", text_ or "")}


def short_steps(flow: list[dict]) -> list[dict]:
    """The summary's steps as the mail's line has room for them (25 Nov 2026, the maintainer: shorter). A break and the
    work going on after it are one step, in the code's words with the hour the next step gives ("Pauza do 11:23"); of
    a step in two parts ("…; …") the first is kept. The same for every day; nothing is added to what a step says."""
    steps = [f for f in flow if f.get("sta") and _clock(f.get("vreme", "")) >= 0]
    out, k = [], 0
    while k < len(steps):
        f, after = steps[k], steps[k + 1] if k + 1 < len(steps) else None
        if re.search(r"\bpauz", f["sta"], re.I) and after and re.match(r"\W*(nastav|konstatovan kvorum|rad je nastavljen)", after["sta"], re.I):
            out.append({"vreme": f["vreme"], "sta": f"Pauza do {after['vreme']}"})
            k += 2
            continue
        out.append({"vreme": f["vreme"], "sta": f["sta"].split(";")[0].strip()})
        k += 1
    return out


def by_lists(people: list, roll: Roll, label=lambda x: x[0]) -> list[tuple[str, str, list]]:
    """People in bands, one per parliamentary group and one for everybody outside the groups: (the band's name, its
    colour, its people in the order given). The groups by their seats in the list, most first, then by the alphabet;
    outside the groups last. The same rule for every list (principle 1)."""
    seats: dict[str, int] = {}
    for mp in roll.mps:
        if mp.group:
            seats[mp.group] = seats.get(mp.group, 0) + 1
    bands: dict[str, list] = {}
    for x in people:
        bands.setdefault(label(x).group, []).append(x)
    order = sorted((g for g in bands if g), key=lambda g: (-seats.get(g, 0), g))
    out = [(g, LISTS.get(g, OTHER_LIST), bands[g]) for g in order]
    if bands.get(""):
        out.append(("Van poslaničkih grupa", OUTSIDE, bands[""]))
    return out


def build(day: date, summary: dict, measures: list[Measure] | None = None, roll: Roll | None = None,
          spoke: dict[str, int] | None = None, cyr: bool = False, unsubscribe: str = "", other_script: str = "",
          quotes: list[dict] | None = None) -> Mail:
    """`summary` is the day's "dan"; `measures` from `mere.measures`; `roll` the convocation's MPs, whose names,
    lists and portraits are shown instead of the model's; `spoke` the seconds each MP (by the list's name) was heard;
    `unsubscribe` the subscriber's own address to leave by; `other_script` the page to receive the other script from;
    `quotes` the sentences the maintainer chose and checked by hand ({"vreme", "ime", "o_cemu", "tekst", "snimak"})."""
    t = cyrillic if cyr else (lambda s: s)
    e = lambda s: html.escape(t(s))  # noqa: E731
    measures, spoke = measures or [], spoke or {}
    weekday, when = DAYS[day.weekday()], f"{day.day}. {MONTHS[day.month - 1]}"
    decisions = summary.get("odluke") or []
    speakers = summary.get("govornici") or []
    flow = summary.get("tok") or []
    warning = next((m.vreme for m in measures if "opomena" in m.mera), "")
    told = [x for x, on in (("šta je odlučeno", decisions), ("ko je dobio opomenu", warning), ("ko je šta rekao", speakers)) if on]
    subject = t(f"Skupština, {weekday} {when}: " + (" i ".join(told[:2]) or "sažetak dana"))
    brief = str(summary.get("kratko") or "")
    title = str(summary.get("naslov") or "").strip().rstrip(".")
    title = title if len(title) <= TITLE_MAX else ""
    prefix = "cir/" if cyr else ""
    day_page, live, method = f"{SITE}{prefix}govornici/{day.isoformat()}", f"{LIVE}{prefix}", f"{SITE}{prefix}{METHOD}"
    support = f"{SITE}{prefix}{SUPPORT}"
    roll = roll or Roll([])

    def who(name: str, lista: str = "") -> MP:
        """The speaker as the list writes the name, with the list's own group; the model's name and list only when
        the list has nobody of that name."""
        return roll.one(name) or MP(name, group=lista)
    people = [(who(s.get("ime", ""), s.get("lista", "")), s.get("o_cemu", "")) for s in speakers]
    people.sort(key=lambda x: -spoke.get(x[0].name, 0))  # the longest first; the day's order among the rest
    given = {}  # an MP's first measure of the day, for the mark beside the name
    for m in measures:
        for mp in m.kome:
            given.setdefault(mp.name, m)
    said = [(who(str(q.get("ime", ""))), q) for q in quotes or [] if q.get("tekst") and q.get("ime")]

    # The day by the clock: the summary's steps, the chair's measures (the code's, with the list's names) and the
    # decisions. A step that tells of a measure, or stands at a decision's minute, would say it twice.
    decided = {d.get("vreme", "") for d in decisions}
    events = [(d.get("vreme", ""), 0, "odluka", d) for d in decisions]
    events += [(m.vreme, 1, "mera", m) for m in measures]
    events += [(f.get("vreme", ""), 2, "", f) for f in short_steps(flow)
               if f.get("vreme", "") not in decided and not re.search(r"opomen|oduz\w+ reč", f["sta"], re.I)]
    clocks = [_clock(x[0]) for x in events if _clock(x[0]) >= 0]
    start = next((_clock(f.get("vreme", "")) for f in flow if _clock(f.get("vreme", "")) >= 0), min(clocks, default=0))  # the summary's first step
    events.sort(key=lambda x: ((_clock(x[0]) - start) % 1440, x[1]))  # a day that ends after midnight stays in order

    def measure_words(m: Measure) -> tuple[str, str]:
        return (m.mera[:1].upper() + m.mera[1:], ", ".join(given_first(p.name) for p in m.kome))

    # The plain text, in the same order as the HTML.
    lines = [t(f"ZA ILI PROTIV · Skupština, {weekday} {day.day}. {MONTHS_OF[day.month - 1]} {day.year}."), "",
             *([t(title), ""] if title else []), t(brief), ""]
    if events:
        lines.append(t("DAN PO SATU"))
        for when_, _, kind, x in events:
            if kind == "odluka":
                lines.append(t(f"  {when_}  ODLUKA: {x.get('sta', '')}") + (f"\n         {t(x['glasovi'])}" if x.get("glasovi") else ""))
            elif kind == "mera":
                what, to = measure_words(x)
                lines.append(t(f"  {when_}  {what}: {to or 'ime nije izgovoreno'}"))
            else:
                lines.append(t(f"  {when_}  {x['sta']}"))
        lines.append("")
    if said:
        lines += [t("REČENO U SALI"), t(f"  {QUOTES_NOTE}")]
        for mp, q in said:
            lines += [t(f"  {given_first(mp.name)} ({mp.label}), {q.get('vreme', '')}: „{q['tekst']}“")]
        lines.append("")
    lines += [t("PODRŽI ZA ILI PROTIV"), t(f"  {SUPPORT_TITLE}"), t(f"  {SUPPORT_LINE}"), "  " + support, ""]
    if people:
        lines.append(t("GOVORILI SU"))
        for band, _, rows in by_lists(people, roll):
            lines.append(t(f"  {band}"))
            for mp, about in rows:
                m = _minutes(spoke.get(mp.name, 0))
                mark = f", {given[mp.name].mera} u {given[mp.name].vreme}" if mp.name in given else ""
                lines.append(t(f"    {given_first(mp.name)}{'' if mp.group else ' (' + mp.label + ')'}{', ' + m if m else ''}{mark}"))
                if about:
                    lines.append(t(f"      {about}"))
        lines.append("")
    lines += [t("Ceo dan, ko je govorio i snimci:") + " " + day_page, t("Mikrofon uživo:") + " " + live, "", "-- ",
              t("Kako nastaje ovaj sažetak:") + " " + method,
              t("Dobijaš ga jer si se prijavio na mikrofon.zailiprotiv.rs.")]
    if unsubscribe:
        lines.append(t("Odjava:") + " " + unsubscribe)
    lines.append(t("Za ili Protiv") + f", {CONTACT}")
    text = "\n".join(lines) + "\n"

    # The HTML: one column of 600 px at most, cards on a grey ground.
    font = f"font-family:{SANS};"

    def table(rows: str, extra: str = "") -> str:
        return f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"{" " + extra if extra else ""}>{rows}</table>'

    def face(mp: MP, px: int, colour: str) -> str:
        """The MP's portrait from the site, the same address for every reader, cut round from its top; the initials
        in the list's colour when the list has no portrait, and under the picture until it is loaded."""
        ring = f"width:{px}px;height:{px}px;border-radius:50%;overflow:hidden;background:{colour};"
        if mp.photo and mp.photo.replace(".", "").replace("-", "").isalnum():
            return (f'<div style="{ring}"><img src="{SITE}foto/{html.escape(mp.photo)}" width="{px}" alt="" '
                    f'style="display:block;width:{px}px;height:auto;border:0"></div>')
        letters = "".join(w[:1] for w in given_first(mp.name).split()[:2])
        return (f'<div style="{ring}{font}font-size:{px * 3 // 8}px;line-height:{px}px;font-weight:bold;color:{PAPER};'
                f'text-align:center">{e(letters)}</div>')

    def heading(words: str, under: str = "") -> str:
        note = f'<div style="{font}font-size:14px;line-height:1.5;color:{MUTED};padding-top:6px">{e(under)}</div>' if under else ""
        return (f'<tr><td style="padding:34px 4px 0"><div style="font-family:{SERIF};font-size:27px;line-height:1.15;font-weight:bold;'
                f'color:{INK}">{e(words)}</div>{note}</td></tr>')

    def band(name: str, colour: str, count: str, rows: str) -> str:
        return ('<tr><td style="padding:14px 0 0">'
                + table(f'<tr><td bgcolor="{colour}" style="background:{colour};border-radius:14px 14px 0 0;padding:11px 20px;{font}'
                        f'font-size:15px;font-weight:bold;color:{PAPER}">{e(name)}<span style="font-weight:normal"> · {e(count)}</span></td></tr>'
                        f'<tr><td bgcolor="{PAPER}" style="background:{PAPER};border-radius:0 0 14px 14px;padding:0 20px 6px">{table(rows)}</td></tr>')
                + "</td></tr>")

    def vote(text_: str) -> str:
        """A vote under its decision: "za" and "protiv" in large figures, blue and orange as everywhere on the site, a
        bar of the hall, and the other figures that are not nought under it."""
        v = _votes(text_)
        parts_ = [("za", ZA_DARK), ("protiv", WARM), ("uzdržano", "#8d939c"), ("nevažeći", "#8d939c"), ("nije glasalo", "#5b616b")]
        whole = sum(v.get(k, 0) for k, _ in parts_)
        if not whole or "za" not in v:
            return f'<br><span style="font-size:14px;font-weight:normal;color:{PALE}">{e(text_)}</span>'
        big = lambda k, c: f'<span style="font-family:{SERIF};font-size:44px;line-height:1;font-weight:bold;color:{c}">{v.get(k, 0)}</span>'  # noqa: E731
        cells = "".join(f'<td width="{max(1, round(100 * v[k] / whole))}%" bgcolor="{c}" style="background:{c};height:8px;line-height:0;font-size:0">&nbsp;</td>'
                        for k, c in parts_ if v.get(k))
        rest = ", ".join(f"{e(k)} {v[k]}" for k in ("prisutno", "uzdržano", "nevažeći", "nije glasalo") if v.get(k))
        return (table(f'<tr><td valign="bottom" style="{font}font-size:14px;font-weight:normal;color:{PALE}">{big("za", ZA_DARK)} {e("za")}</td>'
                      f'<td valign="bottom" align="right" style="{font}font-size:14px;font-weight:normal;color:{PALE}">{e("protiv")} {big("protiv", WARM)}</td></tr>',
                      'style="margin-top:8px"')
                + table(f"<tr>{cells}</tr>", 'style="margin:8px 0 6px;border-radius:4px;overflow:hidden"')
                + (f'<span style="font-size:13px;font-weight:normal;color:{PALE}">{rest}</span>' if rest else ""))

    def event(when_: str, kind: str, x, last: bool) -> str:
        """One step of the day: a decision white and bold (larger with a vote), a measure amber, the rest grey."""
        small = f'<br><span style="font-size:14px;font-weight:normal;color:{PALE}">'
        if kind == "odluka":
            words, dot, size = f'<b>{e(str(x.get("sta", "")).rstrip("."))}</b>' + (vote(x["glasovi"]) if x.get("glasovi") else ""), PAPER, 14 if x.get("glasovi") else 10
        elif kind == "mera":
            what, to = measure_words(x)
            words = f'<b>{e(what)}{": " + e(to) if to else ""}</b>' + ("" if to else f'{small}{e("ime nije izgovoreno")}</span>')
            dot, size = AMBER, 10
        else:
            words, dot, size = e(str(x["sta"]).rstrip(".")), "#5b616b", 10
        pad = 0 if last else 18
        return (f'<tr><td valign="top" align="right" style="width:46px;{font}font-size:14px;line-height:22px;font-weight:bold;'
                f'color:{PAPER if kind else DIM};padding:0 12px {pad}px 0">{html.escape(when_)}</td>'
                f'<td valign="top" style="border-left:2px solid #34383f;padding:0 0 {pad}px 18px;{font}font-size:{16 if kind else 15}px;'
                f'line-height:22px;color:{PAPER if kind else PALE}">'
                f'<div style="float:left;width:{size}px;height:{size}px;border-radius:50%;background:{dot};'
                f'margin:{(22 - size) // 2}px 0 0 -{19 + size // 2}px;line-height:0;font-size:0">&nbsp;</div>{words}</td></tr>')

    # The top: dark, the day in one line and then by the clock.
    line = "".join(event(when_, kind, x, i == len(events) - 1) for i, (when_, _, kind, x) in enumerate(events))
    headline = (f'<div style="font-family:{SERIF};font-size:30px;line-height:1.14;font-weight:bold;color:{PAPER};padding:10px 0 24px">{e(title)}</div>'
                if title else f'<div style="font-family:{SERIF};font-size:20px;line-height:1.4;color:{PAPER};padding:10px 0 24px">{e(brief)}</div>')
    top = (f'<tr><td bgcolor="{DARK}" style="background:{DARK};border-radius:18px;padding:24px 20px">'
           f'<div style="{font}font-size:12px;font-weight:bold;letter-spacing:1.5px;color:{PALE}">{e("DAN U SKUPŠTINI, PO SATU")}</div>'
           f'{headline}{table(line) if line else ""}</td></tr>')

    parts = []
    if said:  # the maintainer's own choice, checked by hand; never the service's
        parts.append(heading("Rečeno u sali", QUOTES_NOTE))
        for name, colour, rows in by_lists(said, roll):
            out = ""
            for k, (mp, q) in enumerate(rows):
                under = (f'<span style="color:{colour};font-weight:600">{e(mp.label)}</span> · ' if not mp.group else "") + e(str(q.get("o_cemu", "")))
                play = str(q.get("snimak", ""))
                out += (f'<tr><td style="padding:20px 0;{"" if k == 0 else f"border-top:1px solid {LINE};"}">'
                        + table(f'<tr><td width="56" valign="middle" style="width:56px">{face(mp, 56, colour)}</td><td valign="middle" style="padding-left:12px;{font}'
                                f'font-size:14px;line-height:1.4;color:{MUTED}"><b style="font-size:17px;color:{INK}">{e(given_first(mp.name))}</b><br>{under}</td></tr>')
                        + f'<div style="font-family:{SERIF};font-size:21px;line-height:1.38;color:{INK};padding:14px 0 {16 if play else 0}px">'
                        f'<span style="color:{colour};font-weight:bold">„</span>{e(str(q["tekst"]))}<span style="color:{colour};font-weight:bold">“</span></div>'
                        + (f'<a href="{html.escape(play)}" style="display:inline-block;{font}font-size:14px;font-weight:bold;color:{colour};text-decoration:none;'
                           f'background:{SOFT};border-radius:999px;padding:13px 18px">&#9654;&#65038; {e("Pusti od")} {html.escape(str(q.get("vreme", "")))}</a>'
                           if play.startswith("https://") else "") + "</td></tr>")
            n = len(rows)
            parts.append(band(name, colour, f"{n} {plural(n, 'rečenica', 'rečenice', 'rečenica')}", out))

    # The call for support, where the mail turns from what happened to who spoke (23 Nov 2026, the maintainer: "izrazi
    # podrži i stavi ga na sredinu"): a dark card, the one thing in the mail that asks something of the reader. The
    # amounts lead to their codes on the page; nothing that says who pressed.
    pill = (f"display:inline-block;{font}font-size:15px;font-weight:bold;text-decoration:none;white-space:nowrap;"
            "border-radius:999px;padding:14px 17px;margin:0 6px 6px 0;")
    amounts = "".join(f'<a href="{html.escape(support)}#din-{a}" style="{pill}background:{PAPER};color:{INK}">{a} {e("din")}</a>'
                      for a in config.SUPPORT_AMOUNTS)
    other = e("ili koliko želiš") if amounts else e("Podrži sajt")
    parts.append(f'<tr><td style="padding:30px 0 0">' + table(
        f'<tr><td bgcolor="{DARK}" style="background:{DARK};border-radius:14px;padding:20px 20px 12px">'
        f'<div style="{font}font-size:12px;letter-spacing:1.5px;font-weight:bold;color:{WARM}">'
        f'<span style="font-size:15px">&#9829;&#65038;</span> {e("PODRŽI ZA ILI PROTIV")}</div>'
        f'<div style="font-family:{SERIF};font-size:19px;line-height:1.3;font-weight:bold;color:{PAPER};padding:8px 0 5px">{e(SUPPORT_TITLE)}</div>'
        f'<div style="{font}font-size:15px;line-height:1.5;color:{PALE};padding:0 0 14px">{e(SUPPORT_LINE)}</div>'
        f'{amounts}<a href="{html.escape(support)}" style="display:inline-block;{font}font-size:14px;font-weight:bold;color:{PAPER};'
        f'padding:14px 4px;white-space:nowrap">{other} →</a></td></tr>') + "</td></tr>")

    if people:
        parts.append(heading("Govorili su", f"{len(people)} {plural(len(people), 'poslanik', 'poslanika', 'poslanika')}, po listama, najduže prvo. "
                             "Opise je napisao model iz automatskog prepisa i može da pogreši."))
        for name, colour, rows in by_lists(people, roll):
            out = ""
            for k, (mp, about) in enumerate(rows):
                mark = (f' <span style="display:inline-block;font-size:11px;font-weight:bold;color:#8a4b00;background:#fdecc8;border-radius:999px;'
                        f'padding:1px 8px;vertical-align:2px;white-space:nowrap">{e(given[mp.name].mera)} {e("u")} {html.escape(given[mp.name].vreme)}</span>'
                        if mp.name in given else "")
                side = (f'<span style="color:{colour};font-weight:600">{e(mp.label)}</span>' if not mp.group and mp.label != "van poslaničkih grupa" else "")
                minutes = _minutes(spoke.get(mp.name, 0))
                side += (" · " if side and minutes else "") + e(minutes)
                out += (f'<tr><td width="44" valign="top" style="width:44px;padding:16px 0 15px;{"" if k == 0 else f"border-top:1px solid {LINE};"}">{face(mp, 44, colour)}</td>'
                        f'<td valign="top" style="padding:14px 0 15px 12px;{"" if k == 0 else f"border-top:1px solid {LINE};"}{font}font-size:15px;line-height:1.5;color:#3a3f47">'
                        + (f'<div style="float:right;font-size:13px;line-height:1.7;color:{MUTED};white-space:nowrap;padding-left:8px">{side}</div>' if side else "")
                        + f'<b style="font-size:16px;line-height:1.35;color:{INK}">{e(given_first(mp.name))}</b>{mark}'
                        + (f'<div style="padding-top:3px">{e(about)}</div>' if about else "") + "</td></tr>")
            n = len(rows)
            parts.append(band(name, colour, f"{n} {plural(n, 'poslanik', 'poslanika', 'poslanika')}", out))

    button = (lambda href, label, solid: f'<tr><td style="padding:{22 if solid else 10}px 0 0"><a href="{html.escape(href)}" style="display:block;{font}'
              f'font-size:16px;font-weight:bold;text-align:center;text-decoration:none;border-radius:14px;padding:17px 18px;'
              + (f"background:{DARK};color:{PAPER};border:1px solid {DARK}" if solid else f"color:{INK};border:1px solid {INK}")
              + f'">{e(label)}</a></td></tr>')
    foot = [f'<a href="{html.escape(method)}" style="color:{MUTED}">{e("Kako nastaje ovaj sažetak")}</a>']
    if unsubscribe:
        foot.append(f'<a href="{html.escape(unsubscribe)}" style="color:{MUTED}">{e("Odjavi se")}</a>')
    if other_script:
        foot.append(f'<a href="{html.escape(other_script)}" style="color:{MUTED}">{"Latinica" if cyr else "Ћирилица"}</a>')
    brand = (f'<span style="color:{ZA}">{e("Za")}</span><span style="color:{INK}"> {e("ili")} </span><span style="color:{PROTIV}">{e("Protiv")}</span>')
    portraits = e("Portreti: Narodna skupština, učitavaju se sa zailiprotiv.rs.") + "<br>" if "<img" in "".join(parts) else ""
    inside = top + "".join(parts)
    read = max(1, round(len(re.sub(r"<[^>]+>", " ", inside).split()) / 200))
    body = f"""<!doctype html>
<html lang="{'sr-Cyrl' if cyr else 'sr-Latn'}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light only"><meta name="supported-color-schemes" content="light"><title>{html.escape(subject)}</title></head>
<body style="margin:0;padding:0;background:{BACK}">
<div style="display:none;max-height:0;overflow:hidden;mso-hide:all">{e(brief)}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" bgcolor="{BACK}" style="background:{BACK}"><tr><td align="center" style="padding:14px 12px 28px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px">
<tr><td style="padding:4px 4px 14px">{table(f'<tr><td style="font-family:{SERIF};font-size:22px;font-weight:bold">{brand}</td>'
                                             f'<td align="right" style="{font}font-size:13px;line-height:1.4;color:{MUTED}">{e(weekday)}, {e(when)}<br>{e("čitanje")} {read} min</td></tr>')}</td></tr>
{inside}
{button(day_page, "Ceo dan na sajtu", True)}{button(live, "Mikrofon uživo", False)}
<tr><td style="{font}font-size:12px;line-height:1.8;color:{MUTED};padding:18px 8px 0;text-align:center">
{" &nbsp;·&nbsp; ".join(foot)}<br>{portraits}{e("Dobijaš ovaj mejl jer si se prijavio na mikrofon.zailiprotiv.rs.")}<br>{e("Za ili Protiv")} · {CONTACT}</td></tr>
</table></td></tr></table></body></html>
"""
    return Mail(subject, text, body)
