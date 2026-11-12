"""The laws a convocation passed, from the Assembly's page of adopted laws ("Донети закони").

Each row of that page's table gives the law's title and PDF, the bill it came from (title, PDF, the day it was
submitted), the day the law was passed and its issue of the Official Gazette, marked "(MU)" when it was published
among international treaties. The bill's PDF carries the proposer's explanatory memorandum.
"""

from __future__ import annotations

import re
import urllib.parse
from dataclasses import asdict, dataclass

from zailiprotiv.config import BASE
from zailiprotiv.skupstina import links
from zailiprotiv.translit import latin

ADOPTED = BASE + "/akti/doneti-zakoni/doneti-zakoni.1033.html"

MONTHS = {"januar": 1, "februar": 2, "mart": 3, "april": 4, "maj": 5, "jun": 6, "jul": 7, "avgust": 8,
          "septembar": 9, "oktobar": 10, "novembar": 11, "decembar": 12}
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
