"""From the stenographic notes read, by rule and with no model: the measures the chair pronounced (a warning, taking
the floor away, removal from the sitting) and the exchanges of replies between two speakers.

Everything is given word for word (principle 6): the chair's words that pronounce the measure with the speech
before them, and every speech of an exchange. The site doesn't say who was right or what an exchange was "about".
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from zailiprotiv import debates as debates_, mps, notes_site, poslovnik
from zailiprotiv.config import CONVOCATIONS
from zailiprotiv.measures import (MEASURES, _END, by_context, measures, present, pronounced, sentence, sentences,  # noqa: F401
                                    to_whom)
from zailiprotiv.site import ORDINAL_NAME, slug
from zailiprotiv.translit import latin

TURNS = 4      # an exchange: this many speeches or more, two speakers taking turns
SHORT = 400    # … none longer than this many words (a reply is short; a speech on the agenda is not)


_MARK = re.compile(r"^\s*\d+/\d+\s*[A-ZА-ЯЈЉЊЂЋЏ]{1,3}\s*/\s*[A-ZА-ЯЈЉЊЂЋЏ]{1,3}\s*$", re.M)


def spoken(text: str) -> str:
    """A speech without the stenographers' page marks ("39/2AL/JG"), which are not anyone's words."""
    return _MARK.sub("", text).strip()


_ASIDE = re.compile(r"\(([^():]{3,60}):\s*([^()]{1,400})\)")   # "(Бошко Обрадовић: Не директно.)": words from the floor
_BRACKET = re.compile(r"\s*\([^()]*\)")
_REASON = re.compile(r"^\s*(?:Зато|Због|Јер)\b|\bзато што\b|\bзбог\b", re.I)


def around(measure: dict, to: str | None) -> dict:
    """What the notes hold right around a measure, word for word, for the reader to see what it was about without
    anyone saying so for them:
    - "lead": the chair's own words up to the measure (two sentences at most) and, when the next sentence gives the
      reason ("Зато што …"), that one too;
    - "asides": what the person the measure went to called out from their seat, as the notes record it in brackets
      in the speech before and in the chair's words up to the measure;
    - "last": the end of the speech before, when it was that person's and the measure came right after it.
    Nothing here says why the measure was pronounced: it shows what was said before it."""
    chair, at = measure["chair"]["text"], measure["at"]
    end = chair.find(measure["sentence"], max(0, at - len(measure["sentence"])))
    end = (end if end >= 0 else at) + len(measure["sentence"])
    start = end - len(measure["sentence"])
    upto = chair[:start] + (")" if chair[:start].count("(") > chair[:start].count(")") else "")  # a bracket cut by the sentence
    lead = sentences(_BRACKET.sub("", upto))[-2:]
    while lead and sum(len(x) for x in lead) > 420:
        lead = lead[1:]
    after = sentences(_BRACKET.sub("", chair[end:]))[:1]
    after = after if after and _REASON.search(after[0]) and len(after[0]) < 420 else []
    surname = to.split()[-1].lower() if to and to.split() else None
    mine = lambda name: surname is None or name.strip().split()[-1].lower() == surname
    before = measure["before"]
    near = (before["text"][-700:] if before and measure["adjacent"] else "") + "\n" + upto
    asides = [(n.strip(), t.strip()) for n, t in _ASIDE.findall(near) if mine(n)][-3:]
    last = []
    if before and measure["adjacent"] and (surname is None or before["speaker"].split()[-1].lower() == surname):
        last = sentences(_BRACKET.sub("", before["text"][-900:]))[-2:]
        if len(before["text"]) > 900:
            last = last[-2:] if len(sentences(before["text"][-900:])) > 2 else last[-1:]
        while len(last) > 1 and sum(len(x) for x in last) > 420:
            last = last[1:]
    return {"lead": " ".join(lead), "after": " ".join(after), "asides": asides,
            "last": marked(" ".join(last)) if last else [], "last_who": before["speaker"] if last else ""}


def exchanges(speeches: list[dict]) -> list[list[dict]]:
    """Runs of speeches in which two speakers take turns, with the chair's words between them."""
    idx = [i for i, s in enumerate(speeches) if not s.get("chair")]
    out, i = [], 0
    while i < len(idx) - TURNS + 1:
        a, b = speeches[idx[i]]["speaker"], speeches[idx[i + 1]]["speaker"]
        j = i
        while (j < len(idx) and a != b and speeches[idx[j]]["speaker"] == (a if (j - i) % 2 == 0 else b)
               and speeches[idx[j]]["day"] == speeches[idx[i]]["day"] and len(speeches[idx[j]]["text"].split()) <= SHORT):
            j += 1
        if j - i >= TURNS:
            out.append(speeches[idx[i]:idx[j - 1] + 1])
            i = j
        else:
            i += 1
    return out


