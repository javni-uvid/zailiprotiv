"""The exchanges of the day, as a conversation: what one MP said and what another replied, by the chair's own word that it
is a reply (24 Nov 2026, the maintainer's choice of three: "Šta se desilo danas" with the words said).

Chosen by what happened, never by tone or by whom: a turn the chair gave as a reply ("replika"; art. 104: one who is
insulted or whose words are misread) is paired with the turn before it, among the last three of others, whose sentence
it takes up: the pair of whole sentences that share the most words rare that day. The chair's warnings are not paired
with a speech: whom one is for is often not said, and a warning to somebody heckling had been put to the speaker (the
same day's try). The same rule for every speaker. Words are the automatic transcript's (it errs, and says so on the
page), whole sentences, never cut inside; each with the moment, so that a reader can hear it. No HTML here."""
from __future__ import annotations

import re

from .rok import limit
from .state_base import CHAIRS

MIN_WORDS, MAX_WORDS = 6, 38  # of a sentence shown
BACK = 3  # turns of others before a reply it may answer
SOON = 420  # seconds from such a turn's end to the reply's beginning
STEM, LEAST = 5, 5  # letters compared of a word, letters of a word that counts
PHRASE = 2.0  # added for two words said one after the other by both ("revizione komisije"): what a reply takes up is a phrase
RARELY = 2.0  # log of the day's turns over the turns a word is in: below this it is everybody's and counts for nothing
WEIGHT = 6.0  # the least of a pair: the shared words' rarity (log of turns in all over turns with it) and the phrases
MOST = 12  # pairs a day
PIECE = 25  # seconds: a piece of the transcript (some 30 s) wholly inside the turn, or its words may be the next speaker's


def sentences(text: str) -> list[str]:
    return [s.strip() for s in re.findall(r"[^.!?…]+(?:[.!?…]+|$)", " ".join(text.split())) if s.strip()]


def stems(text: str) -> set[str]:
    return {w[:STEM].lower() for w in re.findall(r"[^\W\d_]+", text) if len(w) >= LEAST}


def _fit(sentence: str) -> bool:
    return MIN_WORDS <= len(sentence.split()) <= MAX_WORDS and sentence[-1] in ".!?" and not CHAIRS.search(sentence)


def _spoken(said, keys, turn) -> list[tuple[int, str]]:
    """The turn's whole sentences, (the second of its piece, the sentence)."""
    return [(a, s) for a, k in keys if k[0] != "p" and turn["od"] + 2 <= a and a + PIECE <= turn["do"]
            for s in sentences(said[k]) if _fit(s)]


def _words(text: str) -> list[str]:
    return [w[:STEM].lower() for w in re.findall(r"[^\W\d_]+", text) if len(w) >= 3]


def _score(sa: str, sb: str, rare) -> float:
    """How much a sentence takes up another: the rarity of the words both have, and of the pairs of words in a row."""
    wa, wb = _words(sa), _words(sb)
    shared = {w for w in set(wa) & set(wb) if len(w) >= LEAST and rare(w) >= RARELY}
    if len(shared) < 2:
        return 0.0
    total = sum(rare(w) for w in shared)
    runs = {x for x in zip(wa, wa[1:])} & {x for x in zip(wb, wb[1:])}
    return total + PHRASE * sum(1 for x, y in runs if x in shared and y in shared)


def find(said: dict[str, str], turns: list[dict]) -> list[dict]:
    """[{"t": the reply's beginning, "prvi": {"ime", "adresa", "lista", "tekst", "t"}, "odgovor": the same}], oldest first."""
    from math import log
    keys = sorted((int(k.lstrip("p")), k) for k in said if k.lstrip("p").isdigit())
    turns = sorted(turns, key=lambda t: t["od"])
    own = {i: _spoken(said, keys, t) for i, t in enumerate(turns)}
    seen: dict[str, int] = {}
    for i in own:
        for w in {w for _, s in own[i] for w in stems(s)}:
            seen[w] = seen.get(w, 0) + 1
    rare = lambda w: max(0.0, log(max(1, len(turns)) / seen.get(w, 1)))
    got: list[tuple[float, dict]] = []
    for i, b in enumerate(turns):
        kind = limit(said, b["od"], 0)
        if not kind or kind["vrsta"] not in ("replika", ""):
            continue
        before = [j for j in range(i - 1, -1, -1) if turns[j]["ime"] != b["ime"] and b["od"] - turns[j]["do"] <= SOON][:BACK]
        theirs = [(at, s) for at, s in own[i] if at >= b["od"] - 3]
        best = None
        for j in before:
            for ta, sa in own[j]:
                if ta >= b["od"] - 3:
                    continue  # a piece over the seam, the reply's own
                for tb, sb in theirs:
                    if sa == sb:
                        continue
                    w = _score(sa, sb, rare)
                    if w >= WEIGHT and (best is None or w > best[0]):
                        best = (w, j, ta, sa, tb, sb)
        if best:
            w, j, ta, sa, tb, sb = best
            a = turns[j]
            who = lambda t, s, at: {"ime": t["ime"], "adresa": t.get("adresa", ""), "lista": t.get("lista", ""), "tekst": s, "t": at}
            got.append((w, {"t": int(b["od"]), "prvi": who(a, sa, ta), "odgovor": who(b, sb, tb)}))
    got.sort(key=lambda x: -x[0])
    return sorted((r for _, r in got[:MOST]), key=lambda r: r["t"])
