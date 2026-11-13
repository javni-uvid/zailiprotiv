"""The page "Glasaj i ti": the laws visitors vote on, with every group's and MP's votes on them.

Moved out of `site.build` (13 Nov 2026); it takes what it needs from the build as arguments.
"""
from __future__ import annotations

from zailiprotiv.site import (  # noqa: F401
    HERE, ORDINAL_NAME, json, latin, most_against, shutil
)


def render(*, by_key_all, common, profiles=None, convs, current, env, group_rows, items_by_conv, key_votes, line, out, root, rows_mp):
    # A new convocation starts with nothing voted. Until it has passed five laws, the home page and "Glasaj i ti"
    # show the last convocation that has, and say which.
    active = next((c for c, _ in convs if sum(1 for it in items_by_conv[c] if it["final"]) >= 5), current)
    # "Glasaj i ti": the visitor votes on the current convocation's key laws; the page's own script compares the
    # answers with every group's line and every MP's votes. Nothing leaves the browser.
    quiz_laws = list(key_votes[active])
    for r in most_against(items_by_conv[active], len(items_by_conv[active])):
        it = by_key_all[r["key"]]
        if len(quiz_laws) >= 10:
            break
        if it not in quiz_laws and it["law"].get("kind") != "treaty" and not (it["aka"] and any(it["aka"][0] == (q["aka"] or [""])[0] for q in quiz_laws)):
            quiz_laws.append(it)
    quiz_laws = sorted((it for it in quiz_laws if it["gist"]), key=lambda it: it["final"]["when"], reverse=True)
    # The maintainer's choice (data/quiz.json, 13 Nov 2026) replaces the rule for the convocation it names: laws a
    # visitor can have a view on, in the order given, each with a short plain description written from its summary.
    chosen_by_hand = False
    picked = json.loads((root / "quiz.json").read_text(encoding="utf-8")) if (root / "quiz.json").exists() else {}
    if picked.get("convocation") == active:
        by_file = {it["law"].get("bill_file"): it for it in items_by_conv[active] if it["final"]}
        hand = [{**by_file[p["bill_file"]], "opis": p["opis"]} for p in picked["laws"] if p["bill_file"] in by_file]
        if len(hand) >= 5:
            quiz_laws, chosen_by_hand = hand, True
    # After the vote: one thing said in the debate by someone who voted for and one by someone who voted against.
    for it in quiz_laws:
        it["heard"] = [next((q for q in it["quotes"] if q["side"] == side), None) for side in ("za", "protiv")]
        it["heard"] = [q for q in it["heard"] if q]
    # The shortest verbatim quote of each MP's overview, shown with the MP whose votes are closest to the visitor's.
    def quote(mp):
        points = ((profiles or {}).get(mp.key) or {}).get("points") or []
        qs = sorted((t["citat"]["tekst"] for t in points if t.get("citat")), key=len)
        return latin(qs[0]) if qs and len(qs[0].split()) <= 45 else ""
    letter = {"za": "z", "protiv": "p", "uzdrzan": "u"}
    quiz = {"laws": [{"s": it["slug"]} for it in quiz_laws],
            "groups": [{"n": g["name"], "s": g["slug"], "m": g["members"],
                        "v": "".join(letter.get(line.get((it["law"]["final_vote"], g["name"])), "-") for it in quiz_laws)}
                       for g in group_rows.get(active, [])],
            "mps": [{"n": r["mp"].name, "s": r["mp"].slug, "g": (r["by_conv"][active]["groups"] or [""])[0],
                     "v": "".join(letter.get(r["mp"].votes.get(it["law"]["final_vote"]), "-") for it in quiz_laws),
                     **({"q": q} if (q := quote(r["mp"])) else {})}
                    for r in rows_mp if active in r["by_conv"]]}
    settings = json.loads((root / "settings.json").read_text(encoding="utf-8")) if (root / "settings.json").exists() else {}
    # The laws visitors' votes are counted for: the counter (worker/) accepts no others.
    (out / "glasaj.json").write_text(json.dumps({"laws": [it["slug"] for it in quiz_laws]}), encoding="utf-8")
    shutil.copy(HERE / "static" / "glasaj.js", out / "glasaj.js")
    (out / "glasaj.html").write_text(env.get_template("quiz.html").render(
        **common, laws=quiz_laws, chosen_by_hand=chosen_by_hand, of_conv=None if active == current else ORDINAL_NAME.get(active, active), votes_api=settings.get("votes_api", ""), quiz=json.dumps(quiz, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"),
        root=""), encoding="utf-8")
    return active
