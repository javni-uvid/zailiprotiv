"""What happens to the laws of each area, for following an area by mail (27 Nov 2026, the maintainer: "Želim da neko
može da se pretplati na celu oblast zakona pa kada bude donesen novi zakon ili ubačen u proceduru ili se raspravlja o
zakonima iz te oblasti da se dobije mejl").

An area is the point of Article 97 of the Constitution a bill's constitutional basis names (`kinds.areas`), the same
rule for every bill; a bill with none is in no area and is told to no one. Three kinds of event, each by one rule:

- **procedura**: a bill listed on the Assembly's page of bills in procedure (`procedure.json`), on the day submitted;
- **dnevni_red**: a bill on the agenda of a convened sitting (`index.json`), by its name exactly as the page of bills in
  procedure ties them (`link.act_name`), on the day the sitting begins; that the debate began that day is not said;
- **usvojen**: a law passed, on the day of its final vote: from the page of adopted laws when it lists the law, and
  before that from the roll call on the act as a whole whose name is the bill's exactly, the only such roll call that
  day, with at least 126 votes for (a majority of all 250 MPs, enough for any law). Otherwise it waits for the page of
  adopted laws. Measured on the Fourteenth's last 12 months: 96 of its 98 laws with an area were matched so.

An event has an id that does not change, so the sender tells each once: the same law adopted by its roll call and,
later, by the page of adopted laws is one event.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

from zailiprotiv import jsonfile, kinds, link, procedure

EVENTS_FILE = "oblasti-dogadjaji.json"  # the events of the last KEEP_DAYS days, public and the same for everyone
FOLLOW_FILE = "prati-oblasti.json"  # the areas, for the counter: what can be followed by mail (worker/prati.js)
KEEP_DAYS = 30
MAJORITY = 126  # of 250 MPs: a law with this many votes for passed, whichever majority it needed
WHOLE = "Гласање о предлогу акта у целини"
KINDS = ("usvojen", "dnevni_red", "procedura")  # the order in a mail's card


def _name(text: str) -> str:
    return re.sub(r" (u )?(celini|nacelu|pojedinostima)$", "", link.act_name(text))


def _whole(v: dict) -> bool:
    return v.get("kind") == WHOLE or bool(re.search(r"\bu celini$", link.act_name(v.get("item") or "")))


def _votes(folder: Path) -> dict:
    out = {}
    for path in sorted((folder / "votes").glob("*.json")) if (folder / "votes").exists() else []:
        store = json.loads(path.read_text(encoding="utf-8"))
        for key, v in store["votes"].items():
            out[key] = {**v, "sitting_title": store.get("title", "")}
    return out


def _counts(v: dict) -> dict:
    c = v.get("counts") or {}
    return {"za": c.get("za", 0), "protiv": c.get("protiv", 0), "uzdrzan": c.get("uzdrzan", 0)}


def events(root: Path, current: str, newest: str) -> list[dict]:
    """Every event of a bill with an area in the current and the newest convocation, oldest first."""
    convs = list(dict.fromkeys((current, newest)))
    bills: dict[str, dict] = {}  # by the bill's PDF
    laws: dict[str, dict] = {}
    votes: dict[str, dict] = {}
    for c in convs:
        votes.update(_votes(root / c))
        for key, law in (jsonfile.load(root / c / "laws.json", {}).get("laws") or {}).items():
            pdf = law.get("bill_pdf") or key
            laws[pdf] = {**law, "key": key, "conv": c}
            bills[pdf] = {"title": law.get("bill_title") or law["title"], "submitted": law.get("submitted"),
                          "areas": law.get("areas") or [], "proposer": "", "first_seen": ""}
    for pdf, b in procedure.shown(root, current, newest)["bills"].items():
        old = bills.get(pdf, {})
        bills[pdf] = {"title": b["title"], "submitted": b.get("submitted") or old.get("submitted"),
                      "areas": b.get("areas") or old.get("areas") or [], "proposer": b.get("proposer", ""),
                      "first_seen": b.get("first_seen", "")}
    out = []

    def add(kind, pdf, day, **more):
        b = bills[pdf]
        if b["areas"] and day:
            out.append({"id": f"{kind}:{more.pop('key', pdf)}", "vrsta": kind, "dan": day[:10], "oblasti": b["areas"],
                        "naslov": b["title"], "predlog": pdf, **more})

    for pdf, b in bills.items():
        add("procedura", pdf, b["submitted"], predlagac=b["proposer"], poznato=b["first_seen"] or b["submitted"])
    by_name: dict[str, list[str]] = {}
    for pdf, b in bills.items():
        by_name.setdefault(link.act_name(b["title"]), []).append(pdf)
    for c in convs:
        for url, sv in (jsonfile.load(root / c / "index.json", {}).get("sittings") or {}).items():
            starts = sv.get("starts") or ""
            for item in sv.get("agenda") or []:
                # Of the bills with the item's name, the one submitted before the sitting and not passed before it;
                # when that is not exactly one, nothing is told.
                pdfs = [p for p in by_name.get(link.act_name(item), [])
                        if (bills[p]["submitted"] or "9") <= starts[:10] and (laws.get(p, {}).get("passed") or "9") >= starts[:10]]
                if len(pdfs) == 1:
                    add("dnevni_red", pdfs[0], starts, key=f"{url}|{pdfs[0]}", sednica=sv.get("title", ""),
                        pocinje=starts)
    # Adopted: the page of adopted laws, or before it the roll call on the act as a whole by the bill's name.
    whole: dict[tuple[str, str], list[dict]] = {}
    for key, v in votes.items():
        if _whole(v) and v.get("when"):
            whole.setdefault((_name(v["item"]), v["when"][:10]), []).append({**v, "key": key})
    for pdf, b in bills.items():
        law = laws.get(pdf)
        if law and law.get("passed"):
            final = votes.get(law.get("final_vote") or "")
            add("usvojen", pdf, law["passed"], zakon=law["key"], **(_counts(final) if final else {}))
            continue
        days = sorted({d for (n, d) in whole if n == link.act_name(b["title"])})
        for d in days:
            found = whole[(link.act_name(b["title"]), d)]
            if len(found) == 1 and _counts(found[0])["za"] >= MAJORITY:
                add("usvojen", pdf, d, glasanje=found[0]["key"], **_counts(found[0]))
                break
    out.sort(key=lambda e: (e["dan"], KINDS.index(e["vrsta"]), e["naslov"]))
    return out


def recent(evs: list[dict], today: dt.date, days: int = KEEP_DAYS) -> list[dict]:
    """The events of the last `days` days: by their day, or by the day we first saw them when that is later (a bill
    listed some days after it was submitted), and a sitting to come."""
    since = (today - dt.timedelta(days=days)).isoformat()
    return [e for e in evs if max(e["dan"], e.get("poznato") or "") >= since]


def mail_days(evs: list[dict], area: int | None, start: str, end: str) -> dict:
    """What a follower of `area` (None: of every area) would have got between two days, at one mail a day: the events
    by kind, the days with a mail and the most mails in one week (ISO weeks)."""
    mine = {e["id"]: e for e in evs if start <= e["dan"] <= end and (area is None or area in e["oblasti"])}
    days = {e["dan"] for e in mine.values()}
    weeks: dict[tuple, int] = {}
    for d in days:
        w = dt.date.fromisoformat(d).isocalendar()[:2]
        weeks[w] = weeks.get(w, 0) + 1
    return {**{k: sum(1 for e in mine.values() if e["vrsta"] == k) for k in KINDS},
            "mejlova": len(days), "najvise_u_nedelji": max(weeks.values(), default=0)}


def followable(*, latin, cyr, area_slug) -> dict[str, list[str]]:
    """Every area of Article 97, by its page's address: its name in both scripts. All 17, whether any law has it yet."""
    return {area_slug(name): [latin(name), cyr(latin(name))] for name in kinds.AREAS.values()}


