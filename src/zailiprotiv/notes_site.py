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

from zailiprotiv import debates as debates_, family, mps, poslovnik
from zailiprotiv.translit import latin

HERE = Path(__file__).parent
PART = 300_000  # bytes of speech to a page, about; a day longer than that is split
MAIN = "https://zailiprotiv.rs/"
NOTES = "https://beleske.zailiprotiv.rs/"  # where the bucket is served: the pages' own addresses, for search engines
# A speech pointing out a breach of the Rules (as pages_floor._POINT, which imports this module)
_POINT_OF_ORDER = re.compile(r"повред\w* Пословника|по Пословнику|рекламирам\w* члан|члан\w* \d+\.? ?Пословника", re.I)
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


class Finder:
    """Where among our notes' pages a quoted sentence was said: the address of the very speech, for the links under
    quotes (which used to lead to the Assembly's file, a download). A quote is known by the day's file it came from,
    its speaker and its words; the speech is the speaker's on that day that holds the words, and failing that anyone's
    that day, and failing that the day's page. Only pages in the bucket (`pages`) are given."""

    def __init__(self, root: Path, url: str, pages: set | None = None, stores: dict | None = None):
        """`stores` are the notes already read, by convocation and sitting, when the caller has them: reading them
        again, one sitting at a time, was half of the site's build."""
        import json
        self.url, self.pages = url.rstrip("/") + "/" if url else "", pages
        self.by_day: dict[str, tuple[dict, str, int]] = {}  # the day's file at the Assembly → (its notes, convocation, day)
        self._kept: dict = {}
        if not self.url:
            return
        if stores is None:
            stores = {}
            for f in sorted(root.glob("*/transcripts/*.json")):
                stores.setdefault(f.parent.parent.name, {})[f.name] = json.loads(f.read_text(encoding="utf-8"))
        for conv, held in stores.items():
            for notes in held.values():
                for i, d in enumerate(notes.get("days", []), 1):
                    if d.get("url"):
                        self.by_day[d["url"]] = (notes, str(conv), d.get("day") or i)

    @staticmethod
    def _plain(text: str) -> str:
        return re.sub(r"[^0-9a-zа-яђјљњћџžšđčć]+", " ", text.lower()).strip()

    def _notes(self, notes: dict, conv: str):
        """One sitting's notes made ready, once: where each speech is, and each day's speeches as [key, speaker's
        words sorted, text, the text made plain when first needed]."""
        if id(notes) not in self._kept:
            by_day: dict[int, list] = {}
            whole = debates_.whole_names(notes["speeches"].values())
            for k in sorted(notes["speeches"]):
                sp = notes["speeches"][k]
                name = whole.get(sp["speaker"], sp["speaker"])
                by_day.setdefault(sp["day"], []).append([k, " ".join(sorted(self._plain(name).split())), sp["text"], None])
            self._kept[id(notes)] = (layout(conv, notes), by_day)
        return self._kept[id(notes)]

    def __call__(self, day_url: str | None, speaker: str, text: str) -> str:
        at = self.by_day.get(day_url or "")
        if not at:
            return ""
        where, by_day = self._notes(at[0], at[1])
        said, who, want = by_day.get(at[2], []), " ".join(sorted(self._plain(speaker).split())), self._plain(text)
        ok = lambda k: self.pages is None or where[k][0] in self.pages
        for own in (True, False):
            for row in said:
                if (row[1] == who) != own or not want or not ok(row[0]):
                    continue
                if row[3] is None:
                    row[3] = self._plain(row[2])
                if want in row[3]:
                    return f"{self.url}{where[row[0]][0]}#{where[row[0]][1]}"
        return next((self.url + where[row[0]][0] for row in said if ok(row[0])), "")

    def day(self, day_url: str | None, speaker: str = "") -> str:
        """The day's page among ours; with a speaker, at that speaker's first speech of the day."""
        at = self.by_day.get(day_url or "")
        if not at:
            return ""
        where, by_day = self._notes(at[0], at[1])
        said, who = by_day.get(at[2], []), " ".join(sorted(self._plain(speaker).split()))
        ok = lambda k: self.pages is None or where[k][0] in self.pages
        if who:
            for k, name, _, _ in said:
                if name == who and ok(k):
                    return f"{self.url}{where[k][0]}#{where[k][1]}"
        return next((self.url + where[row[0]][0] for row in said if ok(row[0])), "")


