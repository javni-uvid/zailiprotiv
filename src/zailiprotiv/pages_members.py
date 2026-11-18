"""The MPs of the newest convocation before its first roll call (18 Nov 2026; members.py reads them).

`poslanici-<N>.html` lists them all, in the site's order (surname, by the Serbian alphabet), each with the party that
put them forward, place and year of birth as the Assembly gives them, and whether they were MPs in an earlier
convocation the site has (a name of the roll calls whose year of birth, in the Assembly's archive, agrees). Those link
to their page, which says they sit in the new convocation; a new MP gets a page of their own, with what the list says
and nothing more until there is a vote or a speech. With the parliamentary groups read (18 Nov 2026) the list goes
group by group, the largest first (then by name, as everywhere on the site), the MPs in no group last.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from zailiprotiv import members as members_
from zailiprotiv.config import CONVOCATIONS

PAGE = "poslanici-{conv}.html"


def load(root: Path) -> tuple[str, dict] | tuple[None, None]:
    """The newest convocation with a list of members, and the list."""
    found = sorted(((p.parent.name, p) for p in root.glob("*/members.json") if p.parent.name.isdigit()),
                   key=lambda c: int(c[0]))
    if not found:
        return None, None
    conv, path = found[-1]
    return conv, json.loads(path.read_text(encoding="utf-8"))


def match(conv: str, listed: dict, people: dict, years_listed: dict, *, title_case, slug) -> list[dict]:
    """Each member as the pages show them: {"name", "slug", "key", "party", "place", "year", "mp" (the site's MP, if
    the same person), "new"}. A new member's name is written as the roll calls' are, surname first and without
    titles; one whose address another MP has gets the year of birth after the name, as namesakes do."""
    known = members_.years(years_listed, conv)
    taken = {mp.slug for mp in people.values()}
    out = []
    titles = members_.mps.TITLES | {t for t in ("prof", "dr", "mr", "doc", "prim")}
    for m in listed["members"]:
        k = members_.key(m["name"], conv)
        mp = people.get(k)
        if mp and not members_.same_person(k, int(m["year"]), known):
            mp = None
        if mp:
            out.append({**m, "key": k, "mp": mp, "name": mp.name, "slug": mp.slug, "new": False})
            continue
        words = [w for w in title_case(m["name"]).split() if w.lower().strip(".") not in titles]
        name = " ".join(words)
        s = slug(name, 60)
        if s in taken:
            name, s = f"{name} ({m['year']})", slug(f"{name} {m['year']}", 60)
        taken.add(s)
        out.append({**m, "key": k, "mp": None, "name": name, "slug": s, "new": True})
    return out


def party(p: str) -> str:
    """The party as the list writes it; "-" (put forward by no party) as words."""
    return "" if p.strip() in ("", "-", "–") else p.strip()


def since(conv: str) -> str:
    return CONVOCATIONS.get(conv, {}).get("from", "")


def render(*, env, common: dict, out: Path, conv: str, listed: dict, rows: list[dict], convs_of: dict,
           photo_of: dict, conv_name: str) -> None:
    """The list page and a page for each new member."""
    for r in rows:
        r["party_"] = party(r["party"])
        r["before"] = [c for c in convs_of.get(r["slug"], []) if c != conv] if not r["new"] else []
        r["photo"] = photo_of.get(r["key"], "") or (photo_of.get(r["mp"].key, "") if r["mp"] else "")
    parties = {}
    for r in rows:
        parties[r["party_"] or "bez stranke"] = parties.get(r["party_"] or "bez stranke", 0) + 1
    sections = by_group(rows)
    (out / PAGE.format(conv=conv)).write_text(env.get_template("members.html").render(
        **common, rows=rows, conv=conv, conv_name=conv_name, since=since(conv), listed_on=listed.get("fetched", ""),
        source=listed.get("source", ""), parties=sorted(parties.items(), key=lambda kv: (-kv[1], kv[0])),
        sections=sections, grouped=any("group" in r for r in rows),
        new=sum(1 for r in rows if r["new"]), root=""), encoding="utf-8")
    (out / "poslanik").mkdir(exist_ok=True)
    for r in rows:
        if r["new"]:
            (out / "poslanik" / f"{r['slug']}.html").write_text(env.get_template("mp_new.html").render(
                **common, m=r, conv=conv, conv_name=conv_name, since=since(conv), source=listed.get("source", ""),
                list_page=PAGE.format(conv=conv), root="../"), encoding="utf-8")


def by_group(rows: list[dict]) -> list[dict]:
    """The members group by group: the groups by seats, then by name (the site's neutral order); the MPs in no group,
    then those no group's page lists, last. Without groups read, one section of all."""
    from zailiprotiv.site import collate
    from zailiprotiv.translit import latin
    rows = sorted(rows, key=lambda r: collate(r["name"]))  # by surname, in the Serbian Latin alphabet
    if not any("group" in r for r in rows):
        return [{"name": "", "rows": rows}]
    named: dict[str, list] = {}
    for r in rows:
        named.setdefault(r.get("group", None) if "group" in r else None, []).append(r)
    order = sorted((g for g in named if g), key=lambda g: (-len(named[g]), collate(latin(g))))
    out = [{"name": latin(g), "rows": named[g]} for g in order]
    if "" in named:
        out.append({"name": "Van poslaničkih grupa", "rows": named[""], "none": True})
    if None in named:
        out.append({"name": "Grupa nije navedena", "rows": named[None], "none": True})
    return out


def now_of(rows: list[dict]) -> dict:
    """The site's MPs who sit in the new convocation, by key: what their own page says of it."""
    return {r["mp"].key: r for r in rows if r["mp"]}


__all__ = ["PAGE", "load", "match", "render", "now_of", "party", "re"]
