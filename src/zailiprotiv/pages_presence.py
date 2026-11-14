"""The ranking of MPs by presence at final votes ("Prisustvo"), beside the lists of MPs and groups.

Counted only where the Assembly's roll call lists the absent too (since autumn 2025; before that, and in the older
convocations, it listed only those present, so absence cannot be told), and only for an MP listed in twenty such
votes or more. The same count for everyone; why someone was absent the roll call does not say, and the page says so.
"""
from __future__ import annotations

from zailiprotiv.site import ORDINAL_NAME, collate

LEAST = 20  # final votes with the absent listed an MP must be on, to be ranked


def render(*, common, convs, env, finals, group_rows, median_presence, out, presence, rows_mp):
    conv = next((c for c, _ in convs if any(cc == c and n >= LEAST for (_, cc), (_, n) in presence.items())), None)
    if conv is None:  # no convocation has roll calls that list the absent
        return None
    counted = [f for f in finals.values() if f["conv"] == conv and f["final"]["counts"]["nije_prisutan"]]
    keys = {f["law"]["final_vote"] for f in counted}
    rows = []
    for r in rows_mp:
        got = presence.get((r["mp"].key, conv))
        if not got or got[1] < LEAST or conv not in r["by_conv"]:
            continue
        present, listed = got
        silent = sum(1 for k, how in r["mp"].votes.items() if k in keys and how == "nije_glasao")
        rows.append({"mp": r["mp"], "photo": r["photo"], "group": (r["by_conv"][conv]["groups"] or [""])[0],
                     "present": present, "listed": listed, "absent": listed - present, "silent": silent,
                     "share": present / listed})
    rows.sort(key=lambda x: (x["share"], -x["listed"], collate(x["mp"].name)))
    for i, x in enumerate(rows):  # the same share, the same place
        x["rank"] = rows[i - 1]["rank"] if i and round(rows[i - 1]["share"], 4) == round(x["share"], 4) else i + 1
    groups = sorted((g for g in group_rows.get(conv, []) if g.get("presence") and g["presence"][1] >= LEAST),
                    key=lambda g: (g["presence"][0] / g["presence"][1], collate(g["name"])))
    days = sorted(f["final"]["when"][:10] for f in counted)
    names = sorted({x["group"] for x in rows if x["group"]}, key=collate)
    (out / "prisustvo.html").write_text(env.get_template("presence.html").render(
        **common, rows=rows, groups=groups, votes=len(counted), first=days[0], last=days[-1], least=LEAST,
        median=median_presence.get(conv), conv=conv, conv_name=ORDINAL_NAME.get(conv, conv), group_names=names,
        root=""), encoding="utf-8")
    return conv
