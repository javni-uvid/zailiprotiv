"""How long the turn now on may last, where it is heard what it is: a reply or a point of order, two minutes at most
(Rules of Procedure, art. 103 and 104). 24 Nov 2026, the maintainer. Anything else has no clock we know: a group's
representative has twenty minutes but may speak more by the chair's leave, the proposer and the Government have none.

Heard in what the chair said when giving the floor (the last 45 s) or in the speaker's first words: "povreda
Poslovnika" (and "reklamiram povredu"), "replika". Both words heard, or neither kind told apart: no name, the two
minutes alone. A turn that has gone on past it by more than half a minute is no such turn, or was let on: nothing is
shown then. The same rule for every speaker."""
from __future__ import annotations

import re

LIMIT = 120  # seconds (art. 103, para. 4; art. 104, para. 4)
OVER = 30  # seconds past it before the limit is no longer shown
BEFORE, AFTER = 45, 12  # seconds around the turn's beginning whose words count

_ORDER = re.compile(r"\bpovred[aeu] (?:\w+ )?(?:poslovnik|poslani)|\breklamira\w* povred|\bukaz\w+ na povred", re.I)
_REPLY = re.compile(r"\brepli[kc]", re.I)


def limit(said: dict[str, str], start: float, seconds: int) -> dict | None:
    """{"vrsta": "replika" | "povreda" | "", "sek": LIMIT} of the turn begun at `start`, `seconds` long so far; None
    when nothing heard tells."""
    if seconds > LIMIT + OVER:
        return None
    heard = []
    for k, text in said.items():
        key = k.lstrip("p")
        if not key.isdigit():
            continue
        at = int(key)
        if (k[:1] == "p" and start - BEFORE <= at <= start + 2) or (k[:1] != "p" and start - AFTER <= at <= start + AFTER):
            heard.append((at, text))
    text = " ".join(t for _, t in sorted(heard))
    order, reply = bool(_ORDER.search(text)), bool(_REPLY.search(text))
    if not (order or reply):
        return None
    return {"vrsta": "" if order and reply else "povreda" if order else "replika", "sek": LIMIT}
