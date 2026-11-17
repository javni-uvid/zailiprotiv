"""From the stenographic notes read, by rule and with no model: the measures the chair pronounced (a warning, taking
the floor away, removal from the sitting) and the exchanges of replies between two speakers.

Everything is given word for word (principle 6): the chair's words that pronounce the measure with the speech
before them, and every speech of an exchange. The site doesn't say who was right or what an exchange was "about".
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path

from zailiprotiv import debates as debates_, mps, notes_site
from zailiprotiv.config import CONVOCATIONS
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


# Talk about measures is not a measure: "нећу да изричем опомене, нисмо деца", "шта очекујете - да изричем опомене?",
# "могу да почнем да опомињем, изричем опомене, али …". A denial right before the verb, or reprimands in the plural
# with no number ("две опомене"), is talk.
_DENIED = re.compile(r"(?:\bне|\bнећу да|\bнећемо да|\bне желим да|\bнисам хте\w+ да)(?:\s+(?:вам|му|јој|им|сад|сада|још))*\s+$", re.I)
_NONE = re.compile(r"изричем\s+(?:\w+\s+){0,3}(?:никакв|ниједн)", re.I)  # "… изричем сад никакву опомену"
_PLURAL = re.compile(r"изричем(?! (?:вам |му |јој |им )?(?:две|три|четири|\d))[^.!?]{0,30}\bопомене\b", re.I)


def pronounced(text: str, pattern) -> re.Match | None:
    """The place where a measure is pronounced in the chair's words, or None when the words only talk of measures."""
    for m in pattern.finditer(text):
        if _DENIED.search(text[max(0, m.start() - 40):m.start()]) or _PLURAL.match(text, m.start()) or _NONE.match(text, m.start()):
            continue
        return m
    return None


def measures(speeches: list[dict]) -> list[dict]:
    out = []
    for i, s in enumerate(speeches):
        if not s.get("chair"):
            continue
        found = next(((k, label, m) for k, label, pattern in MEASURES if (m := pronounced(s["text"], pattern))), None)
        if found:
            hit, m = found[:2], found[2]
            before = next((p for p in reversed(speeches[max(0, i - 6):i]) if not p.get("chair")), None)
            out.append({"kind": hit[0], "label": hit[1], "chair": s, "before": before,
                        "adjacent": i > 0 and not speeches[i - 1].get("chair"), "at": m.start(),
                        "sentence": sentence(s["text"], m.start(), m.end()).lstrip(')"“” ')})  # the sentence that pronounces the measure
    return out


_ASIDE = re.compile(r"\(([^():]{3,60}):\s*([^()]{1,400})\)")   # "(Бошко Обрадовић: Не директно.)": words from the floor
_BRACKET = re.compile(r"\s*\([^()]*\)")
_REASON = re.compile(r"^\s*(?:Зато|Због|Јер)\b|\bзато што\b|\bзбог\b", re.I)


def _sentences(text: str) -> list[str]:
    out, last = [], 0
    for m in _END.finditer(text):
        out.append(text[last:m.end()].strip())
        last = m.end()
    return [x for x in out + [text[last:].strip()] if x]


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
    lead = _sentences(_BRACKET.sub("", upto))[-2:]
    while lead and sum(len(x) for x in lead) > 420:
        lead = lead[1:]
    after = _sentences(_BRACKET.sub("", chair[end:]))[:1]
    after = after if after and _REASON.search(after[0]) and len(after[0]) < 420 else []
    surname = to.split()[-1].lower() if to and to.split() else None
    mine = lambda name: surname is None or name.strip().split()[-1].lower() == surname
    before = measure["before"]
    near = (before["text"][-700:] if before and measure["adjacent"] else "") + "\n" + upto
    asides = [(n.strip(), t.strip()) for n, t in _ASIDE.findall(near) if mine(n)][-3:]
    last = []
    if before and measure["adjacent"] and (surname is None or before["speaker"].split()[-1].lower() == surname):
        last = _sentences(_BRACKET.sub("", before["text"][-900:]))[-2:]
        if len(before["text"]) > 900:
            last = last[-2:] if len(_sentences(before["text"][-900:])) > 2 else last[-1:]
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


# Also a name right after the measure itself, as the chair of the Thirteenth said it ("изричем опомену Стефану
# Јовановићу", "изричем вам прву опомену Зеленовићу", "одузимање речи, Драгана Ракић"), or the MP named first
# ("Народни посланик Александар Јовановић, … изричем вам опомену").
_ADDRESSED = re.compile(r"(?i:господине|госпођо|госпођице|колега|колегинице|посланиче|посланице|посланику|посланици|"
                        r"посланик|посланица|опомену|опомене|речи|седнице),?\s+"
                        r"((?:[А-ЯЈЉЊЂЋЏ][а-яјљњђћџ]+[ -]?){1,3})")
