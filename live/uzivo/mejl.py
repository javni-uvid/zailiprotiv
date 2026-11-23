"""The day's summary as an e-mail: the subject, the plain text and the HTML, in Latin or Cyrillic.

Made from the day's summary as `sudija` keeps it (`/data/sazetak/<day>.json`, its "dan"), the chair's measures among
the day's lines (`/data/hronika/<day>.json`) and the speakers' time measured from the broadcast. Short pieces, no
paragraph: the decisions, the warnings and to whom, and what each speaker spoke about, on a line of time with the
live page's marks. The subject, the counts and the votes' figures are the code's words, never the model's; how the
summary is made is on the method page, linked at the foot. The HTML is for mail readers: tables and inline styles,
no picture, no font, nothing loaded from anywhere, no tracking of any kind.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

from . import brojevi, config
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
INK, MUTED, LINE, SOFT, ZA, PROTIV, STOP, PAPER, BACK = ("#111111", "#5b616b", "#e3e5e8", "#f6f7f9", "#1f5fa8",
                                                        "#c2410c", "#dc2626", "#ffffff", "#eef0f3")
# The dark top's and the support card's own, as the live page's card that offers the mail; "za" legible on it.
DARK, WARM, PALE, ZA_DARK = "#111318", "#ff9a52", "#c9ced6", "#7cc0f5"
TITLE_MAX = 100  # a day's title longer than this is no title (the model is asked for 80)
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


def build(day: date, summary: dict, measures: list[Measure] | None = None, roll: Roll | None = None,
          spoke: dict[str, int] | None = None, cyr: bool = False, unsubscribe: str = "", other_script: str = "",
          numbers: dict | None = None) -> Mail:
    """`summary` is the day's "dan"; `measures` from `mere.measures`; `roll` the convocation's MPs, whose names and
    lists are shown instead of the model's; `spoke` the seconds each MP (by the list's name) was heard;
    `unsubscribe` the subscriber's own address to leave by; `other_script` the page to receive the other script from; `numbers` the day's figures (`brojevi`)."""
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

    def who(s: dict) -> MP:
        """The speaker as the list writes the name, with the list's own group; the model's name and list only when
        the list has nobody of that name."""
        return roll.one(s.get("ime", "")) or MP(s.get("ime", ""), group=s.get("lista", ""))
    people = [(who(s), s.get("o_cemu", "")) for s in speakers]
    warned = {mp.name for m in measures for mp in m.kome}
    longest = sorted((spoke.get(mp.name, 0) for mp, _ in people), reverse=True)
    top = longest[0] if longest else 0
    hours = f"{flow[0]['vreme']}–{flow[-1]['vreme']}" if len(flow) > 1 and flow[0].get("vreme") else ""
    tiles = brojevi.tiles(numbers or {}, day, warning)

    # The plain text, in the same order as the HTML.
    lines = [t(f"ZA ILI PROTIV · Skupština, {weekday} {day.day}. {MONTHS_OF[day.month - 1]} {day.year}."), "",
             *([t(title), ""] if title else []), t(brief), ""]
    if decisions:
        lines += [t("ODLUKE")] + [t(f"  {d.get('vreme', '')}  {d.get('sta', '')}") + (f"\n         {t(d['glasovi'])}" if d.get("glasovi") else "")
                                 for d in decisions] + [""]
    if tiles:
        lines += [t("DAN U BROJEVIMA")] + [t(f"  {a} {b}") for a, b in tiles] + [""]
    if measures:
        lines += [t("OPOMENE I MERE")] + [t(f"  {m.vreme}  {m.mera[:1].upper() + m.mera[1:]}: "
                                           + (", ".join(given_first(p.name) for p in m.kome) or "ime nije izgovoreno"))
                                         for m in measures]
        lines.append("")
    ask = [t("PODRŽI ZA ILI PROTIV"), t(f"  {SUPPORT_TITLE}"), t(f"  {SUPPORT_LINE}"), "  " + support, ""]
    if decisions or measures:  # in the middle of the mail, before what was said
        lines += ask
    if speakers:
        lines.append(t("KO JE ŠTA REKAO"))
        for mp, said in people:
            m = _minutes(spoke.get(mp.name, 0))
            lines.append(t(f"  {given_first(mp.name)} ({mp.label}){', ' + m if m else ''}"))
            if said:
                lines.append(t(f"    {said}"))
        lines.append("")
    if not (decisions or measures):
        lines += ask
    lines += [t("Ceo dan, ko je govorio i snimci:") + " " + day_page, t("Mikrofon uživo:") + " " + live, "", "-- ",
              t("Kako nastaje ovaj sažetak:") + " " + method,
              t("Dobijaš ga jer si se prijavio na mikrofon.zailiprotiv.rs.")]
    if unsubscribe:
        lines.append(t("Odjava:") + " " + unsubscribe)
    lines.append(t("Za ili Protiv") + f", {CONTACT}")
    text = "\n".join(lines) + "\n"

    # The HTML: one column of 560 px at most; every part is a line of time like the live page's.
    font = f"font-family:{SANS};"

    def dot(kind: str, colour: str = "") -> str:
        """The live page's mark of a step: a filled circle a decision, a red square a measure, a small grey circle a
        speaker."""
        if kind == "odluka":
            style = f"width:10px;height:10px;border-radius:50%;background:{INK};border:2px solid {INK}"
        elif kind == "mera":
            style = f"width:10px;height:10px;border-radius:2px;background:{STOP};border:2px solid {STOP}"
        else:
            style = f"width:10px;height:10px;border-radius:50%;background:{colour or PAPER};border:2px solid {colour or MUTED}"
        return f'<div style="{style};margin:5px auto 0;line-height:0;font-size:0">&nbsp;</div>'

    def row(time: str, kind: str, body: str, last: bool, colour: str = "") -> str:
        rail = "" if last else f"background:linear-gradient({LINE},{LINE}) no-repeat center 18px/2px 100%;"
        return (f'<tr><td valign="top" align="right" style="{font}font-size:13px;color:{MUTED};padding:2px 8px 16px 0;'
                f'white-space:nowrap;width:40px">{html.escape(time)}</td>'
                f'<td valign="top" style="width:18px;padding:0;{rail}">{dot(kind, colour)}</td>'
                f'<td valign="top" style="{font}font-size:15px;line-height:1.45;color:{INK};padding:0 0 16px 10px">{body}</td></tr>')

    def timeline(items: list[tuple]) -> str:
        return ('<table role="presentation" cellpadding="0" cellspacing="0" width="100%">'
                + "".join(row(*it[:3], i == len(items) - 1, *it[3:]) for i, it in enumerate(items)) + "</table>")

    def head(title: str, count: str = "") -> str:
        return (f'<tr><td style="padding:26px 0 12px"><span style="font-family:{SERIF};font-size:19px;font-weight:bold;color:{INK}">'
                f'{e(title)}</span>' + (f' <span style="{font}font-size:13px;color:{MUTED}">{e(count)}</span>' if count else "")
                + "</td></tr>")

    def votes(text_: str) -> str:
        """A vote's figures as the code wrote them ("za 136, protiv 0, ..., prisutno 234"): a bar of the hall, "za" blue
        and "protiv" orange as everywhere on the site, and the figures that are not nought under it."""
        v = {k: int(x) for k, x in re.findall(r"(za|protiv|uzdržano|nevažeći|nije glasalo|glasalo|prisutno) (\d+)", text_)}
        kinds = [("za", ZA), ("protiv", PROTIV), ("uzdržano", "#8a919c"), ("nevažeći", "#8a919c"), ("nije glasalo", "#c9ced6")]
        there = [(k, v[k], c) for k, c in kinds if v.get(k)]
        whole = sum(x for _, x, _ in there)
        if not whole:
            return html.escape(t(text_))
        cells = "".join(f'<td width="{max(1, round(100 * x / whole))}%" bgcolor="{c}" style="background:{c};height:8px;line-height:0;font-size:0">&nbsp;</td>'
                        for _, x, c in there)
        said = " · ".join(f'<b style="color:{c if k in ("za", "protiv") else INK}">{v[k]} {e(k)}</b>' if k in ("za", "protiv") else f"{v[k]} {e(k)}"
                          for k, c in kinds if v.get(k) or (k == "protiv" and k in v))
        return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:7px 0 5px;border-radius:4px;overflow:hidden"><tr>{cells}</tr></table>'
                + said)

    parts = []
    if decisions:
        parts.append(head("Odluke"))
        parts.append("<tr><td>" + timeline([(d.get("vreme", ""), "odluka", e(d.get("sta", ""))
                                             + (f'<div style="font-size:13px;color:{MUTED};margin-top:3px">{votes(d["glasovi"])}</div>' if d.get("glasovi") else ""))
                                            for d in decisions]) + "</td></tr>")
    if tiles:  # light figures of the day, the code's (brojevi.py), two in a row
        cell = lambda a, b, span_: (f'<td valign="top" width="50%"{" colspan=2" if span_ else ""} style="padding:12px 11px;border:1px solid {LINE};background:{SOFT}">'  # noqa: E731
                                    f'<div style="font-family:{SERIF};font-size:21px;font-weight:bold;color:{INK};line-height:1.15">{e(a)}</div>'
                                    f'<div style="{font}font-size:13px;line-height:1.4;color:{MUTED};margin-top:4px">{e(b)}</div></td>')
        rows_ = "".join("<tr>" + "".join(cell(*x, len(tiles[i:i + 2]) == 1) for x in tiles[i:i + 2]) + "</tr>" for i in range(0, len(tiles), 2))
        parts.append(head("Dan u brojevima"))
        parts.append(f'<tr><td><table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;table-layout:fixed">{rows_}</table></td></tr>')

    def name_of(p: MP) -> str:
        return f'<span style="color:{LISTS.get(p.label, OTHER_LIST)};font-weight:600">{e(given_first(p.name))}</span>'

    if measures:
        items = [(m.vreme, "mera", f'<b style="font-weight:600">{e(m.mera[:1].upper() + m.mera[1:])}</b>'
                  + (f'<div style="font-size:14px">{", ".join(name_of(p) for p in m.kome)}</div>' if m.kome
                     else f'<div style="color:{MUTED};font-size:14px">{e("ime nije izgovoreno")}</div>'))
                 for m in measures]
        parts.append(head("Opomene i mere", f"· {len(measures)}"))
        parts.append("<tr><td>" + timeline(items) + "</td></tr>")
    # The call for support, where the mail turns from what was decided to what was said (23 Nov 2026, the maintainer:
    # "izrazi podrži i stavi ga na sredinu"): a dark card, the one thing in the mail that asks something of the reader.
    # The amounts lead to their codes on the page; a heart as a letter, nothing loaded, nothing that says who pressed.
    pill = (f"display:inline-block;{font}font-size:15px;font-weight:bold;text-decoration:none;white-space:nowrap;"
            "border-radius:999px;padding:10px 12px;margin:0 5px 8px 0;")
    amounts = "".join(f'<a href="{html.escape(support)}#din-{a}" style="{pill}background:{PAPER};color:{INK};border:1px solid {PAPER}">'
                      f'{a} {e("din")}</a>' for a in config.SUPPORT_AMOUNTS)
    other = e("ili koliko želiš") if amounts else e("Podrži sajt")
    card = (f'<tr><td style="padding:22px 0 6px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'bgcolor="{DARK}" style="background:{DARK};border-radius:14px"><tr><td style="padding:22px 20px 16px">'
            f'<div style="{font}font-size:12px;letter-spacing:.08em;text-transform:uppercase;font-weight:bold;color:{WARM}">'
            f'<span style="font-size:17px;vertical-align:-1px">&#9829;&#65038;</span> {e("Podrži Za ili Protiv")}</div>'
            f'<div style="font-family:{SERIF};font-size:21px;line-height:1.25;font-weight:bold;color:{PAPER};padding:8px 0 6px">{e(SUPPORT_TITLE)}</div>'
            f'<div style="{font}font-size:15px;line-height:1.5;color:{PALE};padding:0 0 16px">{e(SUPPORT_LINE)}</div>'
            f'<div>{amounts}<a href="{html.escape(support)}" style="display:inline-block;{font}font-size:15px;font-weight:bold;'
            f'color:{PAPER};padding:10px 4px;margin:0 0 8px;white-space:nowrap">{other} →</a></div>'
            "</td></tr></table></td></tr>")
    if parts:
        parts.append(card)
    if speakers:
        parts.append(head("Ko je šta rekao", "· po redu kojim su govorili"))
        items = []
        pill = "display:inline-block;font-size:11px;font-weight:bold;border-radius:999px;padding:0 7px;vertical-align:1px;"
        for mp, said in people:
            colour = MUTED if mp.label == "van poslaničkih grupa" else LISTS.get(mp.label, OTHER_LIST)
            sec = spoke.get(mp.name, 0)
            tags = ""
            if mp.name in warned:
                tags += f' <span style="{pill}color:{STOP};border:1px solid {STOP}">{e("opomena")}</span>'
            if sec and longest.index(sec) < 3:
                tags += f' <span style="{pill}color:{PAPER};background:{INK};border:1px solid {INK}">{e("najduže" if sec == top else "među najdužim")}</span>'
            minutes = _minutes(sec)
            label = e(mp.label) + (f'<span style="color:{MUTED};font-weight:400"> · {e(minutes)}</span>' if minutes else "")
            bar = (f'<div style="height:4px;background:{SOFT};border-radius:2px;margin:5px 0 2px"><div style="height:4px;'
                   f'width:{max(3, round(100 * sec / top))}%;background:{colour};border-radius:2px;line-height:0;font-size:0">&nbsp;</div></div>'
                   if sec and top else "")
            body = (f'<b style="font-weight:650">{e(given_first(mp.name))}</b>{tags}'
                    f'<div style="font-size:13px;color:{colour};font-weight:600">{label}</div>{bar}'
                    + (f'<div style="font-size:14px;line-height:1.45;margin-top:3px">{e(said)}</div>' if said else ""))
            items.append(("", "rec", body, colour))
        parts.append("<tr><td>" + timeline(items).replace("width:40px", "width:0px;padding-right:0") + "</td></tr>")

    if card not in parts:  # a day without a decision or a measure: after what was said
        parts.append(card)

    # The top: dark, the day as a leaf of a calendar (as on the live page), and the day in one line; with decisions
    # under it their list is the summary, so the sentence that says them again stays for the preview and the text.
    lead = "" if title and decisions else brief if title else ""
    leaf = (f'<table role="presentation" cellpadding="0" cellspacing="0" width="64" bgcolor="{PAPER}" style="background:{PAPER};border-radius:10px"><tr>'
            f'<td align="center" style="padding:8px 4px 7px;{font}font-size:11px;font-weight:bold;letter-spacing:.06em;text-transform:uppercase;color:{STOP};line-height:1.1">{e(weekday[:3])}'
            f'<div style="font-family:{SERIF};font-size:28px;color:{INK};letter-spacing:0;line-height:1.1">{day.day}</div>'
            f'<span style="color:{INK}">{e(MONTHS[day.month - 1][:3])}</span></td></tr></table>')
    hero = (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td width="64" valign="middle">{leaf}</td>'
            f'<td valign="middle" style="padding:0 0 0 16px"><div style="font-family:{SERIF};font-size:20px;font-weight:bold;color:{PAPER};line-height:1.2">{e("Dan u Skupštini")}</div>'
            f'<div style="{font}font-size:14px;color:{PALE};padding-top:3px">{e(weekday)}{", " + hours if hours else ""}</div></td></tr></table>'
            + (f'<div style="font-family:{SERIF};font-size:26px;line-height:1.22;font-weight:bold;color:{PAPER};padding:20px 0 0">{e(title)}</div>' if title
               else f'<div style="font-family:{SERIF};font-size:19px;line-height:1.45;color:{PAPER};padding:18px 0 0">{e(brief)}</div>')
            + (f'<div style="{font}font-size:16px;line-height:1.5;color:{PALE};padding:10px 0 0">{e(lead)}</div>' if lead else ""))
    button = (lambda href, label, solid: f'<a href="{html.escape(href)}" style="display:inline-block;{font}font-size:15px;'
              f'font-weight:bold;text-decoration:none;padding:11px 18px;border-radius:999px;margin:0 8px 8px 0;'
              + (f"background:{INK};color:{PAPER};border:1px solid {INK}" if solid else f"color:{INK};border:1px solid {INK}")
              + f'">{e(label)}</a>')
    foot = [f'<a href="{html.escape(method)}" style="color:{MUTED}">{e("Kako nastaje ovaj sažetak")}</a>']
    if unsubscribe:
        foot.append(f'<a href="{html.escape(unsubscribe)}" style="color:{MUTED}">{e("Odjavi se")}</a>')
    if other_script:
        foot.append(f'<a href="{html.escape(other_script)}" style="color:{MUTED}">{"Latinica" if cyr else "Ћирилица"}</a>')
    brand = (f'<span style="color:{ZA_DARK}">{e("Za")}</span> {e("ili")} <span style="color:{WARM}">{e("Protiv")}</span>')
    body = f"""<!doctype html>
