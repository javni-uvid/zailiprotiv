# The live service: how it runs

Decisions about the live page `mikrofon.zailiprotiv.rs` and its service: where it runs, the test and the live image, restarts, when it is down, its secrets and limits, the code's parts. Moved word for word from
`live/AGENTS.md` on 23 Nov 2026 (it had grown to 77 KB, read whole by every agent working in `live/`); what holds now,
in short, is there. **Keep it current:** a decision is added at the end of this file, in the same commit, and one that
changes an earlier one says so. Dates are the maintainer's decisions unless said otherwise.

**Changed since written:** "Test first, then live" (19 Nov): the agent now looks, tests and puts live itself (20 Nov).

- **Not static, so not on GitHub Pages:** a service watches the broadcast. It runs in Docker on the maintainer's
  computer behind a Cloudflare tunnel, because YouTube often refuses data centres' addresses (GitHub's runners
  among them) and a home address works. When the computer is off the page is down; **health** does not ask it.
  The tunnel's token lives in `live/.tunnel.env` (never committed) and in Cloudflare.
- **Test first, then live** (19 Nov 2026, the maintainer's decision): two images. `live/mikrofon.ps1 test` builds
  the working tree as `mikrofon:test` and runs it at `127.0.0.1:8001` (`docker-compose.test.yml`: no tunnel, no
  visits counted, its own data); only after the maintainer has looked at it does `mikrofon.ps1 uzivo` tag that same
  image `mikrofon:uzivo` and run it with the tunnel (`docker-compose.yml`, which never builds); the image it
  replaces stays as `mikrofon:prethodni` (`nazad`). A change to `live/` is never put live without the test.
- **While it is down** (17 Nov 2026): a worker in front of the hostname (`live/edge/`, a route on the zone, published
  by the `worker` workflow) passes every request to the tunnel; on a 5xx (530 when the tunnel is down) it shows the
  site's `mikrofon` page (`pages_mikrofon.py`, noindex) under a `<base>` pointing to zailiprotiv.rs, and the live
  JSON answers `{"radi": false}`. The page says why it is off, links the broadcast and the next sitting, and lists a
  few facts from the site's own counts (laws, urgent procedure, days to adoption, the harsh word said most often),
  each linked to the page with its rule, about no MP in particular.
- **Its tests** (`tests/test_live.py`) cover the names, the caption's lines, the turns and the page, with the
  standard library only; OCR and the stream are tried against the broadcast.
- **The agent tests and puts live itself** (20 Nov 2026, the maintainer's decision; it changes "Test first, then
  live" above, where the maintainer's own look came between the two). The agent that changed `live/` runs
  `mikrofon.ps1 test`, looks at the test page itself (a phone's width, both scripts, what the change was about),
  and after the merge builds the test from the main clone on a clean `origin/main`, looks again and runs
  `mikrofon.ps1 uzivo`; it checks first that nothing but its own change lies between the live image's commit and
  `main` (`mikrofon.ps1 stanje`, `git log <commit>..origin/main -- live/`), and afterwards that the public page
  answers with the change. The maintainer is not asked to run the Docker steps by hand. A principle, DNS or
  anything seen from outside beyond the page itself still waits for the maintainer.
- **A new image put live without a break** (20 Nov 2026, the maintainer's choice of three layers; a blue/green pair
  of services was left out: two would read the same broadcast and write the same files). The restart takes some
  5 s, and finding the stream again 15-30 s more. (1) The edge worker keeps the shared answers on its routes (`/`,
  `/cir/`, `stanje.json`) a second time for two minutes and gives them, marked `x-mikrofon: poslednje`, while the
  service answers 5xx; the site's page for a service that is off only after that. The part an open page asks for
  (`/deo`) is not on the worker's routes (the free plan's requests) and gets Cloudflare's 502 for those seconds,
  which the page's script answers by keeping what it shows; an address with a query (`?fbclid=…`) matches no
  route either and goes straight to the tunnel (checked 20 Nov 2026 by stopping the service at night). (2) The service writes with every
  frame whether a broadcast is on and who is speaking (`state._save`); a new run within `RESUME_SECONDS` (90) of the
  last frame takes that up (`Tracker._resume`), counting the waits for a frame from the restart, so the page does
  not say "no sitting" while the stream is found again, and the same speaker read again is the same turn.
  (3) `mikrofon.ps1 uzivo` waits for the turn on to end (`-Cekaj`, 10 minutes at most; `-Odmah` at once).
- **What goes live is known** (20 Nov 2026, the maintainer's choice; the night before, other agents' worktrees had
  built `mikrofon:test` too, so `uzivo` would have put live whatever was built last). `mikrofon.ps1` passes the
  commit, branch and whether the tree was clean to the build (labels `zailiprotiv.*`, `VERZIJA` in the image:
  `/stanje.json` and the footer show it). A worktree's test is `mikrofon:test-<branch>` on a port and volume of its
  own; `uzivo` runs from the main clone on `main` and takes only an image of a clean `origin/main` (`-Ipak`
  overrides), waits until the new one answers with its commit and puts the one before back if it doesn't in 90 s.
  A Docker healthcheck, `logovi`, `ocisti`, `.env` taken from the main clone, and `mikrofon-whisper` as an external
  volume.
- **A worktree's test goes with the worktree** (20 Nov 2026, the maintainer's request: three tests of merged
  branches had run for hours, 3 GB of memory between them, and nine images of 1.8 GB and as many volumes stayed
  behind, since nothing stopped a test but `uzivo`, and that only the main clone's). `tools/pocisti-projekat.sh`
  removes whatever Docker holds under `mikrofon-test-<branch>` (containers, image, volume) for a branch no
  worktree is on; `osnova/tools/pocisti.sh` runs it after every merge, once the merged worktrees are removed, and
  `mikrofon.ps1 ocisti` by hand. It goes by the name alone, so the slug is computed there as in `mikrofon.ps1`:
  change both together. The main clone's test and the live service are never touched.
- **The maintainer is told when the live page is down during a sitting** (20 Nov 2026, the maintainer's choice of a
  phone notification over an issue). The counter's cron, every five minutes on weekdays 6-19 UTC (`watch`), asks
  the service for `stanje.json` (the edge's copy, `x-mikrofon`, doesn't count as an answer); only when it doesn't
  answer does it read the Assembly's two listings for a sitting marked "(у току)" (at most once in 30 minutes:
  ask the Assembly little). Down in two checks in a row while one is on, the maintainer's devices (table
  `push_admin`) get one notification, and one more when it answers again. A device is put on that list from
  `mikrofon.zailiprotiv.rs/upozorenja?k=<PREPIS_KLJUC>`, which hands its push address to the service, and the
  service to the counter with its token (`/p/admin`). A push carries nothing, so the service worker asks the
  counter which it was (`/p/vrsta`, by its own push address): the watch's for the maintainer's devices, the
  sitting's for everyone else. The Assembly marks a sitting of several days "in progress" on its days off too, so
  a computer turned off on such a day is told about as well.