PAGE = """<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{description}">
<link rel="canonical" href="{here}">
<link rel="alternate" hreflang="sr-Latn" href="{lat}">
<link rel="alternate" hreflang="sr-Cyrl" href="{cyr}">
<link rel="alternate" hreflang="x-default" href="{lat}">
<link rel="icon" type="image/svg+xml" href="{root}favicon.svg">
<link rel="icon" type="image/png" sizes="96x96" href="{root}favicon-96.png">
<link rel="stylesheet" href="{root}style.css">
</head>
<body>
{bar}
<header class="top">
  <a class="brand" href="{main}"><svg class="brand-mark" viewBox="0 0 120 76" aria-hidden="true"><path class="m-za" d="M 14 66 A 46 46 0 0 1 83 26.2"/><path class="m-protiv" d="M 89.6 30.8 A 46 46 0 0 1 106 66"/></svg><span><span class="w-za">Za</span> ili <span class="w-protiv">Protiv</span></span></a>
  <nav><a href="{root}{home}">{t_notes}</a> <a href="{other}" hreflang="{other_lang}">{t_other}</a></nav>
</header>
<main class="notes">
{body}
</main>
<footer><p>{t_foot}</p></footer>
<script type="module">
// A page opened from the search shows the words searched for (…?highlight=word): Pagefind's own script, kept here.
if (new URLSearchParams(location.search).has("highlight")) {{
  import("{root}pagefind/pagefind-highlight.js").then(() => {{ new PagefindHighlight({{ highlightParam: "highlight" }}); }}).catch(() => {{}});
}}
</script>
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
            "about": "Stenografske beleške Narodne skupštine Srbije, od reči do reči",
            "prov": "privremene beleške", "prev": "Prethodni deo", "next": "Sledeći deo", "conv": "saziv",
            "clip": "snimak",
            "clip_how": "Mesto u snimku prenosa Skupštine, nađeno automatski po redosledu govornika iz potpisa u "
                        "prenosu; može da promaši.",
            "no_heading": "Bez imena govornika u beleškama (deo prozivke)"},
    "cir": {"lang": "sr-Cyrl", "notes": "Стенографске белешке", "other": "Latinica", "other_lang": "sr-Latn",
            "chair": "Председавајући", "source": "Изворни фајл Скупштине за овај дан", "day": "дан", "part": "део",
            "foot": "Стенографске белешке Народне скупштине Републике Србије, од речи до речи, како их Скупштина "
                    "објављује. Привремене белешке Скупштина касније замењује коначним. Меродаван је изворни фајл.",
            "lead": "Белешке седница које смо прочитали, говор по говор. Сваки говор има своју адресу.",
            "about": "Стенографске белешке Народне скупштине Србије, од речи до речи",
            "prov": "привремене белешке", "prev": "Претходни део", "next": "Следећи део", "conv": "сазив",
            "clip": "снимак",
            "clip_how": "Место у снимку преноса Скупштине, нађено аутоматски по редоследу говорника из потписа у "
                        "преносу; може да промаши.",
            "no_heading": "Без имена говорника у белешкама (део прозивке)"},
}


def _clip(at: dict | None, w: dict) -> str:
    """A link to where the speech begins in the recording of the broadcast, found by the live page's record."""
    if not at:
        return ""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    when = datetime.fromtimestamp(at["at"], ZoneInfo("Europe/Belgrade")).strftime("%H:%M")
    url = f"https://www.youtube.com/watch?v={urllib.parse.quote(at['video'])}&t={int(at['t'])}s"
    return f'<p class="clip"><a href="{html.escape(url)}" title="{html.escape(w["clip_how"])}">▶ {w["clip"]}, {when}</a></p>'