<html lang="{'sr-Cyrl' if cyr else 'sr-Latn'}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light only"><meta name="supported-color-schemes" content="light"><title>{html.escape(subject)}</title></head>
<body style="margin:0;padding:0;background:{BACK}">
<div style="display:none;max-height:0;overflow:hidden;mso-hide:all">{e(brief)}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{BACK}"><tr><td align="center" style="padding:20px 12px 28px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px">
<tr><td bgcolor="{DARK}" style="background:{DARK};border-radius:14px 14px 0 0;padding:18px 24px 24px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 20px"><tr>
<td style="font-family:{SERIF};font-size:18px;font-weight:bold;color:{PAPER}">{brand}</td>
<td align="right" style="{font}font-size:13px;color:{PALE}">{e("Sažetak dana")}</td></tr></table>
{hero}</td></tr>
<tr><td style="background:{PAPER};border-radius:0 0 14px 14px;padding:4px 24px 22px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">
{"".join(parts)}
<tr><td style="padding:10px 0 0">{button(day_page, "Ceo dan na sajtu", True)}{button(live, "Mikrofon uživo", False)}</td></tr>
</table></td></tr>
<tr><td style="{font}font-size:12px;line-height:1.6;color:{MUTED};padding:16px 8px 0;text-align:center">
{" &nbsp;·&nbsp; ".join(foot)}<br>{e("Dobijaš ovaj mejl jer si se prijavio na mikrofon.zailiprotiv.rs.")}<br>{e("Za ili Protiv")} · {CONTACT}</td></tr>
</table></td></tr></table></body></html>
"""
    return Mail(subject, text, body)
