"""Who holds which office in the Assembly, and the Assembly's news (20 Nov 2026, the maintainer's request: "the
election of committee members, the deputy Speakers, and so on", each office on the MP's page).

Read from the Assembly's own pages of its composition ("Састав"), not from the wording of its news:
- the Speaker: the Speaker's biography, an MP's page like any other (the name in `<h2>`, "Функција у Народној
  скупштини Републике Србије" a list);
- the deputy Speakers: their page, a block per person (name in `<h2>`, group in `<h3>`);
- the chairs of the parliamentary groups: their page, the same blocks;
- the committees: the list of committees links a page per committee, a table of rows "NAME (члан | председник |
  заменик председника), group, DEPUTY (заменик члана), group";
- the standing delegations: the list links a page per delegation, rows "NAME, шеф Делегације | члан Делегације …".
The newest convocation's are the pages under "Састав"; an earlier one's committees and delegations are on its archive
pages (ARCHIVE), read once. Kept in data/<N>/offices.json; each office says the page it is from and the day it was
first seen there (not the day of the election, which the pages don't give).

The news are the list on "Активности" (one page each run): every item kept in data/vesti.json with the day first
seen, and marked `relevant` by a fixed rule on the title (elections, appointments, resignations, mandates, the
constitution of the Assembly or of a body, and the plenary sittings, whose page tells what was elected). A new
relevant item is what makes a run read the committees' and delegations' pages again before their weekly reading.
"""
from __future__ import annotations

import html as htmllib
import json
import re
import urllib.parse

from zailiprotiv.config import BASE

S = BASE + "/народна-скупштина/састав"
SPEAKER = S + "/председник/биографија-.2418.html"
VICE = S + "/потпредседници/потпредседници.9.html"
GROUP_CHAIRS = S + "/посланичке-групе-/председници-посланичких-група.869.html"
COMMITTEES = S + "/радна-тела/одбори.13.html"
DELEGATIONS = S + "/делегације/делегације.14.html"
NEWS = BASE + "/активности.42.html"

# An earlier convocation's committees and delegations, as its archive pages list them. Only those whose rows read
# as the newest's do are listed here.
ARCHIVE = {
    "14": {"committees": S + "/радна-тела/сазив-од-6-фебруара-2024-године.5177.html",
           "delegations": S + "/делегације/сазив-од-6-фебруара-2024-године.5180.html"},
}

WEEK = 7 * 24 * 3600  # the committees' and delegations' pages are read again at least this often


def _text(s: str) -> str:
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def _content(page: str) -> str:
    """The page's own part, without the menus and the margins (which list other pages and the latest news)."""
    i, j = page.find("OCP content start"), page.find("OCP content end")
    return page[i:j] if 0 <= i < j else page


def person(page: str) -> tuple[str, list[str]]:
    """An MP's page at the Assembly → (the name as written, "АЛЕКСАНДАР ЧУПИЋ"; the offices it lists under "Функција у
    Народној скупштини Републике Србије")."""
    page = _content(page)
    m = re.search(r"<h2>(.*?)</h2>", page, re.S)
    name = _text(m.group(1)) if m else ""
    f = re.search(r"<h4>\s*Функција у Народној скупштини[^<]*</h4>\s*(<ul>.*?</ul>|<p>.*?</p>)", page, re.S)
    roles = [_text(x) for x in re.findall(r"<li>(.*?)</li>", f.group(1), re.S)] if f else []
    if f and not roles and _text(f.group(1)) not in ("", "-"):
        roles = [_text(f.group(1))]
    return name, roles


def blocks(page: str) -> list[tuple[str, str]]:
    """The deputy Speakers' or the groups' chairs' page → [(name, group)], in the page's order."""
    return [(_text(a), _text(b)) for a, b in
            re.findall(r'<div class="block">.*?<h2>(.*?)</h2>\s*<h3>(.*?)</h3>', _content(page), re.S)]


def parts(page: str, listing: str) -> list[tuple[str, str]]:
    """The committees or delegations a list page links: [(title, address)], each once, in the page's order. Their
    pages are "<listing's address without .html>.<id>.<listing's number>.html" or so: a link ending in
    ".<id>.<the listing's number>.html"."""
    number = re.search(r"\.(\d+)\.html$", listing).group(1)
    seen, out = set(), []
    for href, title in re.findall(r'<a[^>]+?href="([^"]+\.\d+\.' + number + r'\.html)"[^>]*>(.*?)</a>',
                                  _content(page), re.S):
        url = urllib.parse.urljoin(BASE, htmllib.unescape(href))
        t = _text(title)
        if url not in seen and t and not t.startswith("Погледајте"):
            seen.add(url)
            out.append((t, url))
    return out


