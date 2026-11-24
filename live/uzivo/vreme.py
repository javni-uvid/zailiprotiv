"""The groups' time in the debate of the agenda item under way, as an estimate by our own rule (22 Nov 2026, the
maintainer's request after readers asked "how much time does each party have left"). No HTML here: page._group_time
draws it.

By the Rules of Procedure: in the basic procedure the groups have five hours in all for the debate in principle,
shared in proportion to their MPs (art. 97); in the debate in detail as much again, and each group's chair 15 minutes
more (art. 158); in the shortened procedure half (art. 99). The proposer and the Government speak outside the groups'
time (art. 96), replies and points of order last two minutes at most (art. 103, 104).

What we can know and what we cannot: the time is the time we know a speaker by the caption, the chair's words or the
voice, not the Assembly's clock; we do not hear whether the item runs in the shortened procedure or whether the Assembly gave the
groups more time (art. 97, para. 3), so the page shows the basic procedure's five hours and says so. The same rule
for every group:
- the debate runs from its opening by the chair, or where none was heard from the move to the item (`Tracker.item`,
  kept across days), to now (24 Nov 2026: a point of order between the two had been counted); a debate closed and a
  new one opened after it (the debate in detail) starts the count again;
- a turn counts when it is a sitting MP's of a group the site names (its "lista") and lasts more than REPLY seconds
  (a reply or a point of order is two minutes at most);
- each group's share is the hours times its MPs over all the groups' MPs (MPs of no group are not shared out)."""
from __future__ import annotations

TOTAL = 5 * 3600  # art. 97: the groups' time in all, the basic procedure
CHAIR_MORE = 15 * 60  # art. 158: each group's chair, in the debate in detail
REPLY = 125  # seconds: a turn this long or shorter is taken for a reply or a point of order (two minutes, art. 103, 104)


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
                now: int) -> dict | None:
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
        if g not in used or d["od"] < begun or d["sekundi"] <= REPLY:
            continue
        used[g][0] += d["sekundi"]
        used[g][1] += 1
    if not any(v[1] for v in used.values()):
        return None
    rows = [{"lista": g, "mesta": n, "ima": round(TOTAL * n / whole) + (CHAIR_MORE if detail else 0),
             "potroseno": used[g][0], "govora": used[g][1]} for g, n in seats.items()]
    rows.sort(key=lambda r: (-r["mesta"], r["lista"]))
    return {"tacka": item, "od": begun, "pojedinosti": detail, "zakljucen": closed, "grupe": rows}
