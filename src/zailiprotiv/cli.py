"""Command line: `zailiprotiv <command>`."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
import tempfile
import time
import urllib.parse
from pathlib import Path

from zailiprotiv import bills, jsonfile, kinds, laws, link, rollcall, skupstina
from zailiprotiv.config import DELAY

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


def adopted(args) -> int:
    """The laws the current convocation passed, from the Assembly's page of adopted laws, into data/laws.json."""
    found = laws.parse(skupstina.fetch(laws.ADOPTED).decode("utf-8", "replace"))
    store = {"fetched": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(), "source": laws.ADOPTED,
             "laws": {law.pdf: law.as_dict() for law in found}}
    Path(args.out).write_text(jsonfile.dumps(store, "laws"), encoding="utf-8")
    print(f"laws: {len(found)}, international treaties: {sum(l.treaty for l in found)}, "
          f"without a bill: {sum(not l.bill_pdf for l in found)}")
    return 0 if found else 1


def all_votes(folder: Path) -> dict[str, dict]:
    out = {}
    for path in sorted(folder.glob("*.json")):
        store = json.loads(path.read_text(encoding="utf-8"))
        for key, v in store["votes"].items():
            out[key] = {**v, "sitting": store["sitting"]}
    return out


def linked(args) -> int:
    """Each law's kind, roll calls and final vote, into data/laws.json."""
    path = Path(args.laws)
    store = json.loads(path.read_text(encoding="utf-8"))
    votes = all_votes(Path(args.votes))
    found = link.link(store["laws"], votes)
    for key, law in store["laws"].items():
        law["kind"] = kinds.kind(law["title"], law.get("treaty", False))
        law.update(found[key])
    path.write_text(jsonfile.dumps(store, "laws"), encoding="utf-8")
    n = len(store["laws"])
    final = sum(1 for law in store["laws"].values() if law["final_vote"])
    print(f"laws: {n}, with their final vote: {final}, with some vote: "
          f"{sum(1 for law in store['laws'].values() if law['votes'])}; roll calls read: {len(votes)}")
    for law in store["laws"].values():
        if not law["final_vote"]:
            print(f"  no final vote: {law['passed']}  {law['title'][:110]}")
    return 0


