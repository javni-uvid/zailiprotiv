"""From the stenographic notes read, by rule and with no model: the measures the chair pronounced (a warning, taking
the floor away, removal from the sitting) and the exchanges of replies between two speakers.

Everything is given word for word (principle 6): the chair's words that pronounce the measure with the speech
before them, and every speech of an exchange. The site doesn't say who was right or what an exchange was "about".
"""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from zailiprotiv import debates as debates_, mps
from zailiprotiv.site import ORDINAL_NAME, slug
from zailiprotiv.translit import latin

# What the chair says when pronouncing a measure (Rules of Procedure, Articles 108–111), first person, present tense.
MEASURES = [
    ("udaljenje", "Udaljenje sa sednice", re.compile(r"изричем[^.!?]{0,120}удаљењ|мер[ау] удаљења са седнице", re.I)),
    ("oduzimanje", "Oduzimanje reči", re.compile(r"изричем[^.!?]{0,120}одузимањ\w* речи|одузимам вам реч", re.I)),
    ("opomena", "Opomena", re.compile(r"изричем[^.!?]{0,60}опомен", re.I)),
]
TURNS = 4      # an exchange: this many speeches or more, two speakers taking turns
SHORT = 400    # … none longer than this many words (a reply is short; a speech on the agenda is not)


_MARK = re.compile(r"^\s*\d+/\d+\s*[A-ZА-ЯЈЉЊЂЋЏ]{1,3}\s*/\s*[A-ZА-ЯЈЉЊЂЋЏ]{1,3}\s*$", re.M)


def spoken(text: str) -> str:
    """A speech without the stenographers' page marks ("39/2AL/JG"), which are not anyone's words."""
    return _MARK.sub("", text).strip()


def measures(speeches: list[dict]) -> list[dict]:
    out = []
    for i, s in enumerate(speeches):
        if not s.get("chair"):
            continue
        hit = next(((k, label) for k, label, pattern in MEASURES if pattern.search(s["text"])), None)
        if hit:
            before = next((p for p in reversed(speeches[max(0, i - 6):i]) if not p.get("chair")), None)
            out.append({"kind": hit[0], "label": hit[1], "chair": s, "before": before})
    return out


def exchanges(speeches: list[dict]) -> list[list[dict]]:
    """Runs of speeches in which two speakers take turns (the chair's words between them aside)."""
    seq = [s for s in speeches if not s.get("chair")]
    out, i = [], 0
    while i < len(seq) - TURNS + 1:
        a, b = seq[i]["speaker"], seq[i + 1]["speaker"]
        j = i
        while (j < len(seq) and a != b and seq[j]["speaker"] == (a if (j - i) % 2 == 0 else b)
               and seq[j]["day"] == seq[i]["day"] and len(seq[j]["text"].split()) <= SHORT):
            j += 1
        if j - i >= TURNS:
            out.append(seq[i:j])
            i = j
        else:
            i += 1
    return out


def render(*, env, common, out: Path, debates: dict, people: dict, convs: list) -> dict:
    loose = {debates_.loose(k): k for k in people}

    def who(name: str) -> dict:
        key = loose.get(debates_.loose(mps.key(name)))
        return {"name": people[key].name if key else latin(name).title(), "slug": people[key].slug if key else ""}

    by_conv, by_mp = [], defaultdict(list)
    for c, _ in convs:
        events = []
        for url, notes in debates.get(c, {}).items():
            speeches = [{**notes["speeches"][k], "text": spoken(notes["speeches"][k]["text"])} for k in sorted(notes["speeches"])]
            days = {d["day"]: d for d in notes["days"]}
            title = latin(re.sub(r"^СТЕНОГРАФСКЕ БЕЛЕШКЕ\s*-\s*", "", notes["days"][0]["title"]).split(" - ")[0]) if notes["days"] else ""

            def meta(s):
                d = days.get(s["day"], {})
                date = next((x for x in (d.get("date"), d.get("listed_date")) if re.fullmatch(r"\d{4}-\d\d-\d\d", x or "")), "")
                return {"date": date, "notes": d.get("url", ""), "sitting": title,
                        "sitting_url": url}
            for m in measures(speeches):
                events.append({"type": "mera", **m, **meta(m["chair"]), "id": f"m{len(events)}",
                               "before_who": who(m["before"]["speaker"]) if m["before"] else None})
            for run in exchanges(speeches):
                a, b = who(run[0]["speaker"]), who(run[1]["speaker"])
                ev = {"type": "razmena", "a": a, "b": b, "speeches": [{"who": who(s["speaker"]), "text": s["text"]} for s in run],
                      "n": len(run), **meta(run[0]), "id": f"r{len(events)}"}
                events.append(ev)
                for p in (a, b):
                    if p["slug"]:
                        by_mp[p["slug"]].append(ev)
        events.sort(key=lambda e: e["date"], reverse=True)
        for i, e in enumerate(events):
            e["id"] = f"{c}-{i + 1}"
            e["conv"] = c
        if events:
            by_conv.append({"n": c, "name": ORDINAL_NAME.get(c, c), "events": events,
                            "measures": [e for e in events if e["type"] == "mera"],
                            "exchanges": [e for e in events if e["type"] == "razmena"],
                            "sittings": len(debates.get(c, {}))})
    # A page per convocation (the words in full make a long page); the newest is replike.html.
    for i, c in enumerate(by_conv):
        c["page"] = "replike.html" if i == 0 else f"replike-{c['n']}.html"
    for c in by_conv:
        for e in c["events"]:
            e["page"] = c["page"]
        (out / c["page"]).write_text(env.get_template("floor.html").render(**common, c=c, by_conv=by_conv, root=""),
                                     encoding="utf-8")
    return by_mp
