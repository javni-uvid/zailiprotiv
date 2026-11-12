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


def act_name(text: str) -> str:
    t = _plain(text)
    t = re.sub(r"^[\s\d.]+", "", t)  # "20. ", "28. 11. ", "1.1. "
    t = re.sub(r"^predlog\s+zakona\b", "zakon", t)  # the bill's name → the law's
    t = re.sub(r"^predlog\s+", "", t)
    t = re.split(r",?\s+koj[ie]\s+(?:je|su)\s+podne", t)[0]
    t = re.sub(r"\s+", " ", t).strip(" .;,")
    return t


def matches(vote_item: str, law_title: str) -> bool:
    v, law = act_name(vote_item), act_name(law_title)
    return bool(law) and (v == law or v.startswith(law + " ") or v.startswith(law + ","))


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
        out[key] = {"votes": on, "final_vote": final}
    return out
