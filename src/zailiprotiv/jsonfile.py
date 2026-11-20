"""The derived stores as JSON with one entry per line, so that git keeps a small diff when a few entries change.

Each store is a dict with one big mapping (decisions, documents, stations) and a few small values. The small values
go on the first line and each entry of the mapping on a line of its own, keys sorted, so the file is valid JSON and
`json.loads` reads it back unchanged."""

from __future__ import annotations

import json
from pathlib import Path


def dumps(data: dict, entries: str) -> str:
    """data as JSON text, data[entries] one entry per line."""
    head = ", ".join(f"{json.dumps(k)}: {json.dumps(v, ensure_ascii=False, sort_keys=True)}"
                     for k, v in sorted(data.items()) if k != entries)
    lines = ",\n".join(f"{json.dumps(k, ensure_ascii=False)}: {json.dumps(v, ensure_ascii=False, sort_keys=True)}"
                       for k, v in sorted((data.get(entries) or {}).items()))
    return "{" + (head + ", " if head else "") + json.dumps(entries) + ": {" + ("\n" + lines + "\n" if lines else "") \
        + "}}\n"


def load(path: Path, default=None):
    """The JSON in the file at path, or default when there is no file."""
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def save(path: Path, data: dict, entries: str) -> None:
    """data written to path as dumps writes it."""
    path.write_text(dumps(data, entries), encoding="utf-8")


def shrank(now: int, before: int, share: float = 0.8, least: int = 0) -> bool:
    """Whether a new reading of now entries fell below share of the before kept (with least or more kept): such a
    reading is a page that changed or failed, and what is kept stays."""
    return before >= least and now < before * share
