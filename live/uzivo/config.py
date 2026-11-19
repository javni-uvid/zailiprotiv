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

# The site's own list of MPs (name, address, group), fetched at start and every hour: a new convocation's members reach it the hour the site lists them (18 Nov 2026).
SITE = os.environ.get("SITE", "https://zailiprotiv.rs/").strip()
ROSTER_URL = os.environ.get("ROSTER_URL", SITE + "podaci.json").strip()
ROSTER_HOURS = _f("ROSTER_HOURS", 1)
# The last sitting day read afterwards from the whole recording (the site's pages_mikrofon), fetched with the list:
# between sittings it is shown in place of this service's own record of that day, which may have gaps.
DAY_URL = os.environ.get("DAY_URL", SITE + "mikrofon-dan.json").strip()
# "Dok čekate" (a short quiz and facts from the site's counts, pages_mikrofon), shown between sittings.
WAIT_URL = os.environ.get("WAIT_URL", SITE + "mikrofon-cekanje.json").strip()
# The speaker's final votes and the first facts of their page on the site, shown under the name: a reason to open it.
FACTS_URL = os.environ.get("FACTS_URL", SITE + "mikrofon-poslanici.json").strip()

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

# The automatic transcript (prepis.py): Whisper on this computer writes down what is said, a minute at a time.
# "small" keeps up on four cores; "medium" errs less and needs about three times as long; empty turns it off.
WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "small").strip()
# A finished turn read again by a better model, shown in place of the first reading (prepis.Writer.step_whole).
# Off unless named ("medium"): it keeps the computer busy for hours after a long sitting.
WHISPER_FINAL_MODEL = os.environ.get("WHISPER_FINAL_MODEL", "").strip()
# Whether the transcript is shown on the page (19 Nov 2026, the maintainer's decision: no, it errs too much and does
# more harm than good; it is still written down, for the day's steps and the agenda). "1" shows it again.
SHOW_TRANSCRIPT = os.environ.get("PREPIS_PRIKAZ", "0").strip() == "1"
# With the transcript off the page, /prepis?k=<this> still shows it to whoever has the key (the maintainer, to see
# what is being written down). Empty: nobody. At least 12 characters, so that it cannot be guessed.
TRANSCRIPT_KEY = os.environ.get("PREPIS_KLJUC", "").strip()


def transcript_open(key: str = "") -> bool:
    """Whether the transcript page may be shown to this asker: to all when it is on the page, else to the key only."""
    import hmac
    return SHOW_TRANSCRIPT or (len(TRANSCRIPT_KEY) >= 12 and hmac.compare_digest(key.encode(), TRANSCRIPT_KEY.encode()))
# Only the sound in no turn (the chair's) is written down, the speakers' is let go (19 Nov 2026, the maintainer's
# decision: with the transcript off the page, the day's steps are all it is for, and a better, slower model then
# keeps up). "0" writes everything down again.
CHAIR_ONLY = os.environ.get("PREPIS_SAMO_PREDSEDAVAJUCI", "1").strip() != "0"
WHISPER_THREADS = _i("WHISPER_THREADS", 4)
WHISPER_DEVICE = os.environ.get("WHISPER_DEVICE", "cpu").strip()
WHISPER_COMPUTE = os.environ.get("WHISPER_COMPUTE", "int8").strip()
WHISPER_BEAM = _i("WHISPER_BEAM", 3)
SOUND_PATH = os.environ.get("SOUND_PATH", "/tmp/uzivo/zvuk")  # the segments' sound until it is written down

TZ = os.environ.get("TZ_NAME", "Europe/Belgrade")
FRAME_PATH = os.environ.get("FRAME_PATH", "/tmp/uzivo/frame.jpg")
STATE_PATH = os.environ.get("STATE_PATH", "/data/stanje.json")  # today's turns, kept across restarts


def _analytics() -> str:
    """The site's Cloudflare Web Analytics token (public by design, in every page): the image's copy of
    data/settings.json, or the repository's; ANALYTICS_TOKEN overrides, an empty one turns the counting off."""
    if "ANALYTICS_TOKEN" in os.environ:
        return os.environ["ANALYTICS_TOKEN"].strip()
    import json
    from pathlib import Path
    for path in (Path(__file__).parent / "static" / "settings.json",
                 Path(__file__).resolve().parents[2] / "data" / "settings.json"):
        try:
            return str(json.loads(path.read_text(encoding="utf-8")).get("analytics_token") or "")
        except (OSError, ValueError):
            continue
    return ""


# Visits counted as on the site (AGENTS.md, principle 5): Cloudflare's beacon, no cookies, totals per page.
ANALYTICS_TOKEN = _analytics()

