"""The Assembly's Rules of Procedure (Пословник Народне скупштине), article by article, every version kept
(20 Nov 2026, the maintainer's decision: the site links the articles MPs and the chair invoke, explains its terms
from them and checks the order of a sitting's steps against them; amendments are followed).

The source is the Assembly's own consolidated text (пречишћени текст), the page "Цео Пословник" (PAGE): each chapter
a `<div class="block">` with its `<h3>` ("II. КОНСТИТУИСАЊЕ НАРОДНЕ СКУПШТИНЕ"), sections as `<p class="preamble">`
in blocks of their own; nothing of the Rules stands outside a block, and nothing else of the page in one,
each article "Члан N." in bold, its paragraphs (ставови) the `<p>`s after it. The chapters' own pages are linked
from the site's menu (`/…/пословник-(пречишћени-текст)/<title>.<id>.html`), so an article leads to its chapter there.

Kept in data/poslovnik/: one file per version (`<the day first seen>.json`), written only when the articles' text
differs from the latest (`otisak`, a SHA-256 of it), and index.json listing them. The day a version was first seen
is not the day it came into force (the consolidated text gives none); versions before the first reading are not
known. The text is kept as the Assembly writes it, in Cyrillic.
"""
from __future__ import annotations

import hashlib
import html as html_
import json
import re
from html.parser import HTMLParser
from pathlib import Path

from zailiprotiv.config import BASE

PAGE = BASE + "/народна-скупштина/важна-документа/пословник-(пречишћени-текст)/цео-пословник-(пречишћени-текст).1422.html"
_CHAPTER_LINK = re.compile(r"<a href='(/народна-скупштина/важна-документа/пословник-\(пречишћени-текст\)/[^']+\.\d+\.html)'>([^<]+)</a>")
_ARTICLE = re.compile(r"^Члан\s+(\d+)\s*[а-ш]?\.?$")
_ROMAN = re.compile(r"^([IVXLC]+)\.\s*(.+)$")


def _norm(text: str) -> str:
    return " ".join(html_.unescape(text).replace("\xa0", " ").split())


# Cyrillic letters the page writes for Latin ones in a chapter's number ("IХ.", "Х.": a Cyrillic Х, 20 Nov 2026)
_LOOKALIKE = str.maketrans({"Х": "X", "І": "I", "С": "C", "Л": "L"})
_TO_CYRILLIC = str.maketrans({"a": "а", "e": "е", "o": "о", "c": "с", "p": "р", "x": "х", "y": "у", "k": "к", "m": "м",
                              "t": "т", "j": "ј", "i": "і"})


class _Parser(HTMLParser):
    """Collects, in order: chapters (h3), sections (p.preamble), article heads (a bold "Члан N.") and paragraphs, only
    inside a `<div class="block">` (25 Nov 2026: after the last one come the margin's calendar and news and the foot,
    which had been taken as paragraphs of article 298)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.items: list[tuple[str, str]] = []
        self._tag, self._buf = None, []
        self._divs: list[bool] = []  # the open divs, whether each is a block

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "div":
            self._divs.append(a.get("class") == "block")
        if not any(self._divs):
            return
        if tag == "h3":
            self._tag, self._buf = "h3", []
        elif tag == "p":
            self._tag, self._buf = ("preamble" if a.get("class") == "preamble" else "p"), []

    def handle_startendtag(self, tag, attrs):
        if tag == "br" and self._tag:
            self._buf.append("\n")

    def handle_endtag(self, tag):
        if tag == "br" and self._tag:
            self._buf.append("\n")
            return
        if tag == "div" and self._divs:
            self._divs.pop()
            if not any(self._divs):
                self._tag = None  # a paragraph left open ends with its block
            return
        if self._tag and ((tag == "h3" and self._tag == "h3") or (tag == "p" and self._tag in ("p", "preamble"))):
            # A paragraph is usually one <p>; one article (261) is a single <p> of lines broken by <br/>, its head
            # ("Члан 261.") the first of them: each line is then a paragraph of its own.
            for part in ("".join(self._buf).split("\n") if self._tag == "p" else ["".join(self._buf)]):
                text = _norm(part)
                if text:
                    kind = self._tag
                    if kind == "p" and _ARTICLE.match(text):
                        kind = "clan"
                    self.items.append((kind, text))
            self._tag = None

    def handle_data(self, data):
        if self._tag:
            self._buf.append(data)


def parse(page: str) -> dict:
    """{"glave": [{"broj", "naslov", "url"}], "clanovi": [{"n", "oznaka", "glava", "odeljak", "stavovi"}]} from the
    page with the whole text. An article's "oznaka" is as written ("Члан 27а." gives n 27, "27а")."""
    # the menu writes some titles with Latin look-alikes ("Уводнa одредбa", a Latin a): compared in Cyrillic
    key = lambda s: _norm(s).lower().translate(_TO_CYRILLIC)
    links = {key(t): BASE + u for u, t in _CHAPTER_LINK.findall(page)}
    p = _Parser()
    p.feed(page)
    chapters, articles = [], []
    chapter, section = "", ""
    for kind, text in p.items:
        if kind == "h3":
            head, _, rest = text.partition(".")
            m = _ROMAN.match(head.translate(_LOOKALIKE) + "." + rest)  # only the number: the title stays Cyrillic
            if not m:
                continue
            number, title = m.group(1), rest.strip()
            chapter, section = number, ""
            url = links.get(key(title)) or next((u for t, u in links.items() if t.startswith(key(title)[:30])), "")
            chapters.append({"broj": number, "naslov": title, "url": url})
        elif kind == "preamble":
            section = text
        elif kind == "clan":
            label = re.sub(r"^Члан\s+|\.$", "", text)
            articles.append({"n": int(_ARTICLE.match(text).group(1)), "oznaka": label, "glava": chapter,
                             "odeljak": section, "stavovi": []})
        elif kind == "p" and articles:
            articles[-1]["stavovi"].append(text)
    return {"glave": chapters, "clanovi": articles}


