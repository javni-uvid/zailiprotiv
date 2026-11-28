"""Following a sitting MP by mail (25 Nov 2026): the morning after a day on which the MP spoke in the hall. And an
area of laws (27 Nov 2026): the morning after a bill of the area entered procedure, came on a sitting's agenda or was
passed, by the site's events (`oblasti-dogadjaji.json`, the site's oblasti.py), in the same mail. And one bill or one
law (28 Nov 2026, the maintainer: "Može se nekom i samo na taj zakon prijaviti"; "Možemo sa tvojim preporukama"): a
bill's steps (on the agenda, passed, no longer listed, published in the Gazette) and then its law's; a law's, any bill
whose title names it and that bill's steps; from the same file, in the same mail.

The counter keeps who follows whom sealed (`worker/prati.js`); both are opened here, in memory, only to send, and never
written down or logged. What is kept (`/data/mejl/prati/stanje.json`) is by the counter's row id: the day up to which a
reader was told, and the day a mail last went. Nobody is counted by MP, here or anywhere.

Only a speech whose name was read from the broadcast's caption is told: a name by the voice or by the chair's words
alone is a guess (measured on 18, 24 and 25 Nov against the notes: the caption right for 60 of 61), so a mail may miss
a speech. The same rule for every MP. At most one mail a day to a reader: who has the day's summary too finds this in it
(`Mailer._to_all`), and waits for it until noon; the rest get a mail of its own from nine. For as long as PRATI_SAMO is
not set, only on the maintainer's click.

An area's events are numbered here as they are first seen (`/data/mejl/prati/dogadjaji.json`: public, the same for all,
nothing of any reader), and a reader is kept by the number up to which they were told, so nobody is told an event twice
and the file says nothing of what anybody follows. A day with nothing new sends no mail.

The mail's words are the code's, the same for all; a subject never has a name; nothing is loaded; the links are the same
for every reader."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import threading
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from html import escape
from pathlib import Path

from . import config, cuvar, mejl, mreza, pretplata
from .names import cyrillic
from .state_base import _write

log = logging.getLogger("uzivo.prati")
TZ = pretplata.TZ
FROM_HOUR, TO_HOUR = 9, 13  # the mail goes between these; what is not sent by then goes the next morning
KEEP_DAYS = 3  # a day older than this is told no more
EVERY = 300  # seconds between looks
AREA_MOST = 10  # rows of one kind in an area's card; the rest are on the area's page
KEEP_EVENTS = 60  # days an event's number is kept after it left the site's file
METHOD = "kako-racunamo#pracenje"
PRIVACY = "privatnost#pracenje"


@dataclass(frozen=True)
class Followed:
    slug: str   # the MP's address on the site when the reader asked, and the name then
    name: str
    since: date
    end: tuple[str, ...]  # the links that end it: more than one when the same MP was asked for twice
    kind: str = "p"  # "p" a sitting MP, "o" an area of laws, "b" a bill, "z" a law (its key and name on the site)


@dataclass(frozen=True)
class Follower:
    id: str
    to: str
    cir: bool
    summary: str  # the row of the day's summary of the same address, or ""
    all_end: str
    out: str
    follows: tuple[Followed, ...]


def opened(rows: list[dict]) -> list[Follower]:
    """The counter's list with what it has sealed opened; a row sealed for another key, or not as it must be, is left out."""
    out = []
    for r in rows:
        try:
            to = pretplata.unseal(config.MAIL_KEY, r["adresa"]).rstrip()
            found: dict[str, Followed] = {}
            for p in r.get("prati") or []:
                kind, slug, name = pretplata.unseal(config.MAIL_KEY, p["sta"]).rstrip().split("|", 2)
                if kind not in ("p", "o", "b", "z"):
                    continue  # a kind this service does not tell yet
                had = found.get(f"{kind}|{slug}")
                since = date.fromisoformat(p["od"])
                found[f"{kind}|{slug}"] = Followed(slug, name, min(since, had.since) if had else since,
                                                   (had.end if had else ()) + (p["kraj"],), kind)
            if found:
                out.append(Follower(r["id"], to, bool(r.get("cir")), r.get("mejl") or "", r["sve"], r["svega"], tuple(found.values())))
        except Exception:  # noqa: BLE001 — never sent, never shown
            continue
    return out


def ends(links: tuple[str, ...]) -> str:
    """The links that end one MP's following as one: the first's address, and the others' row and code after it."""
    first, *more = links
    return first + "".join("&" + x.split("?", 1)[1] for x in more if "?" in x)


def spoken(record: dict | None) -> dict[str, list[tuple[int, int]]]:
    """Each MP's speeches of a day by their address, (begun, ended): only those named by the caption, read in two frames
    or more; one speaker's turns in a row are one, as on the page."""
    out: dict[str, list[tuple[int, int]]] = {}
    last = None
    for t in sorted((record or {}).get("govori") or [], key=lambda t: t["od"]):
        sure = t.get("adresa") and t.get("okvira", 0) >= 2 and t.get("izvor") in (None, "", "potpis")
        if not sure:
            last = None if t.get("okvira", 0) >= 2 else last  # somebody else's turn stands between; a chance reading does not
            continue
        mine = out.setdefault(t["adresa"], [])
        if last == t["adresa"] and mine and t["od"] - mine[-1][1] <= config.MERGE_SECONDS:
            mine[-1] = (mine[-1][0], max(mine[-1][1], int(t["do"])))
        else:
            mine.append((int(t["od"]), int(t["do"])))
        last = t["adresa"]
    return out


def whose(f: Followed, facts: dict) -> str:
    """The address the followed MP has now: theirs, or, once no sitting MP has it, the one sitting MP of that name."""
    if f.slug in facts:
        return f.slug
    same = [s for s, x in facts.items() if isinstance(x, dict) and mejl.given_first(str(x.get("ime") or "")) == f.name]
    return same[0] if len(same) == 1 else f.slug


