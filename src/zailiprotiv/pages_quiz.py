"""The page "Glasaj i ti": the laws visitors vote on, with every group's and MP's votes on them.

Moved out of `site.build` (13 Nov 2026); it takes what it needs from the build as arguments.
"""
from __future__ import annotations

from zailiprotiv.site import (  # noqa: F401
    HERE, ORDINAL_NAME, json, most_against, shutil
)


def render(*, by_key_all, common, convs, current, env, group_rows, items_by_conv, key_votes, line, out, root, rows_mp):
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
    letter = {"za": "z", "protiv": "p", "uzdrzan": "u"}
    quiz = {"laws": [{"s": it["slug"]} for it in quiz_laws],
            "groups": [{"n": g["name"], "s": g["slug"], "m": g["members"],
                        "v": "".join(letter.get(line.get((it["law"]["final_vote"], g["name"])), "-") for it in quiz_laws)}
                       for g in group_rows.get(active, [])],
            "mps": [{"n": r["mp"].name, "s": r["mp"].slug, "g": (r["by_conv"][active]["groups"] or [""])[0],
                     "v": "".join(letter.get(r["mp"].votes.get(it["law"]["final_vote"]), "-") for it in quiz_laws)}
                    for r in rows_mp if active in r["by_conv"]]}
    settings = json.loads((root / "settings.json").read_text(encoding="utf-8")) if (root / "settings.json").exists() else {}
    # The laws visitors' votes are counted for: the counter (worker/) accepts no others.
    (out / "glasaj.json").write_text(json.dumps({"laws": [it["slug"] for it in quiz_laws]}), encoding="utf-8")
    shutil.copy(HERE / "static" / "glasaj.js", out / "glasaj.js")
    (out / "glasaj.html").write_text(env.get_template("quiz.html").render(
        **common, laws=quiz_laws, of_conv=None if active == current else ORDINAL_NAME.get(active, active), votes_api=settings.get("votes_api", ""), quiz=json.dumps(quiz, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"),
        root=""), encoding="utf-8")
    return active