def memoranda(args) -> int:
    """Each adopted law's bill, read once: its memorandum's sections and constitutional basis, into
    data/bills/<file>.json, and the law's area(s) into data/laws.json."""
    path = Path(args.laws)
    store = json.loads(path.read_text(encoding="utf-8"))
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    read = failed = 0
    for law in store["laws"].values():
        url = law.get("bill_pdf")
        if not url:
            continue
        target = out_dir / (file_name(url).removesuffix(".pdf") + ".json")
        if not target.exists() or args.again:
            if args.limit and read >= args.limit:
                continue
            time.sleep(DELAY)
            try:
                body = skupstina.fetch(url)
            except skupstina.FetchError as e:
                failed += 1
                print(f"  failed {urllib.parse.unquote(url)}: {e}")
                continue
            with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
                f.write(body)
                f.flush()
                memo = bills.read(f.name)
            target.write_text(json.dumps({"bill": url, "sha256": hashlib.sha256(body).hexdigest(), **memo.as_dict()},
                                         ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            read += 1
        memo = json.loads(target.read_text(encoding="utf-8"))
        law["bill_file"] = target.name
        law["constitution"] = memo["articles"]
        law["areas"] = kinds.areas(memo["articles"])
    path.write_text(jsonfile.dumps(store, "laws"), encoding="utf-8")
    all_laws = store["laws"].values()
    no_memo = [l for l in all_laws if l.get("bill_file") and not l.get("constitution")]
    print(f"bills read now: {read}, failed: {failed}; laws with an area: {sum(1 for l in all_laws if l.get('areas'))}, "
          f"treaties (Art. 99): {sum(1 for l in all_laws if any(a['article'] == 99 for a in l.get('constitution', [])))}, "
          f"no constitutional basis found: {len(no_memo)}")
    for l in no_memo[:30]:
        print(f"  no basis: {l['title'][:110]}")
    return 0


def website(args) -> int:
    from zailiprotiv import site
    stats = site.build(DATA, Path(args.out), args.domain or None)
    print(", ".join(f"{k}: {v}" for k, v in stats.items()))
    return 0


def sitting_id(url: str) -> str:
    """The number the Assembly's site gives a sitting's page ("…_Народне.53524.43.html" → "53524")."""
    m = re.search(r"\.(\d+)\.43\.html$", urllib.parse.unquote(url))
    return m.group(1) if m else re.sub(r"\W+", "_", url)[-40:]


def votes(args) -> int:
    """Read every roll call in data/index.json not read yet, into data/votes/<sitting>.json."""
    index = json.loads(Path(args.index).read_text(encoding="utf-8"))
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    read = failed = 0
    problems: list[str] = []
    for url, sitting in sorted(index["sittings"].items(), key=lambda kv: kv[1]["listed"]):
        if not sitting["votes"]:
            continue
        path = out_dir / f"{sitting_id(url)}.json"
        store = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        store.update({"sitting": url, "title": sitting["title"]})
        store.setdefault("pdfs", {})
        store.setdefault("votes", {})
        changed = False
        for item, pdf in sitting["votes"]:
            again = args.again or (args.reread and args.reread in urllib.parse.unquote(pdf))
            if pdf in store["pdfs"] and not again:
                continue
            if args.limit and read >= args.limit:
                break
            time.sleep(DELAY)
            try:
                body = skupstina.fetch(pdf)
            except skupstina.FetchError as e:
                failed += 1
                print(f"  failed {urllib.parse.unquote(pdf)}: {e}")
                continue
            with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
                f.write(body)
                f.flush()
                found = rollcall.read(f.name)
            for key in [k for k in store["votes"] if k.split("#")[0] == pdf]:
                del store["votes"][key]
            for i, v in enumerate(found):
                store["votes"][f"{pdf}#{i}"] = {
                    "when": v.when, "item": v.item, "kind": v.kind, "session": v.session,
                    "listed_as": item, "counts": v.count(), "problems": v.problems,
                    "rows": [[r.number, r.name, r.vote, r.club] for r in v.rows],
                }
                problems += [f"{urllib.parse.unquote(pdf)} #{i}: {p}" for p in v.problems]
            if not found:
                problems.append(f"{urllib.parse.unquote(pdf)}: no vote read")
            store["pdfs"][pdf] = hashlib.sha256(body).hexdigest()
            read += 1
            changed = True
        if changed:
            path.write_text(jsonfile.dumps(store, "votes"), encoding="utf-8")
    total = sum(len(json.loads(p.read_text(encoding="utf-8"))["votes"]) for p in out_dir.glob("*.json"))
    print(f"PDFs read now: {read}, failed: {failed}; votes in the archive: {total}")
    for p in problems[:50]:
        print(f"  problem: {p}")
    return 1 if failed and not read else 0


def file_name(url: str) -> str:
    """A plain file name for a roll call or a bill, from its address below its folder: ASCII, no spaces."""
    path = urllib.parse.unquote(urllib.parse.urlsplit(url).path)
    path = re.split(r"rezultati_glasanja/|Listinzi/|predlozi_zakona/", path, flags=re.I)[-1]
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
    p = commands.add_parser("laws", help="the laws the current convocation passed → data/laws.json")
    p.add_argument("--out", default=str(DATA / "laws.json"))
    p.set_defaults(run=adopted)
    p = commands.add_parser("link", help="each law's kind, roll calls and final vote, into data/laws.json")
    p.add_argument("--laws", default=str(DATA / "laws.json"))
    p.add_argument("--votes", default=str(DATA / "votes"))
    p.set_defaults(run=linked)
    p = commands.add_parser("bills", help="each law's bill: memorandum and constitutional basis → data/bills/")
    p.add_argument("--laws", default=str(DATA / "laws.json"))
    p.add_argument("--out", default=str(DATA / "bills"))
    p.add_argument("--again", action="store_true")
    p.add_argument("--limit", type=int, default=0)
    p.set_defaults(run=memoranda)
    p = commands.add_parser("site", help="build the static site")
    p.add_argument("--out", default="_site")
    p.add_argument("--domain", default="zailiprotiv.rs")
    p.set_defaults(run=website)
    p = commands.add_parser("votes", help="read the roll calls in the index not read yet, into data/votes/")
    p.add_argument("--index", default=str(DATA / "index.json"))
    p.add_argument("--out", default=str(DATA / "votes"))
    p.add_argument("--again", action="store_true", help="read every PDF again, not only new ones")
    p.add_argument("--limit", type=int, default=0, help="read at most this many PDFs (0: all)")
    p.add_argument("--reread", default="", help="read again the PDFs whose address contains this text")
    p.set_defaults(run=votes)
    p = commands.add_parser("download", help="save roll-call PDFs into a folder (test fixtures)")
    p.add_argument("--to", default="tests/fixtures")
    p.add_argument("urls", nargs="+")
    p.set_defaults(run=download)
    args = parser.parse_args(argv)
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
