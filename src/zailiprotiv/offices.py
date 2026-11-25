"""Who holds which office in the Assembly, and the Assembly's news (20 Nov 2026, the maintainer's request: "the
election of committee members, the deputy Speakers, and so on", each office on the MP's page).

Read from the Assembly's own pages of its composition ("Састав"), not from the wording of its news:
- the Speaker: the Speaker's biography, an MP's page like any other (the name in `<h2>`, "Функција у Народној
  скупштини Републике Србије" a list);
- the deputy Speakers: their page, a block per person (name in `<h2>`, group in `<h3>`);
- the chairs of the parliamentary groups: their page, the same blocks;
- the committees: the list of committees links a page per committee, a table of rows "NAME (члан | председник |
  заменик председника), group, DEPUTY (заменик члана), group", a name bare in the archive and a link to the MP's page
  since the Fifteenth (read by the cell's lines of text, so either way);
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
from collections import Counter

from zailiprotiv.config import BASE

S = BASE + "/народна-скупштина/састав"
SPEAKER = S + "/председник/биографија-.2418.html"
VICE = S + "/потпредседници/потпредседници.9.html"
GROUP_CHAIRS = S + "/посланичке-групе-/председници-посланичких-група.869.html"
COMMITTEES = S + "/радна-тела/одбори.13.html"
DELEGATIONS = S + "/делегације/делегације.14.html"
NEWS = BASE + "/активности.42.html"
# The Speakers and deputy Speakers of every convocation since 1991, with the days they took office and left it: one
# table, the Assembly's own (23 Nov 2026).
HISTORY = BASE + "/народна-скупштина/скупштина-1804-2025/народна-скупштина-републике-србије-(1991-2026).2145.html"

# An earlier convocation's committees and delegations, as its archive pages list them. Only those whose rows read
# as the newest's do are listed here.
ARCHIVE = {
    "9": {"committees": S + "/радна-тела/сазив-од-31-маја-2012-године/одбори-.2196.html",
          "delegations": S + "/делегације/сазив-од-31-маја-2012-године.2203.html"},
    "10": {"committees": S + "/радна-тела/сазив-од-16-априла-2014-године/одбори.3430.html",
           "delegations": S + "/делегације/сазив-од-16-априла-2014-године.3419.html"},
    "11": {"committees": S + "/радна-тела/сазив-од-3-јуна-2016-година/одбори.4255.html",
           "delegations": S + "/делегације/сазив-од-3-јуна-2016-године.4337.html"},
    "12": {"committees": S + "/радна-тела/сазив-од-3-августа-2020-године.4559.html",
           "delegations": S + "/делегације/сазив-од-3-августа-2020-године.4562.html"},
    "13": {"committees": S + "/радна-тела/сазив-од-1-августа-2022-године.4841.html",
           "delegations": S + "/делегације/сазив-од-1-августа-2022-године-.4844.html"},
    "14": {"committees": S + "/радна-тела/сазив-од-6-фебруара-2024-године.5177.html",
           "delegations": S + "/делегације/сазив-од-6-фебруара-2024-године.5180.html"},
}

DAY = 24 * 3600  # the pages, while one gives fewer members than listed, are asked for again this often, not every hour
WEEK = 7 * DAY  # the committees' and delegations' pages are read again at least this often


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


def numbers(page: str, listing: str) -> dict[str, int]:
    """How many members the list says each body has, by its address ("Број чланова": a column of the committees' list,
    a line under a delegation's name). A body with no number beside it isn't named."""
    number = re.search(r"\.(\d+)\.html$", listing).group(1)
    out: dict[str, int] = {}
    url = ""
    for m in re.finditer(r'<a[^>]+?href="(?P<href>[^"]+\.\d+\.' + number + r'\.html)"|'
                         r'class="members_number">\s*<b>\s*(?P<a>\d+)|Број чланова:\s*(?P<b>\d+)', _content(page)):
        if m["href"]:
            url = urllib.parse.urljoin(BASE, htmllib.unescape(m["href"]))
        elif url:
            out.setdefault(url, int(m["a"] or m["b"]))
    return out


def _group(s: str) -> str:
    return re.sub(r"^Посланичка група\s*", "", _text(s)).strip()


def _cells(page: str) -> list[list[str]]:
    """The people's cells of a body's table, each as its lines of text. What stands around a name (a link to the MP's
    page since the Fifteenth, nothing in the archive) does not matter to it. A member without a deputy has a cell the
    page never closes: it runs on into the next one's, or to the table's end."""
    return [[_text(x) for x in re.split(r"<br\s*/?>", cell)]
            for cell in re.findall(r"<td[^>]*>\s*(<strong>.*?)(?:</td>|</table>)", _content(page), re.S)]


_ROLE_OF = re.compile(r"(?P<name>.*\S)\s*\(\s*(?P<role>[^()]+?)\s*\)")


def committee(page: str) -> list[dict]:
    """A committee's page → [{"name", "role", "group"}]: each member with their role (председник, заменик
    председника, члан) and each member's deputy (заменик члана). A cell's lines: NAME (role), group, DEPUTY (заменик
    члана), group."""
    out = []
    for lines in _cells(page):
        for who, group in zip(lines[::2], lines[1::2]):
            m = _ROLE_OF.fullmatch(who)
            if m:
                out.append({"name": m["name"], "role": m["role"], "group": _group(group)})
    return out


def delegation(page: str) -> list[dict]:
    """A delegation's page → [{"name", "role"}] (шеф Делегације, заменик шефа Делегације, члан Делегације …)."""
    return [{"name": lines[0], "role": lines[1]} for lines in _cells(page)
            if len(lines) > 1 and lines[0] and lines[1] and not _ROLE_OF.fullmatch(lines[0])]


