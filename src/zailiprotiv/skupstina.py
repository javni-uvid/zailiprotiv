"""The National Assembly's website: its sittings and the roll-call PDF of every vote taken at them.

The Assembly publishes each roll-call vote as a PDF under /upload/rezultati_glasanja/ (since autumn 2025, for
example /upload/rezultati_glasanja/2026/20.pdf) or, before, /upload/archive/files/cir/doc/Listinzi/<year>/. Only the Cyrillic
pages of the sittings link to them (`….43.html`; the Latin pages, `….941.html`, don't): each agenda item's text is
a link to its vote. The sittings of the current convocation are listed on two Cyrillic pages, one for regular and
one for extraordinary sittings."""

from __future__ import annotations

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

from zailiprotiv.config import BASE, CONVOCATIONS, DELAY, ORDINALS, USER_AGENT, VOTES_PATHS
from zailiprotiv.translit import latin

# The current convocation's sittings: regular, then extraordinary.
LISTINGS = CONVOCATIONS["14"]["listings"]


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


def fetch(url: str, timeout: float = 60, tries: int = 3) -> bytes:
    """The body at url, retried on network errors and server errors; a 4xx is not retried."""
    last = None
    for attempt in range(tries):
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


_MONTHS = ("јануар", "фебруар", "март", "април", "мај", "јун", "јул", "август", "септембар", "октобар", "новембар",
           "децембар")


def convened(html: str) -> str:
    """When a sitting was convened for, from its page's notice: "… за понедељак, 24. август 2026. године, са почетком
    у 10.00 часова". The day alone when no hour is given; empty when the notice has no day."""
    m = re.search(r'class="preamble"[^>]*>(.*?)</p>', html, flags=re.S)
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m.group(1) if m else ""))
    d = re.search(r"за\s+(?:\w+,\s*)?(\d{1,2})\.\s*(\w+)\s+(\d{4})\.", text)
    if not d or d.group(2).lower() not in _MONTHS:
        return ""
    day = f"{d.group(3)}-{_MONTHS.index(d.group(2).lower()) + 1:02d}-{int(d.group(1)):02d}"
    h = re.search(r"почетком у (\d{1,2})[.:,](\d{2})", text[d.end():])
    return f"{day}T{int(h.group(1)):02d}:{h.group(2)}" if h else day


def agenda(html: str) -> list[str]:
    """The items a sitting was convened for: the first numbered list of its page that links no roll calls (the list
    of results, further down, links one per item)."""
    start = html.find('class="preamble"')
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


def archive_sittings(listing: str, get: Callable[[str], bytes] = fetch, delay: float = DELAY) -> list[Sitting]:
    """An earlier convocation's sittings, from its archive page in Latin and the pages after it (?offset=N). A
    sitting's Latin page ("….53525.941.html") has a Cyrillic twin with the next lower number ("….53524.43.html"),
    which is the one linking the roll calls; the site ignores the words before the number."""
    out, seen, pages, todo = [], set(), set(), [listing]
    while todo:
        page = todo.pop(0)
        if page in pages:
            continue
        pages.add(page)
        if len(pages) > 1:
            time.sleep(delay)
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


def index(get: Callable[[str], bytes] = fetch, delay: float = DELAY, convocation: str = "14") -> list[Sitting]:
    """A convocation's sittings with their roll calls."""
    conf = CONVOCATIONS[convocation]
    found = archive_sittings(conf["archive"], get, delay) if "archive" in conf else sittings(get, conf["listings"])
    found = [s for s in found if not other_convocation(s.title, conf["ordinal"])]
    for sitting in found:
        time.sleep(delay)
        page = get(sitting.url).decode("utf-8", "replace")
        sitting.votes, sitting.agenda, sitting.starts = votes(page, sitting.url), agenda(page), convened(page)
    return found