def fingerprint(doc: dict) -> str:
    text = "\n".join(f"{a['oznaka']}\n" + "\n".join(a["stavovi"]) for a in doc["clanovi"])
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def store(folder: Path, doc: dict, day: str) -> str | None:
    """Keep doc as a new version when its articles differ from the latest kept; the file's name when written."""
    folder.mkdir(parents=True, exist_ok=True)
    index_path = folder / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {"izvor": PAGE, "verzije": []}
    mark = fingerprint(doc)
    if index["verzije"] and index["verzije"][-1]["otisak"] == mark:
        return None
    name = f"{day}.json"
    (folder / name).write_text(json.dumps({"izvor": PAGE, "prvi_put_vidjeno": day, "otisak": mark, **doc},
                                          ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    index["verzije"].append({"od": day, "datoteka": name, "otisak": mark, "clanova": len(doc["clanovi"])})
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return name


def load(folder: Path, day: str | None = None) -> dict | None:
    """The version in force on `day` as far as the site knows (the latest first seen on or before it; the earliest
    for a day before any), or the latest. None when nothing is kept."""
    index_path = folder / "index.json"
    if not index_path.exists():
        return None
    versions = json.loads(index_path.read_text(encoding="utf-8"))["verzije"]
    if not versions:
        return None
    pick = versions[-1]
    if day:
        before = [v for v in versions if v["od"] <= day]
        pick = before[-1] if before else versions[0]
    return json.loads((folder / pick["datoteka"]).read_text(encoding="utf-8"))


# An article invoked in the debates (20 Nov 2026). In a speech pointing out a breach of the Rules ("Повреда
# Пословника, члан 103"), the articles named in its first CITE_HEAD characters; anywhere, an article named with the
# Rules' own name ("члан 107. Пословника"). An article named "of the Constitution" or "of the law" is not the Rules'.
CITE_HEAD = 400
_CITE = re.compile(r"\b(?:члан\w*|чл\.)\s+(\d{1,3})\b\.?(?:\s*(?:став|ст\.)\s*\d+\.?)?(?=(?P<after>[^.;:]{0,25}))", re.I)
_OF_RULES = re.compile(r"^\s*(?:,\s*)?Пословник", re.I)
_OTHER = re.compile(r"Устав|[Зз]акон", re.I)


def cited(text: str, point: bool, last: int = 298) -> list[tuple[int, int, int]]:
    """The Rules' articles a speech invokes: [(article, start, end)] of each mention in the text, by the rule above;
    `point` when the speech points out a breach of the Rules; only articles the Rules have (1..last)."""
    out = []
    for m in _CITE.finditer(text):
        n, after = int(m.group(1)), m.group("after") or ""
        if not 1 <= n <= last or _OTHER.search(after[:20]):
            continue
        if _OF_RULES.match(after) or (point and m.start() < CITE_HEAD):
            out.append((n, m.start(), m.end()))
    return out


def short(article: dict, limit: int = 220) -> str:
    """An article's first paragraph, cut between words at `limit` (with "…")."""
    first = (article.get("stavovi") or [""])[0]
    return first if len(first) <= limit else first[:limit].rsplit(" ", 1)[0] + " …"


# The site's terms explained from the Rules (20 Nov 2026, the maintainer's choice): data/poslovnik/pojmovi.json, written
# by hand, each term with the articles it rests on and the version of the Rules it was written against. A sentence of
# ours is shown only while those articles read as they did then; once one changes, the term shows the articles alone.
TERMS = "pojmovi.json"


def terms(folder: Path) -> list[dict]:
    """The terms, each with `articles` [{"n", "label", "text", "glava"}] as the Rules now read and `changed` (an
    article differs from the version the explanation was written against, or is gone). Empty without the Rules."""
    path, now = folder / TERMS, load(folder)
    if not now or not path.exists():
        return []
    current = {a["n"]: a for a in now["clanovi"]}
    out = []
    for t in json.loads(path.read_text(encoding="utf-8")):
        then = {a["n"]: a for a in (load(folder, t["verzija"]) or now)["clanovi"]}
        arts = [current[n] for n in t["clanovi"] if n in current]
        changed = any(n not in current or current[n]["stavovi"] != then.get(n, {}).get("stavovi") for n in t["clanovi"])
        out.append({**t, "changed": changed, "articles": [{"n": a["n"], "label": a["oznaka"], "text": a["stavovi"],
                                                           "glava": a["glava"]} for a in arts]})
    return out