- **One Cyrillic for both** (20 Nov 2026, from a look at the project's structure): the live page had its own
  letter-by-letter converter and wrote "Цлоудфларе Wеб Аналyтицс", "иПхонеу" and the domain in Cyrillic. It now
  uses the site's (`zailiprotiv.cyrillic.cyr`, copied into the image as `uzivo/cirilica.py`), and both keep a word
  with w, q, x or y whole in Latin (no Serbian word has them), beside the names in `KEEP`. A test renders the
  Cyrillic page and finds no word half in one script.
- **Less work per visitor, nothing hidden in the JSON** (20 Nov 2026, from the same look). With the transcript off
  the page (`SHOW_TRANSCRIPT`), the snapshot no longer reads it: `/stanje.json` had carried the speaker's last
  words and the chair's while the page showed none. A snapshot is computed by one thread at a time, the others
  taking the last one, and one begun before a frame is not kept as newer. `/deo` is drawn once per snapshot and
  sent with an ETag (`no-cache`): a page holding the same part gets a 304; the page asks every 5 s while there is
  a broadcast and every 30 s while there is none (`data-stanje`), so a sitting's start shows within half a minute.
  Every file the service keeps is written beside itself and then moved into place (`state._write`). Checked and
  left as it is: a segment's frame is read once (frames per segment on 18 Nov: median 0.95). In the counter the
  VAPID key and each push service's header are kept as promises, so a batch's 30 sends sign once.
- **`page.py` in parts** (20 Nov 2026, from the same look; the output checked byte for byte the same): the words in
  `texts.py` (`TEXT`, months, weekdays, `_t`, converted once per text), the day's steps in `steps.py` (which are
  shown, and as what; no HTML), the page's own styles and script in `static/live.css` and `static/live.js` (read
  at start beside `mikrofon.css` and `mikrofon.js`, still inline in the page). `page.py` draws the HTML. A text
  key given twice (`play_live`) lost its first, dead value.
