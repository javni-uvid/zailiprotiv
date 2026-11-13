"""Atom feeds: new laws, bills in procedure, each area, each MP.

Moved out of `site.build` (13 Nov 2026); it takes what it needs from the build as arguments.
"""
from __future__ import annotations

from zailiprotiv.site import (  # noqa: F401
    latin, write_feed
)


def write(*, area_slug, by_area, domain, feeds_mp, items_by_conv, out, waiting):
    # Atom feeds: the newest laws, and each MP's newest final votes (static files, nothing from other servers).
    site = f"https://{domain}/" if domain else ""
    newest = sorted((it for its in items_by_conv.values() for it in its), key=lambda it: it["law"].get("passed") or "",
                    reverse=True)[:50]
    word = {"za": "za", "protiv": "protiv", "uzdrzan": "uzdržan", "nije_glasao": "nije glasao", "nije_prisutan": "nije prisutan"}

    def entry(it, title, summary):
        c = (it.get("final") or {}).get("counts") or {}
        tally = f"{c.get('za', 0)} za, {c.get('protiv', 0)} protiv. " if c else ""
        return {"title": title, "link": f"{site}zakon/{it['slug']}.html", "id": f"{site}zakon/{it['slug']}.html",
                "updated": (it["law"].get("passed") or "2000-01-01") + "T00:00:00Z", "summary": tally + summary}

    write_feed(out / "zakoni.xml", "Za ili Protiv: novi zakoni", f"{site}zakoni.xml", f"{site}index.html",
               [entry(it, it["law"]["short"], latin(it.get("gist") or "")) for it in newest])
    write_feed(out / "u-proceduri.xml", "Za ili Protiv: novi predlozi zakona", f"{site}u-proceduri.xml", f"{site}u-proceduri.html",
               [{"title": latin(r["title"]), "link": r["pdf"], "id": r["pdf"],
                 "updated": (r["submitted"] or "2000-01-01") + "T00:00:00Z", "summary": "Predlagač: " + latin(r["proposer"])}
                for r in waiting[:50]])
    for a, its in by_area.items():
        write_feed(out / "oblast" / f"{area_slug(a)}.xml", f"Za ili Protiv: {latin(a)}", f"{site}oblast/{area_slug(a)}.xml",
                   f"{site}oblast/{area_slug(a)}.html",
                   [entry(it, it["law"]["short"], latin(it.get("gist") or "")) for it in its[:40]])
    (out / "poslanik").mkdir(exist_ok=True)
    for mp_slug, (name, record) in feeds_mp.items():
        write_feed(out / "poslanik" / f"{mp_slug}.xml", f"Za ili Protiv: {name}", f"{site}poslanik/{mp_slug}.xml",
                   f"{site}poslanik/{mp_slug}.html",
                   [entry(r["it"], f"{word.get(r['vote'], r['vote'])}: {r['it']['law']['short']}",
                          "Drugačije od većine svoje grupe. " if r["differs"] else "") for r in record])