_POINT = re.compile(r"повред\w* Пословника|по Пословнику|рекламирам\w* члан|члан\w* \d+\.? ?Пословника", re.I)
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
_END = re.compile(r"[.!?]+(?=[\s\"“”)]*(?:\n|$|\s+[A-ZА-ЯЈЉЊЂЋЏŠĐČĆŽ(„]))|\n")  # not the point in "300.000" or "чл. 106"


def sentence(text: str, start: int, end: int) -> str:
    """The sentence around text[start:end], word for word."""
    before = [m.end() for m in _END.finditer(text, 0, start)]
    after = _END.search(text, end)
    return text[before[-1] if before else 0:after.end() if after else len(text)].strip()
TOP = 25
PER_PAGE = 20


def harsh(text: str) -> list[tuple[str, str]]:
    """(word, its sentence) for each harsh word in a speech."""
    out = []
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


_HECKLE = re.compile(r"\(((?:[А-ЯЈЉЊЂЋЏ][а-яјљњђћџ]+[ -]?){2,4}):")


def by_context(measure: dict) -> tuple[str, str] | None:
    """Whom a measure without a name is most likely for, with the reason, from the notes themselves:
    - the one person whose interjections the notes record in brackets in the chair's words up to the measure;
    - or, with no interjections, the speaker of the speech right before, when the chair pronounces the measure in
      the first two sentences after it.
    Likely, not certain: shown as such, with the reason, and counted apart."""
    chair = measure["chair"]["text"]
    upto = chair[:measure["at"] + len(measure["sentence"])]
    heckles = [n.strip() for n in _HECKLE.findall(upto)]
    if len({mps.key(n) for n in heckles}) == 1:
        return heckles[-1], "u beleškama je zapisano da dobacuje dok predsedavajući govori, neposredno pre mere"
    if not heckles and measure["before"] and measure["adjacent"] and len(_END.findall(chair[:measure["at"]])) <= 1:
        return measure["before"]["speaker"], "mera je izrečena na samom početku obraćanja predsedavajućeg, odmah posle ovog govora"
    return None


def to_whom(measure: dict, speakers: dict[str, str]) -> str | None:
    """The speaker a measure went to, when the chair's own sentence names them: a speaker of the sitting whose
    surname stands in the sentence that pronounces the measure ("Господине Живковићу, … изричем вам опомену",
    "Народном посланику Александру Јовановићу изричем опомену"), or failing that in the sentence before it. When two
    speakers share the surname, the first name must be there too. None when nobody or more than one fits: the page
    then shows the chair's words only."""
    text = measure["chair"]["text"]
    pattern = next(p for k, _, p in MEASURES if k == measure["kind"])
    sentences = re.split(r"(?<=[.!?])\s+", text)
    at = next((i for i, x in enumerate(sentences) if pattern.search(x)), 0)

    def stems(word: str) -> set[str]:  # the word as it may stand in another case: "Живковићу", "Јованове", "Марији"
        w = word.lower()
        return {w, w[:-1], w[:-2]} if len(w) > 4 else {w}
    for sentence in (sentences[at], sentences[at - 1] if at else ""):
        # Only a name the chair addresses ("господине …", "посланику …") counts: another name in the sentence may be
        # the person the speech was about ("зато што сте колеги Филиповићу рекли …").
        fits = []
        for m in _ADDRESSED.finditer(sentence):
            if re.match(r"\s*(?:,|и)\s+[А-ЯЈЉЊЂЋЏ][а-яјљњђћџ]+\s+[А-ЯЈЉЊЂЋЏ]", sentence[m.end():]):
                return None  # several named at once ("опомену Александру Јовановићу, Бориславу Новаковићу, …"): not one
            words = re.findall(r"[А-ЯЈЉЊЂЋЏ][а-яјљњђћџ]+", m.group(1))
            said = set().union(*(stems(w) for w in words)) if words else set()
            named = [name for name, surname in speakers.items() if surname in said]
            if len(named) > 1 or len(words) > 1:  # two with the surname, or a first name said: the first name decides
                named = [n for n in named if n.split()[0].lower()[:4] in {w.lower()[:4] for w in words}]
            fits += named
        if len(set(fits)) == 1:
            return fits[0]
        if fits:
            return None
    return None


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
            "exchanges": [e for c in by_conv for e in c["exchanges"]], "page": ALL, "page_exchanges": ALL, "page_who": ALL,
            "convs": [{"n": c["n"], "name": c["name"], "years": c["years"], "page": c["page"], "page_who": c["page_who"],
                       "page_exchanges": c["page_exchanges"], "sittings": c["sittings"], "speakers": c["speakers"],
                       "measures": len(c["measures"]), "exchanges": len(c["exchanges"]),
                       "harsh": sum(len(r["harsh"]) for r in c["people"]),
                       "first": {k: (v[0] if v else None) for k, v in c["top"].items()}} for c in by_conv]}


ALL = "varnice-svi.html"  # every convocation read, counted together


