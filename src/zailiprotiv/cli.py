"""Command line: `zailiprotiv <command>`."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
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
    for title in getattr(skupstina.index, "later", []):  # the votes workflow opens an issue on this line
        print(f"::notice::A later convocation's sitting is listed: {title}")
    for s in found:
        print(f"  {len(s.votes):4}  {s.title[:100]}")
    # No roll call at all in the current convocation is a sign the page changed; a newer one may have none yet.
    if found and not total and CONVOCATION == CURRENT:
        print("no roll calls found: has the sittings' page layout changed?")
        return 1
    return 0


def videos_cmd(args) -> int:
    """The convocation's plenary recordings by day, from the broadcaster's archive page → data/<N>/videos.json."""
    from zailiprotiv import videos
    page = CONVOCATIONS[CONVOCATION].get("videos")
    if not page:
        print("no archive of recordings for this convocation")
        return 0
    found = videos.parse(skupstina.fetch(page).decode("utf-8", errors="replace"))
    days = videos.by_day(found)

    def exists(url: str) -> bool:  # a HEAD request: the file's headers, not the file
        import urllib.request
        from zailiprotiv.config import USER_AGENT
        try:
            req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.status == 200
        except OSError:
            return False

    for day in sorted(days)[-3:]:  # the latest days only: the archive adds a day's last parts within hours
        days[day] += videos.unlisted(days[day], exists)
    out = DATA / "videos.json"
    if out.exists() and len(days) < 0.8 * len(json.loads(out.read_text(encoding="utf-8")).get("days") or {}):
        print(f"::warning::videos: the archive gives {len(days)} days, fewer than the file; kept the file")
        return 0
    store = {"fetched": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(), "source": page,
             "days": days}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(jsonfile.dumps(store, "days"), encoding="utf-8")
    print(f"recordings: {len(found)} on {len(days)} days")
    return 0


def uzivo_pull(args) -> int:
    """The live page's records of who spoke when (live/) → data/<N>/uzivo/<date>.json. The page runs on the
    maintainer's computer and may be off: then nothing changes and the run goes on."""
    from zailiprotiv import uzivo
    settings = json.loads((ROOT / "settings.json").read_text(encoding="utf-8")) if (ROOT / "settings.json").exists() else {}
    base = settings.get("live_page", "")
    if not base:
        print("no live_page in data/settings.json")
        return 0
    try:
        days = uzivo.pull(ROOT, base)
    except Exception as exc:  # the computer is off, or the page is down
        print(f"::notice::live records not taken: {exc}")
        days = None
    if days is not None:
        print(f"live records: {', '.join(days) or 'nothing new'}")
    try:  # a sitting on now, by the live page's reading: the site's bar (data/live.json)
        print(f"sitting on now (live page): {uzivo.live_mark(ROOT, base)}")
    except Exception as exc:
        (ROOT / "live.json").unlink(missing_ok=True)  # the page down says nothing of a sitting: the bar goes
        print(f"::notice::live state not read: {exc}")
    return 0


def arhiva_cmd(args) -> int:
    """The archive's recordings lined up with the live page's records (arhiva.py): each new file placed on the clock
    by the captions read in a few of its frames, and each sitting day's file in data/<N>/snimak/ written or given the
    places it lacked. Needs ffmpeg, Tesseract's Serbian, numpy and pytesseract; a day without them changes nothing."""
    from zailiprotiv import arhiva
    changed = arhiva.run(ROOT, CONVOCATION)
    print(f"archive: {', '.join(changed) or 'nothing new'}")
    return 0


