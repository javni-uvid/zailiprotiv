"""The notification when a sitting's broadcast begins (20 Nov 2026, the maintainer's decision): once the service has
read a few frames of a live broadcast in a row, in the day's working hours, it asks the site's counter (worker/) to
send it to every device that asked for it on the page, at most once a day. The counter sends it a batch at a time
(its free plan's limit on requests out), so this asks again with where the next batch starts until none is left.
Only the standard library: the tests run it."""
from __future__ import annotations

import json
import logging
import threading
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from . import config

log = logging.getLogger("obavesti")
FRAMES = 3  # frames of a live broadcast in a row (about 15 s) before it counts as begun
HOURS = (7, 22)  # local hours in which a beginning is told; a broadcast outside them wakes nobody
BATCHES = 200  # at most this many batches (of 30) in one day's sending


class Bell:
    def __init__(self, path: str | None = None, *, token: str | None = None, api: str | None = None, post=None):
        self.path = Path(path or config.PUSH_PATH)
        self.token = config.PUSH_TOKEN if token is None else token
        self.api = (config.VOTES_API if api is None else api).rstrip("/")
        self.post = post or self._post
        self.frames = 0

    def restart(self) -> None:
        """A new run of frames (the broadcast found again): count from nought."""
        self.frames = 0

    def frame(self, now: datetime | None = None, *, wait: bool = False) -> bool:
        """One more frame of a live broadcast. True when this one makes the day's notification go out."""
        if not (self.token and self.api.startswith("https://")):
            return False
        self.frames += 1
        if self.frames != FRAMES:
            return False
        now = now or datetime.now(ZoneInfo(config.TZ))
        if not HOURS[0] <= now.hour < HOURS[1]:
            return False
        day = now.date().isoformat()
        if self._last() == day:
            return False
        self._keep(day)
        t = threading.Thread(target=self.send, daemon=True)
        t.start()
        if wait:
            t.join()
        return True

    def send(self) -> None:
        sent = gone = 0
        od = 0
        try:
            for _ in range(BATCHES):
                r = self.post(od)
                if r.get("already"):
                    log.info("notification: already sent today")
                    return
                sent, gone = sent + int(r.get("sent", 0)), gone + int(r.get("gone", 0))
                if not r.get("next"):
                    break
                od = int(r["next"])
            log.info("notification sent: %d devices, %d no longer there", sent, gone)
        except Exception as exc:  # the counter unreachable: no second try today, the day is kept
            log.warning("notification not sent (%s)", exc)

    def _post(self, od: int) -> dict:
        req = urllib.request.Request(self.api + "/p/salji", data=json.dumps({"od": od}).encode(), method="POST",
                                     headers={"authorization": "Bearer " + self.token, "content-type": "application/json",
                                              "user-agent": "zailiprotiv-mikrofon"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))

    def _last(self) -> str:
        try:
            return str(json.loads(self.path.read_text(encoding="utf-8")).get("dan", ""))
        except (OSError, ValueError, AttributeError):
            return ""

    def _keep(self, day: str) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps({"dan": day}), encoding="utf-8")
        except OSError:
            log.warning("the day of the notification not kept")