def _speech(k: str, s: dict, who: dict | None, w: dict, script: str, at: dict | None = None) -> str:
    show = (lambda t: latin(t)) if script == "lat" else (lambda t: t)
    name = show(s["speaker"]).title() if not s.get("chair") else show(s["speaker"]).capitalize()
    if not s["speaker"]:  # a part the notes give no heading (transcripts.mended): nobody's, and said so
        name = w["no_heading"]
    if who and who.get("slug"):
        name = f'<a href="{MAIN}poslanik/{who["slug"]}">{html.escape(who["name"] if script == "lat" else name)}</a>'
    else:
        name = html.escape(name)
    text = _MARK.sub("", s["text"])
    # The Rules' articles the speech invokes (poslovnik.cited) lead to that article's text on the site (20 Nov 2026).
    cites = poslovnik.cited(text, not s.get("chair") and bool(_POINT_OF_ORDER.search(text[:300])))
    paras, pos = [], 0
    for p in text.split("\n"):
        start, pos = pos, pos + len(p) + 1
        if not p.strip():
            continue
        out, done = [], 0
        for n, a, b in cites:
            if start <= a and b <= start + len(p):
                href = f'{MAIN}{"" if script == "lat" else "cir/"}poslovnik-clanovi#clan-{n}'
                out += [html.escape(show(p[done:a - start])),
                        f'<a class="rule" href="{href}">{html.escape(show(p[a - start:b - start]))}</a>']
                done = b - start
        out.append(html.escape(show(p[done:])))
        paras.append(f"<p>{''.join(out)}</p>")
    paras = "".join(paras)
    return (f'<article class="turn{" turn-chair" if s.get("chair") else ""}" id="g{k}">'
            f'<h2 id="s{k}"><a class="anchor" href="#g{k}">{name}</a></h2>{_clip(at, w)}{paras}</article>')