_POINT = notes_site._POINT_OF_ORDER  # a speech pointing out a breach of the Rules (one pattern for both)
# Harsh words: a fixed list, the same for everyone, of words that are abuse in nearly every use (words with an
# everyday meaning too, like "ђубре", "свиња", "криминал", "фашиста", are left out: they would count talk about waste,
# farming, crime and history). What is counted is that the word was spoken: not at whom, and not whether the
# speaker was quoting someone. Each one is shown in its sentence.
HARSH = ("олош", "стоко", "лопуж", "лопов", "битанг", "гамад", "шљам", "кретен", "имбецил", "идиот", "дебил", "морон",
         "будал", "нељуд", "лажов", "џукел", "фукар", "пробисвет", "ништак", "говнар", "вуцибатин", "издајни[кц]",
         "курв", "говн", "пичк", "шупак", "шупк", "дупе")
# … as names for people: not "лоповлук" and "лоповски" (theft), "нељудски", or "стоком" (cattle; only the vocative).
_NOT = {"лопов": "(?!лу|ск)", "нељуд": "(?!ск)", "стоко": "(?!\\w)"}
_HARSH = re.compile(r"(?<!\w)(?:(?:" + "|".join(w + _NOT.get(w, "") for w in HARSH) + r")\w*|\w*јеб\w*)", re.I)
# What every harsh word holds, as plain text: a speech with none of these (nearly all) is not searched word by word,
# which took a site build some 20 s.
_HARSH_IN = tuple({w.split("[")[0] for w in HARSH} | {"јеб"})
TOP = 25
PER_PAGE = 20


def harsh(text: str) -> list[tuple[str, str]]:
    """(word, its sentence) for each harsh word in a speech."""
    out = []
    folded = text.casefold()  # as re.I compares letters
    if not any(w in folded for w in _HARSH_IN):
        return out
    for m in _HARSH.finditer(text):
        out.append((m.group(0).lower(), sentence(text, m.start(), m.end())))
    return out


def marked(sentence: str) -> list[tuple[str, bool]]:
    """A sentence in pieces, the harsh words apart, for the page to set them in bold."""
    out, at = [], 0
    for m in _HARSH.finditer(sentence):
        out += [(sentence[at:m.start()], False), (m.group(0), True)]
        at = m.end()
    return out + [(sentence[at:], False)]


_PAUSE = re.compile(r"одређујем паузу|прекидам седницу|прекидам рад", re.I)


def _tail(link: str) -> str:
    """A speech's address in the sitting's folder, short: "dan-3-2.html#g00527" → "3-2.00527" (site.js makes it whole)."""
    tail = link.rsplit("/", 1)[1]
    m = re.fullmatch(r"dan-([\d-]+)\.html#g(\d+)", tail)
    return f"{m.group(1)}.{m.group(2)}" if m else tail


def spoken_by_sitting(days) -> list[dict]:
    """An MP's speeches for the MP's page: one row to a sitting (newest first), its days in order, each day's
    speeches as short addresses. The longest MP pages hold thousands of speeches, so nothing is said twice."""
    by = {}
    for d in days:
        s = by.setdefault((d["links"][0].rsplit("/", 1)[0], d["sitting"]), {"sitting": d["sitting"], "base": d["links"][0].rsplit("/", 1)[0] + "/",
                                                                            "first": d["date"], "last": d["date"], "days": [], "n": 0})
        s["days"].append({"day": d["day"], "date": d["date"], "first": d["links"][0], "n": len(d["links"]),
                          "tails": " ".join(_tail(l) for l in d["links"])})
        s["n"] += len(d["links"])
        s["first"], s["last"] = min(s["first"] or d["date"], d["date"] or s["first"]), max(s["last"], d["date"])
    for s in by.values():
        s["days"].sort(key=lambda d: d["day"])  # the notes number the days; a day may lack its date
    return sorted(by.values(), key=lambda s: s["last"], reverse=True)


