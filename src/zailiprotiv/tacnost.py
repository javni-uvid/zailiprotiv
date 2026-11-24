"""How right the live page's record of who spoke when is, measured against the day as the Assembly's notes have it
(24 Nov 2026, the maintainer: who speaks when is the most important part, and no rule for it is to change again on
one example).

The truth is `data/<N>/snimak/<day>.json` with `"izvor": "govor"`: each speech of the notes found in the recording's
words (govor.py), the name the notes'. The record measured is the live page's (`data/<N>/uzivo/<day>.json`, or the
service's own file of the day, or any file of either shape: so a rule can be tried on a kept record and scored before
it runs live). Second by second, inside what both cover:

- right: the record names who the notes say is speaking;
- wrong: it names somebody else (the worst: words put in another's mouth);
- missing: the notes have a speaker, the record nobody;
- extra: the record names somebody where the notes place no speech (the chair's words, a break, or a short speech
  the notes' words were too few to place: so not all of it is an error).

The record's clock runs some seconds behind the recording's (15-20 s, recordings.md), which is no error of whose
speech it is: the seconds are counted at the shift that agrees best, and the shift is told. A speech of the notes is
found when at least half of it is right; of those, how far the record's beginning and end are from the notes'.
The same rule for every speaker; nothing here is shown on the site."""
from __future__ import annotations

import json
from pathlib import Path
from statistics import median

SHIFTS = range(-60, 61, 2)  # seconds the record's clock may be off the recording's
FOUND = 0.5  # a speech is found when this share of its seconds is right


def turns(data: dict) -> list[tuple[int, int, str, str]]:
    """(from, to, who, name) of a record in either shape: the site's ("govori": od, do, adresa, ime) or the service's
    file of a day ("turns": start, seen, slug, name; a turn read in one frame is none, as on the page)."""
    out = []
    for g in data.get("govori") or []:
        out.append((int(g["od"]), int(g["do"]), g.get("adresa") or g["ime"], g["ime"]))
    for t in data.get("turns") or []:
        if t.get("n", 0) >= 2:
            out.append((int(t["start"]), int(t["seen"]), t.get("slug") or t["name"], t["name"]))
    return sorted(x for x in out if x[1] > x[0])


def _cover(data: dict, rows: list) -> list[tuple[int, int]]:
    spans = [(int(c["od"]), int(c["do"])) for c in data.get("pokriveno") or [] if isinstance(c, dict)]
    spans += [(int(c[0]), int(c[1])) for c in data.get("cover") or [] if isinstance(c, (list, tuple)) and len(c) >= 2]
    return spans or ([(rows[0][0], max(r[1] for r in rows))] if rows else [])


def _line(rows: list, start: int, length: int, shift: int = 0) -> list:
    line = [None] * length
    for a, b, who, _ in rows:
        for s in range(max(0, a + shift - start), min(length, b + shift - start)):
            line[s] = who
    return line


def score(truth: dict, record: dict) -> dict | None:
    """The record against the truth: seconds right, wrong, missing and extra inside what both cover, at the shift of
    the record's clock that agrees best; the notes' speeches found; how far the found ones' ends are. None when the two
    share nothing."""
    said, heard = turns(truth), turns(record)
    both = [(max(a, c), min(b, d)) for a, b in _cover(truth, said) for c, d in _cover(record, heard) if min(b, d) > max(a, c)]
    if not said or not heard or not both:
        return None
    start, end = min(a for a, _ in both), max(b for _, b in both)
    inside = [False] * (end - start)
    for a, b in both:
        for s in range(a - start, b - start):
            inside[s] = True
    want = _line(said, start, end - start)

    def count(shift: int) -> tuple[int, int, int, int, list]:
        got = _line(heard, start, end - start, shift)
        right = wrong = missing = extra = 0
        for s, ok in enumerate(inside):
            if not ok:
                continue
            w, g = want[s], got[s]
            if w and g:
                right, wrong = right + (w == g), wrong + (w != g)
            elif w:
                missing += 1
            elif g:
                extra += 1
        return right, wrong, missing, extra, got

    shift = max(SHIFTS, key=lambda d: (count(d)[0], -abs(d)))
    right, wrong, missing, extra, got = count(shift)
    names = {who: name for _, _, who, name in said + heard}
    found, begins, ends, mistaken = 0, [], [], {}
    speeches = [(a, b, who) for a, b, who, _ in said if any(c <= a and b <= d for c, d in both)]
    for a, b, who in speeches:
        mine = [s for s in range(a - start, b - start) if got[s] == who]
        if len(mine) >= FOUND * (b - a):
            found += 1
            first, last = mine[0], mine[-1]
            while first > 0 and got[first - 1] == who:  # the record's turn may begin before the notes' speech
                first -= 1
            while last + 1 < len(got) and got[last + 1] == who:
                last += 1
            begins.append(first + start - a)
            ends.append(last + 1 + start - b)
        for s in range(a - start, b - start):
            if got[s] and got[s] != who:
                key = (names[who], names[got[s]])
                mistaken[key] = mistaken.get(key, 0) + 1
    spoken = right + wrong + missing
    return {"pomak": shift, "sekundi": spoken, "tacno": right, "pogresno": wrong, "nedostaje": missing, "visak": extra,
            "udeo": round(100 * right / spoken, 1) if spoken else 0.0, "govora": len(speeches), "nadjeno": found,
            "pocetak": round(median(abs(x) for x in begins)) if begins else None,
            "kraj": round(median(abs(x) for x in ends)) if ends else None,
            "pocetak_preko_30": sum(1 for x in begins if abs(x) > 30), "kraj_preko_30": sum(1 for x in ends if abs(x) > 30),
            "zamene": sorted(((n, a, b) for (a, b), n in mistaken.items()), reverse=True)[:12]}


def told(day: str, s: dict | None) -> str:
    """The score as lines for a person to read."""
    if not s:
        return f"{day}: nothing to compare (no truth from the notes, or the two cover no common time)"
    m = lambda sec: f"{sec // 60} min" if sec >= 600 else f"{sec} s"
    lines = [f"{day}: {s['udeo']}% of the {m(s['sekundi'])} the notes' speakers spoke are under the right name "
             f"(the record's clock {s['pomak']:+d} s)",
             f"  right {m(s['tacno'])} · wrong name {m(s['pogresno'])} · missing {m(s['nedostaje'])} · "
             f"named where the notes place no speech {m(s['visak'])}",
             f"  speeches found {s['nadjeno']} of {s['govora']}; a found speech's beginning is off by {s['pocetak']} s and "
             f"its end by {s['kraj']} s (the median); over 30 s: {s['pocetak_preko_30']} beginnings, {s['kraj_preko_30']} ends"]
    lines += [f"  {n} s of {a} under the name of {b}" for n, a, b in s["zamene"]]
    return "\n".join(lines)


def day(conv_dir: Path, date: str, record: Path | None = None) -> dict | None:
    """The score of a day: the convocation's truth against its live record, or against `record`."""
    truth = conv_dir / "snimak" / f"{date}.json"
    record = record or conv_dir / "uzivo" / f"{date}.json"
    if not truth.exists() or not record.exists():
        return None
    said = json.loads(truth.read_text(encoding="utf-8"))
    if said.get("izvor") != "govor":
        return None  # a day with no notes yet has no truth: its file is the live record itself, or voices
    return score(said, json.loads(record.read_text(encoding="utf-8")))
