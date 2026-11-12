"""Reading a roll-call PDF: which vote it records and how every MP listed in it voted.

The text comes from poppler's `pdftotext -layout`, which keeps each row on one line with its columns apart.
Three layouts are known:

- since autumn 2025 ("Извештај са резултатима гласања"): one vote per file; the session, the agenda item, the
  kind of vote with its date and time ("Гласање о предлогу акта у целини - 25.06.2026 / 11:17:12"), then sections
  ГЛАСАЛИ ЗА, ГЛАСАЛИ ПРОТИВ, УЗДРЖАНИ, НИСУ ГЛАСАЛИ, НИСУ ПРИСУТНИ, each numbered from 1, a row being
  "SURNAME Given  vote  club" (the absent have no vote word);
- 2024 ("листинзи", "НАРОДНА СКУПШТИНА РЕПУБЛИКЕ СРБИЈЕ / ВРЕМЕ ГЛАСАЊА 30.09.2024. / 17:53:17"): one file may hold
  several votes (items 1.1, 1.2, …), each starting on a page of its own; a row is "Given Surname (list)", and the
  absent aren't listed;
- 2025 listinzi: as 2024, with the list in a column of its own ("-" for none).

Every page repeats its header, so the rows of one vote may be spread over several pages; a vote is known by its
date and time and its agenda item. A file may also hold a second vote on the same item with only its date and time
before its sections (December 2025).
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

# Latin letters that look like Cyrillic ones and turn up in the Assembly's Cyrillic text ("Ниje гласао",
# "Гласање o предлогу", "Извештаj").
_LOOKALIKES = str.maketrans("aceojpxyiAEOJPCXKMHTB", "асеојрхуіАЕОЈРСХКМНТВ")

SECTIONS = {
    "ГЛАСАЛИ ЗА": "za",
    "ГЛАСАЛИ ПРОТИВ": "protiv",
    "УЗДРЖАНИ": "uzdrzan",
    "НИСУ ГЛАСАЛИ": "nije_glasao",
    "НИСУ ПРИСУТНИ": "nije_prisutan",
}
# The vote word a row may carry, by its first letters after normalising.
_VOTE_WORDS = (("за", "za"), ("против", "protiv"), ("уздржан", "uzdrzan"), ("није гласа", "nije_glasao"),
               ("није присут", "nije_prisutan"), ("ниіе гласа", "nije_glasao"), ("ниіе присут", "nije_prisutan"))

_WHEN = re.compile(r"(\d{1,2})\.\s?(\d{1,2})\.\s?(\d{4})\.?\s*/\s*(\d{1,2}):(\d{2}):(\d{2})")
_ROW = re.compile(r"^\s*(\d{1,3})\.?\s+(\S.*)$")
_HEADERS = ("ИЗВЕШТАЈ СА РЕЗУЛТАТИМА ГЛАСАЊА", "НАРОДНА СКУПШТИНА РЕПУБЛИКЕ СРБИЈЕ")


def cyrillic(text: str) -> str:
    """text with Latin look-alike letters made Cyrillic, for matching words (not for keeping names)."""
    return text.translate(_LOOKALIKES)


def vote_word(text: str) -> str | None:
    t = cyrillic(text).strip().lower().replace("і", "и")
    for start, value in _VOTE_WORDS:
        if t.startswith(start.replace("і", "и")):
            return value
    return None


def section_of(line: str) -> str | None:
    t = re.sub(r"\s+", " ", cyrillic(line).strip().rstrip(":").upper().replace("І", "И"))
    return SECTIONS.get(t)


@dataclass
class Row:
    number: int
    name: str
    vote: str  # za, protiv, uzdrzan, nije_glasao, nije_prisutan
    club: str  # as the PDF writes it: a group ("ПГ АВ-СНСДС"), a list's name, or "" for none


@dataclass
class Vote:
    when: str  # ISO date and time, "2026-06-25T11:17:12"
    item: str  # the agenda item as the PDF states it, number included
    kind: str = ""  # "Гласање о предлогу акта у целини", where the PDF says
    session: str = ""
    rows: list[Row] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    def count(self) -> dict[str, int]:
        out = {v: 0 for v in SECTIONS.values()}
        for r in self.rows:
            out[r.vote] += 1
        return out


def text_of(pdf: Path | str) -> str:
    return subprocess.run(["pdftotext", "-layout", str(pdf), "-"], check=True, capture_output=True,
                          text=True).stdout


def _row(line: str, section: str) -> Row | None:
    m = _ROW.match(line)
    if not m:
        return None
    number, rest = int(m.group(1)), m.group(2).strip()
    fields = re.split(r"\s{2,}", rest)
    vote = section
    if len(fields) == 1:  # 2024: "Given Surname (list)"
        p = re.match(r"^(.*?)\s*\((.*)\)\s*$", rest)
        name, club = (p.group(1), p.group(2)) if p else (rest, "")
    else:
        name, others = fields[0], fields[1:]
        word = vote_word(others[0])
        if word and (len(others) > 1 or cyrillic(others[0]).strip().lower() in ("за", "против")
                     or word in ("uzdrzan", "nije_glasao", "nije_prisutan")):
            vote, others = word, others[1:]
        club = " ".join(others).strip()
    # A vote word and the group with one space between them: "За ПГ АВ-СНСДС". Not a group whose name starts
    # with the word: "За помирење СПП-УСС-ДСХВ" (2023).
    m = re.match(r"^(За|Против|Уздржан\w*|Ни[јj]е\s+гласа\w*)\s+(.+)$", cyrillic(club)) if club else None
    if m and vote_word(m.group(1)) and not m.group(2)[:1].islower():
        vote, club = vote_word(m.group(1)), club[m.start(2):]
    club = "" if club in ("-", "–") else club
    return Row(number, name.strip(), vote, club)


def _split_known_groups(vote: "Vote") -> None:
    """A long name and its group with one space between them read as one field ("… Марија Здравковић А. ВУЧИЋ -
    Србија не сме да стане"): where a row has no group and its name ends with a group other rows of the same vote
    carry, that end is the group."""
    groups = sorted({r.club for r in vote.rows if r.club}, key=len, reverse=True)
    for r in vote.rows:
        if r.club:
            continue
        for g in groups:
            if r.name.endswith(" " + g):
                r.name, r.club = r.name[: -len(g)].strip(), g
                break


def parse(text: str) -> list[Vote]:
    """Every vote in a roll-call PDF's layout text, in order."""
    votes: dict[tuple[str, str], Vote] = {}
    order: list[tuple[str, str]] = []
    header: list[str] = []  # lines of the current page's header, before its first section
    in_header = True
    current: Vote | None = None
    section: str | None = None

    def start_vote():
        nonlocal current, section
        joined = [l.strip() for l in header if l.strip()]
        when_line = next((l for l in joined if _WHEN.search(l)), None)
        if when_line is None:
            return
        d, mo, y, h, mi, s = _WHEN.search(when_line).groups()
        when = f"{y}-{int(mo):02d}-{int(d):02d}T{int(h):02d}:{mi}:{s}"
        kind = cyrillic(when_line[: _WHEN.search(when_line).start()]).strip(" -–").strip()
        kind = "" if kind.upper().startswith("ВРЕМЕ ГЛАСАЊА") else kind
        title_at = next((i for i, l in enumerate(joined) if cyrillic(l).upper().replace("І", "И") in _HEADERS), -1)
        item_lines, session_lines = [], []
        for i, l in enumerate(joined):
            if i <= title_at or l is when_line or cyrillic(l).upper().startswith("ВРЕМЕ ГЛАСАЊА"):
                continue
            l = l.lstrip("•· ").strip()
            listinzi = title_at >= 0 and "НАРОДНА" in cyrillic(joined[title_at]).upper()  # no session line there
            session_done = listinzi or (bool(session_lines) and re.search(r"(години|сазиву)\s*$", session_lines[-1]))
            numbered = re.match(r"^\d+(\.\s?\d+)*\.?\s", l) and not re.match(r"^\d{4}\.\s+годин", l)
            if item_lines or numbered or session_done:
                item_lines.append(l)
            else:
                session_lines.append(l)
        item = re.sub(r"\s+", " ", " ".join(item_lines)).strip()
        key = (when, item[:60])
        if key not in votes:
            votes[key] = Vote(when, item, kind, re.sub(r"\s+", " ", " ".join(session_lines)).strip())
            order.append(key)
        current, section = votes[key], None

    for line in text.splitlines():
        if not line.strip():
            continue
        upper = cyrillic(line.strip()).upper().replace("І", "И")
        if upper in _HEADERS:  # a new page
            header, in_header, section = [line], True, None
            continue
        s = section_of(line)
        if s:
            if in_header:
                start_vote()
                in_header = False
            section = s
            continue
        if in_header:
            header.append(line)
            continue
        when = _WHEN.search(line)
        if when and current is not None and not _ROW.match(line):
            # A second vote on the same item in the same file, with only its time as a header (December 2025).
            d, mo, y, h, mi, s_ = when.groups()
            stamp = f"{y}-{int(mo):02d}-{int(d):02d}T{int(h):02d}:{mi}:{s_}"
            key = (stamp, current.item[:60])
            if key not in votes:
                kind = cyrillic(line[: when.start()]).strip(" -–").strip()
                votes[key] = Vote(stamp, current.item, kind, current.session)
                order.append(key)
            current, section = votes[key], None
            continue
        if current is None or section is None:
            continue
        row = _row(line, section)
        if row:
            if row.vote != section:
                current.problems.append(f"row {row.number} in {section} reads {row.vote}")
            row.vote = section
            current.rows.append(row)
    out = [votes[k] for k in order]
    for v in out:
        _split_known_groups(v)
        _check(v)
    return out


def _check(vote: Vote) -> None:
    """Numbers run from 1 within each section; nobody is listed twice."""
    for s in SECTIONS.values():
        numbers = sorted(r.number for r in vote.rows if r.vote == s)
        if numbers and numbers != list(range(1, len(numbers) + 1)) and numbers != list(range(1, numbers[-1] + 1)):
            vote.problems.append(f"{s}: numbers {numbers[:3]}… not 1..{len(numbers)}")
    names = [r.name for r in vote.rows]
    if len(set(names)) != len(names):
        vote.problems.append("a name is listed twice")


def read(pdf: Path | str) -> list[Vote]:
    return parse(text_of(pdf))