def firsts(rows) -> dict[str, list]:
    """The first TOP of the rows by each count, the same rule for everyone; ties by name."""
    def first(key):
        n = lambda r: len(r[key]) if key == "harsh" else r[key]
        return [r for r in sorted(rows, key=lambda r: (-n(r), r["who"]["name"])) if n(r)][:TOP]
    return {k: first(k) for k in ("speeches", "exchanges", "points", "measures", "harsh")}


def together(by_conv: list[dict]) -> dict:
    """All the convocations read as one: a person's counts added up across them (one row for one MP, by the MP's
    page, or by the name for a speaker who has none), and the first TOP by each count."""
    rows, as_mp = {}, {}  # everyone who spoke; and MPs, counted only in the convocations they sat in
    for c in by_conv:
        for r in c["people"]:
            for into in [rows] + ([as_mp] if r["who"]["slug"] and not r.get("outside") else []):
                t = into.setdefault(r["who"]["slug"] or r["who"]["name"], {
                    "who": r["who"], "speeches": 0, "words": 0, "points": 0, "exchanges": 0, "measures": 0,
                    "measures_likely": 0, "harsh": [], "convs": []})
                for k in ("speeches", "words", "points", "exchanges", "measures", "measures_likely"):
                    t[k] += r[k]
                t["harsh"] = t["harsh"] + r["harsh"]
                t["convs"].append(c["n"])
                if r["who"]["photo"] and not t["who"]["photo"]:
                    t["who"] = r["who"]
    for t in list(rows.values()) + list(as_mp.values()):
        t["harsh"].sort(key=lambda h: h["date"], reverse=True)
        t["said"] = list({(h["date"], h["text"]): h for h in t["harsh"]}.values())
        t["harsh_words"] = [w for w, _ in Counter(latin(h["word"]) for h in t["harsh"]).most_common(4)]
    first, last = by_conv[-1]["years"].split("–")[0], by_conv[0]["years"].split("–")[-1]
    return {"n": "svi", "name": "Svi", "years": f"{first}–{last}" if first != last else first, "top": firsts(as_mp.values()),
            "people": sorted(rows.values(), key=lambda r: r["who"]["name"]), "speakers": len(rows),
            "sittings": sum(c["sittings"] for c in by_conv), "measures": [e for c in by_conv for e in c["measures"]],
            "invoked": sum((c.get("invoked", Counter()) for c in by_conv), Counter()),
            "exchanges": [e for c in by_conv for e in c["exchanges"]], "page": ALL, "page_exchanges": ALL, "page_who": ALL,
            "convs": [{"n": c["n"], "name": c["name"], "years": c["years"], "page": c["page"], "page_who": c["page_who"],
                       "page_exchanges": c["page_exchanges"], "sittings": c["sittings"], "speakers": c["speakers"],
                       "measures": len(c["measures"]), "exchanges": len(c["exchanges"]),
                       "harsh": sum(len(r["harsh"]) for r in c["people"]),
                       "first": {k: (v[0] if v else None) for k, v in c["top"].items()}} for c in by_conv]}


ALL = "varnice-svi.html"  # every convocation read, counted together
RULES = "poslovnik-clanovi.html"  # the Rules' articles invoked in the debates, every convocation


def invoked_articles(total: Counter, by_conv: list[dict], rules: dict | None) -> list[dict]:
    """The Rules' articles invoked in the debates (poslovnik.cited), most first then by number: each with its count,
    its count per convocation (newest first), its chapter and section, its text as the Rules now read, and its
    chapter's page at the Assembly. Empty without the Rules."""
    if not rules:
        return []
    art = {a["n"]: a for a in rules["clanovi"]}
    chapters = {c["broj"]: c for c in rules["glave"]}
    out = []
    for n, count in sorted(total.items(), key=lambda x: (-x[1], x[0])):
        a = art.get(n)
        if not a:
            continue
        ch = chapters.get(a["glava"], {})
        out.append({"n": n, "label": a["oznaka"], "count": count,
                    "convs": [{"name": c["name"], "count": c["invoked"][n]} for c in by_conv if c.get("invoked", {}).get(n)],
                    "chapter": latin(ch.get("naslov", "")).capitalize(), "section": latin(a.get("odeljak", "")),
                    "short": latin(poslovnik.short(a)), "text": [latin(s) for s in a["stavovi"]], "url": ch.get("url", "")})
    return out


