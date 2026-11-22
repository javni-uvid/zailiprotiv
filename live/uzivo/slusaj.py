"""Listening live, sound only: a trial for the maintainer (22 Nov 2026, the maintainer: "napravimo probnu verziju";
the rights are settled on their side). Behind the maintainer's key until it is opened to all.

Each segment of the broadcast the service already fetches (stream.Reader: the picture's, or the sound-only track's
when YouTube has one) gives its sound to a playlist of our own, HLS, which a phone plays by itself and keeps playing
with the screen locked: the sound copied as it is (no new encoding), the broadcast's own timestamps kept, so the
segments follow on as in the broadcast. The last WINDOW segments are kept; a gap in the numbers (a stall, a new
broadcast) is marked as a discontinuity. Nothing here raises into the reader: the frame matters more."""
from __future__ import annotations

import logging
import math
import subprocess
import threading
from pathlib import Path

from . import config

log = logging.getLogger("slusaj")
WINDOW = 12  # segments in the playlist (about a minute at YouTube's 5 s)
KEEP = 20  # segment files kept on disk: a player still fetching one just dropped from the list finds it


def on() -> bool:
    """While there is someone to listen: all (SLUSAJ_JAVNO), or the key's holder (the transcript's key)."""
    return config.LISTEN_PUBLIC or len(config.TRANSCRIPT_KEY) >= 12


def fresh(now: float) -> bool:
    """Whether the playlist has a segment from the last minute: the button is offered only then."""
    return bool(PLAYLIST.items) and now - PLAYLIST.seen < 60


class Playlist:
    def __init__(self, folder: str | Path) -> None:
        self.folder = Path(folder)
        self._lock = threading.Lock()
        self.items: list[tuple[int, float, bool]] = []  # (segment number, seconds, a discontinuity before it)
        self.seen = 0.0  # when the last segment was added (time.time())

    def add(self, segment: str, seconds: float, number: int, now: float) -> bool:
        """A fetched segment's sound into the playlist; whether it was."""
        try:
            self.folder.mkdir(parents=True, exist_ok=True)
            out = self.folder / f"z{number}.ts"
            tmp = out.with_suffix(".tmp")
            done = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-copyts",
                                   "-i", segment, "-vn", "-sn", "-dn", "-map", "0:a:0", "-c:a", "copy",
                                   "-muxdelay", "0", "-f", "mpegts", str(tmp)], capture_output=True, timeout=20)
            if done.returncode != 0 or not tmp.exists() or tmp.stat().st_size < 1000:
                tmp.unlink(missing_ok=True)
                return False
            tmp.replace(out)
        except Exception:
            log.debug("sound for listening not kept", exc_info=True)
            return False
        with self._lock:
            last = self.items[-1][0] if self.items else None
            if last is not None and number <= last - 50:  # a new broadcast counts from the start again
                self.items = []
                last = None
            gap = last is not None and number != last + 1
            self.items = [x for x in self.items if x[0] < number][-(WINDOW - 1):] + [(number, seconds, gap)]
            self.seen = now
            keep = {f"z{n}.ts" for n, _, _ in self.items}
            for f in sorted(self.folder.glob("z*.ts"), key=lambda p: p.stat().st_mtime)[:-KEEP]:
                if f.name not in keep:
                    f.unlink(missing_ok=True)
        self.write()
        return True

    def text(self) -> str:
        """The playlist (HLS, a live one: no end)."""
        with self._lock:
            items = list(self.items)
        if not items:
            return ""
        lines = ["#EXTM3U", "#EXT-X-VERSION:3", f"#EXT-X-TARGETDURATION:{max(1, math.ceil(max(s for _, s, _ in items)))}",
                 f"#EXT-X-MEDIA-SEQUENCE:{items[0][0]}"]
        for i, (n, s, gap) in enumerate(items):
            if gap and i:
                lines.append("#EXT-X-DISCONTINUITY")
            lines += [f"#EXTINF:{s:.3f},", f"z{n}.ts"]
        return "\n".join(lines) + "\n"

    def write(self) -> None:
        text = self.text()
        if text:
            tmp = self.folder / "z.m3u8.tmp"
            tmp.write_text(text, encoding="utf-8")
            tmp.replace(self.folder / "z.m3u8")

    def segment(self, name: str) -> Path | None:
        """A segment file asked for by name: one of the folder's own (no path is built from what was asked)."""
        if not self.folder.is_dir():
            return None
        return next((p for p in self.folder.glob("z*.ts") if p.name == name), None)


PLAYLIST = Playlist(config.LISTEN_PATH)
