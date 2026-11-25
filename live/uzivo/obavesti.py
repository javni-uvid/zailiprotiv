"""The notification when a sitting's broadcast begins (20 Nov 2026, the maintainer's decision): once the service has
read a few frames of a live broadcast in a row, in the day's working hours, it asks the site's counter (worker/) to
send it to every device that asked for it on the page, at most once a day. The counter sends it a batch at a time
(its free plan's limit on requests out), so this asks again with where the next batch starts until none is left.
And one when the sitting goes on after a long break (24 Nov 2026, the maintainer's decision), as many as there are breaks:
`resumed` finds it, from what was heard, as soon as they speak again.
Only the standard library: the tests run it."""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from . import config, mreza
from .state_base import _write, counted

log = logging.getLogger("obavesti")
FRAMES = 3  # frames of a live broadcast in a row (about 15 s) before it counts as begun
HOURS = (7, 22)  # local hours in which a beginning is told; a broadcast outside them wakes nobody
BATCHES = 200  # at most this many batches (of 30) in one day's sending
PAUSE = 1200  # seconds nobody is heard: a long break; the five or ten minutes' breaks wake nobody
WORDS = 8  # words in a piece of the transcript for it to be speech (a break's odd sound gave three, 24 Nov 2026)
SURE = 90  # seconds from the first speech after a break in which a second must come
FRESH = 900  # a sitting that went on longer ago than this is no news (the service was down)
RESUMED_MOST = 50  # in a day: no limit of ours (the maintainer), a stop against a fault
LOOK = 15  # seconds between looks


def resumed(said: dict[str, str], turns: list[dict], events: list[dict], now: float) -> int:
    """When the break that has just ended began to be silent, or 0: the chair said a break ("Pauza") about where the
    silence begins, nobody was heard for PAUSE after it, and now somebody is: an MP read at the rostrum, or two pieces
    of the transcript with speech in them, the chair's or anybody's. Not the chair's words "nastavljamo sa radom": on
    19 Nov 2026 they were said twice with no break before them, and the first words after one are not always those.
    A silence with no break said is none: the transcript was off."""
    pieces = sorted(int(k.lstrip("p")) for k, v in said.items() if k.lstrip("p").isdigit() and len(v.split()) >= WORDS)
    # a caption read for sure: the picture's noise was once read as an MP's name in the silent hall (24 Nov 2026, 11:10)
    on = [(float(t["start"]), float(t["seen"])) for t in turns if counted(t)]
    heard = sorted([(float(t), t + 20.0) for t in pieces] + on)
    if not heard:
        return 0
    end, gap = heard[0][1], None
    for a, b in heard[1:]:
        if a - end >= PAUSE:
            gap = (end, a)
        end = max(end, b)
    if not gap or not 0 <= now - gap[1] <= FRESH:
        return 0
    if not any(gap[1] <= a for a, _ in on) and sum(gap[1] <= t <= gap[1] + SURE for t in pieces) < 2:
        return 0
    if not any(e.get("vrsta") == "Pauza" and gap[0] - 300 <= e.get("t", 0) <= gap[1] for e in events):
        return 0
    return int(gap[0])


def to_tell(whole, now: float, tz) -> bool:
    """Whether a day's summary (`whole`, as kept) is to be told of now, by a notification and by the mail to the
    maintainer: it is on the page, in the hours that may wake someone (a day ended at midnight is told in the
    morning), and not news no more (half a day old)."""
    return bool(config.SHOW_SUMMARY and isinstance(whole, dict) and whole.get("ukratko")
                and HOURS[0] <= datetime.fromtimestamp(now, tz).hour < HOURS[1] and now - whole.get("t", now) <= 12 * 3600)


class Bell:
    def __init__(self, path: str | None = None, *, token: str | None = None, api: str | None = None, post=None):
        self.path = Path(path or config.PUSH_PATH)
        self.token = config.PUSH_TOKEN if token is None else token
        self.api = (config.VOTES_API if api is None else api).rstrip("/")
        self.post = post or self._post
        self.frames = 0
        self.looked = 0.0

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

    def heard(self, tracker, now: datetime | None = None, *, wait: bool = False) -> bool:
        """While the broadcast is read: whether the sitting has gone on after a long break; True when that makes its
        notification go out. A break is told once (kept by when its silence began, so a restart doesn't repeat it)."""
        if not (self.token and self.api.startswith("https://")):
            return False
        now = now or datetime.now(ZoneInfo(config.TZ))
        if now.timestamp() - self.looked < LOOK or not HOURS[0] <= now.hour < HOURS[1]:
            return False
        self.looked = now.timestamp()
        since = resumed(*tracker.day_heard(), now.timestamp())
        if not since:
            return False
        day, kept = now.date().isoformat(), self._kept().get("nastavak")
        kept = kept if isinstance(kept, dict) and kept.get("dan") == day else {"dan": day, "pauze": []}
        told = [int(x) for x in kept.get("pauze") or []]
        if len(told) >= RESUMED_MOST or any(abs(x - since) < PAUSE for x in told):
            return False
        self._keep({"dan": day, "pauze": told + [since]}, "nastavak")
        t = threading.Thread(target=self.send, args=("nastavak", len(told) + 1), daemon=True)
        t.start()
        if wait:
            t.join()
        return True

    def summary(self, day: str, *, wait: bool = False) -> bool:
        """The day's summary is out (sudija.py): every device that asked for the notifications is told, once a day,
        by the same counter; the counter keeps the day apart from the sitting's ("s:<day>")."""
        if not (self.token and self.api.startswith("https://")) or self._last("sazetak") == day:
            return False
        self._keep(day, "sazetak")
        t = threading.Thread(target=self.send, args=("sazetak",), daemon=True)
        t.start()
        if wait:
            t.join()
        return True

    def send(self, what: str = "sednica", nth: int = 0) -> None:
        sent = gone = 0
        od = 0
        try:
            for _ in range(BATCHES):
                r = self.post(od) if what == "sednica" else self.post(od, what, nth) if nth else self.post(od, what)
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

    def _post(self, od: int, what: str = "sednica", nth: int = 0) -> dict:
        return mreza.counter(self.api + "/p/salji", self.token, {"od": od, "vrsta": what, **({"broj": nth} if nth else {})})

    def admin(self, endpoint: str, on: bool = True) -> bool:
        """The maintainer's device told (or no longer told) when this service is down while a sitting is on: the
        counter keeps it (/p/admin), asked with the token, which the page never sees."""
        if not (self.token and self.api.startswith("https://")):
            return False
        try:
            mreza.counter(self.api + ("/p/admin" if on else "/p/admin/odjava"), self.token, {"endpoint": endpoint}, timeout=15)
            return True
        except Exception as exc:
            log.warning("admin device not kept (%s)", exc)
            return False

    def _kept(self) -> dict:
        try:
            got = json.loads(self.path.read_text(encoding="utf-8"))
            return got if isinstance(got, dict) else {}
        except (OSError, ValueError):
            return {}

    def _last(self, what: str = "dan") -> str:
        return str(self._kept().get(what, ""))

    def _keep(self, day: str | dict, what: str = "dan") -> None:
        try:
            _write(self.path, {**self._kept(), what: day})
        except OSError:
            log.warning("the day of the notification not kept")
