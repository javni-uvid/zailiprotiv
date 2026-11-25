"""The National Assembly's website: its sittings and the roll-call PDF of every vote taken at them.

The Assembly publishes each roll-call vote as a PDF under /upload/rezultati_glasanja/ (since autumn 2025, for
example /upload/rezultati_glasanja/2026/20.pdf) or, before, /upload/archive/files/cir/doc/Listinzi/<year>/. Only the Cyrillic
pages of the sittings link to them (`….43.html`; the Latin pages, `….941.html`, don't): each agenda item's text is
a link to its vote. The sittings of the current convocation are listed on two Cyrillic pages, one for regular and
one for extraordinary sittings."""

from __future__ import annotations

import datetime as dt
import http.client
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from html import unescape
from html.parser import HTMLParser

from zailiprotiv import months
from zailiprotiv.config import BASE, CONVOCATIONS, DELAY, ORDINALS, USER_AGENT, VOTES_PATHS
from zailiprotiv.translit import latin

# The current convocation's sittings: regular, then extraordinary.
LISTINGS = CONVOCATIONS["14"]["listings"]  # the same pages serve the current convocation, whichever it is


class FetchError(RuntimeError):
    pass


def ascii_url(url: str) -> str:
    """url with non-ASCII characters percent-encoded (the site has Cyrillic paths), and nothing encoded twice."""
    parts = urllib.parse.urlsplit(url)
    host = parts.hostname.encode("idna").decode() if parts.hostname else ""
    netloc = host + (f":{parts.port}" if parts.port else "")
    path = urllib.parse.quote(parts.path, safe="/%:@!$&'()*+,;=~")
    query = urllib.parse.quote(parts.query, safe="=&%:@!$'()*+,;/?~")
    return urllib.parse.urlunsplit((parts.scheme, netloc, path, query, ""))


_asked: dict[str, float] = {}  # when each host last answered (time.monotonic)


def _wait_turn(url: str) -> None:
    """Ask the Assembly little: at least DELAY seconds between the end of one request to a host and the next."""
    host = urllib.parse.urlsplit(url).hostname or ""
    if host in _asked:
        gap = DELAY - (time.monotonic() - _asked[host])
        if gap > 0:
            time.sleep(gap)


def fetch(url: str, timeout: float = 60, tries: int = 3) -> bytes:
    """The body at url, retried on network errors and server errors; a 4xx is not retried. Requests name the project
    in the User-Agent and wait their turn (_wait_turn), so callers need not wait between pages themselves."""
    try:
        return _fetch(url, timeout, tries)
    finally:
        _asked[urllib.parse.urlsplit(url).hostname or ""] = time.monotonic()


def _fetch(url: str, timeout: float, tries: int) -> bytes:
    last = None
    for attempt in range(tries):
        _wait_turn(url)
        request = urllib.request.Request(ascii_url(url), headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as e:
            last = e
            if e.code < 500:
                break
        except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.IncompleteRead) as e:
            last = e
        except (ValueError, http.client.HTTPException) as e:  # a malformed address or reply: not worth retrying
            raise FetchError(f"{url}: {e}") from e
        time.sleep(2 * (attempt + 1))
    raise FetchError(f"{url}: {last}")


class _Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hrefs: list[tuple[str, str]] = []
        self._open: list[int] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.hrefs.append((href, ""))
                self._open.append(len(self.hrefs) - 1)

    def handle_data(self, data):
        for i in self._open:
            href, text = self.hrefs[i]
            self.hrefs[i] = (href, text + data)

    def handle_endtag(self, tag):
        if tag == "a" and self._open:
            self._open.pop()


def links(html: str, base: str) -> list[tuple[str, str]]:
    """(absolute URL, link text) for every link in the page, without fragments, in page order."""
    parser = _Links()
    parser.feed(html)
    out = []
    for href, text in parser.hrefs:
        href = unescape(href.strip())
        if href.startswith(("mailto:", "tel:", "javascript:")):
            continue
        url, _ = urllib.parse.urldefrag(urllib.parse.urljoin(base, href))
        out.append((url, " ".join(text.split())))
    return out


