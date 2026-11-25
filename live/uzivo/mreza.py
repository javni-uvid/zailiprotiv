"""What the service asks of the project's own addresses: the site's files, and the counter with its token. The
broadcast, the Assembly's pages, Whisper's server and the bucket are asked by the parts that need them. Only the
standard library."""
from __future__ import annotations

import json
import time
import urllib.request


def site(url: str, timeout: float = 30, whole: float = 60) -> str:
    """A file of the site's, as text. Raises when it does not come: the caller keeps its last good copy. `timeout` is for
    each step of the net (an address tried, an answer, a piece read); `whole`, for the reading from the first piece to the
    last, as pieces that come one by one are each in time."""
    req = urllib.request.Request(url, headers={"User-Agent": "zailiprotiv-uzivo"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        until, got = time.monotonic() + whole, []
        while piece := resp.read1(1 << 16):
            got.append(piece)
            if time.monotonic() > until:
                raise TimeoutError(f"{url}: not whole after {whole:.0f} s")
        missing = getattr(resp, "length", 0)  # cut short: of the length it said
        if missing:
            raise ConnectionError(f"{url}: {missing} bytes missing")
        return b"".join(got).decode("utf-8")


def counter(url: str, token: str, body: dict | None = None, timeout: float = 30, agent: str = "zailiprotiv-mikrofon") -> dict:
    """The counter's answer to the service: a POST with a body, a GET without one. Raises when it refuses or does not
    answer."""
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"authorization": "Bearer " + token, "content-type": "application/json",
                                          "user-agent": agent})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))
