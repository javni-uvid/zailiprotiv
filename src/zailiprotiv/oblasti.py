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

Following one bill or one law (28 Nov 2026, the maintainer: "Može se nekom i samo na taj zakon prijaviti", and of the
proposal "Možemo sa tvojim preporukama") takes the same events of every bill, with an area or none, and two more:

- **nije_na_spisku**: a bill the page of bills in procedure no longer lists, on the day it was last listed, told once it
  has been missing a whole day more and when no roll call on it as a whole is known (a bill passed leaves the list too);
- **objavljen**: a law the page of adopted laws lists with its number of the Official Gazette, on the day it passed.

Each event names the laws its bill changes (`zakoni`, by `follow_key`): the law a title amends, supplements or repeals
("Predlog zakona o izmenama Zakona o radu" → "Zakon o radu"), or for a new law the law itself. A follower of a law is
told the events of every bill that names it.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

from zailiprotiv import jsonfile, kinds, link, procedure
from zailiprotiv.translit import latin

EVENTS_FILE = "oblasti-dogadjaji.json"  # the events of the last KEEP_DAYS days, public and the same for everyone
FOLLOW_FILE = "prati-oblasti.json"  # the areas, for the counter: what can be followed by mail (worker/prati.js)
BILLS_FILE = "prati-predlozi.json"  # the bills that wait, for the counter: {key: [title, its Cyrillic]}
LAWS_DIR = "prati-zakoni"  # every law of the site, by the law it is or changes: <key>.json = [name, its Cyrillic]
KEEP_DAYS = 30
MAJORITY = 126  # of 250 MPs: a law with this many votes for passed, whichever majority it needed
WHOLE = "Гласање о предлогу акта у целини"
KINDS = ("usvojen", "objavljen", "dnevni_red", "procedura", "nije_na_spisku")  # the order in a mail's card
AREA_KINDS = ("usvojen", "dnevni_red", "procedura")  # what a follower of an area is told
KEY = 80  # the longest key the counter takes
_CHANGE = r"(?:izmen[ai]m?a?|dopun[ai]m?a?|prestanku važenja)(?: i (?:izmen[ai]m?a?|dopun[ai]m?a?))?"


def named(title: str) -> list[str]:
    """The laws a bill's or law's title changes, by their own names: "Predlog zakona o izmenama i dopunama Zakona o
    porezu na dohodak građana" → ["Zakon o porezu na dohodak građana"], "Zakon o izmeni Krivičnog zakonika" →
    ["Krivični zakonik"]; a title that changes none names itself ("Predlog zakona o gasu" → ["Zakon o gasu"]). None
    for an act that is not a law (a decision, an authentic interpretation)."""
    t = re.sub(r"\s+", " ", latin(title)).strip()
    t = re.sub(r"^Predlog zakona\b", "Zakon", t)
    out = [t]
    for _ in range(4):  # "Zakon o prestanku važenja Zakona o izmenama Zakona o …": the law beneath
        m = re.match(rf"(?:Zakon|Zakonik) o {_CHANGE} (.+)$", out[0], flags=re.I)
        if not m:
            break
        names = []
        for part in re.split(r"(?:,| i) (?=[Zz]akona o )", m.group(1)):
            n = re.match(r"([Zz]akon(?:ik)?)a (o|za) (.+)$", part)
            a = re.match(r"(\w+)og (zakon(?:ik)?)a\b(.*)$", part)
            if n:
                names.append(f"{n.group(1).capitalize()} {n.group(2)} {n.group(3)}".rstrip(" ,"))
            elif a:
                names.append(f"{a.group(1)}i {a.group(2)}{a.group(3)}".rstrip(" ,"))
        if not names:
            break
        out = names
    return [n for n in out if re.match(r"^(\w+i )?[Zz]akon", n)]


def follow_key(text: str) -> str:
    """The key the counter takes for a page or a law: its address, or when longer than KEY its first part and a
    short digest of the whole, the same every time."""
    import hashlib
    from zailiprotiv.site import slug
    s = slug(text, 400)
    return s if len(s) <= KEY else s[:KEY - 9].rstrip("-") + "-" + hashlib.sha1(s.encode()).hexdigest()[:8]


def law_key(title: str) -> str:
    """The key of the law a law's page follows: the law it changes, or itself."""
    return follow_key((named(title) or [title])[0])


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
        if day:
            out.append({"id": f"{kind}:{more.pop('key', pdf)}", "vrsta": kind, "dan": day[:10], "oblasti": b["areas"],
                        "naslov": b["title"], "predlog": pdf, "zakoni": [follow_key(n) for n in named(b["title"])], **more})

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
            if law.get("gazette"):
                add("objavljen", pdf, law["passed"], glasnik=law["gazette"])
            continue
        days = sorted({d for (n, d) in whole if n == link.act_name(b["title"])})
        for d in days:
            found = whole[(link.act_name(b["title"]), d)]
            if len(found) == 1 and _counts(found[0])["za"] >= MAJORITY:
                add("usvojen", pdf, d, glasanje=found[0]["key"], **_counts(found[0]))
                break
    # No longer listed: missing at the last reading and on the whole day before it, neither passed nor voted on as a
    # whole under its name (so a bill passed whose roll calls are not read yet is not told as gone).
    proc = procedure.shown(root, current, newest)
    adopted = {e["predlog"] for e in out if e["vrsta"] == "usvojen"}
    for pdf, b in proc["bills"].items():
        last = b.get("last_seen") or ""
        if (last and proc["fetched"] and last < (dt.date.fromisoformat(proc["fetched"]) - dt.timedelta(days=1)).isoformat()
                and pdf not in adopted and pdf not in laws
                and not any(n == link.act_name(b["title"]) for (n, _d) in whole)):
            add("nije_na_spisku", pdf, last, poznato=(dt.date.fromisoformat(last) + dt.timedelta(days=2)).isoformat())
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
    mine = {e["id"]: e for e in evs if start <= e["dan"] <= end and e["vrsta"] in AREA_KINDS
            and (area in e["oblasti"] if area is not None else bool(e["oblasti"]))}
    days = {e["dan"] for e in mine.values()}
    weeks: dict[tuple, int] = {}
    for d in days:
        w = dt.date.fromisoformat(d).isocalendar()[:2]
        weeks[w] = weeks.get(w, 0) + 1
    return {**{k: sum(1 for e in mine.values() if e["vrsta"] == k) for k in AREA_KINDS},
            "mejlova": len(days), "najvise_u_nedelji": max(weeks.values(), default=0)}