def is_vote_pdf(url: str) -> bool:
    path = urllib.parse.unquote(urllib.parse.urlsplit(url).path)
    return any(p.lower() in path.lower() for p in VOTES_PATHS) and path.lower().endswith(".pdf")


def is_sitting(url: str, text: str) -> bool:
    """A link to a sitting's Cyrillic page. The listings also carry other news in their margins."""
    path = urllib.parse.unquote(urllib.parse.urlsplit(url).path)
    t = text.lower()
    return path.endswith(".43.html") and ("седниц" in t or "заседањ" in t)


@dataclass
class Vote:
    item: str  # the agenda item's text as the sitting's page gives it
    pdf: str


@dataclass
class Sitting:
    url: str
    title: str
    votes: list[Vote] = field(default_factory=list)
    agenda: list[str] = field(default_factory=list)  # the items it was convened for, as its page lists them
    starts: str = ""  # "2026-08-24T10:00", from the notice that convened it
    continues: str = ""  # "2026-11-25T10:00", when its page says the Assembly goes on with it


_MONTHS = months.CYR


def _month(word: str) -> int:
    """1-12 from a month's name, as it is ("новембар") or in a sentence ("новембра"); 0 when it is none."""
    return next((i for i, m in enumerate(zip(months.NAMES, months.OF), 1) if latin(word).lower() in m), 0)


# A sitting's title as the Assembly lists it: "Друга седница …", "Прва посебна седница …", "Десето ванредно заседање …",
# never a piece of news about one ("Одржане консултације уочи конститутивне седнице …").
_SITTING = re.compile(r"^(?:prv|drug|treć|četvrt|pet|šest|sedm|osm|devet|deset|\w+naest|\w+deset)\w*(?:\s\w+){0,2}\s"
                      r"(?:sednica|zasedanje)\b.*\bNarodne skupštine", re.I)


def sitting_title(title: str) -> bool:
    return bool(_SITTING.match(" ".join(latin(title).split())))


def convened(html: str) -> str:
    """When a sitting was convened for, from its page's notice: "… за понедељак, 24. август 2026. године, са почетком
    у 10.00 часова". The day alone when no hour is given; empty when the notice has no day. A notice with no year ("за
    среду, 17. јун, са почетком", June 2026) has the year of the page's own date, when the named day of the week is then
    that date's."""
    m = re.search(r'class="preamble"[^>]*>(.*?)</p>', html, flags=re.S)
    text = re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", m.group(1) if m else "")))
    d = re.search(r"за\s+(?:(\w+),\s*)?(\d{1,2})\.\s*([^\W\d]+)(?:\s+(\d{4})\b|(?=,))", text)
    month = _month(d.group(3)) if d else 0
    if not month:
        return ""
    year = d.group(4)
    if not year:
        posted = re.search(r'class="posted"[^>]*>[^<]*?(\d{4})\.', html[:m.start()][-3000:])
        try:
            at = dt.date(int(posted.group(1)), month, int(d.group(2))) if posted else None
        except ValueError:
            at = None
        if not at or (d.group(1) or "").lower() != _DAYS_IN[at.weekday()]:
            return ""
        year = posted.group(1)
    day = f"{year}-{month:02d}-{int(d.group(2)):02d}"
    h = re.search(r"почетком у (\d{1,2})(?:[.:,](\d{2})|(?=\s*(?:час|сат)))", text[d.end():])
    return f"{day}T{int(h.group(1)):02d}:{h.group(2) or '00'}" if h else day


_DAYS_IN = ("понедељак", "уторак", "среду", "четвртак", "петак", "суботу", "недељу")
_GOES_ON = re.compile(r"\b(?:наставља|наставиће)(?:\s+се)?(?:\s+(?:са\s+)?рад(?:ом)?)?,?\s+у\s+(\w+),?\s+"
                      r"(\d{1,2})\.\s*(\w+)\s+(\d{4})\.(?:\s*године)?,?"
                      r"(?:\s+са\s+почетком)?(?:\s+у\s+(\d{1,2})(?:[.:,](\d{2}))?\s*(?:час|сат))?", re.I)


