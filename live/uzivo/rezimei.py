"""A line on each speech, when it ends (24 Nov 2026, the maintainer): the topic of the speech, by Claude Haiku from the
automatic transcript of that speech alone, under the speech in "Svi govori, redom". The topic only, never what was claimed
(the maintainer's choice: in the trial, lines with claims were wrong for some one in seven).

Haiku's lines on a whole stretch had turned a denial into its opposite, and a check of names and numbers could not see
it. So each line is checked twice: the sentence it rests on must stand in the speech word for word (sudija.norm), and a
second call reads the speech and the line together and says whether the line is true to it. One that fails either is
asked for once more, then left out: a speech without a line is better than a line that is wrong. Both calls are the
same model's, so the second is a filter and no proof. Every speech of LEAST seconds or more gets one, by one rule.

Kept in /data/rezimei/<day>.json: the line and what became of it, never the sentence (the transcript is never a quote).
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
from pathlib import Path

from . import config, prepis, sudija
from .state_base import SAID_LEAD, _write, speakers_own

log = logging.getLogger("uzivo.rezimei")

LEAST = 30  # seconds at the rostrum from which a speech gets a line
QUIET = 30  # seconds after its end before it is read
PATIENCE = 600  # seconds after its end it is read though some of its sound still waits to be written down
GREW = 30  # a speech whose end moved by more than this (two turns joined) is read again
WORDS = 25  # fewer words than this written down: nothing to tell
TRIES = 3  # failed calls after which a speech is left without a line

LINE = """Iz AUTOMATSKOG prepisa (Whisper; greši u imenima, brojevima i rečima) jednog govora u Narodnoj skupštini Srbije
pišeš SAMO TEMU govora: o čemu je govornik govorio, ne šta je tvrdio.

PRAVILA
1. Samo ono o čemu je u ovom govoru bilo reči; ništa iz sopstvenog znanja.
2. Jedan izraz koji počinje sa "O " ("O sastavu odbora i zastupljenosti poslaničkih grupa."), najviše 16 reči, jedna do tri
   teme, srpski, latinica. Bez stava, tvrdnje, ocene i tona; bez glagola koji kaže šta je govornik rekao ili uradio.
3. Tema ne sme da pretpostavi da je nešto tačno ni da je neko nešto uradio. Sporno se piše kao tvrdnja ili optužba:
   "O optužbama za …", "O tvrdnjama o …", "O navodnom …". Tako uvek kad je reč o nečijem ružnom postupku (isključivanje,
   pretnja, povreda Poslovnika, laž, nepristojno ponašanje), osim kad je to mera koju je predsedavajući izrekao. Nikad "O njegovom učešću u …" kad on to poriče ili mu to drugi pripisuje.
4. Tešku temu ne ublažavaš i ne izostavljaš ("O nasilju na protestima" ostaje nasilje).
5. Bez imena ljudi, bez brojeva, bez navodnika i bez doslovnih citata. Nazivi ustanova, zakona, mesta i projekata smeju.
6. Na početku i kraju prepisa može stajati reč predsedavajućeg ili drugog poslanika: to nije tema ovog govora. Povreda
   Poslovnika i replika su tema samo kad govor drugu nema.
7. "oslonac": rečenica iz govora iz koje se tema vidi, PREPISANA SLOVO PO SLOVO, sa greškama, 6 do 40 reči.

