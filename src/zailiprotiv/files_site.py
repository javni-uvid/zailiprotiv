"""The site's downloads and share pictures, kept apart from its pages: every law's roll call (CSV, JSON), the
whole-convocation tables and the picture drawn for each law and MP are two files in three of what the site is made
of, and none of them is a page. They live in a Cloudflare R2 bucket behind podaci.zailiprotiv.rs (the maintainer,
14 Nov 2026), which keeps the site itself well under its host's limits on files and size.

`split` moves them out of a built site and points the pages at their new address; `sync` makes the bucket hold
exactly that folder, by the bucket's own list (name and MD5), so nothing has to be remembered between runs.
"""
from __future__ import annotations

import hashlib
import mimetypes
import os
import posixpath
import re
import shutil
from pathlib import Path

_ATTR = re.compile(r'((?:href|content)=")([^"]+)(")')


def apart(rel: str) -> bool:
    """Is this file of the built site (path from its root) one that lives in the bucket?"""
    folder, _, name = rel.rpartition("/")
    if folder == "podaci":
        return True
    if folder == "zakon":
        return name.endswith((".csv", ".json", ".png"))
    return folder == "poslanik" and name.endswith(".png")


def split(site: Path, out: Path, url: str, domain: str = "") -> dict[str, int]:
    """Move the files that are `apart` from `site` to `out` (same paths), and in every page turn the links to them
    and the share pictures' addresses into addresses under `url`."""
    url = url.rstrip("/") + "/"
    moved = set()
    for f in sorted(site.rglob("*")):
        rel = f.relative_to(site).as_posix()
        if f.is_file() and apart(rel):
            (out / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(f), out / rel)
            moved.add(rel)
    own = [f"https://{domain}/"] if domain else []
    pages = 0
    for f in site.rglob("*.html"):
        here = f.parent.relative_to(site).as_posix()

        def link(m, here=here):
            value = m.group(2)
            target = next((value[len(o):] for o in own if value.startswith(o)), None)
            if target is None:
                if ":" in value or value.startswith(("/", "#")):
                    return m.group(0)
                target = posixpath.normpath(posixpath.join(here, value.split("#")[0].split("?")[0]))
            return m.group(1) + url + target + m.group(3) if target in moved else m.group(0)
        text = f.read_text(encoding="utf-8")
        new = _ATTR.sub(link, text)
        if new != text:
            f.write_text(new, encoding="utf-8")
            pages += 1
    return {"moved": len(moved), "pages": pages}


def kind(name: str) -> str:
    k = mimetypes.guess_type(name)[0] or "application/octet-stream"
    return k + "; charset=utf-8" if k.startswith("text/") or k in ("image/svg+xml", "application/json") else k


def client(workers: int = 16):
    import boto3
    from botocore.config import Config
    return boto3.client("s3", endpoint_url=f"https://{os.environ['CLOUDFLARE_ACCOUNT_ID']}.r2.cloudflarestorage.com",
                        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
                        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"], region_name="auto",
                        config=Config(connect_timeout=10, read_timeout=120, max_pool_connections=workers,
                                      retries={"max_attempts": 4, "mode": "standard"}))


def plan(local: dict[str, str], there: dict[str, str]) -> tuple[list[str], list[str]]:
    """What to send and what to remove, given {name: md5} of the folder and of the bucket."""
    return sorted(k for k, v in local.items() if there.get(k) != v), sorted(k for k in there if k not in local)


def purge(url: str, names: list[str]) -> str:
    """Tell Cloudflare's cache that these files under `url` changed, so the new ones are served at once and not when
    the cached copy runs out (a day). A new file needs no telling; this is for those that were there before.
    Needs CLOUDFLARE_API_TOKEN (Zone: Cache Purge) and CLOUDFLARE_ZONE_ID; without them nothing is done.
    Many files at once are purged as the whole host. Returns what was done, in words."""
    import json
    import urllib.parse
    import urllib.request
    token, zone = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip(), os.environ.get("CLOUDFLARE_ZONE_ID", "").strip()
    if not names:
        return "nothing to purge"
    if not (token and zone):
        lacks = " and ".join(n for n, v in (("CLOUDFLARE_API_TOKEN", token), ("CLOUDFLARE_ZONE_ID", zone)) if not v)
        return f"cache not purged ({len(names)} changed): no {lacks}"
    url = url.rstrip("/") + "/"
    host = urllib.parse.urlsplit(url).netloc
    bodies = [{"hosts": [host]}] if len(names) > 300 else \
        [{"files": [url + urllib.parse.quote(n) for n in names[i:i + 30]]} for i in range(0, len(names), 30)]
    try:
        for body in bodies:
            req = urllib.request.Request(f"https://api.cloudflare.com/client/v4/zones/{zone}/purge_cache", method="POST",
                                         data=json.dumps(body).encode(), headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                if not json.load(r).get("success"):
                    return "cache not purged: Cloudflare said no"
    except Exception as e:
        return f"cache not purged: {e}"
    return f"cache purged: {'all of ' + host if 'hosts' in bodies[0] else str(len(names)) + ' files'}"


def sync(folder: Path, bucket: str, dry: bool = False, workers: int = 16, url: str = "") -> int:
    """Make the bucket hold exactly the folder. Returns how many files failed."""
    from boto3.s3.transfer import TransferConfig
    from concurrent.futures import ThreadPoolExecutor, as_completed
    s3 = client(workers)
    there = {}
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket):
        for o in page.get("Contents", []):
            there[o["Key"]] = o["ETag"].strip('"')
    local = {f.relative_to(folder).as_posix(): hashlib.md5(f.read_bytes()).hexdigest()
             for f in sorted(folder.rglob("*")) if f.is_file()}
    send, gone = plan(local, there)
    print(f"files: {len(local)} here, {len(there)} in the bucket, {len(send)} to send, {len(gone)} to remove", flush=True)
    if dry:
        return 0
    if there and len(gone) > max(50, len(there) // 5):  # a build gone wrong must not empty the bucket
        print(f"files: {len(gone)} to remove is too many to be right; nothing removed")
        gone = []
    whole = TransferConfig(multipart_threshold=1 << 30)  # in one piece, so the bucket's ETag is the file's MD5
    failed = 0

    def put(name):
        s3.upload_file(str(folder / name), bucket, name, Config=whole,
                       ExtraArgs={"ContentType": kind(name), "CacheControl": "public, max-age=3600"})
    with ThreadPoolExecutor(workers) as pool:
        jobs = {pool.submit(put, name): name for name in send}
        for i, job in enumerate(as_completed(jobs), 1):
            if job.exception():
                failed += 1
                print(f"  not sent {jobs[job]}: {job.exception()}")
            if i % 1000 == 0:
                print(f"  {i}/{len(send)}", flush=True)
    for i in range(0, len(gone) if not failed else 0, 1000):
        s3.delete_objects(Bucket=bucket, Delete={"Objects": [{"Key": k} for k in gone[i:i + 1000]], "Quiet": True})
    print(f"files: sent {len(send) - failed}, removed {len(gone) if not failed else 0}, failed {failed}")
    if url:
        print("files: " + purge(url, [n for n in send if n in there] + (gone if not failed else [])))
    return failed