def continues(html: str) -> str:
    """When the Assembly goes on with a sitting already begun, as the sitting's page says at the end of a day: "Народна
    скупштина наставља рад у среду, 25. новембра 2026. године, са почетком у 10.00 часова" (25 Nov 2026), "наставља са
    радом у уторак, 24. новембра 2026. године, у 10.00 часова" (20 Nov). The latest such day with its hour, the day
    alone when no hour is given, empty when none is said. A sentence whose day of the week is not its date's is not
    read: which of the two is meant is not for us to say."""
    text = re.sub(r"<[^>]+>", " ", re.sub(r"<!--.*?-->", " ", html, flags=re.S))
    text = re.sub(r"\s+", " ", unescape(text))
    found = []
    for weekday, d, word, y, h, minute in _GOES_ON.findall(text):
        try:
            at = dt.datetime(int(y), _month(word), int(d), int(h or 0), int(minute or 0))
        except ValueError:
            continue
        if weekday.lower() == _DAYS_IN[at.weekday()]:
            found.append(at.strftime("%Y-%m-%dT%H:%M" if h else "%Y-%m-%d"))
    return max(found, default="")


_AGENDA = re.compile(r"\bдневни ред\b[^:]{0,200}:\s*(.*)$", re.I)


def _told(html: str) -> list[str]:
    """The agenda told in the page's lines, not in a list (agenda); empty when it is not."""
    text = re.sub(r"<!--.*?-->|<script\b.*?</script\b[^>]*>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<br\b[^>]*>|</(?:div|p|li|ol|h\d)>", "\n", re.sub(r"\s+", " ", text), flags=re.I)
    lines = [" ".join(unescape(re.sub(r"<[^>]+>", " ", x)).split()) for x in text.split("\n")]
    lines = [x for x in lines if x]
    at = next(((i, m) for i, x in enumerate(lines) if (m := _AGENDA.search(x))), None)
    if not at:
        return []
    i, m = at
    if m.group(1):  # one item, in the same line: to the sentence's end (not an abbreviation's: "Њ. Е. Сакр Гобаша")
        if re.match(r"1\s*[.)]", m.group(1)):
            return []  # several in one line: not read
        return [re.split(r"(?<=\w{4})\.\s+(?=[А-ЯЂЈЉЊЋЏ])", m.group(1))[0].strip(" ;.")]
    out = []
    for line in lines[i + 1:]:
        n = re.match(rf"{len(out) + 1}(?!\d)\s*[.)]?\s*(?=[^\W\d])(.+)$", line)
        if not n:
            break
        out.append(n.group(1).strip(" ;."))
    return out


def agenda(html: str) -> list[str]:
    """The items a sitting was convened for. After the words "дневни ред … :" of its page: the item said in that line
    ("дневни ред са једном тачком и то: …", "следећи дневни ред: Полагање заклетве …"), or the lines numbered from 1
    ("1.Предлог закона …", July 2026). Otherwise the first numbered list that links no roll calls (the list of results,
    further down, links one per item)."""
    start = html.find('class="preamble"')
    told = _told(html[max(start, 0):])
    if told:
        return told
    for block in re.findall(r"<ol\b.*?</ol>", html[max(start, 0):], flags=re.S | re.I):
        if any(p.lower() in urllib.parse.unquote(block).lower() for p in VOTES_PATHS):
            continue
        items = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", li)).strip(" ;.") for li in
                 re.findall(r"<li\b[^>]*>(.*?)</li>", block, flags=re.S | re.I)]
        return [i for i in items if i]
    return []


def sittings(get: Callable[[str], bytes] = fetch, listings=LISTINGS) -> list[Sitting]:
    """Every sitting the listings link to, once, in the listings' order."""
    out, seen = [], set()
    for listing in listings:
        for url, text in links(get(listing).decode("utf-8", "replace"), listing):
            if is_sitting(url, text) and url not in seen:
                seen.add(url)
                out.append(Sitting(url, text))
    return out


def other_convocation(title: str, ordinal: str) -> bool:
    """A sitting whose title names another convocation ("… у Четрнаестом сазиву" listed in the Thirteenth's
    archive, or a notice of the Fifteenth's first sitting among the Fourteenth's)."""
    t = latin(title).lower()
    return any(f"{o}om sazivu" in t or f"{o}og saziva" in t for o in ORDINALS if o != ordinal)


