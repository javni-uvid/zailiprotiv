"""Which roll calls were on which law.

A roll call names its agenda item ("20. Предлог закона о потврђивању …, који је поднела Влада"); the page of
adopted laws names the law ("Zakon o potvrđivanju …"). Both are reduced to the act's plain name ("zakon o
potvrdjivanju …": Latin, lowercase, no diacritics, no item number, no proposer), and a roll call is on a law when
its name is the law's or starts with it (an item may join several acts: "… о буџету …, са Предлогом одлуке …"),
and it was taken between the bill's submission and the law's passing. The final vote is the one on the day the
law passed, on the act as a whole where the PDF says so, otherwise that day's last.
"""

from __future__ import annotations

import re

from zailiprotiv.kinds import _plain

# Below this share of words in common, two names are different acts.
CLOSE = 0.9


def act_name(text: str) -> str:
    t = _plain(text)
    t = re.sub(r"^[\s\d.]+", "", t)  # "20. ", "28. 11. ", "1.1. "
    t = re.sub(r"^predlog\s+zakona\b", "zakon", t)  # the bill's name → the law's
    t = re.sub(r"^predlog\s+", "", t)
    t = re.sub(r"^zakona\s+o\b", "zakon o", t)  # a typo on the page of adopted laws
    t = re.split(r",?\s+koj[ie]\s+(?:je|su)\s+podne", t)[0]
    return words(t)


def words(text: str) -> str:
    """Letters and digits only, one space apart: quotes, dashes and commas don't tell acts apart."""
    return " ".join(re.findall(r"[0-9a-z]+", text))


def closeness(a: str, b: str) -> float:
    """The share of words two names have in common (Jaccard)."""
    x, y = set(a.split()), set(b.split())
    return len(x & y) / len(x | y) if x | y else 0.0


def matches(vote_item: str, law_title: str) -> bool:
    v, law = act_name(vote_item), act_name(law_title)
    return bool(law) and (v == law or v.startswith(law + " "))


FINAL_KIND = "у целини"


def link(laws: dict[str, dict], votes: dict[str, dict]) -> dict[str, dict]:
    """For each law (by key), the keys of the roll calls on it and of its final vote."""
    by_day: dict[str, list[str]] = {}
    for key, v in votes.items():
        by_day.setdefault(v["when"][:10], []).append(key)
    out = {}
    for key, law in laws.items():
        lo, hi = law.get("submitted") or "0000", law.get("passed") or "9999"
        on = sorted((k for day, ks in by_day.items() if lo <= day <= hi for k in ks
                     if matches(votes[k]["item"], law["title"]) or matches(votes[k].get("listed_as", ""), law["title"])),
                    key=lambda k: votes[k]["when"])
        that_day = [k for k in on if votes[k]["when"][:10] == law.get("passed")]
        whole = [k for k in that_day if FINAL_KIND in votes[k].get("kind", "") or FINAL_KIND in votes[k]["item"]]
        final = (whole or that_day or [None])[-1]
        out[key] = {"votes": on, "final_vote": final, "matched": "exact" if final else None}
    _close(laws, votes, by_day, out)
    return out


def _close(laws, votes, by_day, out) -> None:
    """For laws left without a final vote: that day's vote whose name shares most words with the law's, when it
    shares at least CLOSE of them, no other vote comes as close, and no other law took it."""
    taken = {r["final_vote"] for r in out.values() if r["final_vote"]}
    for key, law in laws.items():
        if out[key]["final_vote"]:
            continue
        name = act_name(law["title"])
        scored = sorted(((max(closeness(name, act_name(votes[k]["item"])),
                              closeness(name, act_name(votes[k].get("listed_as", "")))), k)
                         for k in by_day.get(law.get("passed"), []) if k not in taken), reverse=True)
        if not scored or scored[0][0] < CLOSE:
            continue
        best = [k for score, k in scored if score == scored[0][0]]
        if len(best) > 1 and len({act_name(votes[k]["item"]) for k in best}) > 1:
            continue  # two different acts come equally close: leave it to a person
        same = sorted(best, key=lambda k: votes[k]["when"])
        whole = [k for k in same if FINAL_KIND in votes[k].get("kind", "")]
        final = (whole or same)[-1]
        out[key] = {"votes": sorted(set(out[key]["votes"]) | set(same), key=lambda k: votes[k]["when"]),
                    "final_vote": final, "matched": "close"}
        taken.add(final)