def rule_terms(terms: list[dict], invoked: list[dict], rules: dict | None) -> list[dict]:
    """The site's terms explained from the Rules (poslovnik.terms), in Latin script: our sentence (None once an
    article it rests on has changed), how the site counts it, and each article with its text, its chapter's page at the
    Assembly and whether it is in the list of invoked articles (then it leads there too)."""
    if not rules:
        return []
    chapters = {c["broj"]: c for c in rules["glave"]}
    listed = {a["n"] for a in invoked}
    return [{"id": t["id"], "name": t["pojam"], "explained": None if t["changed"] else t["objasnjenje"],
             "on_site": t.get("na_sajtu", ""), "method": t.get("kako", ""),
             "articles": [{"n": a["n"], "label": a["label"], "text": [latin(x) for x in a["text"]],
                           "url": chapters.get(a["glava"], {}).get("url", ""), "listed": a["n"] in listed}
                          for a in t["articles"]]} for t in terms]


@dataclass
class Floor:
    """What the notes count, for the pages of "Varnice" and for the pages that show a part of it."""
    by_conv: list[dict]  # a convocation's events, table and counts, newest first, with its pages' names
    chunks: dict[str, list[tuple[list, str]]]  # a convocation's exchanges, PER_PAGE to a page, with the page's name
    everyone: dict | None  # every convocation together (more than one read)
    invoked: list  # the articles of the Rules invoked, for the page of every convocation
    terms: list  # the site's terms explained from the Rules (rule_terms), on the same page
    by_mp: dict  # an MP's exchanges, by the MP's address
    by_law: dict  # the events of a law's debate, by the law's key
    by_sitting: dict  # a sitting's row of the table, by its address
    per_mp: dict  # an MP's own counts in each convocation, by the MP's address
    top: dict  # the first of each count, by convocation
    totals: dict  # each convocation's totals


