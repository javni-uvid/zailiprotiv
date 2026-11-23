# The live page: listening

Decisions about the live page `mikrofon.zailiprotiv.rs` and its service: the recording's sound, the lock screen, the live sound and its bucket. Moved word for word from
`live/AGENTS.md` on 23 Nov 2026 (it had grown to 77 KB, read whole by every agent working in `live/`); what holds now,
in short, is there. **Keep it current:** a decision is added at the end of this file, in the same commit, and one that
changes an earlier one says so. Dates are the maintainer's decisions unless said otherwise.

**Changed since written:** "A trial behind the key" (22 Nov): open to all since the 24 Nov sitting (`SLUSAJ_JAVNO=1`).

- **The page as an app: only the sound, and the lock screen's player** (22 Nov 2026, the maintainer, predlog 2 after
  readers asked to listen in the car). Beside "Pusti snimak dana" (an archive day's recording) "Slušaj samo zvuk"
  plays the same file in an `<audio>` (`data-zvuk`), which a phone keeps playing with the screen locked; over it who
  speaks at that moment and, where the page holds it, that turn's automatic transcript. For the archive's files the
  page sets the Media Session (`mikrofon.js`, `session`): the title is who speaks (the day's turns' "▶ snimak" of
  that file, as the page lists them), the artist their list or office, ⏮ ⏭ the turn before or after, ±15/30 s;
  the turn now playing is outlined in the list. A turn's ▶ keeps the way the day is played. The live broadcast
  stays YouTube's player (its iframe holds its own session; no sound of ours is relayed: rights, and the tunnel is
  not made for streams). The site's mikrofon page and day pages (`govornici/<date>`) have the same button.
- **Listening live, sound only: a trial behind the key** (22 Nov 2026, the maintainer: the rights are settled on their
  side; "napravimo probnu verziju"). `slusaj.py`: each segment the reader already fetches (the sound-only track's
  when YouTube has one, else the picture's) gives its sound to a live HLS playlist of our own (`LISTEN_PATH`): the
  sound copied as it is (`-c:a copy`, no new encoding) with the broadcast's timestamps (`-copyts`), so the segments
  follow on; the last `WINDOW` (12) listed, `KEEP` (20) files on disk, a gap in the numbers marked a discontinuity.
  No new request to YouTube. `/slusaj/<key>/` (the transcript's key, in the path so that the playlist's relative
  addresses carry it; anything else 404) is a page with an `<audio>` on `z.m3u8`, played by the phone's own player
  (Safari, Chrome on Android; a desktop Chrome is told to use a phone), and the lock screen's player says who speaks
  now from `/stanje.json` every 10 s. Not linked from anywhere; opening it to all (a button on the page, caching at
  Cloudflare's edge, a player for desktops served from our domain) is the maintainer's decision after the trial.
- **Listening live: the button, behind a switch** (22 Nov 2026, the maintainer tried both on a Serbian 24/7 news
  channel, IZLAZ.com, in a hand-run container: `SOURCE_PAGE=`, `CHANNEL_LIVE=`, `YOUTUBE_URL=<watch address>`,
  `SLUSAJ_JAVNO=1`, port 8095). With `SLUSAJ_JAVNO=1` the broadcast's player has "🎧 Slušaj samo zvuk" under the
  picture while the playlist has a segment from the last minute (`slusaj.fresh`), and `/slusaj/z.m3u8` with its
  segments needs no key (segments cacheable, `immutable`). The press puts our sound in the screen ("Samo zvuk,
  uživo", who speaks from the part, the lock screen's player); the same button then offers "▶ Gledaj prenos", and
  back. Off on the live service until the maintainer opens it. Found by the trial: the sound-only track was asked
  for only while the transcript was on (`_resolve_youtube`, `HlsPoller`); listening asks for it too. Chrome 150 and
  phones play the playlist by themselves.
- **The live sound from Cloudflare R2** (22 Nov 2026, the maintainer's choice among three): Cloudflare caches by a
  file's extension and not `.ts` or `.m3u8`, so through the tunnel every listener would draw the sound from the
  maintainer's computer, and its terms for the free plan want video and "a disproportionate percentage of ... audio
  files" served from its paid storage (R2, Stream). With `ZVUK_R2_ENDPOINT`, `ZVUK_R2_BUCKET`, `ZVUK_R2_KLJUC`,
  `ZVUK_R2_TAJNA` and `ZVUK_URL` in `live/.env` (`r2.py`), each segment goes to the bucket once, under
  `uzivo/<the broadcast's video id>/` (the numbers start again with each broadcast; `immutable`), then the playlist
  `uzivo/z.m3u8` (`max-age=1`), from one thread in order, a full queue dropping its oldest job; the button plays
  `ZVUK_URL` + `uzivo/z.m3u8` (`slusaj.address`). The PUT is signed by hand (AWS Signature Version 4), no new
  library; checked against botocore for the same request and moment. The bucket's settings are the maintainer's:
  the public domain `zvuk.zailiprotiv.rs`, CORS for `mikrofon.zailiprotiv.rs`, objects deleted after a day, and a
  cache rule for that host so that listeners are served from Cloudflare's cache.
