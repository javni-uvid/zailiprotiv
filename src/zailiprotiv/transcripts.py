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
import subprocess
import tempfile
from pathlib import Path
import zipfile
from collections import Counter
from html import unescape

from zailiprotiv import skupstina

PATH = "/stenografske_beleske/"
# … and until 2016 under a folder with a misspelt name ("stenobeske"), as .doc or .docx, one link per day.
PATHS = (PATH, "/stenobeske/")
CHAIR = {"ПРЕДСЕДНИК", "ПРЕДСЕДНИЦА", "ПРЕДСЕДАВАЈУЋИ", "ПРЕДСЕДАВАЈУЋА", "ПРЕДСЕДАВАЈУЋ"}
CAPS = "А-ЯЂЈЉЊЋЏШЖЧ"
# "МИЛЕНКО ЈОВАНОВ: …", "Др УГЉЕША МРДИЋ: …", "ИЛИЋ-СТОШИЋ БИЉАНА: …"; at most six words before the colon.
SPEAKER = re.compile(rf"^((?:(?:[Дд]р|[Пп]роф|[Мм]р|[Дд]оц|[Пп]рим)\.?\s+)*[{CAPS}][{CAPS}\-]+(?:\s+[{CAPS}][{CAPS}\-.]*){{0,5}}):\s*(.*)$")
DAY = re.compile(r"(\d+)\.\s*дан")


def days(html: str, base: str) -> list[dict]:
    """The sitting page's stenographic notes, in page order: day number, link text, address."""
    out, seen = [], set()
    for url, text in skupstina.links(html, base):
        if any(p in url for p in PATHS) and url not in seen:
            seen.add(url)
            m = DAY.search(text)
            out.append({"day": int(m.group(1)) if m else len(out) + 1, "title": text, "url": url,
                        "listed_date": iso_date(text) or iso_date(url.rsplit("/", 1)[-1])})
    return out


MONTHS = {m: i for i, m in enumerate(("jan", "feb", "mar", "apr", "maj", "jun", "jul", "avg", "sep", "okt", "nov",
                                     "dec"), 1)}
MONTHS_CYR = {m: i for i, m in enumerate(("јан", "феб", "мар", "апр", "мај", "јун", "јул", "авг", "сеп", "окт", "нов",
                                         "дец"), 1)}


def iso_date(text: str) -> str:
    """A day named in a file name, a link or the notes' heading: "04.11.2025", "5. novembra 2025", "18. јун 2026",
    "04 новембар 2025" → "2025-11-04"; "" if none."""
    import urllib.parse
    t = urllib.parse.unquote(text).lower()
    if m := re.search(r"(\d{1,2})\.\s*(\d{1,2})\.\s*(20\d\d)", t):
        d, mo, y = map(int, m.groups())
    elif m := re.search(r"(\d{1,2})\.?\s+([a-zа-яђјљњћџ]{3})[a-zа-яђјљњћџčćšžđ]*\s+(20\d\d)", t):
        mo = MONTHS.get(m.group(2)) or MONTHS_CYR.get(m.group(2))
        if not mo:
            return ""
        d, y = int(m.group(1)), int(m.group(3))
    else:
        return ""
    return f"{y:04d}-{mo:02d}-{d:02d}" if 1 <= mo <= 12 and 1 <= d <= 31 else ""


class Unreadable(ValueError):
    """A day's notes that are neither a Word file nor one LibreOffice can turn into one."""


def to_docx(body: bytes) -> bytes:
    """The older notes are in Word's old format (.doc), or RTF: turned into .docx with LibreOffice."""
    kind = "doc" if body.startswith(b"\xd0\xcf\x11\xe0") else "rtf" if body.lstrip().startswith(b"{\\rtf") else ""
    if not kind:
        raise Unreadable(f"not a Word file: {body[:80]!r}")
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / f"notes.{kind}").write_bytes(body)
        run = subprocess.run(["soffice", "--headless", "--norestore", f"-env:UserInstallation=file://{tmp}/profile",
                              "--convert-to", "docx:MS Word 2007 XML", "--outdir", tmp, f"{tmp}/notes.{kind}"],
                             capture_output=True, text=True, timeout=300)
        out = Path(tmp) / "notes.docx"
        if run.returncode or not out.exists():
            raise Unreadable(f"LibreOffice could not convert the {kind} ({run.returncode}): {(run.stderr or run.stdout)[-400:]}")
        return out.read_bytes()


