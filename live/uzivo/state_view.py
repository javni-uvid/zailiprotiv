"""The state as the page and /stanje.json have it: the snapshot, drawn from the turns, the recording, the transcript
and the site's facts.

A part of state.Tracker (a mixin): it uses the tracker's own fields and lock."""
from __future__ import annotations

import json
import time

from . import config
from .names import Person
from .state_base import NO_STREAM, SAID_TAIL, counted


class View:
    @staticmethod
    def _out(t: dict) -> dict:
        rec = None
        if t.get("video") and t.get("sq_start") is not None and t.get("seg"):
            rec = int(max(0, t["sq_start"] - config.RECORDING_LEAD) * t["seg"])
        return {"ime": t["name"], "adresa": t["slug"], "grupa": t["group"], "uloga": t["role"],
                "od": int(t["start"]), "do": int(t["seen"]), "sekundi": int(t["seen"] - t["start"]),
                "video": t.get("video") or "", "snimak": rec, **({"izvor": t["izvor"]} if t.get("izvor") else {})}

    def _last_day(self) -> tuple[str, list[dict]]:
        """The latest earlier day with turns: its list stays on the page until the next sitting's broadcast is on."""
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
            # One thread computes it; the others take the last one meanwhile rather than queue on the lock and
            # compute the same again (20 Nov 2026: a day with a long transcript took 0.3 s a snapshot).
            if not self._snapping.acquire(blocking=kept is None):
                return kept[1]
            try:
                kept = self._snap
                if kept and time.time() - kept[0] < 1.0:
                    return kept[1]
                frames = self._frames
                snap = self._snapshot(None)
                if frames == self._frames:  # no frame read meanwhile: it is still the latest
                    self._snap = (time.time(), snap)
                return snap
            finally:
                self._snapping.release()
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
            elif not done and not current and (self.status == NO_STREAM or self.day != today):
                # Not once today's broadcast is on (24 Nov 2026): the chair alone spoke, and the page went on telling
                # what happened on 19 November under "Uživo".
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
            groups = self._group_time(done + ([current] if current else [])) if day == self.day and not recorded else None
            if current:
                self._today(done, current, day)
                from .rok import limit
                current["rok"] = limit(self._said_of(day), current["od"], current["sekundi"])
            # Not while the transcript is not shown (config.SHOW_TRANSCRIPT): /stanje.json carried the speaker's
            # last words and the chair's though the page showed none of them (20 Nov 2026).
            said = self._said_of(day) if config.SHOW_TRANSCRIPT else {}
            unsigned = None
            if said:  # how many words were written down of each turn, and the end of what the speaker is saying
                for d in done + ([current] if current else []):
                    text = self._text(said, d["od"], d["do"])
                    d["reci"] = len(text.split())
                    if d is current and text:
                        d["prepis"] = self.shown(text[-SAID_TAIL:])
                if not current:  # nobody's caption on: what the chair (or the hall) is saying, when it is fresh
                    runs = self._unsigned(said)
                    if runs and self.last_frame - runs[-1]["do"] < 240 and day == self.day:
                        unsigned = {"od": runs[-1]["od"], "tekst": self.shown(runs[-1]["tekst"][-SAID_TAIL:])}
            coming = self.waiting.get("sazvano") if isinstance(self.waiting, dict) else None
            if not (isinstance(coming, dict) and str(coming.get("pocinje", ""))[:10] >= today and not current):
                coming = None  # shown only while nobody is on, and not once its day has passed
            news = [n for n in (self.waiting.get("obavestenja") or []) if isinstance(n, dict) and n.get("tekst")
                    and str(n.get("od", "")) <= today <= (str(n.get("do", "")) or "9999")] if isinstance(self.waiting, dict) else []
            return {"stanje": self.status, "provereno": int(self.last_frame), "sada": current, "sazvano": coming,
                    "obavestenja": news[:3], "dnevni_red": self._agenda(), "bez_potpisa": unsigned, "hronika": [e if e.get("izvor") == "sajt" else {**e, "tekst": self.shown(e.get("tekst", ""))}
                                for e in (self.events if day == self.day else self._events_load(day))[-150:][::-1]],
                    "dan": day, "ranije": day != today, "snimak": recorded, "datoteke": parts,
                    "danas": done[::-1], "sazetak": self._summary_shown(day), "titl": self._captions_shown(),
                    "vreme_grupa": groups, "predsedava": self._presiding_shown()}

    def _presiding_shown(self) -> dict | None:
        """Who presides, by the voice, while a broadcast is on and the chair was heard in the last quarter of an hour."""
        p = getattr(self, "presiding", None) or {}
        if not p or self.status == NO_STREAM or self.last_frame - p.get("do", 0) > 900:
            return None
        return {"ime": p["ime"], "adresa": p["adresa"]}

    def caption(self, start: float, end: float, text: str, program: float | None = None) -> None:
        """A phrase of the line under the picture (prepis.Captions), with when it begins by the broadcast's clock
        when known: the last eight are kept, in memory only."""
        line = {"od": round(start, 1), "do": round(end, 1), "tekst": text}
        if program is not None:
            line["pt"] = round(program, 2)
        self.captions = (self.captions + [line])[-8:]

    def _captions_shown(self) -> list[dict]:
        """The line's newest lines while a broadcast is on and they are fresh (a minute of the last frame), with the
        corrections of the transcript's spellings; none between sittings or with the line off."""
        if not config.SHOW_CAPTIONS or self.status == NO_STREAM:
            return []
        return [{**c, "tekst": self.shown(c["tekst"])} for c in self.captions if self.last_frame - c["do"] < 60]

    def _summary_shown(self, day: str) -> dict | None:
        """The model's summary as the page shows it (config.SHOW_SUMMARY): the day's once written, else the latest
        stretch summed up. None while it is off the page."""
        if not config.SHOW_SUMMARY:
            return None
        kept = self.summary_of(day)
        whole = kept.get("dan")
        if isinstance(whole, dict) and whole.get("ukratko"):
            return {"vrsta": "dan", **{k: whole.get(k) for k in ("kratko", "ukratko", "odluke")}}
        parts = [p for p in kept.get("delovi") or [] if p.get("ukratko")]
        if parts:
            return {"vrsta": "deo", "do": parts[-1].get("do"), "ukratko": parts[-1]["ukratko"],
                    "tok": parts[-1].get("tok"), "ranije": [p["ukratko"] for p in parts[:-1]]}
        return None

    def _lists(self, done: list[dict], current: dict | None, recorded: bool) -> None:
        """Each turn's list ("lista"), for the day's time by list: the line under the name, or the MP's group, when it
        is a list the site names; "*" for a sitting MP of none of those (a smaller list the caption abbreviates, or
        no group) and "" for anyone else (ministers, guests). A day read from the recording says it itself."""
        known = set(self.roster.groups) if self.roster and not recorded else None
        for d in done + ([current] if current else []):
            mine = [x for x in ((d.get("o") or {}).get("lista"), d.get("uloga"), d.get("grupa")) if x]
            d["lista"] = next((x for x in mine if known is None or x in known),
                              "*" if d.get("adresa") in self.facts else "")

    def _group_time(self, today: list[dict]) -> dict | None:
        """The groups' time in the debate of the item under way (vreme.py), over every day of that debate: today's
        turns as listed, the earlier days' from their files (kept once read: a past day does not change)."""
        from .vreme import groups_time
        n, start = int(self.item.get("n") or 0), int(self.item.get("t") or 0)
        agenda = self._agenda()
        if not n or not start or not self.roster or not agenda or not any(
                x["n"] == n and x["stanje"] == "u_toku" for x in agenda["tacke"]):
            return None
        seats: dict[str, int] = {}
        for p in self.roster.people:
            if p.slug in self.roster.current and p.group in self.roster.groups:
                seats[p.group] = seats.get(p.group, 0) + 1
        turns, events = list(today), list(self.events)
        first = self._day(start)
        cache = self._memo.setdefault("past_days", {})
        for f in sorted(self.days.glob("*.json")) if self.days and self.days.exists() else []:
            if not first <= f.stem < self.day:
                continue
            if f.stem not in cache:
                try:
                    kept = [t for t in json.loads(f.read_text(encoding="utf-8")).get("turns", []) if counted(t)]
                except (OSError, ValueError, KeyError):
                    kept = []
                past = [self._out(t) for t in self._named(kept)]
                self._lists(past, None, False)
                cache[f.stem] = (past, self._events_load(f.stem))
            turns += cache[f.stem][0]
            events += cache[f.stem][1]
        return groups_time(item=n, start=start, seats=seats, turns=turns, events=events, now=int(self.last_frame or time.time()))

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
