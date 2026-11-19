"""Who spoke how long in the hall: a page per sitting day read from the recording, and the convocation's sum.

From `data/<N>/snimak/<date>.json` (a day read by hand from the recording, or written by `arhiva.py` from the live
page's record): a turn lasts from the first to the last frame with the speaker's name in the caption, by the same
rule for every speaker; the chair has no caption and is not counted. Per day: each speaker's time and turns, the time
per list (the caption's or the Assembly's list of MPs), every turn in order with its place in the archive's recording
and a link to share it, and a picture of the day's time (the page's share picture). Per convocation: the same sums
over every day read. Orders are by time spoken, a measure, the same for all; ties by name.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from zailiprotiv import card
from zailiprotiv.pages_mikrofon import parts, turns as day_turns

TZ = ZoneInfo("Europe/Belgrade")
DIR, INDEX = "govornici", "govornici.html"
NO_LIST = "lista nije pročitana"
MONTHS = ("januar", "februar", "mart", "april", "maj", "jun", "jul", "avgust", "septembar", "oktobar", "novembar",
          "decembar")


def day_name(day: str) -> str:
    y, m, d = (int(x) for x in day.split("-"))
    return f"{d}. {MONTHS[m - 1]} {y}."


def load(root: Path) -> dict[str, list[dict]]:
    """Every day read, by convocation: {conv: [day, ...]} oldest first."""
    out: dict[str, list[dict]] = {}
    for f in sorted(root.glob("*/snimak/*.json")):
        day = json.loads(f.read_text(encoding="utf-8"))
        day["govori"] = [t for t in day.get("govori", []) if t.get("okvira", 0) >= 2]
        if day["govori"]:
            out.setdefault(f.parent.parent.name, []).append(day)
    return out


def dur(sec: int) -> str:
    h, rest = divmod(int(sec), 3600)
    m, s = divmod(rest, 60)
    return f"{h} h {m} min" if h else f"{m} min {s} s" if m and s and m < 10 else f"{m} min" if m else f"{s} s"


def sums(turns: list[dict]) -> tuple[list[dict], list[dict], int]:
    """Per speaker and per list, longest first: {"name", "slug", "list", "sec", "n", "share", "width"}; and the whole."""
    who: dict[str, dict] = {}
    for t in turns:
        w = who.setdefault(t["ime"], {"name": t["ime"], "slug": t.get("adresa", ""), "lists": {}, "sec": 0, "n": 0})
        w["sec"] += max(0, t["do"] - t["od"])
        w["n"] += 1
        side = t.get("uloga") or t.get("grupa") or ""
        if side:
            w["lists"][side] = w["lists"].get(side, 0) + 1
    whole = sum(w["sec"] for w in who.values()) or 1
    people = sorted(who.values(), key=lambda w: (-w["sec"], w["name"]))
    lists: dict[str, dict] = {}
    for w in people:
        w["list"] = max(w["lists"], key=lambda k: (w["lists"][k], k)) if w["lists"] else ""
        x = lists.setdefault(w["list"] or NO_LIST, {"name": w["list"] or NO_LIST, "sec": 0, "n": 0, "people": 0})
        x["sec"] += w["sec"]
        x["n"] += w["n"]
        x["people"] += 1
    lists_ = sorted(lists.values(), key=lambda x: (-x["sec"], x["name"]))
    for rows in (people, lists_):
        top = rows[0]["sec"] if rows else 1
        for r in rows:
            r["share"] = f"{100 * r['sec'] / whole:.1f}".replace(".", ",")
            r["width"] = f"{max(0.8, 100 * r['sec'] / (top or 1)):.1f}"
            r["time"] = dur(r["sec"])
    return people, lists_, whole


UNSIGNED_GAP = 300  # seconds: a stretch between two turns no longer than this is the chair's or the floor's time
QUICK = 120  # seconds: turns this close, taking turns between two speakers, are a quick exchange


def between(turns: list[dict]) -> int:
    """The time between turns, no stretch longer than UNSIGNED_GAP: the chair (who has no caption), roll calls, short
    stops. A longer stretch is a break and is not counted."""
    ordered = sorted(turns, key=lambda t: t["od"])
    return sum(g for a, b in zip(ordered, ordered[1:]) if 0 < (g := b["od"] - a["do"]) <= UNSIGNED_GAP)


def exchanges(turns: list[dict]) -> list[dict]:
    """Two speakers taking turns three times or more in a row, each turn starting within QUICK seconds of the last:
    {"a", "b", "n", "od"}. By the order of turns only; nothing about what was said."""
    ordered = sorted(turns, key=lambda t: t["od"])
    out: list[dict] = []
    run: list[dict] = []
    def close() -> None:
        if len(run) >= 3:
            out.append({"a": run[0]["ime"], "b": run[1]["ime"], "n": len(run), "od": run[0]["od"]})
    for t in ordered:
        if run and t["od"] - run[-1]["do"] <= QUICK and t["ime"] != run[-1]["ime"] and (
                len(run) < 2 or t["ime"] == run[-2]["ime"]):
            run.append(t)
            continue
        close()
        prev = run[-1] if run else None
        run = [prev, t] if prev and t["od"] - prev["do"] <= QUICK and t["ime"] != prev["ime"] else [t]
    close()
    return out


def picture(path: Path, title: str, when: str, people: list[dict], whole: int) -> None:
    """The day's time as a picture to share: the ten longest, then the rest summed."""
    from PIL import Image, ImageDraw, ImageFont
    bold = lambda size: ImageFont.truetype(str(card.FONTS / "Literata-Bold.ttf"), size)
    regular = lambda size: ImageFont.truetype(str(card.FONTS / "Literata-Regular.ttf"), size)
    W, H, PAD = 1200, 1500, 64
    im = Image.new("RGB", (W, H), "#ffffff")
    d = ImageDraw.Draw(im)
    x = PAD
    for word, color in (("Za", card.ZA), (" ili ", card.FG), ("Protiv", card.PROTIV)):
        d.text((x, 44), word, font=bold(40), fill=color)
        x += d.textlength(word, font=bold(40))
    d.text((W - PAD, 66), "zailiprotiv.rs", font=regular(28), fill=card.MUTED, anchor="rm")
    d.line((PAD, 108, W - PAD, 108), fill=card.FG, width=4)
    d.text((PAD, 140), title, font=bold(54), fill=card.FG)
    d.text((PAD, 216), f"{when} · ukupno {dur(whole)} govora s imenom u potpisu · {len(people)} govornika",
           font=regular(28), fill=card.MUTED)
    rows = people[:10]
    rest = people[10:]
    y, top = 290, (rows[0]["sec"] if rows else 1) or 1
    def bar(name: str, sec: int, n: int, color: str, y: int) -> None:
        d.text((PAD, y + 22), name, font=bold(32), fill=card.FG if color == card.FG else card.MUTED, anchor="lm")
        x0, x1 = PAD + 380, W - PAD - 230
        d.rectangle((x0, y + 8, x0 + max(6, round((x1 - x0) * sec / top)), y + 36), fill=color)
        d.text((W - PAD, y + 10), dur(sec), font=bold(30), fill=card.FG, anchor="ra")
        d.text((W - PAD, y + 46), f"{100 * sec / whole:.1f}".replace(".", ",") + f" % · {n} govor" + ("a" if n != 1 else ""),
               font=regular(22), fill=card.MUTED, anchor="ra")
    from zailiprotiv.site import given_first
    for r in rows:
        bar(given_first(r["name"]), r["sec"], r["n"], card.FG, y)
        y += 96
    if rest:
        bar(f"Ostalih {len(rest)}", sum(r["sec"] for r in rest), sum(r["n"] for r in rest), "#9aa0a8", y)
        y += 96
    d.text((PAD, y + 40), "Vreme dok se ime govornika vidi u potpisu prenosa, isto pravilo za svakog;", font=regular(24),
           fill=card.MUTED)
    d.text((PAD, y + 74), "predsedavajući nema potpis i nije uračunat. Automatsko čitanje može da pogreši.",
           font=regular(24), fill=card.MUTED)
    im = im.crop((0, 0, W, min(H, y + 130)))
    im.quantize(32).save(path)


