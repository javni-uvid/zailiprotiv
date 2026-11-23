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

from .mere import MP, Measure, Roll
from .names import cyrillic, given_first

SITE = "https://zailiprotiv.rs/"
LIVE = "https://mikrofon.zailiprotiv.rs/"
METHOD = "kako-racunamo#sazetak-dana"
SUPPORT = "podrzi"  # the page "Podrži"; one line in every mail (23 Nov 2026, the maintainer: a call, never a lock)
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
          spoke: dict[str, int] | None = None, cyr: bool = False, unsubscribe: str = "", other_script: str = "") -> Mail:
    """`summary` is the day's "dan"; `measures` from `mere.measures`; `roll` the convocation's MPs, whose names and
    lists are shown instead of the model's; `spoke` the seconds each MP (by the list's name) was heard;
    `unsubscribe` the subscriber's own address to leave by; `other_script` the page to receive the other script from."""
    t = cyrillic if cyr else (lambda s: s)
    e = lambda s: html.escape(t(s))  # noqa: E731
    measures, spoke = measures or [], spoke or {}
    weekday, when = DAYS[day.weekday()], f"{day.day}. {MONTHS[day.month - 1]}"
    decisions = summary.get("odluke") or []
    speakers = summary.get("govornici") or []
    flow = summary.get("tok") or []
    n = len(decisions)
    subject = t(f"Skupština, {weekday} {when}: " + (f"{n} {plural(n, 'odluka', 'odluke', 'odluka')}" if n else "sažetak dana"))
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
    stats = [(str(n), plural(n, "odluka", "odluke", "odluka")),
             (str(len(measures)), plural(len(measures), "mera predsedavajućeg", "mere predsedavajućeg", "mera predsedavajućeg")),
             (str(len(speakers)), plural(len(speakers), "govornik", "govornika", "govornika"))]

    # The plain text, in the same order as the HTML.
    lines = [t(f"ZA ILI PROTIV · Skupština, {weekday} {day.day}. {MONTHS_OF[day.month - 1]} {day.year}."), "",
             t(summary.get("kratko", "")), "", "   ".join(t(f"{a} {b}") for a, b in stats), ""]
    if decisions:
        lines += [t("ODLUKE")] + [t(f"  {d.get('vreme', '')}  {d.get('sta', '')}") + (f"\n         {t(d['glasovi'])}" if d.get("glasovi") else "")
                                 for d in decisions] + [""]
    if measures:
        lines += [t("OPOMENE I MERE")] + [t(f"  {m.vreme}  {m.mera[:1].upper() + m.mera[1:]}: "
                                           + (", ".join(given_first(p.name) for p in m.kome) or "ime nije izgovoreno"))
                                         for m in measures]
        lines.append("")
    if speakers:
        lines.append(t("KO JE ŠTA REKAO"))
        for mp, said in people:
            m = _minutes(spoke.get(mp.name, 0))
            lines.append(t(f"  {given_first(mp.name)} ({mp.label}){', ' + m if m else ''}"))
            if said:
                lines.append(t(f"    {said}"))
        lines.append("")
    lines += [t("Ceo dan, ko je govorio i snimci:") + " " + day_page, t("Mikrofon uživo:") + " " + live, "",
              t("Za ili Protiv je besplatan i bez reklama. Podrži ga:") + " " + support, "", "-- ",
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
        """A vote's figures line as the code wrote it, "za" in blue and "protiv" in orange, as everywhere on the site."""
        out = html.escape(t(text_))
        out = re.sub(r"(\b(?:za|за) \d+)", rf'<b style="color:{ZA}">\1</b>', out)
        return re.sub(r"(\b(?:protiv|против) \d+)", rf'<b style="color:{PROTIV}">\1</b>', out)

    parts = []
    if decisions:
        parts.append(head("Odluke"))
        parts.append("<tr><td>" + timeline([(d.get("vreme", ""), "odluka", e(d.get("sta", ""))
                                             + (f'<div style="font-size:13px;color:{MUTED};margin-top:3px">{votes(d["glasovi"])}</div>' if d.get("glasovi") else ""))
                                            for d in decisions]) + "</td></tr>")
    def name_of(p: MP) -> str:
        return f'<span style="color:{LISTS.get(p.label, OTHER_LIST)};font-weight:600">{e(given_first(p.name))}</span>'

    if measures:
        items = [(m.vreme, "mera", f'<b style="font-weight:600">{e(m.mera[:1].upper() + m.mera[1:])}</b>'
                  + (f'<div style="font-size:14px">{", ".join(name_of(p) for p in m.kome)}</div>' if m.kome
                     else f'<div style="color:{MUTED};font-size:14px">{e("ime nije izgovoreno")}</div>'))
                 for m in measures]
        parts.append(head("Opomene i mere", f"· {len(measures)}"))
        parts.append("<tr><td>" + timeline(items) + "</td></tr>")
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

    stat_cells = "".join(
        f'<td valign="top" style="padding:12px 10px;{"border-left:1px solid " + LINE + ";" if i else ""}">'
        f'<div style="font-family:{SERIF};font-size:24px;font-weight:bold;color:{INK};line-height:1.1">{e(a)}</div>'
        f'<div style="{font}font-size:12px;color:{MUTED};margin-top:3px">{e(b)}</div></td>' for i, (a, b) in enumerate(stats))
    button = (lambda href, label, solid: f'<a href="{html.escape(href)}" style="display:inline-block;{font}font-size:15px;'
              f'font-weight:bold;text-decoration:none;padding:11px 18px;border-radius:999px;margin:0 8px 8px 0;'
              + (f"background:{INK};color:{PAPER};border:1px solid {INK}" if solid else f"color:{INK};border:1px solid {INK}")
              + f'">{e(label)}</a>')
    foot = [f'<a href="{html.escape(method)}" style="color:{MUTED}">{e("Kako nastaje ovaj sažetak")}</a>']
    if unsubscribe:
        foot.append(f'<a href="{html.escape(unsubscribe)}" style="color:{MUTED}">{e("Odjavi se")}</a>')
    if other_script:
        foot.append(f'<a href="{html.escape(other_script)}" style="color:{MUTED}">{"Latinica" if cyr else "Ћирилица"}</a>')
    brand = (f'<span style="color:{ZA}">{e("Za")}</span> {e("ili")} <span style="color:{PROTIV}">{e("Protiv")}</span>')
    body = f"""<!doctype html>
<html lang="{'sr-Cyrl' if cyr else 'sr-Latn'}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light only"><meta name="supported-color-schemes" content="light"><title>{html.escape(subject)}</title></head>
<body style="margin:0;padding:0;background:{BACK}">
<div style="display:none;max-height:0;overflow:hidden;mso-hide:all">{e(summary.get("kratko", ""))}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{BACK}"><tr><td align="center" style="padding:20px 12px 28px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px">
<tr><td style="padding:0 4px 12px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
<td style="font-family:{SERIF};font-size:19px;font-weight:bold">{brand}</td>
<td align="right" style="{font}font-size:13px;color:{MUTED}">{e("Sažetak dana")}</td></tr></table></td></tr>
<tr><td style="background:{PAPER};border-radius:14px;padding:26px 24px 22px;border-top:4px solid {INK}">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">
<tr><td style="{font}font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:{MUTED};font-weight:bold;padding:0 0 6px">{e(f"Skupština · {weekday}" + (f" · {hours}" if hours else ""))}</td></tr>
<tr><td style="font-family:{SERIF};font-size:30px;line-height:1.1;font-weight:bold;color:{INK};padding:0 0 14px">{e(f"{day.day}. {MONTHS[day.month - 1]}")}</td></tr>
<tr><td style="font-family:{SERIF};font-size:18px;line-height:1.5;color:{INK};padding:0 0 18px">{e(summary.get("kratko", ""))}</td></tr>
<tr><td style="padding:0"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{SOFT};border-radius:10px"><tr>{stat_cells}</tr></table></td></tr>
{"".join(parts)}
<tr><td style="padding:10px 0 0">{button(day_page, "Ceo dan na sajtu", True)}{button(live, "Mikrofon uživo", False)}</td></tr>
<tr><td style="{font}font-size:14px;line-height:1.5;color:{INK};border-top:1px solid {LINE};padding:14px 0 0;margin-top:8px">{e("Za ili Protiv je besplatan i bez reklama.")} <a href="{html.escape(support)}" style="color:{INK};font-weight:bold">{e("Podrži ga →")}</a></td></tr>
</table></td></tr>
<tr><td style="{font}font-size:12px;line-height:1.6;color:{MUTED};padding:16px 8px 0;text-align:center">
{" &nbsp;·&nbsp; ".join(foot)}<br>{e("Dobijaš ovaj mejl jer si se prijavio na mikrofon.zailiprotiv.rs.")}<br>{e("Za ili Protiv")} · {CONTACT}</td></tr>
</table></td></tr></table></body></html>
"""
    return Mail(subject, text, body)
