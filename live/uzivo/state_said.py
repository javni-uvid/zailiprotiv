"""The automatic transcript of the day, a piece at a time (prepis.py writes it): kept, read back, shown with the
corrections.

A part of state.Tracker (a mixin): it uses the tracker's own fields and lock."""
from __future__ import annotations

import json
from pathlib import Path

from .state_base import SAID_LEAD, _write


class Said:
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

    def say(self, ts: float, text: str, chair: bool = False) -> None:
        """A piece of the transcript: the sound from second `ts` on, written down. Kept with the day. `chair`: sound
        in no turn, the chair's or the hall's, kept apart (a key "p<second>") and shown as nobody's by name."""
        text = " ".join(text.split())
        if not text:
            return
        with self._lock:
            day = self._day(ts)
            if day != self.day:
                return
            self.said[("p" if chair else "") + str(int(ts))] = text
            self._snap = None
            f = self._said_file(day)
            if f:
                try:
                    _write(f, self.said)
                except OSError:
                    pass

    def day_heard(self) -> tuple[dict[str, str], list[dict], list[dict]]:
        """Today's transcript in pieces, turns and steps, copies: what the bell finds the end of a break from."""
        with self._lock:
            return dict(self.said), [dict(t) for t in self.turns], [dict(e) for e in self.events]

    def _said_of(self, day: str) -> dict[str, str]:
        if day == self.day:
            return self.said
        if self._said_other[0] != day:
            self._said_other = (day, self._said_load(day))
        return self._said_other[1]

    @staticmethod
    def _text(said: dict[str, str], start: float, end: float) -> str:
        """What was written down of a turn: the pieces that begin within it (a piece is cut where a turn begins)."""
        return " ".join(said[k] for k in sorted((k for k in said if k.isdigit()), key=int) if start - SAID_LEAD - 1 <= int(k) <= end)

    @staticmethod
    def _unsigned(said: dict[str, str]) -> list[dict]:
        """The sound with no caption (the chair's, or the hall's) as written down, in runs: pieces less than a minute
        and a half apart are one. [{"od", "do", "tekst"}], oldest first."""
        out: list[dict] = []
        for k in sorted((k for k in said if k[:1] == "p" and k[1:].isdigit()), key=lambda k: int(k[1:])):
            at = int(k[1:])
            if out and at - out[-1]["do"] <= 90:
                out[-1]["do"], out[-1]["tekst"] = at, out[-1]["tekst"] + " " + said[k]
            else:
                out.append({"od": at, "do": at, "tekst": said[k]})
        return out

    def shown(self, text: str) -> str:
        """The transcript as shown: as written down, with the corrections (ispravke.py)."""
        from . import ispravke
        rules = self.waiting.get("ispravke") if isinstance(self.waiting, dict) else None
        if self.roster is not None and self._forms[0] is not self.roster:
            sitting = [p.name for p in self.roster.people if not self.roster.current or p.slug in self.roster.current]
            self._forms = (self.roster, ispravke.name_forms(sitting))
        return ispravke.apply(text, rules if isinstance(rules, dict) else None, self._forms[1])

    def transcript(self) -> dict:
        """The day on the page, each turn with what was written down of it, newest first: for the transcript's page."""
        snap = self.snapshot()
        with self._lock:
            said = dict(self._said_of(snap["dan"]))
        turns = ([snap["sada"]] if snap["stanje"] == "govori" and snap.get("sada") else []) + snap["danas"]
        out = [{**{k: d[k] for k in ("ime", "adresa", "od", "do", "sekundi")}, "lista": d.get("lista", ""),
                "tekst": self.shown(self._text(said, d["od"], d["do"]))} for d in turns]
        out += [{"ime": "", "adresa": "", "od": r["od"], "do": r["do"], "sekundi": r["do"] - r["od"], "lista": "",
                 "tekst": self.shown(r["tekst"]), "bez": True} for r in self._unsigned(said)]
        out.sort(key=lambda d: -d["od"])
        return {"dan": snap["dan"], "ranije": snap["ranije"], "govori": [d for d in out if d["tekst"]]}