# What a reader is told: each followed MP who spoke, with the days and the speeches.
News = list[tuple[Followed, list[tuple[date, list[tuple[int, int]]]]]]


def news(reader: Follower, days: dict[date, dict], facts: dict, told: date | None) -> News:
    out = []
    for f in sorted((f for f in reader.follows if f.kind == "p"), key=lambda f: _order(f.name)):
        slug = whose(f, facts)
        rows = [(d, days[d][slug]) for d in sorted(days) if days[d].get(slug) and d >= f.since and (told is None or d > told)]
        if rows:
            out.append((f, rows))
    return out


_ABC = {c: i for i, c in enumerate("a b c č ć d đ e f g h i j k l m n o p q r s š t u v w x y z ž".split())}


def _order(name: str) -> list[int]:
    """By surname, in the Serbian Latin alphabet (lj, nj and dž by their letters)."""
    last = " ".join(name.split()[-1:] + name.split()[:-1]).lower()
    return [_ABC.get(c, -1) for c in last]


# An area's events a reader is told: each followed area with its events, each event once (under the first area by its
# point that the reader follows).
AreaNews = list[tuple[Followed, list[dict]]]
KINDS_ORDER = ("usvojen", "objavljen", "dnevni_red", "procedura", "nije_na_spisku")
# A bill's or a law's events: each followed bill or law with its events, each event once.
LawNews = list[tuple[Followed, list[dict]]]


@dataclass(frozen=True)
class Told:
    """What one mail tells a reader: the MPs' speeches, the areas' events and the bills' and laws', and the number of the
    newest event in it."""
    speeches: News
    areas: AreaNews
    seq: int = 0
    laws: LawNews = ()

    def __bool__(self) -> bool:
        return bool(self.speeches or self.areas or self.laws)

    def last(self, today: date) -> date:
        """The day the mail is of: the last day of a speech in it, else the day before the mail."""
        return max((d for _, rows in self.speeches for d, _ in rows), default=today - timedelta(days=1))


def _own(e: dict) -> str:
    """The day an event counts from: its own, or the day it was first listed or first seen here (a law in the Gazette,
    whose day is the day it passed), or a sitting to come."""
    return max(e.get("dan") or "", e.get("poznato") or "", e.get("prvi") or "" if e.get("vrsta") == "objavljen" else "")


def area_news(reader: Follower, events: list[dict], points: dict[str, int], told_seq: int, today: date,
              skip: frozenset = frozenset()) -> AreaNews:
    """The events of the areas the reader follows not told yet: numbered after `told_seq`, of the last KEEP_DAYS days (by
    the event's own day, or the day it was first listed, or a sitting to come), and not older than the following."""
    areas = sorted((f for f in reader.follows if f.kind == "o"), key=lambda f: (points.get(f.name, 99), f.name))
    by_point = {points.get(f.name): f for f in areas}
    out: dict[str, list[dict]] = {}
    order = lambda e: (KINDS_ORDER.index(e["vrsta"]) if e["vrsta"] in KINDS_ORDER else 9, e.get("naslov") or "")  # noqa: E731
    for e in sorted(events, key=order):
        mine = [by_point[a] for a in e.get("oblasti") or [] if a in by_point]
        if not mine or e.get("seq", 0) <= told_seq or e["id"] in skip:
            continue
        first = min(mine, key=lambda f: (points.get(f.name, 99), f.name))
        own = _own(e)
        if own < max(first.since, today - timedelta(days=KEEP_DAYS)).isoformat():
            continue
        out.setdefault(first.slug, []).append({**e, "i_u": [f.name for f in mine if f is not first]})
    return [(f, out[f.slug]) for f in areas if f.slug in out]


def law_news(reader: Follower, events: list[dict], bills: dict, told_seq: int, today: date) -> LawNews:
    """The events of the bills and laws the reader follows not told yet, by the same numbers and days as an area's: a
    bill's own, and once it passed (`bills`, the site's `predlozi`) those of its laws after that day; a law's, every bill
    that names it. Each event once, under the first bill or law (bills, then laws, by name)."""
    mine = sorted((f for f in reader.follows if f.kind in ("b", "z")), key=lambda f: (f.kind, f.name))
    out: dict[str, list[dict]] = {}
    seen: set[str] = set()
    order = lambda e: (KINDS_ORDER.index(e["vrsta"]) if e["vrsta"] in KINDS_ORDER else 9, e.get("naslov") or "")  # noqa: E731
    for f in mine:
        laws, since_law, head = {f.slug} if f.kind == "z" else set(), "", ""
        if f.kind == "b":
            b = bills.get(f.slug) or {}
            if b.get("usvojen"):
                laws, since_law = {z[0] for z in b.get("zakoni") or [] if z}, b["usvojen"]
                head = next((z[1] for z in b.get("zakoni") or [] if len(z) > 1), "")
        for e in sorted(events, key=order):
            if e["id"] in seen or e.get("seq", 0) <= told_seq:
                continue
            own_bill = f.kind == "b" and e.get("predlog") == f.slug
            if own_bill and e["vrsta"] == "procedura":
                continue  # its own listing: it was followed from its page, so listed by then
            of_law = bool(laws & set(e.get("zakoni") or [])) and (e.get("dan") or "") >= since_law and not own_bill
            if not (own_bill or of_law) or _own(e) < max(f.since, today - timedelta(days=KEEP_DAYS)).isoformat():
                continue
            seen.add(e["id"])
            out.setdefault(f"{f.kind}|{f.slug}", []).append({**e, "svoj": own_bill, "glava": head})
    return [(f, out[f"{f.kind}|{f.slug}"]) for f in mine if f"{f.kind}|{f.slug}" in out]


def _day(d: date) -> str:
    return f"{mejl.DAYS[d.weekday()]}, {d.day}. {mejl.MONTHS[d.month - 1]}"


