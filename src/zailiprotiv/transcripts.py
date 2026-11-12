"""The stenographic notes of a sitting: who spoke, and what they said.

A sitting's Cyrillic page lists, under "Повезана документа", one Word file per day of work
(`/upload/archive/files/cir/doc/stenografske_beleske/…docx`), "СТЕНОГРАФСКЕ БЕЛЕШКЕ - <sitting> - 2. дан (18. јун
2026.)". The files are provisional, unedited and unauthorised notes (the Assembly says so on their first page).
Each speech starts a paragraph with the speaker's name, or the chair's role, in capitals and a colon:
"МИЛЕНКО ЈОВАНОВ: Хвала." The chair's role is ПРЕДСЕДНИК or ПРЕДСЕДАВАЈУЋИ (-А, -Ћ when the notes cut it).
"""

from __future__ import annotations

import io
import re
import zipfile
from collections import Counter
from html import unescape

from zailiprotiv import skupstina

PATH = "/stenografske_beleske/"
CHAIR = {"ПРЕДСЕДНИК", "ПРЕДСЕДНИЦА", "ПРЕДСЕДАВАЈУЋИ", "ПРЕДСЕДАВАЈУЋА", "ПРЕДСЕДАВАЈУЋ"}
CAPS = "А-ЯЂЈЉЊЋЏШЖЧ"
# "МИЛЕНКО ЈОВАНОВ: …", "Др УГЉЕША МРДИЋ: …", "ИЛИЋ-СТОШИЋ БИЉАНА: …"; at most six words before the colon.
SPEAKER = re.compile(rf"^((?:(?:[Дд]р|[Пп]роф|[Мм]р|[Дд]оц|[Пп]рим)\.?\s+)*[{CAPS}][{CAPS}\-]+(?:\s+[{CAPS}][{CAPS}\-.]*){{0,5}}):\s*(.*)$")
DAY = re.compile(r"(\d+)\.\s*дан")


def days(html: str, base: str) -> list[dict]:
    """The sitting page's stenographic notes, in page order: day number, link text, address."""
    out, seen = [], set()
    for url, text in skupstina.links(html, base):
        if PATH in url and url not in seen:
            seen.add(url)
            m = DAY.search(text)
            out.append({"day": int(m.group(1)) if m else 1, "title": text, "url": url})
    return out


def paragraphs(docx: bytes) -> list[str]:
    """The Word file's paragraphs as plain text, empty ones left out."""
    xml = zipfile.ZipFile(io.BytesIO(docx)).read("word/document.xml").decode("utf-8")
    out = []
    for p in re.findall(r"<w:p[ >].*?</w:p>|<w:p/>", xml, flags=re.S):
        p = re.sub(r"<w:(tab|br)[^>]*/>", " ", p)
        text = unescape("".join(re.findall(r"<w:t(?: [^>]*)?>([^<]*)</w:t>", p)))
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            out.append(text)
    return out


def is_chair(name: str) -> bool:
    n = name.upper().rstrip(".")
    return n in CHAIR or (" " not in n and n.startswith("ПРЕДСЕД"))  # "ПРЕДСЕДСАВАЈУЋА": a typo in the notes


def speeches(paras: list[str]) -> list[dict]:
    """Each speech: who ("speaker" as written, "chair" for the chair's role) and its paragraphs' text. What comes
    before the first speech (the notes' heading) is left out."""
    out = []
    for p in paras:
        m = SPEAKER.match(p)
        if m:
            name = m.group(1).strip()
            out.append({"speaker": name, "chair": is_chair(name), "text": m.group(2)})
        elif out:
            out[-1]["text"] = f"{out[-1]['text']}\n{p}".strip()
    return out


AGENDA_ITEM = re.compile(r"^(\d+)\.\s+(Предлог\s.*?)[;.]?$")
JOINT = re.compile(r"(?:отварам|настављамо)\s+заједнички\s+начелни[^.]*?претрес[^.]*?тачака\s+(?:од\s+)?(\d+)\.?\s*до\s+(\d+)", re.I)
ITEM = re.compile(r"(?:Прелазимо|Настављамо)\s+(?:рад\s+)?(?:на|по|са)\s+(\d+)\.\s*тачк", re.I)
DETAIL = re.compile(r"претрес\w*\s+(?:Предлог\w*\s+закона\s+)?у\s+појединостима", re.I)
DETAIL_TITLE = re.compile(r"претрес\w*\s+у\s+појединостима\s*[–-]\s*(.+)", re.I)
GENERAL = re.compile(r"отварам\s+(?:начелни\s+)?претрес\w*\s+(?:о\s+)?(?:Предлог\w*\s+закона\s+)?у\s+начелу|отварам\s+начелни\s+претрес", re.I)
CLOSE = re.compile(r"закључујем\s+(?:заједнички\s+)?(?:начелни\s+)?(?:и\s+)?(?:јединствени\s+)?претрес", re.I)
AMENDMENT = re.compile(r"На\s+члан\s+(\d+)\.?\s+амандман\s+(?:је\s+поднео|је\s+поднела|су\s+заједно\s+поднели)\s+(.+?)\.?\s*$")