def published(evs: list[dict], *, today: dt.date, laws: dict, bills: dict, latin, cyr) -> dict:
    """The file the live service takes (EVENTS_FILE): the events of the last KEEP_DAYS days, each with what a mail
    shows, in both scripts. `laws` and `bills` give a bill's PDF the site's page: {pdf: (path, short name)} for a law,
    {pdf: path} for a bill in procedure. The short name is the one every list of the site shows (written by a model
    and reviewed); a bill keeps the Assembly's title."""
    out = []
    for e in recent(evs, today):
        law = laws.get(e["predlog"])
        page = law[0] if law else bills.get(e["predlog"], "")
        name = latin(law[1] if law and e["vrsta"] == "usvojen" else e["naslov"])
        row = {k: e[k] for k in ("id", "vrsta", "dan", "oblasti") if k in e}
        row.update(naslov=name, naslov_cir=cyr(name), strana=page)
        if e["vrsta"] == "procedura":
            row.update(predlagac=latin(e.get("predlagac", "")), predlagac_cir=cyr(latin(e.get("predlagac", ""))),
                       poznato=e.get("poznato", ""))
        if e["vrsta"] == "dnevni_red":
            row.update(sednica=latin(e.get("sednica", "")), sednica_cir=cyr(latin(e.get("sednica", ""))),
                       pocinje=e.get("pocinje", ""))
        if e["vrsta"] == "usvojen":
            row.update({k: e[k] for k in ("za", "protiv", "uzdrzan") if k in e})
        out.append(row)
    areas = {n: [latin(name), cyr(latin(name))] for n, name in kinds.AREAS.items()}
    return {"izgradjeno": today.isoformat(), "oblasti": areas, "dogadjaji": out}
