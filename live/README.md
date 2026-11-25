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
   every hour, the last copy kept): every word of an MP's name must be on the line, each at least 80 % alike
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

**A speech's own link** (25 Nov 2026; `deljenje.py`, `mikrofon.js`): "podeli" beside each finished turn gives
`/govor/<second it began>` (and `/cir/govor/…`): the page with that speech in the player's place, starting by itself where
the browser lets a page sound without a press, else on its button; the link's card has the speaker's name and the time
(`DELI_IME=0`: no name) and `/govor.png`. A speech of an earlier day leads to the site's page of that day, if the site
lists it (`dani` in `mikrofon-cekanje.json`), and anything else to the page. The edge keeps `/govor/…` three seconds, as `/`.

**After the broadcast** (25 Nov 2026; `prenosi.py`), until the archive has a file of the day, its speeches' and steps' times
play the broadcast's own YouTube video, for as long as that is public: asked of YouTube's oEmbed at most once in ten minutes, and no
link on any answer but yes. `/data/prenosi/<day>.json` keeps the video, when its first second was (`pocetak`) and what was read of
it (`od`, `do`), all as seconds of the clock.

**Between sittings** the service looks for a broadcast once a minute, quietly (one line in the log, not one per
look; yt-dlp's own "not live" errors are kept out of it), and starts reading within a minute of the next sitting
going live. Each sitting day is a new YouTube video, so the broadcaster's page is read afresh every time; `YOUTUBE_URL`
is used only while that page can't be read. When the page's video isn't live (18 Nov 2026: it embedded a private
video while the sitting went on in another), the last video seen live, `YOUTUBE_URL`, and the Assembly's channel's
`/live` (`CHANNEL_LIVE`) are tried, in that order.

Delays: the broadcast runs 15-25 s behind the hall, and a segment is 5 s.

**The last sitting day from the recording.** Between sittings the page lists the last sitting day. The service may
have missed part of it (it was off, or the caption's layout was one it doesn't read), so when the site has that day
read afterwards from the whole recording (`data/<N>/snimak/<date>.json`, published as
`zailiprotiv.rs/mikrofon-dan.json`, fetched with the list of MPs and kept as `/data/snimak.json`), the page lists
that day instead and says so. It does so only for a day the same as or later than the service's own last day, and
never for today. `/dan/<date>.json` stays the service's own record.

**"Da li ste znali".** While there is no broadcast the page also carries a few facts from the site's own
counts (`zailiprotiv.rs/mikrofon-cekanje.json`, fetched with the list and kept as `/data/cekanje.json`), each linked
to the page that says how it is computed. The same file's quiz is no longer shown here (22 Nov 2026); the site's
`mikrofon` page keeps it.

**The player.** Above the list, a button: while the broadcast is on, our own picture of the moment with
"▶ Gledaj prenos", whose press (or that of the same words on the button after "Slušaj") loads the YouTube video of it (`youtube-nocookie.com`), playing, and adds one to the
site's counter (`mikrofon.pusti`, "Slušaj" `mikrofon.slusaj`: sums per day and hour; `VOTES_API=` empty turns it off); between sittings the last day's recording from the broadcaster's archive (a plain
`<video>`), and each turn's "▶ snimak" plays that file from the turn's second. Nothing from YouTube or the archive
loads before a click (AGENTS.md, principle 5; a link to a speech starts by itself, see above); without the script the links open the recording.

**The next sitting and the home screen** (20 Nov 2026). Between sittings, under "no sitting now", the next sitting
convened, or one begun that goes on on another day as its page at the Assembly says (`sazvano` in
`mikrofon-cekanje.json`: the first one still to come, from the current and the newest convocation; `nastavak` for one
begun), stands on a card on top and in the link's picture, with no hand in it. One convened is also counted down each second, with its day, hour, title and agenda. The page has a manifest
(`/manifest.webmanifest`, `/cir/manifest.webmanifest`) and icons drawn from its microphone (`/ikona-*.png`,
`picture.icon`), so a phone can keep it on its home screen; where the browser offers that (Chrome, Edge, Samsung)
the page shows its own button for it, and on an iPhone a line saying where Safari keeps it. On a phone the head is
short, so the broadcast is in the first screen.

**A notification when a sitting begins** (20 Nov 2026). "Obavesti me kad sednica počne" registers the page's
service worker (`/sw.js`) and sends the browser's push address to the site's counter. After three frames of a live
broadcast in a row, between 7 and 22 h, the service (`obavesti.py`) asks the counter to send the day's notification,
once a day; it needs `PUSH_TOKEN` in `.env` (the test has it empty and never sends). See `worker/README.md`.

