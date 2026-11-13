"""MPs' portraits from the Assembly's own list of MPs (the maintainer's decision, 13 Nov 2026).

The list page shows every sitting MP with a small portrait (150 px wide) inside a link to the MP's page, whose
address carries the name ("NENAD_ABRAMOVIĆ.1435.891.html"). The portraits are kept in data/photos/ under the number
the Assembly gives the MP, with data/photos/index.json saying whose each is ({MP's key: {"file", "source", "page"}}).
"""
from __future__ import annotations

import re
import urllib.parse
from html.parser import HTMLParser

from zailiprotiv import mps
from zailiprotiv.config import BASE
from zailiprotiv.cyrillic import cyr

PAGE = BASE + "/narodna-skupstina-/sastav/narodni-poslanici/aktuelni-saziv.890.html"
_MP_PAGE = re.compile(r"/([^/]+)\.(\d+)\.891\.html$")


class _Portraits(HTMLParser):
    def __init__(self):
        super().__init__()
        self.last, self.found = None, {}

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a" and (m := _MP_PAGE.search(urllib.parse.unquote(a.get("href") or ""))):
            self.last = (" ".join(re.split(r"[_+\s]+", m.group(1))).strip(), m.group(2), a["href"])
        elif tag == "img" and self.last and "/poslanici/" in (a.get("src") or ""):
            name, number, page = self.last
            self.found.setdefault(number, {"name": name, "src": urllib.parse.urljoin(BASE, a["src"]),
                                           "page": urllib.parse.urljoin(BASE, page)})


def parse(html: str) -> dict[str, dict]:
    """{the MP's number at the Assembly: {"name", "src", "page"}} from the list of MPs."""
    p = _Portraits()
    p.feed(html)
    return p.found


def key(name: str) -> str:
    """The MP's key (as in the roll calls, which are in Cyrillic) from the Latin name in the page's address."""
    return mps.key(cyr(name.title()))
