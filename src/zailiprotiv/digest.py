"""The week in the Assembly: a page per week in which a law was passed or a bill submitted, a list of the weeks, and
a feed with each week's text in full.

The feed is what a newsletter is sent from: a mailing service that turns a feed into e-mail ("RSS to e-mail") sends
each new week to its subscribers, and the site itself keeps no addresses. `data/settings.json` may name the service's
sign-up page (`newsletter_url`), shown as a link."""
from __future__ import annotations

import datetime as dt
import json
from collections import defaultdict
from pathlib import Path
from xml.sax.saxutils import escape as x

from zailiprotiv.site import against_share, day
from zailiprotiv.translit import latin


def week_of(iso: str) -> tuple[str, dt.date]:
    """The week's key ("2026-35", the ISO year and week) and its Monday."""
    d = dt.date.fromisoformat(iso[:10])
    y, w, _ = d.isocalendar()
    return f"{y}-{w:02d}", d - dt.timedelta(days=d.weekday())


def span(monday: dt.date) -> str:
    sunday = monday + dt.timedelta(days=6)
    a, b = day(monday.isoformat()), day(sunday.isoformat())
    return f"{monday.day}–{b}" if (monday.month, monday.year) == (sunday.month, sunday.year) else f"{a.rstrip('.')} – {b}"


def render(*, env, common, out: Path, root: Path, current: str, items_by_conv: dict, site_url: str) -> list[dict]:
    weeks: dict[str, dict] = defaultdict(lambda: {"laws": [], "bills": []})
    for its in items_by_conv.values():
        for it in its:
            if it["law"].get("passed"):
                key, monday = week_of(it["law"]["passed"])
                weeks[key]["laws"].append(it)
                weeks[key]["monday"] = monday
    proc = root / current / "procedure.json"
    if proc.exists():
        for pdf, b in json.loads(proc.read_text(encoding="utf-8"))["bills"].items():
            if b.get("submitted"):
                key, monday = week_of(b["submitted"])
                weeks[key]["bills"].append({**b, "pdf": pdf})
                weeks[key]["monday"] = monday
    settings = json.loads((root / "settings.json").read_text(encoding="utf-8")) if (root / "settings.json").exists() else {}
    listed = []
    for key, w in sorted(weeks.items(), reverse=True):
        laws = sorted(w["laws"], key=lambda it: (-(against_share(it["final"]["counts"]) if it["final"] else 0),
                                                 it["law"]["short"]))
        voted = [it for it in laws if it["final"]]
        info = {"key": key, "monday": w["monday"], "span": span(w["monday"]), "laws": laws,
                "bills": sorted(w["bills"], key=lambda b: b["submitted"]), "n": len(laws),
                "opposed": sum(1 for it in voted if it["final"]["counts"]["protiv"]),
                "urgent": sum(1 for it in laws if it["urgent"]),
                "days": sorted({it["law"]["passed"] for it in laws})}
        listed.append(info)
    (out / "nedelja").mkdir(exist_ok=True)
    for i, info in enumerate(listed):
        (out / "nedelja" / f"{info['key']}.html").write_text(env.get_template("week.html").render(
            **common, w=info, newer=listed[i - 1] if i else None, older=listed[i + 1] if i + 1 < len(listed) else None,
            newsletter_url=settings.get("newsletter_url", ""), root="../"), encoding="utf-8")
    (out / "nedelje.html").write_text(env.get_template("weeks.html").render(
        **common, weeks=listed, newsletter_url=settings.get("newsletter_url", ""), root=""), encoding="utf-8")
    # The feed: the twelve newest weeks, each with its text in full, so it can be sent as it is.
    entries = []
    for info in listed[:12]:
        url = f"{site_url}nedelja/{info['key']}.html"
        html = env.get_template("week_mail.html").render(w=info, site=site_url, url=url)
        updated = (info["monday"] + dt.timedelta(days=6)).isoformat() + "T18:00:00Z"
        entries.append(f"<entry><title>{x('U Skupštini, ' + info['span'])}</title><link href=\"{x(url)}\"/><id>{x(url)}</id>"
                       f"<updated>{updated}</updated><content type=\"html\">{x(html)}</content></entry>\n")
    newest = (listed[0]["monday"] + dt.timedelta(days=6)).isoformat() + "T18:00:00Z" if listed else "2000-01-01T00:00:00Z"
    (out / "nedelje.xml").write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n<feed xmlns="http://www.w3.org/2005/Atom">\n'
        f"<title>Za ili Protiv: nedelja u Skupštini</title><link rel=\"self\" href=\"{site_url}nedelje.xml\"/>"
        f"<link href=\"{site_url}nedelje.html\"/><id>{site_url}nedelje.html</id><updated>{newest}</updated>\n"
        + "".join(entries) + "</feed>\n", encoding="utf-8")
    return listed
