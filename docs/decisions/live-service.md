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
