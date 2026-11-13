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
        bills.setdefault(path.name, {})["debate"] = json.loads(path.read_text(encoding="utf-8"))
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


ORDINAL_NAME = {"11": "Jedanaesti", "12": "Dvanaesti", "13": "Trinaesti", "14": "Četrnaesti", "15": "Petnaesti"}


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


def build(root: Path, out: Path, domain: str | None = None) -> dict:
    convs = convocations(root)
    current = convs[0][0]
    loaded = {c: load(path) for c, path in convs}
    debates = {c: load_transcripts(path) for c, path in convs}
    all_votes = {k: v for _, votes, _ in loaded.values() for k, v in votes.items()}
    people = registry(all_votes)
    env = Environment(loader=FileSystemLoader(HERE / "templates"), autoescape=select_autoescape(["html"]),
                      trim_blocks=True, lstrip_blocks=True)
    area_slug = lambda a: slug(latin(a))[:80]
    env.filters.update(latin=latin, day=day, day_of=day_of, vote_label=lambda v: VOTE_LABEL.get(v, v), area_slug=area_slug)
    if out.exists():
        shutil.rmtree(out)
    (out / "zakon").mkdir(parents=True)
    (out / "poslanik").mkdir()
    for name in ("style.css", "site.js"):
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
    common = {"css": css_version, "built": built, "fetched": loaded[current][0].get("fetched", "")[:10], "vote_label": VOTE_LABEL,
              "VOTES": VOTES, "convs": conv_list, "current": current, "site_url": f"https://{domain}/" if domain else ""}

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
    # MPs: their final votes on laws, in every convocation.
    finals = {it["law"]["final_vote"]: it for items in items_by_conv.values() for it in items
              if it["law"].get("final_vote")}
    # In each final vote: every MP's group, and how most of each group voted (three or more voting, a clear majority).
    seat, line = {}, {}
    for key, it in finals.items():
        cast: dict[str, Counter] = defaultdict(Counter)
        for _, name, how, group in it["final"]["rows"]:
            g = (latin(group) or "Bez poslaničke grupe").strip("() ")  # "(NADA …)" and "NADA …" are one group
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
    from zailiprotiv import card
    import os
    cache = Path(os.environ.get("ZAILIPROTIV_CACHE", ".cache")) / "og"
    cache.mkdir(parents=True, exist_ok=True)
    for args in law_pages:
        it = args["it"]
        if it["final"]:  # the picture shown when the page is shared
            name = it["aka"][0][:1].upper() + it["aka"][0][1:] if it["aka"] else it["law"]["short"]
            args_ = (name, day(it["law"].get("passed")), it["final"]["counts"], "hitan postupak" if it["urgent"] else "")
            kept = cache / (hashlib.sha256(repr((card.VERSION, args_)).encode()).hexdigest()[:24] + ".png")
            if not kept.exists():  # drawing 1,500 pictures takes a minute; a picture only changes with what it shows
                card.draw(kept, *args_)
            shutil.copy(kept, out / "zakon" / f"{it['slug']}.png")
        (out / "zakon" / f"{args['it']['slug']}.html").write_text(
            env.get_template("law.html").render(**common, **args, group_slug=group_slug), encoding="utf-8")
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
                        "convs": sorted({r["it"]["conv"] for r in record}, key=int, reverse=True)})
        (out / "poslanik" / f"{mp.slug}.html").write_text(env.get_template("mp.html").render(
            **common, mp=mp, record=record, tally=tally, by_conv=by_conv, kinds_table=kinds_table, areas_table=areas_table, periods=periods,
            against=[r for r in record if r["vote"] == "protiv"], for_=[r for r in record if r["vote"] == "za"],
            apart=[r for r in record if r["differs"]],
            timeline=timeline, key_votes=keys_, group_slug=group_slug,
            profile=profiles.get(mp.key), spoke=spoke.get(mp.key, 0), words=words.get(mp.key, []),
            said=sorted(said_by.get(mp.key, []), key=lambda x: x["it"]["law"].get("passed") or "", reverse=True),
            root="../"), encoding="utf-8")
    for conv, _ in convs:
        rows = [{"mp": r["mp"], "in": r["by_conv"][conv]} for r in rows_mp if conv in r["by_conv"]]
        groups = Counter(g for r in rows for g in r["in"]["groups"][:1])
        (out / mps_page(conv, current)).write_text(env.get_template("mps.html").render(
            **common, rows=rows, conv=conv, conv_name=ORDINAL_NAME.get(conv, conv), root="",
            groups=sorted(groups.items(), key=lambda kv: (-kv[1], collate(kv[0])))), encoding="utf-8")

    # A page per group and convocation: members, how united it votes, its line by area and on the key votes, and the
    # votes that split it. The same numbers for every group; no ranking of MPs.
    cast_in: dict[tuple, Counter] = defaultdict(Counter)
    for key, it in finals.items():
        for _, name, how, _ in it["final"]["rows"]:
            cast_in[(key, seat[(key, mps.key(name))])][how] += 1
    (out / "grupa").mkdir(exist_ok=True)
    group_rows: dict[str, list] = defaultdict(list)
    for (c, g), gslug in sorted(group_slug.items()):
        ls = sorted(lines_of[(c, g)], key=lambda kl: finals[kl[0]]["final"]["when"], reverse=True)
        # Everyone listed under this name in the convocation, with their votes while under it.
        members = [{"mp": r["mp"], "tally": Counter(x["vote"] for x in r["by_conv"][c]["record"] if x["group"] == g)}
                   for r in rows_mp if c in r["by_conv"] and g in r["by_conv"][c]["groups"]]
        votes_ = []
        for key, how in ls:
            cc = cast_in[(key, g)]
            voting = cc["za"] + cc["protiv"] + cc["uzdrzan"]
            votes_.append({"it": finals[key], "line": how, "counts": {v: cc.get(v, 0) for v in VOTES}, "voting": voting,
                           "with": cc[how], "share": cc[how] / voting})
        listed = sum(sum(v["counts"].values()) for v in votes_ if v["it"]["final"]["counts"]["nije_prisutan"])
        present = listed - sum(v["counts"]["nije_prisutan"] for v in votes_ if v["it"]["final"]["counts"]["nije_prisutan"])
        by_area_g: dict[str, Counter] = defaultdict(Counter)
        for v in votes_:
            if v["it"]["law"].get("kind") != "treaty":
                for a in v["it"].get("areas") or []:
                    by_area_g[a][v["line"]] += 1
        areas_g = [{"label": a, "n": sum(cn.values()), "za": cn["za"], "protiv": cn["protiv"], "uzdrzan": cn["uzdrzan"],
                    "word": leaning(cn["za"], cn["protiv"])}
                   for a, cn in sorted(by_area_g.items(), key=lambda kv: (-sum(kv[1].values()), collate(kv[0])))
                   if sum(cn.values()) >= 5]
        whens = sorted(finals[key]["final"]["when"][:10] for key, _ in ls)
        info = {"name": g, "slug": gslug, "conv": c, "conv_name": ORDINAL_NAME.get(c, c),
                "members": max(sum(cast_in[(key, g)].values()) for key, _ in ls), "first": whens[0], "last": whens[-1],
                "votes": len(votes_), "lines": Counter(v["line"] for v in votes_),
                "cohesion": sum(v["with"] for v in votes_) / sum(v["voting"] for v in votes_),
                "presence": (present, listed) if listed else None}
        group_rows[c].append(info)
        (out / "grupa" / f"{gslug}.html").write_text(env.get_template("group.html").render(
            **common, g=info, members=members, areas=areas_g,
            key_votes=[v for v in votes_ if v["it"]["law"]["final_vote"] in key_finals][:8],
            against=[v for v in votes_ if v["line"] == "protiv"],
            split=sorted((v for v in votes_ if v["voting"] - v["with"] >= 2), key=lambda v: (v["share"], v["it"]["final"]["when"]))[:10],
            root="../"), encoding="utf-8")
    for c in group_rows:
        group_rows[c].sort(key=lambda g: (-g["members"], collate(g["name"])))
    (out / "grupe.html").write_text(env.get_template("groups.html").render(
        **common, by_conv=[(cv, group_rows[cv["n"]]) for cv in conv_list if group_rows.get(cv["n"])], root=""), encoding="utf-8")
    # The Assembly in numbers, by convocation: how laws are passed, and the same figures for every group.
    def median(xs):
        xs = sorted(xs)
        return xs[len(xs) // 2] if xs else None
    numbers = []
    for cv in conv_list:
        its = items_by_conv[cv["n"]]
        voted = [it for it in its if it["final"]]
        with_bill = [it for it in its if it["law"].get("bill_file")]
        numbers.append({"conv": cv, "laws": len(its), "voted": len(voted),
                        "treaties": sum(1 for it in its if it["law"].get("kind") == "treaty"),
                        "urgent": sum(1 for it in with_bill if it["urgent"]), "with_bill": len(with_bill),
                        "days": median([it["days"] for it in its if it["days"] is not None and it["days"] >= 0]),
                        "unopposed": sum(1 for it in voted if not it["final"]["counts"]["protiv"]),
                        "sittings": len({it["final"]["sitting"] for it in voted}), "groups": group_rows.get(cv["n"], [])})
    (out / "brojke.html").write_text(env.get_template("numbers.html").render(**common, numbers=numbers, root=""),
                                     encoding="utf-8")
    # "Glasaj i ti": the visitor votes on the current convocation's key laws; the page's own script compares the
    # answers with every group's line and every MP's votes. Nothing leaves the browser.
    quiz_laws = list(key_votes[current])
    for r in most_against(items_by_conv[current], len(items_by_conv[current])):
        it = by_key_all[r["key"]]
        if len(quiz_laws) >= 10:
            break
        if it not in quiz_laws and it["law"].get("kind") != "treaty" and not (it["aka"] and any(it["aka"][0] == (q["aka"] or [""])[0] for q in quiz_laws)):
            quiz_laws.append(it)
    quiz_laws = sorted((it for it in quiz_laws if it["gist"]), key=lambda it: it["final"]["when"], reverse=True)
    letter = {"za": "z", "protiv": "p", "uzdrzan": "u"}
    quiz = {"laws": [{"s": it["slug"]} for it in quiz_laws],
            "groups": [{"n": g["name"], "s": g["slug"], "m": g["members"],
                        "v": "".join(letter.get(line.get((it["law"]["final_vote"], g["name"])), "-") for it in quiz_laws)}
                       for g in group_rows.get(current, [])],
            "mps": [{"n": r["mp"].name, "s": r["mp"].slug, "g": (r["by_conv"][current]["groups"] or [""])[0],
                     "v": "".join(letter.get(r["mp"].votes.get(it["law"]["final_vote"]), "-") for it in quiz_laws)}
                    for r in rows_mp if current in r["by_conv"]]}
    settings = json.loads((root / "settings.json").read_text(encoding="utf-8")) if (root / "settings.json").exists() else {}
    # The laws visitors' votes are counted for: the counter (worker/) accepts no others.
    (out / "glasaj.json").write_text(json.dumps({"laws": [it["slug"] for it in quiz_laws]}), encoding="utf-8")
    shutil.copy(HERE / "static" / "glasaj.js", out / "glasaj.js")
    (out / "glasaj.html").write_text(env.get_template("quiz.html").render(
        **common, laws=quiz_laws, votes_api=settings.get("votes_api", ""), quiz=json.dumps(quiz, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"),
        root=""), encoding="utf-8")

    # Bills in procedure (the current convocation): what waits now, what is no longer listed, and the sittings
    # convened whose votes are not out yet, with their agenda.
    from zailiprotiv import link as link_, procedure as procedure_
    proc_path, index_path = root / current / "procedure.json", root / current / "index.json"
    proc = json.loads(proc_path.read_text(encoding="utf-8")) if proc_path.exists() else {"bills": {}, "fetched": ""}
    sittings_index = json.loads(index_path.read_text(encoding="utf-8"))["sittings"] if index_path.exists() else {}
    today = dt.date.today()
    coming = sorted(({"title": sv["title"], "url": u, "starts": sv.get("starts", ""), "agenda": sv["agenda"]}
                     for u, sv in sittings_index.items() if sv.get("agenda") and not sv.get("votes")
                     and (sv.get("starts") or "9999")[:10] >= (today - dt.timedelta(days=45)).isoformat()),
                    key=lambda x: x["starts"])
    on_agenda = {}
    for sv in coming:
        for item in sv["agenda"]:
            on_agenda.setdefault(link_.act_name(item), sv)
    by_bill_pdf = {it["law"].get("bill_pdf"): it for it in items_by_conv[current] if it["law"].get("bill_pdf")}
    waiting, gone = [], []
    for pdf, b in proc["bills"].items():
        row = {**b, "pdf": pdf, "who": procedure_.proposer_kind(b["proposer"]),
               "kind": kinds.KINDS.get(kinds.kind(b["title"]), ""), "kind_key": kinds.kind(b["title"]),
               "days": days_between(b["submitted"], today.isoformat()), "law": by_bill_pdf.get(pdf),
               "sitting": on_agenda.get(link_.act_name(b["title"]))}
        (waiting if b["last_seen"] == proc["fetched"] and not row["law"] else gone).append(row)
    waiting.sort(key=lambda r: (r["submitted"] or "", r["title"]), reverse=True)
    gone.sort(key=lambda r: (r["last_seen"], r["submitted"] or ""), reverse=True)
    who_label = {"vlada": "Vlada", "poslanici": "Poslanici", "drugi": "Drugi predlagači"}
    (out / "u-proceduri.html").write_text(env.get_template("procedure.html").render(
        **common, waiting=waiting, gone=gone[:200], coming=coming, checked=proc["fetched"], who_label=who_label,
        who_counts=[(k, who_label[k], sum(1 for r in waiting if r["who"] == k)) for k in who_label],
        oldest=min((r["submitted"] for r in waiting if r["submitted"]), default=None), root=""), encoding="utf-8")

    # What the page's own script searches and filters: every law and MP, in one file fetched on first use.
    index = {"laws": [{"t": it["law"]["short"], "f": it["law"]["title"] + " " + " ".join(it.get("aka") or []), "s": it["slug"], "d": it["law"].get("passed") or "",
                       "za": it["final"]["counts"]["za"] if it["final"] else None,
                       "pr": it["final"]["counts"]["protiv"] if it["final"] else None,
                       "n": sum(it["final"]["counts"].values()) if it["final"] else None,
                       "sh": round(it.get("share") or 0, 4), "u": int(bool(it["urgent"])), "k": it["law"].get("kind", "other"),
                       "c": it["conv"]} for its in items_by_conv.values() for it in its],
             "mps": [{"n": r["mp"].name, "s": r["mp"].slug, "g": r["mp"].group or ""} for r in rows_mp]}
    (out / "podaci.json").write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    items = items_by_conv[current]
    votes = loaded[current][1]
    stats = {"laws": len(items), "linked": sum(1 for it in items if it["final"]), "votes": len(votes),
             "mps": len({mps.key(r[1]) for v in votes.values() for r in v["rows"]}),
             "treaties": sum(1 for it in items if it["law"].get("kind") == "treaty"),
             "sittings": len({v["sitting"] for v in votes.values()}),
             "all_laws": sum(len(i) for i in items_by_conv.values()), "all_mps": len(people), "waiting": len(waiting)}
    (out / "index.html").write_text(env.get_template("index.html").render(
        **common, stats=stats, latest=items[:6], contested=most_against(items, 9), root="",
        spotlight=spotlight([it for its in items_by_conv.values() for it in its], items,
                            (most_against(items, 1) or [{}])[0].get("key")),
        featured=next((it for it in most_against(items, 9) if len(it["pair"]) == 2), None),
        ranked=most_against([it for its in items_by_conv.values() for it in its], 8),
        kinds_count=[(k, kinds.KINDS[k], n) for k, n in sorted(Counter(it["law"].get("kind", "other") for it in items)
                                                                .items(), key=lambda kv: -kv[1]) if k in kinds.KINDS],
        debated=sum(1 for it in items if it["said"])), encoding="utf-8")
    (out / "o-projektu.html").write_text(env.get_template("about.html").render(**common, stats=stats, root=""),
                                         encoding="utf-8")
    # A page per area (the point of Article 97), every convocation, newest first.
    by_area = defaultdict(list)
    for its in items_by_conv.values():
        for it in its:
            for a in it.get("areas") or []:
                by_area[a].append(it)
    (out / "oblast").mkdir(exist_ok=True)
    for a, its in by_area.items():
        its.sort(key=lambda it: it["law"].get("passed") or "", reverse=True)
        (out / "oblast" / f"{area_slug(a)}.html").write_text(env.get_template("area.html").render(
            **common, area=a, laws=its, root="../"), encoding="utf-8")
    (out / "oblasti.html").write_text(env.get_template("areas.html").render(
        **common, areas=[{"name": a, "slug": area_slug(a), "n": len(by_area[a])}
                         for a in sorted(by_area, key=lambda a: (-len(by_area[a]), collate(a)))], root=""), encoding="utf-8")
    # A page per sitting: its laws and their final votes, the way the Assembly's own sitting page groups them.
    by_sitting: dict[str, list] = defaultdict(list)
    for its in items_by_conv.values():
        for it in its:
            if it.get("final"):
                by_sitting[it["final"]["sitting"]].append(it)
    sitting_slug = {}
    (out / "sednica").mkdir(exist_ok=True)
    for url, its in by_sitting.items():
        its.sort(key=lambda it: it["final"]["when"])
        first = its[0]
        name = sitting_page(url, first["final"]["sitting_title"])
        sitting_slug[url] = name
        (out / "sednica" / f"{name}.html").write_text(env.get_template("sitting.html").render(
            **common, title=first["final"]["sitting_title"], url=url, laws=its, conv_name=first["conv_name"],
            first=its[0]["final"]["when"][:10], last=its[-1]["final"]["when"][:10], root="../"), encoding="utf-8")
    sittings_list = sorted(({"slug": sitting_slug[u], "title": its[0]["final"]["sitting_title"], "n": len(its),
                             "day": its[0]["final"]["when"][:10], "conv": its[0]["conv"], "conv_name": its[0]["conv_name"],
                             "against": sum((it["final"]["counts"]["protiv"] or 0) for it in its)}
                            for u, its in by_sitting.items()), key=lambda x: x["day"], reverse=True)
    (out / "sednice.html").write_text(env.get_template("sittings.html").render(
        **common, by_conv=[(cv, [x for x in sittings_list if x["conv"] == cv["n"]]) for cv in conv_list], root=""),
        encoding="utf-8")
    # A page per convocation: its figures, key votes, groups and sittings, and the way to its laws and MPs.
    for n in numbers:
        c = n["conv"]["n"]
        (out / f"saziv-{c}.html").write_text(env.get_template("convocation.html").render(
            **common, n=n, conv=c, cv=n["conv"], key_votes=key_votes.get(c, []),
            against=most_against(items_by_conv[c], 5), sittings=[x for x in sittings_list if x["conv"] == c],
            mps=sum(1 for r in rows_mp if c in r["by_conv"]),
            first=min((it["law"].get("passed") or "9999" for it in items_by_conv[c]), default=""),
            last=max((it["law"].get("passed") or "" for it in items_by_conv[c]), default=""), root=""), encoding="utf-8")

    # Downloads: every law with its final vote, and every MP's final votes by convocation (CSV), and the roll call
    # of each law beside its page (CSV and JSON).
    import csv, io
    site_url = f"https://{domain}/" if domain else ""

    def display_name(name):
        mp = people.get(mps.key(name))
        return mp.name if mp else name
    (out / "podaci").mkdir(exist_ok=True)
    def write_csv(path, header, rows):
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(header)
        w.writerows(rows)
        path.write_text(buf.getvalue(), encoding="utf-8")
    write_csv(out / "podaci" / "zakoni.csv",
              ["saziv", "usvojen", "kratak_naziv", "zvanican_naziv", "vrsta", "oblast", "za", "protiv", "uzdrzan",
               "nije_glasao", "nije_prisutan", "strana", "glasanje_pdf", "zakon_pdf", "predlog_pdf"],
              [[it["conv"], it["law"].get("passed"), it["law"]["short"], latin(it["law"]["title"]), latin(it["kind"]),
                "; ".join(latin(a) for a in it.get("areas") or []),
                *[(it["final"] or {}).get("counts", {}).get(v, "") if it.get("final") else "" for v in VOTES],
                f"{site_url}zakon/{it['slug']}.html", (it.get("final") or {}).get("key", "").split("#")[0],
                it["law"].get("pdf", ""), it["law"].get("bill_pdf", "")]
               for its in items_by_conv.values() for it in its])
    downloads = []
    for conv, its in items_by_conv.items():
        rows = []
        for it in its:
            f = it.get("final")
            if not f:
                continue
            for _, name, how, group in f["rows"]:
                rows.append([it["law"].get("passed"), it["law"]["short"], display_name(name), latin(group), how])
        write_csv(out / "podaci" / f"glasovi-{conv}.csv", ["usvojen", "zakon", "poslanik", "grupa", "glas"], rows)
        downloads.append({"conv": conv, "name": ORDINAL_NAME.get(conv, conv), "rows": len(rows), "laws": len(its)})
        for it in its:
            f = it.get("final")
            if f:
                roll = [[display_name(n), latin(g), how] for _, n, how, g in f["rows"]]
                write_csv(out / "zakon" / f"{it['slug']}.csv", ["poslanik", "grupa", "glas"], roll)
                (out / "zakon" / f"{it['slug']}.json").write_text(json.dumps(
                    {"zakon": it["law"]["short"], "zvanican_naziv": latin(it["law"]["title"]), "usvojen": it["law"].get("passed"),
                     "glasanje": f["when"], "pdf": f["key"].split("#")[0], "rezultat": f["counts"],
                     "glasovi": [{"poslanik": a, "grupa": b, "glas": c} for a, b, c in roll]},
                    ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "podaci.html").write_text(env.get_template("data.html").render(**common, downloads=downloads, root=""),
                                     encoding="utf-8")
    (out / "kako-racunamo.html").write_text(env.get_template("method.html").render(**common, root=""), encoding="utf-8")
    if domain:
        (out / "CNAME").write_text(domain + "\n", encoding="utf-8")
        base = f"https://{domain}/"
        pages = sorted(p.relative_to(out).as_posix() for p in out.rglob("*.html"))
        (out / "sitemap.xml").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + "".join(f"<url><loc>{base}{p}</loc></url>\n" for p in pages) + "</urlset>\n", encoding="utf-8")
        (out / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {base}sitemap.xml\n", encoding="utf-8")
    # Atom feeds: the newest laws, and each MP's newest final votes (static files, nothing from other servers).
    site = f"https://{domain}/" if domain else ""
    newest = sorted((it for its in items_by_conv.values() for it in its), key=lambda it: it["law"].get("passed") or "",
                    reverse=True)[:50]
    word = {"za": "za", "protiv": "protiv", "uzdrzan": "uzdržan", "nije_glasao": "nije glasao", "nije_prisutan": "nije prisutan"}

    def entry(it, title, summary):
        c = (it.get("final") or {}).get("counts") or {}
        tally = f"{c.get('za', 0)} za, {c.get('protiv', 0)} protiv. " if c else ""
        return {"title": title, "link": f"{site}zakon/{it['slug']}.html", "id": f"{site}zakon/{it['slug']}.html",
                "updated": (it["law"].get("passed") or "2000-01-01") + "T00:00:00Z", "summary": tally + summary}

    write_feed(out / "zakoni.xml", "Za ili Protiv: novi zakoni", f"{site}zakoni.xml", f"{site}index.html",
               [entry(it, it["law"]["short"], latin(it.get("gist") or "")) for it in newest])
    write_feed(out / "u-proceduri.xml", "Za ili Protiv: novi predlozi zakona", f"{site}u-proceduri.xml", f"{site}u-proceduri.html",
               [{"title": latin(r["title"]), "link": r["pdf"], "id": r["pdf"],
                 "updated": (r["submitted"] or "2000-01-01") + "T00:00:00Z", "summary": "Predlagač: " + latin(r["proposer"])}
                for r in waiting[:50]])
    for a, its in by_area.items():
        write_feed(out / "oblast" / f"{area_slug(a)}.xml", f"Za ili Protiv: {latin(a)}", f"{site}oblast/{area_slug(a)}.xml",
                   f"{site}oblast/{area_slug(a)}.html",
                   [entry(it, it["law"]["short"], latin(it.get("gist") or "")) for it in its[:40]])
    (out / "poslanik").mkdir(exist_ok=True)
    for mp_slug, (name, record) in feeds_mp.items():
        write_feed(out / "poslanik" / f"{mp_slug}.xml", f"Za ili Protiv: {name}", f"{site}poslanik/{mp_slug}.xml",
                   f"{site}poslanik/{mp_slug}.html",
                   [entry(r["it"], f"{word.get(r['vote'], r['vote'])}: {r['it']['law']['short']}",
                          "Drugačije od većine svoje grupe. " if r["differs"] else "") for r in record])
    (out / ".nojekyll").write_text("", encoding="utf-8")
    return stats


# What every built page must keep to (project principles): nothing loaded from another site, and pages light enough
# for a phone. The largest page now is under 0.6 MB.
PAGE_LIMIT = 1_000_000
EXTERNAL = re.compile(r"<(?:script|iframe|img|source|video|audio|embed|object)\b[^>]*\bsrc=[\"'](?:https?:)?//"
                      r"|<link\b[^>]*\bhref=[\"'](?:https?:)?//[^\"']*[\"'][^>]*\brel=[\"'](?:stylesheet|preload|icon|modulepreload)"
                      r"|<link\b[^>]*\brel=[\"'](?:stylesheet|preload|icon|modulepreload)[\"'][^>]*\bhref=[\"'](?:https?:)?//"
                      r"|@import\s+url\(\s*[\"']?(?:https?:)?//|url\(\s*[\"']?(?:https?:)?//", re.I)


def check(out: Path) -> list[str]:
    """What is wrong with a built site: pages over the limit, anything loaded from another site."""
    bad = []
    for f in sorted(out.rglob("*")):
        if f.suffix not in (".html", ".css", ".js"):
            continue
        text = f.read_text(encoding="utf-8")
        if f.suffix == ".html" and len(text.encode()) > PAGE_LIMIT:
            bad.append(f"{f.relative_to(out)}: {len(text.encode()) / 1e6:.1f} MB")
        m = EXTERNAL.search(text)
        if m:
            bad.append(f"{f.relative_to(out)}: spoljni resurs: {m.group(0)[:80]}")
    return bad