def govor_cmd(args) -> int:
    """Who spoke when on a sitting day, from the notes lined up with the recording written down word by word
    (govor.py; the words from live/uzivo/zvuk_dana.py in args.heard). Writes data/<N>/snimak/<day>.json; each file's
    start on the clock comes from data/<N>/arhiva.json, or else from the live page's record of that day (the
    speakers it read in captions), and a file with neither is reported and its turns left out."""
    from zailiprotiv import govor, mps, translit
    from zailiprotiv.cyrillic import cyr
    from zailiprotiv.site import slug as site_slug
    conv_dir = ROOT / CONVOCATION
    day_files = [p["url"] for p in sorted(json.loads((conv_dir / "videos.json").read_text(encoding="utf-8"))["days"]
                                          .get(args.day, []), key=lambda p: p["part"])]
    speeches = []
    for path in sorted((conv_dir / "transcripts").glob("*.json")):
        notes = json.loads(path.read_text(encoding="utf-8"))
        day_no = {d["day"] for d in notes.get("days", []) if d.get("listed_date") == args.day}
        speeches += [{"key": f"{path.stem}/{k}", **s} for k, s in sorted(notes.get("speeches", {}).items())
                     if s.get("day") in day_no]
    if not speeches or not day_files:
        print(f"govor {args.day}: {len(speeches)} speeches in the notes, {len(day_files)} files: nothing to do")
        return 1
    placed = govor.place(speeches, govor.heard(Path(args.heard), day_files))
    # Each speaker as the site names them: the newest convocation's list of MPs, else the name as the notes give it.
    members = {mps.key(m["name"]): m for m in json.loads((conv_dir / "members.json").read_text(encoding="utf-8"))["members"]}
    known = {}
    for f in list((conv_dir / "snimak").glob("*.json")) + list((conv_dir / "uzivo").glob("*.json")):
        for t in json.loads(f.read_text(encoding="utf-8")).get("govori", []):
            if t.get("adresa"):
                known.setdefault(mps.key(cyr(" ".join(t["ime"].split(" ", 1)[::-1]))), t)

    def who(speaker: str) -> dict:
        k = mps.key(speaker)
        if k in known:
            t = known[k]
            return {"ime": t["ime"], "adresa": t["adresa"], "grupa": t.get("grupa", ""), "uloga": t.get("uloga", "")}
        words = translit.latin(speaker).title().split()
        name = " ".join(words[-1:] + words[:-1])
        m = members.get(k)
        return {"ime": name, "adresa": site_slug(name, 60) if m else "", "grupa": translit.latin(m["group"]) if m else "",
                "uloga": translit.latin(m["group"]) if m else ""}

    kept = json.loads((conv_dir / "arhiva.json").read_text(encoding="utf-8")) if (conv_dir / "arhiva.json").exists() else {}
    record_path = conv_dir / "uzivo" / f"{args.day}.json"
    record = json.loads(record_path.read_text(encoding="utf-8")).get("govori", []) if record_path.exists() else []
    seen = [(mps.key(cyr(" ".join(t["ime"].split(" ", 1)[::-1]))), t["od"]) for t in record if t.get("okvira", 0) >= 2]
    files = []
    for url in day_files:
        if "od" in kept.get(url, {}):
            files.append({"url": url, "od": kept[url]["od"], "kako": "arhiva.json"})
            continue
        # Every start the file could have by a speech placed in it and a turn of the same speaker in the live record;
        # the file's start is where most of them agree (within 30 s), from two speakers' speeches on.
        diffs = sorted(od - s["od"] for s in placed if s.get("datoteka") == url and not s.get("chair")
                       for key, od in seen if key == mps.key(s["speaker"]))
        good = max(([d for d in diffs if a <= d <= a + 30] for a in diffs), key=len, default=[])
        if len(good) >= 2:
            files.append({"url": url, "od": int(statistics.median(good)), "kako": f"zapis uživo, {len(good)} govora"})
        else:
            files.append({"url": url, "od": None, "kako": "nepoznato"})
    for f in files:
        n = sum(1 for s in placed if s.get("datoteka") == f["url"] and not s.get("chair"))
        print(f"  {f['url'].rsplit('/', 1)[1]}: start {f['od']} ({f['kako']}), {n} speeches placed")
    turns = [t for t in govor.day(placed, files, who) if t["od"] is not None]
    left = [s for s in placed if not s.get("chair") and "datoteka" not in s]
    print(f"govor {args.day}: {len(speeches)} speeches, {len(turns)} turns written, "
          f"{len(left)} speeches of MPs and guests with no place: {', '.join(sorted({s['speaker'] for s in left}))}")
    out = {"dan": args.day, "izvor": "govor", "napomena": govor.NOTE + (args.note or ""),
           "pokriveno": [{"od": min(t["od"] for t in turns), "do": max(t["do"] for t in turns)}] if turns else [],
           "govori": turns,
           "datoteke": [{"url": f["url"], "od": f["od"], "trajanje": int(kept.get(f["url"], {}).get("trajanje") or 0)}
                        for f in files if f["od"] is not None]}
    if args.dry_run:
        return 0
    path = conv_dir / "snimak" / f"{args.day}.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT.parent).as_posix()}")
    return 0


