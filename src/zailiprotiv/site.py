"""The static site: the convocation's laws, each with its final roll call by group and by MP, and every MP's votes.

Pages are written in Latin script: names and titles from the Assembly's Cyrillic documents are transliterated.
Nothing on the pages comes from another server: no scripts, fonts or analytics (AGENTS.md, principle 5).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import urllib.parse
import shutil
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from zailiprotiv import kinds, mps
from zailiprotiv.translit import latin

HERE = Path(__file__).parent
VOTES = ("za", "protiv", "uzdrzan", "nije_glasao", "nije_prisutan")
VOTE_LABEL = {"za": "Za", "protiv": "Protiv", "uzdrzan": "Uzdržan", "nije_glasao": "Nije glasao",
              "nije_prisutan": "Nije prisutan", None: "Nije na spisku"}
MONTHS = ("januar", "februar", "mart", "april", "maj", "jun", "jul", "avgust", "septembar", "oktobar", "novembar",
          "decembar")


def slug(text: str, limit: int = 80) -> str:
    t = unicodedata.normalize("NFKD", latin(text).lower().replace("đ", "dj"))
    t = "".join(c for c in t if not unicodedata.combining(c))
    words, out = re.findall(r"[a-z0-9]+", t), ""
    for w in words:
        if len(out) + len(w) + 1 > limit:
            break
        out = f"{out}-{w}" if out else w
    return out or "x"


def day(iso: str | None) -> str:
    if not iso:
        return ""
    y, m, d = iso[:10].split("-")
    return f"{int(d)}. {MONTHS[int(m) - 1]} {y}."


MONTHS_OF = ("januara", "februara", "marta", "aprila", "maja", "juna", "jula", "avgusta", "septembra", "oktobra",
             "novembra", "decembra")


def day_of(iso: str | None) -> str:
    """"2025-11-04" → "4. novembra 2025": the date after "od", "do", without the final dot."""
    if not iso:
        return ""
    y, m, d = iso[:10].split("-")
    return f"{int(d)}. {MONTHS_OF[int(m) - 1]} {y}"


def title_case(name: str) -> str:
    """"АТЛАГИЋ проф. др МАРКО" → "Atlagić prof. dr Marko": capitals only where the PDF writes them."""
    def cap(w: str) -> str:
        return "-".join(p.capitalize() for p in w.split("-")) if w.isupper() else w
    return " ".join(cap(w) for w in latin(name).split())


# Serbian Latin alphabetical order: a b c č ć d dž đ e f g h i j k l lj m n nj o p r s š t u v z ž.
_ORDER = "a b c č ć d dž đ e f g h i j k l lj m n nj o p q r s š t u v w x y z ž".split()
_RANK = {letter: i for i, letter in enumerate(_ORDER)}


def collate(text: str) -> list[int]:
    """A sort key in Serbian alphabetical order (Latin), digraphs dž, lj, nj counted as one letter."""
    t, out, i = latin(text).lower(), [], 0
    while i < len(t):
        two = t[i:i + 2]
        if two in _RANK:
            out.append(_RANK[two] + 1); i += 2
        elif t[i] in _RANK:
            out.append(_RANK[t[i]] + 1); i += 1
        else:
            out.append(0 if t[i] == " " else 100 + ord(t[i])); i += 1
    return out


@dataclass
class MP:
    key: str
    name: str
    slug: str = ""
    group: str = ""
    last_seen: str = ""
    votes: dict[str, str] = field(default_factory=dict)  # vote key → za, protiv, …


def load(data: Path) -> tuple[dict, dict, dict]:
    laws = json.loads((data / "laws.json").read_text(encoding="utf-8"))
    votes = {}
    for path in sorted((data / "votes").glob("*.json")):
        store = json.loads(path.read_text(encoding="utf-8"))
        for key, v in store["votes"].items():
            votes[key] = {**v, "sitting": store["sitting"], "sitting_title": store["title"], "key": key}
    bills = {}
    for path in sorted((data / "bills").glob("*.json")) if (data / "bills").exists() else []:
        bills[path.name] = json.loads(path.read_text(encoding="utf-8"))
    for path in sorted((data / "summaries").glob("*.json")) if (data / "summaries").exists() else []:
        bills.setdefault(path.name, {})["summary"] = json.loads(path.read_text(encoding="utf-8"))
    for path in sorted((data / "notes").glob("*.json")) if (data / "notes").exists() else []:
        bills.setdefault(path.name, {})["notes"] = json.loads(path.read_text(encoding="utf-8"))
    for path in sorted((data / "debates").glob("*.json")) if (data / "debates").exists() else []:
        record = json.loads(path.read_text(encoding="utf-8"))
        d = record["debate"]
        if d["predlagac"] or d["podrska"] or d["zamerke"]:  # an empty one: the debate passed the law by
            bills.setdefault(path.name, {})["debate"] = record
    # Short names for lists (data/<N>/short_titles.json, {the law's key in laws.json: short name}); the law keeps
    # its official title, shown on its page.
    short = data / "short_titles.json"
    names = json.loads(short.read_text(encoding="utf-8")) if short.exists() else {}
    for key, law in laws["laws"].items():
        law["short"] = names.get(key) or law["title"]
    # Bills whose PDF on the Assembly's site holds another act's memorandum: none of it is shown for this law.
    wrong = data / "wrong_bills.json"
    for name, why in (json.loads(wrong.read_text(encoding="utf-8")) if wrong.exists() else {}).items():
        b = bills.setdefault(name, {})
        b.pop("summary", None)
        b["sections"] = {k: v for k, v in b.get("sections", {}).items() if k == "basis"}
        b["wrong"] = why
    return laws, votes, bills


def load_transcripts(data: Path) -> dict[str, dict]:
    """The stenographic notes read, by the address of their sitting's page."""
    folder = data / "transcripts"
    out = {}
    for path in sorted(folder.glob("*.json")) if folder.exists() else []:
        store = json.loads(path.read_text(encoding="utf-8"))
        out[store["sitting"]] = store
    return out


