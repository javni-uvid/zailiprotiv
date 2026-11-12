"""Command line: `zailiprotiv <command>`."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
import subprocess
import tempfile
import time
import urllib.parse
from pathlib import Path

from zailiprotiv import bills, jsonfile, kinds, laws, link, rollcall, skupstina, transcripts
from zailiprotiv.config import CONVOCATIONS, CURRENT, DELAY

ROOT = Path("data")
DATA = ROOT / CURRENT  # the convocation's own folder; `--convocation N` before the command picks another


def index(args) -> int:
    """The current convocation's sittings and the roll-call PDF of each agenda item, into data/index.json."""
    found = skupstina.index(convocation=CONVOCATION)
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
    source = CONVOCATIONS[CONVOCATION]["laws"]
    found = laws.parse(skupstina.fetch(source).decode("utf-8", "replace"), source)
    store = {"fetched": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(), "source": source,
             "convocation": CONVOCATION,
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
    # Links made by hand where the Assembly's PDF names the act otherwise (a wrong year, a typo, another word):
    # data/<N>/links.json, {law title: {"vote": vote key, "why": "…"}}, each checked to be a vote of that day.
    manual_path = path.parent / "links.json"
    manual = json.loads(manual_path.read_text(encoding="utf-8")) if manual_path.exists() else {}
    for key, law in store["laws"].items():
        law["kind"] = kinds.kind(law["title"], law.get("treaty", False))
        law.update(found[key])
        m = manual.get(law["title"])
        if m and not law["final_vote"]:
            vote = votes.get(m["vote"])
            if not vote or vote["when"][:10] != law.get("passed"):
                print(f"  manual link refused (no such vote that day): {law['title'][:90]}")
                continue
            law.update(final_vote=m["vote"], matched="manual", votes=sorted(set(law.get("votes", [])) | {m["vote"]}))
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
        stale = False
        if target.exists() and not args.again:
            old = json.loads(target.read_text(encoding="utf-8"))
            stale = not old.get("sections") and old.get("reader", 1) < bills.READER
        if not target.exists() or args.again or stale:
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
                try:
                    memo = bills.read(f.name)
                except subprocess.CalledProcessError:  # a file pdftotext can't open: the law goes without its bill
                    failed += 1
                    print(f"  unreadable {urllib.parse.unquote(url)}")
                    continue
            target.write_text(json.dumps({"bill": url, "sha256": hashlib.sha256(body).hexdigest(),
                                          "reader": bills.READER, **memo.as_dict()},
                                         ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            read += 1
        memo = json.loads(target.read_text(encoding="utf-8"))
        again_read = bills.articles(memo.get("sections", {}).get("basis", ""))  # rules may have changed
        if again_read != memo.get("articles"):
            memo["articles"] = again_read
            target.write_text(json.dumps(memo, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
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
    stats = site.build(ROOT, Path(args.out), args.domain or None)
    print(", ".join(f"{k}: {v}" for k, v in stats.items()))
    return 0


def summaries_cmd(args) -> int:
    """Claude's summary of each bill's memorandum not summarised yet (or whose memorandum changed), into
    data/summaries/<bill file>.json. Needs ANTHROPIC_API_KEY."""
    from zailiprotiv import summaries
    store = json.loads(Path(args.laws).read_text(encoding="utf-8"))
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    client = None
    done = failed = skipped = 0
    tokens = {"input": 0, "output": 0}
    for law in sorted(store["laws"].values(), key=lambda l: l.get("passed") or "", reverse=True):
        name = law.get("bill_file")
        if not name or not (Path(args.bills) / name).exists():
            continue
        memo = json.loads((Path(args.bills) / name).read_text(encoding="utf-8"))
        if not memo.get("sections"):
            skipped += 1
            continue
        target = out_dir / name
        text = summaries.material(law, memo)
        if target.exists() and json.loads(target.read_text(encoding="utf-8")).get("fingerprint") == \
                summaries.fingerprint(text):
            continue
        if args.limit and done >= args.limit:
            break
        if client is None:
            import anthropic
            client = anthropic.Anthropic()
        try:
            result = summaries.summarize(law, memo, client)
        except Exception as e:  # one bad reply mustn't stop the rest
            failed += 1
            print(f"  failed {law['title'][:90]}: {type(e).__name__}: {str(e)[:200]}")
            continue
        target.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        tokens["input"] += result["usage"]["input"]
        tokens["output"] += result["usage"]["output"]
        done += 1
    print(f"summaries written: {done}, failed: {failed}, bills without a memorandum: {skipped}; "
          f"tokens in {tokens['input']:,}, out {tokens['output']:,}")
    return 1 if failed and not done else 0


def _pending(args):
    """Laws whose bill has a memorandum and no current summary, newest first: (law, memo, bill file name)."""
    from zailiprotiv import summaries
    store = json.loads(Path(args.laws).read_text(encoding="utf-8"))
    out = []
    for law in sorted(store["laws"].values(), key=lambda l: (l.get("passed") or "", l["title"]), reverse=True):
        name = law.get("bill_file")
        if not name or not (Path(args.bills) / name).exists():
            continue
        memo = json.loads((Path(args.bills) / name).read_text(encoding="utf-8"))
        if not memo.get("sections"):
            continue
        target = Path(args.out) / name
        if target.exists() and json.loads(target.read_text(encoding="utf-8")).get("fingerprint") == \
                summaries.fingerprint(summaries.material(law, memo)):
            continue
        out.append((law, memo, name))
    return out


def export(args) -> int:
    """The material of laws still without a summary, one text file each, for summaries written in a session."""
    from zailiprotiv import summaries
    to = Path(args.to)
    to.mkdir(parents=True, exist_ok=True)
    if args.only:
        wanted = [n.strip() for n in Path(args.only).read_text(encoding="utf-8").split() if n.strip()]
        store = json.loads(Path(args.laws).read_text(encoding="utf-8"))
        by_bill = {l.get("bill_file"): l for l in store["laws"].values() if l.get("bill_file")}
        pending = [(by_bill[n], json.loads((Path(args.bills) / n).read_text(encoding="utf-8")), n)
                   for n in wanted if n in by_bill and (Path(args.bills) / n).exists()]
    else:
        pending = _pending(args)
    if args.kind:
        pending = [p for p in pending if p[0].get("kind") in args.kind.split(",")]
    chosen = pending[args.skip: args.skip + args.limit] if args.limit else pending[args.skip:]
    for law, memo, name in chosen:
        limits = summaries.DEEP_LIMITS if args.deep else None
        (to / (name.removesuffix(".json") + ".txt")).write_text(summaries.material(law, memo, limits),
                                                                 encoding="utf-8")
    (to / "RULES.txt").write_text(summaries.SYSTEM, encoding="utf-8")
    print(f"pending: {len(pending)}, exported: {len(chosen)} to {to}")
    return 0


def import_summaries(args) -> int:
    """Summaries written in a session (a JSON Lines file: {"bill_file", "summary"}), checked and saved like the
    API's, under the name of the model that wrote them."""
    from zailiprotiv import summaries
    store = json.loads(Path(args.laws).read_text(encoding="utf-8"))
    by_bill = {l.get("bill_file"): l for l in store["laws"].values() if l.get("bill_file")}
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    saved = refused = 0
    for line in Path(args.file).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        name = item["bill_file"] if item["bill_file"].endswith(".json") else item["bill_file"] + ".json"
        law = by_bill.get(name)
        try:
            if law is None:
                raise ValueError("no such bill")
            summary = summaries.parse(json.dumps(item["summary"], ensure_ascii=False))
        except ValueError as e:
            refused += 1
            print(f"  refused {name}: {e}")
            continue
        memo = json.loads((Path(args.bills) / name).read_text(encoding="utf-8"))
        (out_dir / name).write_text(json.dumps(summaries.record(law, memo, summary, args.model, deep=args.deep),
                                               ensure_ascii=False,
                                               indent=1) + "\n", encoding="utf-8")
        saved += 1
    print(f"summaries saved: {saved}, refused: {refused}")
    return 1 if refused and not saved else 0


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


def notes_of_debate(args) -> int:
    """The stenographic notes of the sittings where the laws with the most votes against (or the ones named) had
    their final vote, into data/<N>/transcripts/<sitting>.json: the agenda, every speech with the part of the debate
    it was given in, and the amendments announced. A sitting already read is skipped unless --again."""
    import hashlib
    from zailiprotiv.site import against_share
    store = json.loads(Path(args.laws).read_text(encoding="utf-8"))
    votes_ = all_votes(Path(args.votes))
    finals = [(law, votes_[law["final_vote"]]) for law in store["laws"].values()
              if law.get("final_vote") in votes_]
    if args.law:
        chosen = [(l, v) for l, v in finals if l.get("bill_file") in args.law or l["title"] in args.law]
    else:
        chosen = sorted((x for x in finals if x[1]["counts"]["protiv"]),
                        key=lambda x: (against_share(x[1]["counts"]), x[1]["counts"]["protiv"]), reverse=True)
        chosen = chosen[:args.top]
    sittings = sorted({v["sitting"] for _, v in chosen})
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for url in sittings:
        path = out / f"{sitting_id(url)}.json"
        if path.exists() and not args.again:
            continue
        page = skupstina.fetch(url).decode("utf-8", "replace")
        listed = transcripts.days(page, url)
        if not listed:
            print(f"{url}: no stenographic notes linked")
            continue
        days, meta = [], []
        for d in sorted(listed, key=lambda d: d["day"]):
            time.sleep(DELAY)
            body = skupstina.fetch(d["url"])
            paras = transcripts.paragraphs(body)
            days.append(paras)
            meta.append({**d, **transcripts.heading(paras), "sha256": hashlib.sha256(body).hexdigest()})
        found = transcripts.debate(days)
        record = {"sitting": url, "days": meta, "agenda": {str(k): v for k, v in found["agenda"].items()},
                  "amendments": found["amendments"],
                  "speeches": {f"{i:05d}": s for i, s in enumerate(found["speeches"])}}
        path.write_text(jsonfile.dumps(record, "speeches"), encoding="utf-8")
        print(f"{path}: {len(meta)} days, {len(found['speeches'])} speeches, {len(found['amendments'])} amendments")
        time.sleep(DELAY)
    return 0


def _debated(args):
    """The laws whose sitting's notes have been read, with what debates.material needs: (law, bill, notes, final,
    item), the most votes against first."""
    from zailiprotiv import site
    laws_, votes_, bills_ = site.load(DATA)
    notes = site.load_transcripts(DATA)
    items = [{"law": l, "final": votes_.get(l.get("final_vote") or "")} for l in laws_["laws"].values()]
    out = []
    for it in site.most_against(items, len(items)):
        law, final = it["law"], it["final"]
        n = notes.get(final["sitting"])
        d = site.debate_of(law, final, n) if n else None
        if d and law.get("bill_file"):
            out.append((law, bills_.get(law["bill_file"], {}), n, final, d["item"]))
    return out, votes_, bills_


def debates_export(args) -> int:
    """The debate material of the laws with most votes against whose notes were read, one text file each, for
    summaries of the debate written in a session."""
    from zailiprotiv import debates
    found, votes_, bills_ = _debated(args)
    seated, df = debates.seats(votes_), debates.document_frequency(bills_)
    to = Path(args.to)
    to.mkdir(parents=True, exist_ok=True)
    chosen = found[:args.top]
    for law, bill, n, final, item in chosen:
        text = debates.material(law, bill, n, final, seated, item, df)
        (to / (law["bill_file"].removesuffix(".json") + ".txt")).write_text(text, encoding="utf-8")
    (to / "RULES.txt").write_text(debates.SYSTEM, encoding="utf-8")
    print(f"exported: {len(chosen)} to {to}")
    return 0


def debates_import(args) -> int:
    """Debate summaries written in a session (JSON Lines: {"bill_file", "debate"}): quotes checked against the notes
    word for word, saved to data/<N>/debates/<bill file>.json."""
    from zailiprotiv import debates
    found, votes_, bills_ = _debated(args)
    seated, df = debates.seats(votes_), debates.document_frequency(bills_)
    by_bill = {law["bill_file"]: (law, bill, n, final, item) for law, bill, n, final, item in found}
    out = DATA / "debates"
    out.mkdir(parents=True, exist_ok=True)
    saved = refused = 0
    for line in Path(args.file).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        name = entry["bill_file"] if entry["bill_file"].endswith(".json") else entry["bill_file"] + ".json"
        if name not in by_bill:
            print(f"  refused {name}: no notes read for its sitting")
            refused += 1
            continue
        law, bill, n, final, item = by_bill[name]
        try:
            debate, dropped = debates.parse(entry["debate"], n, debates.speaker_groups(n, final, seated))
        except (ValueError, AttributeError) as e:
            print(f"  refused {name}: {e}")
            refused += 1
            continue
        text = debates.material(law, bill, n, final, seated, item, df)
        (out / name).write_text(json.dumps(debates.record(law, text, debate, args.model, dropped), ensure_ascii=False,
                                           indent=1) + "\n", encoding="utf-8")
        print(f"  {name}: {len(debate['citati'])} quotes kept, {len(dropped)} dropped" +
              "".join(f"\n    dropped: {d[:90]}" for d in dropped))
        saved += 1
    print(f"debates saved: {saved}, refused: {refused}")
    return 1 if refused and not saved else 0


CONVOCATION = CURRENT


def main(argv: list[str] | None = None) -> int:
    global DATA, CONVOCATION
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--convocation", default=CURRENT, choices=sorted(CONVOCATIONS))
    known, rest = pre.parse_known_args(argv)
    CONVOCATION, DATA = known.convocation, ROOT / known.convocation
    if CONVOCATION == CURRENT and (ROOT / "laws.json").exists() and not DATA.exists():
        DATA = ROOT  # the layout before data/<N>/: one convocation in data/ itself
    argv = rest
    parser = argparse.ArgumentParser(prog="zailiprotiv",
                                     epilog="--convocation N before the command works on convocation N (default: "
                                            f"{CURRENT})")
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
    p = commands.add_parser("summaries", help="Claude's summaries of the bills' memoranda → data/summaries/")
    p.add_argument("--laws", default=str(DATA / "laws.json"))
    p.add_argument("--bills", default=str(DATA / "bills"))
    p.add_argument("--out", default=str(DATA / "summaries"))
    p.add_argument("--limit", type=int, default=0, help="write at most this many (0: all)")
    p.set_defaults(run=summaries_cmd)
    for name, run, help_ in (("export", export, "write the material of laws still without a summary"),
                             ("import", import_summaries, "save summaries written in a session (JSON Lines)")):
        p = commands.add_parser(name, help=help_)
        p.add_argument("--laws", default=str(DATA / "laws.json"))
        p.add_argument("--bills", default=str(DATA / "bills"))
        p.add_argument("--out", default=str(DATA / "summaries"))
        p.set_defaults(run=run)
        p.add_argument("--deep", action="store_true", help="the memorandum nearly whole (laws with most votes against)")
        if name == "export":
            p.add_argument("--to", required=True)
            p.add_argument("--limit", type=int, default=0)
            p.add_argument("--skip", type=int, default=0)
            p.add_argument("--kind", default="", help="only these kinds, comma-separated (law,change,finance,treaty)")
            p.add_argument("--only", default="", help="a file listing the bill files to export, done or not")
        else:
            p.add_argument("file")
            p.add_argument("--model", required=True, help="who wrote them, e.g. claude-opus-5-5")
    p = commands.add_parser("transcripts", help="stenographic notes of the debates on the most contested laws")
    p.add_argument("--laws", default=str(DATA / "laws.json"))
    p.add_argument("--votes", default=str(DATA / "votes"))
    p.add_argument("--out", default=str(DATA / "transcripts"))
    p.add_argument("--top", type=int, default=20, help="the laws with the largest share of votes against")
    p.add_argument("--law", action="append", default=[], help="a law by bill file or title (instead of --top)")
    p.add_argument("--again", action="store_true")
    p.set_defaults(run=notes_of_debate)
    p = commands.add_parser("debates-export", help="debate material of the most contested laws, for a session")
    p.add_argument("--to", required=True)
    p.add_argument("--top", type=int, default=20)
    p.set_defaults(run=debates_export)
    p = commands.add_parser("debates-import", help="save debate summaries written in a session")
    p.add_argument("file")
    p.add_argument("--model", required=True)
    p.set_defaults(run=debates_import)
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