def _words(title: str) -> set[str]:
    t = re.sub(r"^предлог\w*\s+закона\s+", "", title.lower())
    return set(re.findall(r"\w{3,}", t.split(",")[0]))


def item_of(title: str, agenda: dict[int, str]) -> int | None:
    """The agenda number of the bill a chair names in capitals ("ПРЕДЛОГУ ЗАКОНА О ПОСЕБНИМ ПОСТУПЦИМА …")."""
    best, score = None, 0.0
    w = _words(title)
    for n, t in agenda.items():
        a = _words(t)
        s = len(w & a) / max(1, min(len(w), len(a)))
        if s > score:
            best, score = n, s
    return best if score >= 0.6 else None


def debate(days_: list[list[str]]) -> dict:
    """A sitting's notes, day by day (each a list of paragraphs), read in order: the agenda, and each speech with the
    part of the debate it was given in, "general" (in principle, possibly on several items together) or "detail"
    (on the articles and amendments of one bill), with the agenda items it concerns. Amendments the chair announces
    are kept with their article and who filed them."""
    agenda: dict[int, str] = {}
    state: dict = {"part": "other", "items": []}
    out, amendments, in_agenda = [], [], False
    for day, paras in enumerate(days_, 1):
        current = None
        for p in paras:
            m = SPEAKER.match(p)
            if m:
                name = m.group(1).strip()
                current = {"day": day, "speaker": name, "chair": is_chair(name), "part": state["part"],
                           "items": list(state["items"]), "text": m.group(2)}
                out.append(current)
                line = m.group(2)
            elif current is not None:
                current["text"] = f"{current['text']}\n{p}"
                line = p
            else:
                continue
            if not current["chair"]:
                continue
            # The chair's words move the debate on.
            if re.search(r"Д\s*н\s*е\s*в\s*н\s*и\s+р\s*е\s*д\s*$", line) or "утврдила дневни ред" in line:
                in_agenda = True
                continue
            a = AGENDA_ITEM.match(line)
            if in_agenda and a:
                agenda[int(a.group(1))] = a.group(2).strip()
                continue
            in_agenda = False if agenda else in_agenda
            new = None
            if j := JOINT.search(line):
                new = {"part": "general", "items": list(range(int(j.group(1)), int(j.group(2)) + 1))}
            elif t := DETAIL_TITLE.search(line):
                n = item_of(t.group(1), agenda)
                new = {"part": "detail", "items": [n] if n else []}
            elif i := ITEM.search(line):
                new = {"part": "general", "items": [int(i.group(1))]}
            elif DETAIL.search(line) and state["items"]:
                new = {"part": "detail", "items": state["items"][-1:]}
            elif GENERAL.search(line) and state["items"]:
                new = {"part": "general", "items": state["items"]}
            elif CLOSE.search(line):
                new = {"part": "other", "items": state["items"] if state["part"] == "detail" else []}
            if (am := AMENDMENT.search(line)) and state["part"] == "detail":
                amendments.append({"day": day, "item": state["items"][0] if state["items"] else None,
                                   "article": int(am.group(1)), "by": am.group(2).strip()})
            if new:
                state = new
                # A chair's speech that opens a part belongs to it, so the speeches after it do too.
                current["part"], current["items"] = state["part"], list(state["items"])
    return {"agenda": agenda, "speeches": out, "amendments": amendments}


def heading(paras: list[str]) -> dict:
    """The notes' date ("04. новембар 2025. године") and whether they say they are provisional."""
    head = " ".join(paras[:12])
    m = re.search(r"(\d{1,2})\.\s*([а-я]+)\s+(\d{4})\.\s*године", head)
    return {"date": " ".join(m.groups()) if m else "", "provisional": "ПРИВРЕМЕНЕ" in head.upper()}


def joint(speeches_: list[dict]) -> list[tuple[int, int]]:
    """The agenda items debated together, from the chair's words "отварам заједнички начелни јединствени претрес о
    предлозима закона из тачака од 1. до 8.": [(1, 8)]."""
    out = []
    for s in speeches_:
        if s["chair"]:
            for m in re.finditer(r"заједнички\s+начелни[^.]*?претрес[^.]*?тачака\s+од\s+(\d+)\.\s*до\s+(\d+)", s["text"]):
                out.append((int(m.group(1)), int(m.group(2))))
    return out


def words(text: str) -> int:
    return len(re.findall(r"\w+", text))


def tally(speeches_: list[dict]) -> Counter:
    """Words spoken by each speaker, the chair left out."""
    out: Counter = Counter()
    for s in speeches_:
        if not s["chair"]:
            out[s["speaker"]] += words(s["text"])
    return out
