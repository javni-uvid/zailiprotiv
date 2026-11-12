"""The National Assembly's website: fetching pages and finding the roll-call PDFs they link to.

The Assembly publishes each roll-call vote as a PDF under /upload/rezultati_glasanja/ (for example
/upload/rezultati_glasanja/2026/20.pdf or /upload/rezultati_glasanja/2026/osma_sednica/1.pdf). Which pages list
them is not known yet: `crawl` walks the site from a start page, following the links most likely to lead to
sittings and votes first, and records every such PDF with the pages that link to it."""

from __future__ import annotations

import heapq
import http.client
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from html import unescape
from html.parser import HTMLParser

from zailiprotiv.config import BASE, DELAY, USER_AGENT, VOTES_PATH


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
    return VOTES_PATH in path and path.lower().endswith(".pdf")


def same_site(url: str) -> bool:
    host = urllib.parse.urlsplit(url).hostname or ""
    return host.removeprefix("www.") == urllib.parse.urlsplit(BASE).hostname.removeprefix("www.")


# Words in a link's address or text that make it likelier to lead to sittings and votes (both scripts).
_LEADS = ("седниц", "sednic", "заседањ", "zasedanj", "гласањ", "glasanj", "активност", "aktivnost",
          "пленарн", "plenarn", "дневни-ред", "dnevni-red")
# Earlier convocations come last: the current one is read first (and the archive is large).
_LATER = ("архив", "arhiv", "сазив-од", "saziv-od")
# Files and sections that never lead there.
_SKIP = (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".jpg", ".jpeg", ".png", ".gif", ".zip", ".mp4", "/upload/")


def _score(url: str, text: str) -> int:
    s = (urllib.parse.unquote(url) + " " + text).lower()
    return sum(word in s for word in _LEADS) - 10 * any(word in s for word in _LATER)


@dataclass
class Crawl:
    pdfs: dict[str, set[str]] = field(default_factory=dict)  # vote PDF -> pages linking to it
    visited: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)


def crawl(start: str, max_pages: int = 80, delay: float = DELAY,
          get: Callable[[str], bytes] = fetch) -> Crawl:
    """Walk the site from start, best leads first, reading at most max_pages pages."""
    result = Crawl()
    queue: list[tuple[int, int, str]] = [(0, 0, start)]
    seen = {start}
    order = 1
    while queue and len(result.visited) < max_pages:
        _, _, url = heapq.heappop(queue)
        if result.visited:
            time.sleep(delay)
        try:
            body = get(url)
        except FetchError as e:
            result.failed.append((url, str(e)))
            continue
        result.visited.append(url)
        for link, text in links(body.decode("utf-8", "replace"), url):
            if is_vote_pdf(link):
                result.pdfs.setdefault(link, set()).add(url)
                continue
            if link in seen or not same_site(link) or any(x in link.lower() for x in _SKIP):
                continue
            seen.add(link)
            heapq.heappush(queue, (-_score(link, text), order, link))
            order += 1
    return result
