"""The page shown at mikrofon.zailiprotiv.rs while "Ko sada govori" is down (17 Nov 2026).

"Ko sada govori" (live/) runs on the maintainer's computer behind a Cloudflare tunnel; when the computer is off,
Cloudflare answers with its own error. The edge worker (live/edge/) then shows this page instead, built with the
site: since 27 Nov 2026 the live page itself, drawn by the service's own code from the site's last day
(`live_snapshot`, `offline_page`), saying the broadcast is not followed.

The last sitting day read from the whole recording afterwards (`data/<N>/snimak/<date>.json`, 18 Nov 2026) is listed
on this page and published as `mikrofon-dan.json`, which the live service shows between sittings in place of its own,
when it is of the same day or a later one: the service may have missed part of the day, the recording has all of it.

"Dok čekate" (18 Nov 2026): a short quiz and the facts, from the site's own counts by the same rules as the pages
they link to, about no MP in particular. The quiz asks for a number (or a word) the site has computed; the wrong
answers are the right one scaled by fixed factors, so nothing about them is chosen by hand. Both are on this page
and in `mikrofon-cekanje.json`, which the live service shows between sittings.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from zailiprotiv import jsonfile, months, offices
from zailiprotiv.config import LIVE
from zailiprotiv.skupstina import sitting_title
from zailiprotiv.translit import latin

PAGE = "mikrofon.html"
DAY_FILE = "mikrofon-dan.json"
WAIT_FILE = "mikrofon-cekanje.json"
# The wrong answers: the right one times one of these pairs, picked by the question's key, so the right one is now the
# smallest, now in the middle, now the largest, in no order a player could learn.
SCALES = ((1.5, 2.4), (0.5, 1.6), (0.35, 0.65))
TZ = ZoneInfo("Europe/Belgrade")


def last_day(root: Path) -> dict | None:
    """The newest day read from a recording, any convocation's."""
    files = sorted(root.glob("*/snimak/*.json"), key=lambda f: f.stem)
    return json.loads(files[-1].read_text(encoding="utf-8")) if files else None


def parts(day: dict) -> list[dict]:
    """The day's recording in the broadcaster's archive, file by file, each with the hours it covers."""
    clock = lambda ts: datetime.fromtimestamp(ts, TZ).strftime("%H:%M")
    return [{"url": p["url"], "from": clock(p["od"] + p.get("preskoceno", 0)), "to": clock(p["od"] + p["trajanje"])}
            for p in day.get("datoteke") or [] if p.get("url") and p.get("od") and p.get("trajanje")]


def turns(day: dict) -> list[dict]:
    """The day's turns for the page, in order: a turn named in a single frame is left out, as on the live page. A
    turn's recording is a file in the broadcaster's archive (`datoteka`, its second as a media fragment), or the
    YouTube video of the live broadcast: the Assembly makes those private after a while (18 Nov 2026)."""
    out = []
    for t in day["govori"]:
        if t.get("okvira", 0) < 2:
            continue
        sec = t["do"] - t["od"]
        rec = t.get("snimak")
        out.append({"od": t["od"], "do": t["do"], "from": datetime.fromtimestamp(t["od"], TZ).strftime("%H:%M"),
                    "to": datetime.fromtimestamp(t["do"], TZ).strftime("%H:%M"),
                    "name": " ".join(t["ime"].split(" ", 1)[::-1]), "slug": t["adresa"], "side": t["uloga"] or t["grupa"],
                    "minutes": max(1, round(sec / 60)),
                    "recording": "" if rec is None else f"{t['datoteka']}#t={rec}" if t.get("datoteka") else
                    f"https://www.youtube.com/watch?v={t['video']}&t={rec}s" if t.get("video") else "",
                    # for the page's player, which opens an archive file in place on a click
                    "file": t.get("datoteka", "") if rec is not None else "", "t": rec or 0})
    return out


