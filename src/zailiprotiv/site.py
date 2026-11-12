"""The static site: the convocation's laws, each with its final roll call by group and by MP, and every MP's votes.

Pages are written in Latin script: names and titles from the Assembly's Cyrillic documents are transliterated.
Nothing on the pages comes from another server: no scripts, fonts or analytics (AGENTS.md, principle 5).
"""

from __future__ import annotations

import datetime as dt
import json
import re
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
    name = re.sub(r" u (celini|nacelu|pojedinostima)$", "", link.act_name(final.get("item") or law["title"]))
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
    for v in sorted(votes.values(), key=lambda v: v["when"]):
        report = v["counts"]["nije_prisutan"] > 0
        for _, name, vote, group in v["rows"]:
            k = mps.key(name)
            mp = out.setdefault(k, MP(k, title_case(name)))
            if report and not name.split()[0].istitle():
                mp.name = title_case(name)
            mp.votes[v["key"]] = vote
            mp.group, mp.last_seen = latin(group), v["when"]
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


def most_against(items: list[dict], n: int) -> list[dict]:
    """The laws whose final vote had the largest share against, the same rule for every law; ties go to more
    votes against, then the newer law."""
    voted = [it for it in items if it["final"] and it["final"]["counts"]["protiv"]]
    ranked = sorted(voted, key=lambda it: (against_share(it["final"]["counts"]), it["final"]["counts"]["protiv"],
                                           it["law"].get("passed") or ""), reverse=True)
    return [{**it, "share": against_share(it["final"]["counts"]), "against": against_by_group(it["final"])}
            for it in ranked[:n]]


ORDINAL_NAME = {"12": "Dvanaesti", "13": "Trinaesti", "14": "Četrnaesti", "15": "Petnaesti"}


def convocations(root: Path) -> list[tuple[str, Path]]:
    """The convocations with data, newest first: data/<N>/laws.json (or a single folder with laws.json in it)."""
    from zailiprotiv.config import CURRENT
    if (root / "laws.json").exists():
        return [(CURRENT, root)]
    found = [(p.name, p) for p in root.iterdir() if p.is_dir() and (p / "laws.json").exists()]
    return sorted(found, key=lambda c: int(c[0]) if c[0].isdigit() else 0, reverse=True)


def laws_page(conv: str, current: str) -> str:
    return "zakoni.html" if conv == current else f"zakoni-{conv}.html"


def build(root: Path, out: Path, domain: str | None = None) -> dict:
    convs = convocations(root)
    current = convs[0][0]
    loaded = {c: load(path) for c, path in convs}
    debates = {c: load_transcripts(path) for c, path in convs}
    all_votes = {k: v for _, votes, _ in loaded.values() for k, v in votes.items()}
    people = registry(all_votes)
    env = Environment(loader=FileSystemLoader(HERE / "templates"), autoescape=select_autoescape(["html"]),
                      trim_blocks=True, lstrip_blocks=True)
    env.filters.update(latin=latin, day=day, day_of=day_of, vote_label=lambda v: VOTE_LABEL.get(v, v))
    if out.exists():
        shutil.rmtree(out)
    (out / "zakon").mkdir(parents=True)
    (out / "poslanik").mkdir()
    shutil.copy(HERE / "static" / "style.css", out / "style.css")
    built = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    conv_list = [{"n": c, "name": ORDINAL_NAME.get(c, c + "."), "page": laws_page(c, current),
                  "laws": len(loaded[c][0]["laws"])} for c, _ in convs]
    common = {"built": built, "fetched": loaded[current][0].get("fetched", "")[:10], "vote_label": VOTE_LABEL,
              "VOTES": VOTES, "convs": conv_list, "current": current}

    # Laws, newest first within each convocation, the current one first so its addresses never change.
    items_by_conv, taken = {}, Counter()
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
                          "summary": bill.get("summary"), "notes": bill.get("notes"),
                          "said": bill.get("debate"), "conv": conv,
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
            page = env.get_template("law.html").render(
                **common, it=it, law=law, final=final, groups=by_group(final) if final else [], roll=roll,
                others=others, reasons=excerpt(sections.get("reasons", ""), 1200),
                funds=excerpt(sections.get("funds", ""), 500), effects=excerpt(sections.get("effects", ""), 600),
                report=bool(final and final["counts"]["nije_prisutan"]), root="../")
            (out / "zakon" / f"{it['slug']}.html").write_text(page, encoding="utf-8")
        by_kind = defaultdict(list)
        for it in items:
            by_kind[it["law"].get("kind", "other")].append(it)
        kind_order = [k for k in kinds.KINDS if k in by_kind]
        (out / laws_page(conv, current)).write_text(env.get_template("laws.html").render(
            **common, by_kind=by_kind, kind_order=kind_order, KINDS=kinds.KINDS, total=len(items), conv=conv,
            conv_name=ORDINAL_NAME.get(conv, conv), root=""), encoding="utf-8")

    # MPs: their final votes on laws, in every convocation.
    finals = {it["law"]["final_vote"]: it for items in items_by_conv.values() for it in items
              if it["law"].get("final_vote")}
    rows_mp = []
    for mp in sorted(people.values(), key=lambda m: collate(m.name)):
        record = [{"it": finals[k], "vote": how} for k, how in mp.votes.items() if k in finals]
        record.sort(key=lambda r: r["it"]["final"]["when"], reverse=True)
        tally = Counter(r["vote"] for r in record)
        rows_mp.append({"mp": mp, "tally": tally, "n": len(record),
                        "convs": sorted({r["it"]["conv"] for r in record}, key=int, reverse=True)})
        (out / "poslanik" / f"{mp.slug}.html").write_text(env.get_template("mp.html").render(
            **common, mp=mp, record=record, tally=tally, root="../"), encoding="utf-8")
    (out / "poslanici.html").write_text(env.get_template("mps.html").render(
        **common, rows=rows_mp, root=""), encoding="utf-8")

    items = items_by_conv[current]
    votes = loaded[current][1]
    stats = {"laws": len(items), "linked": sum(1 for it in items if it["final"]), "votes": len(votes),
             "mps": len({mps.key(r[1]) for v in votes.values() for r in v["rows"]}),
             "treaties": sum(1 for it in items if it["law"].get("kind") == "treaty"),
             "sittings": len({v["sitting"] for v in votes.values()}),
             "all_laws": sum(len(i) for i in items_by_conv.values()), "all_mps": len(people)}
    (out / "index.html").write_text(env.get_template("index.html").render(
        **common, stats=stats, latest=items[:6], contested=most_against(items, 12), root="",
        kinds_count=[(k, kinds.KINDS[k], n) for k, n in sorted(Counter(it["law"].get("kind", "other") for it in items)
                                                                .items(), key=lambda kv: -kv[1]) if k in kinds.KINDS],
        debated=sum(1 for it in items if it["said"])), encoding="utf-8")
    (out / "o-projektu.html").write_text(env.get_template("about.html").render(**common, stats=stats, root=""),
                                         encoding="utf-8")
    if domain:
        (out / "CNAME").write_text(domain + "\n", encoding="utf-8")
        base = f"https://{domain}/"
        pages = sorted(p.relative_to(out).as_posix() for p in out.rglob("*.html"))
        (out / "sitemap.xml").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + "".join(f"<url><loc>{base}{p}</loc></url>\n" for p in pages) + "</urlset>\n", encoding="utf-8")
        (out / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {base}sitemap.xml\n", encoding="utf-8")
    (out / ".nojekyll").write_text("", encoding="utf-8")
    return stats
