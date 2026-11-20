"""The pages and files kept in buckets: the notes' pages, the downloads, the raw notes."""

from __future__ import annotations

import json
import os
from pathlib import Path

from zailiprotiv import jsonfile

from zailiprotiv.cli import common


def notes_site_cmd(args) -> int:
    """The stenographic notes read, as pages of their own (see notes_site), into --out."""
    from zailiprotiv import notes_site
    n = notes_site.build(common.ROOT, Path(args.out))
    print(f"notes: {n['pages']} pages (each in two scripts), {n['speeches']} speeches")
    return 0


def notes_upload_cmd(args) -> int:
    """Send the notes' pages that changed to the R2 bucket (S3 API), and remember what is there in
    data/notes_manifest.json so the next run sends only what is new. Needs R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY and
    CLOUDFLARE_ACCOUNT_ID in the environment."""
    import mimetypes
    import os
    from zailiprotiv import notes_site
    folder, store = Path(args.dir), common.ROOT / "notes_manifest.json"
    manifest = jsonfile.load(store, {})
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
    # Nothing is removed in a run that did not send everything. Removed as many at once as are sent: one at a time,
    # the search index's 600 old files took some four minutes a run.
    with ThreadPoolExecutor(workers) as pool:
        jobs = {pool.submit(s3.delete_object, Bucket=args.bucket, Key=name): name for name in (gone if not failed else [])}
        for job in as_completed(jobs):
            name = jobs[job]
            if job.exception():
                failed.append(name)
                print(f"  not removed {name}: {job.exception()}")
            else:
                manifest.pop(name, None)
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
    store = common.ROOT / "notes_manifest.json"
    names = sorted(jsonfile.load(store, []))
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
    store = common.ROOT / "settings.json"
    url = args.url or (jsonfile.load(store, {}).get("files_url", ""))
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


def notes_raw_cmd(args) -> int:
    """The notes as read (data/<N>/transcripts/*.json), kept whole in the notes' bucket under sirovo/: the repository
    holds those of the contested laws only, the bucket all of them. --push sends what the bucket lacks or holds in
    another form; --pull brings what this folder lacks."""
    from zailiprotiv import files_site
    store = common.ROOT / "settings.json"
    if args.pull and not args.force and not jsonfile.load(store, {}).get("notes_all"):
        # Until data/settings.json says "notes_all": true, the site and the notes' pages are built from the notes in
        # the repository alone (the bucket is being filled; the builds are tried with all of it first).
        print("notes: every sitting's notes are not asked for yet (notes_all in data/settings.json)")
        return 0
    missing = [v for v in ("R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "CLOUDFLARE_ACCOUNT_ID") if not os.environ.get(v)]
    if missing:
        print("notes: the bucket's keys are missing (" + ", ".join(missing) + "); only the notes in the repository are used")
        return 1 if args.push else 0
    try:
        n = (files_site.raw_push if args.push else files_site.raw_pull)(common.ROOT, args.bucket)
    except Exception as e:
        print(f"notes: the bucket {args.bucket} does not answer: {e}")
        return 1 if args.push else 0
    print(f"notes: {n} sittings' notes {'sent to' if args.push else 'brought from'} the bucket")
    return 0
