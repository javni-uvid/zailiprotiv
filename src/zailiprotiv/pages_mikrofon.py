"""The page shown at mikrofon.zailiprotiv.rs while "Ko sada govori" is down (17 Nov 2026).

"Ko sada govori" (live/) runs on the maintainer's computer behind a Cloudflare tunnel; when the computer is off,
Cloudflare answers with its own error. The edge worker (live/edge/) then shows this page instead, built with the
site: what the page is and why it is down, where the broadcast is, the next sitting convened, and a few facts from
the site's data, each by the same rule as on the page it links to, about no MP in particular.

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
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from zailiprotiv.config import LIVE

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
    return [{"url": p["url"], "from": clock(p["od"]), "to": clock(p["od"] + p["trajanje"])}
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
        out.append({"from": datetime.fromtimestamp(t["od"], TZ).strftime("%H:%M"),
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


MONTHS_OF = ("januara", "februara", "marta", "aprila", "maja", "juna", "jula", "avgusta", "septembra", "oktobra",
             "novembra", "decembra")


def _day(iso: str) -> str:
    """"20. aprila 2026", as a date is said in a sentence."""
    y, m, d = iso[:10].split("-")
    return f"{int(d)}. {MONTHS_OF[int(m) - 1]} {y}"


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
QUOTE_AT_MOST = 240  # characters: a quote is shown whole or not at all (principle 6), and the box is small


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


def speakers(rows: list[dict], known: dict[str, dict], *, conv: str, spoken_: dict, plain, latin, day) -> dict:
    """What the live page says under the speaker, for every MP of the newest convocation, by address. `rows` are its
    members (pages_members.match, with "photo"); `known` has, for one the site knows from earlier roll calls,
    {"tally", "facts" (the MP page's card), "convs", "quote"}. Each line of "c" says where it is from ("iz"), by the
    same rule for every MP; "za"/"protiv"/"uzdrzan"/"f" stay for a service not yet rebuilt."""
    out = {}
    for r in rows:
        k = known.get(r["slug"]) if not r["new"] else None
        bio = " · ".join(x for x in (
            (latin(r.get("occupation") or "")[:1].upper() + latin(r.get("occupation") or "")[1:]),
            latin(r.get("place", "")), f"godište {r['year']}" if r.get("year") else "") if x)
        lines = []
        e: dict = {"lista": latin(r.get("group", "") or "")}
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
        e["c"] = lines
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
    "url", "adresa"}]. Only what the source says, no comment; shown from "od" until "do"."""
    path = Path(root) / NOTICES_FILE
    if not path.exists():
        return []
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return []
    return [{k: str(r.get(k, "")) for k in ("od", "do", "tekst", "izvor", "url", "adresa")}
            for r in rows if isinstance(r, dict) and r.get("tekst") and str(r.get("url", "")).startswith("https://")]


def waiting(facts_: list[dict], quiz_: list[dict], coming: list[dict] | None = None,
            notices_: list[dict] | None = None, sittings_: list[str] | None = None) -> dict:
    """"Dok čekate" for the live service: links as addresses under the site (no ".html", as the site's own); and the
    next sitting convened, as the Assembly lists it ("sazvano": title, address, when it starts)."""
    plain = lambda h: h if h.startswith("http") else h.removesuffix(".html")
    out = {"kviz": [{**q, "href": plain(q["href"])} for q in quiz_],
           "cinjenice": [{**f, "href": plain(f["href"])} for f in besides(facts_, quiz_)]}
    if coming:
        c = coming[0]
        out["sazvano"] = {"naslov": latin(c.get("title", "")), "url": c.get("url", ""), "pocinje": c.get("starts", "")}
    if notices_:
        out["obavestenja"] = notices_
    if sittings_:  # the pages of the sittings going on, which the service reads for what the Assembly adds (hronika.py)
        out["sednice"] = sittings_
    return out


def render(*, common: dict, env, out, facts_: list[dict], coming: list[dict], day: dict | None = None,
           quiz_: list[dict] | None = None, notices_: list[dict] | None = None,
           sittings_: list[str] | None = None) -> None:
    """mikrofon.html: an ordinary page of the site (its links relative), which the edge worker (live/edge) shows at
    mikrofon.zailiprotiv.rs with a <base> pointing them back to the site; noindex, so out of the sitemap. With the
    last day read from a recording, its list too, and the day as mikrofon-dan.json for the live service."""
    (out / PAGE).write_text(env.get_template("mikrofon.html").render(
        **common, facts=besides(facts_, quiz_ or []), quiz=quiz_ or [], coming=coming[:1], broadcast=LIVE, root="",
        day=day["dan"] if day else "", day_turns=turns(day) if day else [], day_parts=parts(day) if day else []),
        encoding="utf-8")
    (out / WAIT_FILE).write_text(json.dumps(waiting(facts_, quiz_ or [], coming, notices_, sittings_), ensure_ascii=False), encoding="utf-8")
    if day:
        (out / DAY_FILE).write_text(json.dumps(day, ensure_ascii=False), encoding="utf-8")