- **`state.py` in parts** (20 Nov 2026, the same look; the output checked byte for byte the same): `Tracker` keeps
  the turns, the day files and the resume; it takes three parts as mixins, each in a module of its own, the
  methods moved unchanged: `state_said.Said` (the transcript), `state_chronicle.Chronicle` (the day's steps, the
  agenda's progress, the Assembly's pages read) and `state_view.View` (the snapshot). What they share (the states,
  `counted` and `SURE_FRAMES`, `SAID_LEAD`, `SAID_TAIL`, `_write`) is in `state_base.py`: a test that changes the
  rule patches it there.
- **What a request names never becomes a path or markup** (20 Nov 2026, after CodeQL's first findings in `live/`,
  none of which could be used as the code stood). A day's file is found among the folder's own files (`state._kept`)
  and a font among the fonts' (`main._fonts`), so the check of the address is no longer the only thing between a
  request and the disk. `/upozorenja` writes the key it holds, not the one it was sent, and inside `<script>` a
  `</` is broken. The player's `yt()` and `file()` check what they are given themselves (the next part of a
  recording was played unchecked), and the cards' labels are set as text. **security** now runs on pull
  requests too and on changes under `live/`: a finding used to come after the merge.
- **The service doesn't run as root, and its image is built from named content** (20 Nov 2026, from the security
  review). It reads video from outside with ffmpeg, yt-dlp and tesseract and holds the model's key and the
  notifications' token, on the maintainer's own computer, so a flaw in any of the three was a root shell there.
  - `ulaz.sh`, the image's entry, starts as root only to give `/data` to the user `uzivo` (the volumes were written
    by root until now) and then becomes it (`setpriv`); compose adds `no-new-privileges` and drops every capability
    but the entry's. `docker exec` still enters as root, for looking; a command given to `docker run` runs as `uzivo`,
    so `Dockerfile.analiza` adds its models readable by all.
  - The base images are named by digest (`python`, `deno`, `cloudflared`, which was `latest`), and the packages are
    built at `constraints.txt`'s exact versions: a build next month is today's unless Dependabot's monthly pull
    request moved them. **yt-dlp stays unpinned** as before. **security** checks `constraints.txt` with pip-audit.
  - Not done: a read-only root filesystem (Whisper, tesseract and yt-dlp write where they like; to be tried on a
    day without a sitting).
- **The sound never holds up the picture** (23 Nov 2026, found in a look at the code): the reader fetched each
  segment's sound in the loop that reads the frames, up to three tries of ten seconds when YouTube's sound-only track
  was slow, and the frames meanwhile were skipped (`newest > nxt`). The sound is now taken by a thread of its own
  (`HlsPoller._hear_loop`), in order, with the moment its frame was read; two minutes of it may wait, beyond which
  the oldest is let go.
- **A test has none of the live service's secrets but the page's key** (23 Nov 2026: `env_file: .env` gave every test
  the bucket's keys and the mail's: during a sitting a test left running would have written its own segments over the
  live playlist in R2). `docker-compose.test.yml` empties each by name; `tests/test_live.py` reads the code for what
  looks like a secret and fails when one is not emptied there. A test container started by hand gets no `--env-file`.
- **One way to write a file, one to ask the project's own addresses** (23 Nov 2026, the maintainer's choice among the
  points of an analysis). Writing beside and moving into place was written out four times, and two files were written
  without it (the day of the last notification and the list of MPs): all go through `state_base.write_text` and
  `_write`. The site's files and the counter are asked by `mreza.py`. Left to their own parts: the broadcast, the
  Assembly's pages, Whisper's server, the bucket, the voices' numbers. A made-up day's outputs compared before and
  after: the same.
