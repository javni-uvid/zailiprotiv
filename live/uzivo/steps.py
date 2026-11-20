"""The day's steps as the live page shows them ("Šta se desilo danas"): which of the steps heard in the chair's words
and read on the Assembly's page are shown, and as what. No HTML here: page._steps draws them."""
from __future__ import annotations

from .names import given_first

# A step heard in the chair's words, as the page writes it: our own short line for the kind of step, never the
# sentence as the transcript has it (19 Nov 2026: the transcript's wording errs too much to be shown).
STEP_TITLES = {"Sednica otvorena": "Sednica je otvorena", "Nastavak rada": "Rad je nastavljen", "Pauza": "Pauza",
               "Kraj rada": "Kraj rada za danas", "Glasanje": "Glasanje", "Glasanje zaključeno": "Glasanje je zaključeno",
               "Pretres otvoren": "Pretres je otvoren", "Pretres zaključen": "Pretres je zaključen"}
STEP_SAME = 900  # the same step heard again within this many seconds is one line (the chair repeats the phrases)
STEP_QUIET = 240  # a break (or the day's end) is one when nobody is at the rostrum for this long after it is said
STEP_IDLE = 600  # work is resumed when nobody was at the rostrum for this long before the chair says so
_UNDER_WAY = {"Glasanje", "Glasanje zaključeno", "Pretres otvoren", "Pretres zaključen"}
# Steps said in the same second, in the order the Assembly's work takes them.
_PHASE = {"Sednica otvorena": 0, "Nastavak rada": 0, "Tačka dnevnog reda": 1, "Pretres otvoren": 2,
          "Pretres zaključen": 3, "Glasanje": 4, "Glasanje zaključeno": 5}


def _in_order(kind: str, debate: str, voting: bool) -> tuple[bool, str, bool]:
    """Whether a step of an agenda item fits what has been shown of it, and the item's state after it: a debate is
    opened once and before it is closed (one already under way when the item is taken up, "nastavljamo pretres",
    counts as opened); a vote is closed only after it was put; a vote put while one is open is that vote."""
    if kind == "Pretres otvoren":
        return (debate == "", "open" if debate == "" else debate, voting)
    if kind == "Pretres zaključen":
        return (debate != "closed" and not voting, "closed" if debate != "closed" and not voting else debate, voting)
    if kind == "Glasanje":
        return (not voting, debate, True)
    if kind == "Glasanje zaključeno":
        return (voting, debate, False)
    return (True, debate, voting)


