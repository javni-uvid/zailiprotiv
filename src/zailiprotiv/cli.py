"""Command line: `zailiprotiv <command>`."""

from __future__ import annotations

import argparse
import re
import sys
import urllib.parse
from collections import Counter
from pathlib import Path

from zailiprotiv import skupstina
from zailiprotiv.config import BASE, VOTES_PATH

# A roll-call PDF known to exist (found by a web search on 12 Nov 2026): the probe's first check.
KNOWN_PDF = BASE + VOTES_PATH + "2026/20.pdf"


def _shape(url: str) -> str:
    """The PDF's address with numbers as N, to see how the Assembly lays out its folders."""
    path = urllib.parse.unquote(urllib.parse.urlsplit(url).path)
    return re.sub(r"\d+", "N", path.removeprefix(VOTES_PATH))


def probe(args) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    try:
        body = skupstina.fetch(KNOWN_PDF)
        print(f"known PDF: {len(body):,} bytes, starts {body[:5]!r}")
        (out / "known.pdf").write_bytes(body)
    except skupstina.FetchError as e:
        print(f"known PDF: not reachable ({e})")
    result = skupstina.crawl(args.start, max_pages=args.max_pages)
    print(f"pages read: {len(result.visited)}, failed: {len(result.failed)}, vote PDFs found: {len(result.pdfs)}")
    for url, error in result.failed[:10]:
        print(f"  failed {urllib.parse.unquote(url)}: {error}")
    print("PDF addresses by shape:")
    for shape, n in Counter(_shape(u) for u in result.pdfs).most_common(20):
        print(f"  {n:5}  {shape}")
    print("pages linking to vote PDFs:")
    referrers = Counter(page for pages in result.pdfs.values() for page in pages)
    for page, n in referrers.most_common(20):
        print(f"  {n:5}  {urllib.parse.unquote(page)}")
    with open(out / "pdfs.txt", "w", encoding="utf-8") as f:
        for url in sorted(result.pdfs):
            f.write(url + "\t" + " ".join(sorted(result.pdfs[url])) + "\n")
    with open(out / "visited.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(result.visited) + "\n")
    for i, page in enumerate(p for p, _ in referrers.most_common(args.samples)):
        try:
            (out / f"referrer-{i}.html").write_bytes(skupstina.fetch(page))
        except skupstina.FetchError as e:
            print(f"  referrer {i}: {e}")
    for i, url in enumerate(sorted(result.pdfs)[: args.samples]):
        try:
            (out / f"sample-{i}.pdf").write_bytes(skupstina.fetch(url))
        except skupstina.FetchError as e:
            print(f"  sample {i}: {e}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="zailiprotiv")
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("probe", help="can we reach the Assembly's site, and where does it list roll-call PDFs?")
    p.add_argument("--start", default=BASE + "/", help="page to start the walk from")
    p.add_argument("--max-pages", type=int, default=80)
    p.add_argument("--samples", type=int, default=5, help="how many PDFs and listing pages to save")
    p.add_argument("--out", default="probe")
    p.set_defaults(run=probe)
    args = parser.parse_args(argv)
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
