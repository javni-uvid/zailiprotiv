"""An MP's offices as small cards beside the portrait (23 Nov 2026, the maintainer's choice of the look; "ne mora samo
rukovodeća funkcija": every office is a card, the first few shown and the rest folded).

One card an office, however many convocations it was held in: what it is of (Skupština, Vlada, Grupa, Odbor,
Delegacija), the office as the Assembly or the decision writes it, linked to the page or the decision it is from, and
when: the days where the source gives them, the year of each election to the Government, the convocations always. The
same rule and order for every MP: the Assembly's Speaker and deputies, the Government, the groups' chairs, then the
committees and delegations, chairs before members; within each the latest convocation first.
"""
from __future__ import annotations

from zailiprotiv import offices, vlada

SHOWN = 4
_LABEL = {"speaker": "Skupština", "vice": "Skupština", "vlada": "Vlada", "group": "Grupa", "committee": "Odbor",
          "delegation": "Delegacija"}
_FIRST = {"speaker": 0, "vice": 1, "vlada": 2, "group": 3}


def listed(xs: list[str]) -> str:
    """["11", "12", "13"] → "11, 12. i 13."; ["14"] → "14."; years as well."""
    if len(xs) == 1:
        return xs[0] + "."
    return ", ".join(xs[:-1]) + ". i " + xs[-1] + "."


def _rank(o: dict) -> tuple:
    if o["kind"] in _FIRST:
        pm = o["kind"] == "vlada" and o["post"].startswith("председника")
        return (_FIRST[o["kind"]], 0 if pm else 1)
    role = o["role"].lower()
    place = next((i for i, x in enumerate(offices._ROLE) if role.startswith(x)), len(offices._ROLE))
    return (4 if place < 2 else 5, place)  # the chairs of committees and heads of delegations, then the rest


def _text(o: dict, latin) -> str:
    return latin(vlada.say(o["post"])) if o["kind"] == "vlada" else offices.say(o, latin)


def cards(rows: list[dict], latin, day) -> list[dict]:
    """`rows` the MP's offices, each with "conv" → [{"label", "text", "when", "source"}], in their order."""
    def on(d: str) -> str:  # "20. marta 2024." : the year's full stop, whether the filter writes it or not
        return day(d).rstrip(".") + "."
    groups: dict[tuple, list[dict]] = {}
    for o in rows:
        groups.setdefault((o["kind"], _text(o, latin)), []).append(o)
    out = []
    for (kind, text), os_ in groups.items():
        os_ = sorted(os_, key=lambda o: (int(o["conv"]), o.get("since", "")))
        convs = list(dict.fromkeys(o["conv"] for o in os_))
        in_convs = listed(convs) + " saziv"
        last = os_[-1]
        if kind == "vlada":
            years = list(dict.fromkeys(o["since"][:4] for o in os_))
            when = f"izbor {listed(years)} · {in_convs}"
            if last.get("until"):
                when += f" · razrešenje {on(last['until'])}"
        elif kind in ("speaker", "vice") and len(os_) == 1 and last.get("dated") and last.get("since"):
            when = f"od {on(last['since'])}" + (f" do {on(last['until'])}" if last.get("until") else "") + f" · {in_convs}"
        else:
            when = in_convs
        out.append({"label": _LABEL.get(kind, ""), "text": text, "when": when, "source": last["source"],
                    "_order": (*_rank(last), -max(int(c) for c in convs), text)})
    out.sort(key=lambda c: c["_order"])
    return [{k: v for k, v in c.items() if k != "_order"} for c in out]
