"""The roll calls that are not a final vote on an adopted law ("Ostala glasanja", 27 Nov 2026).

Elections and appointments, decisions, conclusions, authentic interpretations and bills that were not adopted, as the
Assembly names them: every roll call of a convocation that no adopted law's page lists among its votes. They are shown
as the Assembly's record, the subject written once, on the sitting's page (one anchor each); an MP's page has their
latest ones and their "-glasovi" page every one, linked to it. The same rule for every convocation, the newest one
included before its first law. They enter no count of the site's: presence, the line of a group, agreement, the quiz,
the numbers, rankings and feeds stay on final votes on laws, and their "nije prisutan" is summed nowhere.
"""
from __future__ import annotations

import hashlib
import re
from collections import defaultdict

LATEST = 10  # an MP's page shows this many, the newest first; their "-glasovi" page every one

_BULLET = re.compile(r"^[•\s]+")
_NUMBER = re.compile(r"^(\d+(?:\.\s?\d+)*)\.?\s")


def subject(item: str) -> str:
    """The roll call's subject as the Assembly writes it, without the list bullet some years' PDFs carry."""
    return _BULLET.sub("", item or "").strip()


def point(item: str) -> str:
    """The point of the agenda the subject begins with ("4", "6.1"), or ""."""
    m = _NUMBER.match(subject(item))
    return re.sub(r"\s", "", m.group(1)) if m else ""


def anchor(key: str) -> str:
    """The roll call's anchor on its sitting's page, the same in every build."""
    return "glasanje-" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:8]


def collect(votes_by_conv: dict, linked: set, page_of) -> list[dict]:
    """Every roll call no adopted law lists among its votes, oldest first: {"key", "conv", "subject", "point", "when",
    "counts", "sitting", "sitting_title", "page" (the sitting's page), "anchor", "rows"}."""
    out = []
    for conv, votes in votes_by_conv.items():
        for key, v in votes.items():
            if key in linked:
                continue
            out.append({"key": key, "conv": conv, "subject": subject(v.get("item", "")), "point": point(v.get("item", "")),
                        "when": v.get("when") or "", "counts": v.get("counts") or {}, "sitting": v.get("sitting", ""),
                        "sitting_title": v.get("sitting_title", ""), "page": page_of(v.get("sitting", ""), v.get("sitting_title", "")),
                        "anchor": anchor(key), "rows": v.get("rows") or []})
    out.sort(key=lambda o: (o["when"], o["key"]))
    return out


def by_mp(others: list[dict], key_of) -> dict[str, list[dict]]:
    """An MP's roll calls among them, the newest first: {key_of(name, convocation): [{"o": the roll call, "vote"}]};
    a row whose key_of is None is left out."""
    mine: dict[str, list[dict]] = defaultdict(list)
    for o in others:
        for row in o["rows"]:
            k = key_of(row[1], o["conv"])
            if k is not None:
                mine[k].append({"o": o, "vote": row[2]})
    for rs in mine.values():
        rs.reverse()
    return mine


def by_conv(rows: list[dict], names: dict) -> list[tuple[str, int, list[dict]]]:
    """An MP's rows for their "-glasovi" page: [(convocation's name, how many, [{"page", "day", "rows"}])], the newest
    first, a sitting's rows together (its page's address written once: 230,932 rows in all, 27 Nov 2026)."""
    out = []
    for conv in sorted({r["o"]["conv"] for r in rows}, key=int, reverse=True):
        mine = [r for r in rows if r["o"]["conv"] == conv]
        sittings: dict[str, dict] = {}
        for r in mine:
            s = sittings.setdefault(r["o"]["page"], {"page": r["o"]["page"], "day": r["o"]["when"][:10], "rows": []})
            s["rows"].insert(0, r)  # in the order held
            s["day"] = min(s["day"], r["o"]["when"][:10])
        for s in sittings.values():  # the same vote in a row written once: "4, 5, 6.1: Za"
            s["runs"] = []
            for r in s["rows"]:
                if s["runs"] and s["runs"][-1]["vote"] == r["vote"]:
                    s["runs"][-1]["points"].append(r["o"]["point"] or "—")
                else:
                    s["runs"].append({"vote": r["vote"], "points": [r["o"]["point"] or "—"]})
        out.append((names.get(conv, conv), len(mine), list(sittings.values())))
    return out


def by_sitting(others: list[dict]) -> dict[str, list[dict]]:
    """The roll calls of each sitting, by the address of its page on the Assembly's site, in the order they were held."""
    out: dict[str, list[dict]] = defaultdict(list)
    for o in others:
        out[o["sitting"]].append(o)
    return out
