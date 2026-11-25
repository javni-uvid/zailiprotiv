"""Following a sitting MP by mail (25 Nov 2026): the morning after a day on which the MP spoke in the hall.

The counter keeps who follows whom sealed (`worker/prati.js`); both are opened here, in memory, only to send, and never
written down or logged. What is kept (`/data/mejl/prati/stanje.json`) is by the counter's row id: the day up to which a
reader was told, and the day a mail last went. Nobody is counted by MP, here or anywhere.

Only a speech whose name was read from the broadcast's caption is told: a name by the voice or by the chair's words
alone is a guess (measured on 18, 24 and 25 Nov against the notes: the caption right for 60 of 61), so a mail may miss
a speech. The same rule for every MP. At most one mail a day to a reader: who has the day's summary too finds this in it
(`Mailer._to_all`), and waits for it until noon; the rest get a mail of its own from nine. For as long as PRATI_SAMO is
not set, only on the maintainer's click.

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

from . import config, cuvar, mejl, pretplata
from .names import cyrillic
from .state_base import _write

log = logging.getLogger("uzivo.prati")
TZ = pretplata.TZ
FROM_HOUR, TO_HOUR = 9, 13  # the mail goes between these; what is not sent by then goes the next morning
KEEP_DAYS = 3  # a day older than this is told no more
EVERY = 300  # seconds between looks
METHOD = "kako-racunamo#pracenje"
PRIVACY = "privatnost#pracenje"


@dataclass(frozen=True)
class Followed:
    slug: str   # the MP's address on the site when the reader asked, and the name then
    name: str
    since: date
    end: tuple[str, ...]  # the links that end it: more than one when the same MP was asked for twice


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
                if kind != "p":
                    continue
                had = found.get(slug)
                since = date.fromisoformat(p["od"])
                found[slug] = Followed(slug, name, min(since, had.since) if had else since, (had.end if had else ()) + (p["kraj"],))
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
    for f in sorted(reader.follows, key=lambda f: _order(f.name)):
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


def _manage(reader: Follower, cyr: bool) -> tuple[str, list[str]]:
    """Everything the reader follows, each with the link that ends it, and the two that end more."""
    t = cyrillic if cyr else (lambda s: s)
    e = lambda s: escape(t(s))  # noqa: E731
    font = f"font-family:{mejl.SANS};"
    a = lambda href, words: f'<a href="{escape(href)}" style="color:{mejl.MUTED}">{e(words)}</a>'  # noqa: E731
    html = [f'<div style="{font}font-size:16px;font-weight:bold;color:{mejl.INK};padding:16px 20px 4px">{e("Sve što pratiš")}</div>']
    text = [t("Sve što pratiš")]
    for f in sorted(reader.follows, key=lambda f: _order(f.name)):
        html.append(f'<div style="{font}font-size:15px;line-height:1.5;color:{mejl.INK};padding:8px 20px">{e(f.name)} · {a(ends(f.end), "Prestani da pratiš")}</div>')
        text.append(t(f"  {f.name} · Prestani da pratiš: ") + ends(f.end))
    html.append(f'<div style="{font}font-size:15px;line-height:1.5;color:{mejl.MUTED};padding:8px 20px">{a(reader.all_end, "Prestani sve da pratiš")} · '
                f'{a(reader.out, "Odjavi me sa svega")}</div>')
    text += [t("  Prestani sve da pratiš: ") + reader.all_end, t("  Odjavi me sa svega: ") + reader.out]
    return "".join(html), text


def build(reader: Follower, told: News) -> mejl.Mail:
    """A mail of its own (the plain list: variant B): the subject the same for all, no name in it."""
    cyr = reader.cir
    t = cyrillic if cyr else (lambda s: s)
    e = lambda s: escape(t(s))  # noqa: E731
    font, pre = f"font-family:{mejl.SANS};", "cir/" if cyr else ""
    last = max(d for _, rows in told for d, _ in rows)
    subject = t(f"Ono što pratiš: {_day(last)}")
    rows, lines = _rows(told, cyr)
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


def block(reader: Follower, told: News, cyr: bool) -> tuple[str, list[str]]:
    """The same inside the day's summary, as a card, in the summary's script: (HTML, the plain text's lines)."""
    t = cyrillic if cyr else (lambda s: s)
    rows, lines = _rows(told, cyr)
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
        self._lock = threading.Lock()  # the state's
        mailer.following = self

    # What is kept.
    def _state(self) -> dict:
        try:
            kept = json.loads(self.file.read_text(encoding="utf-8"))
            return kept if isinstance(kept, dict) else {}
        except (OSError, ValueError):
            return {}

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
        today = datetime.now(TZ).date().isoformat()
        out = {}
        for p in people:
            if (state.get("citaoci") or {}).get(p.id, {}).get("poslat") == today:
                continue  # a mail of its own went today already
            told = news(p, days, self._facts(), self._told(state, p.id))
            if told:
                out[p.summary] = (p, told)
        return out

    @staticmethod
    def card(told: tuple[Follower, News], cyr: bool) -> tuple[str, list[str]]:
        return block(*told, cyr)

    def begin(self, people: list[tuple[Follower, News]]) -> dict[str, dict | None]:
        """Marked as told before the call that sends: whatever happens to it, nobody is told twice. Returns what stood."""
        with self._lock:
            before = {p.id: (self._state().get("citaoci") or {}).get(p.id) for p, _ in people}
        today = datetime.now(TZ).date().isoformat()
        self._mark({p.id: {"do": max(d for _, rows in told for d, _ in rows).isoformat(), "poslat": today} for p, told in people})
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
        for p in people:
            if p.to.lower() in seen or (state.get("citaoci") or {}).get(p.id, {}).get("poslat") == today.isoformat():
                continue
            seen.add(p.to.lower())
            told = news(p, days, self._facts(), self._told(state, p.id))
            if not told:
                continue
            held = p.summary and any(not self.mailer.went(d) and now <= pretplata.deadline(d) for _, rows in told for d, _ in rows)
            if held:
                waits += 1
            else:
                ready.append((p, told))
        gone = set(state.get("citaoci") or {}) - {p.id for p in people}
        if gone and people:  # a reader who ended everything: nothing is kept of them
            self._mark({i: None for i in gone})
        return ready, waits

    def _send(self, people: list[tuple[Follower, News]]) -> tuple[int, int]:
        """(how many went, how many did not): a batch at a time, marked before its call."""
        went = not_ = 0
        for i in range(0, len(people), pretplata.BATCH):
            batch = people[i:i + pretplata.BATCH]
            messages = []
            for p, told in batch:
                m = build(p, told)
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
        last = max(days)
        slug = min(days[last], key=lambda s: _order(name(s)))
        shown = build(Follower("", "", False, "", "#", "#", (Followed(slug, name(slug), last, ("#",)),)),
                      [(Followed(slug, name(slug), last, ("#",)), [(last, days[last][slug])])])
        url = f"{config.PUBLIC_URL.rstrip('/')}/mejl/prati?dan={now.date().isoformat()}&k={code(now.date())}"
        top = ('<div style="font-family:sans-serif;padding:12px;background:#fbf0dc"><p><a href="' + escape(url) + '"><b>Pošalji onima koji prate</b></a> '
               f'(do {TO_HOUR} h). Spremno: {ready}; čekaju sažetak dana: {waits}.</p><p>Po natpisu su govorili:</p><ul>{heard}</ul>'
               "<p>Primer, prvi po azbuci (linkovi za prekid ne vode nikuda):</p></div>")
        return "[za tebe] " + shown.subject, pretplata._with_top(shown.html, top), f"Pošalji onima koji prate: {url}\n\n{shown.text}"

    def step(self, now: datetime | None = None) -> bool:
        """A look: in the morning, the maintainer's mail once; then, when he clicked (or on its own), who is to be told."""
        now = now or datetime.now(TZ)
        if not (config.MAIL_KEY and config.MAIL_EDITOR and config.PUSH_TOKEN) or not FROM_HOUR <= now.hour < TO_HOUR:
            return False
        today, state = now.date().isoformat(), self._state()
        if not self.days(now.date() - timedelta(days=1)):
            return False
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
