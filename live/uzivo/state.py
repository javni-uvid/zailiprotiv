"""Who is speaking now, and today's turns, from one reading per frame. Only the standard library.

The same rule for every speaker: a turn starts with the first frame whose caption names them, lasts while frames go
on naming them (frames with no readable name in between do not end it for HOLD_SECONDS), and ends when another name
is read, when two frames in a row name someone else even if unreadably, when nothing is read for HOLD_SECONDS, or
when the broadcast stops. A name not on the site's list of MPs
(a minister, a guest) must be read in two frames in a row first: OCR noise can look like a name once.

Every day is kept in a file of its own (`dani/<date>.json` beside STATE_PATH): its turns, each with where it is in
the broadcast (the YouTube video and the numbers of its first and last segment), and when the service saw the
broadcast at all (`cover`), so a day's record says where it has gaps.

Between sittings the page lists the last sitting day. When the site has that day (or a later one) read afterwards from
the whole recording (`use_recording`, kept beside STATE_PATH as `snimak.json`), the page lists that instead, said so:
this service may have missed part of the day. Its own record at /dan/<date>.json stays as it was read.
"""
from __future__ import annotations

import json
import threading
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from . import config
from .names import Person, Roster

SPEAKING, UNKNOWN, NO_STREAM = "govori", "nepoznato", "nema_prenosa"


SURE_FRAMES = 4  # a turn with no line under the name read in any frame is kept only from this many frames on


def counted(t: dict) -> bool:
    """Whether a turn goes into the day's list: read in two frames or more, and either with the line under the name
    (the list or office, which every real caption has) read at least once, or long enough to be no chance reading.
    19 Nov 2026: two turns of two frames each, no second line, named an MP who had not spoken; something else on the
    screen had been read as a name. The same rule for every name."""
    return t.get("n", 0) >= 2 and bool(t.get("role") or t.get("n", 0) >= SURE_FRAMES)


SAID_LEAD = 6  # seconds: a turn's sound begins this long before its first frame (the caption comes up late)
SAID_TAIL = 420  # characters of the newest transcript shown with the speaker