def facts(*, stats: dict, numbers: list[dict], items: list[dict], most_against, totals: dict, active: str) -> list[dict]:
    """The facts, each {"text", "href"}: whole numbers from the site's own counts, in a fixed order."""
    out = [{"text": f"Na sajtu je {stats['all_laws']} zakona iz {len(numbers)} saziva, od 2012, i "
                    f"{stats['all_mps']} poslanika, svaki sa svakim svojim glasom.", "href": "zakoni.html", "key": "laws"}]
    n = next((x for x in numbers if x["conv"]["n"] == active), None)
    if n:
        years = n["conv"]["years"]
        if n["with_bill"]:
            out.append({"text": f"U sazivu {years} po hitnom postupku predloženo je {n['urgent']} od "
                                f"{n['with_bill']} zakona.", "href": "brojke.html", "key": "urgent"})
        if n["days"] is not None:
            d = n["days"]
            out.append({"text": f"Polovina zakona u sazivu {years} usvojena je za {d} "
                                f"{'dan' if d % 10 == 1 and d % 100 != 11 else 'dana'} ili manje od podnošenja predloga.",
                        "href": "brojke.html", "key": "days"})
        if n["voted"]:
            out.append({"text": f"{n['unopposed']} od {n['voted']} zakona u sazivu {years} prošlo je bez ijednog "
                                f"glasa protiv.", "href": "brojke.html", "key": "unopposed"})
    top = (most_against(items, 1) or [None])[0]
    if top:
        c = top["final"]["counts"]
        out.append({"text": f"Najveći udeo glasova protiv u sazivu {n['conv']['years'] if n else ''}: "
                            f"{top['law']['short']}, {c['za']} za i {c['protiv']} protiv.".replace("sazivu :", "sazivu:"),
                    "href": f"zakon/{top['slug']}.html", "key": "against"})
    t = next(iter(totals.values()), None)  # the newest convocation with notes read
    if t:
        out.append({"text": f"U {t['sittings']} sednica saziva {t['years']} čije su beleške pročitane: "
                            f"{t['speeches']} govora, {t['measures']} mera predsedavajućeg i {t['exchanges']} "
                            f"razmena replika.", "href": t["page"], "key": "speeches"})
        word, times = t["harsh_word"]
        if word:
            out.append({"text": f"Teška reč izgovorena najčešće u sazivu {t['years']}: „{word}“, u svim oblicima "
                                f"{times} puta.", "href": t["page_who"], "key": "harsh"})
    return out


def options(right: int, turn: int, cap: int | None = None) -> tuple[list[int], int]:
    """Three answers in increasing order and where the right one is: the wrong ones from SCALES[turn], each no
    larger than `cap` (when the question says "of N"), all different; another pair when these won't do."""
    for a, b in SCALES[turn % 3:] + SCALES[:turn % 3]:
        wrong = {max(1, round(right * a)), max(1, round(right * b))} - {right}  # unrounded, like the right one
        if len(wrong) == 2 and (cap is None or max(wrong) <= cap):
            out = sorted(wrong | {right})
            return out, out.index(right)
    return [right], 0


_day = months.day_of  # "20. aprila 2026", as a date is said in a sentence


def _times(n: int) -> str:
    return "put" if n % 10 == 1 and n % 100 != 11 else "puta"