def render(*, env, common, out: Path, debates: dict, people: dict, convs: list, items_by_conv: dict, photo_of: dict | None = None,
           years_of: dict | None = None, notes_url: str = "", notes_pages: set | None = None,
           seated: dict | None = None) -> tuple[dict, dict]:
    loose = {debates_.loose(k): k for k in people}
    years_of = years_of or {}

    def who(name: str) -> dict:
        key = loose.get(debates_.loose(mps.key(name)))
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
                                     "measures_likely": 0, "harsh": [], "days": {}})
        pair_of = {}
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
            surnames = {s["speaker"]: s["speaker"].split()[-1].lower() for s in speeches if not s.get("chair") and s["speaker"].split()}

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
                to = to_whom(m, surnames)
                ctx = None if to else by_context(m)
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
                t["words"] += len(s_["text"].split())
                t["points"] += bool(_POINT.search(s_["text"][:300]))
                # Where each speech is among the notes' pages, day by day: the MP's page lists them to be read.
                m_ = meta(s_)
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
                                                         "measures": 0, "measures_likely": 0, "harsh": [], "raw": [], "days": {}})
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
                                                 "points": r["points"], "measures": r["measures"], "harsh": len(r["harsh"]),
                                                 "measures_likely": r["measures_likely"],
                                                 "said": r["said"], "harsh_place": place,
                                                 "spoken": spoken_by_sitting(r["days"].values()),
                                                 "measure_events": [e for e in events if e["type"] == "mera" and (
                                                     (e.get("to") or e.get("likely") or {}).get("slug") == r["who"]["slug"])]})
        if events:
            by_conv.append({"n": c, "name": ORDINAL_NAME.get(c, c), "years": years_of.get(c, ""), "events": events, "table": sittings, "top": top, "speakers": len(rows),
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
    for c in by_conv:
        # The exchanges, word for word, run to megabytes in a convocation with many notes read: PER_PAGE to a page.
        chunks = [c["exchanges"][k:k + PER_PAGE] for k in range(0, len(c["exchanges"]), PER_PAGE)] or [[]]
        names = [c["page_exchanges"] if k == 0 else c["page_exchanges"].replace(".html", f"-s{k + 1}.html")
                 for k in range(len(chunks))]
        for chunk, name in zip(chunks, names):
            for e in chunk:
                e["page"] = name
        for e in c["measures"]:
            e["page"] = c["page"]
        for part, name in (("mere", c["page"]), ("ko", c["page_who"])):
            (out / name).write_text(env.get_template("floor.html").render(**common, c=c, by_conv=by_conv, part=part, all_page=ALL if len(by_conv) > 1 else "", root=""),
                                    encoding="utf-8")
        for k, (chunk, name) in enumerate(zip(chunks, names)):
            (out / name).write_text(env.get_template("floor.html").render(
                **common, c=c, by_conv=by_conv, part="razmene", shown=chunk, pages=names, page_now=k,
                all_page=ALL if len(by_conv) > 1 else "", root=""), encoding="utf-8")
    if len(by_conv) > 1:  # all of them together: a tab beside the convocations'
        (out / ALL).write_text(env.get_template("floor.html").render(
            **common, c=together(by_conv), by_conv=by_conv, part="svi", all_page=ALL, root=""), encoding="utf-8")
    # For the home page: the first of each count in each convocation.
    render.by_sitting = {x["url"]: {**x, "page": c["page"], "page_exchanges": c["page_exchanges"]}
                         for c in by_conv for x in c["table"]}
    pages = {c["n"]: c["page_who"] for c in by_conv}
    render.per_mp = {slug_: [{**x, "page": pages.get(x["conv"], "")} for x in xs] for slug_, xs in per_mp.items()}
    render.top = {c["n"]: {k: (v[0] if v else None) for k, v in c["top"].items()} | {"page": c["page_who"]} for c in by_conv}
    # Each convocation's totals, as the table of all convocations gives them (for the page shown while "Ko sada
    # govori" is down): sittings read, speeches, chair's measures, exchanges, harsh words and the commonest of them.
    render.totals = {c["n"]: {"name": c["name"], "years": c["years"], "page": c["page"], "page_who": c["page_who"],
                              "sittings": c["sittings"], "speeches": sum(r["speeches"] for r in c["people"]),
                              "measures": len(c["measures"]), "exchanges": len(c["exchanges"]),
                              "harsh": sum(len(r["harsh"]) for r in c["people"]),
                              "harsh_word": commonest([h["word"] for r in c["people"] for h in r["harsh"]])}
                     for c in by_conv}
    return by_mp, by_law


def commonest(words: list[str]) -> tuple[str | None, int]:
    """The harsh word said most often, its forms counted together by their entry in HARSH ("издајници" and
    "издајника" are one), shown in the form said most often; and how many times."""
    entry = lambda w: next((h for h in HARSH if re.match(h, w, re.I)), w)
    by_entry = Counter(entry(w) for w in words)
    if not by_entry:
        return None, 0
    top, n = by_entry.most_common(1)[0]
    return latin(Counter(w for w in words if entry(w) == top).most_common(1)[0][0]), n
