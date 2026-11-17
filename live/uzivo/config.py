"""Settings from the environment (live/.env). Defaults fit the Assembly's broadcast as it looks in November 2026."""
import os


def _f(name: str, default: float) -> float:
    return float(os.environ.get(name, default))


def _i(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


# Where the broadcast comes from: a stream (STREAM_URL), a YouTube address (YOUTUBE_URL), or the broadcaster's page
# that embeds the Assembly's YouTube stream (SOURCE_PAGE, read once per start).
STREAM_URL = os.environ.get("STREAM_URL", "").strip()
YOUTUBE_URL = os.environ.get("YOUTUBE_URL", "").strip()
SOURCE_PAGE = os.environ.get("SOURCE_PAGE", "https://www.videonet.co.rs/nsrsZasedanje1l.htm").strip()
YTDLP_COOKIES = os.environ.get("YTDLP_COOKIES", "").strip()
MAX_HEIGHT = _i("MAX_HEIGHT", 480)  # the caption reads well at 480p, and the stream is two to three times lighter
FRAME_INTERVAL = _f("FRAME_INTERVAL", 2)  # only for a stream that is not HLS; HLS gives one frame per segment

# The site's own list of MPs (name, address, group), fetched at start and every few hours.
SITE = os.environ.get("SITE", "https://zailiprotiv.rs/").strip()
ROSTER_URL = os.environ.get("ROSTER_URL", SITE + "podaci.json").strip()
ROSTER_HOURS = _f("ROSTER_HOURS", 6)

# Where the caption is, as a share of the frame: its two lines sit in the bottom ~12 %, on the left.
CROP_LEFT = _f("CROP_LEFT", 0.0)
CROP_TOP = _f("CROP_TOP", 0.86)
CROP_WIDTH = _f("CROP_WIDTH", 0.62)
CROP_HEIGHT = _f("CROP_HEIGHT", 0.14)
OCR_LANG = os.environ.get("OCR_LANG", "srp")
WHITE_THRESHOLD = _i("WHITE_THRESHOLD", 190)  # the caption is white text
TOPHAT_MIN = _i("TOPHAT_MIN", 40)  # how far the text must stand out from what is around it

# When a reading counts.
MATCH = _f("MATCH", 0.8)  # each word of a name on the list, compared letter by letter (0-1)
CLEAN_CONF = _i("CLEAN_CONF", 85)  # a name not on the list is shown only when every word is read this surely
HOLD_SECONDS = _f("HOLD_SECONDS", 25)  # no readable name this long: the speaker is no longer known
STALE_SECONDS = _f("STALE_SECONDS", 60)  # no new frame this long: no broadcast
MERGE_SECONDS = _f("MERGE_SECONDS", 120)  # the same speaker again within this: one turn, not two

TZ = os.environ.get("TZ_NAME", "Europe/Belgrade")
FRAME_PATH = os.environ.get("FRAME_PATH", "/tmp/uzivo/frame.jpg")
STATE_PATH = os.environ.get("STATE_PATH", "/data/stanje.json")  # today's turns, kept across restarts