def members(page: str) -> list[dict]:
    return committee(page) or delegation(page)


def keep_unread(old: list[dict], listed: dict[str, int], rows: list[tuple[str, str, list[dict]]], kind: str) -> list:
    """A body whose page gave nobody though the list says it has members keeps those read before (`unread` says it)."""
    return [(t, url, got or [{k: o[k] for k in ("name", "role", "group") if k in o} for o in old
                             if o["kind"] == kind and o["source"] == url and listed.get(url)]) for t, url, got in rows]


def unread(kept: dict, now) -> list[str]:
    """What data/<N>/offices.json shows was not read, a line each: the bodies whose pages gave fewer members than the
    Assembly lists, and a reading long overdue. Empty when all is well. (25 Nov 2026: names had become links, no
    committee of the Fifteenth was read for a week, and every run was green.)"""
    from datetime import datetime
    out = [f"- {url} (na spisku {kept['listed'][url]}, nije pročitano {n})" for url, n in kept.get("unread", {}).items()]
    read = kept.get("parts_read")
    if read and (now - datetime.fromisoformat(read)).total_seconds() > WEEK + DAY:
        out.append(f"- odbori i delegacije nisu čitani od {read[:10]}")
    return out


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


def compare(old: list[dict], found: list[dict]) -> tuple[list[dict], list[dict]]:
    """The rows of `found` that `old` hasn't and the rows of `old` that `found` hasn't; a row that stands twice counts
    twice."""
    def left(a, b):
        have = Counter((o["name"], o["kind"], o["role"], o["body"], o.get("group"), o["source"]) for o in b)
        out = []
        for o in a:
            k = (o["name"], o["kind"], o["role"], o["body"], o.get("group"), o["source"])
            if have[k]:
                have[k] -= 1
            else:
                out.append(o)
        return out
    return left(found, old), left(old, found)


def dumps(fetched: str, offices: list[dict], read_parts: str, listed: dict[str, int] | None = None,
          unread: dict[str, int] | None = None, lost: list[dict] | None = None) -> str:
    """data/<N>/offices.json: one office to a line, so a change shows as a small diff. `listed`: the bodies as listed
    when their pages were last read, with the numbers of members (None: an archive's as read before 25 Nov 2026); `unread`: those of
    them whose page gave fewer, with how many are missing; `lost`: an
    archive's rows a later reading did not find, which the file keeps. They stand on lines of their own: the workflow's commit passes over a change of
    "fetched" alone, and a reading that is not kept would be made again every hour."""
    rows = ",\n".join(json.dumps(o, ensure_ascii=False, sort_keys=True) for o in offices)
    if listed is None:
        return (f'{{"fetched": {json.dumps(fetched)}, "parts_read": {json.dumps(read_parts)}, '
                f'"offices": [\n{rows}\n]}}\n')

    def one(d):
        return json.dumps(d, ensure_ascii=False, sort_keys=True)
    gone = f'"lost": {one(lost)},\n' if lost else ""
    return (f'{{"fetched": {json.dumps(fetched)},\n"parts_read": {json.dumps(read_parts)},\n"listed": {one(listed)},\n'
            f'"unread": {one(unread or {})},\n{gone}"offices": [\n{rows}\n]}}\n')


def dumps_news(fetched: str, items: list[dict]) -> str:
    rows = ",\n".join(json.dumps(x, ensure_ascii=False, sort_keys=True) for x in items)
    return f'{{"fetched": {json.dumps(fetched)}, "source": {json.dumps(NEWS, ensure_ascii=False)}, "items": [\n{rows}\n]}}\n'


