"""Pages that list laws another way: by area, by sitting, by convocation.

Moved out of `site.build` (13 Nov 2026); it takes what it needs from the build as arguments.
"""
from __future__ import annotations

from zailiprotiv.site import (  # noqa: F401
    collate, defaultdict, most_against, sitting_page
)


def render(*, area_slug, common, conv_list, env, items_by_conv, key_votes, numbers, out, rows_mp):
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
    from zailiprotiv import pages_floor
    floor_by_sitting = getattr(pages_floor.render, "by_sitting", {})
    (out / "sednica").mkdir(exist_ok=True)
    for url, its in by_sitting.items():
        its.sort(key=lambda it: it["final"]["when"])
        first = its[0]
        name = sitting_page(url, first["final"]["sitting_title"])
        sitting_slug[url] = name
        (out / "sednica" / f"{name}.html").write_text(env.get_template("sitting.html").render(
            **common, title=first["final"]["sitting_title"], url=url, laws=its, conv_name=first["conv_name"],
            lead=max(its, key=lambda it: (it["final"]["counts"]["protiv"] or 0)), floor=floor_by_sitting.get(url),
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
    return by_area
