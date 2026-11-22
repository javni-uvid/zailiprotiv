"""Finding the broadcast and taking its newest frame.

For an HLS stream (YouTube live) the playlist is read here and only the newest segment is fetched, its last frame
taken. ffmpeg's own HLS reader gave YouTube's frames in bursts 20-30 s apart; this way each frame is from the very
end of the broadcast.
"""
from __future__ import annotations

import http.client
import io
import logging
import os
import re
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from . import config, prepis

log = logging.getLogger("stream")
_YT_ID = re.compile(r"youtube(?:-nocookie)?\.com/embed/([\w-]{11})")


_BROWSER_HEADERS = {
    # The broadcaster's page refuses (403) requests that do not look like a browser.
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "sr,en;q=0.8",
    "Referer": "https://www.parlament.gov.rs/",
}
_last_youtube_url = ""
VIDEO: dict = {}  # the YouTube video being read: its id and when the broadcast began (for links to its minute)


class NotLive(RuntimeError):
    """No broadcast now: between sittings. Expected, so waited out quietly."""


class _Quiet:
    """yt-dlp's own messages: its "ERROR: … not live" lines between sittings are not errors here."""

    def debug(self, msg: str) -> None:
        pass

    info = warning = debug

    def error(self, msg: str) -> None:
        log.debug("yt-dlp: %s", msg)


def _youtube_url_from_page(page_url: str) -> str:
    global _last_youtube_url
    try:
        req = urllib.request.Request(page_url, headers=_BROWSER_HEADERS)
        with urllib.request.urlopen(req, timeout=20) as resp:
            html = resp.read().decode("utf-8", "replace")
        m = _YT_ID.search(html)
        if not m:
            raise RuntimeError("no YouTube embed on the page")
        _last_youtube_url = f"https://www.youtube.com/watch?v={m.group(1)}"
    except Exception as exc:
        if not _last_youtube_url:
            raise RuntimeError(
                f"{page_url} not read ({exc}); set YOUTUBE_URL in .env"
            ) from exc
        log.warning("page not read (%s); using the last known stream", exc)
    return _last_youtube_url


def _resolve_youtube(url: str) -> str:
    from yt_dlp import YoutubeDL

    h = config.MAX_HEIGHT
    opts = {
        "quiet": True,
        "no_warnings": True,
        "logger": _Quiet(),
        # The picture is what is needed; a format with sound first, for the automatic transcript (prepis.py), one
        # without will do. HLS (m3u8) first: it is read below.
        "format": (
            f"b[protocol^=m3u8][height<={h}]/bv*[protocol^=m3u8][height<={h}]/"
            f"b[height<={h}]/bv*[height<={h}]/b/bv*"
        ),
    }
    if config.YTDLP_COOKIES:
        opts["cookiefile"] = config.YTDLP_COOKIES
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:
        text = str(exc)
        if any(w in text for w in ("not live", "not currently live", "live event will begin", "Premieres in", "is offline", "has ended")):
            raise NotLive(f"{url}: no broadcast now") from exc
        raise RuntimeError(f"yt-dlp got no stream for {url}: {exc}") from exc
    if not info.get("is_live"):
        # Between sittings the page may embed a past broadcast: its last frame would name the last speaker of then.
        raise NotLive(f"{url} is not live ({info.get('live_status')})")
    log.info(
        "format %s: %sp, %s, ~%s kbit/s",
        info.get("format_id"), info.get("height"), info.get("protocol"), info.get("tbr"),
    )
    VIDEO.update(id=info.get("id", ""), started=info.get("release_timestamp"))
    SOUND.clear()
    if prepis.on() and (info.get("acodec") or "none") == "none":
        # YouTube's live formats came without sound in the picture (19 Nov 2026: format 231): the sound is a
        # playlist of its own, with the same segment numbers.
        SOUND.update(url=sound_format(info.get("formats") or []))
        log.info("sound: %s", "a playlist of its own" if SOUND.get("url") else "none found, no transcript")
        if not SOUND.get("url"):  # what there was, to see why
            log.info("formats: %s", "; ".join(f"{f.get('format_id')} {f.get('protocol')} v={f.get('vcodec')} a={f.get('acodec')}"
                                              for f in info.get("formats") or []))
    return info["url"], info.get("http_headers") or {}


