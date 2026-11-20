"""The laws a convocation passed, from the Assembly's page of adopted laws ("Донети закони").

Each row of that page's table gives the law's title and PDF, the bill it came from (title, PDF, the day it was
submitted), the day the law was passed and its issue of the Official Gazette, marked "(MU)" when it was published
among international treaties. The bill's PDF carries the proposer's explanatory memorandum.
"""

from __future__ import annotations

import re
import urllib.parse
from dataclasses import asdict, dataclass

from zailiprotiv import months
from zailiprotiv.config import BASE
from zailiprotiv.skupstina import links
from zailiprotiv.translit import latin

ADOPTED = BASE + "/akti/doneti-zakoni/doneti-zakoni.1033.html"

MONTHS = {m: i for i, m in enumerate(months.NAMES, 1)}
_DATE = re.compile(r"(\d{1,2})\.\s*([a-zšđčćž]+)\s+(\d{4})\.", re.I)


def date(text: str) -> str | None:
    m = _DATE.search(latin(text))
    if not m or m.group(2).lower() not in MONTHS:
        return None
    return f"{m.group(3)}-{MONTHS[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"


@dataclass
class Law:
    title: str
    passed: str | None  # ISO date
    gazette: str  # "7/26"
    treaty: bool  # published among international treaties, "(MU)"
    pdf: str
    bill_title: str
    bill_pdf: str
    submitted: str | None

    def as_dict(self) -> dict:
        return asdict(self)


def _text(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def parse(html: str, base: str = ADOPTED) -> list[Law]:
    out = []
    for row in re.findall(r"<tr\b.*?</tr>", html, flags=re.S | re.I):
        found = links(row, base)
        law = next(((u, t) for u, t in found if "/zakoni/" in urllib.parse.unquote(u) and t), None)
        if not law:
            continue
        bill = next(((u, t) for u, t in found if "/predlozi_zakona/" in urllib.parse.unquote(u)), ("", ""))
        cells = [_text(c) for c in re.findall(r"<td\b[^>]*>(.*?)</td>", row, flags=re.S | re.I)]
        submitted = re.search(r"\(([^()]*\d{4}\.)\s*\)", _text(row))
        gazette = next((c for c in cells[1:] if re.match(r"^\d+/\d+", c)), "")
        out.append(Law(
            title=law[1],
            passed=next((date(c) for c in cells[1:] if date(c)), None),
            gazette=re.match(r"^(\d+/\d+)", gazette).group(1) if gazette else "",
            treaty=bool(re.search(r"\((M|М)U\)", gazette)),
            pdf=law[0],
            bill_title=bill[1],
            bill_pdf=bill[0],
            submitted=date(submitted.group(1)) if submitted else None,
        ))
    return out


def carry(before: dict, now: dict) -> dict:
    """The laws just read (now, {pdf: law}) with what later steps added to the same law in the file before (before):
    its roll calls and final vote (link), kind, and its bill's file, constitutional basis and areas (bills), as long
    as its bill is the same. Those steps run again after this one; a run that stops between them (17 Nov 2026: the
    Eleventh lost every final vote when the reading of roll calls failed after `laws`) leaves the file as it was."""
    for pdf, law in now.items():
        old = before.get(pdf)
        if old and old.get("bill_pdf") == law.get("bill_pdf"):
            for field, value in old.items():
                law.setdefault(field, value)
    return now
