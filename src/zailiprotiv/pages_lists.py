"""Pages that list laws another way: by area, by sitting, by convocation.

Moved out of `site.build` (13 Nov 2026); it takes what it needs from the build as arguments.
"""
from __future__ import annotations

import json
from pathlib import Path

from zailiprotiv.pages_mikrofon import label
from zailiprotiv.site import (  # noqa: F401
    ORDINAL_NAME, given_first, collate, defaultdict, most_against, sitting_page
)


ROMAN = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]


def recorded(dates, recordings, latin):
    """The recordings of a sitting's days: [(day, [{"title", "parts": [{"n", "url"}]}])], a day's entries grouped by
    the archive's words for them (one day can hold the sitting and MPs' questions)."""
    import re
    rows = []
    for d in dates:
        groups = {}
        for p in recordings.get(d) or []:
            title = re.sub(r"\s+(Народне скупштине Републике Србије|НСРС)\b.*$", "", p["title"]).strip()
            groups.setdefault(latin(title), []).append({"n": ROMAN[p["part"]] if p["part"] < len(ROMAN) else str(p["part"]),
                                                        "url": p["url"]})
        if groups:
            rows.append((d, [{"title": t, "parts": ps} for t, ps in groups.items()]))
    return rows


def own_days(listed, days, today=None) -> dict[str, list[dict]]:
    """Each begun sitting's days read from the recording (`pages_govornici.load`), by the Assembly's listing (the latest
    first; a page that gives no day counts as begun and as the earliest): from its start until the next one's."""
    from datetime import date
    today = today or date.today().isoformat()
    begun = [s for s in listed if (s.get("starts") or "")[:10] <= today]
    out = {}
    for s in begun:
        start = (s.get("starts") or "")[:10]
        until = min((x["starts"][:10] for x in begun if (x.get("starts") or "") > (s.get("starts") or "")), default="9999")
        out[s["url"]] = [d for d in days if start <= d["dan"] < until]
    return out


def floor_card(own, *, root, conv, facts=None, colours=None) -> dict:
    """A sitting's days and who spoke, for its card (28 Nov 2026): each day (the latest first) with its time at the
    lectern, its share of the longest day's ("width"), its time by list, its three longest speakers and the day
    summary's title; and over the whole sitting its five longest speakers, its time by list and how many spoke. Lists
    with a colour of their own on the live page (`LIST_COLOURS`) keep it; the rest are one part, "ostali"."""
    from zailiprotiv import pages_govornici as gv
    facts, colours = facts or {}, colours or {}

    def split(secs: dict) -> list[dict]:
        total = sum(secs.values()) or 1
        merged: dict[str, int] = {}
        for n, x in secs.items():
            k = n if n in colours else ""
            merged[k] = merged.get(k, 0) + x
        rows = sorted(((n, x) for n, x in merged.items() if n and x), key=lambda kv: -kv[1]) + [("", merged.get("", 0))]
        return [{"name": n or "ostali", "cls": colours.get(n, "c-mn"), "pct": round(100 * x / total, 1), "time": gv.dur(x)}
                for n, x in rows if x]

    def face(name, t, sec):
        foto = str((facts.get(t.get("adresa", "")) or {}).get("foto") or "")
        return {"name": given_first(name), "slug": t.get("adresa", ""), "sec": sec, "time": gv.dur(sec),
                "foto": foto if foto.replace(".", "").replace("-", "").isalnum() else "",
                "initials": "".join(w[:1] for w in given_first(name).split()[:2]),
                "cls": colours.get(t.get("uloga") or t.get("grupa") or "", "")}

    side = lambda t: t.get("uloga") or t.get("grupa") or ""  # noqa: E731
    out_days, whole = [], {}
    for d in sorted(own, key=lambda d: d["dan"], reverse=True):
        sm = gv.day_summary(root, str(conv), d["dan"]) or {}
        secs, first = {}, {}
        for t in d["govori"]:
            secs[t["ime"]] = secs.get(t["ime"], 0) + max(0, t["do"] - t["od"])
            first.setdefault(t["ime"], t)
        by_list: dict[str, int] = {}
        for n, x in secs.items():
            whole.setdefault(n, {"sec": 0, "t": first[n]})["sec"] += x
            by_list[side(first[n])] = by_list.get(side(first[n]), 0) + x
        out_days.append({"day": d["dan"], "when": gv.day_name(d["dan"]), "sec": sum(secs.values()),
                         "time": gv.dur(sum(secs.values())), "people": len(secs), "split": split(by_list),
                         "top": [face(n, first[n], secs[n]) for n in sorted(secs, key=lambda n: (-secs[n], n))[:3]],
                         "title": sm.get("naslov") or ""})
    most = max((x["sec"] for x in out_days), default=0) or 1
    for x in out_days:
        x["width"] = round(100 * x["sec"] / most)
    by_list = {}
    for w in whole.values():
        by_list[side(w["t"])] = by_list.get(side(w["t"]), 0) + w["sec"]
    sec = sum(x["sec"] for x in out_days)
    return {"days": out_days, "sec": sec, "time": gv.dur(sec) if sec else "", "people": len(whole), "split": split(by_list),
            "top": [face(n, whole[n]["t"], whole[n]["sec"]) for n in sorted(whole, key=lambda n: (-whole[n]["sec"], n))[:5]]}