def _rows(told: News, cyr: bool) -> tuple[str, list[str]]:
    """The speeches, as the HTML's rows and the plain text's lines."""
    t = cyrillic if cyr else (lambda s: s)
    e = lambda s: escape(t(s))  # noqa: E731
    font, pre = f"font-family:{mejl.SANS};", "cir/" if cyr else ""
    html, text = [], []
    many = len({d for _, rows in told for d, _ in rows}) > 1
    for f, rows in told:
        n = sum(len(x) for _, x in rows)
        page = f"{mejl.SITE}{pre}poslanik/{f.slug}"
        html.append(f'<div style="{font}font-size:16px;line-height:1.4;color:{mejl.INK};padding:18px 20px 4px"><b><a href="{escape(page)}" '
                    f'style="color:{mejl.INK};font-weight:bold">{e(f.name)}</a></b> <span style="color:{mejl.MUTED}">· {e("govori u sali")}, {n}</span></div>')
        text.append(t(f"{f.name} · govori u sali, {n}"))
        for d, speeches in rows:
            if many:
                html.append(f'<div style="{font}font-size:14px;line-height:1.4;color:{mejl.MUTED};padding:8px 20px 0">{e(_day(d))}</div>')
                text.append("  " + t(_day(d)))
            for od, do in speeches:
                at = datetime.fromtimestamp(od, TZ).strftime("%H.%M")
                long = mejl._minutes(do - od)
                about = f"{at} · {e('oko')} {e(long)} · " if long else f"{at} · "
                href = f"{mejl.LIVE}{pre}iz-mejla/govor/{od}"
                html.append(f'<div style="{font}font-size:15px;line-height:1.5;color:{mejl.INK};padding:9px 20px">{about}'
                            f'<a href="{escape(href)}" style="color:{mejl.ZA};font-weight:bold">{e("Pusti govor")}</a></div>')
                text.append(t(f"  {at}{f' · oko {long}' if long else ''} · ") + href)
    html.append(f'<div style="{font}font-size:14px;line-height:1.5;color:{mejl.MUTED};padding:12px 20px 0">{e(CAPTION)}</div>')
    text += ["", t(CAPTION)]
    return "".join(html), text


CAPTION = "Po natpisu na prenosu. Prepoznavanje može da pogreši; merodavne su stenografske beleške."
AREA_NOTE = ("Oblast je tačka člana 97. Ustava na koju se predlagač poziva. Zakoni bez oblasti, najčešće potvrđivanje "
             "međunarodnih ugovora, ovde se ne javljaju.")
AREA_SOURCE = "Iz spiska zakona u proceduri, dnevnog reda i poimeničnih glasanja koje objavljuje Narodna skupština."
_GROUP = {"usvojen": ("Usvojen", "Usvojeno {n}"), "dnevni_red": ("Na dnevnom redu", "Na dnevnom redu"),
          "procedura": ("Ušao u proceduru", "Ušlo u proceduru {n}"), "objavljen": ("Objavljen", "Objavljeno {n}"),
          "nije_na_spisku": ("Više nije na spisku", "Više nije na spisku")}
LAW_GROUP = {**_GROUP, "procedura": ("Predložena izmena", "Predložene izmene {n}")}  # in a law's card
LAW_NOTE = "Dalje pratiš zakon: javljamo kad bude predložena njegova izmena."  # once, when a followed bill passed
LAW_SOURCE = ("Iz spiska zakona u proceduri, dnevnog reda, poimeničnih glasanja i spiska donetih zakona koje objavljuje "
              "Narodna skupština.")


def _when(at: str) -> str:
    """A sitting's start, "2026-06-17T11:00" -> "sreda, 17. jun u 11" (with the minutes when they are not 0)."""
    try:
        t = datetime.fromisoformat(at)
    except ValueError:
        return _day(date.fromisoformat(at[:10])) if at[:10] else ""
    if len(at) <= 10:
        return _day(t.date())
    return f"{_day(t.date())} u {t.hour}" + (f".{t.minute:02d}" if t.minute else "")


def _event_lines(x: dict) -> list[str]:
    """An event's line under its name, in Latin, its parts in order (the Assembly's own words as they are)."""
    k = x["vrsta"]
    if k == "usvojen":
        out = [_day(date.fromisoformat(x["dan"]))]
        if "za" in x:
            out += [f"za {x['za']}", f"protiv {x['protiv']}", f"uzdržan {x['uzdrzan']}"]
    elif k == "dnevni_red":
        out = [f"sednica počinje: {_when(x.get('pocinje') or x['dan'])}"] + ([x["sednica"]] if x.get("sednica") else [])
    elif k == "objavljen":
        out = [f"u „Službenom glasniku RS“ br. {x.get('glasnik') or ''}".rstrip()]
    elif k == "nije_na_spisku":
        out = ["povučen je, ili mu je postupak prestao; Skupština ne navodi razlog",
               f"poslednji put na spisku: {_day(date.fromisoformat(x['dan']))}"]
    else:
        out = ([f"podneo: {x['predlagac']}"] if x.get("predlagac") else []) + [_day(date.fromisoformat(x["dan"]))]
    if x.get("i_u"):
        out.append("i u oblasti: " + ", ".join(x["i_u"]))
    return out