class Tracker:
    def __init__(self, path: str | None = None, tz: str | None = None) -> None:
        self._lock = threading.Lock()
        self.days = Path(path).parent / "dani" if path else None
        self.old = Path(path) if path else None  # until 17 Nov 2026 today's turns were kept here
        self.tz = ZoneInfo(tz or config.TZ)
        self.status = NO_STREAM
        self.last_frame = 0.0
        self.turns: list[dict] = []  # oldest first; the last may be open
        self.cover: list[list[float]] = []  # [from, to]: frames kept coming
        self.day = ""
        self.open = False
        self._pending = ""  # a name not on the list, read once
        self._others = 0  # frames in a row naming someone other than the current speaker
        self.recording_file = Path(path).with_name("snimak.json") if path else None
        self.recording: dict = {}  # the last sitting day read from the recording (the site's mikrofon-dan.json)
        self.waiting_file = Path(path).with_name("cekanje.json") if path else None
        self.waiting: dict = {}  # "Dok čekate": the site's quiz and facts (mikrofon-cekanje.json)
        self.facts_file = Path(path).with_name("poslanici.json") if path else None
        self.facts: dict = {}  # the speaker's votes and facts from their page (mikrofon-poslanici.json)
        self.roster: Roster | None = None  # the site's list of MPs, to name turns read before it knew them
        self.said: dict[str, str] = {}  # the day's automatic transcript in pieces, by each piece's first second (prepis.py)
        self._said_other: tuple[str, dict] = ("", {})  # an earlier day's, read when the page shows that day
        self._snap: tuple[float, dict] | None = None  # the last snapshot and when: every visitor asks every few seconds
        self._memo: dict = {}  # names and lines already matched to the list, by the list they were matched to
        self._migrate()
        self._load()
        for f, attr in ((self.recording_file, "recording"), (self.waiting_file, "waiting"), (self.facts_file, "facts")):
            try:
                if f and f.exists():
                    setattr(self, attr, json.loads(f.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                pass

    def use_waiting(self, w: dict) -> None:
        """The site's "Dok čekate"; anything not shaped like it is ignored."""
        if not isinstance(w, dict) or not isinstance(w.get("kviz"), list) or not isinstance(w.get("cinjenice"), list):
            return
        self.waiting = w
        if self.waiting_file:
            self.waiting_file.parent.mkdir(parents=True, exist_ok=True)
            self.waiting_file.write_text(json.dumps(w, ensure_ascii=False), encoding="utf-8")

    def use_facts(self, facts: dict) -> None:
        """The site's facts per MP's page (mikrofon-poslanici.json): {slug: {"za", "protiv", "uzdrzan", "f", "novi"}}."""
        if isinstance(facts, dict):
            with self._lock:
                self.facts = facts
                self._snap = None
            if self.facts_file:
                try:
                    self.facts_file.write_text(json.dumps(facts, ensure_ascii=False), encoding="utf-8")
                except OSError:
                    pass

    def use_recording(self, day: dict) -> None:
        """The site's last sitting day read from the recording; anything not shaped like one is ignored."""
        if not isinstance(day, dict) or not isinstance(day.get("dan"), str) or not isinstance(day.get("govori"), list):
            return
        with self._lock:
            self.recording = day
            self._snap = None
        if self.recording_file:
            self.recording_file.parent.mkdir(parents=True, exist_ok=True)
            self.recording_file.write_text(json.dumps(day, ensure_ascii=False), encoding="utf-8")

    # --- keeping today's turns across restarts ---
    def _day(self, ts: float) -> str:
        return datetime.fromtimestamp(ts, self.tz).date().isoformat()

    def _file(self, day: str) -> Path | None:
        return self.days / f"{day}.json" if self.days else None

    def _migrate(self) -> None:
        """Days recorded before the day files (until 17 Nov 2026) are only in the old state file: each gets its file,
        so the last sitting day stays on the page and is served at /dan/<date>.json."""
        if not self.days or not self.old or not self.old.exists():
            return
        try:
            turns = json.loads(self.old.read_text(encoding="utf-8")).get("turns", [])
        except (OSError, ValueError):
            return
        by_day: dict[str, list[dict]] = {}
        for t in turns:
            by_day.setdefault(self._day(t["start"]), []).append(t)
        today = self._day(time.time())
        for day, ts in by_day.items():
            f = self._file(day)
            if day < today and f and not f.exists():
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_text(json.dumps({"day": day, "turns": ts, "cover": []}, ensure_ascii=False), encoding="utf-8")

    def _load(self, day: str | None = None) -> None:
        self.day = day or self._day(time.time())
        self.turns, self.cover, self.open = [], [], False
        self.said = self._said_load(self.day)
        f = self._file(self.day)
        try:
            if f and f.exists():
                kept = json.loads(f.read_text(encoding="utf-8"))
                self.turns, self.cover = kept.get("turns", []), kept.get("cover", [])
            elif self.old and self.old.exists():
                turns = json.loads(self.old.read_text(encoding="utf-8")).get("turns", [])
                self.turns = [t for t in turns if self._day(t["start"]) == self.day]
        except (OSError, ValueError):
            pass

    # --- the automatic transcript (prepis.py writes it, a piece at a time) ---
    def _said_file(self, day: str) -> Path | None:
        return self.days.parent / "prepis" / f"{day}.json" if self.days else None

    def _said_load(self, day: str) -> dict[str, str]:
        f = self._said_file(day)
        try:
            if f and f.exists():
                kept = json.loads(f.read_text(encoding="utf-8"))
                return {str(k): str(v) for k, v in kept.items()} if isinstance(kept, dict) else {}
        except (OSError, ValueError):
            pass
        return {}

    def say(self, ts: float, text: str) -> None:
        """A piece of the transcript: the sound from second `ts` on, written down. Kept with the day."""
        text = " ".join(text.split())
        if not text:
            return
        with self._lock:
            day = self._day(ts)
            if day != self.day:
                return
            self.said[str(int(ts))] = text
            self._snap = None
            f = self._said_file(day)
            if f:
                try:
                    f.parent.mkdir(parents=True, exist_ok=True)
                    tmp = f.with_suffix(".tmp")
                    tmp.write_text(json.dumps(self.said, ensure_ascii=False), encoding="utf-8")
                    tmp.replace(f)
                except OSError:
                    pass

    def _said_of(self, day: str) -> dict[str, str]:
        if day == self.day:
            return self.said
        if self._said_other[0] != day:
            self._said_other = (day, self._said_load(day))
        return self._said_other[1]

    @staticmethod
    def _text(said: dict[str, str], start: float, end: float) -> str:
        """What was written down of a turn: the pieces that begin within it (a piece is cut where a turn begins)."""
        return " ".join(said[k] for k in sorted(said, key=int) if start - SAID_LEAD - 1 <= int(k) <= end)

    def transcript(self) -> dict:
        """The day on the page, each turn with what was written down of it, newest first: for the transcript's page."""
        snap = self.snapshot()
        with self._lock:
            said = dict(self._said_of(snap["dan"]))
        turns = ([snap["sada"]] if snap["stanje"] == "govori" and snap.get("sada") else []) + snap["danas"]
        out = [{**{k: d[k] for k in ("ime", "adresa", "od", "do", "sekundi")}, "lista": d.get("lista", ""),
                "tekst": self._text(said, d["od"], d["do"])} for d in turns]
        return {"dan": snap["dan"], "ranije": snap["ranije"], "govori": [d for d in out if d["tekst"]]}

    def _save(self) -> None:
        f = self._file(self.day)
        if not f:
            return
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_suffix(".tmp")
        tmp.write_text(json.dumps({"day": self.day, "turns": self.turns, "cover": self.cover}, ensure_ascii=False),
                       encoding="utf-8")
        tmp.replace(f)

    # --- readings ---
    def _close(self) -> None:
        if self.open:
            self.open = False
            self._save()

    def current(self) -> str:
        with self._lock:
            return self.turns[-1]["name"] if self.open and self.turns else ""

    def observe(self, person: Person | None, role: str = "", now: float | None = None, other: bool = False,
                at: dict | None = None) -> None:
        """One frame read: who its caption names (or None), the line under the name if read cleanly, whether the
        caption names someone else than the current speaker without saying clearly whom (`caption.differs`), and
        where the frame is in the broadcast (`at`: video, sq, seg)."""
        now = time.time() if now is None else now
        at = at or {}
        self._snap = None
        with self._lock:
            if self._day(now) != self.day:
                self._close()
                self._load(self._day(now))  # a new day, a new file
            if self.cover and now - self.cover[-1][1] <= config.STALE_SECONDS:
                self.cover[-1][1] = now
            else:
                self.cover.append([now, now])
            self.last_frame = now
            if self.status == NO_STREAM:
                self.status = UNKNOWN
            cur = self.turns[-1] if self.turns else None
            if person and not person.slug and not (self.open and cur["key"] == person.key):
                if self._pending != person.key:
                    self._pending, person = person.key, None  # wait for a second frame
            self._others = self._others + 1 if (other and not person) else 0
            if person:
                self._pending = ""
                if self.open and cur["key"] == person.key:
                    cur["seen"], cur["n"] = now, cur["n"] + 1
                    cur["role"] = role or cur["role"]
                    if at.get("sq") is not None and cur.get("video") == at.get("video"):
                        cur["sq_seen"] = at["sq"]
                else:
                    self._close()
                    prev = self.turns[-2] if len(self.turns) > 1 else None
                    if (cur and cur["key"] != person.key and cur["n"] == 1 and prev and prev["key"] == person.key
                            and now - prev["seen"] <= config.MERGE_SECONDS):
                        # one frame of another name inside a speech (a caption misread, 18 Nov 2026): not a turn
                        self.turns.pop()
                        cur = prev
                    if cur and cur["key"] == person.key and now - cur["seen"] <= config.MERGE_SECONDS:
                        cur["seen"], cur["n"] = now, cur["n"] + 1  # the same speaker after a short break
                        if at.get("sq") is not None and cur.get("video") == at.get("video"):
                            cur["sq_seen"] = at["sq"]
                    else:
                        self.turns.append({"key": person.key, "name": person.name, "slug": person.slug,
                                           "group": person.group, "role": role, "start": now, "seen": now, "n": 1,
                                           "video": at.get("video", ""), "sq_start": at.get("sq"),
                                           "sq_seen": at.get("sq"), "seg": at.get("seg")})
                    self.open = True
                    self._save()
                self.status = SPEAKING
            elif self.open and (self._others >= 2 or now - cur["seen"] > config.HOLD_SECONDS):
                self._close()
                self.status = UNKNOWN
            elif not self.open:
                self.status = UNKNOWN
            self._save()

    def tick(self, now: float | None = None) -> None:
        """Called each second, frame or not: a broadcast that stopped ends the turn."""
        now = time.time() if now is None else now
        with self._lock:
            if self.status != NO_STREAM and now - self.last_frame > config.STALE_SECONDS:
                self._close()
                self.status = NO_STREAM
                self._snap = None

    @staticmethod
    def _out(t: dict) -> dict:
        rec = None
        if t.get("video") and t.get("sq_start") is not None and t.get("seg"):
            rec = int(max(0, t["sq_start"] - config.RECORDING_LEAD) * t["seg"])
        return {"ime": t["name"], "adresa": t["slug"], "grupa": t["group"], "uloga": t["role"],
                "od": int(t["start"]), "do": int(t["seen"]), "sekundi": int(t["seen"] - t["start"]),
                "video": t.get("video") or "", "snimak": rec}

    def _last_day(self) -> tuple[str, list[dict]]:
        """The latest earlier day with turns: its list stays on the page until someone is read at the next sitting."""
        if not self.days or not self.days.exists():
            return "", []
        for f in sorted(self.days.glob("*.json"), reverse=True):
            if f.stem >= self.day:
                continue
            try:
                turns = [t for t in json.loads(f.read_text(encoding="utf-8")).get("turns", []) if counted(t)]
            except (OSError, ValueError, KeyError):
                continue
            if turns:
                return f.stem, turns
        return "", []

    @staticmethod
    def _recorded(t: dict) -> dict:
        return {"ime": t["ime"], "adresa": t.get("adresa", ""), "grupa": t.get("grupa", ""), "uloga": t.get("uloga", ""),
                "od": int(t["od"]), "do": int(t["do"]), "sekundi": int(t["do"] - t["od"]),
                "video": t.get("video") or "", "datoteka": t.get("datoteka") or "", "snimak": t.get("snimak")}

    def _named(self, turns: list[dict], merge: bool = True) -> list[dict]:
        """Turns as shown: a name read before the list knew it (or half read) given the MP's name from the list,
        the line under it written as the list writes it, and one speaker's turns in a row taken as one (18 Nov
        2026: "Hubač KU Željko", "2 KE Mo Jugoslav Gašić", a speech cut into five)."""
        from .caption import role
        out: list[dict] = []
        for t in turns:
            if self.roster:
                if self._memo.get("roster") is not self.roster:
                    self._memo = {"roster": self.roster}
                person = Person(t["key"], t["name"], t["slug"], t["group"])
                if not t["slug"]:
                    k = ("name", t["name"])
                    if k not in self._memo:
                        self._memo[k] = self.roster.match(t["name"], config.MATCH)
                    found = self._memo[k]
                    if found:
                        person = found
                        t = {**t, "key": found.key, "name": found.name, "slug": found.slug, "group": found.group}
                if t.get("role"):
                    k = ("role", t["role"], person.group)
                    if k not in self._memo:
                        self._memo[k] = role(t["role"], person, self.roster, config.MATCH)
                    t = {**t, "role": self._memo[k]}
            last = out[-1] if out else None
            if merge and last and last["key"] == t["key"] and t["start"] - last["seen"] <= config.MERGE_SECONDS:
                out[-1] = {**last, "seen": t["seen"], "n": last["n"] + t["n"], "role": last["role"] or t["role"],
                           "sq_seen": t.get("sq_seen", last.get("sq_seen"))}
            else:
                out.append(t)
        return out

    def snapshot(self, now: float | None = None) -> dict:
        """The state for the page. Kept a second (and dropped with each frame read): thousands of open pages and
        other sites ask for it every few seconds, and each answer used to compute it anew under the lock."""
        if now is None:
            kept = self._snap
            if kept and time.time() - kept[0] < 1.0:
                return kept[1]
            snap = self._snapshot(None)
            self._snap = (time.time(), snap)
            return snap
        return self._snapshot(now)

    def _snapshot(self, now: float | None) -> dict:
        today = self._day(time.time() if now is None else now)
        with self._lock:
            current = self._out(self._named([self.turns[-1]])[0]) if self.open and self.turns else None
            # A turn read in a single frame is shown while it lasts, and left out of the day's list after.
            done = [self._out(t) for t in self._named(
                [t for t in self.turns if counted(t) and not (self.open and t is self.turns[-1])])]
            day = self.day  # the day of the last frame: past midnight with no frame yet, an earlier one
            recorded, parts = False, []
            rec = self.recording
            if done and not current and self.status == NO_STREAM and rec and rec["dan"] == self.day:
                # Today's sitting is over and the site has the day read from the recording: that list, with its
                # links into the Assembly's archive (the YouTube video goes private after the broadcast, 18 Nov 2026).
                recorded, parts = True, [p for p in rec.get("datoteke") or []
                                         if p.get("url") and p.get("od") and p.get("trajanje")]
                done = [self._recorded(t) for t in rec["govori"] if t.get("okvira", 0) >= 2]
            elif not done and not current:
                day, turns = self._last_day()
                day, done = (day, [self._out(t) for t in self._named(turns)]) if turns else (self.day, [])
                rec = self.recording
                if rec and rec["dan"] < today and (not done or rec["dan"] >= day):
                    day, recorded, parts = rec["dan"], True, [p for p in rec.get("datoteke") or []
                                                              if p.get("url") and p.get("od") and p.get("trajanje")]
                    done = [self._recorded(t) for t in rec["govori"] if t.get("okvira", 0) >= 2]
            if self.status == NO_STREAM:  # no broadcast: a link into its YouTube video would lead to a private video
                done = [{**d, "snimak": None} if not d.get("datoteka") else d for d in done]
            if current and current["adresa"] in self.facts:
                current["o"] = self.facts[current["adresa"]]
            self._lists(done, current, recorded)
            if current:
                self._today(done, current, day)
            said = self._said_of(day)
            if said:  # how many words were written down of each turn, and the end of what the speaker is saying
                for d in done + ([current] if current else []):
                    text = self._text(said, d["od"], d["do"])
                    d["reci"] = len(text.split())
                    if d is current and text:
                        d["prepis"] = text[-SAID_TAIL:]
            coming = self.waiting.get("sazvano") if isinstance(self.waiting, dict) else None
            if not (isinstance(coming, dict) and str(coming.get("pocinje", ""))[:10] >= today and not current):
                coming = None  # shown only while nobody is on, and not once its day has passed
            news = [n for n in (self.waiting.get("obavestenja") or []) if isinstance(n, dict) and n.get("tekst")
                    and str(n.get("od", "")) <= today <= (str(n.get("do", "")) or "9999")] if isinstance(self.waiting, dict) else []
            return {"stanje": self.status, "provereno": int(self.last_frame), "sada": current, "sazvano": coming,
                    "obavestenja": news[:3],
                    "dan": day, "ranije": day != today, "snimak": recorded, "datoteke": parts,
                    "danas": done[::-1]}

    def _lists(self, done: list[dict], current: dict | None, recorded: bool) -> None:
        """Each turn's list ("lista"), for the day's time by list: the line under the name, or the MP's group, when it
        is a list the site names; "*" for a sitting MP of none of those (a smaller list the caption abbreviates, or
        no group) and "" for anyone else (ministers, guests). A day read from the recording says it itself."""
        known = set(self.roster.groups) if self.roster and not recorded else None
        for d in done + ([current] if current else []):
            mine = [x for x in ((d.get("o") or {}).get("lista"), d.get("uloga"), d.get("grupa")) if x]
            d["lista"] = next((x for x in mine if known is None or x in known),
                              "*" if d.get("adresa") in self.facts else "")

    @staticmethod
    def _today(done: list[dict], current: dict, day: str) -> None:
        """The speaker's day so far, by the same rule for every speaker: which turn of theirs this is, their time
        today and its place among today's speakers; how many of today's finished turns this one has outlasted (with
        five or more to compare with); and their time in the convocation, the site's sum of the days read plus today."""
        sums: dict[str, int] = {}
        for d in done + [current]:
            sums[d["ime"]] = sums.get(d["ime"], 0) + max(0, d["sekundi"])
        mine = sum(1 for d in done if d["ime"] == current["ime"]) + 1
        total = sums[current["ime"]]
        current["danas"] = {"n": mine, "sek": total, "mesto": 1 + sum(1 for v in sums.values() if v > total),
                            "od": len(sums)}
        if len(done) >= 5:
            current["duze"] = round(100 * sum(1 for d in done if d["sekundi"] < current["sekundi"]) / len(done))
        sv = (current.get("o") or {}).get("sv")
        if sv:
            more = sv.get("do", "") < day  # the site's sum doesn't hold today yet
            current["saziv"] = {"broj": sv.get("saziv", ""), "sek": sv["sek"] + (total if more else 0),
                                "n": sv["n"] + (mine if more else 0)}

    def record(self, day: str) -> dict | None:
        """A day's record, as published at /dan/<date>.json: every turn (with how many frames named the speaker,
        so a reader can leave out one-frame readings), where each is in the broadcast, and when the broadcast was
        seen at all."""
        with self._lock:
            if day == self.day:
                turns, cover = list(self.turns), list(self.cover)
            else:
                f = self._file(day)
                if not f or not f.exists():
                    return None
                kept = json.loads(f.read_text(encoding="utf-8"))
                turns, cover = kept.get("turns", []), kept.get("cover", [])
        return {
            "dan": day,
            "napomena": "Pročitano automatski iz potpisa u prenosu Skupštine; može da sadrži greške. Van 'pokriveno' "
                        "servis prenos nije video.",
            "pokriveno": [{"od": int(a), "do": int(b)} for a, b in cover],
            "govori": [{"ime": t["name"], "adresa": t["slug"], "grupa": t["group"], "uloga": t["role"],
                        "od": int(t["start"]), "do": int(t["seen"]), "okvira": t["n"] if counted(t) or t["n"] < 2 else 1,  # a turn not kept reads as a single frame to the site, which drops those
                        "video": t.get("video", ""),
                        "sq_od": t.get("sq_start"), "sq_do": t.get("sq_seen"), "segment": t.get("seg")}
                       for t in (self._named(turns, merge=False) if self.roster else turns)],
        }

    def days_kept(self) -> list[str]:
        if not self.days or not self.days.exists():
            return [self.day] if self.turns or self.cover else []
        return sorted({p.stem for p in self.days.glob("*.json")} | ({self.day} if self.turns or self.cover else set()))