def glas_dan_cmd(args) -> int:
    """A sitting day with no notes yet, from captions and voices (govor.voice_day; 20 Nov 2026): the live record's
    turns the caption gave, and where there were none, the stretches ko.py named by voice (args.stretches, written
    in the analysis image: {"files": [{"url", "trajanje"}], "stretches": {url: [[address, from, to, likeness]]},
    "known": {url: start}}). Each file's clock from `known` or from captions read in passing (govor.clock); a file
    with neither is reported and its stretches left out. Writes data/<N>/snimak/<day>.json unless the day has been
    read from its notes."""
    from zailiprotiv import govor, translit
    conv_dir = ROOT / CONVOCATION
    path = conv_dir / "snimak" / f"{args.day}.json"
    if path.exists() and json.loads(path.read_text(encoding="utf-8")).get("izvor") == "govor":
        print(f"glas-dan {args.day}: read from the notes already; the notes win")
        return 0
    data = json.loads(Path(args.stretches).read_text(encoding="utf-8"))
    record = json.loads((conv_dir / "uzivo" / f"{args.day}.json").read_text(encoding="utf-8"))
    rec = record.get("govori", [])
    files = data["files"]
    starts = govor.clock(files, data["stretches"], rec, data.get("known", {}))
    for f in files:
        print(f"  {f['url'].rsplit('/', 1)[1]}: {starts.get(f['url'], ('?', 'not placed'))}")
    named = {}
    for p in list((conv_dir / "snimak").glob("*.json")) + list((conv_dir / "uzivo").glob("*.json")):
        if p == path:  # not the file this writes: a name it got wrong would come back
            continue
        for t in json.loads(p.read_text(encoding="utf-8")).get("govori", []):
            if t.get("adresa"):
                named.setdefault(t["adresa"], {k: t.get(k, "") for k in ("ime", "adresa", "grupa", "uloga")})

    from zailiprotiv.site import slug as site_slug
    for m in json.loads((conv_dir / "members.json").read_text(encoding="utf-8"))["members"]:
        # "Surname Given", as the site lists names, without the degree the list puts in some ("ДРЕЦУН мр МИЛОВАН")
        name = " ".join(w for w in translit.latin(m["name"]).split() if w.lower().rstrip(".") not in {"mr", "dr", "prof"}).title()
        group = translit.latin(m.get("group") or "")
        s = site_slug(name, 60)
        named.setdefault(s, {"ime": name, "adresa": s, "grupa": group, "uloga": group})
        if not named[s].get("uloga"):  # a caption read with no list line: the list the Assembly gives
            named[s] = {**named[s], "grupa": named[s].get("grupa") or group, "uloga": group}

    def who(address: str) -> dict:
        return named.get(address) or {"ime": address, "adresa": address, "grupa": "", "uloga": ""}

    # The captions' turns, by the live page's rule (okvira 2 or more: counted); then the voices where no caption was.
    caps = [{**t, "po": "potpis"} for t in rec if t.get("okvira", 0) >= 2]
    all_voiced = govor.voice_day(files, data["stretches"], starts, who)
    # A caption read with no list line under it, where the voice is surely someone else's, is a misreading (19 Nov
    # 2026, 20:58: "Vučić" in four frames while Petrašinović spoke): the voice stands.
    caps = [c for c in caps if c.get("uloga") or not any(
        v["adresa"] != c.get("adresa") and v["od"] <= c["od"] and c["do"] <= v["do"] for v in all_voiced)]
    for c in caps:  # a caption read with no list line: the list the Assembly gives
        if not c.get("uloga") and c.get("adresa") in named:
            c["uloga"] = named[c["adresa"]].get("uloga", "")
    voiced = [t for t in all_voiced
              if not any(c["od"] - 30 <= t["od"] <= c["do"] + 30 or t["od"] <= c["od"] <= t["do"] for c in caps)]
    for c in caps:  # the captions' turns get their place in the archive's files too
        for f in files:
            if f["url"] in starts and starts[f["url"]][0] <= c["od"] < starts[f["url"]][0] + f["trajanje"]:
                c.update(datoteka=f["url"], snimak=int(max(0, c["od"] - starts[f["url"]][0] - govor.LEAD)), video="")
    turns = sorted(caps + voiced, key=lambda t: t["od"])
    how = "; ".join(f"{f['url'].rsplit('/', 1)[1]}: {starts[f['url']][1]}" for f in files if f["url"] in starts)
    out = {"dan": args.day, "izvor": "glas", "napomena": govor.VOICE_NOTE + f"Sat delova snimka: {how}.",
           "pokriveno": [{"od": int(starts[f["url"]][0]), "do": int(starts[f["url"]][0] + f["trajanje"])}
                         for f in files if f["url"] in starts],
           "govori": turns,
           "datoteke": [{"url": f["url"], "od": int(starts[f["url"]][0]), "trajanje": int(f["trajanje"])}
                        for f in files if f["url"] in starts]}
    print(f"glas-dan {args.day}: {len(caps)} turns by caption, {len(voiced)} by voice, "
          f"{sum(t['do'] - t['od'] for t in voiced) // 60} min by voice")
    if not args.dry_run:
        path.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"wrote {path.as_posix()}")
    return 0


def prepis_cmd(args) -> int:
    """An automatic transcript of a sitting day's speeches from the archive's recording (prepis.py; Whisper)."""
    from zailiprotiv import prepis
    prepis.run(ROOT, CONVOCATION, args.day, model=args.model, minutes=args.minutes)
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

    old = set(manifest)
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
    from zailiprotiv import files_site
    print("notes: " + files_site.purge("https://beleske.zailiprotiv.rs/", [n for n in send if n in old and n not in failed] + (gone if not failed else [])))
    print(f"notes: sent {len(send) - len([f for f in failed if f in now])}, removed {len(gone) if not failed else 0}, failed {len(failed)}")
    return 1 if failed else 0


def notes_cors_cmd(args) -> int:
    """Let the site read the notes' search index from the bucket's address (the search page merges it with its own):
    a rule on the bucket that answers the site's origins. A key that may not set it says so; then it is set by hand."""
    from zailiprotiv import files_site
    rule = {"CORSRules": [{"AllowedOrigins": ["https://zailiprotiv.rs", "https://www.zailiprotiv.rs"],
                           "AllowedMethods": ["GET", "HEAD"], "AllowedHeaders": ["*"], "MaxAgeSeconds": 86400}]}
    try:
        files_site.client().put_bucket_cors(Bucket=args.bucket, CORSConfiguration=rule)
        print(f"notes: the bucket {args.bucket} answers the site's origins")
    except Exception as e:
        print(f"notes: the rule was not set ({type(e).__name__}: {e}); set it by hand in the bucket's settings")
    return 0


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


