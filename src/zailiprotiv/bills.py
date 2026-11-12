"""A bill's explanatory memorandum (образложење), read from the bill's PDF.

After the law's text, a bill carries its memorandum in numbered sections, in Cyrillic or Latin:
"I Уставни основ", "II Разлози за доношење", "III Објашњење основних правних института", "IV Процена/Оцена
финансијских средстава", "V Анализа ефеката" (a treaty's bill has the same headings with "потврђивање"). The
constitutional basis names the article and point the proposer relies on: Article 97 lists the areas the Republic
regulates, one per point; Article 99, paragraph 1, point 4 is the Assembly's power to ratify treaties.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path

from zailiprotiv.translit import latin

# Section headings by their key word (in Latin, lowercased, after transliteration).
SECTIONS = (("ustavni osnov", "basis"), ("hitn", "urgency"), ("razlo", "reasons"), ("objasnjenj", "explained"), ("objašnjenj", "explained"),
            ("finansijsk", "funds"), ("sredstav", "funds"), ("analiz", "effects"))
_ROMAN = r"(?:I|II|III|IV|V|VI|VII|VIII|IX|X|XI|XII)"
_HEADING = re.compile(rf"^\s*({_ROMAN})\.?\s+(\S.*)$")


@dataclass
class Memorandum:
    sections: dict[str, str] = field(default_factory=dict)  # basis, reasons, urgency, explained, funds, effects
    articles: list[dict] = field(default_factory=list)  # [{"article": 97, "paragraph": None, "points": [6, 7]}]

    def as_dict(self) -> dict:
        return asdict(self)


def text_of(pdf: Path | str) -> str:
    return subprocess.run(["pdftotext", "-layout", str(pdf), "-"], check=True, capture_output=True,
                          text=True).stdout


def _kind(heading: str) -> str | None:
    h = latin(heading).lower()
    for word, kind in SECTIONS:
        if word in h:
            return kind
    return None


def memorandum(text: str) -> Memorandum:
    """The memorandum's sections, found from the first heading on the constitutional basis."""
    lines = text.splitlines()
    start = next((i for i, l in enumerate(lines)
                  if _HEADING.match(l) and _kind(_HEADING.match(l).group(2)) == "basis"), None)
    out = Memorandum()
    if start is None:
        return out
    current, buf = None, []

    def flush():
        if current and buf:
            body = re.sub(r"[ \t]+", " ", "\n".join(l.strip() for l in buf)).strip()
            out.sections[current] = (out.sections.get(current, "") + "\n" + body).strip()

    for line in lines[start:]:
        m = _HEADING.match(line)
        kind = _kind(m.group(2)) if m else None
        if kind:
            flush()
            current, buf = kind, [m.group(2).strip()]
        elif m and m.group(1) != "I":  # another section (overview of changed provisions, …): not kept.
            flush()  # "I" alone may be the word "и" starting a line, so it never ends a section.
            current, buf = None, []
        else:
            buf.append(line)
    flush()
    out.articles = articles(out.sections.get("basis", ""))
    return out


_ARTICLE = re.compile(r"(?:član|clan)\w*\s+(\d+)\.?((?:\s*(?:,|i|stav|tačk|tack)\w*\.?\s*\d+\.?)*)", re.I)


def articles(basis: str) -> list[dict]:
    """The Constitution's articles, paragraphs and points the basis cites: "члан 97. тачка 6. и 7." → 97, [6, 7]."""
    text = re.sub(r"\s+", " ", latin(basis))
    if "ustav" not in text.lower():
        return []
    out = []
    for m in _ARTICLE.finditer(text):
        rest = m.group(2) or ""
        paragraph = re.search(r"stav\w*\.?\s*(\d+)", rest, re.I)
        points_at = re.search(r"ta[čc]k\w*\.?\s*(.*)$", rest, re.I)
        points = [int(n) for n in re.findall(r"\d+", points_at.group(1))] if points_at else []
        out.append({"article": int(m.group(1)), "paragraph": int(paragraph.group(1)) if paragraph else None,
                    "points": points})
    return out


def read(pdf: Path | str) -> Memorandum:
    return memorandum(text_of(pdf))