IZLAZ: samo JSON: {"rezime": "O …", "oslonac": "..."}. Kad tema nije jasna: {"rezime": "", "oslonac": ""}"""

CHECK = """Proveravaš da li tema verno kaže o čemu je bio govor iz Narodne skupštine Srbije (automatski prepis, greši u
rečima). Budi strog. Netačna je kad: o tome u govoru nije bilo reči; pretpostavlja kao činjenicu ono što govornik tvrdi,
poriče ili mu neko pripisuje; nečiji ružan postupak piše bez "o tvrdnjama", "o optužbama" ili "navodno"; iznosi stav ili ocenu; pominje ime čoveka; tema je reč predsedavajućeg ili drugog poslanika.
Tačna je i kad izostavlja deo tema.
IZLAZ: samo JSON: {"tacno": true ili false, "razlog": "kratko"}"""


class Writer(threading.Thread):
    """Reads each speech that has ended, the newest first, and keeps its line with the day."""

    def __init__(self, tracker, stop: threading.Event, ask=None) -> None:
        super().__init__(daemon=True)
        self.tracker, self.halt = tracker, stop
        self.ask = ask or (lambda system, user: sudija.ask_claude(system, user, 4000, "low"))
        self.day, self.kept = "", []

    def _file(self, day: str) -> Path | None:
        return Path(config.STATE_PATH).parent / "rezimei" / f"{day}.json" if config.STATE_PATH else None

    def _load(self, day: str) -> None:
        if day == self.day:
            return
        self.day, self.kept = day, []
        f = self._file(day)
        try:
            if f and f.exists():
                self.kept = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
        self.tracker.use_lines(day, self.kept)

    def _save(self) -> None:
        f = self._file(self.day)
        if f:
            try:
                _write(f, self.kept)
            except OSError:
                pass
        self.tracker.use_lines(self.day, self.kept)

    @staticmethod
    def _waits(files, d: dict) -> bool:
        return any(d["od"] - 5 <= start + length / 2 <= d["do"] + 5 for start, length, _ in files)

    def due(self, snap: dict, now: float, files) -> list[dict]:
        """The speeches that have ended and have no line, or have grown since theirs was written; newest first."""
        out = []
        for d in snap.get("danas") or []:
            if d["sekundi"] < LEAST or now - d["do"] < QUIET or (self._waits(files, d) and now - d["do"] < PATIENCE):
                continue
            mine = next((k for k in self.kept if k["ime"] == d["ime"] and same(k, d)), None)
            if mine and abs(mine["do"] - d["do"]) <= GREW and (mine["rezime"] or mine["pokusaja"] >= TRIES or mine.get("gotovo")):
                continue
            out.append(d)
        return sorted(out, key=lambda d: -d["od"])

    def line(self, text: str) -> tuple[str, bool]:
        """(the line, or "" when there is none that holds; whether the answer is final)."""
        note = ""
        for _ in range(2):
            got = sudija.reply_json(self.ask(LINE, "Govor:\n" + text + note)) or {}
            said, basis = str(got.get("rezime") or "").strip(), sudija.norm(str(got.get("oslonac") or ""))
            if not said and not got:
                return "", False
            if not said:
                return "", True
            why = ""
            if not said.startswith("O ") or len(said.split()) > 20 or re.search(r'[„"“]|\d', said):
                why = "nije izraz koji počinje sa O, predugačak je, ili ima broj ili navodnike"
            elif len(basis) < 12 or basis not in sudija.norm(text):
                why = "oslonac nije doslovno u govoru"
            else:
                judged = sudija.reply_json(self.ask(CHECK, f"Govor:\n{text}\n\nRečenica: {said}")) or {}
                if judged.get("tacno") is True:
                    return said, True
                why = str(judged.get("razlog") or "rečenica nije tačna")
            log.info("line not kept: %s", why)
            note = f"\n\nPrethodna rečenica nije prošla proveru ({why}): „{said}“. Napiši je ponovo po pravilima."
        return "", True

    def step(self, now: float | None = None) -> None:
        now = time.time() if now is None else now
        snap = self.tracker.snapshot(now=now)
        if not snap.get("dan") or snap.get("ranije") or snap.get("snimak"):
            return
        self._load(snap["dan"])
        for d in self.due(snap, now, prepis.waiting())[:1]:  # one at a time: a speech that has just ended goes first
            with self.tracker._lock:
                said = dict(self.tracker._said_of(snap["dan"]))
            text = self.tracker.shown(spoken(said, d))
            old = next((k for k in self.kept if k["ime"] == d["ime"] and same(k, d)), None)
            tries = (old or {}).get("pokusaja", 0) + 1
            line, final = "", True
            if len(text.split()) >= WORDS:
                try:
                    line, final = self.line(text)
                except Exception as exc:
                    log.warning("line not written (%s)", exc)
                    final = False
            self.kept[:] = [k for k in self.kept if k is not old] + [
                {"ime": d["ime"], "od": int(d["od"]), "do": int(d["do"]), "rezime": line, "pokusaja": tries, "gotovo": final}]
            self._save()

    def run(self) -> None:
        while not self.halt.is_set():
            try:
                self.step()
            except Exception:
                log.exception("the lines' look")
            self.halt.wait(8)


def spoken(said: dict[str, str], d: dict) -> str:
    """What was written down of a speech, in order: the pieces of its sound, and those kept as the chair's that are the
    speaker's (state_base.speakers_own)."""
    rows = [(int(k.lstrip("p")), k.startswith("p"), v) for k, v in said.items() if k.lstrip("p").isdigit()]
    return " ".join(v for ts, chair, v in sorted(rows)
                    if (speakers_own(ts, v, d["od"], d["do"]) if chair else d["od"] - SAID_LEAD - 1 <= ts <= d["do"]))


def same(k: dict, d: dict) -> bool:
    """Whether a kept line is of this speech: they share most of the shorter one's time."""
    both = min(k["do"], d["do"]) - max(k["od"], d["od"])
    return both > 0 and both >= 0.5 * max(1, min(k["do"] - k["od"], d["do"] - d["od"]))


def shown(lines: list[dict], d: dict) -> str:
    """The line of a speech as the page shows it ("" when there is none)."""
    k = next((k for k in lines if k["ime"] == d["ime"] and same(k, d)), None)
    return k["rezime"] if k and k.get("rezime") else ""
