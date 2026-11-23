"""The day's summary to those who asked for it: first to the maintainer, to all on his click (22 Nov 2026, choice B).

The counter keeps the addresses sealed for the maintainer's key (`worker/mejl.js`); only this service, with
MEJL_KLJUC in live/.env, opens them, and only to send. When the day's summary is on the page (`obavesti.Bell`), the
mail of the day goes to MEJL_UREDNIK alone, with a link to send it to everyone; the link works until 8 the next
morning, and once. A mail with a word in two scripts (`mejl.mixed_words`) goes to the maintainer saying so, and to
nobody else.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import urllib.request
from datetime import date, datetime, timedelta
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

from . import config, mejl, mere

log = logging.getLogger("uzivo.pretplata")
COUNTER = "https://glasovi.zailiprotiv.rs"
BATCH = 20
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
    """A day's mail goes to all until 8 the morning after."""
    return datetime.combine(day + timedelta(days=1), datetime.min.time(), TZ).replace(hour=8)


def _call(path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(COUNTER + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"authorization": "Bearer " + config.PUSH_TOKEN, "content-type": "application/json",
                                          "user-agent": "zailiprotiv-uzivo"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def send(messages: list[dict]) -> tuple[int, list]:
    """Through the counter, BATCH at a time; how many went and what failed."""
    sent, failed = 0, []
    for i in range(0, len(messages), BATCH):
        got = _call("/m/salji", {"poruke": messages[i:i + BATCH]})
        sent += got.get("poslato", 0)
        failed += [{**f, "i": f.get("i", 0) + i} for f in got.get("greske", [])]
    return sent, failed


class Mailer:
    """The day's mail: once to the maintainer when the summary is ready, then to all on his link, once."""

    def __init__(self, folder: Path, build):
        self.folder = Path(folder)  # /data/mejl: what went, by day
        self.build = build          # day, cyr, unsubscribe link → mejl.Mail of that day, or None

    def _state(self, day: date) -> dict:
        f = self.folder / f"{day.isoformat()}.json"
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}

    def _keep(self, day: date, state: dict) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        (self.folder / f"{day.isoformat()}.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

    def ready(self, day: date) -> bool:
        """The day's summary is on the page: the maintainer gets the mail and the link, once a day."""
        if not (config.MAIL_KEY and config.MAIL_EDITOR and config.PUSH_TOKEN) or self._state(day).get("uredniku"):
            return False
        m = self.build(day, False, "")
        if m is None:
            return False
        slips = mejl.mixed_words(m.text)
        link = f"{config.PUBLIC_URL.rstrip('/')}/mejl/posalji?dan={day.isoformat()}&k={link_key(day)}"
        note = (f"<p><b>Ne može svima:</b> reč u dva pisma ({', '.join(slips)}). Ispravi sažetak dana, pa će stići novi.</p>"
                if slips else f'<p><a href="{link}"><b>Pošalji svima</b></a> (do 8 ujutru, jednom).</p>')
        top = f'<div style="font-family:sans-serif;padding:12px;background:#fbf0dc">{note}</div>'
        sent, failed = send([{"to": config.MAIL_EDITOR, "subject": "[za tebe] " + m.subject,
                              "html": _with_top(m.html, top),
                              "text": ("NE MOŽE SVIMA: " + ", ".join(slips) if slips else "Pošalji svima: " + link) + "\n\n" + m.text}])
        self._keep(day, {"uredniku": datetime.now(TZ).isoformat(), "greske": failed, "dvopis": slips})
        log.info("mejl %s: uredniku %s", day, "poslat" if sent else f"nije poslat {failed}")
        return bool(sent)

    def to_all(self, day: date, code: str) -> tuple[str, int]:
        """The maintainer's link: (what happened, how many went)."""
        if not hmac.compare_digest(code, link_key(day)):
            return "kod", 0
        state = self._state(day)
        if state.get("svima"):
            return "vec", state.get("poslato", 0)
        if state.get("dvopis"):
            return "dvopis", 0
        if datetime.now(TZ) > deadline(day):
            return "kasno", 0
        people = _call("/m/spisak").get("primaoci", [])
        messages, seen = [], set()
        for p in people:
            try:
                to = unseal(config.MAIL_KEY, p["adresa"])
            except Exception:  # noqa: BLE001 — sealed for another key: never sent, never shown
                continue
            if to.lower() in seen:
                continue
            seen.add(to.lower())
            m = self.build(day, bool(p.get("cir")), p["odjava"])
            if m:
                messages.append({"to": to, "subject": m.subject, "html": m.html, "text": m.text, "odjava": p["odjava"]})
        state.update(svima=datetime.now(TZ).isoformat())
        self._keep(day, state)  # before sending: a second click never sends twice
        sent, failed = send(messages)
        state.update(poslato=sent, greske=failed)
        self._keep(day, state)
        log.info("mejl %s: svima %d od %d", day, sent, len(messages))
        return "ok", sent


def _with_top(html: str, top: str) -> str:
    """The maintainer's note above the mail: right after <body …>."""
    i = html.find(">", html.find("<body"))
    return html[:i + 1] + top + html[i + 1:] if i > 0 else top + html


def roll_of(facts: dict) -> mere.Roll:
    """The convocation's MPs as the site gives them to this service (mikrofon-poslanici.json: "ime", "lista", "stranka")."""
    return mere.Roll([mere.MP(f["ime"], slug, f.get("lista", ""), f.get("stranka", "")) for slug, f in (facts or {}).items()
                      if isinstance(f, dict) and f.get("ime")])


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
        other = f"{(config.PUBLIC_URL or 'https://mikrofon.zailiprotiv.rs').rstrip('/')}/{'' if cyr else 'cir/'}"
        return mejl.build(day, kept["dan"], measures, roll, spoke, cyr=cyr, unsubscribe=out, other_script=other)
    return build


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
                             f"do 8 ujutru sledećeg dana.</p><form method=\"post\"><input type=\"hidden\" name=\"dan\" "
                             f"value=\"{escape(day)}\"><input type=\"hidden\" name=\"k\" value=\"{escape(code[:64])}\">"
                             f"<button>Pošalji svima</button></form>")


def page_done(what: str, n: int) -> str:
    text = {"ok": f"Poslato: {n}.", "vec": f"Već je poslato ({n}); drugi put se ne šalje.",
            "kasno": "Prošlo je 8 ujutru: taj dan se ne šalje.", "dvopis": "Sažetak ima reč u dva pisma: ne šalje se.",
            "kod": "Link nije ispravan."}.get(what, "Nije poslato.")
    return _PAGE.format(body=f"<h1>Sažetak dana</h1><p>{escape(text)}</p>")
