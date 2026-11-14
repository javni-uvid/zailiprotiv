"""The page "Glasaj i ti" with the visitor's own ballot ("Moj listić"), and what its script reads.

The ballot lives in the visitor's browser: what they voted on a law's page, a bill's page or in a quiz. To show it
(the Assembly's result beside each vote, who in the chamber voted the same), the page's script reads small files
written here: where each law is (listic/zakoni.json), each convocation's final votes as a letter per MP
(listic/<N>.json), and the bills (listic/predlozi.json). Nothing about the visitor is sent to read them.
"""
from __future__ import annotations

from zailiprotiv.site import ORDINAL_NAME, json, latin

LETTER = {"za": "z", "protiv": "p", "uzdrzan": "u"}


def below(values: list[float]) -> dict[float, float]:
    """For each value, the share of the values that are smaller: its place among them, 0 to 1."""
    ordered = sorted(values)
    first = {}
    for i, v in enumerate(ordered):
        first.setdefault(v, i)
    return {v: round(first[v] / max(1, len(ordered) - 1), 2) for v in first}


def render(*, common, convs, current, env, floor_of, gone, items_by_conv, out, quiz_laws, rows_mp, waiting):
    folder = out / "listic"
    folder.mkdir(exist_ok=True)
    where = {}
    for conv, _ in convs:
        items = [it for it in items_by_conv[conv] if it["final"]]
        if not items:
            continue
        mps = [r for r in rows_mp if conv in r["by_conv"]]
        # What makes a law stand out on a ballot, each as its place among the convocation's laws: how the chamber
        # split, the sparks in its debate (the chair's measures and exchanges of replies), and its amendments.
        raw = {}
        for it in items:
            c = it["final"]["counts"]
            sparks = floor_of.get(it["key"], [])
            raw[it["slug"]] = (it.get("share") or 0, sum(1 for e in sparks if e["type"] == "mera"),
                               sum(1 for e in sparks if e["type"] == "razmena"), (it["debate"] or {}).get("amendments") or 0)
        place = [below([v[0] for v in raw.values()]), below([v[1] + v[2] for v in raw.values()]), below([v[3] for v in raw.values()])]
        laws = {}
        for it in items:
            c, r = it["final"]["counts"], raw[it["slug"]]
            laws[it["slug"]] = {
                "t": it["law"]["short"], "d": it["law"].get("passed") or it["final"]["when"][:10],
                "k": [c.get("za", 0), c.get("protiv", 0), sum(c.values()) - c.get("za", 0) - c.get("protiv", 0)],
                "v": "".join(LETTER.get(m["mp"].votes.get(it["law"]["final_vote"]), "-") for m in mps),
                "g": [r[1], r[2], r[3]], "r": [place[0][r[0]], place[1][r[1] + r[2]], place[2][r[3]]]}
            where[it["slug"]] = conv
        (folder / f"{conv}.json").write_text(json.dumps({
            "c": conv, "n": ORDINAL_NAME.get(conv, conv),
            "mps": [[m["mp"].slug, m["mp"].name, (m["by_conv"][conv]["groups"] or [""])[0]] for m in mps],
            "laws": laws}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (folder / "zakoni.json").write_text(json.dumps(where, separators=(",", ":")), encoding="utf-8")
    (folder / "predlozi.json").write_text(json.dumps(
        {b["slug"]: {"t": latin(b["title"]), "d": b["submitted"] or "", **({"z": b["law"]["slug"]} if b.get("law") else {}),
                     **({} if b in waiting else {"x": 1})} for b in waiting + gone},
        ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    # The bill shown first: the newest that has a summary to read before voting, and failing that the newest.
    # A treaty's ratification gives way to a law, as few visitors have a view on one.
    bill = next((b for b in waiting if b.get("gist") and b.get("kind_key") != "treaty"),
                next((b for b in waiting if b.get("gist")), waiting[0] if waiting else None))
    (out / "glasaj.html").write_text(env.get_template("ballot.html").render(
        **common, quiz_laws=quiz_laws, bill=bill, waiting=len(waiting), root=""), encoding="utf-8")