LATIN_CAPS = re.compile(r"^((?:(?:Dr|Prof|Mr|Doc|Prim)\.?\s+)*[A-ZČĆŽŠĐ][A-ZČĆŽŠĐ\-]+(?:\s+[A-ZČĆŽŠĐ][A-ZČĆŽŠĐ\-.]*){0,5}):")


def to_cyrillic(text: str) -> str:
    """Notes typed in Latin script, read as Cyrillic so the same patterns find speakers and the chair's words."""
    pairs = [("Lj", "Љ"), ("LJ", "Љ"), ("lj", "љ"), ("Nj", "Њ"), ("NJ", "Њ"), ("nj", "њ"), ("Dž", "Џ"), ("DŽ", "Џ"),
             ("dž", "џ")]
    for a, b in pairs:
        text = text.replace(a, b)
    table = str.maketrans("ABVGDĐEŽZIJKLMNOPRSTĆUFHCČŠabvgdđežzijklmnoprstćufhcčš",
                          "АБВГДЂЕЖЗИЈКЛМНОПРСТЋУФХЦЧШабвгдђежзијклмнопрстћуфхцчш")
    return text.translate(table)


def pdf_paragraphs(pdf: bytes) -> list[str]:
    """The older notes (2016–2017) are PDFs: lines from pdftotext, joined into paragraphs. A paragraph ends at an
    empty line, and a new one starts at a speaker's name, an agenda item or the agenda's heading."""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "n.pdf").write_bytes(pdf)
        run = subprocess.run(["pdftotext", "-enc", "UTF-8", f"{tmp}/n.pdf", "-"], capture_output=True, timeout=300)
        if run.returncode:
            raise Unreadable(f"pdftotext failed: {run.stderr[-300:]!r}")
        text = run.stdout.decode("utf-8", "replace")
    cyr = sum(1 for c in text if "\u0400" <= c <= "\u04ff")
    lat = sum(1 for c in text if c.isascii() and c.isalpha())
    if lat > cyr:
        text = to_cyrillic(text)
    out, cur = [], []

    def flush():
        if cur:
            joined = re.sub(r"(\w)-\s+(\w)", r"\1\2", " ".join(cur))
            out.append(re.sub(r"\s+", " ", joined).strip())
            cur.clear()
    for line in text.replace("\f", "\n").splitlines():
        line = line.strip()
        if not line:
            flush()
            continue
        if re.fullmatch(r"\d{1,4}", line) or MARK.match(line):
            continue
        if SPEAKER.match(line) or AGENDA_HEAD.search(line) or (cur and AGENDA_ITEM.match(line)):
            flush()
        cur.append(line)
    flush()
    return [p for p in out if p]


def paragraphs(docx: bytes) -> list[str]:
    """The Word file's paragraphs as plain text, empty ones left out. The older notes are in Word's old format
    (.doc), turned into the new one with LibreOffice first."""
    if docx.startswith(b"%PDF"):
        return pdf_paragraphs(docx)
    if not docx.startswith(b"PK"):
        docx = to_docx(docx)
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


# An agenda item, numbered by hand ("1. Предлог закона …;") or by Word's list numbering, which leaves no number in
# the text ("Предлог закона …,").
AGENDA_ITEM = re.compile(r"^(?:(\d+)[.,]\s*(.+?)|((?:Предлог|Предлози|Избор|Избори|Извештај|Разматрање|Утврђивање|"
                         r"Давање|Именовање|Аутентичн|Одлука|Престанак|Потврђивање|Листа|Редовн|Годишњ)\w*\s.*?))[;,.]?$")
