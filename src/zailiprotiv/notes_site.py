"""The stenographic notes read, as pages of their own: every speech word for word, each with an address, so that a
quote, a measure or a harsh word on the site can point at the very speech and what was said around it.

They are too much for the site's own host (twelve million words and growing), so they are built into a folder of
their own and kept in a Cloudflare R2 bucket behind beleske.zailiprotiv.rs (the maintainer, 14 Nov 2026):
`notes-site` builds the folder, `notes-upload` sends what changed. Latin pages at the root, the notes' own
Cyrillic under cir/. One page per day of a sitting, or several when the day is long.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import shutil
import urllib.parse
from pathlib import Path

from zailiprotiv import debates as debates_, mps
from zailiprotiv.translit import latin

HERE = Path(__file__).parent
PART = 300_000  # bytes of speech to a page, about; a day longer than that is split
MAIN = "https://zailiprotiv.rs/"
_MARK = re.compile(r"^\s*\d+/\d+\s*[A-ZА-ЯЈЉЊЂЋЏ]{1,3}\s*/\s*[A-ZА-ЯЈЉЊЂЋЏ]{1,3}\s*$", re.M)


def number(sitting_url: str) -> str:
    """The number the Assembly's site gives a sitting ("….53893.43.html" → "53893")."""
    m = re.search(r"\.(\d+)\.\d+\.html$", urllib.parse.unquote(sitting_url or ""))
    return m.group(1) if m else hashlib.sha256((sitting_url or "").encode()).hexdigest()[:10]


def layout(conv: str, notes: dict) -> dict[str, tuple[str, str]]:
    """Where each speech is: {speech key: (page, anchor)}, the page relative to the notes' root. The same for the
    builder of these pages and for the site that links to them."""
    out, base = {}, f"{conv}/{number(notes['sitting'])}"
    by_day: dict[int, list[str]] = {}
    for k in sorted(notes["speeches"]):
        by_day.setdefault(notes["speeches"][k]["day"], []).append(k)
    for day, keys in sorted(by_day.items()):
        part, size = 1, 0
        for k in keys:
            n = len(notes["speeches"][k]["text"].encode("utf-8"))
            if size and size + n > PART:
                part, size = part + 1, 0
            size += n
            out[k] = (f"{base}/dan-{day}{'' if part == 1 else f'-{part}'}.html", f"g{k}")
    return out


PAGE = """<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="icon" type="image/svg+xml" href="{root}favicon.svg">
<link rel="stylesheet" href="{root}style.css">
</head>
<body>
<header class="top">
  <a class="brand" href="{main}"><svg class="brand-mark" viewBox="0 0 120 76" aria-hidden="true"><path class="m-za" d="M 14 66 A 46 46 0 0 1 83 26.2"/><path class="m-protiv" d="M 89.6 30.8 A 46 46 0 0 1 106 66"/></svg><span><span class="w-za">Za</span> ili <span class="w-protiv">Protiv</span></span></a>
  <nav><a href="{root}{home}">{t_notes}</a> <a href="{other}" hreflang="{other_lang}">{t_other}</a></nav>
</header>
<main class="notes">
{body}
</main>
<footer><p>{t_foot}</p></footer>
</body>
</html>
"""
WORDS = {
    "lat": {"lang": "sr-Latn", "notes": "Stenografske beleške", "other": "Ћирилица", "other_lang": "sr-Cyrl",
            "chair": "Predsedavajući", "source": "Izvorni fajl Skupštine za ovaj dan", "day": "dan", "part": "deo",
            "foot": "Stenografske beleške Narodne skupštine Republike Srbije, od reči do reči, kako ih Skupština "
                    "objavljuje; preslovljene na latinicu. Privremene beleške Skupština kasnije zamenjuje konačnim. "
                    "Merodavan je izvorni fajl.",
            "lead": "Beleške sednica koje smo pročitali, govor po govor. Svaki govor ima svoju adresu.",
            "prov": "privremene beleške", "prev": "Prethodni deo", "next": "Sledeći deo", "conv": "saziv"},
    "cir": {"lang": "sr-Cyrl", "notes": "Стенографске белешке", "other": "Latinica", "other_lang": "sr-Latn",
            "chair": "Председавајући", "source": "Изворни фајл Скупштине за овај дан", "day": "дан", "part": "део",
            "foot": "Стенографске белешке Народне скупштине Републике Србије, од речи до речи, како их Скупштина "
                    "објављује. Привремене белешке Скупштина касније замењује коначним. Меродаван је изворни фајл.",
            "lead": "Белешке седница које смо прочитали, говор по говор. Сваки говор има своју адресу.",
            "prov": "привремене белешке", "prev": "Претходни део", "next": "Следећи део", "conv": "сазив"},
}