def quiz(*, numbers: list[dict], totals: dict, active: str, items: list[dict] | None = None) -> list[dict]:
    """The questions, each {"key", "q", "options", "answer" (its index), "why", "href"} and maybe "more" (the link's
    words), in a fixed order; a question whose number the site lacks is left out. A fact the quiz asks about (the
    same key) is not listed beside it. Numbers are the site's own counts; the one sentence quoted is chosen by rule
    (`pages_floor.harsh_quote`), and the days and words offered are the three with the most, so nothing is picked."""
    out = []

    def ask(key: str, q: str, right: int, why: str, href: str, cap: int | None = None) -> None:
        opts, at = options(right, sum(map(ord, key)), cap)  # the factors by the question's key: no pattern to learn
        if len(opts) == 3:
            out.append({"key": key, "q": q, "options": [str(o) for o in opts], "answer": at, "why": why, "href": href})

    n = next((x for x in numbers if x["conv"]["n"] == active), None)
    t = next(iter(totals.values()), None)  # the newest convocation with notes read
    top = (t or {}).get("harsh_top") or []
    quote = (t or {}).get("harsh_quote")
    if t and quote and len(top) == 3:  # which word is missing from a sentence said in the hall
        said = quote["word"]
        words = sorted({said, *(w for w, _ in top[1:])}, key=str.lower)  # the quote's word is the commonest one
        if len(words) == 3:
            gap = quote["text"].replace(said, "_____", 1)
            out.append({"key": "quote", "q": f"Koja reč nedostaje? „{gap}“", "options": [f"„{w}“" for w in words],
                        "answer": words.index(said),
                        "why": f"„{quote['text']}“ Rečeno {_day(quote['date'])}." if quote["date"] else f"„{quote['text']}“",
                        "href": quote["url"] or t["page_who"], "more": "Ceo govor" if quote["url"] else ""})
    if n and n["with_bill"]:
        ask("urgent", f"Od {n['with_bill']} zakona u sazivu {n['conv']['years']}, koliko ih je predloženo po hitnom "
                      f"postupku?", n["urgent"], f"{n['urgent']}. Hitni postupak skraćuje rokove za raspravu.",
            "brojke.html", cap=n["with_bill"])
    if t and top:
        word, times = top[0]
        ask("harsh", f"Koliko puta je u sazivu {t['years']} izgovorena reč „{word}“, u svim oblicima?", times,
            f"{times} {_times(times)}. To je teška reč izgovorena najčešće.", t["page_who"])
    passed = Counter((it["law"].get("passed") or "")[:10] for it in items or [] if it["law"].get("passed"))
    if n and passed:
        most_day, most = sorted(passed.items(), key=lambda kv: (-kv[1], kv[0]))[0]
        ask("per_day", f"Koliko je zakona najviše usvojeno u jednom danu u sazivu {n['conv']['years']}?", most,
            f"{most}, {_day(most_day)}. Na sednicama se o zakonima često glasa u nizu, posle zajedničke rasprave.",
            "zakoni.html")
    if n and n["days"] is not None:
        d = n["days"]
        ask("days", f"Za koliko dana od podnošenja predloga je usvojena polovina zakona u sazivu {n['conv']['years']}?",
            d, f"{d} {'dan' if d % 10 == 1 and d % 100 != 11 else 'dana'} ili manje.", "brojke.html")
    if t and t.get("harsh"):
        ask("harsh_all", f"Koliko teških reči (uvreda kao „lopovi“, „izdajnici“, „ološ“) je izgovoreno u sazivu "
                         f"{t['years']}?", t["harsh"],
            f"{t['harsh']}, u {t['sittings']} sednica čije su beleške pročitane.", t["page_who"])
    if t and t.get("measures"):
        ask("measures", f"Koliko puta je predsedavajući u sazivu {t['years']} izrekao meru: opomenu, oduzimanje reči "
                        f"ili udaljenje sa sednice?", t["measures"], f"{t['measures']} {_times(t['measures'])}.",
            t["page"])
    if n and n["voted"]:
        ask("unopposed", f"Od {n['voted']} zakona u sazivu {n['conv']['years']} o kojima se glasalo, koliko ih je "
                         f"prošlo bez ijednog glasa protiv?", n["unopposed"], f"{n['unopposed']}.", "brojke.html",
            cap=n["voted"])
    days = (t or {}).get("harsh_days") or []
    if len(days) == 3:  # the day with the most harsh words, among the three with the most
        dates = sorted(d for d, _ in days)
        first, times = days[0]
        out.append({"key": "harsh_day", "q": f"Kog dana u sazivu {t['years']} je izgovoreno najviše teških reči?",
                    "options": [_day(d) for d in dates], "answer": dates.index(first),
                    "why": f"{_day(first)}: {times} {_times(times)}. Sva tri dana su među onima sa najviše.",
                    "href": t["page_who"]})
    if t:
        ask("speeches", f"Koliko govora je zapisano u stenogramima {t['sittings']} sednica saziva {t['years']}?",
            t["speeches"], f"{t['speeches']}, zajedno sa {t['exchanges']} razmena replika.", t["page"])
    return out


SPEAKERS_FILE = "mikrofon-poslanici.json"
FOLLOW_FILE = "prati-poslanici.json"  # the sitting MPs, for the counter: who can be followed by mail (worker/prati.js)
QUOTE_AT_MOST = 240  # characters: a quote is shown whole or not at all (principle 6), and the box is small


def followable(rows: list[dict], *, latin, given_first, cyr) -> dict[str, list[str]]:
    """Who can be followed by mail, by address: the name as people say it, in both scripts. Every sitting MP, and only
    they (`rows` as in `speakers`)."""
    out = {}
    for r in rows:
        name = given_first(re.sub(r"\s*\(\d{4}\)$", "", latin(r.get("name") or "")).strip())
        if name:
            out[r["slug"]] = [name, cyr(name)]
    return out


def span(convs: list[str]) -> str:
    """Which convocations a number is from, said beside it: "14. saziv", "sazivi 12–14", "sazivi 11, 13, 14"."""
    ns = sorted({int(c) for c in convs})
    if not ns:
        return ""
    if len(ns) == 1:
        return f"{ns[0]}. saziv"
    return f"sazivi {ns[0]}–{ns[-1]}" if ns == list(range(ns[0], ns[-1] + 1)) else "sazivi " + ", ".join(map(str, ns))


