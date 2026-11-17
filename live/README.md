# uzivo: who is speaking now

**https://mikrofon.zailiprotiv.rs**: who is speaking in the National Assembly at this moment, and who spoke today, read
from the caption under the speaker in the Assembly's live broadcast.

Unlike the rest of the project this is not a static page: something has to watch the broadcast. It runs as two
Docker containers on the maintainer's computer, reached through a Cloudflare tunnel. YouTube often refuses data
centres' addresses (GitHub's runners among them), and a home address works.

## How it works

1. **The broadcast.** The broadcaster's page (`videonet.co.rs/nsrsZasedanje1l.htm`, linked from the Assembly's
   "Prenosi") embeds the Assembly's YouTube stream; yt-dlp turns it into an HLS address (480p, video only). Only a
   live stream is taken: a past broadcast's last frame would name a speaker of then.
2. **A frame per segment.** YouTube's playlist answers slowly (5-12 s) while a segment comes in a fraction of a
   second, so the playlist is read in the background and each next segment is asked for by its number (`/sq/N/`)
   as soon as it is out; its last frame is kept. About one frame every 5 s, from the very end of the broadcast.
3. **The caption.** Its place in the frame (bottom 14 %, left 62 %) is cut out, the thin white letters kept (a
   top-hat filter, so white shirts and papers behind drop out), and Tesseract reads it (Serbian Cyrillic). The
   caption has two lines: the name, and under it the list or office. A list's name often holds its leader's name, so
   **a name is looked for only on the upper line.**
4. **Who it is.** The name line is compared with the site's own list of MPs (`zailiprotiv.rs/podaci.json`, fetched
   every 6 hours, the last copy kept): every word of an MP's name must be on the line, each at least 80 % alike
   letter by letter, with at most one word of noise; two MPs equally close count for none. A name not on the list (a
   minister, a guest, an MP the list doesn't have yet) is shown only when every word is read surely and in two frames
   in a row.
5. **Turns.** The same rule for everyone: a turn starts with the first frame naming the speaker and lasts while
   frames go on naming them; it ends when another name is read, when two frames in a row name someone else even
   unreadably, when no name is read for 25 s, or when the broadcast stops. The same speaker again within 2 minutes
   is one turn. Today's turns are listed by time (a turn read in a single frame is left out), kept across restarts.

The page is in Latin at `/` and in Cyrillic at `/cir/`, links each MP to their page on the site, and loads nothing
from elsewhere (the fonts are served with it, the one script is inline). `/stanje.json` is the same as JSON.

**Each day's record** is kept in a file of its own (`/data/dani/<date>.json`) and served at `/dan/<date>.json`
(`/dani.json` lists the days): every turn with how many frames named the speaker (`okvira`), where it is in the
broadcast (the YouTube video, the numbers of its first and last HLS segment, the segment's length), and the spans
when the service saw the broadcast at all (`pokriveno`; outside them there is no record, not silence). The site's
**votes** workflow takes these in (`uzivo-pull`), to link each speech in the notes to its minute in the recording.

**On the page** (18 Nov 2026), each turn of the day links to its place in the YouTube recording ("▶ snimak 1:23:45":
the first segment that named the speaker, less one, times the segment's length; `RECORDING_LEAD`). After the sitting
day, the list stays, under "Poslednji dan sednice" and its date, until someone is read at the next sitting.

Delays: the broadcast runs 15-25 s behind the hall, and a segment is 5 s.

## Running it

```sh
cd live
cp .env.example .env
printf 'TUNNEL_TOKEN=%s\n' '<token from Cloudflare>' > .tunnel.env   # never committed
docker compose up -d --build
docker compose logs -f uzivo
```

In Cloudflare (Zero Trust → Networks → Tunnels), the tunnel's public hostname `mikrofon.zailiprotiv.rs` points to
`http://uzivo:8000`. A log line per frame: `name matched | name line | list line -> state`.

While the computer is off, Cloudflare would answer with its own error (530). A worker in front of the hostname
(`edge/`, published by the `worker` workflow) passes every request to the tunnel and, when it fails, shows the site's
page for that instead (zailiprotiv.rs/mikrofon: why it is down, the broadcast, the next sitting, a few facts from the
site). Nothing changes in the tunnel or the DNS.

When YouTube asks to sign in, put a `cookies.txt` in the volume and set `YTDLP_COOKIES=/data/cookies.txt`; when
yt-dlp stops working, `docker compose build --pull --no-cache uzivo` takes the newest.

Settings are in `uzivo/config.py`, each overridable from `.env`.

## Code

```
uzivo/
  stream.py     the broadcast: the YouTube address, the HLS segments, a frame each
  ocr.py        the caption's place, its letters, Tesseract's words by line
  caption.py    the two lines; who the name line names (no OCR: tested)
  names.py      both scripts; the site's list of MPs and matching to it (tested)
  state.py      the current speaker and today's turns (tested)
  page.py       the page in both scripts (tested)
  worker.py, main.py, config.py
```

The tests are in the repository's `tests/test_live.py` and run with the rest (`uv run pytest -q`); they need none
of the service's packages.
