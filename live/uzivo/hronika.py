"""What happened in the sitting, as it happens (19 Nov 2026, the maintainer's decision): a line a step.

Two sources, each named beside its line:
- the automatic transcript (prepis.py), the chair's words above all: the chair says every step aloud in set phrases
  ("prelazimo na tačku", "zaključujem pretres", "stavljam na glasanje", "određujem pauzu"), and `find` looks for those
  by rule, the same whoever says them. Whisper errs in names and numbers, so a line from it is a pointer to the moment,
  never a result;
- the sitting's own page on the Assembly's site, which the Assembly fills in during the day: `Watcher` reads it every
  ten minutes and each sentence new since the last reading becomes a line, in the Assembly's words.
Nothing is summed up or judged; a line is the sentence it was found in.
"""
from __future__ import annotations

import html as html_
import logging
import re
import threading
import time
import urllib.parse
import urllib.request

from . import config
from .names import latin
from .state import Tracker
from .stream import _BROWSER_HEADERS

log = logging.getLogger("hronika")

# (what the line is called, a pattern over the sentence in Latin lower case). The first that fits names the line.
RULES: list[tuple[str, re.Pattern]] = [(label, re.compile(rx)) for label, rx in [
    ("Glasanje zaključeno", r"zaključuj\w* glasanj|zaključeno glasanj"),
    ("Glasanje", r"stavlj\w* na glasanj|prelaz\w* na glasanj|pristup\w* glasanj|molim\w* da se izjasn|dan za glasanj"),
    ("Tačka dnevnog reda", r"prelaz\w* na \w*\s*\w*\s*tačk|prelaz\w* na dnevn\w* red|tačk\w* dnevnog reda"),
    ("Pretres zaključen", r"zaključuj\w* \w*\s*\w*\s*(pretres|rasprav)"),
    ("Pretres otvoren", r"otvaram\w* \w*\s*\w*\s*(pretres|rasprav)"),  # the chair's own verb, not "do otvaranja pretresa"
    ("Pauza", r"određuj\w* pauz|pravimo pauz|pauz\w* u trajanju|nastavljamo u \d|nastavljamo sutra|nastavak sednice"),
    ("Nastavak rada", r"nastavlja\w* (sa )?rad|nastavljamo sednic"),
    ("Mera predsedavajućeg", r"izrič\w* \w*\s*(opomen|mer)|oduzima\w* \w*\s*reč|udaljenj\w* sa sednic"),
    ("Sednica otvorena", r"otvaram\w* \w*\s*\w*\s*sednic"),
    ("Kraj rada", r"zaključuj\w* \w*\s*\w*\s*sednic|završ\w* rad za danas|zaključuj\w* današnj"),
    ("Predsedavajući konstatuje", r"konstatuj\w* da (je|su|nije)"),
]]
_ORDINALS = {"prv": 1, "drug": 2, "treć": 3, "trec": 3, "četvrt": 4, "cetvrt": 4, "pet": 5, "šest": 6, "sest": 6, "sedm": 7,
             "osm": 8, "devet": 9, "deset": 10}
_ITEM = re.compile(r"(?:na|po)\s+(\w+)\s+tačk|tačk\w*\s+(\d{1,2})\b|(\d{1,2})\.?\s+tačk|(\w+)\s+tačk\w*\s+dnevnog\s+reda")


def item_no(sentence: str) -> int:
    """The number of the agenda item a sentence moves to ("prelazimo na drugu tačku", "tačku 3"); 0 when it names none."""
    m = _ITEM.search(latin(sentence).lower())
    if not m:
        return 0
    if m.group(2) or m.group(3):
        return int(m.group(2) or m.group(3))
    word = m.group(1) or m.group(4)  # "na treću tačku", or the chair naming it: "Treća tačka dnevnog reda, izbor…"
    return next((n for stem, n in _ORDINALS.items() if word.startswith(stem)), 0)


_SENTENCE = re.compile(r"(?<=[.!?])\s+")
LONGEST_LINE = 220


def find(text: str) -> list[tuple[str, str]]:
    """The steps said in a piece of text: [(what, the sentence it was said in)], in the order said."""
    out = []
    for sentence in _SENTENCE.split(" ".join(latin(text).split())):
        low = sentence.lower()
        for label, rx in RULES:
            if rx.search(low):
                s = sentence.strip()
                out.append((label, s if len(s) <= LONGEST_LINE else s[:LONGEST_LINE].rsplit(" ", 1)[0] + "…"))
                break
    return out