def spoken(days: list[dict]) -> dict[str, dict]:
    """Each speaker's time and turns over the convocation's days read from the recording, by the MP's address:
    {"sek", "n", "do": the last day counted}. The live page adds today's to it."""
    out: dict[str, dict] = {}
    last = max((d["dan"] for d in days), default="")
    for d in days:
        for t in d.get("govori", []):
            if t.get("okvira", 0) >= 2 and t.get("adresa"):
                x = out.setdefault(t["adresa"], {"sek": 0, "n": 0, "do": last})
                x["sek"] += max(0, t["do"] - t["od"])
                x["n"] += 1
    return out


def office(o: dict, latin) -> dict:
    """One office for the live page's sheet "O govorniku" (26 Nov 2026): {"v": the kind as offices.json has it, "t":
    the body as the Assembly writes it, empty for the Assembly's own offices, "u": the role}, in Latin, the Assembly's
    own words as on the MP's page (offices.say)."""
    if o["kind"] in ("speaker", "vice"):
        return {"v": o["kind"], "t": "", "u": offices.say(o, latin)}
    role = re.sub(r"\s+делегације$", "", o["role"].strip(), flags=re.I) if o["kind"] == "delegation" else o["role"]
    return {"v": o["kind"], "t": latin(o["body"]).strip(), "u": latin(role).strip().lower()}


def speakers(rows: list[dict], known: dict[str, dict], *, conv: str, spoken_: dict, plain, latin, day,
             offices_read: str = "") -> dict:
    """What the live page says under the speaker, for every MP of the newest convocation, by address. `rows` are its
    members (pages_members.match, with "photo", "offices" in offices.order and "offices_known"); `known` has, for one
    the site knows from earlier roll calls, {"tally", "facts" (the MP page's card), "convs", "quote"}. Each line of "c"
    says where it is from ("iz"), by the same rule for every MP; "za"/"protiv"/"uzdrzan"/"f" stay for a service not
    yet rebuilt. "fn" is every office of the convocation (`office`) and "fn_dan" the day the Assembly's pages were read
    (`offices_read`, the file's "fetched", as a day in Belgrade), for every MP whose offices are known: none for a name
    two MPs share, which gets no office."""
    out = {}
    try:
        read_on = datetime.fromisoformat(offices_read).astimezone(ZoneInfo("Europe/Belgrade")).date().isoformat()
    except ValueError:
        read_on = ""
    for r in rows:
        k = known.get(r["slug"]) if not r["new"] else None
        bio = " · ".join(x for x in (
            (latin(r.get("occupation") or "")[:1].upper() + latin(r.get("occupation") or "")[1:]),
            latin(r.get("place", "")), f"godište {r['year']}" if r.get("year") else "") if x)
        lines = []
        e: dict = {"lista": latin(r.get("group", "") or "")}
        # the name as the list writes it and the party that proposed the MP: the day's mail names every MP so
        # and shows the party of one in no group (live/uzivo/mere.py; 23 Nov 2026)
        # (pages_members.match gives the name as the site writes it, "Brnabić Ana"; a new MP who shares a name
        # with an earlier one has the year after it, "Jovanović Aleksandar (1968)", which no sentence says)
        e["ime"] = re.sub(r"\s*\(\d{4}\)$", "", latin(r.get("name") or "")).strip()
        if (r.get("party") or "").strip() not in ("", "-", "–"):
            e["stranka"] = latin(r["party"].strip())
        if r.get("photo"):
            e["foto"] = r["photo"]
        if k:
            where = span(k["convs"])
            t = k["tally"]
            e.update(za=t.get("za", 0), protiv=t.get("protiv", 0), uzdrzan=t.get("uzdrzan", 0),
                     f=[plain(f) for f in k["facts"][:3]])
            if e["za"] + e["protiv"] + e["uzdrzan"]:
                lines.append({"t": f"{e['za']} za · {e['protiv']} protiv · {e['uzdrzan']} uzdržan na konačnim "
                                   "glasanjima o zakonima.", "iz": where})
            # a line about speeches says the convocations the speeches are from, which may be other than the votes'
            # (19 Nov 2026: a minister's and a president's speeches stood under the one convocation he voted in)
            said = span(k.get("floor_convs") or k["convs"])
            lines += [{"t": x, "iz": where if "glas" in x else said} for x in (plain(f) for f in k["facts"])]
            if k.get("quote"):
                lines.append({"t": f"„{latin(k['quote']['tekst'])}“", "iz": f"stenogram, {day(k['quote']['date'])}"})
            if bio:
                lines.append({"t": bio + ".", "iz": "sajt Skupštine"})
        else:
            e.update(novi=1, f=[bio + "."] if bio else [])
            if bio:
                lines.append({"t": bio + ".", "iz": "sajt Skupštine"})
            lines.append({"t": f"Prvi mandat: nema glasanja u sazivima od 2012. do {conv}. saziva.", "iz": "spiskovi glasanja"})
            party = (r.get("party") or "").strip()
            if party not in ("", "-", "–"):
                lines.append({"t": f"Na predlog stranke: {latin(party)}.", "iz": "sajt Skupštine"})
        held = [o["text"] for o in r.get("offices") or []]
        if held:  # the offices in this convocation first (offices.py), the Assembly's own words, at most three
            lines.insert(0, {"t": "; ".join(held[:3]) + ("; …" if len(held) > 3 else "") + ".", "iz": "sajt Skupštine"})
        e["c"] = lines
        if read_on and r.get("offices_known", True):
            e["fn"] = [office(o, latin) for o in r.get("offices") or []]
            e["fn_dan"] = read_on
        if r["slug"] in spoken_:
            e["sv"] = {**spoken_[r["slug"]], "saziv": conv}
        out[r["slug"]] = e
    return out