def steps_shown(snap: dict) -> list[dict]:
    """The day's steps as shown, newest first: [{"t", "izvor", "naslov", "opis", "url"}]. From the Assembly's page: its
    sentence, whole. From the chair's words: the step's name (STEP_TITLES), shown only when something else bears it
    out (19 Nov 2026, the maintainer's decision: what cannot be confirmed is not shown):
    - a move to an agenda item: the agenda has the item, and its number is higher than the last one heard today;
    - a break, the day's end: nobody is at the rostrum for STEP_QUIET seconds after it (so it shows that much later);
    - work resumed: a break shown before it, nobody had spoken yet today, or nobody was at the rostrum for
      STEP_IDLE before it (once: a second "we go on" with no break between is the chair's turn of phrase);
      the sitting opened: nobody had spoken yet;
    - a vote, a debate opened or closed: an agenda item is under way;
    - the floor given to an MP ("Reč ima: …"): the chair's words name exactly one sitting MP, whole (hronika.floor),
      and no turn read from the picture stands at that time (with captions on, the captions say who speaks);
    - anything else (a measure, "the chair notes that…") waits for the Assembly's own page.
    The same step within a quarter of an hour is one line. And every step must fit the order of the Assembly's work
    (20 Nov 2026, the maintainer's request; `_in_order`): within an agenda item the debate is opened before it is
    closed and once, a vote is closed only after one was put, and a second "put to the vote" while one is open is
    the same vote; steps said in the same second are taken in that order (an item, then its debate, then its vote)."""
    if any(e.get("izvor") == "model" for e in snap.get("hronika") or []):
        return model_steps(snap)
    from .hronika import find, item_no
    agenda = (snap.get("dnevni_red") or {}).get("tacke") or []
    items = {int(x["n"]): x["tekst"] for x in agenda}
    now = snap.get("provereno") or 0
    turns = [(d["od"], d["do"]) for d in snap.get("danas") or []]
    if snap.get("sada"):
        turns.append((snap["sada"]["od"], now))
    quiet = lambda t: now >= t + STEP_QUIET and not any(a < t + STEP_QUIET and b > t + 30 for a, b in turns)
    first =lambda t: not any(b < t - 30 for a, b in turns)
    idle = lambda t: not any(a < t and b > t - STEP_IDLE for a, b in turns)  # nobody at the rostrum just before
    out: list[dict] = []
    last: dict[str, int] = {}
    item, paused, resumed = 0, False, ""
    debate, voting = "", False  # the current item's debate ("", "open", "closed") and whether a vote is open
    for e in sorted(snap.get("hronika") or [], key=lambda e: (e["t"], _PHASE.get(e.get("vrsta", ""), 9))):
        if e.get("izvor") == "sajt":
            out.append({"t": e["t"], "izvor": "sajt", "naslov": "", "opis": e.get("tekst", ""), "url": e.get("url", "")})
            continue
        kind, more, t = e.get("vrsta", ""), "", e["t"]
        if kind == "Reč ima":  # the chair named a sitting MP (hronika.floor); only while the picture names nobody
            title = "Reč ima: " + given_first(e.get("tekst", ""))
            if any(a < t + 180 and b > t - 60 for a, b in turns) or t - last.get(title, -10 ** 9) < STEP_SAME:
                continue
            last[title] = t
            out.append({"t": t, "izvor": "prepis", "naslov": title, "opis": "", "url": "", "adresa": e.get("url", ""), "rec": True})
            continue
        kinds = [k for k, _ in find(e.get("tekst", ""))]
        if kind not in kinds:  # kept by a rule since mended: what today's rules find in the sentence, or nothing
            if not kinds:
                continue
            kind = kinds[0]
        title = STEP_TITLES.get(kind, "")
        if kind == "Tačka dnevnog reda":
            n = item_no(e.get("tekst", ""))
            if not n or n not in items or n <= item:
                continue
            title, more = f"Prelazak na {n}. tačku dnevnog reda", items[n]
        elif kind in ("Pauza", "Kraj rada"):
            if not quiet(t):
                continue
        elif kind == "Nastavak rada":
            if not (paused or first(t) or (idle(t) and resumed != "on")):
                continue
        elif kind == "Sednica otvorena":
            if not first(t):
                continue
        elif kind in _UNDER_WAY:
            if not (item or any(x.get("stanje") == "u_toku" for x in agenda)):
                continue
        else:
            continue
        if kind in _UNDER_WAY:  # the order of the Assembly's work decides, not the quarter of an hour
            ok, debate, voting = _in_order(kind, debate, voting)
            if not ok:
                continue
        elif t - last.get(title, -10 ** 9) < STEP_SAME:
            continue
        last[title] = t
        if kind == "Tačka dnevnog reda":
            item = n
            debate, voting = ("open" if "pretres" in e.get("tekst", "").lower() else ""), False
        paused = kind in ("Pauza", "Kraj rada") or (paused and kind != "Nastavak rada")
        resumed = "on" if kind == "Nastavak rada" else ("" if paused else resumed)
        out.append({"t": t, "izvor": "prepis", "naslov": title, "opis": more, "url": ""})
    return out[::-1]


# The model's steps (sudija.py) as the page writes them: our line for the kind, and what the model read besides,
# where the sentence it rests on bears it out.
MODEL_TITLES = {**STEP_TITLES, "Tačka dnevnog reda": "", "Rezultat glasanja": "Rezultat glasanja", "Izbor": "Izbor",
                "Mera predsedavajućeg": "Mera predsedavajućeg"}


