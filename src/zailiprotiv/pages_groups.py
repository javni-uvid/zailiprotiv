"""A page per parliamentary group and convocation, the list of groups, and the Assembly in numbers.

Moved out of `site.build` (13 Nov 2026); it takes what it needs from the build as arguments.
"""
from __future__ import annotations

from zailiprotiv.site import (  # noqa: F401
    Counter, ORDINAL_NAME, VOTES, collate, defaultdict, leaning, mps
)


def render(*, common, conv_list, env, finals, former, group_slug, items_by_conv, key_finals, lines_of, out, rows_mp, seat):
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
                "former": former.get((c, g), []),
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
    return group_rows, numbers