def quote(profile: dict | None) -> dict | None:
    """One checked quote of the MP's overview for the live page: the latest said, among those short enough to show
    whole. The same rule for every MP."""
    quotes = [p["citat"] for p in (profile or {}).get("points", [])
              if p.get("citat") and p["citat"].get("date") and len(p["citat"].get("tekst", "")) <= QUOTE_AT_MOST]
    return max(quotes, key=lambda q: q["date"], default=None)


def besides(facts_: list[dict], quiz_: list[dict]) -> list[dict]:
    """The facts the quiz does not ask about: listed below it, they would give its answers away."""
    asked = {q["key"] for q in quiz_}
    return [f for f in facts_ if f.get("key") not in asked]


NOTICES_FILE = "obavestenja.json"  # data/obavestenja.json


def notices(root) -> list[dict]:
    """What the Assembly has decided that the live page should say on top (19 Nov 2026: a Speaker elected), written
    by hand into data/obavestenja.json, each a sentence of fact with its source: [{"od", "do", "tekst", "izvor",
    "url", "adresa"}]. Only what the source says, no comment; shown from "od" until "do". A notice of when a sitting
    goes on may also say it as "pocinje" ("2026-11-24T10:00"), for the site's announcement (next_start)."""
    path = Path(root) / NOTICES_FILE
    if not path.exists():
        return []
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return []
    return [{k: str(r.get(k, "")) for k in ("od", "do", "tekst", "izvor", "url", "adresa")}
            for r in rows if isinstance(r, dict) and r.get("tekst") and str(r.get("url", "")).startswith("https://")]


WEEKDAYS = ("ponedeljak", "utorak", "sreda", "četvrtak", "petak", "subota", "nedelja")


def _called(s: dict) -> bool:
    """A sitting convened and not voted at yet: with its agenda, or by its title when its page's agenda is not read
    (25 Nov 2026: one told in a sentence made the Ninth extraordinary session no sitting)."""
    return not s.get("votes") and bool(s.get("agenda") or (s.get("starts") and sitting_title(s.get("title", ""))))


def sittings(root, conv: str) -> list[dict]:
    """The convocation's sittings as the Assembly lists them, the latest begun or convened first (one whose page gives no
    day last): [{"title", "url", "starts", "agenda"}], in Latin. Also one whose agenda is not read, so that an earlier
    sitting's is not taken for its own."""
    try:
        listed = jsonfile.load(Path(root) / str(conv) / "index.json", {}).get("sittings", {})
    except (ValueError, AttributeError):
        listed = {}
    rows = [{"title": latin(s.get("title", "")), "url": u, "starts": s.get("starts", ""),
             "agenda": [latin(x).removesuffix(" i") for x in s.get("agenda") or []]}
            for u, s in listed.items() if s.get("agenda") or sitting_title(s.get("title", ""))]
    return sorted(rows, key=lambda r: r["starts"], reverse=True)


def current_sitting(rows: list[dict], now: datetime | None = None) -> dict | None:
    """Of `sittings`, the one to speak of: the nearest of today or to come, else the latest begun."""
    today = (now or datetime.now(TZ)).astimezone(TZ).date().isoformat()
    return min((r for r in rows if r["starts"][:10] >= today), key=lambda r: r["starts"], default=None) or next(iter(rows), None)


