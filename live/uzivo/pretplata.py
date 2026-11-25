"""The day's summary to those who asked for it: first to the maintainer, to all on his click (22 Nov 2026, choice B).

The counter keeps the addresses sealed for the maintainer's key (`worker/mejl.js`); only this service, with
MEJL_KLJUC in live/.env, opens them, and only to send. When the day's summary is on the page (`obavesti.Bell`), the
mail of the day goes to MEJL_UREDNIK alone, with a link to send it to everyone; the link works until noon the
next day, and once. A mail with a word in two scripts (`mejl.mixed_words`) goes to the maintainer saying so, and to
nobody else until that is mended.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import re
import socket
import threading
import time
import urllib.error
from datetime import date, datetime, timedelta
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

from . import config, cuvar, mejl, mere, mreza
from .obavesti import to_tell
from .state_base import _write

log = logging.getLogger("uzivo.pretplata")
COUNTER = "https://glasovi.zailiprotiv.rs"
BATCH = 20
# What Cloudflare answers for an address it will not send to: a bounce, a complaint or an entry by hand put it on the
# list of those it refuses (Email Service, "Suppressions"). Only this code is about the reader's address: the others
# are the account's, the sender's, a quota's or the message's, or may pass (E_DELIVERY_FAILED), and are tried again.
REFUSED = {"E_RECIPIENT_SUPPRESSED"}
TZ = ZoneInfo(config.TZ)
_N = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551  # the order of P-256


def private_key(secret_b64: str):
    """The maintainer's key: 32 random bytes (MEJL_KLJUC), read as a P-256 private number. Its public half is
    MEJL_JAVNI in worker/wrangler.toml."""
    from cryptography.hazmat.primitives.asymmetric import ec
    d = int.from_bytes(base64.b64decode(secret_b64), "big") % (_N - 1) + 1
    return ec.derive_private_key(d, ec.SECP256R1())


def public_jwk(secret_b64: str) -> dict:
    nums = private_key(secret_b64).public_key().public_numbers()
    b64u = lambda i: base64.urlsafe_b64encode(i.to_bytes(32, "big")).rstrip(b"=").decode()  # noqa: E731
    return {"kty": "EC", "crv": "P-256", "x": b64u(nums.x), "y": b64u(nums.y)}


def unseal(secret_b64: str, sealed: str) -> str:
    """An address sealed by the counter (`mejl.js`, seal): its one-time public key, the nonce, the ciphertext."""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    raw = base64.urlsafe_b64decode(sealed + "=" * (-len(sealed) % 4))
    theirs = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), raw[:65])
    shared = private_key(secret_b64).exchange(ec.ECDH(), theirs)
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"zailiprotiv mejl").derive(shared)
    return AESGCM(key).decrypt(raw[65:77], raw[77:], None).decode()


def link_key(day: date) -> str:
    """The code in the maintainer's "send to all" link of a day: the day signed with the service's own key."""
    return hmac.new((config.MAIL_KEY or "").encode(), f"posalji|{day.isoformat()}".encode(), hashlib.sha256).hexdigest()[:32]


def deadline(day: date) -> datetime:
    """A day's mail goes to all until noon the day after (until 23 Nov 2026 until 8: a day ended late left the
    maintainer, who gets the mail at 7, an hour)."""
    return datetime.combine(day + timedelta(days=1), datetime.min.time(), TZ).replace(hour=12)


def _call(path: str, body: dict | None = None) -> dict:
    return mreza.counter(COUNTER + path, config.PUSH_TOKEN, body, timeout=60, agent="zailiprotiv-uzivo")


def send(messages: list[dict]) -> tuple[int, list]:
    """Through the counter, BATCH at a time; how many went and what failed."""
    sent, failed = 0, []
    for i in range(0, len(messages), BATCH):
        got = _call("/m/salji", {"poruke": messages[i:i + BATCH]})
        sent += got.get("poslato", 0)
        failed += [{**f, "i": f.get("i", 0) + i} for f in got.get("greske", [])]
    return sent, failed


def _not_sent(exc: Exception) -> bool:
    """Whether a call that failed surely sent nothing: the counter refused it, or was never reached. A timeout or a
    5xx is neither: some of its messages may have gone."""
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code < 500
    return isinstance(exc, urllib.error.URLError) and isinstance(exc.reason, (ConnectionRefusedError, socket.gaierror))


class Mailer:
    """The day's mail: to the maintainer when the summary is ready, then to all on his link.

    What went is kept per reader (the counter's row id, never the address), written before and after every batch, so
    that a break in the middle loses nobody and nobody gets the day twice: a batch is "nesigurni" while its call is
    out, then each of its readers is sent or failed. The next click goes on with those not yet sent; the uncertain
    (at most one batch) are never sent again (23 Nov 2026). Nor, that day, are those Cloudflare refuses ("odbijeni", by
    the row id): they do not keep the day from its end (25 Nov 2026)."""

    def __init__(self, folder: Path, build):
        self.folder = Path(folder)  # /data/mejl: what went, by day
        self.build = build          # day, cyr, unsubscribe link → mejl.Mail of that day, or None
        self._lock = threading.Lock()  # one sending at a time: the button pressed twice is one sending
        self.hints = getattr(build, "hints", None)  # day → what the chair said after a measure with no name

    def _state(self, day: date) -> dict:
        f = self.folder / f"{day.isoformat()}.json"
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}

    def went(self, day: date) -> bool:
        """Whether the day's mail has begun to go to all: who signs up now is not sure to get it. Read only."""
        try:
            return bool(self._state(day).get("svima"))
        except (OSError, ValueError):
            return False

    def _basis(self, day: date) -> str:
        """For the maintainer's mail only (24 Nov 2026): what each speaker's line rests on in the transcript, word for
        word, the lines that rest on none first; or that the stronger model did not write the day (sudija._whole)."""
        if not config.DAY_MODEL:
            return ""
        f = self.folder.parent / "osnova" / f"{day.isoformat()}.json"
        try:
            kept = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return WEAK
        weak = kept.get("bez_oslonca") or []
        rows = "".join(f"<li><b>{escape(n)}</b>{' (OSLONAC NIJE NAĐEN)' if n in weak else ''}: "
                       f"{escape(' … '.join(str(x) for x in said))}</li>"
                       for n, said in sorted((kept.get("oslonac") or {}).items(), key=lambda kv: kv[0] not in weak))
        return (f"<p>Na čemu počivaju rečenice o govornicima ({escape(str(kept.get('model', '')))}, iz automatskog prepisa; "
                f"samo za tebe){': bez oslonca ' + str(len(weak)) if weak else ''}</p><ul>{rows}</ul>")

    def _keep(self, day: date, state: dict) -> None:
        _write(self.folder / f"{day.isoformat()}.json", state)

    def ready(self, day: date) -> bool:
        """The day's summary is on the page: the maintainer gets the mail and the link. Asked again every few minutes
        (Watch): once it went it goes no more, unless it said a word is in two scripts and that has
        changed since; one that did not go is tried again."""
        if not (config.MAIL_KEY and config.MAIL_EDITOR and config.PUSH_TOKEN) or not self._lock.acquire(blocking=False):
            return False
        try:
            state = self._state(day)
            if state.get("uredniku") and not state.get("dvopis"):
                return False
            m = self.build(day, False, "")
            if m is None:
                return False
            slips = mejl.mixed_words(m.text)
            if state.get("uredniku") and slips == state["dvopis"]:
                return False
            link = f"{config.PUBLIC_URL.rstrip('/')}/mejl/posalji?dan={day.isoformat()}&k={link_key(day)}"
            note = (f"<p><b>Ne može svima:</b> reč u dva pisma ({escape(', '.join(slips))}). Ispravi sažetak dana, pa će stići novi.</p>"
                    if slips else f'<p><a href="{escape(link)}"><b>Pošalji svima</b></a> (do podneva, jednom).</p>')
            basis = self._basis(day)
            top = f'<div style="font-family:sans-serif;padding:12px;background:#fbf0dc">{note}{basis}{self.hints(day) if self.hints else ""}</div>'
            sent, failed = send([{"to": config.MAIL_EDITOR, "subject": ("[za tebe, SLABIJI MODEL] " if basis == WEAK else "[za tebe] ") + m.subject,
                                  "html": _with_top(m.html, top),
                                  "text": ("NE MOŽE SVIMA: " + ", ".join(slips) if slips else "Pošalji svima: " + link) + "\n\n" + m.text}])
            if sent:
                state.update(uredniku=datetime.now(TZ).isoformat(), dvopis=slips)
                self._keep(day, state)
            log.info("mejl %s: uredniku %s", day, "poslat" if sent else f"nije poslat {failed}")
            return bool(sent)
        finally:
            self._lock.release()

    def to_all(self, day: date, code: str) -> tuple[str, int]:
        """The maintainer's link: (what happened, how many have the day's mail in all)."""
        if not config.MAIL_KEY or not hmac.compare_digest(code.encode(), link_key(day).encode()):
            return "kod", 0
        if not self._lock.acquire(blocking=False):
            return "u_toku", 0
        try:
            with cuvar.making("the day's mail to all"):
                return self._to_all(day)
        finally:
            self._lock.release()

    def _to_all(self, day: date) -> tuple[str, int]:
        state = self._state(day)
        done = list(state.get("poslati") or [])
        if state.get("zavrseno"):
            return "vec", len(done)
        first = self.build(day, False, "")
        if first is None:
            return "prazno", 0
        if mejl.mixed_words(first.text):
            return "dvopis", 0
        if datetime.now(TZ) > deadline(day):
            return "kasno", len(done)
        try:
            people = _call("/m/spisak").get("primaoci", [])
        except Exception as exc:  # nothing begun: the same click later
            log.warning("mejl %s: spisak nije stigao (%s)", day, exc)
            return "brojac", len(done)
        unsure = list(state.get("nesigurni") or [])
        refused = list(state.get("odbijeni") or [])
        settled = {*done, *unsure, *refused}
        waiting, seen = [], set()
        for p in sorted(people, key=lambda p: p["id"] not in settled):  # those settled first
            try:
                to = unseal(config.MAIL_KEY, p["adresa"])
            except Exception:  # noqa: BLE001 — sealed for another key: never sent, never shown
                continue
            if to.lower() in seen:
                continue
            seen.add(to.lower())
            if p["id"] not in settled:
                waiting.append((p, to))
        state.setdefault("svima", datetime.now(TZ).isoformat())
        earlier = [g for g in state.get("greske") or [] if g.get("id") in refused]
        failed: list[dict] = []
        broken = False
        for i in range(0, len(waiting), BATCH):
            batch = waiting[i:i + BATCH]
            ids = [p["id"] for p, _ in batch]
            messages = []
            for p, to in batch:
                m = self.build(day, bool(p.get("cir")), p["odjava"]) or first
                messages.append({"to": to, "subject": m.subject, "html": m.html, "text": m.text, "odjava": p["odjava"]})
            state.update(poslati=done, nesigurni=unsure + ids)
            self._keep(day, state)  # before the call: whatever happens to it, these are not sent a second time
            try:
                _, wrong = send(messages)
            except Exception as exc:
                broken = True
                if not _not_sent(exc):
                    unsure += ids
                log.warning("mejl %s: prekid (%s)", day, exc)
                break
            bad = {w.get("i") for w in wrong}
            failed += [{"id": ids[w["i"]], "code": str(w.get("code", ""))} for w in wrong if w.get("i") in range(len(ids))]
            done += [x for j, x in enumerate(ids) if j not in bad]
        # The same code is Cloudflare's answer when it is the sender's own address that is refused, and then it is
        # everybody's: a refusal is the reader's only while more have the day's mail than are refused it.
        now = [f["id"] for f in failed if f["code"] in REFUSED]
        if len(done) > len(refused) + len(now):
            refused += now
        passing = [f for f in failed if f["id"] not in refused]
        state.update(poslati=done, nesigurni=unsure, odbijeni=refused, greske=earlier + failed)
        if not broken and not passing:
            state["zavrseno"] = datetime.now(TZ).isoformat()
        self._keep(day, state)
        log.info("mejl %s: svima %d, nije proslo %d, odbijeno %d, nesigurno %d", day, len(done), len(passing), len(refused), len(unsure))
        if broken or passing:
            return "deo", len(done)
        return ("nesigurno" if unsure else "odbijeni" if refused else "ok"), len(done)


MAIL_EVERY = 300  # seconds between tries of the day's mail to the maintainer


class Watch(threading.Thread):
    """The day's mail to the maintainer, with the link that sends it to all, once the day's summary is kept: asked again
    every few minutes, so that one that did not go is tried again (Mailer.ready knows what went). By the kept files
    alone (25 Nov 2026; until then in the model's loop): whoever serves the page sends the mail, and a restart of the
    measuring does not hold it back."""

    def __init__(self, tracker, mailer: Mailer, stop: threading.Event) -> None:
        super().__init__(daemon=True)
        self.tracker, self.mailer, self.halt = tracker, mailer, stop

    def step(self, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        day = str(self.tracker.snapshot(now=now).get("dan") or "")
        if not day or not to_tell(self.tracker.summary_of(day).get("dan"), now, TZ):
            return False
        with cuvar.making("the mail to the maintainer"):
            return self.mailer.ready(date.fromisoformat(day))

    def run(self) -> None:
        while not self.halt.is_set():
            try:
                self.step()
            except Exception:
                log.exception("the day's mail not tried")
            self.halt.wait(MAIL_EVERY)


WEAK = "<p><b>Pažnja:</b> sažetak je napisao slabiji model iz sažetaka delova. Proveri rečenice po govorniku.</p>"
UNREAD = "<p><b>Pažnja:</b> fajl sa ispravkama ranijeg mejla ne može ceo da se pročita. Mejl ide bez onoga što se ne čita.</p>"
HINT_AFTER = 300  # seconds after a measure with no name in which the chair's words may say whose it was


def hints(measures: list, said: dict, roll: mere.Roll, day: date) -> str:
    """For the maintainer's mail only (25 Nov 2026: on 24 Nov the chair named whom he had warned three minutes later,
    "imam potrebu da objasnim koleginici Kuburović, bila su dva upozorenja pre opomene", and no rule took it): under
    each measure with no name, the chair's pieces of the next five minutes that name a sitting MP and speak of a
    warning, word for word. Nothing is named by it: the maintainer reads and decides."""
    rows = []
    for m in measures:
        if m.kome:
            continue
        h, mi = m.vreme.split(":")
        t0 = datetime(day.year, day.month, day.day, int(h), int(mi), tzinfo=TZ).timestamp()
        for k in sorted((k for k in said if k[:1] == "p" and k[1:].isdigit()), key=lambda k: int(k[1:])):
            text = str(said[k])
            if t0 + 60 <= int(k[1:]) <= t0 + 60 + HINT_AFTER and re.search(r"opomen|upozoren", text, re.I):
                who = roll.find(text)
                if who:
                    at = datetime.fromtimestamp(int(k[1:]), TZ).strftime("%H:%M")
                    rows.append(f"<li><b>{escape(m.vreme)} {escape(m.mera)}, bez imena.</b> Predsedavajući u {at} pominje "
                                f"{escape(', '.join(p.name for p in who))}: „{escape(text[:300])}“</li>")
    return ("<p>Mere bez imena posle kojih predsedavajući nekoga pominje (samo za tebe; ništa nije upisano):</p><ul>"
            + "".join(rows) + "</ul>") if rows else ""


def _with_top(html: str, top: str) -> str:
    """The maintainer's note above the mail: right after <body …>."""
    i = html.find(">", html.find("<body"))
    return html[:i + 1] + top + html[i + 1:] if i > 0 else top + html


def roll_of(facts: dict) -> mere.Roll:
    """The convocation's MPs as the site gives them to this service (mikrofon-poslanici.json: "ime", "lista", "stranka")."""
    return mere.Roll([mere.MP(f["ime"], slug, f.get("lista", ""), f.get("stranka", ""), str(f.get("foto") or "")) for slug, f in (facts or {}).items()
                      if isinstance(f, dict) and f.get("ime")])


def corrections(f: Path) -> tuple[list[tuple[date, str]], bool]:
    """The corrections a day's mail carries, put by hand in `/data/mejl/ispravke-<day>.json`: a list of {"dan": the day
    whose mail was wrong, "tekst": the words}, shown as written. And whether all of the file was read: an entry that
    cannot be is left out, and the maintainer's mail says so (`day_mail`)."""
    if not f.exists():
        return [], True
    try:
        kept = json.loads(f.read_text(encoding="utf-8-sig"))  # a file written on Windows may begin with a mark
    except (OSError, ValueError):
        kept = None
    if not isinstance(kept, list):
        return [], False
    out = []
    for x in kept:
        try:
            if x["tekst"].strip():
                out.append((date.fromisoformat(x["dan"]), x["tekst"].strip()))
        except (AttributeError, KeyError, TypeError, ValueError):
            continue
    return out, len(out) == len(kept)


def day_mail(tracker):
    """The day's mail from what this service keeps: the day's summary and its stretches (/data/sazetak), the day's
    lines (/data/hronika), the MPs (the site's facts) and, for today, each MP's time at the rostrum."""
    base = Path(config.STATE_PATH).parent

    def build(day: date, cyr: bool, out: str):
        kept = tracker.summary_of(day.isoformat()) or {}
        if not isinstance(kept.get("dan"), dict):
            return None
        f = base / "hronika" / f"{day.isoformat()}.json"
        lines = json.loads(f.read_text(encoding="utf-8")) if f.exists() else []
        roll = roll_of(getattr(tracker, "facts", {}))
        spoke: dict[str, int] = {}
        snap = tracker.snapshot()
        if snap.get("dan") == day.isoformat():
            for t in snap.get("danas") or []:
                mp = roll.one(t.get("ime", ""))
                name = mp.name if mp else t.get("ime", "")
                spoke[name] = spoke.get(name, 0) + int(t.get("sekundi") or 0)
        measures = mere.measures(lines, kept.get("delovi") or [], roll, TZ)
        q = base / "mejl" / f"recenice-{day.isoformat()}.json"  # the maintainer's own, added by hand before the click
        try:
            quotes = json.loads(q.read_text(encoding="utf-8")) if q.exists() else []
        except ValueError:
            log.warning("mejl %s: recenice se ne citaju, mejl ide bez njih", day)
            quotes = []
        fixes, whole = corrections(base / "mejl" / f"ispravke-{day.isoformat()}.json")
        if not whole:
            log.warning("mejl %s: ispravke se ne citaju cele", day)
        other = f"{(config.PUBLIC_URL or 'https://mikrofon.zailiprotiv.rs').rstrip('/')}/{'' if cyr else 'cir/'}"
        return mejl.build(day, kept["dan"], measures, roll, spoke, cyr=cyr, unsubscribe=out, other_script=other,
                          quotes=quotes if isinstance(quotes, list) else [], corrections=fixes)

    def whom(day: date) -> str:
        kept = tracker.summary_of(day.isoformat()) or {}
        f, p = base / "hronika" / f"{day.isoformat()}.json", base / "prepis" / f"{day.isoformat()}.json"
        try:
            lines = json.loads(f.read_text(encoding="utf-8")) if f.exists() else []
            said = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        except ValueError:
            return ""
        roll = roll_of(getattr(tracker, "facts", {}))
        return hints(mere.measures(lines, kept.get("delovi") or [], roll, TZ), said, roll, day)

    def hint(day: date) -> str:
        whole = corrections(base / "mejl" / f"ispravke-{day.isoformat()}.json")[1]
        return ("" if whole else UNREAD) + whom(day)
    build.hints = hint
    return build


def sample(build, day: date, cyr: bool) -> str:
    """A day's mail as a page, with what it is said on top ("" when there is none, or it may go to nobody)."""
    from .names import cyrillic
    from .texts import TEXT
    m = build(day, cyr, "")
    if m is None or mejl.mixed_words(m.text):
        return ""
    t = (lambda k: escape(cyrillic(TEXT[k]))) if cyr else (lambda k: escape(TEXT[k]))
    home = "/cir/#mejl" if cyr else "/#mejl"
    top = (f'<div style="font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;font-size:14px;line-height:1.5;padding:12px 16px;'
           f'background:#111318;color:#ffffff;text-align:center">{t("ml_sample_top")} '
           f'<a href="{home}" style="color:#7cc0f5;font-weight:bold;white-space:nowrap">{t("ml_sample_back")} →</a></div>')
    return _with_top(m.html, top)


_PAGE = """<!doctype html><html lang="sr-Latn"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex"><title>Sažetak dana: slanje</title><style>body{{margin:0;background:#eef0f3;color:#111;
font:16px/1.55 system-ui,sans-serif}}main{{max-width:30rem;margin:12vh auto 0;background:#fff;border-top:4px solid #111;
border-radius:14px;padding:1.6rem 1.5rem}}h1{{font:700 1.5rem/1.2 Georgia,serif}}button{{font:inherit;font-weight:700;
background:#111;color:#fff;border:0;border-radius:999px;padding:.7rem 1.2rem;cursor:pointer}}</style></head><body><main>{body}</main></body></html>"""


def page_ask(day: str, code: str) -> str:
    """The maintainer's page before sending: the day and one button."""
    try:
        d = date.fromisoformat(day)
    except ValueError:
        return _PAGE.format(body="<h1>Link nije ispravan</h1>")
    when = f"{d.day}. {mejl.MONTHS_OF[d.month - 1]}"
    return _PAGE.format(body=f"<h1>Sažetak dana, {escape(when)}</h1><p>Mejl ide svima koji su potvrdili prijavu, jednom, "
                             f"do podneva sledećeg dana.</p><form method=\"post\"><input type=\"hidden\" name=\"dan\" "
                             f"value=\"{escape(day)}\"><input type=\"hidden\" name=\"k\" value=\"{escape(code[:64])}\">"
                             f"<button>Pošalji svima</button></form>")


def page_done(what: str, n: int) -> str:
    text = {"ok": f"Poslato: {n}.", "vec": f"Već je poslato ({n}); drugi put se ne šalje.",
            "deo": f"Poslato do sada: {n}. Nije završeno: otvori link iz mejla i klikni ponovo, nastavlja gde je stalo.",
            "nesigurno": f"Poslato: {n}. Za deo čitalaca veza je pukla usred slanja, pa se ne zna da li im je stiglo; "
                         "njima se ne šalje drugi put.",
            "odbijeni": f"Poslato: {n}. Ima adresa koje Cloudflare odbija (koliko, piše u dnevniku servisa); za ovaj dan im se "
                        "ne pokušava ponovo.",
            "u_toku": "Slanje je već u toku.", "brojac": "Brojač ne odgovara, ništa nije poslato: probaj ponovo za koji minut.",
            "prazno": "Sažetak tog dana još ne postoji.",
            "kasno": "Prošlo je podne: taj dan se više ne šalje.", "dvopis": "Sažetak ima reč u dva pisma: ne šalje se.",
            "kod": "Link nije ispravan."}.get(what, "Nije poslato.")
    return _PAGE.format(body=f"<h1>Sažetak dana</h1><p>{escape(text)}</p>")