def noted_days(root: Path, conv: str) -> set[str]:
    """The days whose stenographic notes are read: their transcripts give way to the notes."""
    days: set[str] = set()
    for f in (root / conv / "transcripts").glob("*.json"):
        try:
            for d in json.loads(f.read_text(encoding="utf-8")).get("days") or []:
                days.add(d if isinstance(d, str) else d.get("date", "") if isinstance(d, dict) else "")
        except (OSError, ValueError, AttributeError):
            continue
    return days


def transcript(root: Path, conv: str, day: str) -> tuple[dict, str]:
    path = root / conv / "prepis" / f"{day}.json"
    if not path.exists():
        return {}, ""
    data = json.loads(path.read_text(encoding="utf-8"))
    return {k: v.get("tekst", "") for k, v in data.get("govori", {}).items()}, data.get("model", "")


def render(*, common: dict, env, out: Path, root: Path) -> list[dict]:
    """govornici/<date>.html per day read, govornici.html for each convocation's sum. Returns the days, newest first,
    for the pages that link them."""
    convs = load(root)
    if not convs:
        return []
    (out / DIR).mkdir(exist_ok=True)
    listed = []
    for conv, days in convs.items():
        noted = noted_days(root, conv)
        for day in days:
            people, lists, whole = sums(day["govori"])
            turns = day_turns(day)
            said, model = transcript(root, conv, day["dan"]) if day["dan"] not in noted else ({}, "")
            for t, raw in zip(turns, day["govori"]):
                t["id"] = f"g{raw['od']}"
                t["said"] = said.get(str(raw["od"]), "")
            when = day_name(day["dan"])
            picture(out / DIR / f"{day['dan']}.png", "Ko je koliko govorio u Skupštini", when, people, whole)
            quick = exchanges(day["govori"])
            for x in quick:
                x["at"] = datetime.fromtimestamp(x["od"], TZ).strftime("%H:%M")
            (out / DIR / f"{day['dan']}.html").write_text(env.get_template("govornici_dan.html").render(
                gap=dur(between(day["govori"])), quick=quick,
                **common, root="../", day=day["dan"], when=when, people=people, lists=lists, whole=dur(whole),
                turns=turns, day_parts=parts(day), source=day.get("izvor", "snimak"), conv=conv, model=model),
                encoding="utf-8")
            listed.append({"day": day["dan"], "when": when, "conv": conv, "whole": dur(whole), "people": len(people)})
    newest = max(convs, key=int)
    every = [t for day in convs[newest] for t in day["govori"]]
    people, lists, whole = sums(every)
    days_ = sorted([x for x in listed if x["conv"] == newest], key=lambda x: x["day"], reverse=True)
    (out / INDEX).write_text(env.get_template("govornici.html").render(
        **common, root="", conv=newest, people=people, lists=lists, whole=dur(whole), days=days_), encoding="utf-8")
    return sorted(listed, key=lambda x: x["day"], reverse=True)


__all__ = ["render", "sums", "load", "dur", "DIR", "INDEX"]
