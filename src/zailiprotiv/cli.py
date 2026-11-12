"""Command line: `zailiprotiv <command>`."""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
import urllib.parse
from pathlib import Path

from zailiprotiv import jsonfile, skupstina

DATA = Path("data")


def index(args) -> int:
    """The current convocation's sittings and the roll-call PDF of each agenda item, into data/index.json."""
    found = skupstina.index()
    store = {
        "fetched": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "sittings": {
            s.url: {"listed": i, "title": s.title, "votes": [[v.item, v.pdf] for v in s.votes]}
            for i, s in enumerate(found)
        },
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(jsonfile.dumps(store, "sittings"), encoding="utf-8")
    total = sum(len(s.votes) for s in found)
    print(f"sittings: {len(found)}, roll calls: {total}")
    for s in found:
        print(f"  {len(s.votes):4}  {s.title[:100]}")
    if found and not total:
        print("no roll calls found: has the sittings' page layout changed?")
        return 1
    return 0


def file_name(url: str) -> str:
    """A plain file name for a roll call, from its address under rezultati_glasanja: ASCII, no spaces."""
    path = urllib.parse.unquote(urllib.parse.urlsplit(url).path).split("rezultati_glasanja/")[-1]
    return re.sub(r"[^A-Za-z0-9.-]+", "_", path).strip("_").lower()


def download(args) -> int:
    """Save each URL into a folder, named by file_name: to add real roll calls to the tests."""
    to = Path(args.to)
    to.mkdir(parents=True, exist_ok=True)
    for url in args.urls:
        body = skupstina.fetch(url)
        (to / file_name(url)).write_bytes(body)
        print(f"{len(body):9,}  {file_name(url)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="zailiprotiv")
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("index", help="list the current convocation's sittings and their roll-call PDFs")
    p.add_argument("--out", default=str(DATA / "index.json"))
    p.set_defaults(run=index)
    p = commands.add_parser("download", help="save roll-call PDFs into a folder (test fixtures)")
    p.add_argument("--to", default="tests/fixtures")
    p.add_argument("urls", nargs="+")
    p.set_defaults(run=download)
    args = parser.parse_args(argv)
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