def build(root: Path, out: Path) -> dict[str, int]:
    """The pages of every sitting whose notes were read, into `out`. Returns how many pages and speeches."""
    from zailiprotiv import site
    convs = site.convocations(root)
    mps.load_aliases(root / "mp_aliases.json")
    loaded = {conv: site.load(path)[1] for conv, path in convs}  # each convocation's roll calls, read once
    votes = {k: v for conv, _ in convs for k, v in loaded[conv].items()}
    people = site.registry(votes)
    loose = {debates_.loose(k): k for k in people}
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for name in ("style.css", "favicon.svg", "favicon-96.png"):
        shutil.copy(HERE / "static" / name, out / name)
    family.write_stylesheet(out)  # the family's look in front of the site's own, as on the site
    shutil.copytree(HERE / "static" / "fonts", out / "fonts")
    pages = speeches = 0
    listing: dict[str, list] = {}
    from zailiprotiv import uzivo
    settings = json.loads((root / "settings.json").read_text(encoding="utf-8")) if (root / "settings.json").exists() else {}
    for conv, path in convs:
        # The live page's record of who spoke when, by day: links to the recording's minute, once the maintainer has
        # checked a few by hand and set `recording_links` (data/settings.json).
        records = uzivo.load(path) if settings.get("recording_links") else {}
        stores = site.load_transcripts(path)
        debates_.mend(stores, loaded[conv])  # the speakers' names mistyped in the notes, set right
        for url, notes in stores.items():
            if not notes.get("speeches"):
                continue
            where = layout(conv, notes)
            clips = uzivo.minutes(notes, records) if records else {}
            whole = debates_.whole_names(notes["speeches"].values())  # a surname alone → the one such speaker of the sitting
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
                            "<div data-pagefind-body>",  # what the search reads: the heading and the speeches
                            f"<h1>{html.escape(head)}</h1>",
                            f'<p class="meta">{html.escape(day.get("listed_date") or day.get("date") or "")}'
                            + (f' · {w["prov"]}' if day.get("provisional") else "")
                            + (f' · <a href="{html.escape(day["url"])}">{w["source"]}</a>' if day.get("url") else "") + "</p>"]
                    nav = []
                    if i and names[i - 1].rsplit("/", 1)[0] == page.rsplit("/", 1)[0]:
                        nav.append(f'<a href="{names[i - 1].rsplit("/", 1)[-1]}">← {w["prev"]}</a>')
                    if i + 1 < len(names):
                        nav.append(f'<a href="{names[i + 1].rsplit("/", 1)[-1]}">{w["next"]} →</a>')
                    pager = f'<nav class="page-menu" data-pagefind-ignore>{"".join(nav)}</nav>' if nav else ""
                    body.append(pager)
                    for k in keys:
                        s = notes["speeches"][k]
                        if s["speaker"] in whole:
                            s = {**s, "speaker": whole[s["speaker"]]}
                        key = None if s.get("chair") else loose.get(debates_.loose(mps.key(s["speaker"])))
                        body.append(_speech(k, s, {"slug": people[key].slug, "name": people[key].name} if key else None, w, script,
                                            clips.get(k)))
                    body.append(pager)
                    body.append("</div>")
                    target = out / ("" if script == "lat" else "cir") / page
                    target.parent.mkdir(parents=True, exist_ok=True)
                    twin = ("../../cir/" if script == "lat" else "../../../") + page
                    target.write_text(PAGE.format(
                        lang=w["lang"], title=html.escape(head), description=html.escape(f"{head}. {w['about']}."),
                        here=NOTES + ("" if script == "lat" else "cir/") + page, lat=NOTES + page, cyr=NOTES + "cir/" + page, root="../../" if script == "lat" else "../../../",
                        main=MAIN if script == "lat" else MAIN + "cir/", bar=family.bar("lat" if script == "lat" else "cyr", MAIN if script == "lat" else MAIN + "cir/", twin=False), home="index.html" if script == "lat" else "cir/index.html",
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
            lang=w["lang"], title=w["notes"], description=html.escape(w["about"] + ". " + w["lead"]),
            here=NOTES + ("" if script == "lat" else "cir/"), lat=NOTES, cyr=NOTES + "cir/", root="" if script == "lat" else "../", main=MAIN if script == "lat" else MAIN + "cir/", bar=family.bar("lat" if script == "lat" else "cyr", MAIN if script == "lat" else MAIN + "cir/", twin=False),
            home="index.html" if script == "lat" else "cir/index.html", t_notes=w["notes"],
            other="cir/index.html" if script == "lat" else "../index.html", other_lang=w["other_lang"], t_other=w["other"],
            body="\n".join(body), t_foot=w["foot"]), encoding="utf-8")
    # For search engines: every page, in both scripts, and where the list of them is. The search index is not for them.
    found = sorted(p.relative_to(out).as_posix() for p in out.rglob("*.html"))
    (out / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"<url><loc>{NOTES}{'' if p == 'index.html' else 'cir/' if p == 'cir/index.html' else html.escape(p)}</loc></url>\n" for p in found)
        + "</urlset>\n", encoding="utf-8")
    (out / "robots.txt").write_text(f"User-agent: *\nAllow: /\nDisallow: /pagefind/\n\nSitemap: {NOTES}sitemap.xml\n", encoding="utf-8")
    return {"pages": pages, "speeches": speeches}


def changed(folder: Path, manifest: dict[str, str]) -> tuple[dict[str, str], list[str], list[str]]:
    """The folder's files by content ({path: sha256}), those new or different from `manifest`, and those gone."""
    now = {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
           for p in sorted(folder.rglob("*")) if p.is_file()}
    return now, [k for k, v in now.items() if manifest.get(k) != v], [k for k in manifest if k not in now]