def count(*, debates: dict, people: dict, convs: list, items_by_conv: dict, photo_of: dict | None = None,
          years_of: dict | None = None, notes_url: str = "", notes_pages: set | None = None,
          seated: dict | None = None, extra: dict | None = None, rules: dict | None = None,
          terms: list | None = None) -> Floor:
    """`terms`: poslovnik.terms. `extra`: MPs not on any roll call yet (a new convocation's new members), by their loose name key:
    {"name", "slug", "photo"}, so that their speeches lead to their pages too."""
    loose = {debates_.loose(k): k for k in people}
    years_of = years_of or {}
    extra = extra or {}

    def who(name: str) -> dict:
        key = loose.get(debates_.loose(mps.key(name)))
        if not key and debates_.loose(mps.key(name)) in extra:
            return dict(extra[debates_.loose(mps.key(name))])
        return {"name": people[key].name if key else latin(name).title(), "slug": people[key].slug if key else "",
                "photo": (photo_of or {}).get(key, "") if key else ""}

    # The law debated under an agenda item of a sitting, where the notes tell.
    law_at = {(it["final"]["sitting"], str(it["debate"]["item"])): it for its in items_by_conv.values() for it in its
              if it.get("final") and it.get("debate") and it["debate"].get("item")}
    by_conv, by_mp, by_law = [], defaultdict(list), defaultdict(list)
    per_mp = defaultdict(list)
    for c, _ in convs:
        events, sittings = [], []
        tally = defaultdict(lambda: {"speeches": 0, "words": 0, "points": 0, "exchanges": 0, "measures": 0,
                                     "measures_likely": 0, "harsh": [], "days": {}, "longest": None})
        pair_of = {}
        invoked: Counter = Counter()  # the Rules' articles invoked (poslovnik.cited), one count a speech an article
        # everybody who spoke or heckled in the convocation, for a measure to someone not at that sitting
        everyone_c = {}
        for notes in debates.get(c, {}).values():
            for n, sur in present([x for x in notes["speeches"].values()]).items():
                everyone_c.setdefault(n, sur)
        for url, notes in debates.get(c, {}).items():
            whole = debates_.whole_names(notes["speeches"].values())  # "ОБРАДОВИЋ" alone → the one Obradović of the sitting
            speeches = [{**notes["speeches"][k], "key": k, "text": spoken(notes["speeches"][k]["text"]),
                         "speaker": whole.get(notes["speeches"][k]["speaker"], notes["speeches"][k]["speaker"])}
                        for k in sorted(notes["speeches"])]
            # The speech's own address among the notes' pages (notes_site), when those are published.
            # Only pages known to be in the bucket (data/notes_manifest.json) are linked: no link ahead of its page.
            where = notes_site.layout(c, notes) if notes_url else {}
            if notes_pages is not None:
                where = {k: v for k, v in where.items() if v[0] in notes_pages}
            days = {d["day"]: d for d in notes["days"]}
            title = latin(re.sub(r"^СТЕНОГРАФСКЕ БЕЛЕШКЕ\s*-\s*", "", notes["days"][0]["title"]).split(" - ")[0]) if notes["days"] else ""
            agenda = notes["agenda"] if isinstance(notes["agenda"], dict) else dict(notes["agenda"])
            # surnames of the sitting's speakers: the last word of the name as the notes write it
            surnames = present(speeches)

            def meta(s):
                d = days.get(s["day"], {})
                date = next((x for x in (d.get("date"), d.get("listed_date")) if re.fullmatch(r"\d{4}-\d\d-\d\d", x or "")), "")
                items = [str(i) for i in s.get("items") or []]
                on = None
                if 1 <= len(items) <= 3:  # a debate on one act (or a few): say which; a joint debate on dozens is not "on" any
                    law = law_at.get((url, items[0]))
                    on = {"text": latin(agenda.get(items[0], "")), "law": law, "more": len(items) - 1}
                ours = where.get(s.get("key"))
                return {"date": date, "notes": d.get("url", ""), "sitting": title, "sitting_url": url, "on": on,
                        "ours": f"{notes_url}{ours[0]}#{ours[1]}" if ours else "",
                        "joint": len(items) if len(items) > 3 else 0}
            found = []
            for m in measures(speeches):
                to = to_whom(m, surnames, everyone_c)
                ctx = None if to else by_context(m, surnames)
                found.append({"type": "mera", **m, **meta(m["chair"]), "to": who(to) if to else None, "to_raw": to,
                              "likely": who(ctx[0]) if ctx else None, "likely_raw": ctx[0] if ctx else None,
                              "why": ctx[1] if ctx else "",
                              "around": {**(ar := around(m, to or (ctx[0] if ctx else None))),
                                         "last_who": who(ar["last_who"]) if ar["last_who"] else None,
                                         "asides": [(who(n)["name"], t) for n, t in ar["asides"]]},
                              "before_who": who(m["before"]["speaker"]) if m["before"] else None})
            for run in exchanges(speeches):
                pair = [s for s in run if not s.get("chair")]
                a, b = who(pair[0]["speaker"]), who(pair[1]["speaker"])
                found.append({"type": "razmena", "a": a, "b": b, "n": len(pair), **meta(pair[0]),
                              "speeches": [{"who": who(s["speaker"]) if not s.get("chair") else None, "text": s["text"],
                                            "side": "chair" if s.get("chair") else ("a" if s["speaker"] == pair[0]["speaker"] else "b")}
                                           for s in run]})
                pair_of[id(found[-1])] = pair[:2]
            for s_ in speeches:  # who takes part: speeches, words, points of order, harsh words
                if s_.get("chair"):
                    continue
                t = tally[s_["speaker"]]
                t["speeches"] += 1
                n_words = len(s_["text"].split())
                t["words"] += n_words
                t["points"] += bool(_POINT.search(s_["text"][:300]))
                invoked.update({n for n, _, _ in poslovnik.cited(s_["text"], bool(_POINT.search(s_["text"][:300])))})
                # Where each speech is among the notes' pages, day by day: the MP's page lists them to be read.
                m_ = meta(s_)
                if not t["longest"] or n_words > t["longest"]["words"]:  # the longest speech, for the MP's card
                    t["longest"] = {"words": n_words, "date": m_["date"], "url": m_["ours"] or m_.get("notes", "")}
                if m_["ours"]:
                    d_ = t["days"].setdefault((url, s_["day"]), {"date": m_["date"], "day": s_["day"], "links": [],
                                                                  "sitting": re.sub(r"\s+Narodne skupštine Republike Srbije(?: u \w+ sazivu)?", "", title)})
                    d_["links"].append(m_["ours"])
                for word, sentence in harsh(s_["text"]):
                    t["harsh"].append({"word": word, "text": sentence, "parts": marked(sentence), **meta(s_)})
            for e in found:
                if e["type"] == "razmena":
                    for s_ in {x["speaker"] for x in pair_of[id(e)]}:
                        tally[s_]["exchanges"] += 1
                elif e.get("to_raw"):
                    tally[e["to_raw"]]["measures"] += 1
                elif e.get("likely_raw"):
                    tally[e["likely_raw"]]["measures_likely"] += 1
            events += found
            dates = sorted(e["date"] for e in found if e["date"]) or sorted(
                d.get("listed_date") or "" for d in notes["days"] if d.get("listed_date"))
            sittings.append({"url": url, "title": title, "date": dates[0] if dates else "", "days": len(notes["days"]),
                             "dates": sorted({d["listed_date"] for d in notes["days"] if d.get("listed_date")}),
                             "measures": sum(1 for e in found if e["type"] == "mera"),
                             "exchanges": sum(1 for e in found if e["type"] == "razmena"),
                             "points": sum(1 for s in speeches if not s.get("chair") and _POINT.search(s["text"][:300])),
                             "pauses": sum(1 for s in speeches if s.get("chair") and _PAUSE.search(s["text"]))})
        events.sort(key=lambda e: e["date"], reverse=True)
        sittings.sort(key=lambda x: x["date"], reverse=True)
        for i, e in enumerate(events):
            e["id"], e["conv"] = f"e{c}-{i + 1}", c
            if e["type"] == "razmena":
                for p_ in (e["a"], e["b"]):
                    if p_["slug"]:
                        by_mp[p_["slug"]].append(e)
            if e["on"] and e["on"]["law"]:
                by_law[e["on"]["law"]["key"]].append(e)
        # One row per person (two spellings of one MP are one), and the first TOP by each count.
        rows = {}
        for raw, t in tally.items():
            w = who(raw)
            r = rows.setdefault(w["slug"] or w["name"], {"who": w, "speeches": 0, "words": 0, "points": 0, "exchanges": 0,
                                                         "measures": 0, "measures_likely": 0, "harsh": [], "raw": [], "days": {},
                                                         "longest": None})
            if t["longest"] and (not r["longest"] or t["longest"]["words"] > r["longest"]["words"]):
                r["longest"] = t["longest"]
            for k_, d_ in t["days"].items():  # two spellings of one MP on one day: their speeches together
                if k_ in r["days"]:
                    r["days"][k_]["links"] += d_["links"]
                else:
                    r["days"][k_] = {**d_, "links": list(d_["links"])}
            r["raw"].append(raw)
            for k in ("speeches", "words", "points", "exchanges", "measures", "measures_likely"):
                r[k] += t[k]
            r["harsh"] += t["harsh"]
        # Was the person on any roll call of this convocation? If on none, they spoke here as a member of the
        # Government or as a guest, whatever convocation they sat in as an MP. Said only of the whole convocation:
        # roll calls are too far apart to tell it of a single speech.
        conf = CONVOCATIONS.get(c, {})
        lo, hi = conf.get("from", ""), conf.get("to", "9999")
        for r in rows.values():
            r["outside"] = seated is not None and not any(
                lo <= d.isoformat() < hi for raw in r["raw"] for d in seated.get(debates_.loose(mps.key(raw)), []))
        for r in rows.values():
            r["harsh"].sort(key=lambda h: h["date"], reverse=True)
            r["said"] = list({(h["date"], h["text"]): h for h in r["harsh"]}.values())  # a sentence once, however many words
            r["harsh_words"] = [w for w, _ in Counter(latin(h["word"]) for h in r["harsh"]).most_common(4)]
        # The first of each count are MPs of this convocation only: a minister or a guest speaks under other rules
        # (no time limit of an MP's, no chair's measure), and a name on no roll call may be anyone's, mistyped.
        top = firsts([r for r in rows.values() if r["who"]["slug"] and not r["outside"]])
        for key_, r in rows.items():  # each MP's own counts in this convocation, for the MP's page
            if r["who"]["slug"]:
                place = next((k + 1 for k, x in enumerate(top["harsh"]) if x is r), None)
                per_mp[r["who"]["slug"]].append({"conv": c, "name": ORDINAL_NAME.get(c, c), "exchanges": r["exchanges"],
                                                 "speeches": r["speeches"], "words": r["words"], "outside": r["outside"],
                                                 "longest": r["longest"],
                                                 "points": r["points"], "measures": r["measures"], "harsh": len(r["harsh"]),
                                                 "measures_likely": r["measures_likely"],
                                                 "said": r["said"], "harsh_place": place,
                                                 "spoken": spoken_by_sitting(r["days"].values()),
                                                 "measure_events": [e for e in events if e["type"] == "mera" and (
                                                     (e.get("to") or e.get("likely") or {}).get("slug") == r["who"]["slug"])]})
        if events:
            by_conv.append({"n": c, "name": ORDINAL_NAME.get(c, c), "years": years_of.get(c, ""), "events": events, "invoked": invoked, "table": sittings, "top": top, "speakers": len(rows),
                            "people": sorted(rows.values(), key=lambda r: r["who"]["name"]),
                            "measures": [e for e in events if e["type"] == "mera"],
                            "exchanges": [e for e in events if e["type"] == "razmena"],
                            "sittings": sum(1 for n in debates.get(c, {}).values() if n.get("speeches"))})
    # Two pages per convocation, as the words in full make long pages: the table by sitting with the chair's
    # measures (replike.html for the newest), and the exchanges (razmene.html).
    for i, c in enumerate(by_conv):
        c["page"] = "replike.html" if i == 0 else f"replike-{c['n']}.html"
        c["page_exchanges"] = "razmene.html" if i == 0 else f"razmene-{c['n']}.html"
        c["page_who"] = "ko-najvise.html" if i == 0 else f"ko-najvise-{c['n']}.html"
    chunks = {}
    for c in by_conv:
        # The exchanges, word for word, run to megabytes in a convocation with many notes read: PER_PAGE to a page.
        parts = [c["exchanges"][k:k + PER_PAGE] for k in range(0, len(c["exchanges"]), PER_PAGE)] or [[]]
        names = [c["page_exchanges"] if k == 0 else c["page_exchanges"].replace(".html", f"-s{k + 1}.html")
                 for k in range(len(parts))]
        for chunk, name in zip(parts, names):
            for e in chunk:
                e["page"] = name
        # The chair's measures with the words around them, PER_PAGE to a page too (23 Nov 2026: read again, the
        # Eleventh's 1.3 MB in Cyrillic stopped the publishing).
        held = [c["measures"][k:k + PER_PAGE] for k in range(0, len(c["measures"]), PER_PAGE)] or [[]]
        at = [c["page"] if k == 0 else c["page"].replace(".html", f"-s{k + 1}.html") for k in range(len(held))]
        c["measure_pages"] = list(zip(held, at))
        for chunk, name in c["measure_pages"]:
            for e in chunk:
                e["page"] = name
        chunks[c["n"]] = list(zip(parts, names))
    everyone = together(by_conv) if len(by_conv) > 1 else None  # all of them together: a tab beside the convocations'
    invoked = invoked_articles(everyone["invoked"], by_conv, rules) if everyone else []
    # For the home page: the first of each count in each convocation.
    by_sitting = {x["url"]: {**x, "page": c["page"], "page_exchanges": c["page_exchanges"]}
                  for c in by_conv for x in c["table"]}
    pages = {c["n"]: c["page_who"] for c in by_conv}
    per_mp_ = {slug_: [{**x, "page": pages.get(x["conv"], "")} for x in xs] for slug_, xs in per_mp.items()}
    top = {c["n"]: {k: (v[0] if v else None) for k, v in c["top"].items()} | {"page": c["page_who"]} for c in by_conv}
    # Each convocation's totals, as the table of all convocations gives them (for the page shown while "Ko sada
    # govori" is down): sittings read, speeches, chair's measures, exchanges, harsh words and the commonest of them.
    totals = {c["n"]: {"name": c["name"], "years": c["years"], "page": c["page"], "page_who": c["page_who"],
                       "sittings": c["sittings"], "speeches": sum(r["speeches"] for r in c["people"]),
                       "measures": len(c["measures"]), "exchanges": len(c["exchanges"]),
                       "harsh": sum(len(r["harsh"]) for r in c["people"]),
                       "harsh_word": commonest([h["word"] for r in c["people"] for h in r["harsh"]]),
                       "harsh_top": commonest_k([h["word"] for r in c["people"] for h in r["harsh"]], 3),
                       "harsh_days": Counter(h["date"] for r in c["people"] for h in r["harsh"]
                                             if h.get("date")).most_common(3),
                       "harsh_quote": harsh_quote(c["people"])}
              for c in by_conv}
    return Floor(by_conv=by_conv, chunks=chunks, everyone=everyone, invoked=invoked,
                 terms=rule_terms(terms or [], invoked, rules), by_mp=by_mp, by_law=by_law,
                 by_sitting=by_sitting, per_mp=per_mp_, top=top, totals=totals)