def read_live(rows: list[dict], now: datetime | None = None) -> list[str]:
    """The pages the live service reads during a broadcast (hronika.Watcher): the latest sitting begun and those to come,
    not the closed ones, whose later sentences are no news of the day."""
    today = (now or datetime.now(TZ)).astimezone(TZ).date().isoformat()
    begun = [r["url"] for r in rows if r["starts"][:10] <= today]
    return [r["url"] for r in rows if r["starts"][:10] > today] + begun[:1]


def label(title: str) -> str:
    """A sitting's short name, from its title: "Prva sednica", "Druga sednica Drugog redovnog zasedanja"."""
    return title.split(" Narodne skupštine")[0].strip()


def next_start(root, conv: str, now: datetime | None = None) -> dict | None:
    """When the Assembly sits next, for the site's way to the live page (22 Nov 2026): the first sitting of the
    convocation convened for today or later, as the Assembly lists it (data/<N>/index.json "starts"), or the next day
    of a sitting going on, as its page at the Assembly says ("continues", skupstina.continues) or a notice gives it
    ("pocinje" beside the notice's sentence in data/obavestenja.json, written by hand from the Assembly's site). The
    nearest still to come; today's, its hour past, only when no other is known. Times are Belgrade's; the page's script shows the announcement from
    the day before ("od") until the start ("u"), "sutra" until the day itself begins ("dan"). None when none is known."""
    now = now or datetime.now(TZ)
    today = now.date().isoformat()
    found = []
    try:
        listed = jsonfile.load(Path(root) / str(conv) / "index.json", {}).get("sittings", {})
    except (ValueError, AttributeError):
        listed = {}
    for s in listed.values():
        at = str(s.get("starts") or "")
        if _called(s) and len(at) >= 16:
            found.append(at[:16])
        if len(str(s.get("continues") or "")) >= 16:
            found.append(s["continues"][:16])
    try:
        rows = json.loads((Path(root) / NOTICES_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        rows = []
    for r in rows if isinstance(rows, list) else []:
        at = str(r.get("pocinje", "")) if isinstance(r, dict) else ""
        if len(at) >= 16:
            found.append(at[:16])
    starts = []
    for at in found:
        try:
            starts.append(datetime.fromisoformat(at).replace(tzinfo=TZ))
        except ValueError:
            pass
    start = min((s for s in starts if s > now), default=None) or max(
        (s for s in starts if s.date().isoformat() == today), default=None)
    if start is None:
        return None
    day0 = start.replace(hour=0, minute=0)
    before = day0 - timedelta(days=1)
    hour = f"{start.hour} h" if not start.minute else f"{start.hour}.{start.minute:02d} h"
    return {"pocinje": start.strftime("%Y-%m-%dT%H:%M"), "sat": hour,
            "dan": f"{WEEKDAYS[start.weekday()]}, {start.day}. {months.NAMES[start.month - 1]}",
            "od": int(before.timestamp()), "dan_od": int(day0.timestamp()), "u": int(start.timestamp())}


def fixes(root) -> dict:
    """The corrections to the automatic transcript, written by hand (data/prepis-ispravke.json): {as Whisper writes
    it: as it is written}, spellings only."""
    path = Path(root) / "prepis-ispravke.json"
    try:
        rows = jsonfile.load(path, {})
    except ValueError:
        return {}
    return {str(k): str(v) for k, v in rows.items() if str(k).strip() and str(v).strip()} if isinstance(rows, dict) else {}


def agenda(root, conv: str, sittings: list[dict]) -> list[dict]:
    """The agenda of each sitting of the convocation as the Assembly lists it, with the items the Assembly's page of
    the sitting says are done: [{"naslov", "url", "pocinje", "tacke": [{"n", "tekst", "gotova", "kada", "sta"}]}]. What is done
    is written by hand into data/<N>/tacke.json from that page ({sitting's address: {item's number: {"kada", "sta"}}}),
    a sentence of fact each; the live service adds what the chair says aloud (hronika.py)."""
    path = Path(root) / str(conv) / "tacke.json"
    try:
        done = jsonfile.load(path, {})
    except ValueError:
        done = {}
    out = []
    for s in sittings:
        mine = done.get(s["url"]) or {}
        out.append({"naslov": s["title"], "url": s["url"], "pocinje": s.get("starts", ""), "tacke": [
            {"n": i, "tekst": a, "gotova": str(i) in mine, "kada": (mine.get(str(i)) or {}).get("kada", ""),
             "sta": (mine.get(str(i)) or {}).get("sta", "")} for i, a in enumerate(s["agenda"], 1)]})
    return out


def upcoming(root: Path, coming: list[dict], conv: str) -> list[dict]:
    """The sittings convened that the live page may count down to: the current convocation's (`coming`, from the
    bills in procedure) and the newest convocation's from its index (`conv`; before its first law the current one
    is the earlier convocation, whose listing the Assembly no longer shows): a sitting with an agenda and no roll
    calls yet, once each; and one already begun, at the day its page says the Assembly goes on with it ("continues",
    25 Nov 2026), with no agenda of its own: the live page has it as the agenda of the sitting under way."""
    out, seen = [], {c.get("url") for c in coming}
    try:
        listed = json.loads((Path(root) / str(conv) / "index.json").read_text(encoding="utf-8"))["sittings"]
    except (OSError, ValueError, KeyError):
        listed = {}
    for url, s in listed.items():
        if s.get("continues"):
            out.append({"title": s.get("title", ""), "url": url, "starts": s["continues"], "agenda": [], "goes_on": True})
        if _called(s) and url not in seen:
            out.append({"title": s.get("title", ""), "url": url, "starts": s.get("starts", ""), "agenda": s.get("agenda") or []})
    return [*coming, *out]


def waiting(facts_: list[dict], quiz_: list[dict], coming: list[dict] | None = None,
            notices_: list[dict] | None = None, sittings_: list[str] | None = None,
            agenda_: list[dict] | None = None, fixes_: dict | None = None, now: datetime | None = None,
            days_: list[str] | None = None, notes_: list[str] | None = None) -> dict:
    """"Dok čekate" for the live service: links as addresses under the site (no ".html", as the site's own); and the
    next sitting convened, as the Assembly lists it ("sazvano": title, address, when it starts, its agenda; "nastavak"
    for one already begun that goes on then)."""
    plain = lambda h: h if h.startswith("http") else h.removesuffix(".html")
    out = {"kviz": [{**q, "href": plain(q["href"])} for q in quiz_],
           "cinjenice": [{**f, "href": plain(f["href"])} for f in besides(facts_, quiz_)]}
    # The next sitting: the first convened for today or later (one convened earlier and not yet voted on is not
    # "next"), with its agenda, for the live page's countdown (20 Nov 2026); one whose hour has come today only when
    # no other is known (the live page takes it off once it has begun).
    at = (now or datetime.now(TZ)).astimezone(TZ).strftime("%Y-%m-%dT%H:%M")
    when = lambda c: c.get("starts") or ""
    rows = sorted((c for c in coming or [] if when(c)[:10] >= at[:10]), key=when)
    c = next((c for c in rows if when(c) > at or len(when(c)) == 10), rows[-1] if rows else None)
    if c:
        out["sazvano"] = {"naslov": latin(c.get("title", "")), "url": c.get("url", ""), "pocinje": c.get("starts", ""),
                          "tacke": [latin(a) for a in c.get("agenda") or []]}
        if c.get("goes_on"):
            out["sazvano"]["nastavak"] = True
    if notices_:
        out["obavestenja"] = notices_
    if agenda_:
        out["dnevni_red"] = agenda_
    if fixes_:  # corrections to the automatic transcript (live/uzivo/ispravke.py)
        out["ispravke"] = fixes_
    if days_:  # the days the site has a page of (govornici/<day>), where a shared speech of an earlier day leads
        out["dani"] = sorted(days_)
    if notes_:  # of those, the days made from the Assembly's notes: the live service's own record of them says so (/dan/<day>.json)
        out["iz_beleski"] = sorted(notes_)
    if sittings_:  # the pages of the sittings going on, which the service reads for what the Assembly adds (hronika.py)
        out["sednice"] = sittings_
    return out


LIVE_DIR = Path(__file__).resolve().parents[2] / "live"  # the live service's code (live/uzivo), as ko.py takes it


def _uzivo():
    """The live service's page and state (live/uzivo): only the standard library, as the repository's tests render it."""
    if str(LIVE_DIR) not in sys.path:
        sys.path.insert(0, str(LIVE_DIR))
    from uzivo import page as live_page, state
    return live_page, state


def live_snapshot(day: dict | None, *, facts: dict, waiting_: dict, summary: dict | None = None,
                  now: float | None = None) -> dict:
    """What the live service shows between sittings with the site's last day read from the recording, made by the
    service's own state (state.Tracker, its `use_recording`, `use_facts`, `use_waiting` and `snapshot`, as it takes
    mikrofon-dan.json, mikrofon-poslanici.json and mikrofon-cekanje.json from the site), so the page drawn from it is
    the live page's own (27 Nov 2026, the maintainer: the page while the service is off to look like the live one).
    Taken on the day after the shown one at the earliest, as the service lists an earlier day. The day's summary,
    where the site has it, as the service shows it (state_view._summary_shown). A day with turns that comes out with
    none fails the build here rather than draw an empty list."""
    if day and (not isinstance(day.get("dan"), str) or not isinstance(day.get("govori"), list)):
        raise ValueError("the last day read from the recording is not shaped as the live service takes it")  # it ignores it
    _, state = _uzivo()
    t = state.Tracker(None, "Europe/Belgrade")
    t.use_facts(facts)
    t.use_waiting(waiting_)
    if day:
        t.use_recording(day)
    after = datetime.fromisoformat(day["dan"]).replace(tzinfo=TZ) + timedelta(days=1) if day else datetime.now(TZ)
    snap = t.snapshot(max(now or datetime.now(TZ).timestamp(), after.timestamp()))
    if summary and summary.get("ukratko"):
        snap["sazetak"] = {"vrsta": "dan", **{k: summary.get(k) for k in ("kratko", "ukratko", "odluke", "model")}}
    shown = [x for x in (day or {}).get("govori") or [] if x.get("okvira", 0) >= 2]
    if shown and (snap.get("dan") != day["dan"] or len(snap.get("danas") or []) != len(shown)):
        raise ValueError(f"the live service's snapshot of {day['dan']} lists {len(snap.get('danas') or [])} turns of {len(shown)}")
    return snap


def offline_page(snap: dict, *, cyr: bool, waiting_: dict, api: str = "", analytics: str = "", live: str = "") -> str:
    """mikrofon.html (and cir/mikrofon.html): the live page itself (page.page, `off`), drawn from `live_snapshot`. Shown
    at mikrofon.zailiprotiv.rs by the edge worker (live/edge) while the service is down, under a <base> that points
    relative links to the site, and at zailiprotiv.rs/mikrofon: so the site's links are relative (one folder down
    for Cyrillic), and the page's links to the service's own addresses ("/cir/", "/govor/<second>") lead there."""
    live_page, _ = _uzivo()
    html = live_page.page(snap, cyr=cyr, site="../" if cyr else "./", tz=TZ, waiting=waiting_, api=api.rstrip("/"),
                          analytics=analytics, off=True)
    own = live.rstrip("/")
    return re.sub(r'\b(href|data-share)="/(?!/)', lambda m: f'{m[1]}="{own}/', html) if own else html


def render(*, common: dict, env, out, facts_: list[dict], coming: list[dict], day: dict | None = None,
           quiz_: list[dict] | None = None, notices_: list[dict] | None = None,
           sittings_: list[str] | None = None, agenda_: list[dict] | None = None, fixes_: dict | None = None,
           next_: list[dict] | None = None, days_: list[str] | None = None, notes_: list[str] | None = None,
           summary: dict | None = None) -> str:
    """mikrofon.html, the live page as the service draws it between sittings (`offline_page`), noindex, so out of the
    sitemap; with the last day read from a recording, the day as mikrofon-dan.json for the live service, and "Dok
    čekate" as mikrofon-cekanje.json. Returns cir/mikrofon.html, written after the site's Cyrillic edition (which
    would write it again from the Latin)."""
    told = waiting(facts_, quiz_ or [], coming if next_ is None else next_, notices_, sittings_, agenda_, fixes_,
                   days_=days_, notes_=notes_)
    (out / WAIT_FILE).write_text(json.dumps(told, ensure_ascii=False), encoding="utf-8")
    if day:
        (out / DAY_FILE).write_text(json.dumps(day, ensure_ascii=False), encoding="utf-8")
    try:
        facts = json.loads((out / SPEAKERS_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        facts = {}
    snap = live_snapshot(day, facts=facts, waiting_=told, summary=summary)
    g = env.globals
    draw = lambda cyr: offline_page(snap, cyr=cyr, waiting_=told, api=g.get("votes_api", ""),
                                    analytics=common.get("analytics", ""), live=g.get("live_page", ""))
    (out / PAGE).write_text(draw(False), encoding="utf-8")
    return draw(True)
