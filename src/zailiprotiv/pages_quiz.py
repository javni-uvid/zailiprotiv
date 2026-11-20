"""The page "Glasaj i ti": the laws visitors vote on, with every group's and MP's votes on them.

Moved out of `site.build` (13 Nov 2026); it takes what it needs from the build as arguments.
"""
from __future__ import annotations

from collections import defaultdict

from zailiprotiv import jsonfile, kinds
from zailiprotiv.site import (  # noqa: F401
    HERE, ORDINAL_NAME, json, latin, most_against, shutil, slug
)

THEME_LEAST = 5  # an area gets its own quiz when this many of its laws had votes against
# A theme's name as people say it: the points of Article 97 are long lists. The last point ("other matters of
# interest to the Republic") is no theme and gets no quiz.
THEMES = {1: "Bezbednost i međunarodni odnosi", 2: "Prava građana i sudovi", 3: "Lokalna samouprava",
          4: "Odbrana", 5: "Granice i stranci", 6: "Privreda i porezi", 7: "Svojina i ugovori",
          8: "Rad i zapošljavanje", 9: "Životna sredina", 10: "Zdravstvo, obrazovanje, kultura i mediji",
          11: "Kontrola javnog novca", 12: "Razvoj, nauka i tehnologija", 13: "Saobraćaj", 14: "Praznici i odlikovanja",
          15: "Budžet i finansije", 16: "Državni organi"}


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
    picked = jsonfile.load(root / "quiz.json", {})
    if picked.get("convocation") == active:
        by_file = {it["law"].get("bill_file"): it for it in items_by_conv[active] if it["final"]}
        hand = [{**by_file[p["bill_file"]], "opis": p["opis"]} for p in picked["laws"] if p["bill_file"] in by_file]
        if len(hand) >= 5:
            quiz_laws, chosen_by_hand = hand, True
    # After the vote: one thing said in the debate by someone who voted for and one by someone who voted against.
    for it in quiz_laws:
        it["heard"] = [next((q for q in it["quotes"] if q["side"] == side), None) for side in ("za", "protiv")]
        it["heard"] = [q for q in it["heard"] if q]
    letter = {"za": "z", "protiv": "p", "uzdrzan": "u"}

    def data(laws):  # what the page's script compares the visitor's answers with
        return {"laws": [{"s": it["slug"]} for it in laws],
            "groups": [{"n": g["name"], "s": g["slug"], "m": g["members"],
                        "v": "".join(letter.get(line.get((it["law"]["final_vote"], g["name"])), "-") for it in laws)}
                       for g in group_rows.get(active, [])]}
    quiz = data(quiz_laws)
    settings = jsonfile.load(root / "settings.json", {})
    # The laws visitors' votes are counted for: the counter (worker/) accepts no others.
    (out / "glasaj.json").write_text(json.dumps({"laws": [it["slug"] for it in quiz_laws]}), encoding="utf-8")
    shutil.copy(HERE / "static" / "glasaj.js", out / "glasaj.js")
    # The quiz has its own page; "Glasaj i ti" (glasaj.html, pages_ballot) leads to it and holds the visitor's ballot.
    (out / "kviz").mkdir(exist_ok=True)
    (out / "kviz" / "podelili-salu.html").write_text(env.get_template("quiz.html").render(
        **common, laws=quiz_laws, chosen_by_hand=chosen_by_hand, of_conv=None if active == current else ORDINAL_NAME.get(active, active), votes_api=settings.get("votes_api", ""), quiz=json.dumps(quiz, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"),
        root="../"), encoding="utf-8")
    # A quiz per area of the convocation (the point of Article 97 the bill names): its laws with votes against, the
    # most divided first, ten at most, by the same rule as the main quiz; treaties left out.
    by_area = defaultdict(list)
    for it in items_by_conv[active]:
        if it["final"] and it["gist"] and it["law"].get("kind") != "treaty":
            for a in it.get("areas") or []:
                by_area[a].append(it)
    themes = []
    for a, its in by_area.items():
        laws = []
        for r in most_against(its, len(its)):
            it = by_key_all[r["key"]]
            if len(laws) < 10 and not (it["aka"] and any(it["aka"][0] == (q["aka"] or [""])[0] for q in laws)):
                laws.append(it)
        if len(laws) < THEME_LEAST:
            continue
        laws.sort(key=lambda it: it["final"]["when"], reverse=True)
        for it in laws:
            it["heard"] = [q for q in (next((q for q in it["quotes"] if q["side"] == side), None) for side in ("za", "protiv")) if q]
        point = next((k for k, v in kinds.AREAS.items() if v == a), None)
        if point not in THEMES:
            continue
        theme = {"name": THEMES[point], "slug": slug(THEMES[point]), "area": slug(latin(a))[:80], "n": len(laws), "of": len(its)}
        (out / "kviz" / f"{theme['slug']}.html").write_text(env.get_template("quiz.html").render(
            **common, laws=laws, theme=theme, chosen_by_hand=False, of_conv=None if active == current else ORDINAL_NAME.get(active, active),
            votes_api=settings.get("votes_api", ""), quiz=json.dumps(data(laws), ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"),
            root="../"), encoding="utf-8")
        themes.append(theme)
    render.themes = sorted(themes, key=lambda t: (-t["of"], t["name"]))  # for "Glasaj i ti" and the areas' pages
    env.globals["quiz_themes"] = {t["area"]: t for t in render.themes}  # by the area page's address
    render.laws = quiz_laws  # for the home page's band
    render.by_hand = chosen_by_hand  # the quiz's name on "Glasaj i ti" says how its laws were picked
    return active
