"""Putting the live sound's files in Cloudflare R2 (22 Nov 2026, the maintainer's choice: Cloudflare's terms want
audio served from its storage, not through the tunnel, and the computer then sends each piece once however many
listen). An S3 PUT signed by hand (AWS Signature Version 4): no new library in the image.

From live/.env: ZVUK_R2_ENDPOINT (https://<account>.r2.cloudflarestorage.com), ZVUK_R2_BUCKET, ZVUK_R2_KLJUC (the
access key's id), ZVUK_R2_TAJNA (its secret), ZVUK_URL (the bucket's public address, https://zvuk.zailiprotiv.rs/).
Uploads run in one thread of their own, in order (a segment before the playlist that names it), never in the
reader's way: a queue that is full drops the oldest work rather than wait."""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import logging
import os
import queue
import threading
import urllib.parse
import urllib.request

log = logging.getLogger("r2")

ENDPOINT = os.environ.get("ZVUK_R2_ENDPOINT", "").strip().rstrip("/")
BUCKET = os.environ.get("ZVUK_R2_BUCKET", "").strip()
KEY_ID = os.environ.get("ZVUK_R2_KLJUC", "").strip()
SECRET = os.environ.get("ZVUK_R2_TAJNA", "").strip()
PUBLIC = os.environ.get("ZVUK_URL", "").strip().rstrip("/") + "/" if os.environ.get("ZVUK_URL", "").strip() else ""
REGION = os.environ.get("ZVUK_R2_REGION", "auto").strip()


def on() -> bool:
    return bool(ENDPOINT.startswith(("https://", "http://")) and BUCKET and KEY_ID and SECRET and PUBLIC)


def _sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def request(key: str, data: bytes, content_type: str, cache: str, *, now: dt.datetime | None = None,
            endpoint: str = "", bucket: str = "", key_id: str = "", secret: str = "", region: str = "") -> urllib.request.Request:
    """The signed PUT of one object (path-style: <endpoint>/<bucket>/<key>)."""
    endpoint, bucket = endpoint or ENDPOINT, bucket or BUCKET
    key_id, secret, region = key_id or KEY_ID, secret or SECRET, region or REGION
    now = now or dt.datetime.now(dt.timezone.utc)
    stamp, day = now.strftime("%Y%m%dT%H%M%SZ"), now.strftime("%Y%m%d")
    host = urllib.parse.urlsplit(endpoint).netloc
    path = "/" + urllib.parse.quote(bucket) + "/" + urllib.parse.quote(key, safe="/~")
    body_hash = hashlib.sha256(data).hexdigest()
    signed = "cache-control;content-type;host;x-amz-content-sha256;x-amz-date"
    canonical = "\n".join(["PUT", path, "", f"cache-control:{cache}", f"content-type:{content_type}", f"host:{host}",
                           f"x-amz-content-sha256:{body_hash}", f"x-amz-date:{stamp}", "", signed, body_hash])
    scope = f"{day}/{region}/s3/aws4_request"
    to_sign = "\n".join(["AWS4-HMAC-SHA256", stamp, scope, hashlib.sha256(canonical.encode()).hexdigest()])
    k = _sign(_sign(_sign(_sign(("AWS4" + secret).encode(), day), region), "s3"), "aws4_request")
    signature = hmac.new(k, to_sign.encode(), hashlib.sha256).hexdigest()
    headers = {"Cache-Control": cache, "Content-Type": content_type, "x-amz-content-sha256": body_hash,
               "x-amz-date": stamp,
               "Authorization": f"AWS4-HMAC-SHA256 Credential={key_id}/{scope}, SignedHeaders={signed}, Signature={signature}"}
    return urllib.request.Request(endpoint + path, data=data, headers=headers, method="PUT")


def put(key: str, data: bytes, content_type: str, cache: str, **conf) -> bool:
    try:
        with urllib.request.urlopen(request(key, data, content_type, cache, **conf), timeout=10) as r:
            return 200 <= r.status < 300
    except Exception as exc:
        log.info("R2: %s not sent: %s", key, exc)
        return False


class Uploader(threading.Thread):
    """One thread, in order. The newest playlist matters most: a full queue drops its oldest job."""

    def __init__(self) -> None:
        super().__init__(daemon=True, name="r2")
        self.jobs: queue.Queue = queue.Queue(maxsize=40)
        self.sent = 0

    def add(self, key: str, data: bytes, content_type: str, cache: str) -> None:
        while True:
            try:
                self.jobs.put_nowait((key, data, content_type, cache))
                return
            except queue.Full:
                try:
                    self.jobs.get_nowait()
                except queue.Empty:
                    pass

    def run(self) -> None:
        while True:
            key, data, content_type, cache = self.jobs.get()
            if put(key, data, content_type, cache):
                self.sent += 1


_uploader: Uploader | None = None


def send(key: str, data: bytes, content_type: str, cache: str) -> None:
    """Queues one object for the bucket (started on first use)."""
    global _uploader
    if not on():
        return
    if _uploader is None:
        _uploader = Uploader()
        _uploader.start()
    _uploader.add(key, data, content_type, cache)