def followable(*, latin, cyr, area_slug) -> dict[str, list[str]]:
    """Every area of Article 97, by its page's address: its name in both scripts. All 17, whether any law has it yet."""
    return {area_slug(name): [latin(name), cyr(latin(name))] for name in kinds.AREAS.values()}


def bills_followable(rows: list[dict], *, latin, cyr) -> dict[str, list[str]]:
    """The bills that wait, by their key (`follow_key` of their page's address): the title in both scripts. A bill
    once passed or gone is no longer taken; who follows it already goes on (as its law, once passed)."""
    return {follow_key(r["slug"]): [latin(r["title"]), cyr(latin(r["title"]))] for r in rows}


def laws_followable(titles: list[str], *, latin, cyr) -> dict[str, list[str]]:
    """Every law a law of the site is or changes, by its key: one name in both scripts. Spellings of one name (a
    dash, quotation marks, a capital) are one key; its name is the law's own title when the site has the law, else
    the one most titles give."""
    own = {follow_key(latin(t)): latin(t) for t in titles}
    seen: dict[str, dict[str, int]] = {}
    for t in titles:
        for n in named(t):
            seen.setdefault(follow_key(n), {}).setdefault(n, 0)
            seen[follow_key(n)][n] += 1
    out = {}
    for k, names in seen.items():
        name = own.get(k) or max(sorted(names), key=lambda n: names[n])
        out[k] = [name, cyr(name)]
    return out


def published(evs: list[dict], *, today: dt.date, laws: dict, bills: dict, latin, cyr) -> dict:
    """The file the live service takes (EVENTS_FILE): the events of the last KEEP_DAYS days, each with what a mail
    shows, in both scripts. `laws` and `bills` give a bill's PDF the site's page: {pdf: (path, short name)} for a law,
    {pdf: path} for a bill in procedure. The short name is the one every list of the site shows (written by a model
    and reviewed); a bill keeps the Assembly's title.

    For following one bill or law, each event has the key of its bill (`predlog`, "" for a bill the site has no page
    of) and of the laws it changes (`zakoni`), and `predlozi` gives every bill of a page the laws it changes, with
    their names, and the day it passed: who follows a bill goes on following them from then."""
    out = []
    key_of = {pdf: follow_key(path.removeprefix("predlog/")) for pdf, path in bills.items()}
    for e in recent(evs, today):
        law = laws.get(e["predlog"])
        page = law[0] if law else bills.get(e["predlog"], "")
        name = latin(law[1] if law and e["vrsta"] in ("usvojen", "objavljen") else e["naslov"])
        row = {k: e[k] for k in ("id", "vrsta", "dan", "oblasti", "zakoni") if k in e}
        row.update(naslov=name, naslov_cir=cyr(name), strana=page, predlog=key_of.get(e["predlog"], ""))
        if e["vrsta"] not in AREA_KINDS:  # told to no area's follower (and not to a sender that knows only those)
            row["oblasti"] = []
        if e["vrsta"] == "procedura":
            row.update(predlagac=latin(e.get("predlagac", "")), predlagac_cir=cyr(latin(e.get("predlagac", ""))),
                       poznato=e.get("poznato", ""))
        if e["vrsta"] == "dnevni_red":
            row.update(sednica=latin(e.get("sednica", "")), sednica_cir=cyr(latin(e.get("sednica", ""))),
                       pocinje=e.get("pocinje", ""))
        if e["vrsta"] == "usvojen":
            row.update({k: e[k] for k in ("za", "protiv", "uzdrzan") if k in e})
        if e["vrsta"] == "objavljen":
            row.update(glasnik=e.get("glasnik", ""))
        if e["vrsta"] == "nije_na_spisku":
            row.update(poznato=e.get("poznato", ""))
        out.append(row)
    areas = {n: [latin(name), cyr(latin(name))] for n, name in kinds.AREAS.items()}
    passed = {e["predlog"]: e["dan"] for e in evs if e["vrsta"] == "usvojen"}
    titles = {e["predlog"]: e["naslov"] for e in evs}
    bills_out = {}
    for pdf, k in key_of.items():
        names = named(titles.get(pdf, ""))
        bills_out[k] = {"zakoni": [[follow_key(n), latin(n), cyr(latin(n))] for n in names],
                        "usvojen": passed.get(pdf, "")}
    return {"izgradjeno": today.isoformat(), "oblasti": areas, "dogadjaji": out, "predlozi": bills_out}