def _area_rows(told: AreaNews, cyr: bool) -> tuple[str, list[str]]:
    """The areas' cards: each area, its events by kind (at most AREA_MOST of one kind, the rest on the area's page)."""
    t = cyrillic if cyr else (lambda s: s)
    e = lambda s: escape(t(s))  # noqa: E731
    font, pre = f"font-family:{mejl.SANS};", "cir/" if cyr else ""
    html, text = [], []
    for f, evs in told:
        page = f"{mejl.SITE}{pre}oblast/{f.slug}"
        html.append(f'<div style="{font}font-size:16px;line-height:1.4;color:{mejl.INK};padding:22px 20px 2px"><b><a href="{escape(page)}" '
                    f'style="color:{mejl.INK};font-weight:bold">{e(f.name)}</a></b></div>')
        text += ["", t(f.name)]
        for kind in KINDS_ORDER:
            mine = [x for x in evs if x["vrsta"] == kind]
            if not mine:
                continue
            one, many = _GROUP[kind]
            label = one if len(mine) == 1 else many.format(n=len(mine))
            html.append(f'<div style="{font}font-size:12px;letter-spacing:.06em;font-weight:bold;color:{mejl.MUTED};padding:12px 20px 0">{e(label.upper())}</div>')
            text.append(t(label.upper()))
            for x in mine[:AREA_MOST]:
                parts = [t(p) for p in _event_lines(x)]
                shown = [escape(p) for p in parts]
                if "za" in x:  # the colours of "za" and "protiv", as on the site
                    shown[1] = f'<b style="color:{mejl.ZA}">{shown[1]}</b>'
                    shown[2] = f'<b style="color:{mejl.PROTIV}">{shown[2]}</b>'
                name = t(x.get("naslov") or "")
                href = f"{mejl.SITE}{pre}{x['strana']}" if x.get("strana") else page
                html.append(f'<div style="{font}font-size:15px;line-height:1.45;color:{mejl.INK};padding:8px 20px"><a href="{escape(href)}" '
                            f'style="color:{mejl.INK};font-weight:bold;text-decoration:underline">{escape(name)}</a><br>'
                            f'<span style="color:{mejl.MUTED};font-size:14px">{" · ".join(shown)}</span></div>')
                text.append(f"  {name} · " + " · ".join(parts) + f": {href}")
            if len(mine) > AREA_MOST:
                more = f"još {len(mine) - AREA_MOST} na strani oblasti"
                html.append(f'<div style="{font}font-size:15px;color:{mejl.INK};padding:6px 20px"><a href="{escape(page)}" '
                            f'style="color:{mejl.ZA};font-weight:bold">{e(more)}</a></div>')
                text.append(f"  {t(more)}: {page}")
    if told:
        html.append(f'<div style="{font}font-size:13px;line-height:1.5;color:{mejl.MUTED};padding:18px 20px 0">{e(AREA_NOTE)}</div>'
                    f'<div style="{font}font-size:13px;line-height:1.5;color:{mejl.MUTED};padding:6px 20px 0">{e(AREA_SOURCE)}</div>')
        text += ["", t(AREA_NOTE), t(AREA_SOURCE)]
    return "".join(html), text


def _law_rows(told: LawNews, cyr: bool) -> tuple[str, list[str]]:
    """The bills' and laws' cards: the bill's or law's name, its events by kind; a bill's own without its name again,
    another bill's (a change of the law) with its title, as in an area's card."""
    t = cyrillic if cyr else (lambda s: s)
    e = lambda s: escape(t(s))  # noqa: E731
    font, pre = f"font-family:{mejl.SANS};", "cir/" if cyr else ""
    html, text = [], []
    for f, evs in told:
        own = [x for x in evs if x.get("svoj")]
        # A bill's name as the Assembly gives it (whole: what is sealed may be cut); once passed, the law's short name.
        named = [x["naslov"] for x in own if x["vrsta"] in ("usvojen", "objavljen")] or \
                [x["naslov"] for x in own if x["vrsta"] not in ("usvojen", "objavljen")] or                 [x["glava"] for x in evs if x.get("glava")] or [f.name]
        page = next((x["strana"] for x in own if x.get("strana")), "")
        head = e(named[0])
        if page:
            head = (f'<a href="{escape(mejl.SITE + pre + page)}" style="color:{mejl.INK};font-weight:bold">{head}</a>')
        html.append(f'<div style="{font}font-size:16px;line-height:1.4;color:{mejl.INK};padding:22px 20px 2px"><b>{head}</b></div>')
        text += ["", t(named[0]) + (f": {mejl.SITE}{pre}{page}" if page else "")]
        groups = LAW_GROUP if f.kind == "z" else _GROUP
        for kind in KINDS_ORDER:
            mine = [x for x in evs if x["vrsta"] == kind]
            if not mine:
                continue
            one, many = (LAW_GROUP if not all(x.get("svoj") for x in mine) else groups)[kind]
            label = one if len(mine) == 1 else many.format(n=len(mine))
            html.append(f'<div style="{font}font-size:12px;letter-spacing:.06em;font-weight:bold;color:{mejl.MUTED};padding:12px 20px 0">{e(label.upper())}</div>')
            text.append(t(label.upper()))
            for x in mine[:AREA_MOST]:
                parts = [t(p) for p in _event_lines(x)]
                shown = [escape(p) for p in parts]
                if "za" in x:
                    shown[1] = f'<b style="color:{mejl.ZA}">{shown[1]}</b>'
                    shown[2] = f'<b style="color:{mejl.PROTIV}">{shown[2]}</b>'
                href = f"{mejl.SITE}{pre}{x['strana']}" if x.get("strana") else ""
                if x.get("svoj"):
                    html.append(f'<div style="{font}font-size:15px;line-height:1.45;color:{mejl.MUTED};padding:8px 20px">{" · ".join(shown)}</div>')
                    text.append("  " + " · ".join(parts))
                else:
                    name = escape(t(x.get("naslov") or ""))
                    name = f'<a href="{escape(href)}" style="color:{mejl.INK};font-weight:bold;text-decoration:underline">{name}</a>' if href else f"<b>{name}</b>"
                    html.append(f'<div style="{font}font-size:15px;line-height:1.45;color:{mejl.INK};padding:8px 20px">{name}<br>'
                                f'<span style="color:{mejl.MUTED};font-size:14px">{" · ".join(shown)}</span></div>')
                    text.append(f"  {t(x.get('naslov') or '')} · " + " · ".join(parts) + (f": {href}" if href else ""))
            if len(mine) > AREA_MOST:
                more = f"još {len(mine) - AREA_MOST}"
                html.append(f'<div style="{font}font-size:15px;color:{mejl.MUTED};padding:6px 20px">{e(more)}</div>')
                text.append(f"  {t(more)}")
        if f.kind == "b" and any(x.get("svoj") and x["vrsta"] == "usvojen" for x in evs):
            html.append(f'<div style="{font}font-size:15px;line-height:1.5;color:{mejl.INK};padding:8px 20px">{e(LAW_NOTE)}</div>')
            text.append("  " + t(LAW_NOTE))
    if told:
        html.append(f'<div style="{font}font-size:13px;line-height:1.5;color:{mejl.MUTED};padding:18px 20px 0">{e(LAW_SOURCE)}</div>')
        text += ["", t(LAW_SOURCE)]
    return "".join(html), text