# The stenographers' page marks ("1/2МТ/ ВЗ") between paragraphs.
MARK = re.compile(r"^\d+/\d+\s*[А-ЯЂЈЉЊЋЏШЖЧA-Z]{1,3}/\s*[А-ЯЂЈЉЊЋЏШЖЧA-Z/ ]{0,8}$")
AGENDA_HEAD = re.compile(r"Д\s*н\s*е\s*в\s*н\s*и\s+р\s*е\s*д\s*:?\s*$")
RANGE = r"тач\w*\s+(?:од\s+)?(\d+)\.?\s*(?:до|-|–)\s*(\d+)"
JOINT = re.compile(r"(?:отварам|настављамо)\s+(?:сада\s+)?заједнички\W+(?:\w+\W+){0,4}?претрес", re.I)
DETAIL = re.compile(r"(?:отварам\s+|настављамо\s+|прелазимо\s+на\s+|^)(?:сада\s+)?претрес\w*\W+(?:\w+\W+){0,3}?[уо]\s+појединостима", re.I)
GENERAL = re.compile(r"(?:отварам|настављамо)\s+(?:сада\s+)?(?:начелни\s+(?:и\s+јединствени\s+)?)?претрес\w*(?!\W+(?:\w+\W+){0,3}?[уо]\s+појединостима)", re.I)
CLOSE_JOINT = re.compile(r"закључујем\s+заједнички\W+(?:\w+\W+){0,4}?претрес", re.I)
QUESTIONS = re.compile(r"члан\w*\s+287|сат\w*\s+(?:времена\s+)?(?:постављања\s+питања|тражења)", re.I)
RESUME = re.compile(r"настављамо|листи\b|листу\b|листом\b", re.I)
MOVE = re.compile(r"Прелазимо\s+(?:сада\s+)?на\s+(?:(\d+)\.?\s*тачк\w*|следећу\s+тачк\w*|(\w+)\s+тачк\w*|(Предлог\w*\s.+))", re.I)
NTH = re.compile(r"(?:о|по)\s+(?:тачки\s+(\d+)\.|(\d+)\.\s*тачк|(\w+ој)\s+тачк)", re.I)
VOTING = re.compile(r"Прелазимо\s+(?:сада\s+)?на\s+(?:одлучивање|гласање)|дан\s+за\s+гласање\s+(?:је|почиње)", re.I)
ORDINAL = {w: i for i, w in enumerate("прв друг трећ четврт пет шест седм осм девет десет".split(), 1)}
# "На члан 3. амандман је поднео …", "… амандман су заједно поднели …", "… амандмане, у истоветном тексту, поднели су …"
AMENDMENT = re.compile(r"На\s+члан\s+(\d+)\.?\s+амандман\w*[^.]{0,40}?подне[ол]\w*\s+(?:су\s+|је\s+)?(?:заједно\s+)?(.+?)\.?\s*$")


def ordinal(word: str) -> int | None:
    """"трећу", "Првој", "Пету" → 3, 1, 5 (up to ten)."""
    w = word.lower()
    for stem in sorted(ORDINAL, key=len, reverse=True):
        if w.startswith(stem) and len(w) - len(stem) <= 3 and not w.startswith(("петна", "шестна", "седамн")):
            return ORDINAL[stem]
    return None


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


def _item(line: str, agenda: dict[int, str], state: dict) -> list[int]:
    """The agenda items a chair's line names: "тачака 1. до 8.", "8. тачку", "Првој тачки", "следећу тачку", or a
    bill's title."""
    if r := re.search(RANGE, line, re.I):
        return list(range(int(r.group(1)), int(r.group(2)) + 1))
    m = MOVE.search(line)
    if m and m.group(1):
        return [int(m.group(1))]
    if m and m.group(2) and (n := ordinal(m.group(2))):
        return [n]
    if m and re.search(r"следећу\s+тачк", m.group(0), re.I):
        title = re.split(r"\s+[–-]\s+", line, maxsplit=1)
        if len(title) == 2 and (n := item_of(title[1], agenda)):
            return [n]
        return [state["items"][-1] + 1] if state["items"] else []
    if n := NTH.search(line):
        if n.group(1) or n.group(2):
            return [int(n.group(1) or n.group(2))]
        return [k] if (k := ordinal(n.group(3))) else []
    if m and m.group(3) and (n := item_of(m.group(3), agenda)):
        return [n]
    t = re.split(r"појединостима\s*(?:о\s+|[–-]\s*)", line, maxsplit=1)
    if len(t) == 2 and (n := item_of(t[1], agenda)):
        return [n]
    return []


