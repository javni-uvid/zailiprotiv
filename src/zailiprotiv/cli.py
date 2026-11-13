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


def _shrunk(path: Path, what: str, now: int, counts=lambda v: True) -> bool:
    """True, with a warning, when a new reading has far fewer entries than the file it would replace: the Assembly's
    page then shows something else (a new convocation's empty list, an error page), and what was read is kept. A
    convocation's laws and sittings only grow."""
    if not path.exists():
        return False
    before = sum(1 for v in json.loads(path.read_text(encoding="utf-8"))[what].values() if counts(v))
    if before >= 10 and now < before * 0.8:
        print(f"::warning::{what}: the Assembly's page gives {now}, the file has {before}. Kept the file: has a new "
              f"convocation taken over the page? See AGENTS.md, 'The Fifteenth convocation'.")
        return True
    return False


def index(args) -> int:
    """The current convocation's sittings and the roll-call PDF of each agenda item, into data/index.json."""
    found = skupstina.index(convocation=CONVOCATION)
    store = {
        "fetched": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "sittings": {
            s.url: {"listed": i, "title": s.title, "votes": [[v.item, v.pdf] for v in s.votes],
                    "agenda": s.agenda, "starts": s.starts}
            for i, s in enumerate(found)
        },
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    total = sum(len(s.votes) for s in found)
    if _shrunk(out, "sittings", sum(1 for s in found if s.votes), lambda v: bool(v.get("votes"))):
        return 0
    out.write_text(jsonfile.dumps(store, "sittings"), encoding="utf-8")
    print(f"sittings: {len(found)}, roll calls: {total}")
    for s in found:
        print(f"  {len(s.votes):4}  {s.title[:100]}")
    if found and not total:
        print("no roll calls found: has the sittings' page layout changed?")
        return 1
    return 0


def in_procedure(args) -> int:
    """The bills waiting in the Assembly now, from its page "Zakoni u proceduri", into data/<N>/procedure.json, which
    also remembers the bills no longer listed and when each was first and last seen."""
    from zailiprotiv import procedure
    found = procedure.parse(skupstina.fetch(procedure.PAGE).decode("utf-8", "replace"))
    out = Path(args.out)
    store = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    today = dt.datetime.now(dt.timezone.utc).date().isoformat()
    before = {k for k, b in (store.get("bills") or {}).items() if b["last_seen"] == store.get("fetched")}
    store = procedure.merge(store, found, today)
    now = {b.pdf for b in found}
    out.write_text(jsonfile.dumps(store, "bills"), encoding="utf-8")
    print(f"bills in procedure: {len(found)}, new: {len(now - before)}, no longer listed: {len(before - now)}")
    return 0


def notes_site_cmd(args) -> int:
    """The stenographic notes read, as pages of their own (see notes_site), into --out."""
    from zailiprotiv import notes_site
    n = notes_site.build(ROOT, Path(args.out))
    print(f"notes: {n['pages']} pages (each in two scripts), {n['speeches']} speeches")
    return 0


def notes_upload_cmd(args) -> int:
    """Send the notes' pages that changed to the R2 bucket (S3 API), and remember what is there in
    data/notes_manifest.json so the next run sends only what is new. Needs R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY and
    CLOUDFLARE_ACCOUNT_ID in the environment."""
    import mimetypes
    import os
    from zailiprotiv import notes_site
    folder, store = Path(args.dir), ROOT / "notes_manifest.json"
    manifest = json.loads(store.read_text(encoding="utf-8")) if store.exists() else {}
    now, send, gone = notes_site.changed(folder, manifest)
    print(f"notes: {len(now)} files, {len(send)} to send, {len(gone)} to remove")
    if args.dry or not (send or gone):
        return 0
    missing = [v for v in ("R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "CLOUDFLARE_ACCOUNT_ID") if not os.environ.get(v)]
    if missing:
        print("not sent, missing: " + ", ".join(missing))
        return 1
    import boto3
    from botocore.config import Config
    from concurrent.futures import ThreadPoolExecutor, as_completed
    workers = 16
    s3 = boto3.client("s3", endpoint_url=f"https://{os.environ['CLOUDFLARE_ACCOUNT_ID']}.r2.cloudflarestorage.com",
                      aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
                      aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"], region_name="auto",
                      config=Config(connect_timeout=10, read_timeout=60, max_pool_connections=workers,
                                    retries={"max_attempts": 4, "mode": "standard"}))
    try:  # a wrong key, account or bucket is said at once, not after an hour of retries
        s3.list_objects_v2(Bucket=args.bucket, MaxKeys=1)
    except Exception as e:
        print(f"not sent, the bucket {args.bucket} does not answer: {e}")
        return 1

    def save():
        store.write_text(json.dumps(manifest, ensure_ascii=False, indent=0, sort_keys=True) + "\n", encoding="utf-8")

    def put(name):
        kind = mimetypes.guess_type(name)[0] or "application/octet-stream"
        if kind.startswith("text/") or kind in ("image/svg+xml", "application/json"):
            kind += "; charset=utf-8"
        s3.upload_file(str(folder / name), args.bucket, name,
                       ExtraArgs={"ContentType": kind, "CacheControl": "public, max-age=3600"})

    failed = []
    # The pages first and the lists that link to them last, so a list never points at a page not yet there.
    order = sorted(send, key=lambda n: (n.rsplit("/", 1)[-1] == "index.html", n))
    with ThreadPoolExecutor(workers) as pool:
        jobs = {pool.submit(put, name): name for name in order}
        for i, job in enumerate(as_completed(jobs), 1):
            name = jobs[job]
            if job.exception():
                failed.append(name)
                print(f"  not sent {name}: {job.exception()}")
            else:
                manifest[name] = now[name]
            if i % 200 == 0:  # keep what was sent, should the run stop
                save()
                print(f"  {i}/{len(order)}", flush=True)
    for name in gone if not failed else []:  # nothing is removed in a run that did not send everything
        try:
            s3.delete_object(Bucket=args.bucket, Key=name)
            manifest.pop(name, None)
        except Exception as e:
            failed.append(name)
            print(f"  not removed {name}: {e}")
    save()
    print(f"notes: sent {len(send) - len([f for f in failed if f in now])}, removed {len(gone) if not failed else 0}, failed {len(failed)}")
    return 1 if failed else 0


def notes_check_cmd(args) -> int:
    """Do the notes' pages answer at their public address? The front page, the style and a few pages picked across
    data/notes_manifest.json, each asked for and read: 200, the right kind, and for a page the speeches in it."""
    import urllib.request
    store = ROOT / "notes_manifest.json"
    names = sorted(json.loads(store.read_text(encoding="utf-8"))) if store.exists() else []
    pages = [n for n in names if "/dan-" in n]
    if not pages:
        print("notes: nothing in the bucket yet")
        return 1
    ask = ["index.html", "style.css"] + [pages[i * (len(pages) - 1) // 4] for i in range(5)]
    bad = 0
    for name in dict.fromkeys(ask):
        url = args.url.rstrip("/") + "/" + urllib.parse.quote(name)
        want = "text/css" if name.endswith(".css") else "text/html"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "zailiprotiv-check"})
            with urllib.request.urlopen(req, timeout=30) as r:
                kind, body = r.headers.get("Content-Type", ""), r.read().decode("utf-8", "replace")
            ok = want in kind and "utf-8" in kind.lower() and ("/dan-" not in name or 'id="g' in body)
            why = "" if ok else f" (kind {kind!r}, {len(body)} bytes)"
        except Exception as e:
            ok, why = False, f" ({e})"
        bad += not ok
        print(f"  {'ok ' if ok else 'BAD'} {url}{why}")
    print(f"notes: {len(names)} files in the bucket, {len(dict.fromkeys(ask)) - bad} of {len(dict.fromkeys(ask))} asked for answer")
    return 1 if bad else 0


def photos_cmd(args) -> int:
    """MPs' portraits from the Assembly's list of MPs into data/photos/; only those not there yet are downloaded."""
    import time
    from zailiprotiv import config, photos
    found = photos.parse(skupstina.fetch(photos.PAGE).decode("utf-8", "replace"))
    folder = ROOT / "photos"
    folder.mkdir(parents=True, exist_ok=True)
    index_file = folder / "index.json"
    index = json.loads(index_file.read_text(encoding="utf-8")) if index_file.exists() else {}
    new = 0
    for number, mp in sorted(found.items()):
        k, name = photos.key(mp["name"]), f"{number}.jpg"
        if index.get(k, {}).get("source") == mp["src"] and (folder / name).exists():
            continue
        try:
            data = skupstina.fetch(mp["src"])
        except skupstina.FetchError as e:
            print(f"  {mp['name']}: {e}")
            continue
        if data[:2] != b"\xff\xd8":  # not a JPEG: a placeholder or an error page
            continue
        (folder / name).write_bytes(data)
        index[k] = {"file": name, "source": mp["src"], "page": mp["page"]}
        new += 1
        time.sleep(config.DELAY)
    index_file.write_text(json.dumps(index, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"portraits listed: {len(found)}, new: {new}, kept: {len(index)}")
    return 0


def adopted(args) -> int:
    """The laws the current convocation passed, from the Assembly's page of adopted laws, into data/laws.json."""
    source = CONVOCATIONS[CONVOCATION]["laws"]
    found = laws.parse(skupstina.fetch(source).decode("utf-8", "replace"), source)
    store = {"fetched": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(), "source": source,
             "convocation": CONVOCATION,
             "laws": {law.pdf: law.as_dict() for law in found}}
    if _shrunk(Path(args.out), "laws", len(found)):
        return 0
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


def _waiting(laws_path: Path) -> tuple[Path, dict, list[dict]]:
    """The bills in procedure now (procedure.json beside laws.json), as records the commands for laws can read: each
    with its `bill_pdf`. They are read and summarised like the bills of adopted laws, before the vote."""
    path = laws_path.parent / "procedure.json"
    if not path.exists():
        return path, {}, []
    store = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for pdf, b in store["bills"].items():
        if b["last_seen"] == store["fetched"]:
            b["bill_pdf"] = pdf
            out.append(b)
    return path, store, out


def memoranda(args) -> int:
    """Each adopted law's bill, read once: its memorandum's sections and constitutional basis, into
    data/bills/<file>.json, and the law's area(s) into data/laws.json."""
    path = Path(args.laws)
    store = json.loads(path.read_text(encoding="utf-8"))
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    read = failed = 0
    proc_path, proc, waiting = _waiting(path)
    for law in list(store["laws"].values()) + waiting:
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
    if waiting:
        for b in waiting:
            b.pop("bill_pdf", None)
        proc_path.write_text(jsonfile.dumps(proc, "bills"), encoding="utf-8")
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
    stats = site.build(ROOT, Path(args.out), args.domain or None, clean=not args.html_links, cyrillic=not args.latin_only)
    print(", ".join(f"{k}: {v}" for k, v in stats.items()))
    bad = site.check(Path(args.out))  # the site is not published while any page breaks the rules
    for b in bad:
        print(f"  {b}")
    return 1 if bad else 0


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
    todo, claimed = {}, set()
    waiting = _waiting(Path(args.laws))[2]  # bills in procedure first: they are what is about to be voted on
    everything = waiting + sorted(store["laws"].values(), key=lambda l: l.get("passed") or "", reverse=True)
    for law in everything:
        name = law.get("bill_file")
        if not name or not (Path(args.bills) / name).exists():
            continue
        memo = json.loads((Path(args.bills) / name).read_text(encoding="utf-8"))
        if not memo.get("sections"):
            skipped += 1
            continue
        if name in claimed:  # two laws linked to one memorandum: a linking error, and each would rewrite the other's
            print(f"  {name}: also linked to {law['title'][:80]} (skipped)")
            continue
        claimed.add(name)
        target = out_dir / name
        text = summaries.material(law, memo)
        if target.exists() and json.loads(target.read_text(encoding="utf-8")).get("fingerprint") == \
                summaries.fingerprint(text):
            continue
        if args.limit and done + len(todo) >= args.limit:
            break
        if getattr(args, "batch", False):
            todo[name] = (law, memo, target)
            continue
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
    if getattr(args, "batch", False):
        from zailiprotiv import batch
        client, state = _batch_client(args)
        if client is None:
            return 0
        kind = f"summaries-{CONVOCATION}"
        pending = state.pending(kind)
        for name in (pending or {}).get("names", []):
            if name not in todo:
                law = next(l for l in everything if l.get("bill_file") == name)
                todo[name] = (law, json.loads((Path(args.bills) / name).read_text(encoding="utf-8")), out_dir / name)
        requests = {name: {"model": summaries.MODEL, "max_tokens": batch.ROOM, "system": batch.cached(summaries.SYSTEM),
                           "messages": [{"role": "user", "content": summaries.material(law, memo)}]}
                    for name, (law, memo, _) in todo.items()}
        replies = batch.run(client, state, kind, requests, args.wait)
        for name, text in sorted((replies or {}).items()):
            law, memo, target = todo[name]
            try:
                result = summaries.record(law, memo, summaries.parse(text), summaries.MODEL)
            except (ValueError, json.JSONDecodeError) as e:
                failed += 1
                print(f"  failed {law['title'][:90]}: {e}")
                continue
            target.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
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
            try:
                paras = transcripts.paragraphs(body)
            except transcripts.Unreadable as e:  # the day is left out, and the log says why
                print(f"  {d['url']}: {e}")
                paras = []
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


def profiles_export(args) -> int:
    """The speeches of every MP with enough of them in the notes read, one JSON file each, for overviews written in
    a session (rules: data/profiles/RULES.md). MPs who have an overview are skipped unless --again."""
    from zailiprotiv import profiles
    to = Path(args.to)
    to.mkdir(parents=True, exist_ok=True)
    n = 0
    for key, own in sorted(profiles.speeches(ROOT).items()):
        long = [s for s in own if len(s["text"].split()) >= profiles.LONG]
        name = key.replace(" ", "-") + ".json"
        if len(long) < args.min or ((ROOT / "profiles" / name).exists() and not args.again):
            continue
        (to / name).write_text(json.dumps({"mp": key, "total_speeches": len(own), "speeches": profiles.selection(own)},
                                          ensure_ascii=False, indent=1), encoding="utf-8")
        n += 1
    print(f"exported: {n} to {to}")
    return 0


def profiles_import(args) -> int:
    """Overviews written in a session (DIR/out/<name>.json beside the exported DIR/<name>.json), checked and saved to
    data/profiles/. With --check FILE: only say what is wrong with one reply."""
    from zailiprotiv import profiles
    src = Path(args.dir)
    files = [Path(args.check)] if args.check else sorted((src / "out").glob("*.json"))
    saved = refused = 0
    for f in files:
        try:
            reply, material = json.loads(f.read_text(encoding="utf-8")), json.loads((src / f.name).read_text(encoding="utf-8"))
            bad = profiles.check(reply, material)
        except (ValueError, KeyError, TypeError, OSError) as e:
            bad = [f"nečitljivo: {e}"]
        if bad:
            refused += 1
            print(f"  {f.name}: " + "; ".join(bad))
        elif not args.check:
            (ROOT / "profiles").mkdir(exist_ok=True)
            (ROOT / "profiles" / f.name).write_text(json.dumps(profiles.record(reply, material, args.model), ensure_ascii=False,
                                                               indent=1) + "\n", encoding="utf-8")
            saved += 1
    print("OK" if args.check and not refused else f"saved: {saved}, refused: {refused}")
    return 1 if refused else 0


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


def _batch_client(args):
    """The API client and the batch state, or None when there is no way in (the workflow then does nothing): an API
    key, or in GitHub Actions the repository's identity exchanged for a short-lived token (`federated`)."""
    import os
    from zailiprotiv import batch, federated
    state = batch.State(ROOT / "batches.json")
    if os.environ.get("ANTHROPIC_API_KEY"):
        import anthropic
        return anthropic.Anthropic(), state
    if federated.available():
        return federated.client(), state
    print("No ANTHROPIC_API_KEY and no federated sign-in: nothing sent")
    return None, None


def profiles_batch(args) -> int:
    """Overviews of what MPs most often say, for every MP with enough speeches and no overview yet, written through
    the Batch API, checked like a session's (quotes word for word) and saved to data/profiles/."""
    from zailiprotiv import batch, profiles, summaries
    client, state = _batch_client(args)
    if client is None:
        return 0
    kind, system = "profiles", profiles.system(ROOT)
    materials = {}
    for key, own in sorted(profiles.speeches(ROOT).items()):
        long = [s for s in own if len(s["text"].split()) >= profiles.LONG]
        name = key.replace(" ", "-") + ".json"
        if len(long) < args.min or ((ROOT / "profiles" / name).exists() and not args.again) or state.gave_up(kind, name):
            continue
        materials[name] = {"mp": key, "total_speeches": len(own), "speeches": profiles.selection(own)}
        if args.limit and len(materials) >= args.limit:
            break
    pending = state.pending(kind)
    if pending:  # the material of a batch already sent, so its replies can be checked
        for name in pending["names"]:
            if name not in materials:
                key = name.removesuffix(".json").replace("-", " ")
                own = profiles.speeches(ROOT).get(key, [])
                materials[name] = {"mp": key, "total_speeches": len(own), "speeches": profiles.selection(own)}
    requests = {n: {"model": summaries.MODEL, "max_tokens": batch.ROOM, "system": batch.cached(system),
                    "messages": batch.messages(kind, n, json.dumps(m, ensure_ascii=False), state)}
                for n, m in materials.items()}
    replies = batch.run(client, state, kind, requests, args.wait)
    if replies is None:
        return 0
    saved = refused = 0
    for name, text in sorted(replies.items()):
        material = materials[name]
        try:
            reply = profiles.reply_json(text)
            bad = profiles.check(reply, material)
            result = None if bad else profiles.record(reply, material, summaries.MODEL)
        except (ValueError, KeyError, TypeError, AttributeError) as e:
            bad = [f"nečitljivo: {type(e).__name__}: {e}"]
        if bad:
            state.refuse(kind, name, text, bad)
            refused += 1
            print(f"  refused {name}: " + "; ".join(bad)[:300])
            continue
        (ROOT / "profiles" / name).write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        state.accept(kind, name)
        saved += 1
    state.save()
    print(f"profiles saved: {saved}, refused: {refused} (sent again next run, at most {batch.TRIES} tries)")
    return 0


def debates_batch(args) -> int:
    """Debate summaries for the laws with most votes against whose notes were read and that have none (or whose
    material changed), written through the Batch API; quotes not in the notes word for word are dropped."""
    from zailiprotiv import batch, debates, summaries
    client, state = _batch_client(args)
    if client is None:
        return 0
    # A sample (--only, with --out): the named laws written again by the model in ZAILIPROTIV_MODEL into a folder
    # of their own, to compare models without touching the published texts.
    only = set(filter(None, (args.only or "").split(",")))
    kind = f"sample-{CONVOCATION}" if only else f"debates-{CONVOCATION}"
    found, votes_, bills_ = _debated(args)
    seated, df = debates.seats(votes_), debates.document_frequency(bills_)
    out = Path(args.out) if args.out else DATA / "debates"
    if only and not args.out:
        raise SystemExit("--only needs --out: a sample must not replace the published texts")
    out.mkdir(parents=True, exist_ok=True)
    chosen, pending = {}, state.pending(kind)
    wanted = set(pending["names"]) if pending else set()
    for i, (law, bill, n, final, item) in enumerate(found):
        name = law["bill_file"]
        text = debates.material(law, bill, n, final, seated, item, df)
        done = (out / name).exists() and json.loads((out / name).read_text(encoding="utf-8")).get("fingerprint") == \
            debates.fingerprint(text)
        if only:
            if name in only and not done:
                chosen[name] = (law, n, final, text)
        elif name in wanted or (i < args.top and not done and not state.gave_up(kind, name)):
            chosen[name] = (law, n, final, text)
    requests = {name: {"model": summaries.MODEL, "max_tokens": batch.ROOM, "system": batch.cached(debates.SYSTEM),
                       "messages": batch.messages(kind, name, text, state)}
                for name, (law, n, final, text) in chosen.items()}
    replies = batch.run(client, state, kind, requests, args.wait, force=bool(only))
    if replies is None:
        return 0
    saved = refused = 0
    for name, reply in sorted(replies.items()):
        law, n, final, text = chosen[name]
        try:
            debate, dropped = debates.parse(reply, n, debates.speaker_groups(n, final, seated))
        except (ValueError, AttributeError, TypeError) as e:
            state.refuse(kind, name, reply, [str(e) or type(e).__name__])
            refused += 1
            print(f"  refused {name}: {e}")
            continue
        (out / name).write_text(json.dumps(debates.record(law, text, debate, summaries.MODEL, dropped),
                                           ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        state.accept(kind, name)
        saved += 1
        print(f"  {name}: {len(debate['citati'])} quotes kept, {len(dropped)} dropped")
    state.save()
    print(f"debates saved: {saved}, refused: {refused}")
    return 0


def status(args) -> int:
    """What the data still lacks, per convocation: laws without a final vote, a memorandum, a summary or a debate
    summary; notes read; and the batches still running or refused. Read-only."""
    from zailiprotiv import batch, profiles, site
    rows = []
    for conv in sorted((d.name for d in ROOT.iterdir() if (d / "laws.json").exists()), key=int, reverse=True):
        d = ROOT / conv
        laws_ = json.loads((d / "laws.json").read_text(encoding="utf-8"))["laws"].values()
        names = {l.get("bill_file") for l in laws_ if l.get("bill_file")}
        have = lambda sub: {f.name for f in (d / sub).glob("*.json")} if (d / sub).is_dir() else set()
        memos = {n for n in names if (d / "bills" / n).exists() and
                 json.loads((d / "bills" / n).read_text(encoding="utf-8")).get("sections")}
        notes = have("transcripts")
        read = sum(1 for n in notes if json.loads((d / "transcripts" / n).read_text(encoding="utf-8")).get("speeches"))
        rows.append((conv, len(laws_), sum(1 for l in laws_ if not l.get("final_vote")), len(names - memos),
                     len(memos - have("summaries")), len(notes), read, len(have("debates"))))
    print(f"{'saziv':>5} {'zakona':>7} {'bez konačnog':>13} {'bez obrazl.':>11} {'bez sažetka':>11} "
          f"{'beleške':>8} {'sa govorima':>11} {'rasprave':>9}")
    for r in rows:
        print(f"{r[0]:>5} {r[1]:>7} {r[2]:>13} {r[3]:>11} {r[4]:>11} {r[5]:>8} {r[6]:>11} {r[7]:>9}")
    eligible = sum(1 for own in profiles.speeches(ROOT).values()
                   if len([s for s in own if len(s["text"].split()) >= profiles.LONG]) >= args.min)
    done = len([f for f in (ROOT / "profiles").glob("*.json")])
    print(f"pregledi poslanika: {done} (sa dovoljno govora: {eligible})")
    state = batch.State(ROOT / "batches.json")
    for kind, p in state.data["pending"].items():
        print(f"batch u toku: {kind} {p['id']} ({len(p['names'])})")
    for kind, names in state.data["refused"].items():
        print(f"odbijeno: {kind}: " + ", ".join(f"{n} ({r['tries']}x)" for n, r in sorted(names.items())))
    for kind, models in sorted(state.data["usage"].items()):
        for model, u in sorted(models.items()):
            print(f"potrošeno: {kind} {model}: {u['replies']} odgovora, ulaz {u['input']:,} (+ keš upis "
                  f"{u['cache_written']:,}, keš čitanje {u['cache_read']:,}), izlaz {u['output']:,} tokena")
    return 0


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
    p.add_argument("--batch", action="store_true", help="through the Batch API (half the price; results may come next run)")
    p.add_argument("--wait", type=float, default=300, help="with --batch: minutes to wait for the batch")
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
    p = commands.add_parser("profiles-export", help="MPs' speeches from the notes read, for overviews written in a session")
    p.add_argument("--to", required=True)
    p.add_argument("--min", type=int, default=10, help="speeches of some length an MP needs")
    p.add_argument("--again", action="store_true")
    p.set_defaults(run=profiles_export)
    p = commands.add_parser("profiles-import", help="save overviews of MPs' speeches written in a session")
    p.add_argument("dir")
    p.add_argument("--model", default="")
    p.add_argument("--check", default="", help="check one reply only")
    p.set_defaults(run=profiles_import)
    p = commands.add_parser("debates-import", help="save debate summaries written in a session")
    p.add_argument("file")
    p.add_argument("--model", required=True)
    p.set_defaults(run=debates_import)
    p = commands.add_parser("profiles-batch", help="overviews of MPs' speeches through the Batch API → data/profiles/")
    p.add_argument("--min", type=int, default=10, help="speeches of some length an MP needs")
    p.add_argument("--again", action="store_true")
    p.add_argument("--limit", type=int, default=0, help="send at most this many (0: all)")
    p.add_argument("--wait", type=float, default=300, help="minutes to wait for the batch before leaving it for next run")
    p.set_defaults(run=profiles_batch)
    p = commands.add_parser("debates-batch", help="debate summaries through the Batch API → data/<N>/debates/")
    p.add_argument("--top", type=int, default=20)
    p.add_argument("--wait", type=float, default=300)
    p.add_argument("--only", help="a sample: these bill files only (comma-separated), sent even while paused")
    p.add_argument("--out", help="where a sample is written")
    p.set_defaults(run=debates_batch)
    p = commands.add_parser("procedure", help="the bills in procedure now → data/<N>/procedure.json")
    p.add_argument("--out", default=str(DATA / "procedure.json"))
    p.set_defaults(run=in_procedure)
    p = commands.add_parser("notes-site", help="the stenographic notes as pages of their own → --out")
    p.add_argument("--out", default="_beleske")
    p.set_defaults(run=notes_site_cmd)
    p = commands.add_parser("notes-upload", help="send the notes' pages that changed to the R2 bucket")
    p.add_argument("--dir", default="_beleske")
    p.add_argument("--bucket", default="zailiprotiv-beleske")
    p.add_argument("--dry", action="store_true", help="say what would be sent, send nothing")
    p.set_defaults(run=notes_upload_cmd)
    p = commands.add_parser("notes-check", help="do the notes' pages answer at their public address?")
    p.add_argument("--url", default="https://beleske.zailiprotiv.rs/")
    p.set_defaults(run=notes_check_cmd)
    p = commands.add_parser("photos", help="MPs' portraits from the Assembly's list → data/photos/")
    p.set_defaults(run=photos_cmd)
    p = commands.add_parser("status", help="what the data still lacks, per convocation")
    p.add_argument("--min", type=int, default=10)
    p.set_defaults(run=status)
    p = commands.add_parser("site", help="build the static site")
    p.add_argument("--out", default="_site")
    p.add_argument("--domain", default="zailiprotiv.rs")
    p.add_argument("--latin-only", action="store_true", help="skip the Cyrillic edition (cir/), for a quicker build")
    p.add_argument("--html-links", action="store_true", help="keep .html in links, to open the pages from disk")
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
