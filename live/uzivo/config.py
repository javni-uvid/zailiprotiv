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
# The Assembly's own YouTube channel: its "/live" is whatever it broadcasts now. Tried when the page's video isn't
# live (18 Nov 2026: the page embedded a private video while the sitting went on in another).
CHANNEL_LIVE = os.environ.get("CHANNEL_LIVE", "https://www.youtube.com/channel/UCghngrfQwzJ4aaPZ-UgNIZQ/live").strip()
YTDLP_COOKIES = os.environ.get("YTDLP_COOKIES", "").strip()
MAX_HEIGHT = _i("MAX_HEIGHT", 480)  # the caption reads well at 480p, and the stream is two to three times lighter
FRAME_INTERVAL = _f("FRAME_INTERVAL", 2)  # only for a stream that is not HLS; HLS gives one frame per segment

# The site's own list of MPs (name, address, group), fetched at start and every few hours.
SITE = os.environ.get("SITE", "https://zailiprotiv.rs/").strip()
ROSTER_URL = os.environ.get("ROSTER_URL", SITE + "podaci.json").strip()
ROSTER_HOURS = _f("ROSTER_HOURS", 6)
# The last sitting day read afterwards from the whole recording (the site's pages_mikrofon), fetched with the list:
# between sittings it is shown in place of this service's own record of that day, which may have gaps.
DAY_URL = os.environ.get("DAY_URL", SITE + "mikrofon-dan.json").strip()
# "Dok čekate" (a short quiz and facts from the site's counts, pages_mikrofon), shown between sittings.
WAIT_URL = os.environ.get("WAIT_URL", SITE + "mikrofon-cekanje.json").strip()

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
# Where a turn begins in the recording: its first segment's number, less one segment as the caption comes up
# after the speaker begins, times the segment's length (the YouTube video keeps the broadcast's numbering).
RECORDING_LEAD = _i("RECORDING_LEAD", 1)

TZ = os.environ.get("TZ_NAME", "Europe/Belgrade")
FRAME_PATH = os.environ.get("FRAME_PATH", "/tmp/uzivo/frame.jpg")
STATE_PATH = os.environ.get("STATE_PATH", "/data/stanje.json")  # today's turns, kept across restarts