def _speech(k: str, s: dict, who: dict | None, w: dict, script: str) -> str:
    show = (lambda t: latin(t)) if script == "lat" else (lambda t: t)
    name = show(s["speaker"]).title() if not s.get("chair") else show(s["speaker"]).capitalize()
    if who and who.get("slug"):
        name = f'<a href="{MAIN}poslanik/{who["slug"]}">{html.escape(who["name"] if script == "lat" else name)}</a>'
    else:
        name = html.escape(name)
    paras = "".join(f"<p>{html.escape(show(p))}</p>" for p in _MARK.sub("", s["text"]).split("\n") if p.strip())
    return (f'<article class="turn{" turn-chair" if s.get("chair") else ""}" id="g{k}">'
            f'<h2><a class="anchor" href="#g{k}">{name}</a></h2>{paras}</article>')


def build(root: Path, out: Path) -> dict[str, int]:
    """The pages of every sitting whose notes were read, into `out`. Returns how many pages and speeches."""
    from zailiprotiv import site
    convs = site.convocations(root)
    mps.load_aliases(root / "mp_aliases.json")
    votes = {k: v for _, path in convs for k, v in site.load(path)[1].items()}
    people = site.registry(votes)
    loose = {debates_.loose(k): k for k in people}
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for name in ("style.css", "favicon.svg"):
        shutil.copy(HERE / "static" / name, out / name)
    shutil.copytree(HERE / "static" / "fonts", out / "fonts")
    pages = speeches = 0
    listing: dict[str, list] = {}
    for conv, path in convs:
        for url, notes in site.load_transcripts(path).items():
            if not notes.get("speeches"):
                continue
            where = layout(conv, notes)
            days = {d["day"]: d for d in notes["days"]}
            title = re.sub(r"^СТЕНОГРАФСКЕ БЕЛЕШКЕ\s*-\s*", "", notes["days"][0]["title"]).split(" - ")[0] if notes["days"] else url
            by_page: dict[str, list[str]] = {}
            for k in sorted(notes["speeches"]):
                by_page.setdefault(where[k][0], []).append(k)
            names = list(by_page)
            listing.setdefault(conv, []).append({"title": title, "pages": names, "days": days,
                                                 "date": min((d.get("listed_date") or "9999" for d in notes["days"]), default="")})
            for i, (page, keys) in enumerate(by_page.items()):
                first = notes["speeches"][keys[0]]
                day = days.get(first["day"], {})
                part = re.search(r"-(\d+)\.html$", page.rsplit("/", 1)[-1].replace(f"dan-{first['day']}", ""))
                for script in ("lat", "cir"):
                    w = WORDS[script]
                    show = latin if script == "lat" else (lambda t: t)
                    head = f"{show(title)}, {first['day']}. {w['day']}" + (f", {part.group(1)}. {w['part']}" if part else "")
                    body = [f'<p class="crumbs"><a href="../../{"index.html"}">{w["notes"]}</a> › {site.ORDINAL_NAME.get(conv, conv) if script == "lat" else conv + "."} {w["conv"]}</p>',
                            f"<h1>{html.escape(head)}</h1>",
                            f'<p class="meta">{html.escape(day.get("listed_date") or day.get("date") or "")}'
                            + (f' · {w["prov"]}' if day.get("provisional") else "")
                            + (f' · <a href="{html.escape(day["url"])}">{w["source"]}</a>' if day.get("url") else "") + "</p>"]
                    nav = []
                    if i and names[i - 1].rsplit("/", 1)[0] == page.rsplit("/", 1)[0]:
                        nav.append(f'<a href="{names[i - 1].rsplit("/", 1)[-1]}">← {w["prev"]}</a>')
                    if i + 1 < len(names):
                        nav.append(f'<a href="{names[i + 1].rsplit("/", 1)[-1]}">{w["next"]} →</a>')
                    pager = f'<nav class="page-menu">{"".join(nav)}</nav>' if nav else ""
                    body.append(pager)
                    for k in keys:
                        s = notes["speeches"][k]
                        key = None if s.get("chair") else loose.get(debates_.loose(mps.key(s["speaker"])))
                        body.append(_speech(k, s, {"slug": people[key].slug, "name": people[key].name} if key else None, w, script))
                    body.append(pager)
                    target = out / ("" if script == "lat" else "cir") / page
                    target.parent.mkdir(parents=True, exist_ok=True)
                    twin = ("../../cir/" if script == "lat" else "../../../") + page
                    target.write_text(PAGE.format(
                        lang=w["lang"], title=html.escape(head), root="../../" if script == "lat" else "../../../",
                        main=MAIN if script == "lat" else MAIN + "cir/", home="index.html" if script == "lat" else "cir/index.html",
                        t_notes=w["notes"], other=twin, other_lang=w["other_lang"], t_other=w["other"],
                        body="\n".join(body), t_foot=w["foot"]), encoding="utf-8")
                pages += 1
                speeches += len(keys)
    for script in ("lat", "cir"):  # the list of what is here
        w = WORDS[script]
        show = latin if script == "lat" else (lambda t: t)
        body = [f"<h1>{w['notes']}</h1>", f'<p class="standfirst">{w["lead"]}</p>']
        for conv in sorted(listing, key=int, reverse=True):
            body.append(f"<h2>{site.ORDINAL_NAME.get(conv, conv) if script == 'lat' else conv + '.'} {w['conv']}</h2><ul class=\"plain sittings-list\">")
            for s in sorted(listing[conv], key=lambda s: s["date"], reverse=True):
                links = " ".join(f'<a href="{p}">{re.sub(r"^dan-", "", p.rsplit("/", 1)[-1][:-5]).replace("-", "/")}</a>' for p in s["pages"])
                body.append(f'<li>{html.escape(show(s["title"]))} <span class="meta">· {s["date"]} · {w["day"]}: {links}</span></li>')
            body.append("</ul>")
        target = out / ("index.html" if script == "lat" else "cir/index.html")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(PAGE.format(
            lang=w["lang"], title=w["notes"], root="" if script == "lat" else "../", main=MAIN if script == "lat" else MAIN + "cir/",
            home="index.html" if script == "lat" else "cir/index.html", t_notes=w["notes"],
            other="cir/index.html" if script == "lat" else "../index.html", other_lang=w["other_lang"], t_other=w["other"],
            body="\n".join(body), t_foot=w["foot"]), encoding="utf-8")
    return {"pages": pages, "speeches": speeches}


def changed(folder: Path, manifest: dict[str, str]) -> tuple[dict[str, str], list[str], list[str]]:
    """The folder's files by content ({path: sha256}), those new or different from `manifest`, and those gone."""
    now = {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
           for p in sorted(folder.rglob("*")) if p.is_file()}
    return now, [k for k, v in now.items() if manifest.get(k) != v], [k for k in manifest if k not in now]