def files_split_cmd(args) -> int:
    """Move the downloads and share pictures out of a built site and point its pages at the bucket's address
    (files_url in data/settings.json; without it nothing is done)."""
    from zailiprotiv import files_site
    store = ROOT / "settings.json"
    url = args.url or (json.loads(store.read_text(encoding="utf-8")).get("files_url", "") if store.exists() else "")
    if not url:
        print("files: no files_url in data/settings.json, the site keeps its files")
        return 0
    n = files_site.split(Path(args.site), Path(args.out), url, args.domain)
    print(f"files: {n['moved']} moved to {args.out}, links changed in {n['pages']} pages")
    return 0


def files_upload_cmd(args) -> int:
    """Make the R2 bucket hold exactly the folder of downloads and share pictures."""
    import os
    from zailiprotiv import files_site
    if not Path(args.dir).is_dir():
        print(f"files: no folder {args.dir}, nothing to send")
        return 0
    missing = [v for v in ("R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "CLOUDFLARE_ACCOUNT_ID") if not os.environ.get(v)]
    if missing:
        print("not sent, missing: " + ", ".join(missing))
        return 1
    try:
        return 1 if files_site.sync(Path(args.dir), args.bucket, args.dry, url=args.url) else 0
    except Exception as e:
        print(f"not sent, the bucket {args.bucket} does not answer: {e}")
        try:  # which buckets does this key see? (only a key allowed to list them can say)
            print("buckets: " + ", ".join(b["Name"] for b in files_site.client().list_buckets()["Buckets"]))
        except Exception as e2:
            print(f"buckets: the key may not list them ({type(e2).__name__})")
        return 1


def files_purge_cmd(args) -> int:
    """Tell Cloudflare's cache to forget these files of a bucket's public address (by hand; uploads do it themselves)."""
    from zailiprotiv import files_site
    said = files_site.purge(args.url, args.names)
    print("files: " + said)
    return 0 if said.startswith("cache purged") else 1


def members_cmd(args) -> int:
    """The sitting MPs from the Assembly's list → data/<N>/members.json (members.py), for the newest convocation
    before its first roll call. A page with far fewer MPs than the file keeps the file."""
    from zailiprotiv import members
    from zailiprotiv.config import NEWEST
    conv = NEWEST
    import time
    page = skupstina.fetch(members.URL).decode("utf-8", "replace")
    found = members.read(page)
    by_group = {}
    for value, label in members.groups(page):  # each group's MPs: the page filtered by it (members.py)
        time.sleep(DELAY)
        by_group[label] = members.read(skupstina.fetch(members.group_url(value)).decode("utf-8", "replace"))
        print(f"  {label}: {len(by_group[label])}")
    found = members.with_groups(found, by_group)
    path = ROOT / conv / "members.json"
    old = json.loads(path.read_text(encoding="utf-8"))["members"] if path.exists() else []
    if len(found) < 200 or (old and len(found) < len(old) * 0.8):
        print(f"members: {len(found)} read, {len(old)} kept; the file stays")
        return 0 if old else 1
    # Each MP's occupation, from the MP's own page at the Assembly: read once, then kept (members.py).
    had = {(m["name"], m["year"]): m["occupation"] for m in old if "occupation" in m}
    links, read_now = members.pages(page), 0
    for m in found:
        if (m["name"], m["year"]) in had:
            m["occupation"] = had[(m["name"], m["year"])]
        elif m["name"] in links:
            time.sleep(DELAY)
            try:
                m["occupation"] = members.occupation(skupstina.fetch(links[m["name"]]).decode("utf-8", "replace"))
                read_now += 1
            except skupstina.FetchError as e:  # tried again at the next run
                print(f"  {m['name']}: {e}")
    print(f"members: occupations read now: {read_now}, known: {sum('occupation' in m for m in found)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(members.dumps(dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(), found),
                    encoding="utf-8")
    print(f"members: {len(found)} MPs of convocation {conv}")
    return 0


def offices_cmd(args) -> int:
    """Who holds which office in the newest convocation (the Speaker, the deputy Speakers, the groups' chairs, the
    committees, the delegations) → data/<N>/offices.json, and the Assembly's news → data/vesti.json (offices.py). The
    committees' and delegations' own pages are read when their lists changed, when a relevant news item is new, or
    once a week; an earlier convocation's (offices.ARCHIVE) once."""
    from zailiprotiv import offices
    from zailiprotiv.config import NEWEST
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    today = now.date().isoformat()

    def get(url):
        time.sleep(DELAY)
        return skupstina.fetch(url).decode("utf-8", "replace")

    news_path = ROOT / "vesti.json"
    old_news = json.loads(news_path.read_text(encoding="utf-8"))["items"] if news_path.exists() else []
    found_news = offices.news(get(offices.NEWS))
    items, fresh = offices.merge_news(old_news, found_news, today)
    if found_news:
        news_path.write_text(offices.dumps_news(now.isoformat(), items), encoding="utf-8")
    print(f"news: {len(found_news)} listed, {len(items) - len(old_news)} new, {len(fresh)} relevant new")
    for x in fresh:
        print(f"  relevant: {x['title']} ({x['url']})")
    if fresh and os.environ.get("GITHUB_STEP_SUMMARY"):  # on the run's page, for whoever looks at it
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write("### Nove vesti Skupštine o izboru i funkcijama\n\n"
                    + "".join(f"- [{x['title']}]({x['url']})\n" for x in fresh) + "\n")

    def read_parts(listing):
        out = []
        for t, url in offices.parts(get(listing), listing):
            page = get(url)
            out.append((t, url, offices.committee(page) or offices.delegation(page)))  # named as the list names it
        return out

    for conv, pages in offices.ARCHIVE.items():  # an earlier convocation's: its archive doesn't change
        path = ROOT / conv / "offices.json"
        if path.exists():
            continue
        found = offices.offices_of(speaker=None, vice=[], chairs=[], committees=read_parts(pages["committees"]),
                                   delegations=read_parts(pages["delegations"]), sources={})
        if found:
            path.write_text(offices.dumps(now.isoformat(), [{**o, "since": ""} for o in found], now.isoformat()),
                            encoding="utf-8")
        print(f"offices: {len(found)} in convocation {conv}'s archive")

    conv = NEWEST
    path = ROOT / conv / "offices.json"
    old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"offices": [], "parts_read": ""}
    sources = {"speaker": offices.SPEAKER, "vice": offices.VICE, "group": offices.GROUP_CHAIRS}
    speaker = offices.person(get(offices.SPEAKER))
    vice, chairs = offices.blocks(get(offices.VICE)), offices.blocks(get(offices.GROUP_CHAIRS))
    listed = {k: offices.parts(get(u), u) for k, u in (("committee", offices.COMMITTEES),
                                                        ("delegation", offices.DELEGATIONS))}
    had = {k: sorted({o["source"] for o in old["offices"] if o["kind"] == k}) for k in listed}
    last = dt.datetime.fromisoformat(old["parts_read"]) if old.get("parts_read") else None
    again = (fresh or last is None or (now - last).total_seconds() > offices.WEEK
             or any(sorted(u for _, u in listed[k]) != had[k] for k in listed))
    if again:
        parts = {k: read_parts(u) for k, u in (("committee", offices.COMMITTEES), ("delegation", offices.DELEGATIONS))}
        read_at = now.isoformat()
    else:  # the committees and delegations as last read
        parts = {k: [] for k in listed}
        for o in old["offices"]:
            if o["kind"] in parts:
                body = next((p for p in parts[o["kind"]] if p[1] == o["source"]), None)
                if not body:
                    body = (o["body"], o["source"], [])
                    parts[o["kind"]].append(body)
                body[2].append({k: o[k] for k in ("name", "role", "group") if k in o})
        read_at = old["parts_read"]
    found = offices.offices_of(speaker=speaker, vice=vice, chairs=chairs, committees=parts["committee"],
                               delegations=parts["delegation"], sources=sources)
    if not found and old["offices"]:
        print(f"offices: none read, {len(old['offices'])} kept; the file stays")
        return 1
    found = offices.keep_since(old["offices"], found, today)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(offices.dumps(now.isoformat(), found, read_at), encoding="utf-8")
    by = {}
    for o in found:
        by[o["kind"]] = by.get(o["kind"], 0) + 1
    print(f"offices: convocation {conv}: " + ", ".join(f"{k} {n}" for k, n in by.items())
          + ("" if again else " (committees and delegations as last read)"))
    return 0


def mp_years_cmd(args) -> int:
    """The year of birth of every MP from the Assembly's archive of convocations → data/mp_years.json, and the check:
    a name whose year differs between convocations is two people (split by hand in data/mp_splits.json)."""
    import time
    from zailiprotiv import mp_years, mps
    mps.load_aliases(ROOT / "mp_aliases.json")
    pages, todo, listed = {}, [mp_years.START], {}
    while todo:  # the start page links the archive's other pages
        url = todo.pop()
        if url in pages:
            continue
        rows, links = mp_years.parse(skupstina.fetch(url).decode("utf-8", "replace"))
        pages[url] = rows
        todo += [u for u in links if u not in pages and mp_years.convocation(u)]
        time.sleep(DELAY)
    for url, rows in pages.items():
        conv = mp_years.convocation(url)
        if conv and rows:
            listed[conv] = rows
            print(f"convocation {conv}: {len(rows)} MPs listed ({url})")
    if not listed:
        print("no archive page read")
        return 1
    seated = {}
    for conv in listed:
        keys = set()
        for f in sorted((ROOT / conv / "votes").glob("*.json")):
            for v in json.loads(f.read_text(encoding="utf-8"))["votes"].values():
                keys |= {mps.key(mps.split(r[1], conv)) for r in v["rows"]}
        seated[conv] = keys
    found = mp_years.check(listed, seated)
    (ROOT / "mp_years.json").write_text(jsonfile.dumps({"check": found, "listed": listed}, "listed"), encoding="utf-8")
    print(f"\nthe same name, another year of birth ({len(found['differ'])}):")
    for d in found["differ"]:
        print(f"  {d['key']}: " + ", ".join(f"{c}: {'/'.join(map(str, y))}" for c, y in d["years"].items()))
    print(f"\none name twice in one convocation ({len(found['twice'])}):")
    for t in found["twice"]:
        print(f"  {t['convocation']}: " + "; ".join(f"{r['name']} {r['party']} {r['place']} {r['year']}" for r in t["rows"]))
    print("\non the roll calls, not in the archive's list (left mid-term, or spelled otherwise):")
    for conv, keys in sorted(found["missing"].items(), key=lambda c: int(c[0])):
        print(f"  {conv}: {len(keys)}: " + ", ".join(keys[:40]) + (" …" if len(keys) > 40 else ""))
    return 0


def poslovnik_cmd(args) -> int:
    """The Rules of Procedure from the Assembly's consolidated text into data/poslovnik/ (poslovnik.py): a new version
    only when the articles' text changed. Asked at most once a day (index.json's "provereno")."""
    from zailiprotiv import poslovnik
    folder = ROOT / "poslovnik"
    today = dt.date.today().isoformat()
    index_path = folder / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {}
    if index.get("provereno") == today and not args.again:
        print("poslovnik: checked today already")
        return 0
    doc = poslovnik.parse(skupstina.fetch(poslovnik.PAGE).decode("utf-8", "replace"))
    if len(doc["clanovi"]) < 250:  # a page that came out short: keep what is there
        print(f"::warning::poslovnik: only {len(doc['clanovi'])} articles read; nothing kept")
        return 0
    written = poslovnik.store(folder, doc, today)
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["provereno"] = today
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"poslovnik: {len(doc['clanovi'])} articles, {len(doc['glave'])} chapters; " + (f"new version {written}" if written else "unchanged"))
    return 0


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
    listed = len(found)
    found = [law for law in found if skupstina.within(law.passed or "", CONVOCATIONS[CONVOCATION])]  # the page may hold two
    store = {"fetched": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(), "source": source,
             "convocation": CONVOCATION,
             "laws": {law.pdf: law.as_dict() for law in found}}
    if _shrunk(Path(args.out), "laws", len(found)):
        return 0
    if Path(args.out).exists():
        laws.carry(json.loads(Path(args.out).read_text(encoding="utf-8")).get("laws") or {}, store["laws"])
    Path(args.out).write_text(jsonfile.dumps(store, "laws"), encoding="utf-8")
    print(f"laws: {len(found)} (of {listed} on the page), international treaties: {sum(l.treaty for l in found)}, "
          f"without a bill: {sum(not l.bill_pdf for l in found)}")
    # A page that lists nothing is broken; a new convocation that has passed nothing yet is not.
    return 0 if found or listed else 1


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
            # read again by a newer reader: a bill with no section found, or with nothing but its basis
            stale = set(old.get("sections") or {}) <= {"basis"} and old.get("reader", 1) < bills.READER
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
            # closed before pdftotext opens it (Windows won't share an open file), removed when the block ends
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete_on_close=False) as f:
                f.write(body)
                f.close()
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