def summary_of(root, conv, slug) -> dict | None:
    """A sitting's own summary, written from its days' (tools/sazetak_sednice.py), where there is one."""
    if not root:
        return None
    f = Path(root) / str(conv) / "sazetak" / f"sednica-{slug}.json"
    return json.loads(f.read_text(encoding="utf-8")) if slug and f.exists() else None


def lead(*, listed, days, sittings, root, conv, latin, today=None, facts=None, colours=None):
    """The sitting the sittings page opens on (28 Nov 2026): of the newest convocation's sittings as the Assembly lists
    them (`pages_mikrofon.sittings`, the latest first), the latest begun; else the newest of the list with roll calls.
    With its short name, its days read from the recording and who spoke (`floor_card`), its own summary where there is
    one, and, when it has roll calls, its place in the list ("n", "against", "za", "others", "slug", "lead_law"). The
    same rule whatever the convocation; None when there is nothing to show."""
    from datetime import date
    today = today or date.today().isoformat()
    begun = [s for s in listed if (s.get("starts") or "")[:10] <= today]  # a page that gives no day: begun, it is listed
    by_url = {s["url"]: s for s in sittings if s.get("url")}
    keys = ("slug", "n", "against", "za", "others", "lead_law")
    if begun:
        s = begun[0]
        row = by_url.get(s["url"], {})
        out = {"title": s["title"], "url": s["url"], "agenda": s.get("agenda") or [], "conv": str(conv),
               "starts": (s.get("starts") or "")[:10], **{k: row.get(k) for k in keys}}
        own = own_days(listed, days, today).get(s["url"], [])
    elif sittings:
        row = sittings[0]
        out = {"title": latin(row["title"]), "url": row.get("url", ""), "agenda": [], "conv": str(row["conv"]),
               "starts": row["day"], **{k: row.get(k) for k in keys}}
        own = []
    else:
        return None
    out["short"], out["conv_name"] = label(out["title"]), ORDINAL_NAME.get(out["conv"], out["conv"])
    out.update(floor_card(own, root=root, conv=out["conv"], facts=facts, colours=colours))
    out["summary"] = summary_of(root, out["conv"], out.get("slug"))
    return out