- **What the tracker is told is kept, to go through a day again** (24 Nov 2026, the maintainer: "uzmi najbolji
  pristup", after ten rules for who speaks went live in a day, each on one to three examples, and the measure
  (`zailiprotiv tacnost`) could score only a finished record: nothing the rules decide from was kept). `dnevnik.py`:
  every call that takes something in (a frame read, a floor given by the chair's words, a voice, the broadcast's
  clock, a piece of the transcript, a step) is a line of `/data/ulazi/<day>.jsonl` with its second, written before
  the call runs, by a wrapper put on in `main.py`; no other part of the service knows of it, and a line that cannot
  be written is never in the call's way. `python -m uzivo.dnevnik <day> <out.json>` tells a new tracker the day's
  lines over again, the clock at each line's second, and writes the record the rules as they now are come to, which
  `zailiprotiv tacnost <day> --zapis` scores once the day's notes are out. Only on the service's computer, never
  served; thirty days kept; `ULAZI_CUVAJ=0` keeps none. Appended a line at a time, unlike the files read back whole
  (a line torn by a stop is skipped). What it cannot show: the voices and the chair's words were found beside the
  tracker as it then was, so a rule that would have made them find something else is not seen. The pictures of the
  captions are not kept (a rule for reading them cannot be tried again yet). **The order of work it serves, the
  maintainer's: no rule for who speaks is changed or put live during a sitting, but for a false claim about a person
  on the page; a rule is told a kept day again and scored before it goes live.** Seen the same day in the frames:
  the broadcast shows a speaker's caption only now and then (some 15 s, minutes apart; none in two stretches of four
  minutes watched), so a turn cannot end where the caption does.
- **The measuring and the page are to be two containers** (25 Nov 2026, the maintainer: "2 da", asked whether to split
  them so that a release of the page does not interrupt the measuring; the day before, restarts had held the day's mail
  back 50 minutes). Of 119 commits since 20 Nov touching the service's code, Dockerfile or requirements, 57 touch only what the page
  will run. The plan, accepted by the conductor, in steps that each leave the service working: (1) what this entry says;
  (2) roles in the code; (3) the test as two; (4) live as two; (5) the one-process form goes.
  - **The cut:** the measuring keeps the frames, the sound, the voices, Whisper, the steps, the model, the bell and every write
    to `/data` but `/data/mejl`; the page has what readers are served, the snapshot's drawing (`state_view` and its helpers,
    which the measuring imports too, each its own version) and the mail. One image, told apart by its role. Not cut
    further: the measuring's parts share one Tracker in memory and write the steps together.
  - **The page reads the kept files**, each written whole, and one new one, `/data/sada.json` (`sada.py`): what was in memory
    only, and two clocks. No HTTP between the two. `citac.Reader` is a Tracker that is told nothing and writes nothing; its
    snapshot equals the tracker's, compared step by step in `tests/test_dva.py`. Who speaks and whether the turn is open
    come from the same file (`dani/<day>.json`), so nobody is shown for another's turn; `sada.json`, up to a second
    behind, may only say that there is no broadcast.
  - **Two clocks, for two faults.** No heartbeat (`t`, every 5 s) for 30 s: the measuring is not there, and the page answers as
    when the service is down. A heartbeat but a loop of frames that stands (yt-dlp hung): the heartbeat has a thread of its
    own and goes on, and the tracker's own `tick`, which ends a turn after 60 s with no frame, is in the loop that stands;
    so the Reader applies that rule itself, from the last frame's time: after 60 s nobody is shown as speaking. With the
    loop's clock (`petlja`) 300 s old the page is not served at all (between sittings one look for a broadcast may ask yt-dlp four times).
  - **One writer, by a lock** (`sada.only_writer`, flock on `/data/.pisac`, taken before anything is read): a second
    measuring on the same volume waits. Tried between two containers on one volume, and with the first killed; on
    Windows (the tests) there is none.
  - **Nothing reads `sada.json` yet:** step 1 changes nothing of what is served. Tried for the later steps: a page with `/data`
    read-only and only the volume's `mejl` subpath writable, and the page's modules, which took 63 MB with both pages and two
    pictures of an empty day drawn and load no model, stream reader or OCR.
