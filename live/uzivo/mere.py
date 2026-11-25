"""Who is who in the day's summary and to whom the chair's measures went: names as the list writes them, never as heard.

The model reads names from an automatic transcript, in whatever case the sentence put them ("Anji Brnabić",
"Milinku Jovanovu", "Bakiću") and sometimes misheard. Every name shown is the MP's own from the convocation's list:
a name in a sentence is the MP whose surname it is (any case ending), the given name deciding between MPs of one
surname. An MP's list is the list's, never the model's: the group, or the party who proposed them when not in one.

A measure is the chair's own words giving it ("izričem vam opomenu", "druga opomena", "oduzimam vam reč"); a sentence
that only speaks of a measure given before ("dali ste mu opomenu") is none. To whom, in this order, each said so on
the page: a name in the chair's sentence; the stretch's summary naming who got a measure at that minute; the chair
naming, a little later, whom he had warned ("dao sam opomene poslanici …"); for a word taken away for going over
time, the MP who had the floor. Otherwise nobody: it is never guessed.
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

from .names import latin, normalize

BELGRADE = ZoneInfo("Europe/Belgrade")
_GIVES = re.compile(r"izri[čc]\w*|izli[čc]\w*|izvrkao|izrkao|druga opomena|prva opomena|oduz\w* (sam )?(vam |mu |joj )?re[čćc]"
                    r"|udalj\w* (vas )?sa sednic", re.I)
_SPOKEN_OF = re.compile(r"\bste (mu |joj |ga |je |im )?(dali|izrekli|opomenuli)\b|\bopomenuli\b|\bdobili opomen", re.I)
_RECAP = re.compile(r"\b((dao|izrekao) sam|sam (dao|izrekao)) (\w+ )?opomen", re.I)
def given(text: str) -> bool:
    """Whether the sentence gives a measure: not one spoken of by an MP, nor told of afterwards (checked on 19 Nov 2026:
    of 13 model's measures the eight given are, the five not are not)."""
    text = latin(text)
    return bool(_GIVES.search(text)) and not _SPOKEN_OF.search(text) and not _RECAP.search(text)


# Why a warning was given, by the Rules' own list (art. 109), told in our words where the chair's sentence says it
# (24 Nov 2026, the maintainer: the day's steps fuller, with no sentence of the transcript shown). In the article's order.
_REASONS = (
    ("zbog prilaska govornici bez dozvole", r"pri[sš]l\w+ (ste |je )?(govornici )?bez (poziva|dozvole)"),
    ("zbog govora bez date reči", r"bez (date|dobijene) re[cčć]i"),
    ("zbog govora van teme", r"\b(niste|nije|nisi) u temi|\b(van|mimo|izvan) teme\b|vrati\w* (se )?na temu|ne vezuje\w* za temu"
                             r"|nije na dnevnom redu"),
    ("zbog dobacivanja", r"\bdobac(uje|ivanj)\w*|prekida\w* govornik|ometa\w* govornik"),
    ("zbog neposrednog obraćanja drugom poslaniku", r"obra[cć]a\w* (se )?(direktno|neposredno|li[cč]no)"
                                                    r"|(direktno|neposredno|li[cč]no) (se )?obra[cć]a|obratili (ste )?(se )?li[cč]no"),
    ("zbog uvredljivih izraza", r"\buvred\w+|\bpsovk\w+|\bpsuje\w*"),
    ("zbog iznošenja privatnog života", r"privatn\w+ [zž]ivot"),
)
_REASONS = tuple((label, re.compile(rx, re.I)) for label, rx in _REASONS)


def reason(text: str) -> str:
    """Why the measure was given, when the sentence that gives it says exactly one of the Rules' reasons (art. 109);
    "" when none is heard or more than one (the sentence may hold another's words too). Never the transcript's wording."""
    text = latin(text)
    if not given(text):
        return ""
    hit = [label for label, rx in _REASONS if rx.search(text)]
    return hit[0] if len(hit) == 1 else ""


_TIME = re.compile(r"\b(\d{1,2}):(\d{2})\b")


@dataclass(frozen=True)
class MP:
    name: str          # "Surname Given", as the list writes it, Latin
    slug: str = ""
    group: str = ""    # the parliamentary group, Latin; "" when in none
    party: str = ""    # who proposed the MP, Latin; "-" or "" when nobody
    photo: str = ""    # the portrait's file on the site ("1435.jpg"), "" when none

    @property
    def label(self) -> str:
        """The MP's list as the mail shows it: the group, else the party, else "van poslaničkih grupa"."""
        if self.group:
            return self.group
        return self.party if self.party and self.party != "-" else "van poslaničkih grupa"


@dataclass
class Measure:
    vreme: str
    mera: str                                    # "opomena", "druga opomena", "oduzimanje reči"
    kome: list[MP] = field(default_factory=list)
    kako: str = ""                               # "ime", "sažetak", "kasnije", "za govornicom"


_ENDINGS = ("", "a", "u", "e", "om", "em", "i", "ju", "oj", "ovi", "ima", "ama", "in", "ina")


def _stem_hit(name_word: str, word: str) -> bool:
    """A word of the text is the surname in one of its cases: the name with a case ending ("bakicu", "jovanovu"),
    or a name in -a with its -a changed ("radeti" for "radeta"). Not a longer name: "jovanovic" is not "jovanov"."""
    if len(name_word) < 3:
        return False
    stems = [name_word] + ([name_word[:-1]] if name_word.endswith("a") else [])
    return any(word.startswith(s) and word[len(s):] in _ENDINGS for s in stems)


class Roll:
    """The convocation's MPs, to find in text."""

    def __init__(self, mps: list[MP]):
        self.mps = mps

    def find(self, text: str, prefer: MP | None = None) -> list[MP]:
        """The MPs a text names, in the order named: each by a form of the surname, the given name (or a word near
        it, misheard) deciding when more MPs share the surname, then `prefer` (who had the floor) when it is one of
        them; none when that still leaves two."""
        words = normalize(text).split()
        found: list[tuple[int, MP]] = []
        for mp in self.mps:
            parts = normalize(mp.name).split()
            surname, given = parts[:-1], parts[-1:]
            at = [i for i, w in enumerate(words) if _stem_hit(surname[-1], w)] if surname else []
            if not at:
                continue
            found.append((at[0], mp))
        out: list[MP] = []
        by_surname: dict[str, list[tuple[int, MP]]] = {}
        for i, mp in found:
            by_surname.setdefault(normalize(mp.name).split()[0], []).append((i, mp))
        for group in by_surname.values():
            if len(group) == 1:
                pick = group[0]
            else:
                def near(item: tuple[int, MP]) -> float:
                    i, mp = item
                    given = normalize(mp.name).split()[-1]
                    around = words[max(0, i - 2): i + 3]
                    return max((difflib.SequenceMatcher(None, given, w).ratio() for w in around), default=0.0)
                scored = sorted(group, key=near, reverse=True)
                if near(scored[0]) >= 0.6 and near(scored[0]) - near(scored[1]) >= 0.1:
                    pick = scored[0]
                elif prefer and any(mp == prefer for _, mp in group):
                    pick = next(x for x in group if x[1] == prefer)
                else:
                    continue
            out.append(pick)
        return [mp for _, mp in sorted(out, key=lambda x: x[0])]

    def one(self, name: str) -> MP | None:
        """The MP a name as the summary gives it stands for ("Brnabić Ana"), when exactly one."""
        hits = self.find(name)
        return hits[0] if len(hits) == 1 else None


def _clock(t: float, tz: ZoneInfo) -> str:
    return datetime.fromtimestamp(t, tz).strftime("%H:%M")


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def measures(lines: list[dict], stretches: list[dict], roll: Roll, tz: ZoneInfo = BELGRADE) -> list[Measure]:
    """The chair's measures of a day from its lines (`/data/hronika/<day>.json`) and its stretches' summaries
    (the day summary's "delovi"), with to whom as the module's rules find it."""
    floor: MP | None = None
    floors: list[tuple[int, MP]] = []  # (minute, who was given the floor)
    out: list[Measure] = []
    recaps: list[tuple[str, list[MP]]] = []
    for e in lines:
        text = latin(e.get("tekst") or "")
        if e.get("vrsta") == "Reč ima":
            floor = (roll.find(text) or [None])[0] or floor
            if floor:
                floors.append((_minutes(_clock(e["t"], tz)), floor))
            continue
        if e.get("vrsta") != "Mera predsedavajućeg" or e.get("izvor") != "model":
            continue
        when = _clock(e["t"], tz)
        if _RECAP.search(text):
            recaps.append((when, roll.find(text + " " + ((e.get("vise") or {}).get("kome") or ""))))
            continue
        if _SPOKEN_OF.search(text) or not _GIVES.search(text):
            continue
        kind = ((e.get("vise") or {}).get("napomena") or "opomena").strip().lower()
        if "oduz" in text.lower() and "opomen" not in text.lower():
            kind = "oduzimanje reči"
        if out and out[-1].vreme == when and out[-1].mera == kind:
            continue  # one measure written twice
        m = Measure(when, kind)
        named = roll.find(text + " " + ((e.get("vise") or {}).get("kome") or ""))
        if named:
            m.kome, m.kako = named, "ime"
        elif kind == "oduzimanje reči" and re.search(r"prob\w* vreme|isteklo|vreme vam", text, re.I) and floor:
            m.kome, m.kako = [floor], "za govornicom"
        out.append(m)
    # The stretches' summaries: a line that names an MP and gives a measure's minute ("izrekao opomene u 17:03 i 17:05").
    told: dict[str, list[MP]] = {}
    for part in stretches:
        for s in part.get("tok") or []:
            sta = s.get("sta", "")
            if not re.search(r"opomen|oduz\w* re", sta, re.I) or re.search(r"pitao da li|povla[čc]", sta, re.I):
                continue
            for h, mi in _TIME.findall(sta):
                at = int(h) * 60 + int(mi)
                had = [mp for m_, mp in floors if m_ <= at]
                who = roll.find(sta, prefer=had[-1] if had else None)
                if who:
                    told[f"{int(h):02d}:{mi}"] = who[:1]
    for m in out:
        if not m.kome and m.vreme in told:
            m.kome, m.kako = told[m.vreme], "sažetak"
    # The chair naming afterwards whom he warned: the last unnamed measures before it, one name each or all at once.
    for when, who in recaps:
        if not who:
            continue
        before = [m for m in out if not m.kome and 0 <= _minutes(when) - _minutes(m.vreme) <= 60]
        if before:
            before[-1].kome, before[-1].kako = who, "kasnije"
    return out


def roll_from(members: list[dict], latin_name=latin) -> Roll:
    """The convocation's list as `data/<N>/members.json` keeps it ({"name", "group", "party"}, Cyrillic)."""
    def title(name: str) -> str:
        """"ПАСТОР проф. др БАЛИНТ" → "Pastor Balint": the capitals are the name, titles left out."""
        return " ".join(latin_name(w).capitalize() for w in name.split() if w.isupper())
    return Roll([MP(title(m["name"]), group=latin_name(m.get("group") or ""), party=latin_name(m.get("party") or ""))
                 for m in members])