def _all_rows(told: Told, cyr: bool) -> tuple[str, list[str]]:
    html, text = _rows(told.speeches, cyr) if told.speeches else ("", [])
    more, lines = _area_rows(told.areas, cyr)
    laws, law_lines = _law_rows(told.laws, cyr)
    return html + more + laws, text + lines + law_lines


def _manage(reader: Follower, cyr: bool) -> tuple[str, list[str]]:
    """Everything the reader follows, each with the link that ends it, and the two that end more."""
    t = cyrillic if cyr else (lambda s: s)
    e = lambda s: escape(t(s))  # noqa: E731
    font = f"font-family:{mejl.SANS};"
    a = lambda href, words: f'<a href="{escape(href)}" style="color:{mejl.MUTED}">{e(words)}</a>'  # noqa: E731
    html = [f'<div style="{font}font-size:16px;font-weight:bold;color:{mejl.INK};padding:16px 20px 4px">{e("Sve što pratiš")}</div>']
    text = [t("Sve što pratiš")]
    # The MPs by surname, then the areas, the bills and the laws by name: "Oblast: …", "Predlog: …", "Zakon: …".
    kinds = {"p": "", "o": "Oblast: ", "b": "Predlog: ", "z": "Zakon: "}
    for f in sorted(reader.follows, key=lambda f: ("pobz".index(f.kind), _order(f.name) if f.kind == "p" else f.name)):
        shown = kinds[f.kind] + f.name
        html.append(f'<div style="{font}font-size:15px;line-height:1.5;color:{mejl.INK};padding:8px 20px">{e(shown)} · {a(ends(f.end), "Prestani da pratiš")}</div>')
        text.append(t(f"  {shown} · Prestani da pratiš: ") + ends(f.end))
    html.append(f'<div style="{font}font-size:15px;line-height:1.5;color:{mejl.MUTED};padding:8px 20px">{a(reader.all_end, "Prestani sve da pratiš")} · '
                f'{a(reader.out, "Odjavi me sa svega")}</div>')
    text += [t("  Prestani sve da pratiš: ") + reader.all_end, t("  Odjavi me sa svega: ") + reader.out]
    return "".join(html), text


def _told(told: Told | News) -> Told:
    return told if isinstance(told, Told) else Told(told, [])


def build(reader: Follower, told: Told | News, today: date | None = None) -> mejl.Mail:
    """A mail of its own (the plain list: variant B): the subject the same for all, no name in it."""
    told = _told(told)
    cyr = reader.cir
    t = cyrillic if cyr else (lambda s: s)
    e = lambda s: escape(t(s))  # noqa: E731
    font, pre = f"font-family:{mejl.SANS};", "cir/" if cyr else ""
    last = told.last(today or datetime.now(TZ).date())
    subject = t(f"Ono što pratiš: {_day(last)}")
    rows, lines = _all_rows(told, cyr)
    manage, tail = _manage(reader, cyr)
    method, privacy = f"{mejl.SITE}{pre}{METHOD}", f"{mejl.SITE}{pre}{PRIVACY}"
    html = f"""<!doctype html>
<html lang="{'sr-Cyrl' if cyr else 'sr-Latn'}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light only"><meta name="supported-color-schemes" content="light"><title>{escape(subject)}</title></head>
<body style="margin:0;padding:0;background:{mejl.PAPER}">
<div style="display:none;max-height:0;overflow:hidden;mso-hide:all">{e("Šta je novo kod onoga što pratiš.")}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" bgcolor="{mejl.PAPER}"><tr><td align="center">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px"><tr><td>
<div style="{font}font-size:14px;color:{mejl.MUTED};padding:20px 20px 0">{e("Za ili Protiv")} · {e(_day(last))}</div>
<div style="font-family:{mejl.SERIF};font-size:24px;font-weight:bold;color:{mejl.INK};padding:6px 20px">{e("Ono što pratiš")}</div>
{rows}
<div style="margin:22px 20px 0;border-top:1px solid {mejl.LINE}"></div>
{manage}
<div style="{font}font-size:12px;line-height:1.8;color:{mejl.MUTED};padding:22px 20px 28px"><a href="{escape(method)}" style="color:{mejl.MUTED}">{e("Kako nastaje ovaj mejl")}</a> · <a href="{escape(privacy)}" style="color:{mejl.MUTED}">{e("Politika o privatnosti")}</a><br>{e("Ovaj mejl stiže jer je praćenje potvrđeno sa ove adrese.")}<br>{e("Za ili Protiv")} · {mejl.CONTACT}</div>
</td></tr></table></td></tr></table></body></html>
"""
    text = "\n".join([t(f"ZA ILI PROTIV · {_day(last)}"), "", t("Ono što pratiš"), "", *lines, "", *tail, "",
                      t("Kako nastaje ovaj mejl: ") + method, t("Politika o privatnosti: ") + privacy,
                      t("Ovaj mejl stiže jer je praćenje potvrđeno sa ove adrese."), f"{t('Za ili Protiv')} · {mejl.CONTACT}"]) + "\n"
    return mejl.Mail(subject, text, html)