def archive_sittings(listing: str, get: Callable[[str], bytes] = fetch) -> list[Sitting]:
    """An earlier convocation's sittings, from its archive page in Latin and the pages after it (?offset=N). A
    sitting's Latin page ("….53525.941.html") has a Cyrillic twin with the next lower number ("….53524.43.html"),
    which is the one linking the roll calls; the site ignores the words before the number."""
    out, seen, pages, todo = [], set(), set(), [listing]
    while todo:
        page = todo.pop(0)
        if page in pages:
            continue
        pages.add(page)
        for url, text in links(get(page).decode("utf-8", "replace"), page):
            if "offset=" in url and url.split("?")[0] == listing.split("?")[0] and url not in pages:
                todo.append(url)
            m = re.search(r"\.(\d+)\.941\.html$", urllib.parse.unquote(url))
            low = latin(text).lower()
            if m and ("sednic" in low or "zasedanj" in low):
                cyr = f"{BASE}/sednica.{int(m.group(1)) - 1}.43.html"
                if cyr not in seen:
                    seen.add(cyr)
                    out.append(Sitting(cyr, text))
    return out


def votes(html: str, base: str) -> list[Vote]:
    """The agenda items of a sitting's page that link to a roll call, in page order, each PDF once."""
    out, seen = [], set()
    for url, text in links(html, base):
        if is_vote_pdf(url) and url not in seen:
            seen.add(url)
            out.append(Vote(text.rstrip(" ;."), url))
    return out


def index(get: Callable[[str], bytes] = fetch, convocation: str = "14") -> tuple[list[Sitting], list[str]]:
    """A convocation's sittings with their roll calls, and the titles of sittings listed among them that belong to a
    later convocation (a newer one has begun)."""
    conf = CONVOCATIONS[convocation]
    found = archive_sittings(conf["archive"], get) if "archive" in conf else sittings(get, conf["listings"])
    later = [s.title for s in found if later_convocation(s.title, conf["ordinal"])]
    found = [s for s in found if not other_convocation(s.title, conf["ordinal"])]
    for sitting in found:
        page = get(sitting.url).decode("utf-8", "replace")
        sitting.votes, sitting.agenda, sitting.starts = votes(page, sitting.url), agenda(page), convened(page)
        sitting.continues = continues(page)
    later += [s.title for s in found if s.starts and s.starts[:10] >= conf.get("to", "9999")]
    return [s for s in found if within(s.starts, conf)], later


def news_of(known: dict, now: dict) -> list[tuple[str, str]]:
    """What the maintainer is told of when the listing is read (25 Nov 2026): a sitting newly listed, or one not voted at
    yet whose day or agenda has come or changed: [(a line to head it, the words below)], in Latin, with the Assembly's
    page. Nothing on the first reading, when every sitting would be new."""
    out = []
    for url, s in now.items() if known else ():
        if not sitting_title(s["title"]) or s["votes"]:
            continue
        before = known.get(url)
        if before and (before.get("starts"), before.get("agenda")) == (s["starts"], s["agenda"]):
            continue
        items = [f"{i}. {x}" for i, x in enumerate(s["agenda"], 1)] or ["Dnevni red nije pročitan sa strane."]
        head = f"Sednica na sajtu Skupštine: {s['title'].split(' Народне скупштине')[0]}"
        body = "\n".join(["Nova na spisku." if not before else "Promenjen dan ili dnevni red.",
                          f"Počinje: {s['starts'] or 'dan nije pročitan sa strane'}", url, "", *items, ""])
        # an "@" in the Assembly's words must call nobody on GitHub
        out.append((latin(head).replace("@", ""), "\n".join(x if x.startswith("http") else latin(x) for x in body.split("\n")).replace("@", "")))
    return out


def later_convocation(title: str, ordinal: str) -> bool:
    """A sitting whose title names a convocation after this one."""
    t = latin(title).lower()
    return any(f"{o}om sazivu" in t or f"{o}og saziva" in t for o in ORDINALS[ORDINALS.index(ordinal) + 1:])


def within(day: str, conf: dict) -> bool:
    """Whether a day (a sitting's start, a law's adoption) falls in a convocation's own dates; one without a day is
    kept, and left to the title's ordinal."""
    return not day or conf.get("from", "") <= day[:10] < conf.get("to", "9999")