_COMMITTEE_ROW = re.compile(
    r"<strong>(?P<name>[^<]+)</strong>\s*\(\s*(?:<strong>)?(?P<role>[^<)]+?)(?:</strong>)?\s*\)\s*<br\s*/?>"
    r"(?P<group>[^<]*)<br\s*/?>(?P<deputy>[^<(]*)\(заменик члана\)\s*<br\s*/?>(?P<dgroup>[^<]*)", re.S)
_DELEGATION_ROW = re.compile(r"<td[^>]*>\s*<strong>(?P<name>[^<]+)</strong>\s*<br\s*/?>(?P<role>[^<]+)</td>", re.S)


def _group(s: str) -> str:
    return re.sub(r"^Посланичка група\s*", "", _text(s)).strip()


def committee(page: str) -> list[dict]:
    """A committee's page → [{"name", "role", "group"}]: each member with their role (председник, заменик
    председника, члан) and each member's deputy (заменик члана)."""
    out = []
    for m in _COMMITTEE_ROW.finditer(_content(page)):
        out.append({"name": _text(m["name"]), "role": _text(m["role"]), "group": _group(m["group"])})
        if _text(m["deputy"]):
            out.append({"name": _text(m["deputy"]), "role": "заменик члана", "group": _group(m["dgroup"])})
    return out


def delegation(page: str) -> list[dict]:
    """A delegation's page → [{"name", "role"}] (шеф Делегације, заменик шефа Делегације, члан Делегације …)."""
    return [{"name": _text(m["name"]), "role": _text(m["role"])} for m in _DELEGATION_ROW.finditer(_content(page))]


# The rule for a relevant news item, on its title: who was elected, appointed, dismissed or resigned, a mandate, a
# body constituted, and the plenary sittings (whose page tells what the Assembly elected).
RELEVANT = re.compile(r"избор|изабран|бира|именова|разреш|оставк|мандат|конститути|констатова|"
                      r"\bседниц\w* Народне скупштине|\bзаседањ\w* Народне скупштине|посланичк\w* груп", re.I)


def news(page: str) -> list[dict]:
    """The news on "Активности": [{"id", "title", "url", "date" (when the list gives it, "17. новембар 2026.")}],
    each once, in the page's order."""
    out, seen = [], set()
    body = _content(page)
    for m in re.finditer(r'<a[^>]+?href="([^"]+\.(\d+)\.43\.html)"[^>]*>(.*?)</a>', body, re.S):
        href, nid, t = m.group(1), m.group(2), _text(m.group(3))
        if not t or nid in seen:
            continue
        seen.add(nid)
        after = body[m.end():m.end() + 600]
        d = re.match(r'\s*</h\d>\s*(?:<div class="clear"></div>\s*)?<p class="posted">\s*[^,<]+,\s*([^|<]+)', after)
        item = {"id": nid, "title": t, "url": urllib.parse.urljoin(BASE, htmllib.unescape(href))}
        if d:
            item["date"] = d.group(1).strip()
        out.append(item)
    return out


def relevant(title_: str) -> bool:
    return bool(RELEVANT.search(title_))


def merge_news(old: list[dict], found: list[dict], today: str) -> tuple[list[dict], list[dict]]:
    """Every item ever seen, newest first (by the Assembly's number), each with the day first seen ("seen") and
    `relevant`; and the relevant ones new in this reading."""
    have = {x["id"]: x for x in old}
    new = []
    for f in found:
        if f["id"] in have:
            have[f["id"]].update({k: v for k, v in f.items() if k != "id"})
        else:
            have[f["id"]] = {**f, "seen": today, "relevant": relevant(f["title"])}
            if have[f["id"]]["relevant"]:
                new.append(have[f["id"]])
    for x in have.values():
        x["relevant"] = relevant(x["title"])
    return sorted(have.values(), key=lambda x: -int(x["id"])), new