def _borne(said: str, sentence: str) -> str:
    """What the model read besides (a result, a name, how long), when every number and capitalised word of it is in
    the sentence it rests on: else nothing, rather than a figure or a name the transcript doesn't hold."""
    import re
    from .ispravke import fold
    said = " ".join(str(said or "").split())
    if not said:
        return ""
    body = fold(sentence)
    if any(n not in re.findall(r"\d+", sentence) for n in re.findall(r"\d+", said)):
        return ""
    if any(fold(w)[:4] not in body for w in re.findall(r"\b[A-ZČĆŠŽĐ][a-zčćšžđ]{3,}", said)):
        return ""
    return said


def model_steps(snap: dict) -> list[dict]:
    """The day's steps when the model tells them (20 Nov 2026, the maintainer's decision: the model is the source,
    the rules the fallback): the model's steps and the Assembly's page; of the rules' steps only "Reč ima", which
    names a sitting MP by the list. A break or the day's end shows once nobody is at the rostrum for STEP_QUIET after
    it; a move to an agenda item only to an item the agenda has, after the last one; the order of the work as for the
    rules (`_in_order`); the same line within a quarter of an hour once."""
    agenda = (snap.get("dnevni_red") or {}).get("tacke") or []
    items = {int(x["n"]): x["tekst"] for x in agenda}
    now = snap.get("provereno") or 0
    turns = [(d["od"], d["do"]) for d in snap.get("danas") or []]
    if snap.get("sada"):
        turns.append((snap["sada"]["od"], now))
    quiet = lambda t: now >= t + STEP_QUIET and not any(a < t + STEP_QUIET and b > t + 30 for a, b in turns)
    out: list[dict] = []
    last: dict[str, int] = {}
    item, debate, voting = 0, "", False
    order = {**_PHASE, "Rezultat glasanja": 5, "Izbor": 6}
    for e in sorted(snap.get("hronika") or [], key=lambda e: (e["t"], order.get(e.get("vrsta", ""), 9))):
        src, kind, t = e.get("izvor"), e.get("vrsta", ""), e["t"]
        if src == "sajt":
            out.append({"t": t, "izvor": "sajt", "naslov": "", "opis": e.get("tekst", ""), "url": e.get("url", "")})
            continue
        if src == "prepis" and kind == "Reč ima":
            title = "Reč ima: " + given_first(e.get("tekst", ""))
            if any(a < t + 180 and b > t - 60 for a, b in turns) or t - last.get(title, -10 ** 9) < STEP_SAME:
                continue
            last[title] = t
            out.append({"t": t, "izvor": "prepis", "naslov": title, "opis": "", "url": "", "adresa": e.get("url", ""),
                        "rec": True, "model": True})
            continue
        if src != "model" or kind not in MODEL_TITLES:
            continue
        more, sentence = e.get("vise") or {}, e.get("tekst", "")
        title, what = MODEL_TITLES[kind], ""
        if kind == "Tačka dnevnog reda":
            try:
                n = int(more.get("tacka") or 0)
            except (TypeError, ValueError):
                n = 0
            if not n or n not in items or n <= item:
                continue
            title, what = f"Prelazak na {n}. tačku dnevnog reda", items[n]
            item, debate, voting = n, ("open" if "pretres" in sentence.lower() else ""), False
        elif kind in ("Pauza", "Kraj rada"):
            if not quiet(t):
                continue
            what = _borne(more.get("do"), sentence)
        elif kind == "Rezultat glasanja":
            ok, debate, voting = _in_order("Glasanje zaključeno", debate, voting)
            what = _borne(more.get("napomena"), sentence)
        elif kind == "Izbor":
            what = _borne(more.get("ko"), sentence)
            if not what:
                continue
        elif kind == "Mera predsedavajućeg":
            what = " · ".join(x for x in (_borne(more.get("napomena"), sentence), _borne(more.get("kome"), sentence)) if x)
        elif kind in _UNDER_WAY:
            ok, debate, voting = _in_order(kind, debate, voting)
            if not ok:
                continue
        key = title + "|" + what
        if kind not in _UNDER_WAY and kind != "Rezultat glasanja" and t - last.get(key, -10 ** 9) < STEP_SAME:
            continue
        last[key] = t
        out.append({"t": t, "izvor": "prepis", "naslov": title, "opis": what, "url": "", "model": True})
    return out[::-1]