def static_patch(args) -> int:
    """static/ into a site built before: the pages workflow's fast path when a push changes nothing else."""
    from zailiprotiv import site
    got = site.patch_static(Path(args.site))
    print(f"static: version {got['was']} -> {got['version']}, {got['pages']} pages")
    bad = site.check(Path(args.site))
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
        if "\n## " not in text:  # a memorandum whose only section found is the constitutional basis: nothing to summarise
            skipped += 1
            continue
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
    """The material of laws still without a summary, one text file each, for summaries written by hand."""
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
    """Summaries written by hand (a JSON Lines file: {"bill_file", "summary"}), checked and saved like the
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
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete_on_close=False) as f:  # closed first, as above
                f.write(body)
                f.close()
                found = rollcall.read(f.name)
            for key in [k for k in store["votes"] if k.split("#")[0] == pdf]:
                del store["votes"][key]
            # A sitting listed without a day can be another convocation's (the Eleventh's first, on the Tenth's
            # page, 17 Nov 2026): a roll call outside the convocation's dates is not its own.
            if any(not skupstina.within(v.when or "", CONVOCATIONS[CONVOCATION]) for v in found):
                print(f"  another convocation's (by its day): {urllib.parse.unquote(pdf)}")
                found = [v for v in found if skupstina.within(v.when or "", CONVOCATIONS[CONVOCATION])]
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
        if changed and (store["votes"] or path.exists()):
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
    if args.all:  # every sitting of the convocation the index knows, not only those of the contested laws
        sittings = sorted(json.loads(Path(args.index).read_text(encoding="utf-8"))["sittings"])
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    until = time.time() + args.minutes * 60 if args.minutes else None
    read = failed = 0
    for url in sittings:
        path = out / f"{sitting_id(url)}.json"
        if path.exists() and not args.again:
            continue
        if until and time.time() > until:  # the rest next run: what was read is kept
            print(f"time is up; {sum(1 for u in sittings if not (out / (sitting_id(u) + '.json')).exists())} sittings left for the next run")
            break
        try:
            page = skupstina.fetch(url).decode("utf-8", "replace")
            listed = transcripts.days(page, url)
            if not listed:
                print(f"{url}: no stenographic notes linked")
                if args.all:  # written down as read and empty, so the next run does not ask again
                    path.write_text(jsonfile.dumps({"sitting": url, "days": [], "agenda": {}, "amendments": [],
                                                    "speeches": {}}, "speeches"), encoding="utf-8")
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
        except Exception as e:  # one sitting that cannot be fetched or read does not stop the others
            if not args.all:
                raise
            failed += 1
            print(f"{url}: not read ({type(e).__name__}: {e})")
            continue
        record = {"sitting": url, "days": meta, "agenda": {str(k): v for k, v in found["agenda"].items()},
                  "amendments": found["amendments"],
                  "speeches": {f"{i:05d}": s for i, s in enumerate(found["speeches"])}}
        path.write_text(jsonfile.dumps(record, "speeches"), encoding="utf-8")
        read += 1
        print(f"{path}: {len(meta)} days, {len(found['speeches'])} speeches, {len(found['amendments'])} amendments", flush=True)
        time.sleep(DELAY)
    if args.all:
        print(f"transcripts: {read} sittings read, {failed} not read")
    return 0


def notes_raw_cmd(args) -> int:
    """The notes as read (data/<N>/transcripts/*.json), kept whole in the notes' bucket under sirovo/: the repository
    holds those of the contested laws only, the bucket all of them. --push sends what the bucket lacks or holds in
    another form; --pull brings what this folder lacks."""
    from zailiprotiv import files_site
    store = ROOT / "settings.json"
    if args.pull and not args.force and not (json.loads(store.read_text(encoding="utf-8")) if store.exists() else {}).get("notes_all"):
        # Until data/settings.json says "notes_all": true, the site and the notes' pages are built from the notes in
        # the repository alone (the bucket is being filled; the builds are tried with all of it first).
        print("notes: every sitting's notes are not asked for yet (notes_all in data/settings.json)")
        return 0
    missing = [v for v in ("R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "CLOUDFLARE_ACCOUNT_ID") if not os.environ.get(v)]
    if missing:
        print("notes: the bucket's keys are missing (" + ", ".join(missing) + "); only the notes in the repository are used")
        return 1 if args.push else 0
    try:
        n = (files_site.raw_push if args.push else files_site.raw_pull)(ROOT, args.bucket)
    except Exception as e:
        print(f"notes: the bucket {args.bucket} does not answer: {e}")
        return 1 if args.push else 0
    print(f"notes: {n} sittings' notes {'sent to' if args.push else 'brought from'} the bucket")
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
    summaries of the debate written by hand."""
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
    """Overviews written by hand (DIR/out/<name>.json beside the exported DIR/<name>.json), checked and saved to
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
    """Debate summaries written by hand (JSON Lines: {"bill_file", "debate"}): quotes checked against the notes
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
    model = (state.pending(kind) or {}).get("model") or summaries.MODEL
    replace = set(filter(None, os.environ.get("ZAILIPROTIV_REPLACE", "").split(",")))  # see debates_batch
    for key, own in sorted(profiles.speeches(ROOT).items()):
        long = [s for s in own if len(s["text"].split()) >= profiles.LONG]
        name = key.replace(" ", "-") + ".json"
        there = ROOT / "profiles" / name
        again = args.again or (replace and there.exists() and json.loads(there.read_text(encoding="utf-8")).get("model") in replace)
        if len(long) < args.min or (there.exists() and not again) or state.gave_up(kind, name):
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
    requests = {n: {"model": model, "max_tokens": batch.ROOM, "system": batch.cached(system),
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
            result = None if bad else profiles.record(reply, material, model)
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
    model = (pending or {}).get("model") or summaries.MODEL
    # ZAILIPROTIV_REPLACE names a model whose texts are to be written again by the model of this run (a run by hand,
    # to move from a weaker model to a stronger one); the old text stays until the new one passes the checks.
    replace = set(filter(None, os.environ.get("ZAILIPROTIV_REPLACE", "").split(",")))
    for i, (law, bill, n, final, item) in enumerate(found):
        name = law["bill_file"]
        text = debates.material(law, bill, n, final, seated, item, df)
        saved = json.loads((out / name).read_text(encoding="utf-8")) if (out / name).exists() else {}
        done = saved.get("fingerprint") == debates.fingerprint(text) and saved.get("model") not in replace
        if only:
            if name in only and not done:
                chosen[name] = (law, n, final, text)
        elif name in wanted or (i < args.top and not done and not state.gave_up(kind, name)):
            chosen[name] = (law, n, final, text)
    requests = {name: {"model": model, "max_tokens": batch.ROOM, "system": batch.cached(debates.SYSTEM),
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
        (out / name).write_text(json.dumps(debates.record(law, text, debate, model, dropped),
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
                             ("import", import_summaries, "save summaries written by hand (JSON Lines)")):
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
    p.add_argument("--all", action="store_true", help="every sitting of the convocation (data/<N>/index.json)")
    p.add_argument("--index", default=str(DATA / "index.json"))
    p.add_argument("--minutes", type=float, default=0, help="stop asking for new sittings after this long")
    p.set_defaults(run=notes_of_debate)
    p = commands.add_parser("notes-raw", help="the notes as read, to or from the bucket (sirovo/)")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--push", action="store_true")
    g.add_argument("--pull", action="store_true")
    p.add_argument("--force", action="store_true", help="--pull even before notes_all is set")
    p.add_argument("--bucket", default="zailiprotiv-beleske")
    p.set_defaults(run=notes_raw_cmd)
    p = commands.add_parser("debates-export", help="debate material of the most contested laws, for a session")
    p.add_argument("--to", required=True)
    p.add_argument("--top", type=int, default=20)
    p.set_defaults(run=debates_export)
    p = commands.add_parser("profiles-export", help="MPs' speeches from the notes read, for overviews written by hand")
    p.add_argument("--to", required=True)
    p.add_argument("--min", type=int, default=10, help="speeches of some length an MP needs")
    p.add_argument("--again", action="store_true")
    p.set_defaults(run=profiles_export)
    p = commands.add_parser("profiles-import", help="save overviews of MPs' speeches written by hand")
    p.add_argument("dir")
    p.add_argument("--model", default="")
    p.add_argument("--check", default="", help="check one reply only")
    p.set_defaults(run=profiles_import)
    p = commands.add_parser("debates-import", help="save debate summaries written by hand")
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
    p = commands.add_parser("files-split", help="move downloads and share pictures out of a built site, for the bucket")
    p.add_argument("--site", default="_site")
    p.add_argument("--out", default="_podaci")
    p.add_argument("--url", default="", help="the bucket's public address (default: files_url of data/settings.json)")
    p.add_argument("--domain", default="zailiprotiv.rs")
    p.set_defaults(run=files_split_cmd)
    p = commands.add_parser("files-upload", help="make the R2 bucket hold exactly the folder files-split made")
    p.add_argument("--dir", default="_podaci")
    p.add_argument("--bucket", default="zailiprotiv-podaci")
    p.add_argument("--url", default="https://podaci.zailiprotiv.rs/", help="the bucket's public address, for purging the cache")
    p.add_argument("--dry", action="store_true", help="say what would be sent, send nothing")
    p.set_defaults(run=files_upload_cmd)
    p = commands.add_parser("files-purge", help="make Cloudflare's cache forget these files of a bucket's address")
    p.add_argument("names", nargs="+")
    p.add_argument("--url", default="https://podaci.zailiprotiv.rs/")
    p.set_defaults(run=files_purge_cmd)
    p = commands.add_parser("notes-cors", help="let the site read the notes' search index from the bucket")
    p.add_argument("--bucket", default="zailiprotiv-beleske")
    p.set_defaults(run=notes_cors_cmd)
    p = commands.add_parser("notes-check", help="do the notes' pages answer at their public address?")
    p.add_argument("--url", default="https://beleske.zailiprotiv.rs/")
    p.set_defaults(run=notes_check_cmd)
    p = commands.add_parser("videos", help="the plenary recordings by day, from the broadcaster's archive → videos.json")
    p.set_defaults(run=videos_cmd)
    p = commands.add_parser("uzivo-pull", help="the live page's records of who spoke when → data/<N>/uzivo/")
    p.set_defaults(run=uzivo_pull)
    p = commands.add_parser("arhiva", help="the archive's recordings lined up with the live records → data/<N>/snimak/")
    p.set_defaults(run=arhiva_cmd)
    p = commands.add_parser("govor", help="who spoke when, from the notes lined up with the recording's words → data/<N>/snimak/")
    p.add_argument("day", help="the sitting day, YYYY-MM-DD")
    p.add_argument("heard", help="the folder of the day's words (live/uzivo/zvuk_dana.py)")
    p.add_argument("--note", default="", help="added to the day's note (how each file's start was found, when by hand)")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(run=govor_cmd)
    p = commands.add_parser("glas-dan", help="a day with no notes yet, from captions and voices → data/<N>/snimak/")
    p.add_argument("day")
    p.add_argument("stretches", help="the stretches named by voice (ko.py, in the analysis image)")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(run=glas_dan_cmd)
    p = commands.add_parser("prepis", help="an automatic transcript of a day's speeches (Whisper) → data/<N>/prepis/")
    p.add_argument("day", help="YYYY-MM-DD, a day in data/<N>/snimak/")
    p.add_argument("--model", default="large-v3-turbo")
    p.add_argument("--minutes", type=float, default=300, help="stop after this long; the next run goes on")
    p.set_defaults(run=prepis_cmd)
    p = commands.add_parser("poslovnik", help="the Rules of Procedure, every version kept → data/poslovnik/")
    p.add_argument("--again", action="store_true", help="read it even if checked today")
    p.set_defaults(run=poslovnik_cmd)
    p = commands.add_parser("photos", help="MPs' portraits from the Assembly's list → data/photos/")
    p.set_defaults(run=photos_cmd)
    p = commands.add_parser("members", help="the sitting MPs from the Assembly's list → data/<N>/members.json")
    p.set_defaults(run=members_cmd)
    p = commands.add_parser("offices", help="offices in the Assembly (Speaker, deputies, committees, delegations) "
                                            "→ data/<N>/offices.json, and its news → data/vesti.json")
    p.set_defaults(run=offices_cmd)
    p = commands.add_parser("mp-years", help="MPs' years of birth from the Assembly's archive, and names that are two people")
    p.set_defaults(run=mp_years_cmd)
    p = commands.add_parser("status", help="what the data still lacks, per convocation")
    p.add_argument("--min", type=int, default=10)
    p.set_defaults(run=status)
    p = commands.add_parser("site", help="build the static site")
    p.add_argument("--out", default="_site")
    p.add_argument("--domain", default="zailiprotiv.rs")
    p.add_argument("--latin-only", action="store_true", help="skip the Cyrillic edition (cir/), for a quicker build")
    p.add_argument("--html-links", action="store_true", help="keep .html in links, to open the pages from disk")
    p.set_defaults(run=website)
    p = commands.add_parser("static-patch", help="put static/ into a site built before (styles and scripts only)")
    p.add_argument("--site", default="_site")
    p.set_defaults(run=static_patch)
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