def debate_of(law: dict, final: dict | None, notes: dict | None) -> dict | None:
    """The course of the law's debate from the notes of its sitting: its agenda item, the days it was debated, the
    items debated with it in principle, and the amendments debated."""
    from zailiprotiv import link
    if not final or not notes:
        return None
    name = re.sub(r" (u )?(celini|nacelu|pojedinostima)$", "", link.act_name(final.get("item") or law["title"]))
    # An agenda item may bundle other acts after the bill ("… за 2023. годину, са Предлогом одлуке о …").
    scored = [(1.0 if link.act_name(t) == name or link.act_name(t).startswith(name + " ") else
               link.closeness(link.act_name(t), name), int(n)) for n, t in notes["agenda"].items()]
    score, item = max(scored, default=(0.0, None))
    if item is None or score < 0.6:
        return None
    general = [s for s in notes["speeches"].values() if not s["chair"] and s["part"] == "general" and item in s["items"]]
    detail = [s for s in notes["speeches"].values() if not s["chair"] and s["part"] == "detail" and s["items"] == [item]]
    used = sorted({s["day"] for s in general + detail})
    days = [d for i, d in enumerate(notes["days"], 1) if i in used]
    dates = [d["listed_date"] for d in days if d.get("listed_date")]
    joint = sorted({i for s in general for i in s["items"]} - {item})
    return {"item": item, "joint": joint, "days": days, "all_days": notes["days"], "first": min(dates, default=""),
            "last": max(dates, default=""), "n_days": len(used), "general": len(general), "detail": len(detail),
            "amendments": sum(1 for a in notes["amendments"] if a["item"] == item),
            "provisional": any(d.get("provisional") for d in notes["days"])}


def quotes_with_votes(said: dict | None, final: dict | None) -> list[dict]:
    """The debate's quotes, each with how its speaker voted on the law ("za", "protiv", …; "vlada" for the
    Government; None if not on the roll call), for the reader to see which side a quote comes from."""
    if not said:
        return []
    from zailiprotiv import debates
    rows = {debates.loose(mps.key(r[1])): r[2] for r in (final or {}).get("rows", [])}
    known = {k: k for k in rows}
    out = []
    for q in said.get("debate", {}).get("citati", []):
        if q.get("grupa") == debates.GOVERNMENT:
            side = "vlada"
        else:
            k = debates.resolve(q["govornik"], known)
            side = rows.get(k) if k else None
        out.append({**q, "side": side})
    return out


def pair(quotes: list[dict]) -> list[dict]:
    """Two quotes to show first: one from those for the law (the Government first), one from those against."""
    for_ = [q for q in quotes if q["side"] == "vlada"] + [q for q in quotes if q["side"] == "za"]
    against = [q for q in quotes if q["side"] == "protiv"]
    return ([for_[0]] if for_ else []) + ([against[0]] if against else [])


def registry(votes: dict) -> dict[str, MP]:
    """Every MP met in a roll call, under one key whatever the layout wrote. The name shown is the report
    layout's ("SURNAME Given", one order for everyone) where the MP is in one, else the listinzi's."""
    out: dict[str, MP] = {}
    surname_first = set()
    for v in sorted(votes.values(), key=lambda v: v["when"]):
        report = v["counts"]["nije_prisutan"] > 0
        for _, name, vote, group in v["rows"]:
            k = mps.key(name)
            mp = out.setdefault(k, MP(k, title_case(name)))
            if report and not name.split()[0].istitle():
                mp.name = title_case(name)
                surname_first.add(k)
            mp.votes[v["key"]] = vote
            mp.group, mp.last_seen = latin(group), v["when"]
    # The older lists write "Given Surname": shown surname first too, so every list sorts one way.
    for k, mp in out.items():
        titles = mps.TITLES | {latin(t) for t in mps.TITLES}
        words = [w for w in mp.name.split() if w.lower().strip(".") not in titles] or mp.name.split()
        if k not in surname_first and len(words) > 1:
            words = words[1:] + words[:1]
        mp.name = " ".join(words)  # without titles (dr, prof.): they are not part of the name
    taken = Counter()
    for mp in sorted(out.values(), key=lambda m: collate(m.name)):
        base = slug(mp.name, 60)
        taken[base] += 1
        mp.slug = base if taken[base] == 1 else f"{base}-{taken[base]}"
    return out


def by_group(vote: dict) -> list[dict]:
    """A vote's counts per group, groups with most MPs listed first, then by name: a neutral order."""
    table: dict[str, Counter] = defaultdict(Counter)
    for _, _, how, group in vote["rows"]:
        table[latin(group) or "Bez poslaničke grupe"][how] += 1
    rows = [{"group": g, "total": sum(c.values()), **{k: c.get(k, 0) for k in VOTES}} for g, c in table.items()]
    return sorted(rows, key=lambda r: (-r["total"], collate(r["group"])))


