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
    return laws, votes, bills


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


def build(data: Path, out: Path, domain: str | None = None) -> dict:
    laws_store, votes, bills = load(data)
    laws = laws_store["laws"]
    people = registry(votes)
    env = Environment(loader=FileSystemLoader(HERE / "templates"), autoescape=select_autoescape(["html"]),
                      trim_blocks=True, lstrip_blocks=True)
    env.filters.update(latin=latin, day=day, vote_label=lambda v: VOTE_LABEL.get(v, v))
    if out.exists():
        shutil.rmtree(out)
    (out / "zakon").mkdir(parents=True)
    (out / "poslanik").mkdir()
    shutil.copy(HERE / "static" / "style.css", out / "style.css")
    built = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    common = {"built": built, "fetched": laws_store.get("fetched", "")[:10], "vote_label": VOTE_LABEL,
              "VOTES": VOTES}

    # Laws, newest first; slugs unique.
    items, taken = [], Counter()
    for key, law in sorted(laws.items(), key=lambda kv: (kv[1].get("passed") or "", kv[1]["title"]), reverse=True):
        s = slug(law["title"])
        taken[s] += 1
        s = s if taken[s] == 1 else f"{s}-{taken[s]}"
        final = votes.get(law.get("final_vote") or "")
        summary = bills.get(law.get("bill_file", ""), {}).get("summary")
        items.append({"key": key, "slug": s, "law": law, "final": final, "summary": summary,
                      "kind": kinds.KINDS.get(law.get("kind", "other"), ""),
                      "areas": [kinds.AREAS[a] for a in law.get("areas", [])]})
    ranked = most_against(items, len(items))
    by_key = {it["key"]: it for it in items}
    for i, r in enumerate(ranked, 1):
        r["rank"] = i
        by_key[r["key"]].update(rank=i, share=r["share"])
    for it in items:
        law, final = it["law"], it["final"]
        bill = bills.get(law.get("bill_file", ""), {})
        it["urgent"] = "urgency" in bill.get("sections", {})
        it["days"] = days_between(law.get("submitted"), law.get("passed"))
        sections = bill.get("sections", {})
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
    (out / "zakoni.html").write_text(env.get_template("laws.html").render(
        **common, by_kind=by_kind, kind_order=kind_order, KINDS=kinds.KINDS, total=len(items), root=""),
        encoding="utf-8")

    # MPs: their final votes on laws.
    finals = {it["law"]["final_vote"]: it for it in items if it["law"].get("final_vote")}
    rows_mp = []
    for mp in sorted(people.values(), key=lambda m: collate(m.name)):
        record = [{"it": finals[k], "vote": how} for k, how in mp.votes.items() if k in finals]
        record.sort(key=lambda r: r["it"]["final"]["when"], reverse=True)
        tally = Counter(r["vote"] for r in record)
        rows_mp.append({"mp": mp, "tally": tally, "n": len(record)})
        (out / "poslanik" / f"{mp.slug}.html").write_text(env.get_template("mp.html").render(
            **common, mp=mp, record=record, tally=tally, root="../"), encoding="utf-8")
    (out / "poslanici.html").write_text(env.get_template("mps.html").render(
        **common, rows=rows_mp, root=""), encoding="utf-8")

    stats = {"laws": len(items), "linked": sum(1 for it in items if it["final"]), "votes": len(votes),
             "mps": len(people), "treaties": sum(1 for it in items if it["law"].get("kind") == "treaty"),
             "sittings": len({v["sitting"] for v in votes.values()})}
    (out / "index.html").write_text(env.get_template("index.html").render(
        **common, stats=stats, latest=items[:12], contested=most_against(items, 12), root=""), encoding="utf-8")
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
