"""The groups' time in the debate of the agenda item under way, as an estimate by our own rule (22 Nov 2026, the
maintainer's request after readers asked "how much time does each party have left"). No HTML here: page._group_time
draws it.

By the Rules of Procedure: in the basic procedure the groups have five hours in all for the debate in principle,
shared in proportion to their MPs (art. 97); in the debate in detail as much again, and each group's chair 15 minutes
more (art. 158); in the shortened procedure half (art. 99). The proposer and the Government speak outside the groups'
time (art. 96), replies and points of order last two minutes at most (art. 103, 104). Each group's chair or
representative has 20 minutes besides (art. 96), kept apart from the group's time by the Assembly's own clock (the
notes: "iskoristili ste vreme ovlašćenog predstavnika. Imate još od vremena grupe 7,24"); we do not hear which turn
uses them, so they are added to what each group has (24 Nov 2026), as the 15 minutes of the debate in detail are.

What we can know and what we cannot: the time is the time we know a speaker by the caption, the chair's words or the
voice, not the Assembly's clock; we do not hear whether the item runs in the shortened procedure or whether the Assembly gave the
groups more time (art. 97, para. 3), so the page shows the basic procedure's five hours and says so. The same rule
for every group:
- the debate runs from its opening by the chair, or where none was heard from the move to the item (`Tracker.item`,
  kept across days), to now (24 Nov 2026: a point of order between the two had been counted); a debate closed and a
  new one opened after it (the debate in detail) starts the count again;
- a turn counts when it is a sitting MP's of a group the site names (its "lista") and lasts more than REPLY seconds
  (a reply or a point of order is two minutes at most), and is not heard to be one of these though it ran over them
  (`rok.short`: up to REPLY_OVER seconds; 24 Nov 2026: a reply of 142 s was counted), the chair's "po kom osnovu?"
  when giving the floor telling it too;
- each group's share is the hours times its MPs over all the groups' MPs (MPs of no group are not shared out), and
  its chair's or representative's minutes more."""
from __future__ import annotations

import re

TOTAL = 5 * 3600  # art. 97: the groups' time in all, the basic procedure
REPRESENTATIVE = 20 * 60  # art. 96: each group's chair or representative, in the debate in principle, apart from TOTAL
CHAIR_MORE = 15 * 60  # art. 158: each group's chair, in the debate in detail
REPLY_OVER = 180  # seconds: a turn heard to be a reply or a point of order is none of the group's up to this long
REPLY = 125  # seconds: a turn this long or shorter is taken for a reply or a point of order (two minutes, art. 103, 104)


# The time left as the chair says it when giving the floor ("po pretresu, sad ću vam reći vreme, 23 minuta 21 sekunda"):
# minutes with seconds, or minutes after "još"/"preostalo". The Assembly's own clock, so it is where the count goes on from.
_TOLD = re.compile(r"\b(\d{1,3}) minut\w*,? (?:i )?(\d{1,2}) sekund|\b(?:još|preostal\w+|ostal\w+)(?: vam)?(?: je)? (\d{1,3}) minut", re.I)


def told(said: dict[str, str], people: list) -> list[tuple[int, str, int]]:
    """(when, the group, seconds left) each time the chair's words give one sitting MP the floor and say the time
    left in the same piece. Nothing where two MPs are named, where the MP has no group, or where no time is said."""
    from . import hronika
    out = []
    for k, text in said.items():
        key = k.lstrip("p")
        m = _TOLD.search(text) if key.isdigit() else None
        if not m:
            continue
        given = hronika.floor(text, people, now_only=True)
        if len(given) != 1 or not given[0].group:
            continue
        left = int(m.group(1)) * 60 + int(m.group(2)) if m.group(1) else int(m.group(3)) * 60
        if left >= 180:  # under three minutes it is a reply's time, not the group's
            out.append((int(key), given[0].group, left))
    return sorted(out)


def phase(events: list[dict], start: int) -> tuple[int, bool, bool]:
    """From the events of the item's days: when the debate being counted began, whether it is the debate in detail
    (a debate closed and another opened after it), and whether it has been closed."""
    begun, detail, closed, opened = start, False, False, False
    for e in sorted(events, key=lambda e: e["t"]):
        if e["t"] < start:
            continue
        kind = e.get("vrsta", "")
        if kind == "Pretres zaključen":
            closed = True
        elif kind == "Pretres otvoren" and closed:
            # "jedinstveni pretres" (a decision, art. 192) has no debate in detail, so no more time for it
            begun, detail, closed = e["t"], "jedinstven" not in e.get("tekst", "").lower(), False
        elif kind == "Pretres otvoren" and not opened:
            begun, opened = e["t"], True
    return begun, detail, closed


def groups_time(*, item: int, start: int, seats: dict[str, int], turns: list[dict], events: list[dict],
                now: int, told: list[tuple[int, str, int]] = ()) -> dict | None:
    """The groups' time in the debate of item `item`, moved to at `start`: {"tacka", "od", "pojedinosti",
    "zakljucen", "grupe": [{"lista", "mesta", "ima", "potroseno", "govora"}]}, the groups with most MPs first. None
    without groups or without a turn counted."""
    if not item or not start or not seats or now < start:
        return None
    begun, detail, closed = phase(events, start)
    whole = sum(seats.values())
    used: dict[str, list[int]] = {g: [0, 0] for g in seats}
    for d in turns:
        g = d.get("lista") or ""
        if g not in used or d["od"] < begun or d["sekundi"] <= REPLY or d.get("kratko") or d.get("predlagac"):
            continue  # a reply or a point of order, or the proposer's word (no limit, art. 96: none of the group's)
        used[g][0] += d["sekundi"]
        used[g][1] += 1
    if not any(v[1] for v in used.values()):
        return None
    rows = [{"lista": g, "mesta": n, "ima": round(TOTAL * n / whole) + (CHAIR_MORE if detail else REPRESENTATIVE),
             "potroseno": used[g][0], "govora": used[g][1]} for g, n in seats.items()]
    for r in rows:
        # The chair said how much the group has left (24 Nov 2026: 23 min 21 s said while our count stood at 3 min,
        # and at "over by 16 min" a quarter of an hour later): from there on the count is what was said, less the
        # group's turns since. The newest such word in this debate; one that says more than the group can have is none.
        said = [(t, left) for t, g, left in told if g == r["lista"] and begun <= t <= now and left <= r["ima"]]
        if said:
            t0, left = said[-1]
            # a turn's part after the word counts: the page joins a speaker's turns two minutes apart, so the turn
            # given the floor with that word may have begun before it (the same evening: 23 minutes of it not taken off)
            mine = [d for d in turns if (d.get("lista") or "") == r["lista"] and not d.get("kratko") and not d.get("predlagac")]
            after = [min(d.get("do", d["od"] + d["sekundi"]), now) - max(d["od"], t0) for d in mine]
            since = sum(x for x in after if x > REPLY)
            # what our own count said was left at that moment, kept beside the chair's figure: how far off we were
            ours = r["ima"] - sum(min(d.get("do", d["od"] + d["sekundi"]), t0) - d["od"] for d in mine
                                  if begun <= d["od"] < t0 and d["sekundi"] > REPLY)
            r["potroseno"], r["receno"] = r["ima"] - left + since, {"t": t0, "sek": left, "nase": ours}
    rows.sort(key=lambda r: (-r["mesta"], r["lista"]))
    return {"tacka": item, "od": begun, "pojedinosti": detail, "zakljucen": closed, "grupe": rows}
