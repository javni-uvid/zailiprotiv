"""What an MP most often says in the debates read: the material for a model's overview, and the check of its reply.

Only speeches made as an MP count: the speaker is on a roll call within two months of the day (a minister is not).
The rules the model writes under are in data/profiles/RULES.md.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from collections import defaultdict
from pathlib import Path

from zailiprotiv import debates, mps

MODEL_WORDS, CUT, LONG = 18000, 700, 120


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[„“”\"'’]", "", text)).strip().lower()


def speeches(root: Path) -> dict[str, list[dict]]:
    """Every speech made as an MP in the notes read, by the speaker's name key (words sorted)."""
    seated: dict[str, list[str]] = defaultdict(list)
    for f in root.glob("*/votes/*.json"):
        votes = json.loads(f.read_text(encoding="utf-8"))["votes"]
        for v in (votes.values() if isinstance(votes, dict) else votes):
            if isinstance(v, dict):
                for _, name, _, _ in v["rows"]:
                    seated[debates.loose(mps.key(name))].append(v["when"][:10])
    days_of = {k: sorted({dt.date.fromisoformat(d) for d in v}) for k, v in seated.items()}
    out: dict[str, list[dict]] = defaultdict(list)
    for f in sorted(root.glob("*/transcripts/*.json")):
        notes = json.loads(f.read_text(encoding="utf-8"))
        conv, sitting = f.parent.parent.name, f.stem
        days = {d["day"]: d for d in notes["days"]}
        iso = lambda d: next((x for x in (d.get("listed_date"), d.get("date")) if re.fullmatch(r"\d{4}-\d\d-\d\d", x or "")), None)
        any_date = next((iso(d) for d in notes["days"] if iso(d)), None)
        for i, s in notes["speeches"].items():
            if s.get("chair"):
                continue
            day = days.get(s["day"]) or (notes["days"][s["day"] - 1] if 0 < s["day"] <= len(notes["days"]) else None)
            date = (day and iso(day)) or any_date
            key = debates.loose(mps.key(s["speaker"]))
            if not date or key not in days_of:
                continue
            at = dt.date.fromisoformat(date)
            if min(abs((d - at).days) for d in days_of[key]) > 60:
                continue  # not seated then: spoke as a member of the Government, or as a guest
            out[key].append({"id": f"{conv}/{sitting}/{i}", "date": (day and iso(day)), "url": day["url"] if day else notes["sitting"],
                             "part": s["part"], "items": [notes["agenda"].get(str(x), "")[:160] for x in s["items"][:3]],
                             "text": s["text"]})
    return out


def selection(own: list[dict]) -> list[dict]:
    """The longest speeches of each sitting in turn, up to MODEL_WORDS, each cut at CUT words."""
    by: dict[str, list[dict]] = defaultdict(list)
    for s in own:
        if len(s["text"].split()) >= LONG:
            by[s["id"].rsplit("/", 1)[0]].append(s)
    for v in by.values():
        v.sort(key=lambda s: -len(s["text"].split()))
    chosen, words = [], 0
    while words < MODEL_WORDS and any(by.values()):
        for v in by.values():
            if v and words < MODEL_WORDS:
                s = dict(v.pop(0))
                w = s["text"].split()
                if len(w) > CUT:
                    s["text"], s["cut"] = " ".join(w[:CUT]), True
                chosen.append(s)
                words += min(len(w), CUT)
    return sorted(chosen, key=lambda s: s["id"])


def check(reply: dict, material: dict) -> list[str]:
    """What is wrong with a model's reply: every point in two speeches or more, its quote word for word in one."""
    by_id = {s["id"]: s for s in material["speeches"]}
    bad = []
    if not 1 <= len(reply.get("tacke", [])) <= 5:
        bad.append("1 do 5 tačaka")
    for t in reply.get("tacke", []):
        ids, q = t.get("govori", []), t.get("citat", {})
        if len(set(ids)) < 2 or any(i not in by_id for i in ids):
            bad.append(f"govori: {ids}")
        if q.get("govor") not in ids or norm(q.get("tekst", "")) not in norm(by_id.get(q.get("govor"), {}).get("text", "")):
            bad.append(f"citat nije doslovan: {q.get('tekst', '')[:60]}")
        elif not 12 <= len(q["tekst"].split()) <= 50:
            bad.append(f"dužina citata: {len(q['tekst'].split())}")
    return bad


def record(reply: dict, material: dict, model: str) -> dict:
    by_id = {s["id"]: s for s in material["speeches"]}
    points = [{"tekst": t["tekst"].strip(), "govora": len(set(t["govori"])),
               "citat": {"tekst": t["citat"]["tekst"].strip(), "date": by_id[t["citat"]["govor"]]["date"],
                         "url": by_id[t["citat"]["govor"]]["url"]}} for t in reply["tacke"]]
    return {"mp": material["mp"], "model": model, "read": len(material["speeches"]), "speeches": material["total_speeches"],
            "sittings": len({s["id"].rsplit("/", 1)[0] for s in material["speeches"]}), "points": points}