def render(*, area_slug, common, conv_list, env, items_by_conv, key_votes, numbers, out, rows_mp, recordings=None,
           floor_by_sitting=None, quiz_themes=None, waiting=(), others_by_sitting=None, lead_from=None):
    # A page per area (the point of Article 97), every convocation, newest first.
    by_area = defaultdict(list)
    for its in items_by_conv.values():
        for it in its:
            for a in it.get("areas") or []:
                by_area[a].append(it)
    (out / "oblast").mkdir(exist_ok=True)
    # Every area of Article 97 has its page, also one with no law yet (27 Nov 2026, following an area by mail: each
    # of the 17 can be followed).
    from zailiprotiv import kinds
    for a in kinds.AREAS.values():
        by_area.setdefault(a, [])
    for a, its in by_area.items():
        its.sort(key=lambda it: it["law"].get("passed") or "", reverse=True)
        (out / "oblast" / f"{area_slug(a)}.html").write_text(env.get_template("area.html").render(
            **common, area=a, laws=its, quiz_themes=quiz_themes, root="../",
            waiting_here=[r for r in waiting if a in r.get("area_names", [])]), encoding="utf-8")
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
    floor_by_sitting = floor_by_sitting or {}
    root_ = (lead_from or {}).get("root")
    (out / "sednica").mkdir(exist_ok=True)
    for url, its in by_sitting.items():
        its.sort(key=lambda it: it["final"]["when"])
        first = its[0]
        name = sitting_page(url, first["final"]["sitting_title"])
        sitting_slug[url] = name
        floor = floor_by_sitting.get(url)
        days = sorted(set((floor or {}).get("dates") or []) | {it["final"]["when"][:10] for it in its})
        others = (others_by_sitting or {}).get(url, [])
        days = sorted(set(days) | {o["when"][:10] for o in others if o["when"]})
        (out / "sednica" / f"{name}.html").write_text(env.get_template("sitting.html").render(
            **common, title=first["final"]["sitting_title"], url=url, laws=its, conv_name=first["conv_name"],
            lead=max(its, key=lambda it: (it["final"]["counts"]["protiv"] or 0)), floor=floor, others=others,
            recordings=recorded(days, recordings or {}, env.filters["latin"]),
            summary=summary_of(root_, first["conv"], name),
            first=its[0]["final"]["when"][:10], last=its[-1]["final"]["when"][:10], root="../"), encoding="utf-8")
    sittings_list = sorted(({"slug": sitting_slug[u], "url": u, "title": its[0]["final"]["sitting_title"], "n": len(its),
                             "day": its[0]["final"]["when"][:10], "conv": its[0]["conv"], "conv_name": its[0]["conv_name"],
                             "against": sum((it["final"]["counts"]["protiv"] or 0) for it in its),
                             "za": sum((it["final"]["counts"]["za"] or 0) for it in its),
                             "lead_law": (lambda w: {"slug": w["slug"], "short": w["law"]["short"], "counts": w["final"]["counts"]})(
                                 max(its, key=lambda it: (it["final"]["counts"]["protiv"] or 0))),
                             "others": len((others_by_sitting or {}).get(u, []))}
                            for u, its in by_sitting.items()), key=lambda x: x["day"], reverse=True)
    # A sitting with roll calls but no adopted law (other_votes.py, 27 Nov 2026) gets a page of the same kind, with
    # them alone, and its place in the list.
    for url, others in (others_by_sitting or {}).items():
        if url in by_sitting or not others:
            continue
        first = others[0]
        name = sitting_page(url, first["sitting_title"])
        floor = floor_by_sitting.get(url)
        days = sorted(set((floor or {}).get("dates") or []) | {o["when"][:10] for o in others if o["when"]})
        conv_name = ORDINAL_NAME.get(first["conv"], first["conv"])
        (out / "sednica" / f"{name}.html").write_text(env.get_template("sitting.html").render(
            **common, title=first["sitting_title"], url=url, laws=[], conv_name=conv_name, lead=None, floor=floor,
            others=others, recordings=recorded(days, recordings or {}, env.filters["latin"]),
            summary=summary_of(root_, first["conv"], name), first=others[0]["when"][:10], last=others[-1]["when"][:10], root="../"), encoding="utf-8")
        sittings_list.append({"slug": name, "url": url, "title": first["sitting_title"], "n": 0, "day": others[0]["when"][:10],
                              "conv": first["conv"], "conv_name": conv_name, "against": 0, "others": len(others)})
    sittings_list.sort(key=lambda x: x["day"], reverse=True)
    latin = env.filters["latin"]
    for x in sittings_list:
        x["short"], x["year"] = label(latin(x["title"])), x["day"][:4]
    # The sittings page: the latest sitting's card on top, and any other sitting with days read from the recording opens
    # them the same way under its row (28 Nov 2026).
    from zailiprotiv import pages_mikrofon
    speakers = out / pages_mikrofon.SPEAKERS_FILE
    look = {"facts": json.loads(speakers.read_text(encoding="utf-8")) if speakers.exists() else {},
            "colours": pages_mikrofon._uzivo()[0].LIST_COLOURS}
    top = lead(**lead_from, sittings=sittings_list, latin=latin, **look) if lead_from else None
    global LEAD
    LEAD = top  # DRAFT: the home page's drafts take the same card
    if lead_from:
        for url, own in own_days(lead_from["listed"], lead_from["days"]).items():
            row = next((x for x in sittings_list if x["url"] == url), None)
            if own and row and not (top and top["url"] == url):
                row["floor"] = floor_card(own, root=lead_from["root"], conv=lead_from["conv"], **look)
    by_conv = [(cv, [x for x in sittings_list if x["conv"] == cv["n"]]) for cv in conv_list]
    from zailiprotiv import pages_govornici
    from zailiprotiv import pages_govornici
    (out / "sednice.html").write_text(env.get_template("sittings.html").render(
        **common, by_conv=by_conv, lead=top, card_css=pages_govornici.card_css(), root=""), encoding="utf-8")
    # A page per convocation: its figures, key votes, groups and sittings, and the way to its laws and MPs.
    for n in numbers:
        c = n["conv"]["n"]
        (out / f"saziv-{c}.html").write_text(env.get_template("convocation.html").render(
            **common, n=n, conv=c, cv=n["conv"], key_votes=key_votes.get(c, []),
            against=most_against(items_by_conv[c], 5), sittings=[x for x in sittings_list if x["conv"] == c and x["n"]],
            mps=sum(1 for r in rows_mp if c in r["by_conv"]),
            first=min((it["law"].get("passed") or "9999" for it in items_by_conv[c]), default=""),
            last=max((it["law"].get("passed") or "" for it in items_by_conv[c]), default=""), root=""), encoding="utf-8")
    return by_area