def render(floor: Floor, *, env, common, out: Path) -> None:
    """The pages of "Varnice": per convocation the table with the chair's measures, who leads, the exchanges (a
    page per PER_PAGE), and every convocation together."""
    by_conv = floor.by_conv
    for c in by_conv:
        names = [name for _, name in floor.chunks[c["n"]]]
        (out / c["page_who"]).write_text(env.get_template("floor.html").render(
            **common, c=c, by_conv=by_conv, part="ko", all_page=ALL if len(by_conv) > 1 else "", root=""), encoding="utf-8")
        for k, (chunk, name) in enumerate(c["measure_pages"]):
            (out / name).write_text(env.get_template("floor.html").render(
                **common, c=c, by_conv=by_conv, part="mere", shown=chunk, pages=[n for _, n in c["measure_pages"]], page_now=k,
                all_page=ALL if len(by_conv) > 1 else "", root=""), encoding="utf-8")
        for k, (chunk, name) in enumerate(floor.chunks[c["n"]]):
            (out / name).write_text(env.get_template("floor.html").render(
                **common, c=c, by_conv=by_conv, part="razmene", shown=chunk, pages=names, page_now=k,
                all_page=ALL if len(by_conv) > 1 else "", root=""), encoding="utf-8")
    if floor.everyone:
        (out / ALL).write_text(env.get_template("floor.html").render(
            **common, c=floor.everyone, by_conv=by_conv, part="svi", all_page=ALL, root="",
            invoked=floor.invoked), encoding="utf-8")
    if floor.invoked or floor.terms:  # a page of its own (20 Nov 2026: with the articles' text, varnice-svi grew past 1 MB in Cyrillic)
        (out / RULES).write_text(env.get_template("rules_cited.html").render(**common, invoked=floor.invoked,
                                                                             terms=floor.terms, root=""),
                                 encoding="utf-8")