_FLOOR = re.compile(r"(?=\b(?:reč ima|ima reč)\b([^.!?]{0,90}))")  # a look ahead: two in one sentence are both found


def floor(text: str, people: list) -> list:
    """Whom the chair gave the floor to in a piece of text ("Reč ima narodni poslanik Jovo Bakić"): the sitting MPs
    (names.Person) named right after the phrase. Strict, since Whisper errs in names and a wrong one would put a
    speech in someone's mouth: every word of the MP's name, whole (but for diacritics), among the seven words after
    the phrase, and exactly one MP fitting. Anything less names nobody."""
    from .ispravke import fold
    names = [({fold(w) for w in p.name.split()}, p) for p in people if len(p.name.split()) >= 2]
    out = []
    for m in _FLOOR.finditer(" ".join(latin(text).split()).lower()):
        said = {fold(w) for w in re.findall(r"[^\W\d_]+", m.group(1))[:7]}
        hits = [p for ws, p in names if ws <= said]
        if len(hits) == 1 and hits[0] not in out:
            out.append(hits[0])
    return out


_TAGS = re.compile(r"<script.*?</script>|<style.*?</style>|<[^>]+>", re.S)


def page_sentences(page: str) -> list[str]:
    """The sitting's report on its page at the Assembly, a sentence each, in Latin: the text between the page's
    title and its gallery or documents. Sentences of at least six words (menus and captions are shorter)."""
    text = html_.unescape(_TAGS.sub(" ", page))
    text = " ".join(text.split())
    for end in ("Фото галерија", "Повезана документа"):
        cut = text.find(end)
        if cut > 0:
            text = text[:cut]
    start = max(text.rfind("Претрага сајта"), 0)
    out = []
    for s in _SENTENCE.split(text[start:]):
        s = latin(s.strip())
        if len(s.split()) >= 6 and len(s) < 700:
            out.append(s)
    return out


class Watcher(threading.Thread):
    """Reads the sitting's page(s) the site names (`sednice` in mikrofon-cekanje.json) every ten minutes while a
    broadcast is on, and the site's notices and that list every ten minutes whatever is on."""

    EVERY = 600

    def __init__(self, tracker: Tracker, stop: threading.Event, fetch=None) -> None:
        super().__init__(daemon=True)
        self.tracker, self.halt = tracker, stop
        self.fetch = fetch or self._fetch
        self.seen: dict[str, set[str]] = {}

    @staticmethod
    def _fetch(url: str) -> str:
        # the address may hold Cyrillic letters; the Assembly's server wants them percent-encoded
        safe = urllib.parse.quote(url, safe=":/?&=%#+")
        with urllib.request.urlopen(urllib.request.Request(safe, headers=_BROWSER_HEADERS), timeout=30) as resp:
            return resp.read().decode("utf-8", "replace")

    def look(self, now: float | None = None) -> int:
        """One reading of each page; returns how many new lines it gave."""
        now = time.time() if now is None else now
        added = 0
        waiting = self.tracker.waiting if isinstance(self.tracker.waiting, dict) else {}
        for url in [u for u in waiting.get("sednice") or [] if str(u).startswith("https://www.parlament.gov.rs/")][:3]:
            try:
                sentences = page_sentences(self.fetch(url))
            except Exception as exc:
                log.info("the sitting's page not read (%s)", exc)
                continue
            known = self.seen.get(url)
            if known is None:  # the first reading is where we start from, not news
                kept = self.tracker.page_seen(url)
                self.seen[url] = known = set(kept) if kept else set(sentences)
            new = [s for s in sentences if s not in known]
            for s in new:
                self.tracker.note(now, "Sajt Skupštine", s if len(s) <= 420 else s[:420].rsplit(" ", 1)[0] + "…", "sajt", url)
            known.update(new)
            self.tracker.page_seen(url, sorted(known))
            added += len(new)
        return added

    def run(self) -> None:
        import json
        while not self.halt.is_set():
            try:
                req = urllib.request.Request(config.WAIT_URL, headers={"User-Agent": "zailiprotiv-uzivo"})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    self.tracker.use_waiting(json.loads(resp.read().decode("utf-8")))
            except Exception as exc:
                log.debug("notices not fetched (%s)", exc)
            try:
                if self.tracker.status != "nema_prenosa":
                    n = self.look()
                    if n:
                        log.info("the sitting's page: %d new sentences", n)
            except Exception:
                log.exception("the sitting's page")
            self.halt.wait(self.EVERY)