- **Two roles in the code** (25 Nov 2026, step 2 of the same plan; live it is still one process). `ULOGA` empty: the page and
  the measuring in one process, as before. `merenje`: `python -m uzivo.merenje`, every thread of the measuring and no web
  server; its check is `python -m uzivo.merenje zdravo`. `strana`: `main.py` with `citac.Reader`, which loads nothing of the measuring.
  - **The page by itself answers 503** on what says who speaks now (the home in both scripts, `/deo`, `/stanje.json`, `/stanje.js`,
    the pictures) while the measuring is not there (`citac.alive`); the days, the summaries and the mail go on. The edge
    and the counter's watch take that as a service that is down, with no change to either; an answer kept by the edge may so stand
    150 s at worst (30 and the edge's 120), where it is 120 in one process. `/zdravlje` says only that the page answers.
  - **The maintainer's mail is asked for by `pretplata.Watch`**, from the kept summary, in whichever process serves the page; until
    now from the model's loop. `obavesti.to_tell` is the one rule of when a summary is told of, the bell's and the mail's.
  - `/stanje.json` has `merenje`, the measuring's commit, beside `verzija`. The live sound's freshness and address come from
    `sada.json`; without the bucket the page serves the playlist from `LISTEN_PATH`, a folder both must then have.
  - Measured: the page 97 MB after 150 pages and pictures of a made-up day of 230 turns and 2,500 pieces (the budget was 150).
- **The test as two, when asked** (25 Nov 2026, step 3): `mikrofon.ps1 test -Dva` runs the tree's test as `merenje` and `uzivo` (the page),
  `docker-compose.test.dva.yml` over the test's own file; plain `test` stays one container, since that is the form `uzivo` puts
  live until step 4, and a test must run what goes live. Same image, names, port, project and volume, so `pocisti-projekat.sh` (it goes
  by the project's label and the names) needed no change. The form that ran before is stopped first: the measuring waits for the lock, and
  the page for a healthy measuring (which makes `/data/mejl` on a new volume), so a one-container test left running would hold
  both. Tried with no broadcast: the page cannot write outside `mejl`, the page replaced while the measuring went on, one form
  and the other in turn.
- **Live as two containers** (25 Nov 2026, step 4; the maintainer on who holds the mail's keys, asked with the page proposed
  and "if it is the same to you I go with the page": "3 stranica, svejedno mi je").
  - **The keys.** The page alone has `MEJL_KLJUC` and `MEJL_UREDNIK`: the measuring runs ffmpeg, yt-dlp and tesseract on video from
    outside, the likeliest way in, and the mail is made of kept files. Against: the page answers the internet; what
    answers there is fixed routes, and it no longer has the model's key or the bucket's, which the measuring alone has. `PUSH_TOKEN`
    (the bell; the mail) and `PREPIS_KLJUC` both. With the token alone the sealed addresses can be fetched, not opened. One `.env`
    as before, emptied by name in `docker-compose.yml`: splitting the file would have secrets moved by hand, and the way back
    needs them all in one place. A test names every secret and whose it is, so a new one fails it until it is placed.
  - **The volume.** The measuring writes `/data`; the page has it read-only, but for the subpath `mejl`. A `cookies.txt` put there for
    yt-dlp would be readable by the page (as in one container, which could write it too).
  - **Memory.** 300 MB at most on the page, so a fault there takes none of the measuring's. None on the measuring: some 300 MB, but
    2.1 GiB once Whisper has written on the CPU, as on 25 Nov at 10:07, when the card did not answer once and the model
    stayed loaded. The plan's 318 MB for the whole service was a reading before that.
  - **Releases by part** (`mikrofon.ps1 uzivo -Deo strana|merenje|oba`, the page when none is named), each part with its image before kept.
    `nazad` must be told which part: with two, going back by habit could take the wrong one. Parts of two formats
    (`state_base.FORMAT`) go only together, and a page that meets another format serves nothing of the moment rather than misread it.
    `uzivo -Jedan` releases as one while live is one. A test container is two by default, as what goes live is; `-Jedan` one.
  - **The measuring's check asks for its own commit:** `sada.json` of the run before is fresh for half a minute, so a new
    measuring that dies at once would have passed for a healthy one, and would not have been put back.
  - **The switch** stops the old container first: the new measuring would wait for its lock and the page for a healthy measuring. It
    undoes itself when either does not answer in 90 s. `docker-compose.jedan.yml` is the form before, kept until step 5.
  - **Tried** on a renamed copy of the script and the compose files (another project, port, volume and images, the tunnel a
    sleeping container), on a live broadcast, asking the page four times a second. Without an answer: to two 9 s; the page
    released 1 s, the measuring 0 (the page goes on); both 1 s; back to one 1 s; one container released as before 1.5 s. A page or a
    measuring that fails at its start was put back after 90 s by itself (the measuring's: the page answered 200 for 30 s and 503
    for 64), and so was a switch that failed (93 s without an answer, under the edge's 120). Formats that differ refused, a page
    released while the measuring is down, a request of 25 s under way ended before its page was replaced, the tunnel
    never restarted. As two on the rebroadcast of the sitting of 25 Nov: captions, steps, the live sound without a bucket; the
    measuring killed or paused, 503 after 30 s and 200 within 2 s of its return.
  - **Not tried:** the mail really sent from the page's container (a test has no keys); the bucket's live sound with two (the
    page takes its address from `sada.json`); a name read from a caption on a live broadcast (the rebroadcast's
    captions were covered), which `tests/test_dva.py` compares step by step instead; a whole sitting.
