"""Bills in procedure, from the Assembly's page "Zakoni u proceduri": title and PDF, the day submitted, the proposer.

The page lists what is waiting now; it keeps no history. So the store remembers when each bill was first and last
seen on it: a bill no longer listed was passed (it is then among the adopted laws, by its PDF), withdrawn, or lapsed
with the convocation, and the page says only that it is no longer listed.
"""
from __future__ import annotations

import re
import urllib.parse
from dataclasses import asdict, dataclass

from zailiprotiv.config import BASE
from zailiprotiv.laws import _text, date
from zailiprotiv.skupstina import links
from zailiprotiv.translit import latin

PAGE = BASE + "/akti/zakoni-u-proceduri/zakoni-u-proceduri.1037.html"


@dataclass
class Bill:
    title: str
    pdf: str
    submitted: str | None
    proposer: str

    def as_dict(self) -> dict:
        return asdict(self)


def parse(html: str, base: str = PAGE) -> list[Bill]:
    out, seen = [], set()
    for row in re.findall(r"<tr\b.*?</tr>", html, flags=re.S | re.I):
        bill = next(((u, t) for u, t in links(row, base) if "/predlozi_zakona/" in urllib.parse.unquote(u) and
                     t.strip().upper() not in ("PDF", "DOC", "")), None)
        if not bill or bill[0] in seen:
            continue
        seen.add(bill[0])
        cells = [_text(c) for c in re.findall(r"<td\b[^>]*>(.*?)</td>", row, flags=re.S | re.I)]
        when = next((date(c) for c in cells[1:] if date(c)), None)
        proposer = next((c for c in cells[1:] if c and not date(c) and c.upper() not in ("PDF", "DOC", "PDF DOC")), "")
        out.append(Bill(re.sub(r"\s+", " ", bill[1]).strip(), bill[0], when, proposer))
    return out


def proposer_kind(proposer: str) -> str:
    """Who proposed, in three kinds the page's own words tell apart: the Government, MPs, anyone else (the
    Ombudsman, the National Bank, citizens, a provincial assembly)."""
    p = latin(proposer).lower()
    if p.startswith("vlada"):
        return "vlada"
    if "poslani" in p:  # "narodni poslanici …", "Poslanička grupa …"
        return "poslanici"
    return "drugi"


def merge(store: dict, found: list[Bill], today: str) -> dict:
    """The store after today's reading: every bill ever seen, by its PDF, with the first and last day it was listed."""
    bills = dict(store.get("bills") or {})
    for b in found:
        old = bills.get(b.pdf, {})
        bills[b.pdf] = {**b.as_dict(), "first_seen": old.get("first_seen", today), "last_seen": today}
    return {"fetched": today, "source": PAGE, "bills": bills}