def _program_time(text: str) -> float | None:
    """#EXT-X-PROGRAM-DATE-TIME's value as a Unix time, or None."""
    from datetime import datetime
    try:
        return datetime.fromisoformat(text.strip().replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


SOUND: dict = {}  # the address of the broadcast's sound, when the picture's format has none


def sound_format(formats: list[dict]) -> str:
    """The lightest HLS format that is sound only, its address; "" when there is none."""
    # yt-dlp marks a playlist's sound track by "no picture" (vcodec none); its acodec is often not said at all
    only = [f for f in formats if str(f.get("protocol", "")).startswith("m3u8") and f.get("vcodec") == "none"
            and f.get("acodec") != "none" and f.get("url")]
    return min(only, key=lambda f: (f.get("abr") or f.get("tbr") or 0, str(f.get("format_id"))))["url"] if only else ""


def resolve_input() -> tuple[str, dict]:
    """An address (or a path) to read frames from, and the HTTP headers for it."""
    if config.STREAM_URL:
        VIDEO.clear()
        SOUND.clear()
        return config.STREAM_URL, {}
    # The broadcaster's page first, read afresh each time: each sitting day is a new YouTube video, and an address
    # fixed in .env would keep pointing at a broadcast that has ended. YOUTUBE_URL only when the page can't be read.
    global _last_youtube_url
    if config.YOUTUBE_URL and not _last_youtube_url:
        _last_youtube_url = config.YOUTUBE_URL
    # The page's video may be other than the live one (18 Nov 2026: a private video, the sitting live in another):
    # then the last video seen live, the one in .env, and the channel's "/live", whichever is live first.
    first = _youtube_url_from_page(config.SOURCE_PAGE) if config.SOURCE_PAGE else config.YOUTUBE_URL
    tried, err = [], None
    for yt in (first, _last_live, config.YOUTUBE_URL, config.CHANNEL_LIVE):
        if not yt or yt in tried:
            continue
        tried.append(yt)
        try:
            got = _resolve_youtube(yt)
        except NotLive as exc:
            err = exc
            continue
        except Exception as exc:  # a private or removed video: try the next
            err = exc
            continue
        _remember_live()
        log.debug("YouTube stream: %s", yt)
        return got
    if isinstance(err, NotLive) or err is None:
        raise NotLive(f"none live of {len(tried)} tried")
    raise err


_last_live = ""  # the last video found live, kept for when the page points elsewhere


def _remember_live() -> None:
    global _last_live
    if VIDEO.get("id"):
        _last_live = f"https://www.youtube.com/watch?v={VIDEO['id']}"


def _is_hls(source: str) -> bool:
    return not os.path.exists(source) and ("m3u8" in source or "hls_playlist" in source)


def _ffmpeg_last_frame(segment: str) -> None:
    """A segment's last frame → FRAME_PATH (atomically, so the worker never reads half a file)."""
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
            "-i", segment, "-an", "-vf", "fps=2", "-q:v", "3",
            "-f", "image2", "-atomic_writing", "1", "-update", "1", config.FRAME_PATH,
        ],
        check=True, capture_output=True, timeout=30,
    )


_SQ = re.compile(r"/sq/(\d+)/")


