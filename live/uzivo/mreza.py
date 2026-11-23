"""What the service asks of the project's own addresses: the site's files, and the counter with its token. The
broadcast, the Assembly's pages, Whisper's server and the bucket are asked by the parts that need them. Only the
standard library."""
from __future__ import annotations

import json
import urllib.request


def site(url: str, timeout: float = 30) -> str:
    """A file of the site's, as text. Raises when it does not come: the caller keeps its last good copy."""
    req = urllib.request.Request(url, headers={"User-Agent": "zailiprotiv-uzivo"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8")


def counter(url: str, token: str, body: dict | None = None, timeout: float = 30, agent: str = "zailiprotiv-mikrofon") -> dict:
    """The counter's answer to the service: a POST with a body, a GET without one. Raises when it refuses or does not
    answer."""
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"authorization": "Bearer " + token, "content-type": "application/json",
                                          "user-agent": agent})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))