def offices_of(*, speaker: tuple[str, list[str]] | None, vice: list[tuple[str, str]],
               chairs: list[tuple[str, str]], committees: list[tuple[str, str, list[dict]]],
               delegations: list[tuple[str, str, list[dict]]], sources: dict) -> list[dict]:
    """Every office read, one to a row: {"name", "kind", "role", "body", "group"?, "source"}. Kinds: speaker, vice,
    group, committee, delegation; "role" and "body" as the Assembly writes them."""
    out = []
    if speaker and speaker[0]:
        for r in speaker[1] or ["Председник Народне скупштине"]:
            out.append({"name": speaker[0], "kind": "speaker", "role": r, "body": "Народна скупштина",
                        "source": sources["speaker"]})
    for name, group in vice:
        out.append({"name": name, "kind": "vice", "role": "потпредседник", "body": "Народна скупштина",
                    "group": _group(group), "source": sources["vice"]})
    for name, group in chairs:
        out.append({"name": name, "kind": "group", "role": "председник", "body": "Посланичка група " + _group(group).strip('"„“'),
                    "source": sources["group"]})
    for kind, rows in (("committee", committees), ("delegation", delegations)):
        for body, url, members in rows:
            for m in members:
                out.append({"name": m["name"], "kind": kind, "role": m["role"], "body": body, "source": url,
                            **({"group": m["group"]} if m.get("group") else {})})
    return out


def keep_since(old: list[dict], found: list[dict], today: str) -> list[dict]:
    """Each office with the day it was first seen ("since"), kept from the last reading for one still listed."""
    def k(o):
        return (o["name"], o["kind"], o["role"], o["body"])
    had = {k(o): o.get("since", today) for o in old}
    return [{**o, "since": had.get(k(o), today)} for o in found]


def dumps(fetched: str, offices: list[dict], read_parts: str) -> str:
    """data/<N>/offices.json: one office to a line, so a change shows as a small diff."""
    rows = ",\n".join(json.dumps(o, ensure_ascii=False, sort_keys=True) for o in offices)
    return (f'{{"fetched": {json.dumps(fetched)}, "parts_read": {json.dumps(read_parts)}, '
            f'"offices": [\n{rows}\n]}}\n')


def dumps_news(fetched: str, items: list[dict]) -> str:
    rows = ",\n".join(json.dumps(x, ensure_ascii=False, sort_keys=True) for x in items)
    return f'{{"fetched": {json.dumps(fetched)}, "source": {json.dumps(NEWS, ensure_ascii=False)}, "items": [\n{rows}\n]}}\n'


# How the site says an office, in Latin after `latin`: "Predsednik Narodne skupštine", "Odbor za spoljne poslove:
# predsednik", "Delegacija u Interparlamentarnoj uniji: šef". The Assembly's own words, cased for a sentence.
def say(o: dict, latin) -> str:
    role = latin(o["role"]).strip()
    if o["kind"] == "speaker":
        return role[:1].upper() + role[1:]
    if o["kind"] == "vice":
        return "Potpredsednik Narodne skupštine"
    if o["kind"] == "group":
        return f"{latin(o['body'])}: predsednik"
    if o["kind"] == "delegation":
        role = re.sub(r"\s+делегације$", "", o["role"], flags=re.I)
        return f"{latin(o['body'])}: {latin(role).strip().lower()}"
    return f"{latin(o['body'])}: {role.lower()}"


# The order an MP's offices are listed in: the Assembly's own first, then the groups, the committees and the
# delegations; within each, chairs before members, then by name.
_KIND = {"speaker": 0, "vice": 1, "group": 2, "committee": 3, "delegation": 4}
_ROLE = ("председник", "шеф", "заменик председника", "заменик шефа", "члан", "заменик члана")


def order(o: dict) -> tuple:
    r = o["role"].lower()
    rank = next((i for i, x in enumerate(_ROLE) if r.startswith(x)), len(_ROLE))
    return (_KIND.get(o["kind"], 9), rank, o["body"])


def load(root) -> dict[str, list[dict]]:
    """{convocation: offices} from data/<N>/offices.json."""
    out = {}
    for p in sorted(root.glob("*/offices.json")):
        if p.parent.name.isdigit():
            out[p.parent.name] = json.loads(p.read_text(encoding="utf-8"))["offices"]
    return out


__all__ = ["SPEAKER", "VICE", "GROUP_CHAIRS", "COMMITTEES", "DELEGATIONS", "NEWS", "ARCHIVE", "person", "blocks",
           "parts", "committee", "delegation", "news", "merge_news", "offices_of", "keep_since", "say",
           "order", "load"]