def block(reader: Follower, told: Told | News, cyr: bool) -> tuple[str, list[str]]:
    """The same inside the day's summary, as a card, in the summary's script: (HTML, the plain text's lines)."""
    t = cyrillic if cyr else (lambda s: s)
    rows, lines = _all_rows(_told(told), cyr)
    manage, tail = _manage(reader, cyr)
    html = ('<tr><td style="padding:14px 0 0"><table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>'
            f'<td bgcolor="{mejl.PAPER}" style="background:{mejl.PAPER};border-radius:14px;padding:18px 0 10px">'
            f'<div style="font-family:{mejl.SERIF};font-size:24px;font-weight:bold;color:{mejl.INK};padding:0 20px">{escape(t("Ono što pratiš"))}</div>'
            f'{rows}<div style="margin:18px 20px 0;border-top:1px solid {mejl.LINE}"></div>{manage}</td></tr></table></td></tr>')
    return html, [t("ONO ŠTO PRATIŠ"), *lines, "", *tail, ""]


def code(day: date) -> str:
    """The code in the maintainer's link of a morning: not the summary's, though of the same key."""
    return hmac.new((config.MAIL_KEY or "").encode(), f"prati|{day.isoformat()}".encode(), hashlib.sha256).hexdigest()[:32]


class Following(threading.Thread):
    """Sends what is followed: a part of the day's summary (asked by `Mailer._to_all`), and a mail of its own from nine."""

    def __init__(self, tracker, mailer: pretplata.Mailer, stop: threading.Event) -> None:
        super().__init__(daemon=True)
        self.tracker, self.mailer, self.halt = tracker, mailer, stop
        self.file = Path(mailer.folder) / "prati" / "stanje.json"
        self.numbers = Path(mailer.folder) / "prati" / "dogadjaji.json"  # the areas' events by number: public, nobody's
        self._lock = threading.Lock()  # the state's
        self.fetch = lambda: json.loads(mreza.site(config.AREAS_URL))  # the site's file of the areas' events
        self.points: dict[str, int] = {}  # an area's name: its point of Article 97, from the same file
        self.bills: dict = {}  # a bill's key: the laws it changes and the day it passed, from the same file
        mailer.following = self

    # What is kept.
    def _state(self) -> dict:
        try:
            kept = json.loads(self.file.read_text(encoding="utf-8"))
            return kept if isinstance(kept, dict) else {}
        except (OSError, ValueError):
            return {}

    def _told_seq(self, state: dict, rid: str) -> int:
        """The number of the last area's event a reader was told (0: none)."""
        n = (state.get("citaoci") or {}).get(rid, {}).get("o_do", 0)
        return n if isinstance(n, int) else 0

    def events(self, today: date) -> list[dict]:
        """The site's events of the areas, each with its number: a new one gets the next, the day it is first seen here.
        Not reached: none this time, and the numbers stay as they were."""
        try:
            got = self.fetch()
            evs = [e for e in got.get("dogadjaji") or [] if isinstance(e, dict) and e.get("id")]
            self.points = {v[0]: int(k) for k, v in (got.get("oblasti") or {}).items() if isinstance(v, list) and v}
            self.bills = {k: v for k, v in (got.get("predlozi") or {}).items() if isinstance(v, dict)}
        except Exception as exc:  # noqa: BLE001
            log.warning("praćenje oblasti: spisak događaja nije stigao (%s)", type(exc).__name__)
            return []
        with self._lock:
            try:
                kept = json.loads(self.numbers.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                kept = {}
            n, ids = int(kept.get("n") or 0), dict(kept.get("ids") or {})
            for e in evs:
                if e["id"] not in ids:
                    n += 1
                    ids[e["id"]] = [n, today.isoformat()]
            now = {e["id"] for e in evs}
            old = (today - timedelta(days=KEEP_EVENTS)).isoformat()
            ids = {k: v for k, v in ids.items() if k in now or v[1] >= old}
            if ids != kept.get("ids") or n != kept.get("n"):
                self.numbers.parent.mkdir(parents=True, exist_ok=True)
                _write(self.numbers, {"n": n, "ids": ids})
        return [{**e, "seq": ids[e["id"]][0], "prvi": ids[e["id"]][1]} for e in evs]

    def told(self, p: Follower, days: dict[date, dict], events: list[dict], state: dict, today: date) -> Told:
        """What a reader is to be told now: speeches since the day told, events since the number told."""
        speeches = news(p, days, self._facts(), self._told(state, p.id))
        laws = law_news(p, events, self.bills, self._told_seq(state, p.id), today)
        areas = area_news(p, events, self.points, self._told_seq(state, p.id), today,
                          frozenset(e["id"] for _, evs in laws for e in evs))  # a bill's or law's event under its own card
        return Told(speeches, areas, max((e["seq"] for _, evs in [*areas, *laws] for e in evs), default=0), laws)

    def _told(self, state: dict, rid: str) -> date | None:
        try:
            return date.fromisoformat((state.get("citaoci") or {}).get(rid, {}).get("do", ""))
        except ValueError:
            return None

    def _mark(self, marks: dict[str, dict | None]) -> None:
        """What a reader was told, by the row id (None: nothing is kept of that reader)."""
        with self._lock:
            state = self._state()
            kept = dict(state.get("citaoci") or {})
            for rid, m in marks.items():
                if m is None:
                    kept.pop(rid, None)
                else:
                    kept[rid] = m
            state["citaoci"] = kept
            self.file.parent.mkdir(parents=True, exist_ok=True)
            _write(self.file, state)

    def _set(self, **more) -> None:
        with self._lock:
            state = {**self._state(), **more}
            self.file.parent.mkdir(parents=True, exist_ok=True)
            _write(self.file, state)

    # What there is to tell.
    def followers(self) -> list[Follower]:
        return opened(pretplata._call("/m/prati/spisak").get("pratioci", []))

    def days(self, upto: date) -> dict[date, dict]:
        """The last days' speeches, `upto` the last of them."""
        out = {}
        for x in self.tracker.days_kept():
            try:
                d = date.fromisoformat(x)
            except ValueError:
                continue
            if upto - timedelta(days=KEEP_DAYS) < d <= upto:
                said = spoken(self.tracker.record(x))
                if said:
                    out[d] = said
        return out

    def _facts(self) -> dict:
        return getattr(self.tracker, "facts", None) or {}

    def blocks(self, day: date) -> dict[str, tuple[Follower, News]]:
        """For the day's summary: what each of its readers who follows somebody is told in it, by the summary's row id.
        Empty when the counter does not answer: the summary goes without it, and the mail of its own tells it."""
        try:
            people = [p for p in self.followers() if p.summary]
        except Exception as exc:  # noqa: BLE001 — the summary is not held up
            log.warning("praćenje %s: spisak nije stigao (%s)", day, type(exc).__name__)
            return {}
        state, days = self._state(), self.days(day)
        now = datetime.now(TZ).date()
        events = self.events(now) if any(f.kind != "p" for p in people for f in p.follows) else []
        out = {}
        for p in people:
            if (state.get("citaoci") or {}).get(p.id, {}).get("poslat") == now.isoformat():
                continue  # a mail of its own went today already
            told = self.told(p, days, events, state, now)
            if told:
                out[p.summary] = (p, told)
        return out

    @staticmethod
    def card(told: tuple[Follower, News], cyr: bool) -> tuple[str, list[str]]:
        return block(*told, cyr)

    def begin(self, people: list[tuple[Follower, Told]]) -> dict[str, dict | None]:
        """Marked as told before the call that sends: whatever happens to it, nobody is told twice. Returns what stood."""
        with self._lock:
            before = {p.id: (self._state().get("citaoci") or {}).get(p.id) for p, _ in people}
        today = datetime.now(TZ).date().isoformat()
        marks = {}
        for p, told in people:
            told = _told(told)
            m = {**(before.get(p.id) or {}), "poslat": today}
            if told.speeches:
                m["do"] = max(d for _, rows in told.speeches for d, _ in rows).isoformat()
            if told.areas or told.laws:
                m["o_do"] = max(told.seq, m.get("o_do", 0) if isinstance(m.get("o_do"), int) else 0)
            marks[p.id] = m
        self._mark(marks)
        return before

    def undo(self, before: dict[str, dict | None], ids: list[str]) -> None:
        """Those to whom it surely did not go."""
        self._mark({i: before.get(i) for i in ids})

    # A mail of its own.
    def due(self, now: datetime) -> tuple[list[tuple[Follower, News]], int]:
        """Who is to be told now, and how many wait for the day's summary."""
        today, state = now.date(), self._state()
        days = self.days(today - timedelta(days=1))
        ready, waits, seen = [], 0, set()
        people = self.followers()
        events = self.events(today) if any(f.kind != "p" for p in people for f in p.follows) else []
        for p in people:
            if p.to.lower() in seen or (state.get("citaoci") or {}).get(p.id, {}).get("poslat") == today.isoformat():
                continue
            seen.add(p.to.lower())
            told = self.told(p, days, events, state, today)
            if not told:
                continue  # nothing new: no mail (a day with no speech and no event sends nothing)
            held = p.summary and any(not self.mailer.went(d) and now <= pretplata.deadline(d) for _, rows in told.speeches for d, _ in rows)
            if held:
                waits += 1
            else:
                ready.append((p, told))
        gone = set(state.get("citaoci") or {}) - {p.id for p in people}
        if gone and people:  # a reader who ended everything: nothing is kept of them
            self._mark({i: None for i in gone})
        return ready, waits

    def _send(self, people: list[tuple[Follower, Told]]) -> tuple[int, int]:
        """(how many went, how many did not): a batch at a time, marked before its call."""
        went = not_ = 0
        for i in range(0, len(people), pretplata.BATCH):
            batch = people[i:i + pretplata.BATCH]
            messages = []
            for p, told in batch:
                m = build(p, told, datetime.now(TZ).date())
                messages.append({"to": p.to, "subject": m.subject, "html": m.html, "text": m.text, "odjava": p.all_end})
            before = self.begin(batch)
            try:
                _, wrong = pretplata.send(messages)
            except Exception as exc:  # noqa: BLE001
                if pretplata._not_sent(exc):
                    self.undo(before, [p.id for p, _ in batch])
                log.warning("praćenje: prekid (%s)", type(exc).__name__)
                return went, not_ + len(batch)
            bad = {w["i"] for w in wrong if w.get("i") in range(len(batch))}
            today = datetime.now(TZ).date().isoformat()  # not told, and not tried again today: tomorrow's tells it
            self._mark({batch[k][0].id: {**(before.get(batch[k][0].id) or {}), "poslat": today} for k in bad})
            went, not_ = went + len(batch) - len(bad), not_ + len(bad)
        return went, not_

    def _preview(self, now: datetime, ready: int, waits: int) -> tuple[str, str, str]:
        """The maintainer's mail of the morning: how many in all, who spoke by the caption, and a sample of the first of
        them by the alphabet. Nothing of who follows whom."""
        days = self.days(now.date() - timedelta(days=1))
        facts = self._facts()
        name = lambda s: mejl.given_first(str((facts.get(s) or {}).get("ime") or s))  # noqa: E731
        heard = "".join(f"<li>{escape(_day(d))}: " + escape(", ".join(f"{name(s)} ({len(x)})" for s, x in sorted(
            days[d].items(), key=lambda kv: _order(name(kv[0]))))) + "</li>" for d in sorted(days))
        new = self.new_events(now.date())
        if days:
            last = max(days)
            slug = min(days[last], key=lambda s: _order(name(s)))
            one = Followed(slug, name(slug), last, ("#",))
            shown = build(Follower("", "", False, "", "#", "#", (one,)), Told([(one, [(last, days[last][slug])])], []), now.date())
        elif any(e.get("oblasti") for e in new):  # no MP spoke: the first area by its point with something new
            point = min(a for e in new for a in e.get("oblasti") or [])
            area = next(n for n, k in self.points.items() if k == point)
            one = Followed(area, area, now.date() - timedelta(days=KEEP_DAYS), ("#",), "o")
            reader = Follower("", "", False, "", "#", "#", (one,))
            shown = build(reader, Told([], area_news(reader, new, self.points, 0, now.date())), now.date())
        else:  # nor an area's: the first bill with something new, as its follower would get it
            key = next((e["predlog"] for e in sorted(new, key=lambda e: e.get("naslov") or "") if e.get("predlog")), "")
            one = Followed(key, key, now.date() - timedelta(days=KEEP_DAYS), ("#",), "b")
            reader = Follower("", "", False, "", "#", "#", (one,))
            shown = build(reader, Told([], [], 0, law_news(reader, new, self.bills, 0, now.date())), now.date())
        url = f"{config.PUBLIC_URL.rstrip('/')}/mejl/prati?dan={now.date().isoformat()}&k={code(now.date())}"
        top = ('<div style="font-family:sans-serif;padding:12px;background:#fbf0dc"><p><a href="' + escape(url) + '"><b>Pošalji onima koji prate</b></a> '
               f'(do {TO_HOUR} h). Spremno: {ready}; čekaju sažetak dana: {waits}.</p>'
               + (f"<p>Po natpisu su govorili:</p><ul>{heard}</ul>" if days else "")
               + (f"<p>Novo u oblastima zakona: {sum(1 for e in new if e.get('oblasti'))}; kod predloga i zakona: {len(new)}.</p>" if new else "")
               + "<p>Primer, prvi po azbuci ili po tački člana 97. (linkovi za prekid ne vode nikuda):</p></div>")
        return "[za tebe] " + shown.subject, pretplata._with_top(shown.html, top), f"Pošalji onima koji prate: {url}\n\n{shown.text}"

    def new_events(self, today: date) -> list[dict]:
        """The events that some reader could still be told: of the last KEEP_DAYS days."""
        since = (today - timedelta(days=KEEP_DAYS)).isoformat()
        return [e for e in self.events(today) if _own(e) >= since]

    def step(self, now: datetime | None = None) -> bool:
        """A look: in the morning, the maintainer's mail once; then, when he clicked (or on its own), who is to be told."""
        now = now or datetime.now(TZ)
        if not (config.MAIL_KEY and config.MAIL_EDITOR and config.PUSH_TOKEN) or not FROM_HOUR <= now.hour < TO_HOUR:
            return False
        today, state = now.date().isoformat(), self._state()
        if not self.days(now.date() - timedelta(days=1)) and not self.new_events(now.date()):
            return False  # nothing new to anybody: no mail, and the counter is not asked
        allowed = config.FOLLOW_ALONE or state.get("klik") == today
        if not allowed and state.get("uredniku") == today:
            return False  # nothing to do until the click
        if not self.mailer._lock.acquire(blocking=False):
            return False
        try:
            with cuvar.making("the mail to who follows an MP"):
                ready, waits = self.due(now)
                if allowed:
                    if not ready:
                        return False
                    went, not_ = self._send(ready)
                    log.info("praćenje: poslato %d, nije prošlo %d, čeka sažetak %d", went, not_, waits)
                    return bool(went)
                if not ready and not waits:
                    return False
                subject, html, text = self._preview(now, len(ready), waits)
                sent, _ = pretplata.send([{"to": config.MAIL_EDITOR, "subject": subject, "html": html, "text": text}])
                if sent:
                    self._set(uredniku=today)
                return bool(sent)
        finally:
            self.mailer._lock.release()

    def to_all(self, day: date, k: str, now: datetime | None = None) -> tuple[str, int]:
        """The maintainer's click: (what happened, how many it went to). Good that morning only."""
        now = now or datetime.now(TZ)
        if not config.MAIL_KEY or not hmac.compare_digest(k.encode(), code(day).encode()):
            return "kod", 0
        if day != now.date() or not FROM_HOUR <= now.hour < TO_HOUR:
            return "kasno", 0
        if not self.mailer._lock.acquire(blocking=False):
            return "u_toku", 0
        try:
            with cuvar.making("the mail to who follows an MP"):
                try:
                    ready, waits = self.due(now)
                except Exception as exc:  # noqa: BLE001
                    log.warning("praćenje: spisak nije stigao (%s)", type(exc).__name__)
                    return "brojac", 0
                self._set(klik=day.isoformat())
                went, not_ = self._send(ready)
                log.info("praćenje: poslato %d, nije prošlo %d, čeka sažetak %d", went, not_, waits)
                return ("deo" if not_ else "ok"), went
        finally:
            self.mailer._lock.release()

    def run(self) -> None:
        while not self.halt.is_set():
            try:
                self.step()
            except Exception as exc:  # noqa: BLE001 — never with what was opened in it
                log.warning("praćenje nije pokušano: %s", type(exc).__name__)
            self.halt.wait(EVERY)


def page_ask(day: str, k: str) -> str:
    try:
        d = date.fromisoformat(day)
    except ValueError:
        return pretplata._PAGE.format(body="<h1>Link nije ispravan</h1>")
    return pretplata._PAGE.format(body=f"<h1>Praćenje, {d.day}. {mejl.MONTHS_OF[d.month - 1]}</h1><p>Mejl ide onima koji prate nekog ko je govorio, "
                                       f"jednom, do {TO_HOUR} h. Ko prima i sažetak dana koji još nije poslat, dobija ga s njim ili u podne.</p>"
                                       f'<form method="post"><input type="hidden" name="dan" value="{escape(day)}"><input type="hidden" name="k" '
                                       f'value="{escape(k[:64])}"><button>Pošalji</button></form>')


def page_done(what: str, n: int) -> str:
    text = {"ok": f"Poslato: {n}.", "deo": f"Poslato: {n}. Nekima nije prošlo: ako je veza pukla, klikni ponovo; inače im ide sutra.",
            "kasno": f"Link važi samo tog jutra, od {FROM_HOUR} do {TO_HOUR} h. Što nije poslato ide sutra.", "u_toku": "Slanje je već u toku.",
            "brojac": "Brojač ne odgovara, ništa nije poslato: probaj ponovo za koji minut.", "kod": "Link nije ispravan."}.get(what, "Nije poslato.")
    return pretplata._PAGE.format(body=f"<h1>Praćenje</h1><p>{escape(text)}</p>")