def excerpt(text: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut + " …"


def days_between(a: str | None, b: str | None) -> int | None:
    if not a or not b:
        return None
    return (dt.date.fromisoformat(b[:10]) - dt.date.fromisoformat(a[:10])).days


def against_share(counts: dict) -> float:
    """The share of votes against among the votes for and against: 0 when nobody voted against."""
    cast = counts["za"] + counts["protiv"]
    return counts["protiv"] / cast if cast else 0.0


def against_by_group(vote: dict) -> list[tuple[str, int]]:
    """Groups with MPs voting against, most first, then by name."""
    c = Counter(latin(g) or "Bez poslaničke grupe" for _, _, how, g in vote["rows"] if how == "protiv")
    return sorted(c.items(), key=lambda kv: (-kv[1], collate(kv[0])))


def spotlight(all_items: list[dict], current: list[dict], skip: str | None, n: int = 6) -> list[dict]:
    """Votes picked out on the home page, by a rule rather than by hand: laws the public knows by another name
    (one per name, newest first), then the most divided laws of the current convocation."""
    out, names, keys = [], set(), {skip}
    named = sorted((it for it in all_items if it["aka"] and it["final"]), key=lambda it: it["law"].get("passed") or "",
                   reverse=True)
    for it in named:
        if it["aka"][0] in names or it["key"] in keys:
            continue
        names.add(it["aka"][0]); keys.add(it["key"])
        out.append({**it, "why": "naziv iz javnosti", "share": against_share(it["final"]["counts"])})
    out = out[:n - 2] if len(out) > n - 2 else out
    for it in most_against(current, n * 2):
        if len(out) >= n:
            break
        if it["key"] not in keys and not (it["aka"] and it["aka"][0] in names):
            keys.add(it["key"])
            out.append({**it, "why": "podelio Skupštinu"})
    return sorted(out, key=lambda it: it["law"].get("passed") or "", reverse=True)


def most_against(items: list[dict], n: int) -> list[dict]:
    """The laws whose final vote had the largest share against, the same rule for every law; ties go to more
    votes against, then the newer law."""
    voted = [it for it in items if it["final"] and it["final"]["counts"]["protiv"]]
    ranked = sorted(voted, key=lambda it: (against_share(it["final"]["counts"]), it["final"]["counts"]["protiv"],
                                           it["law"].get("passed") or ""), reverse=True)
    return [{**it, "share": against_share(it["final"]["counts"]), "against": against_by_group(it["final"])}
            for it in ranked[:n]]


def hemicycle(counts: dict, rows=((60, 17), (75, 21), (90, 25), (105, 29), (120, 33), (135, 37), (150, 42), (165, 46))) -> list[tuple]:
    """The chamber's 250 seats as (x, y, vote) in a half circle, filled from the left: for, then those who did not
    vote, abstained or were absent, then against. A picture of the count, not of where anyone sits."""
    import math
    seats = sorted(((math.pi - math.pi * i / (n - 1), r) for r, n in rows for i in range(n)), reverse=True)
    za, protiv = counts.get("za") or 0, counts.get("protiv") or 0
    total = len(seats)
    out = []
    for i, (t, r) in enumerate(seats):
        kind = "za" if i < za else ("protiv" if i >= total - protiv else "ostali")
        out.append((round(170 + r * math.cos(t), 1), round(172 - r * math.sin(t), 1), kind))
    return out


ORDINAL_NAME = {"9": "Deveti", "10": "Deseti", "11": "Jedanaesti", "12": "Dvanaesti", "13": "Trinaesti", "14": "Četrnaesti", "15": "Petnaesti"}


def convocations(root: Path) -> list[tuple[str, Path]]:
    """The convocations with data, newest first: data/<N>/laws.json (or a single folder with laws.json in it)."""
    from zailiprotiv.config import CURRENT
    if (root / "laws.json").exists():
        return [(CURRENT, root)]
    found = [(p.name, p) for p in root.iterdir() if p.is_dir() and (p / "laws.json").exists()]
    return sorted(found, key=lambda c: int(c[0]) if c[0].isdigit() else 0, reverse=True)


def laws_page(conv: str, current: str) -> str:
    return "zakoni.html" if conv == current else f"zakoni-{conv}.html"


def mps_page(conv: str, current: str) -> str:
    return "poslanici.html" if conv == current else f"poslanici-{conv}.html"


def sitting_page(url: str, title: str) -> str:
    """A sitting's page name: its title and the number the Assembly's site gives it."""
    m = re.search(r"\.(\d+)\.\d+\.html$", urllib.parse.unquote(url or ""))
    return slug(latin(title))[:70] + ("-" + m.group(1) if m else "")


def leaning(za: int, protiv: int) -> str:
    """A vote record in words, as TheyWorkForYou puts it: from "dosledno za" to "dosledno protiv"; five votes or more."""
    n = za + protiv
    if n < 5:
        return ""
    share = za / n
    for at, word in ((0.95, "dosledno za"), (0.75, "uglavnom za"), (0.6, "češće za"), (0.4, "mešovito"),
                     (0.25, "češće protiv"), (0.05, "uglavnom protiv")):
        if share >= at:
            return word
    return "dosledno protiv"


def write_feed(path: Path, title: str, self_url: str, page_url: str, entries: list[dict]) -> None:
    from xml.sax.saxutils import escape as x
    updated = max((e["updated"] for e in entries), default="2000-01-01T00:00:00Z")
    body = "".join(f"<entry><title>{x(e['title'])}</title><link href=\"{x(e['link'])}\"/><id>{x(e['id'])}</id>"
                   f"<updated>{e['updated']}</updated><summary>{x(e['summary'])}</summary></entry>\n" for e in entries)
    path.write_text('<?xml version="1.0" encoding="utf-8"?>\n<feed xmlns="http://www.w3.org/2005/Atom">\n'
                    f"<title>{x(title)}</title><link rel=\"self\" href=\"{x(self_url)}\"/><link href=\"{x(page_url)}\"/>"
                    f"<id>{x(page_url or self_url)}</id><updated>{updated}</updated>\n{body}</feed>\n", encoding="utf-8")


def build(root: Path, out: Path, domain: str | None = None, clean: bool = False, cyrillic: bool = False) -> dict:
    convs = convocations(root)
    current = convs[0][0]
    mps.load_aliases(root / "mp_aliases.json")
    loaded = {c: load(path) for c, path in convs}
    debates = {c: load_transcripts(path) for c, path in convs}
    all_votes = {k: v for _, votes, _ in loaded.values() for k, v in votes.items()}
    people = registry(all_votes)
    env = Environment(loader=FileSystemLoader(HERE / "templates"), autoescape=select_autoescape(["html"]),
                      trim_blocks=True, lstrip_blocks=True)
    area_slug = lambda a: slug(latin(a))[:80]
    env.globals.update(hemicycle=hemicycle)
    env.filters.update(latin=latin, day=day, day_of=day_of, vote_label=lambda v: VOTE_LABEL.get(v, v), area_slug=area_slug)
    if out.exists():
        shutil.rmtree(out)
    (out / "zakon").mkdir(parents=True)
    (out / "poslanik").mkdir()
    for name in ("style.css", "site.js", "favicon.svg", "pretraga.js"):
        shutil.copy(HERE / "static" / name, out / name)
    shutil.copytree(HERE / "static" / "fonts", out / "fonts")
    # The stylesheet's and script's address changes with their content, so a browser or cache never pairs new pages
    # with old styles.
    css_version = hashlib.sha256((HERE / "static" / "style.css").read_bytes()
                                 + (HERE / "static" / "site.js").read_bytes()).hexdigest()[:10]
    built = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    from zailiprotiv.config import CONVOCATIONS

    def years(c: str) -> str:
        passed = sorted(l.get("passed") or "" for l in loaded[c][0]["laws"].values())
        conf = CONVOCATIONS.get(c, {})
        first = (conf.get("from") or (passed[0] if passed else ""))[:4]
        last = (conf.get("to") or (passed[-1] if passed else ""))[:4]
        return f"{first}–{last}" if first and last and first != last else first or last

    conv_list = [{"n": c, "name": ORDINAL_NAME.get(c, c + "."), "page": laws_page(c, current),
                  "mps_page": mps_page(c, current), "years": years(c), "saziv_page": f"saziv-{c}.html",
                  "laws": len(loaded[c][0]["laws"])} for c, _ in convs]
    settings_file = root / "settings.json"
    settings = json.loads(settings_file.read_text(encoding="utf-8")) if settings_file.exists() else {}
    common = {"analytics": settings.get("analytics_token", ""), "css": css_version, "built": built, "fetched": loaded[current][0].get("fetched", "")[:10], "vote_label": VOTE_LABEL,
              "VOTES": VOTES, "convs": conv_list, "current": current, "site_url": f"https://{domain}/" if domain else "", "cyrillic": cyrillic}

    # Laws, newest first within each convocation, the current one first so its addresses never change.
    # Names the public and the media use for a law, for search (data/aliases.json, each checked in the press).
    aliases = json.loads((root / "aliases.json").read_text(encoding="utf-8")) if (root / "aliases.json").exists() else {}
    items_by_conv, taken = {}, Counter()
    law_pages = []  # written once the groups' pages are known, so a law's table can link to them
    for conv, _ in convs:
        laws_store, votes, bills = loaded[conv]
        items = []
        for key, law in sorted(laws_store["laws"].items(), key=lambda kv: (kv[1].get("passed") or "", kv[1]["title"]),
                               reverse=True):
            s = slug(law["title"])
            taken[s] += 1
            s = s if taken[s] == 1 else f"{s}-{taken[s]}"
            bill = bills.get(law.get("bill_file", ""), {})
            items.append({"key": key, "slug": s, "law": law, "final": votes.get(law.get("final_vote") or ""),
                          "aka": aliases.get(key, {}).get("names", []), "aka_source": aliases.get(key, {}).get("source", ""),
                          "summary": bill.get("summary"), "notes": bill.get("notes"),
                          "said": bill.get("debate"), "wrong_bill": bill.get("wrong"), "conv": conv,
                          "conv_name": ORDINAL_NAME.get(conv, conv), "conv_page": laws_page(conv, current),
                          "kind": kinds.KINDS.get(law.get("kind", "other"), ""),
                          "areas": [kinds.AREAS[a] for a in law.get("areas", [])],
                          "urgent": "urgency" in bill.get("sections", {}),
                          "days": days_between(law.get("submitted"), law.get("passed")),
                          "debate": debate_of(law, votes.get(law.get("final_vote") or ""),
                                              debates[conv].get((votes.get(law.get("final_vote") or "") or {})
                                                                .get("sitting", "")))})
        for it in items:
            it["quotes"] = quotes_with_votes(it["said"], it["final"])
            it["pair"] = pair(it["quotes"])
            it["against"] = against_by_group(it["final"]) if it["final"] else []
            sm = (it["summary"] or {}).get("summary") or {}
            it["gist"] = sm.get("ukratko", "")
        by_key = {it["key"]: it for it in items}
        ranked = most_against(items, len(items))
        for i, r in enumerate(ranked, 1):
            by_key[r["key"]].update(rank=i, share=r["share"], conv_total=len(ranked))
        items_by_conv[conv] = items
        for it in items:
            law, final = it["law"], it["final"]
            sections = bills.get(law.get("bill_file", ""), {}).get("sections", {})
            others = [votes[k] for k in law.get("votes", []) if k != law.get("final_vote") and k in votes]
            roll = []
            if final:
                listed = {mps.key(r[1]): r for r in final["rows"]}
                roll = sorted(({"mp": people[k], "vote": r[2], "group": latin(r[3])} for k, r in listed.items()),
                              key=lambda x: collate(x["mp"].name))
            law_pages.append(dict(
                it=it, law=law, final=final,
                sitting_slug=sitting_page(final["sitting"], final["sitting_title"]) if final else "", groups=by_group(final) if final else [], roll=roll,
                others=others, reasons=excerpt(sections.get("reasons", ""), 1200),
                funds=excerpt(sections.get("funds", ""), 500), effects=excerpt(sections.get("effects", ""), 600),
                report=bool(final and final["counts"]["nije_prisutan"]), root="../"))
        by_kind = defaultdict(list)
        for it in items:
            by_kind[it["law"].get("kind", "other")].append(it)
        kind_order = [k for k in kinds.KINDS if k in by_kind]
        (out / laws_page(conv, current)).write_text(env.get_template("laws.html").render(
            **common, items=items, kind_counts=[(k, kinds.KINDS[k], len(by_kind[k])) for k in kind_order],
            urgent=sum(1 for it in items if it["urgent"]), total=len(items), conv=conv,
            area_options=sorted({a for it in items for a in it.get("areas") or []}, key=lambda a: collate(latin(a))),
            year_options=sorted({(it["law"].get("passed") or "")[:4] for it in items if it["law"].get("passed")}, reverse=True),
            conv_name=ORDINAL_NAME.get(conv, conv), root=""), encoding="utf-8")

    by_key_all = {it["key"]: it for its in items_by_conv.values() for it in its}
    # One group under two names. The Assembly's listings changed how they write groups, and groups rename: within a
    # convocation, a name that stops being used is the same group as a later name when two thirds or more of its
    # MPs are next listed under that name and make up half or more of it. The newest name is shown.
    listed: dict[tuple, dict] = defaultdict(lambda: {"mps": set(), "first": "9999", "last": ""})
    for it in by_key_all.values():
        if it["final"]:
            for _, name, _, group in it["final"]["rows"]:
                g = listed[(it["conv"], (latin(group) or "Bez poslaničke grupe").strip("() "))]
                g["mps"].add(mps.key(name))
                g["first"], g["last"] = min(g["first"], it["final"]["when"]), max(g["last"], it["final"]["when"])
    renamed: dict[tuple, str] = {}
    for (c, a), A in listed.items():
        later = [(B["first"], b) for (c2, b), B in listed.items()
                 if c2 == c and b != a and A["last"] < B["first"] and b not in ("Bez poslaničke grupe", "-")
                 and b.lower() != "samostalni" and len(A["mps"]) >= 3
                 and len(A["mps"] & B["mps"]) * 3 >= len(A["mps"]) * 2 and len(A["mps"] & B["mps"]) * 2 >= len(B["mps"])]
        if later and a not in ("Bez poslaničke grupe", "-") and a.lower() != "samostalni":
            renamed[(c, a)] = min(later)[1]
    former: dict[tuple, list] = defaultdict(list)
    group_now: dict[tuple, str] = {}

    def group_of(c: str, group: str) -> str:
        g = first = (latin(group) or "Bez poslaničke grupe").strip("() ")  # "(NADA …)" and "NADA …" are one group
        for _ in range(5):
            if (c, g) not in renamed:
                break
            g = renamed[(c, g)]
        if g != first and first not in former[(c, g)]:
            former[(c, g)].append(first)
        group_now[(c, first)] = g
        return g

    # MPs: their final votes on laws, in every convocation.
    finals = {it["law"]["final_vote"]: it for items in items_by_conv.values() for it in items
              if it["law"].get("final_vote")}
    # In each final vote: every MP's group, and how most of each group voted (three or more voting, a clear majority).
    seat, line = {}, {}
    for key, it in finals.items():
        cast: dict[str, Counter] = defaultdict(Counter)
        for _, name, how, group in it["final"]["rows"]:
            g = group_of(it["conv"], group)
            seat[(key, mps.key(name))] = g
            if how in ("za", "protiv", "uzdrzan"):
                cast[g][how] += 1
        for g, c in cast.items():
            (top, n), total = c.most_common(1)[0], sum(c.values())
            if total >= 3 and n > total / 2 and g != "Bez poslaničke grupe" and g.lower() != "samostalni":
                line[(key, g)] = top
    groups_in: dict[str, list] = defaultdict(list)
    for (key, g) in line:
        groups_in[key].append(g)
    # What each MP is quoted saying in the debates summarised (the laws with most votes against).
    from zailiprotiv import debates as debates_
    loose_keys = {debates_.loose(k): k for k in people}
    said_by: dict[str, list] = defaultdict(list)
    for its in items_by_conv.values():
        for it in its:
            for q in it["quotes"]:
                k = loose_keys.get(debates_.loose(mps.key(q["govornik"])))
                if k and q.get("grupa") != debates_.GOVERNMENT:
                    days_ = (it["debate"] or {}).get("all_days") or []
                    said_by[k].append({"it": it, "q": q, "day": days_[q["dan"] - 1] if 0 < q["dan"] <= len(days_) else None})
    # What an MP most often says in the debates read (an AI model's overview, each point with a verbatim quote).
    profiles = {}
    for f in sorted((root / "profiles").glob("*.json")):
        p = json.loads(f.read_text(encoding="utf-8"))
        if (k := loose_keys.get(debates_.loose(p["mp"]))):
            spans = {c for t in p["points"] for c in t.get("sazivi", [])}
            for t in p["points"]:  # when the points come from several convocations, each says which
                t["when"] = ", ".join(years(c) for c in t.get("sazivi", [])) if len(spans) > 1 else ""
            profiles[k] = p
    feeds_mp: dict[str, tuple] = {}
    # Presence at final votes, only where the Assembly lists the absent (the report layout), by convocation;
    # with the median of all MPs listed in twenty such votes or more, to compare with.
    presence: dict[tuple, tuple] = {}
    for mp in people.values():
        seen = Counter()
        for k, how in mp.votes.items():
            f = finals.get(k)
            if f and f["final"]["counts"]["nije_prisutan"]:
                seen[(f["conv"], "listed")] += 1
                seen[(f["conv"], "present")] += how != "nije_prisutan"
        for c in {c for c, _ in seen}:
            presence[(mp.key, c)] = (seen[(c, "present")], seen[(c, "listed")])
    median_presence = {}
    for c in {c for _, c in presence}:
        shares = sorted(p / n for (k, cc), (p, n) in presence.items() if cc == c and n >= 20)
        if shares:
            median_presence[c] = shares[len(shares) // 2]
    spoke, words = Counter(), {}
    from zailiprotiv import profiles as profiles_
    spoken = profiles_.speeches(root)
    distinct = profiles_.distinctive(spoken)
    for key, own in spoken.items():
        if (k := loose_keys.get(key)):
            spoke[k] = len(own)
            if distinct.get(key):
                words[k] = distinct[key]
    # Groups with a page: those with a line (most of three or more voting) in five final votes or more of a convocation.
    lines_of: dict[tuple, list] = defaultdict(list)
    for (key, g), how in line.items():
        lines_of[(finals[key]["conv"], g)].append((key, how))
    group_slug = {(c, g): f"{c}-{slug(g, 60)}" for (c, g), ls in lines_of.items() if len(ls) >= 5 and slug(g)}
    # Replies and the chair's measures, from the notes read; an MP's exchanges go on the MP's page, a law's on its page.
    # Portraits from the Assembly's list of MPs (data/photos/, the `photos` command), by the MP's key.
    photos_index = root / "photos" / "index.json"
    photo_of = {}
    if photos_index.exists():
        shutil.copytree(root / "photos", out / "foto", ignore=shutil.ignore_patterns("*.json"))
        photo_of = {k: v["file"] for k, v in json.loads(photos_index.read_text(encoding="utf-8")).items()}
        # The Assembly's list sometimes gives a name more fully than the roll calls (a second surname, an initial):
        # a portrait whose name holds all the words of exactly one MP's name, or the other way round, is that MP's.
        words = {k: {w for w in k.split() if len(w) > 1} for k in photo_of}
        for key_ in people:
            if key_ not in photo_of:
                mine = set(key_.split())
                close = [k for k, w in words.items() if k not in people and len(mine & w) >= 2 and (mine <= w or w <= mine)]
                if len(close) == 1:
                    photo_of[key_] = photo_of[close[0]]
    from zailiprotiv import pages_floor
    exchanges_of, floor_of = pages_floor.render(photo_of=photo_of, env=env, common=common, out=out, debates=debates, people=people,
                                                convs=convs, items_by_conv=items_by_conv)
    from zailiprotiv import card
    import os
    cache = Path(os.environ.get("ZAILIPROTIV_CACHE", ".cache")) / "og"
    cache.mkdir(parents=True, exist_ok=True)
    def picture(path: Path, *args_) -> None:
        """A share picture, drawn once for what it shows and copied from the cache after that."""
        kept = cache / (hashlib.sha256(repr((card.VERSION, args_)).encode()).hexdigest()[:24] + ".png")
        if not kept.exists():
            card.draw(kept, *args_)
        shutil.copy(kept, path)
    picture(out / "za-ili-protiv.png", "Kako glasaju poslanici Narodne skupštine Srbije", "Zakoni, glasanja, rasprave", None, "")
    for args in law_pages:
        it = args["it"]
        if it["final"]:  # the picture shown when the page is shared
            name = it["aka"][0][:1].upper() + it["aka"][0][1:] if it["aka"] else it["law"]["short"]
            picture(out / "zakon" / f"{it['slug']}.png", name, day(it["law"].get("passed")), it["final"]["counts"],
                    "hitan postupak" if it["urgent"] else "", tuple(hemicycle(it["final"]["counts"])))
        (out / "zakon" / f"{args['it']['slug']}.html").write_text(
            env.get_template("law.html").render(**common, **args, group_slug=group_slug, group_now=group_now,
                                                floor=floor_of.get(it["key"], [])), encoding="utf-8")
    # Key votes, by a rule: in each convocation the laws the public knows by another name (one per name) and the
    # four with the largest share of votes against. Shown on MP pages, group pages and in "Glasaj i ti".
    key_votes: dict[str, list] = {}
    for c, its in items_by_conv.items():
        chosen, names = [], set()
        for it in its:
            if it["aka"] and it["final"] and it["aka"][0] not in names:
                names.add(it["aka"][0])
                chosen.append(it)
        divided = [by_key_all[r["key"]] for r in most_against(its, len(its))
                   if not (r["aka"] and r["aka"][0] in names) and r["law"].get("kind") != "treaty"][:4]
        key_votes[c] = sorted(chosen + divided, key=lambda it: it["final"]["when"], reverse=True)
    key_finals = {it["law"]["final_vote"]: it for its in key_votes.values() for it in its}
    # Speeches by day, for the MP page's timeline.
    spoke_days: dict[str, Counter] = {}
    speech_url: dict[tuple, str] = {}
    for key, own in spoken.items():
        if (k := loose_keys.get(key)):
            spoke_days[k] = Counter(sp["date"] for sp in own if sp["date"])
            for sp in own:
                speech_url[(k, sp["date"])] = sp["url"]
    rows_mp = []
    for mp in sorted(people.values(), key=lambda m: collate(m.name)):
        record = []
        for k, how in mp.votes.items():
            if k in finals:
                g = seat.get((k, mp.key), "")
                own = line.get((k, g))
                record.append({"it": finals[k], "vote": how, "group": g, "line": own,
                               "differs": bool(own and how in ("za", "protiv", "uzdrzan") and how != own)})
        record.sort(key=lambda r: r["it"]["final"]["when"], reverse=True)
        feeds_mp[mp.slug] = (mp.name, record[:40])
        tally = Counter(r["vote"] for r in record)
        by_conv = []
        for c in sorted({r["it"]["conv"] for r in record}, key=int, reverse=True):
            rs = [r for r in record if r["it"]["conv"] == c]
            groups = list(dict.fromkeys(r["group"] for r in rs if r["group"]))
            # How often the MP voted as most of each group did, in the votes where both voted.
            same, both = Counter(), Counter()
            for r in rs:
                if r["vote"] in ("za", "protiv", "uzdrzan"):
                    for g in groups_in[r["it"]["law"]["final_vote"]]:
                        both[g] += 1
                        same[g] += line[(r["it"]["law"]["final_vote"], g)] == r["vote"]
            agree = sorted(({"group": g, "same": same[g], "both": n, "share": same[g] / n, "own": g in groups}
                            for g, n in both.items() if n >= 10), key=lambda a: (-a["share"], -a["both"], a["group"]))
            pr = presence.get((mp.key, c))
            by_conv.append({"conv": c, "name": ORDINAL_NAME.get(c, c), "groups": groups, "n": len(rs), "agree": agree,
                            "present": pr if pr and pr[1] >= 20 else None, "median": median_presence.get(c),
                            "tally": Counter(r["vote"] for r in rs), "record": rs})
        def view(rs):
            """The lists and tables of the MP page for these votes: one period, or all of them."""
            kinds_table = []
            for k, label in kinds.KINDS.items():
                c = Counter(r["vote"] for r in rs if r["it"]["law"].get("kind", "other") == k)
                if c:
                    kinds_table.append({"label": label, "total": sum(c.values()), **{v: c.get(v, 0) for v in VOTES}})
            # By area (the point of Article 97 the proposer relies on): the areas with five laws or more.
            by_area: dict[str, list] = defaultdict(list)
            for r in rs:
                for a in r["it"].get("areas") or []:
                    by_area[a].append(r)
            areas_table = []
            for a, ars in sorted(by_area.items(), key=lambda kv: (-len(kv[1]), collate(kv[0]))):
                if len(ars) >= 5:
                    c = Counter(r["vote"] for r in ars)
                    # International treaties are informative, as TheyWorkForYou treats votes that decide nothing
                    # of the Assembly's own: counted in the table, left out of the words.
                    scoring = [r for r in ars if r["it"]["law"].get("kind") != "treaty"]
                    cs = Counter(r["vote"] for r in scoring)
                    g = Counter(r["line"] for r in scoring if r["line"])
                    areas_table.append({"label": a, "total": len(ars), **{v: c.get(v, 0) for v in VOTES},
                                        "treaties": len(ars) - len(scoring),
                                        "word": leaning(cs["za"], cs["protiv"]), "group_word": leaning(g["za"], g["protiv"]),
                                        "against": [r for r in ars if r["vote"] == "protiv"]})
            return {"tally": Counter(r["vote"] for r in rs), "n": len(rs), "kinds": kinds_table, "areas": areas_table[:15],
                    "against": [r for r in rs if r["vote"] == "protiv"], "for_": [r for r in rs if r["vote"] == "za"],
                    "apart": [r for r in rs if r["differs"]]}

        # The last days the MP voted or spoke, newest first: the two kinds of activity side by side.
        days_: dict[str, dict] = defaultdict(lambda: {"votes": Counter(), "speeches": 0, "url": ""})
        for r in record:
            days_[r["it"]["final"]["when"][:10]]["votes"][r["vote"]] += 1
        for d, n in spoke_days.get(mp.key, {}).items():
            days_[d].update(speeches=n, url=speech_url.get((mp.key, d), ""))
        timeline = [{"day": d, **v} for d, v in sorted(days_.items(), reverse=True)[:10]]
        keys_ = sorted((r for r in record if r["it"]["law"]["final_vote"] in key_finals),
                       key=lambda r: r["it"]["final"]["when"], reverse=True)[:6]
        periods = [{"key": "sve", "label": "Svi sazivi", **view(record)}]
        if len(by_conv) > 1:
            periods += [{"key": c["conv"], "label": f"{c['name']} saziv", **view(c["record"])} for c in by_conv]
        kinds_table, areas_table = periods[0]["kinds"], periods[0]["areas"]
        rows_mp.append({"mp": mp, "tally": tally, "n": len(record), "by_conv": {c["conv"]: c for c in by_conv},
                        "photo": photo_of.get(mp.key, ""),
                        "convs": sorted({r["it"]["conv"] for r in record}, key=int, reverse=True)})
        if tally:  # the picture shown when the MP's page is shared: the name and the final votes
            picture(out / "poslanik" / f"{mp.slug}.png", mp.name, "Konačna glasanja o zakonima",
                    {k: tally.get(k, 0) for k in VOTES}, (by_conv[0]["groups"] or [""])[0] if by_conv else "")
        (out / "poslanik" / f"{mp.slug}.html").write_text(env.get_template("mp.html").render(
            **common, mp=mp, record=record, tally=tally, by_conv=by_conv, kinds_table=kinds_table, areas_table=areas_table, periods=periods,
            against=[r for r in record if r["vote"] == "protiv"], for_=[r for r in record if r["vote"] == "za"],
            apart=[r for r in record if r["differs"]],
            timeline=timeline, key_votes=keys_, group_slug=group_slug, exchanges=exchanges_of.get(mp.slug, []),
            profile=profiles.get(mp.key), spoke=spoke.get(mp.key, 0), words=words.get(mp.key, []),
            photo=photo_of.get(mp.key, ""),
            floor=[x for x in getattr(pages_floor.render, "per_mp", {}).get(mp.slug, [])
                   if x["exchanges"] or x["points"] or x["measures"] or x["harsh"]],
            said=sorted(said_by.get(mp.key, []), key=lambda x: x["it"]["law"].get("passed") or "", reverse=True),
            root="../"), encoding="utf-8")
    for conv, _ in convs:
        rows = [{"mp": r["mp"], "in": r["by_conv"][conv], "photo": r["photo"]} for r in rows_mp if conv in r["by_conv"]]
        # Who stands out in the convocation, by the same count for everyone: the first five of each.
        def first(n, label, unit):
            top = sorted((r for r in rows if n(r)), key=lambda r: (-n(r), collate(r["mp"].name)))[:5]
            return {"label": label, "unit": unit, "rows": [{"mp": r["mp"], "photo": r["photo"], "n": n(r),
                                                           "group": (r["in"]["groups"] or [""])[0]} for r in top]}
        boards = [first(lambda r: r["in"]["tally"].get("protiv", 0), "Najviše glasova protiv", "protiv"),
                  first(lambda r: sum(1 for x in r["in"]["record"] if x["differs"]), "Najčešće drugačije od svoje grupe", "puta"),
                  first(lambda r: r["in"]["tally"].get("nije_prisutan", 0) + r["in"]["tally"].get("nije_glasao", 0),
                        "Najviše izostanaka sa glasanja", "glasanja")]
        groups = Counter(g for r in rows for g in r["in"]["groups"][:1])
        (out / mps_page(conv, current)).write_text(env.get_template("mps.html").render(
            **common, rows=rows, boards=[b for b in boards if b["rows"]], conv=conv, conv_name=ORDINAL_NAME.get(conv, conv), root="",
            groups=sorted(groups.items(), key=lambda kv: (-kv[1], collate(kv[0])))), encoding="utf-8")

    from zailiprotiv import pages_groups
    group_rows, numbers = pages_groups.render(common=common, conv_list=conv_list, env=env, finals=finals,
        former=former, group_slug=group_slug, items_by_conv=items_by_conv, key_finals=key_finals,
        lines_of=lines_of, out=out, rows_mp=rows_mp, seat=seat)
    from zailiprotiv import pages_quiz
    active = pages_quiz.render(by_key_all=by_key_all, common=common, profiles=profiles, convs=convs, current=current, env=env,
        group_rows=group_rows, items_by_conv=items_by_conv, key_votes=key_votes, line=line, out=out, root=root,
        rows_mp=rows_mp)
    from zailiprotiv import pages_procedure
    coming, waiting = pages_procedure.render(common=common, current=current, env=env,
        items_by_conv=items_by_conv, loaded=loaded, out=out, root=root)
    from zailiprotiv import digest
    digest.render(env=env, common=common, out=out, root=root, current=current, items_by_conv=items_by_conv,
                  site_url=f"https://{domain}/" if domain else "")
    # What the page's own script searches and filters: every law and MP, in one file fetched on first use.
    index = {"laws": [{"t": it["law"]["short"], "f": it["law"]["title"] + " " + " ".join(it.get("aka") or []), "s": it["slug"], "d": it["law"].get("passed") or "",
                       "za": it["final"]["counts"]["za"] if it["final"] else None,
                       "pr": it["final"]["counts"]["protiv"] if it["final"] else None,
                       "n": sum(it["final"]["counts"].values()) if it["final"] else None,
                       "sh": round(it.get("share") or 0, 4), "u": int(bool(it["urgent"])), "k": it["law"].get("kind", "other"),
                       "c": it["conv"]} for its in items_by_conv.values() for it in its],
             "mps": [{"n": r["mp"].name, "s": r["mp"].slug, "g": r["mp"].group or ""} for r in rows_mp]}
    (out / "podaci.json").write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    items = items_by_conv[active]
    votes = loaded[active][1]
    stats = {"laws": len(items), "linked": sum(1 for it in items if it["final"]), "votes": len(votes),
             "mps": len({mps.key(r[1]) for v in votes.values() for r in v["rows"]}),
             "treaties": sum(1 for it in items if it["law"].get("kind") == "treaty"),
             "sittings": len({v["sitting"] for v in votes.values()}),
             "all_laws": sum(len(i) for i in items_by_conv.values()), "all_mps": len(people), "waiting": len(waiting)}
    # The home page's lead: the law of the last year (of the convocation shown) with the largest share against.
    newest = max((it["law"].get("passed") or "" for it in items), default="")
    year_ago = f"{int(newest[:4]) - 1}{newest[4:]}" if newest else ""
    divisive = (most_against([it for it in items if (it["law"].get("passed") or "") >= year_ago], 1) or most_against(items, 1) or [None])[0]
    # The newest sitting's laws, the most votes against first (a sitting often passes a run of alike laws).
    last_sitting = [it for it in items if it["final"] and it["final"]["sitting"] == next(
        (x["final"]["sitting"] for x in items if x["final"]), None)]
    last_sitting.sort(key=lambda it: -(it["final"]["counts"]["protiv"] or 0))
    (out / "index.html").write_text(env.get_template("index.html").render(
        **common, divisive=divisive,
        quiz_laws=getattr(pages_quiz.render, "laws", []), floor_top=getattr(pages_floor.render, "top", {}).get(active),
        last_sitting=last_sitting, last_sitting_slug=sitting_page(last_sitting[0]["final"]["sitting"], last_sitting[0]["final"]["sitting_title"]) if last_sitting else "",
        stats=stats, coming=coming, of_conv=None if active == current else ORDINAL_NAME.get(active, active), latest=items[:6], contested=most_against(items, 9), root="",
        spotlight=spotlight([it for its in items_by_conv.values() for it in its], items,
                            (most_against(items, 1) or [{}])[0].get("key")),
        featured=next((it for it in most_against(items, 9) if len(it["pair"]) == 2), None),
        ranked=most_against([it for its in items_by_conv.values() for it in its], 8),
        kinds_count=[(k, kinds.KINDS[k], n) for k, n in sorted(Counter(it["law"].get("kind", "other") for it in items)
                                                                .items(), key=lambda kv: -kv[1]) if k in kinds.KINDS],
        debated=sum(1 for it in items if it["said"])), encoding="utf-8")
    (out / "o-projektu.html").write_text(env.get_template("about.html").render(**common, stats=stats, root=""),
                                         encoding="utf-8")
    from zailiprotiv import pages_lists
    by_area = pages_lists.render(area_slug=area_slug, common=common, conv_list=conv_list, env=env,
        items_by_conv=items_by_conv, key_votes=key_votes, numbers=numbers, out=out, rows_mp=rows_mp)
    from zailiprotiv import downloads
    downloads.write(common=common, domain=domain, env=env, items_by_conv=items_by_conv, out=out, people=people)
    from zailiprotiv import feeds
    feeds.write(area_slug=area_slug, by_area=by_area, domain=domain, feeds_mp=feeds_mp,
        items_by_conv=items_by_conv, out=out, waiting=waiting)
    (out / ".nojekyll").write_text("", encoding="utf-8")
    if cyrillic:  # every page again under cir/, in Cyrillic
        from zailiprotiv import cyrillic as cyrillic_
        cyrillic_.edition(out)
    if clean:
        clean_urls(out)
    return stats


from zailiprotiv.publish import PAGE_LIMIT, check, clean_urls  # noqa: E402,F401  (used as site.check and so on)
