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

# The reader's version: a bill whose memorandum an older reader didn't find is read again by a newer one.
READER = 2

# Section headings by their key word (in Latin, lowercased, after transliteration).
SECTIONS = (("ustavni osnov", "basis"), ("hitn", "urgency"), ("razlo", "reasons"), ("objasnjenj", "explained"), ("objašnjenj", "explained"),
            ("finansijsk", "funds"), ("sredstav", "funds"), ("analiz", "effects"))
_ROMAN = r"(?:I|II|III|IV|V|VI|VII|VIII|IX|X|XI|XII)"
_HEADING = re.compile(rf"^\s*({_ROMAN}|\d{{1,2}})\.?\s+(\S.*)$")


def _heading(line: str):
    """A section heading: "II Разлози …" (Roman numeral), or "2. RAZLOZI ZA DONOŠENJE ZAKONA" (Arabic numeral,
    written in capitals: an Arabic-numbered line in small letters is a list item, not a heading)."""
    m = _HEADING.match(line)
    if not m:
        return None
    if m.group(1).isdigit():
        letters = [c for c in m.group(2) if c.isalpha()]
        if len(letters) < 8 or sum(c.isupper() for c in letters) / len(letters) < 0.8:
            return None
    return m


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
    start = next((i for i, l in enumerate(lines) if _heading(l) and _kind(_heading(l).group(2)) == "basis"), None)
    out = Memorandum()
    if start is None:
        return out
    current, buf = None, []

    def flush():
        if current and buf:
            body = re.sub(r"[ \t]+", " ", "\n".join(l.strip() for l in buf)).strip()
            out.sections[current] = (out.sections.get(current, "") + "\n" + body).strip()

    for line in lines[start:]:
        m = _heading(line)
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


_ARTICLE = re.compile(r"\b(?:član|clan)\w*\s+(\d+)\.?", re.I)
_PARAGRAPH = re.compile(r"^\s*,?\s*(?:stav|st)\w*\.?\s*(\d+)", re.I)
_POINTS = re.compile(r"(?:ta[čc]k\w*|ta[čc])\.?\s*((?:\d+\)?\.?(?:\s*(?:,|i|и)\s*)?)+)", re.I)


def articles(basis: str) -> list[dict]:
    """The Constitution's articles, paragraphs and points the basis cites. Bills write them in many ways:
    "члан 97. тачка 6. и 7.", "člana 97. tač. 6, 7, 12. i 17.", "članu 97. Ustava …, u tački 2.", and for
    Article 97, whose points stand in one paragraph, "članu 97. stav 10." meaning point 10."""
    text = re.sub(r"\s+", " ", latin(basis))
    if "ustav" not in text.lower():
        return []
    out = []
    found = list(_ARTICLE.finditer(text))
    for i, m in enumerate(found):
        article = int(m.group(1))
        stop = found[i + 1].start() if i + 1 < len(found) else len(text)
        after = text[m.end():stop]
        near = after[:40]
        paragraph = _PARAGRAPH.match(near)
        points_at = _POINTS.search(after[:60] if not article == 97 else after[:250])
        points = [int(n) for n in re.findall(r"\d+", points_at.group(1))] if points_at else []
        par = int(paragraph.group(1)) if paragraph else None
        if article == 97 and not points and par and par > 1:  # "član 97. stav 10." is its point 10
            points, par = [par], None
        out.append({"article": article, "paragraph": par, "points": points})
    return out


def read(pdf: Path | str) -> Memorandum:
    return memorandum(text_of(pdf))