def _move(line: str, agenda: dict[int, str], state: dict, debated: set[int], detailed: set[int]) -> dict | None:
    """Where the chair's line takes the debate, or None if it doesn't move it. An item whose principle was debated
    together with others goes straight to its amendments when the chair moves to it."""
    if VOTING.search(line):
        return {"part": "other", "items": []}
    items = _item(line, agenda, state)
    if JOINT.search(line):
        return {"part": "general", "items": items if len(items) > 1 else state.get("joint") or sorted(agenda)}
    if DETAIL.search(line):
        rest = sorted(debated - detailed)
        return {"part": "detail", "items": items or (rest[:1] if state["part"] != "detail" else state["items"][-1:])}
    if MOVE.search(line) and items:
        return {"part": "detail" if set(items) <= debated else "general", "items": items}
    if GENERAL.search(line):
        if not items and (t := re.search(r"претрес\w*\s+о\s+(Предлог\w*\s+.+)", line)):
            # A sitting with a single bill names it instead of a number; an agenda read without its list gets it.
            items = [n] if (n := item_of(t.group(1), agenda)) else []
            if not items and not agenda:
                agenda[1] = re.sub(r"^Предлог\w*", "Предлог", t.group(1)).rstrip(".")
                items = [1]
        if not items and not state["items"] and len(agenda) == 1:
            items = list(agenda)
        if items or state["items"]:
            return {"part": "general", "items": items or state["items"]}
    return None


def debate(days_: list[list[str]]) -> dict:
    """A sitting's notes, day by day (each a list of paragraphs), read in order: the agenda, and each speech with the
    part of the debate it was given in, "general" (in principle, possibly on several items together) or "detail"
    (on the articles and amendments of one bill), with the agenda items it concerns; "other" is everything else
    (MPs' questions, the agenda, voting). The chair's words move the debate on; the hour of MPs' questions (Article
    287 of the Rules) pauses it, and it resumes where it was. Amendments the chair announces are kept with their
    article and who filed them."""
    agenda: dict[int, str] = {}
    state: dict = {"part": "other", "items": [], "joint": []}
    paused: dict | None = None
    debated: set[int] = set()
    detailed: set[int] = set()
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
            if not current["chair"] or MARK.match(line):
                continue
            if AGENDA_HEAD.search(line) or "утврдила дневни ред" in line:
                in_agenda = True
                continue
            if in_agenda and (a := AGENDA_ITEM.match(line)):
                n = int(a.group(1)) if a.group(1) else max(agenda, default=0) + 1
                agenda[n] = (a.group(2) or a.group(3)).strip()
                continue
            if agenda:
                in_agenda = False
            if (am := AMENDMENT.search(line)) and state["part"] == "detail":
                amendments.append({"day": day, "item": state["items"][0] if state["items"] else None,
                                   "article": int(am.group(1)), "by": am.group(2).strip()})
            if c := CLOSE_JOINT.search(line):
                items = _item(line, agenda, state) or state.get("joint") or sorted(agenda)
                # The notes may miss the opening ("настављамо заједнички претрес" with no items named): the general
                # speeches with no item belong to the debate it closes.
                for sp in out:
                    if sp["part"] == "general" and not sp["items"]:
                        sp["items"] = list(items)
                debated |= set(items)
                state = {"part": "other", "items": [], "joint": items}
                continue
            if QUESTIONS.search(line) and state["part"] != "other":
                paused, state = state, {"part": "other", "items": [], "joint": state.get("joint", [])}
                current["part"], current["items"] = "other", []
                continue
            if paused and RESUME.search(line) and not MOVE.search(line):
                state, paused = paused, None
                current["part"], current["items"] = state["part"], list(state["items"])
            new = _move(line, agenda, state, debated, detailed)
            if new:
                paused = None
                if new["part"] == "general":
                    debated |= set(new["items"])
                if new["part"] == "detail":
                    detailed |= set(new["items"])
                state = {**new, "joint": new["items"] if len(new["items"]) > 1 else state.get("joint", [])}
                # A chair's speech that opens a part belongs to it, so the speeches after it do too.
                current["part"], current["items"] = state["part"], list(state["items"])
    return {"agenda": agenda, "speeches": out, "amendments": amendments}


def heading(paras: list[str]) -> dict:
    """The notes' date ("04. новембар 2025. године") and whether they say they are provisional."""
    head = " ".join(paras[:20])
    m = re.search(r"(\d{1,2})\.\s*([а-я]+|\d{1,2}\.)\s*(\d{4})\.\s*године", head)
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