**Told when it is down** (20 Nov 2026): open `/upozorenja?k=<PREPIS_KLJUC>` on your phone and turn it on; the
site's counter then notifies that phone when this service doesn't answer through two checks five minutes apart
while the Assembly lists a sitting in progress (weekdays, 7-20 h), and again when it answers. See
`worker/README.md`.

## Running it

Two images, **test first, then live** (19 Nov 2026, the maintainer's decision): a change is built and tried
locally, and only the image the test ran goes live, never one built afresh for it. Since 20 Nov 2026 only an image
of a clean `origin/main` goes live, and every image says which commit it is.

```powershell
cd live
cp .env.example .env
Set-Content -Encoding ascii .tunnel.env "TUNNEL_TOKEN=<token from Cloudflare>"   # never committed
.\mikrofon.ps1 test      # this tree's test, as two containers (-Jedan: as one; -Novo: the newest yt-dlp); says where it is
.\mikrofon.ps1 uzivo     # mikrofon:test goes live as the page, if built from a clean origin/main (-Ipak: anyway); -Deo
                         # merenje or oba: the measuring, or both; -Jedan: while live is one container
.\mikrofon.ps1 nazad -Deo strana   # (merenje, oba) the part's image that was live before, live again; -Jedan: below
.\mikrofon.ps1 stanje    # each image's commit, the containers and their health, and the commits of each part not live
.\mikrofon.ps1 logovi    # the live service's log (-Deo strana or merenje; -Test: this tree's test)
.\mikrofon.ps1 ocisti    # remove untagged images and the tests of worktrees that are gone
```

- **Live** (`docker-compose.yml`, project `mikrofon`): two containers and the tunnel, none of which builds. `merenje`
  (`mikrofon:uzivo`, before it `mikrofon:prethodni`) reads the broadcast and writes all that is kept, in the volume
  `mikrofon-podaci`; `uzivo` (`mikrofon:strana`, `mikrofon:strana-prethodni`) is the page on port 8000 and the mail. `uzivo`
  runs only from the main clone on `main`, and only an image whose labels say it was built from `origin/main` as it is
  now, with nothing uncommitted; it waits until the new one answers with that commit, and if it doesn't within 90 s, puts
  the one before back. Not by `docker compose up` by hand, which replaces both.
- **Which part to release:** `stanje` says which commits wait for which (one in a module both load stands under both, and
  the page alone may have it at once). The page is replaced in a second or two and the measuring goes on; the measuring is back in some
  seven seconds, in which the page goes on with what it had, so it waits for the turn to end; when both, the measuring goes first.
  Parts of two formats (`state_base.FORMAT`, the image's label) go live only together; the script asks.
- **What each container has of `.env`** (it is one file; what one must not have is emptied by name in `docker-compose.yml`):
  the page `MEJL_KLJUC` and `MEJL_UREDNIK` (the readers' addresses and the maintainer's own), the measuring `ANTHROPIC_API_KEY`
  and `ZVUK_R2_*`, both `PUSH_TOKEN` and `PREPIS_KLJUC`. The page reads `/data` and writes only `/data/mejl`.
- **From one container to two:** `uzivo -Deo oba`, once, on a day without a sitting (nothing answers for some nine seconds, the
  edge gives the last answers); it undoes itself if it fails. **Back:** `nazad -Jedan` (`docker-compose.jedan.yml`: one container of the
  measuring's image, with the whole `.env`), then, if the image is at fault, `nazad`. The kept files are the same either way.
- **Tests** (`docker-compose.test.yml`): from the main clone on `main`, `mikrofon:test` at port 8001 (project
  `mikrofon-test`, volume `mikrofon-test-podaci`); from a worktree, `mikrofon:test-<branch>` on a port of its own
  (8002-8091, from the branch's name) with its own project and volume, as two containers like the live service, so that agents' tests never replace each
  other's or the one `uzivo` takes. A worktree's test takes `.env` from the main clone. No tunnel, no visits counted,
  no notifications sent, four Whisper threads. They read the same broadcast as the live service.
- Every image carries its commit, branch and whether the tree was clean (labels `zailiprotiv.*`); `/stanje.json`
  gives `verzija` and the page's footer shows it. Docker checks each container answers (`docker ps`: healthy).
- All keep Whisper's model in the volume `mikrofon-whisper` (made by the script, `external` in the compose files).
- **Whisper on the graphics card** (`whisper-gpu.ps1`): whisper.cpp's server with the same model on the computer's
  Radeon through Vulkan, at `127.0.0.1:8178`, beside Docker; the live service and the tests send it the sound
  (`WHISPER_URL`, `http://host.docker.internal:8178` in the compose files) and write on the CPU while it does not
  answer (asked again after five minutes). Once: the Vulkan SDK and Visual Studio Build Tools with C++, then

```powershell
.\whisper-gpu.ps1 napravi   # build whisper.cpp at its pinned commit with Vulkan, fetch the two models, checked
.\whisper-gpu.ps1 zakazi    # start it with Windows (the user's Startup folder)
.\whisper-gpu.ps1 pokreni   # now; stanje / zaustavi
```

In Cloudflare (Zero Trust → Networks → Tunnels), the tunnel's public hostname `mikrofon.zailiprotiv.rs` points to
`http://uzivo:8000`. A log line per frame: `name matched | name line | list line -> state`.

While the computer is off, Cloudflare would answer with its own error (530). A worker in front of the hostname
(`edge/`, published by the `worker` workflow) passes every request to the tunnel and, when it fails, shows the site's
page for that instead (zailiprotiv.rs/mikrofon: why it is down, the broadcast, the next sitting, a few facts from the
site). Nothing changes in the tunnel or the DNS.

**Putting a new image live doesn't break the page** (20 Nov 2026): `uzivo` waits for the turn on to end (at most
`-Cekaj` minutes, 10 by default; `-Odmah` at once); during the restart the edge worker gives the page's last answers
(up to two minutes old), and the new run takes up the speaker and the broadcast where the last one was, if its last
frame is under 90 s old (`RESUME_SECONDS`).

When YouTube asks to sign in, put a `cookies.txt` in the volume and set `YTDLP_COOKIES=/data/cookies.txt`; when
yt-dlp stops working, `.\mikrofon.ps1 test -Novo` takes the newest, then `.\mikrofon.ps1 uzivo -Deo merenje`
(yt-dlp runs in the measuring).

The service holds a lock on `/data` (`/data/.pisac`) from its start to its end: a second one on the same volume waits,
and says so in its log every half a minute. `docker exec` commands (`uzivo.popuna` and the like) do not take it, and go
to `mikrofon-merenje-1`: the page's container, `mikrofon-uzivo-1`, cannot write there.

**When the loop of frames stands** 180 s (`docker ps` calls the measuring unhealthy only after 300), the measuring ends
itself and Docker starts it again (`uzivo/cuvar.py`), at most three times in an hour, and never while the day's summary,
a mail or a notification is being made. `docker logs mikrofon-merenje-1` then has a line of `cuvar`: "the loop has stood
180 s; this process ends, 1. of at most 3 in 60 minutes, …; it is at: …" (the place in the code where it stood), or "not
ended" and why, when it did not. The times it did are in `/data/cuvar.json`; while that file cannot be read or written
it ends nothing, and deleting it lets it end again. After three the page stays at 503 until somebody looks; a test
container is not started again (`docker start`). A process put back by Docker has its restart counted: `docker inspect -f
"{{.RestartCount}}" mikrofon-merenje-1`.

One image is both parts, told apart by `ULOGA` (`merenje`, `strana`; empty: one process that is both, `docker-compose.jedan.yml`).

Settings are in `uzivo/config.py`, each overridable from `.env`.

## Code

```
uzivo/
  stream.py     the broadcast: the YouTube address, the HLS segments, a frame each
  ocr.py        the caption's place, its letters, Tesseract's words by line
  caption.py    the two lines; who the name line names (no OCR: tested)
  names.py      both scripts; the site's list of MPs and matching to it (tested)
  state.py      the current speaker and today's turns (tested)
  prenosi.py    the day on YouTube after its broadcast, while the video is public (/data/prenosi/)
  sada.py       the moment and two clocks in /data/sada.json, for the page's own process; one writer of /data (tested)
  citac.py      the same state read from the kept files, for the page's own process (ULOGA=strana; tested)
  merenje.py    the measuring's threads, in the page's process or in its own (ULOGA=merenje); its health check
  cuvar.py      ends the measuring when its loop stands, for Docker to start it again (tested)
  page.py       the page in both scripts (tested)
  worker.py, main.py, config.py
```

The tests are in the repository's `tests/test_live.py` and run with the rest (`uv run pytest -q`); they need none
of the service's packages.

**Visits** are counted as on the site, by Cloudflare Web Analytics (no cookies, totals per page): the page carries
the site's beacon, its token from `data/settings.json` (copied into the image). Set `ANALYTICS_TOKEN=` (empty) in
the environment to leave it out. Opened anywhere but at the project's own hosts the page counts nothing.