_MONTH = {m: i + 1 for i, m in enumerate(("јануара", "фебруара", "марта", "априла", "маја", "јуна", "јула", "августа",
                                           "септембра", "октобра", "новембра", "децембра"))}
_DATE = re.compile(r"(\d{1,2})\.\s+(" + "|".join(_MONTH) + r")\s+(\d{4})")
_ROMAN = {"VIII": "8", "IX": "9", "X": "10", "XI": "11", "XII": "12", "XIII": "13", "XIV": "14", "XV": "15"}


def _iso(text: str) -> str:
    m = _DATE.search(text)
    return f"{m[3]}-{_MONTH[m[2]]:02d}-{int(m[1]):02d}" if m else ""


def _people(cell: str) -> list[dict]:
    """A cell of the table → [{"name", "since", "until"}]. Each "од <date>" starts a list of names ("др" and the like
    as the table writes them); a name's own "(до …)" or "(од …)" stands after it. Names are left as written."""
    out: list[dict] = []
    for part in re.split(r"(?=<b>\s*од\s)", cell):
        head = re.match(r"<b>(.*?)</b>", part, re.S)
        if not head:
            continue
        since, until = _iso(head[1]), ""
        if " до " in " " + _text(head[1]) + " ":
            until = _iso(head[1].split(" до ")[-1])
        rest = re.sub(r"\s+", " ", _text(part[head.end():]))
        for m in re.finditer(r"([^,()]+?)\s*(\([^)]*\))?\s*(?:,|\sи\s(?=[А-ЯЉЊЂЋЏ])|$)", rest):
            name = re.sub(r"^\s*и\s+", "", m[1]).strip(" :;.")
            if not name:
                continue
            note = m[2] or ""
            row = {"name": name, "since": since, "until": until}
            if note.startswith("(од") or " од " in note:
                row["since"] = _iso(note.split("до")[0]) or since
            if "до" in note:
                row["until"] = _iso(note.split("до")[-1]) or until
            out.append(row)
    return out


def history(page: str) -> list[dict]:
    """Who was the Speaker and who were the deputy Speakers of each convocation → [{"conv", "kind" (speaker, vice),
    "name", "since", "until"}], "until" "" when the table gives none (the term ran to the convocation's end)."""
    out = []
    body = _content(page)
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", body, re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        m = re.search(r"<b>\s*([XIV]+)\s+сазив", cells[0]) if len(cells) >= 3 else None
        if not m or m[1] not in _ROMAN:
            continue
        for kind, cell in (("speaker", cells[1]), ("vice", cells[2])):
            out += [{"conv": _ROMAN[m[1]], "kind": kind, **p} for p in _people(cell)]
    return out


def with_history(offices_: list[dict], found: list[dict], conv: str) -> list[dict]:
    """A convocation's offices with its Speaker and deputies from `history`: the newest's, read from their pages, get
    the day they took office; an earlier one's are added whole (their rows "dated", as no other office's day is known)."""
    mine = [h for h in found if h["conv"] == conv]
    if not mine:
        return offices_
    others = [o for o in offices_ if o["kind"] not in ("speaker", "vice")]
    rows = [{"name": h["name"], "kind": h["kind"], "role": "Председник Народне скупштине" if h["kind"] == "speaker" else "потпредседник",
             "body": "Народна скупштина", "source": HISTORY, "since": h["since"], "until": h["until"], "dated": True} for h in mine]
    if any(o["kind"] in ("speaker", "vice") for o in offices_):  # the pages of those who hold it now stay the source
        day = {(mp_key(h["name"]), h["kind"]): h for h in mine}
        kept = []
        for o in offices_:
            h = day.get((mp_key(o["name"]), o["kind"])) if o["kind"] in ("speaker", "vice") else None
            kept.append({**o, "since": h["since"], "until": h["until"], "dated": True} if h else o)
        known = {(mp_key(o["name"]), o["kind"]) for o in kept}
        return kept + [r for r in rows if (mp_key(r["name"]), r["kind"]) not in known]
    return rows + others


def mp_key(name: str) -> str:
    """A name in any order and either script, titles left out → one key."""
    from zailiprotiv.translit import latin
    words = re.sub(r"[^a-zčćžšđ ]", " ", latin(name).lower()).split()
    return " ".join(sorted(w for w in words if w not in ("prof", "dr", "mr", "doc", "prim")))


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
           "parts", "numbers", "members", "committee", "delegation", "unread", "news", "merge_news", "offices_of", "keep_since", "say",
           "order", "load"]