def harsh_quote(people: list[dict]) -> dict | None:
    """One sentence with the commonest harsh word, for the mikrofon page's quiz ("which word is missing?"), chosen by
    rule so that nobody is picked: the sentence holds that word and no other harsh one, is 40 to 170 characters long,
    and is the latest said (then the shortest, then by the alphabet). Word for word, with who said it and where."""
    entry = lambda w: next((h for h in HARSH if re.match(h, w, re.I)), w)
    words = [h["word"] for r in people for h in r["harsh"]]
    if not words:
        return None
    top = Counter(entry(w) for w in words).most_common(1)[0][0]
    found = [(h.get("date") or "", -len(h["text"]), h["text"], r, h) for r in people for h in r["harsh"]
             if entry(h["word"]) == top and 40 <= len(h["text"]) <= 170 and len(_HARSH.findall(h["text"])) == 1]
    if not found:
        return None
    _, _, text, r, h = max(found, key=lambda x: (x[0], x[1], [-ord(ch) for ch in x[2]]))
    said = _HARSH.search(text).group(0)
    return {"text": latin(text), "word": latin(said), "who": r["who"]["name"], "slug": r["who"].get("slug") or "",
            "date": h.get("date") or "", "url": h.get("ours") or h.get("notes") or ""}


def commonest(words: list[str]) -> tuple[str | None, int]:
    """The harsh word said most often, its forms counted together by their entry in HARSH ("издајници" and
    "издајника" are one), shown in the form said most often; and how many times."""
    top = commonest_k(words, 1)
    return top[0] if top else (None, 0)


def commonest_k(words: list[str], k: int) -> list[tuple[str, int]]:
    """The k harsh words said most often, counted as `commonest` does, most often first."""
    entry = lambda w: next((h for h in HARSH if re.match(h, w, re.I)), w)
    by_entry = Counter(entry(w) for w in words)
    return [(latin(Counter(w for w in words if entry(w) == e).most_common(1)[0][0]), n)
            for e, n in by_entry.most_common(k)]