class HlsPoller(threading.Thread):
    """Takes the last frame of each new HLS segment. Behaves like Popen (poll/kill/stderr), so the worker need not
    know the difference.

    YouTube's playlist answers slowly (5-12 s) while a segment comes in a fraction of a second. So the playlist is
    read in the background only to know where the broadcast's end is, and the next segment is asked for by its
    number (/sq/N/ in the address) as soon as it is there.
    """

    def __init__(self, playlist_url: str, headers: dict, sound_url: str = "") -> None:
        super().__init__(daemon=True)
        self.url = playlist_url
        self.sound_url = sound_url  # the sound's own playlist, when the picture's segments have none
        self._sound_segments: dict[int, str] = {}
        self.headers = {"User-Agent": "Mozilla/5.0", **headers}
        self.stderr = io.BytesIO()
        self._halt = threading.Event()
        self._code: int | None = None
        self._lock = threading.Lock()
        self._segments: dict[int, str] = {}   # number → address, from the latest playlist
        self._program: dict[int, float] = {}  # number → when it begins by the broadcast's own clock (PROGRAM-DATE-TIME)
        self._newest = -1
        self._dur = 5.0
        self._ended = False
        self._pl_error: Exception | None = None
        self._net_error: Exception | None = None  # the last segment that did not come for a fault on the way
        self._pl_ok_at = time.time()
        self.frame_seq: int | None = None
        self.seg_dur: float | None = None
        self.start()

    # --- network -------------------------------------------------------------------------
    def _get(self, url: str, timeout: float = 20) -> bytes:
        req = urllib.request.Request(url, headers=self.headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()

    def _read_playlist(self) -> None:
        text = self._get(self.url).decode("utf-8", "replace")
        if "#EXT-X-STREAM-INF" in text:  # a master playlist: take its first variant
            variant = next(l for l in text.splitlines() if l and not l.startswith("#"))
            self.url = urllib.parse.urljoin(self.url, variant.strip())
            return self._read_playlist()
        seq, dur, segs, clock, program = 0, self._dur, {}, None, {}
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("#EXT-X-MEDIA-SEQUENCE:"):
                seq = int(line.split(":", 1)[1])
            elif line.startswith("#EXTINF:"):
                dur = float(line[8:].split(",")[0] or dur)
            elif line.startswith("#EXT-X-PROGRAM-DATE-TIME:"):
                clock = _program_time(line.split(":", 1)[1])
            elif line and not line.startswith("#"):
                url = urllib.parse.urljoin(self.url, line)
                m = _SQ.search(url)
                n = int(m.group(1)) if m else seq
                segs[n] = url
                if clock is not None:  # the broadcast's clock: what the viewer's player tells the page it shows
                    program[n] = clock
                    clock += dur
                seq += 1
        if not segs:
            raise RuntimeError("playlist without segments")
        with self._lock:
            self._segments, self._newest, self._dur = segs, max(segs), dur
            self._program = program
            self._ended = "#EXT-X-ENDLIST" in text
            self._pl_ok_at = time.time()

    def _playlist_loop(self) -> None:
        while not self._halt.is_set():
            try:
                self._read_playlist()
                self._pl_error = None
            except Exception as exc:  # one error is not the end; the worker judges by frames
                self._pl_error = exc
                log.warning("playlist: %s", exc)
            self._halt.wait(1.0)

    def _sound_loop(self) -> None:
        """The sound's playlist, read now and then for its segments' addresses (the numbers are the picture's)."""
        while not self._halt.is_set():
            try:
                text = self._get(self.sound_url).decode("utf-8", "replace")
                if "#EXT-X-STREAM-INF" in text:
                    variant = next(l for l in text.splitlines() if l and not l.startswith("#"))
                    self.sound_url = urllib.parse.urljoin(self.sound_url, variant.strip())
                    continue
                seq, segs = 0, {}
                for line in text.splitlines():
                    line = line.strip()
                    if line.startswith("#EXT-X-MEDIA-SEQUENCE:"):
                        seq = int(line.split(":", 1)[1])
                    elif line and not line.startswith("#"):
                        url = urllib.parse.urljoin(self.sound_url, line)
                        m = _SQ.search(url)
                        segs[int(m.group(1)) if m else seq] = url
                        seq += 1
                if segs:
                    with self._lock:
                        self._sound_segments = segs
            except Exception as exc:
                log.debug("sound playlist: %s", exc)
            self._halt.wait(10.0)

    def _sound(self, n: int) -> bytes | None:
        """Segment n's sound, or None: never an error, the frame matters more."""
        with self._lock:
            url = self._sound_segments.get(n)
            if not url:
                url = next((_SQ.sub(f"/sq/{n}/", u) for u in reversed(list(self._sound_segments.values()))
                            if _SQ.search(u)), None)
        if not url:
            return None
        for _ in range(3):  # the sound's segment may come a moment after the picture's
            try:
                data = self._get(url, timeout=10)
                if len(data) > 512:
                    return data
            except Exception:
                pass
            if self._halt.wait(0.7):
                break
        return None

    def program_of(self, n: int) -> float | None:
        """When segment n begins by the broadcast's own clock; past the playlist, counted on from its last."""
        with self._lock:
            if n in self._program:
                return self._program[n]
            if not self._program:
                return None
            last = max(self._program)
            return self._program[last] + (n - last) * self._dur

    def _segment_url(self, n: int) -> str | None:
        with self._lock:
            if n in self._segments:
                return self._segments[n]
            # Not yet in the (slow) playlist: make its address from a known segment's.
            for url in reversed(list(self._segments.values())):
                if _SQ.search(url):
                    return _SQ.sub(f"/sq/{n}/", url)
        return None

    def _fetch(self, n: int) -> bytes | None:
        url = self._segment_url(n)
        if not url:
            return None
        try:
            data = self._get(url, timeout=15)
        except urllib.error.HTTPError as exc:
            if exc.code in (204, 404, 410, 425):  # not published yet
                return None
            raise
        except (OSError, http.client.HTTPException) as exc:
            # A fault on the way (a name not found, a reset, a timeout: 18 Nov 2026, one lookup failed and the
            # reading stopped) is asked again; only the broadcast standing still for long ends the reading.
            self._net_error = exc
            return None
        self._net_error = None
        return data if len(data) > 1024 else None

    # --- main loop -----------------------------------------------------------------
    def run(self) -> None:
        os.makedirs(os.path.dirname(config.FRAME_PATH), exist_ok=True)
        threading.Thread(target=self._playlist_loop, daemon=True).start()
        if self.sound_url:
            threading.Thread(target=self._sound_loop, daemon=True).start()
        try:
            while self._newest < 0:  # the first playlist
                if self._halt.wait(0.2):
                    return
                if self._pl_error and time.time() - self._pl_ok_at > 60:
                    raise RuntimeError(f"playlist unavailable: {self._pl_error}")
            nxt = self._newest
            last_new = time.time()
            with tempfile.TemporaryDirectory() as tmp:
                path = os.path.join(tmp, "seg")
                while not self._halt.is_set():
                    with self._lock:
                        newest, dur, ended = self._newest, self._dur, self._ended
                    if newest > nxt:      # fell behind (after a stall): jump to the end
                        nxt = newest
                    t0 = time.time()
                    data = self._fetch(nxt)
                    if data is None:
                        if ended and nxt > newest:
                            raise RuntimeError("end of broadcast")
                        if time.time() - last_new > max(60, 6 * dur):
                            why = f" (last: {self._net_error})" if self._net_error else ""
                            raise RuntimeError(f"no new segment for {time.time() - last_new:.0f} s{why}")
                        self._halt.wait(1.0 if self._net_error else 0.5)
                        continue
                    t1 = time.time()
                    with open(path, "wb") as f:
                        f.write(data)
                    self.frame_seq, self.seg_dur = nxt, dur  # read with the frame: where it is in the broadcast
                    _ffmpeg_last_frame(path)
                    t2 = time.time()
                    if not prepis.on():
                        pass
                    elif not self.sound_url:
                        prepis.keep(path, t2, dur, self.program_of(nxt))  # the segment's sound, for the transcript
                    else:
                        heard = self._sound(nxt)
                        if heard:
                            with open(path + "-zvuk", "wb") as f:
                                f.write(heard)
                            prepis.keep(path + "-zvuk", t2, dur, self.program_of(nxt))
                    if t2 - last_new > 2.5 * dur:
                        log.info(
                            "segment %d after %.0f s (segment %.1f s, fetch %.1f s, frame %.1f s)",
                            nxt, t2 - last_new, dur, t1 - t0, t2 - t1,
                        )
                    last_new = t2
                    nxt += 1
            self._code = 0
        except Exception as exc:
            if isinstance(exc, subprocess.CalledProcessError):
                msg = exc.stderr.decode("utf-8", "replace")
            else:
                msg = str(exc)
            self.stderr = io.BytesIO(msg.encode())
            self._code = 1
        finally:
            # The playlist's thread ends with this one. Left running (until 18 Nov 2026 it was, after every reading
            # that ended by itself), each kept asking YouTube for its playlist for as long as the service ran.
            self._halt.set()

    def poll(self) -> int | None:
        return self._code

    def kill(self) -> None:
        self._halt.set()


def start_ffmpeg(source: str, headers: dict | None = None):
    os.makedirs(os.path.dirname(config.FRAME_PATH), exist_ok=True)
    if _is_hls(source):
        return HlsPoller(source, headers or {}, SOUND.get("url", "") if prepis.on() else "")
    # A file or another stream: one ffmpeg that keeps running.
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-re"]
    if headers and headers.get("User-Agent"):
        cmd += ["-user_agent", headers["User-Agent"]]
    cmd += [
        "-i", source,
        "-an",
        "-vf", f"fps=1/{config.FRAME_INTERVAL}",
        "-q:v", "3",
        "-f", "image2", "-atomic_writing", "1", "-update", "1", "-y",
        config.FRAME_PATH,
    ]
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
