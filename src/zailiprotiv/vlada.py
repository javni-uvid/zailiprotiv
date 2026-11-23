"""Who the Assembly elected to the Government, and dismissed (23 Nov 2026, the maintainer: an MP's offices, "itd.").

The source is the Assembly's own decisions ("Акти → Остала акта → Донета акта"): electing a Government (its President
and its members, each with the post), members or one minister, and dismissing one. Their texts say the day, the name
and the post; the convocation is the one sitting that day. Kept in data/vlada.json, one decision to a line.

The day an office ended is kept only when a decision says it (a dismissal, "разрешава се"): a resignation, or a new
Government's election, says nothing of when a given minister left (Ana Brnabić became the Speaker on 20 March 2024 and
the next Government was elected on 2 May). The decisions before 2012 are not read: the site begins with the 9th.
"""
from __future__ import annotations

import html as htmllib
import json
import re
import urllib.parse

from zailiprotiv.config import BASE

LIST = BASE + "/акти/остала-акта/донета-акта"
LISTS = {"9": LIST + "/у-сазиву-од-31-маја-2012.2202.html", "10": LIST + "/у-сазиву-од-16-априла-2014.3407.html",
         "11": LIST + "/у-сазиву-од-3-јуна-2016.4238.html", "12": LIST + "/у-сазиву-од-3-августа-2020.4681.html",
         "13": LIST + "/у-сазиву-од-1-августа-2022.4958.html", "14": LIST + "/сазив-од-6-фебруара-2024.5290.html",
         "15": LIST + "/донета-акта.48.html"}
# The day each convocation was constituted: a decision is of the convocation sitting on its day.
SINCE = {"9": "2012-05-31", "10": "2014-04-16", "11": "2016-06-03", "12": "2020-08-03", "13": "2022-08-01",
         "14": "2024-02-06", "15": "2026-11-17"}
TITLE = re.compile(r"^[ОO]длук[аa] о (избору (чланова |члана )?Владе|избору министр|разрешењу (члана Владе|министр))", re.I)

_MONTHS = ("јануара", "фебруара", "марта", "априла", "маја", "јуна", "јула", "августа", "септембра", "октобра",
           "новембра", "децембра")
_DAY = re.compile(r"одржаној\s+(\d{1,2})\.\s+(" + "|".join(_MONTHS) + r")\s+(\d{4})\.")


def decisions(page: str) -> list[tuple[str, str]]:
    """The list's page → [(title, address)] of the decisions about the Government, in the page's order."""
    out = []
    for href, t in re.findall(r"<a[^>]+?href=[\"']([^\"']+/ostala_akta/[^\"']+)[\"'][^>]*>(.*?)</a>", page, re.S):
        title = re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", t))).strip()
        if TITLE.match(title):
            out.append((title, urllib.parse.urljoin(BASE, htmllib.unescape(href))))
    return out


def conv_of(day: str) -> str:
    return max((c for c, d in SINCE.items() if d <= day), key=int, default="")


