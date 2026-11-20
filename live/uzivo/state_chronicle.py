"""What happened in the sitting, a line a step (hronika.py), the agenda's progress and the Assembly's pages already
read.

A part of state.Tracker (a mixin): it uses the tracker's own fields and lock."""
from __future__ import annotations

import json
from pathlib import Path

from .state_base import _write


class Chronicle:
    # --- what happened in the sitting, a line a step (hronika.py) ---
    def _events_file(self, day: str) -> Path | None:
        return self.days.parent / "hronika" / f"{day}.json" if self.days else None

    def _events_load(self, day: str) -> list[dict]:
        f = self._events_file(day)
        try:
            if f and f.exists():
                rows = json.loads(f.read_text(encoding="utf-8"))
                return [r for r in rows if isinstance(r, dict) and r.get("tekst")] if isinstance(rows, list) else []
        except (OSError, ValueError):
            pass
        return []

    def note(self, ts: float, kind: str, text: str, source: str, url: str = "", more: dict | None = None) -> bool:
        """A line of the day: when, what it is called, the sentence, where it is from ("prepis", "model" or "sajt"),
        and for the model's steps what it read besides (`more`: the item's number, to whom, who was elected…). The
        same sentence from the same source twice within ten minutes is one line (a piece of sound may be heard again
        at a seam; the model and the rules may find the same sentence, and both are kept)."""
        text = " ".join(str(text).split())
        with self._lock:
            if not text or self._day(ts) != self.day:
                return False
            if any(e["tekst"] == text and e.get("izvor") == source and e.get("vrsta") == kind and abs(e["t"] - ts) < 600
                   for e in self.events[-80:]):
                return False
            self.events.append({"t": int(ts), "vrsta": kind, "tekst": text, "izvor": source, "url": url,
                                **({"vise": more} if more else {})})
            if kind == "Tačka dnevnog reda" and source in ("prepis", "model"):  # the item moved to, kept across days
                from .hronika import item_no
                n = item_no(text)
                if source == "model":
                    try:
                        n = int((more or {}).get("tacka") or 0)
                    except (TypeError, ValueError):
                        n = 0
                if n > self.item.get("n", 0):
                    self.item = {"n": n, "t": int(ts)}
                    f2 = self.days.parent / "tacka.json" if self.days else None
                    try:
                        if f2:
                            _write(f2, self.item)
                    except OSError:
                        pass
            self.events.sort(key=lambda e: e["t"])
            self._snap = None
            f = self._events_file(self.day)
            if f:
                try:
                    f.parent.mkdir(parents=True, exist_ok=True)
                    tmp = f.with_suffix(".tmp")
                    tmp.write_text(json.dumps(self.events, ensure_ascii=False), encoding="utf-8")
                    tmp.replace(f)
                except OSError:
                    pass
            return True

    def _agenda(self) -> dict | None:
        """The sitting's agenda from the site (as the Assembly lists it), each item with where it stands: done by the
        Assembly's page ("sajt"), done or under way by what the chair said aloud ("prepis": moving to item N says
        the ones before it are over), or the next in turn."""
        rows = self.waiting.get("dnevni_red") if isinstance(self.waiting, dict) else None
        if not rows or not isinstance(rows, list) or not rows[0].get("tacke"):
            return None
        s = rows[0]
        heard = int(self.item.get("n", 0) or 0)
        if heard > len(s["tacke"]):
            heard = 0  # a number the agenda does not have: misheard
        out = []
        for x in s["tacke"]:
            n = int(x["n"])
            if x.get("gotova"):
                state, src = "gotova", "sajt"
            elif heard and n < heard:
                state, src = "gotova", "prepis"
            elif heard and n == heard:
                state, src = "u_toku", "prepis"
            else:
                state, src = "", ""
            out.append({"n": n, "tekst": x["tekst"], "stanje": state, "izvor": src, "kada": x.get("kada", ""), "sta": x.get("sta", "")})
        if not any(x["stanje"] == "u_toku" for x in out):  # nothing heard as under way: the first not done is next
            first = next((x for x in out if not x["stanje"]), None)
            if first:
                first["stanje"] = "na_redu"
        return {"naslov": s.get("naslov", ""), "url": s.get("url", ""), "tacke": out}

    def page_seen(self, url: str, sentences: list[str] | None = None) -> list[str]:
        """The sentences already read on a page of the Assembly, kept across restarts (hronika.Watcher)."""
        f = self.days.parent / "strane.json" if self.days else None
        try:
            kept = json.loads(f.read_text(encoding="utf-8")) if f and f.exists() else {}
        except (OSError, ValueError):
            kept = {}
        if sentences is not None and f:
            kept[url] = sentences
            try:
                _write(f, kept)
            except OSError:
                pass
        return list(kept.get(url) or [])