def _name(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip(" ,;.")


def parse(text: str) -> dict | None:
    """A decision's text → {"date", "kind" ("izbor", "razresenje"), "people": [{"name", "post"}]}, names and posts as
    the decision writes them ("министра спољних послова"); None when it is no such decision."""
    t = re.sub(r"(?:\f|\^L)[ \t]*\d+[ \t]*\r?\n", "\n", text)  # a page's number at the head of the next
    t = re.sub(r"\f|\^L", " ", t)
    flat = re.sub(r"\s+", " ", t)
    d = _DAY.search(flat)
    if not d:
        return None
    day = f"{d[3]}-{_MONTHS.index(d[2]) + 1:02d}-{int(d[1]):02d}"
    people: list[dict] = []
    m = re.search(r"Разрешава се (.+?) (?:функције|дужности) (?:члана Владе\s*[–-]\s*)?((?:министр|потпредседник)\S* .+?)\.", flat)
    if m:
        return {"date": day, "kind": "razresenje", "people": [{"name": _name(m[1]), "post": _name(m[2])}]}
    m = re.search(r"За (председника Владе(?: и министр\S+ .+?)?) бира се (.+?)\.(?= |$)", flat)
    if m:
        # "др Ђуро Мацут." : a title's full stop is not the sentence's end
        rest = flat[m.start(2):]
        who = re.match(r"((?:(?:проф|др|мр|доц)\.?\s*)*[^.]+)\.", rest)
        people.append({"name": _name(who[1]), "post": m[1]})
    m = re.search(r"За чланове Владе бирају се:(.*?)Ову одлуку објавити", flat)
    if m:
        body, want, pos = m[1], 1, 0
        marks = []
        for k in re.finditer(r"(?<!\d)(\d{1,2})\.\s+(?=[А-Яа-яЂЈЉЊЋЏђјљњћџ])", body):
            if int(k[1]) == want:  # the numbers in their order: a number inside a post is no item
                marks.append((k.start(), k.end()))
                want += 1
        for i, (_, end) in enumerate(marks):
            item = body[end: marks[i + 1][0] if i + 1 < len(marks) else len(body)]
            x = re.match(r"(.+?)\s*,\s*за\s+(.+)$", item.strip())
            if not x or re.search(r"\d{1,2}\.\s+\S+ \S+.*?, за ", x[2]):
                raise ValueError(f"an item of the list not read: {item[:80]}")  # never a shorter list, silently
            if x:
                post = re.sub(r"\s+и$", "", _name(re.sub(r"\s+[IVХШПИ]{1,3}\s*$|\s+[шП]\s*$", "", x[2].strip())))
                people.append({"name": _name(x[1]), "post": _name(post)})
    if not people:
        m = re.search(r"За (министр\S+ .+?)(?: у Влади Републике Србије)? бира се ((?:(?:проф|др|мр|доц)\.?\s*)*[^.]+)\.", flat)
        if m:
            people.append({"name": _name(m[2]), "post": _name(m[1])})
    return {"date": day, "kind": "izbor", "people": people} if people else None


# A post as the decisions write it, in the accusative ("првог потпредседника Владе и министра спољних послова"), said
# as the person's office.
_SAY = ((r"^председника Владе", "Председник Владе"), (r"^првог потпредседника(?: Владе)?", "Први потпредседник Владе"),
        (r"^потпредседницу(?: Владе)?", "Потпредседница Владе"),
        (r"^пот?п?редседника(?: Владе)?", "Потпредседник Владе"),  # "потредседника", as one decision has it (2014)
        (r"^министарку ", "Министарка "), (r"^министра ", "Министар "),
        (r" и министарку ", " и министарка "), (r" и министра ", " и министар "))


def say(post: str) -> str:
    """"првог потпредседника Владе и министра спољних послова" → "Први потпредседник Владе и министар спољних послова"
    (Cyrillic; the caller writes it in Latin)."""
    out = re.sub(r"\s+", " ", post).strip()
    for a, b in _SAY:
        out = re.sub(a, b, out)
    return out


def merge(old: list[dict], found: list[dict]) -> list[dict]:
    """Every decision once (by its address), oldest first."""
    by = {d["url"]: d for d in old}
    by.update({d["url"]: d for d in found})
    return sorted(by.values(), key=lambda d: (d["date"], d["url"]))


def dumps(items: list[dict]) -> str:
    rows = ",\n".join(json.dumps(d, ensure_ascii=False, sort_keys=True) for d in items)
    return '{"decisions": [\n' + rows + "\n]}\n"


def offices(items: list[dict]) -> list[dict]:
    """The decisions as offices: one per person and decision that elected them, with the day, the convocation, and the
    end when a later decision dismissed the same person from the same post: {"name", "kind": "vlada", "post", "since",
    "until", "conv", "source"}. A name is as the decision writes it."""
    out = []
    for d in sorted(items, key=lambda x: x["date"]):
        for p in d["people"]:
            if d["kind"] == "izbor":
                out.append({"name": p["name"], "kind": "vlada", "post": p["post"], "since": d["date"], "until": "",
                            "conv": conv_of(d["date"]), "source": d["url"]})
            else:
                from zailiprotiv.offices import mp_key
                for o in reversed(out):
                    if mp_key(o["name"]) == mp_key(p["name"]) and not o["until"] and _same(o["post"], p["post"]):
                        o["until"] = d["date"]
                        break
    return out


MARGIN = 10  # days between the end of an MP's mandate and the election to the Government


def confirmed(items: list[dict], listed: dict[str, list[dict]], reviewed: dict) -> set[str]:
    """The keys (offices.mp_key) of the Government's members who are an MP of the same name for sure, never for the
    name alone: the MP's mandate, as the Assembly's archive of MPs gives it ("16.04.2014 - 27.04.2014."), ended within
    MARGIN days of an election to the Government; or a person looked at by hand (data/vlada_isti.json, "isti": the
    MP's year of birth in the archive and the minister's on the page named are the same; "drugi", two people of one
    name). The page named only checks who is who; no office is taken from it."""
    import datetime as dt

    from zailiprotiv.offices import mp_key
    ends: dict[str, list[dt.date]] = {}
    for rows in listed.values():
        for r in rows:
            m = re.search(r"-\s*(\d{2})\.(\d{2})\.(\d{4})", str(r.get("place", "")))
            if m:
                ends.setdefault(mp_key(r["name"].replace("-", " ")), []).append(dt.date(int(m[3]), int(m[2]), int(m[1])))
    out = {mp_key(n.replace("-", " ")) for n in reviewed.get("isti", [])}
    for o in offices(items):
        k = mp_key(o["name"].replace("-", " "))
        if any(abs((e - dt.date.fromisoformat(o["since"])).days) <= MARGIN for e in ends.get(k, [])):
            out.add(k)
    return out - {mp_key(n.replace("-", " ")) for n in reviewed.get("drugi", [])}


def load(root) -> tuple[list[dict], dict]:
    """(the decisions, the people looked at by hand) from data/vlada.json and data/vlada_isti.json."""
    from zailiprotiv import jsonfile
    return jsonfile.load(root / "vlada.json", {}).get("decisions", []), jsonfile.load(root / "vlada_isti.json", {})


def _same(a: str, b: str) -> bool:
    """Two wordings of one post: the ministry named in both."""
    def core(s: str) -> str:
        return re.sub(r"^(?:.*?\bи )?министр\S*\s+", "", re.sub(r"\s+", " ", s)).strip()
    return core(a) == core(b)
