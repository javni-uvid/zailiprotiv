# AGENTS.md for `live/`: "Ko sada govori"

The decisions about the live page `mikrofon.zailiprotiv.rs` and the service behind it. It continues the repository's
`AGENTS.md` (how to work, the principles, where each part's decisions are), which is read first;
`docs/decisions/recordings.md` has what the site makes of the service's records and of the recordings; `README.md`
here says how the service works. **Keep it current** in the same way: a decision about `live/` is added at the end
of this file, in the same commit. Dates are the maintainer's decisions unless said otherwise.

- **A page of its own at `mikrofon.zailiprotiv.rs`** (17 Nov 2026): who is speaking in the Assembly now, and who spoke
  today, read from the caption under the speaker in the live broadcast (README in `live/`). It grew out of the
  maintainer's page following one speaker; under the project it follows **every speaker by one rule** (principle
  1): nobody is followed, singled out or ranked; today's turns are listed by time.
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
- **Read from the broadcast, matched to the roll calls:** a name counts when it matches an MP on the site's list
  (`podaci.json`, from the roll calls) on the caption's name line only, never the list line under it (a list's name
  often holds its leader's name). A name not on the list (ministers, guests) is shown only when read surely in two
  frames in a row; a half-read name is never shown. The page says it is read automatically and may err.
- **Visits counted as on the site** (18 Nov 2026, the maintainer's decision, once the page became the site's main way
  in): the live page carries the site's Cloudflare Web Analytics beacon (principle 5's first exception), its token
  read from `data/settings.json` copied into the image (`config.ANALYTICS_TOKEN`; `ANALYTICS_TOKEN=` empty turns it
  off); the footer says so. Until then only the site's page shown while the service is down was counted.
- **Nothing from elsewhere** (principle 5): the fonts are copied from `src/zailiprotiv/static/fonts` into the image,
  the one script is inline; the site's MP pages are linked.
- **Its tests** (`tests/test_live.py`) cover the names, the caption's lines, the turns and the page, with the
  standard library only; OCR and the stream are tried against the broadcast.
- **The speaker's box** (19 Nov 2026, the maintainer's request: the box under the speaker was unclear, the page should
  draw visitors in). In this order: the MP's portrait from the Assembly's site (when the site has one), the name, the
  list, a clock that ticks in the browser from the turn's start and "longer than N% of today's turns" (from five
  finished turns on, shown from 50%); then **today first** (which turn of theirs, their time today, their place by
  time among today's speakers) and the convocation (the site's days read from recordings plus today), computed by
  `state._today` by one rule for all; then one line about the MP at a time, changing every 15 s or on a tap, **each
  labelled with where it is from** ("sazivi 13–14", "sajt Skupštine"), so that a number from an earlier convocation
  is never read as this one's. The lines are the MP's card facts as plain sentences (`pages_mikrofon.speakers`,
  published as `mikrofon-poslanici.json`, read hourly), one whole quote with its date when the profile has a checked
  one (at most 240 characters, never cut), and for everyone place, year of birth and **occupation** as the Assembly's
  own page of the MP states it (`members.occupation`, read once per MP in `members`). Nothing about private life.
  The card's wording no longer assumes a gender ("% prisustva", "glas drugačiji"). Under the box: the way to the
  MP's page and "Podeli ovaj trenutak", which draws a picture in the browser (name, list, minutes so far, the
  address; nothing is sent to us) and hands it to the phone's share sheet, or downloads it and copies the text.
  Below, the day: **time by list** as one bar (**in the list's colour**, 19 Nov 2026, the maintainer's decision and an exception, on this page only, to
  "colour only for za and protiv": `page.LIST_COLOURS`, blue for "Aleksandar Vučić - Srbija pobeđuje", red for
  "Studentska lista", green for the smaller lists together, hues apart from the two vote colours and checked for
  colour-blind readers in both themes; a list with no colour of its own keeps a shade of grey, and the key always
  names each; the day's strip and the bars per speaker wear the same colours; sitting MPs of smaller lists or no
  group together, the Government and guests hatched; a list is taken from the caption only when the site names it,
  so a misread makes no list), **the day as a strip** (a block a turn, a click leads to it in the list), and the
  totals per speaker with the list under each name, the current turn included. One sentence on top says what the
  page is and links the site, for those who arrive from a shared picture.
- **The day in one sentence, the summary on a break, the link's picture** (19 Nov 2026, the maintainer's choice among
  proposals drawn from debate clocks of NPR, NBC and CNN). `page.headline`: the speaker with the most time today,
  their time, and the largest other list whose speakers together had less, or else their share of all the time; one
  rule whoever leads, no gendered verb, from two speakers on. Shown above the day's bars; while nobody is on (a break,
  or between sittings) it stands in the speaker's place with the three longest and "Podeli presek dana". The picture
  (`picture.py`, `/slika.png` and `/cir/slika.png`, 1200×630, Pillow with the image's DejaVu fonts) shows who is on
  and since when, or that sentence, over the day's time by list; it is the page's `og:image` (with `og:title` and
  `og:description` saying the same; `PUBLIC_URL` must be set), drawn at most once in 20 s and kept as long by
  Cloudflare. Its address carries the turn's start, since some services keep a picture by its address; X keeps a
  link's card for days whatever we do. On the site, `govornici.html` has **"Po danima"** (`pages_govornici.trend`):
  per list and day, the number of turns, their mean length and sum, the four lists with the most time and the rest
  together.
- **What is being said, the day in numbers and cards, the broadcast on the page** (19 Nov 2026, the maintainer's
  choices after a look at skupstina.live; its chat, muting and model-written summaries were left out).
  **Automatic transcript** (`live/uzivo/prepis.py`): each segment read for its frame leaves its sound (16 kHz), a
  thread gives the sound to the turn it falls in and has Whisper (faster-whisper on the maintainer's CPU,
  `WHISPER_MODEL`, `large-v3-turbo`, the one model since 20 Nov 2026, empty for off; the model is kept in `/data/hf`) write it down about a minute
  at a time while the speaker is on, the rest when the turn ends; turns under 20 s and sound in no turn (the chair)
  are thrown away unread. The text is kept per day (`/data/prepis/<day>.json`, `Tracker.say`), shown with the speaker
  as its last 400 characters and whole at `/prepis` (and `/cir/prepis`), always labelled automatic, may err, **not a
  quote**; nothing is summed up or reworded by a model (principle 6 stays: the site quotes the notes). The page's
  changing part carries only the tail and word counts, so it stays small. **Four numbers** of the day above the
  bars (time, turns, speakers, words written down). **"Dan u karticama"**: the day in cards to tap through, each by
  a rule (whole time, most time, time by list, longest turn, most turns from three on, the way to the site).
  **The broadcast is on the page while a sitting is on**, YouTube's player in its no-cookie mode, playing when
  pressed. Since the evening of 19 Nov 2026 (the maintainer's decision, point 4 of the analysis of how long visits
  last: 86% of them on phones, and no way to see whether anyone plays it) it is behind a **facade**: our own picture
  of the moment (`/slika.png`) with "▶ Gledaj prenos", and only the press loads YouTube's player, playing, so
  principle 5's "only on a click" holds again on this page. The press adds one to the counter's sum of the day
  (`mikrofon.pusti`, `POST /e`; the counter takes uses from `mikrofon.zailiprotiv.rs` too, only `mikrofon.` ones;
  the service reads `votes_api` from `data/settings.json`, `VOTES_API=` empty turns it off). The archive's
  recordings load on a click as before. **The site's live bar names the speaker** and since when (`site.js` reads the service's
  `stanje.js` every half a minute while the bar is on the page).
- **A name with nothing under it** (19 Nov 2026): the live page listed two turns of an MP who had not spoken, each
  read in two frames with no second line. `state.counted`: a turn goes into the day's list when read in two frames
  or more and either the line under the name (the list or office, which every real caption has) was read at least
  once, or it lasted four frames or more; the day's record gives a turn not counted as one frame, which the site
  drops. The same rule for every name.
- **A notice on top of the live page** (19 Nov 2026, the maintainer's request: the Speaker's election). What the
  Assembly has decided is written by hand into `data/obavestenja.json` (a sentence of fact as the Assembly's site
  says it, its source's address, the days it stands, the MP's page), published in `mikrofon-cekanje.json` and shown
  above the speaker from "od" until "do"; the service reads it with the hour's fetch, so a new notice needs no
  rebuild. No comment and nothing the source does not say.
- **"Šta se desilo danas"** (19 Nov 2026, the maintainer's decision; `live/uzivo/hronika.py`). The chair has no
  caption, so the chair's sound used to be thrown away; now sound in no turn, once 45 s old (no turn begins
  there), is written down too, never shown as anyone's speech, and searched with every other piece for the set
  phrases of the procedure (`hronika.RULES`: an agenda item, a debate opened or closed, a vote, a break, a measure,
  what the chair "konstatuje"): each hit is a line of the day with the sentence it was found in. A second source,
  named beside its lines: the sitting's page at the Assembly (`sednice` in `mikrofon-cekanje.json`), read every ten
  minutes while a broadcast is on, each sentence new since the last reading a line in the Assembly's words (the
  first reading is the start, not news). The notices and that list are fetched every ten minutes as well. Nothing
  is summed up; a line from the transcript points at the moment and is no result (Whisper errs in names and
  numbers), which the page says. Kept per day in `/data/hronika/`.
- **The agenda under the broadcast** (19 Nov 2026, the maintainer's request). The sitting's agenda as the Assembly
  lists it (`dnevni_red` in `mikrofon-cekanje.json`, `pages_mikrofon.agenda`), folded to one line: how many items
  are done and which is on or next. An item is done when the Assembly's page of the sitting says so, written by
  hand into `data/<N>/tacke.json` with the day and a sentence of what was decided, or when the chair moves to a
  later item, heard in the automatic transcript (`hronika.item_no`, kept in `/data/tacka.json`; a number the agenda
  does not have is taken as misheard). Each state names its source, and the note under the list says the second
  may err. What the reader opened stays open when the page's changing part is replaced.
- **Chance readings during a break** (19 Nov 2026: one MP's name kept flashing as the speaker while nobody was on
  the screen). Two causes, both mended. In `names.Roster` one word read could stand for two words of a name
  ("Сара" was both "Sarag" and "Sarah"): each word of the name now needs a word of its own (`_pair`). And in
  `Tracker.observe` a name with no line read under it, like a name not on the list, is taken only on its second
  frame in a row (within `HOLD_SECONDS`), the turn then counted from the first of the two; a whole caption, with its
  list or office, is taken at once as before.
- **Corrections to the automatic transcript: first out, then corrected** (19 Nov 2026, the maintainer's decision).
  Before a piece Whisper is told the Assembly's set terms and today's speakers' names (`prepis.Writer.hint_for`, as
  the model's `initial_prompt`). The text is kept as written; what is shown is that text with the corrections
  (`live/uzivo/ispravke.py`, applied when shown, so a new correction mends what is already out): the site's list
  `data/prepis-ispravke.json` (as Whisper writes it → as it is written, whole words; published as `ispravke`), and a
  sitting MP's name written without its diacritics, in any case, gets them. Only spellings: nothing is reworded, no
  model rewrites it, and a word a letter away from a name is left for the list. Each speech on `/prepis` has
  "Prijavi grešku u prepisu" (a letter to the site's address, filled in with the speaker and the time); what the
  maintainer accepts goes into the list. A finished turn can be read again by a better model and shown in place of
  the first reading, marked as such (`WHISPER_FINAL_MODEL`, off by default: it runs only while the first reading
  has nothing to do, and still keeps the computer busy long after a sitting). When the Assembly's notes of the day
  come, they are what the site quotes; the transcript stays with the recording as what it is.
- **The chair's words are shown too, as no one's by name** (19 Nov 2026, the maintainer's remark that the transcript
  stops while the chair speaks). Sound in no turn is written down in shorter pieces (`CHAIR_PIECE`, after
  `CHAIR_WAIT`), kept apart in the day's record (keys `p<second>`), shown under "Bez potpisa: predsedavajući ili
  sala" while nobody's caption is on (snapshot `bez_potpisa`) and on `/prepis` in its place in time. It is never put
  to an MP, never counted in anyone's time, and the day's steps are still read from it.
- **The transcript is written down but not shown** (19 Nov 2026, the maintainer's decision: it errs too much and
  does more harm than good). `PREPIS_PRIKAZ=1` shows it again (`config.SHOW_TRANSCRIPT`); off, the page has no
  "Šta govori", no "Bez potpisa", no words tile, no links to `/prepis`, and `/prepis` leads back to the page. The
  writing goes on: the day's steps and the agenda's progress are read from it.
  With it off, `/prepis?k=<PREPIS_KLJUC>` still shows it to whoever has the key from `live/.env` (the maintainer,
  to see what is being written down): at least 12 characters, answered with no-store and no referrer; without the
  key the address leads back to the page.
- **"Šta se desilo danas" never shows the transcript's wording** (`page.steps_shown`). A step heard in the chair's
  words is our own short line for its kind (`STEP_TITLES`: "Rad je nastavljen", "Pauza"…), a move to an agenda item
  with its number and the item as the agenda writes it; a step with nothing sure to say (an item with no number or
  one the agenda lacks, "konstatujem da…") is left out, and the same step within a quarter of an hour is one line.
  The Assembly's own sentences from the sitting's page are shown whole, with the link. Drawn as a line of time: a
  ring for what was heard (automatic, may err), a full dot for what the Assembly wrote; the key is under the list.
  A line from the Assembly's page carries the time we first read it there, not the time of the event (the page is
  read every ten minutes and the Assembly writes after the fact), so it is marked "Zvanično", its hour says
  "objava", and the line says the event was earlier (19 Nov 2026: the Speaker's election stood after the move to
  the next item).
- **The speakers' sound is written down too, and a heard step is shown only when something else bears it out**
  (19 Nov 2026, the maintainer's decision). For a few hours only the chair's sound was written down, so that a
  slower model (`WHISPER_MODEL=large-v3-turbo`, about real time on the maintainer's computer) kept up; the same
  evening the maintainer asked for the MPs' speeches to be kept as well. Now everything is written down and kept
  (off the page, as above), the chair's sound first (`prepis.choose`), so the day's steps keep up while the
  speakers' waits; the computer may fall behind during a sitting and catch up after. `PREPIS_SAMO_PREDSEDAVAJUCI=1`
  (`config.CHAIR_ONLY`) writes only the chair's again, with the second reading off. `page.steps_shown` shows a step
  from the chair's words only when confirmed: an agenda item the agenda has, with a higher number than the last
  heard; a break or the day's end when nobody is at the rostrum for `STEP_QUIET` after it; work resumed after a
  shown break, before anyone spoke, or (once) after ten minutes with nobody at the rostrum (`STEP_IDLE`: a break
  need not have been heard); a vote or a debate's opening or closing while an agenda item is under way. A kept
  step is checked against today's rules again when shown, so a mended rule also clears what it had found.
  Measures and anything else wait for the Assembly's page. Next, once a day of this has been looked at: a model
  over an API as a judge of the chair's words (a step's kind from the set list, the item's number, till when the
  break is), never as the writer of what the page says.
- **"Reč ima: …" from the chair's words, while the picture names nobody** (19 Nov 2026: that afternoon the
  broadcast showed no captions at all, the frame checked). `hronika.floor`: after "reč ima" / "ima reč" the next
  seven words must name one sitting MP: every word of the name whole but for diacritics, or, as a guess the
  maintainer allowed after that phrase, the clearly nearest MP by every word of the name (`FLOOR_NEAR`,
  `FLOOR_CLEAR`; "Jova Bakič", "Krko Babić"), or a surname alone that only one MP has, right after a title
  ("kolega Jovanov") and never after a given name we do not know. Two MPs fitting: nobody. Shown in the day's steps as a lighter line with a link to the MP's page, and not where a turn read from
  the picture stands. No time at the rostrum is counted from it (the end of the speech is not known), and nobody
  is ever named from a face.
- **Trying another Whisper model** without touching the service: `python -m uzivo.proba <model> [seconds]` in the
  container (`live/uzivo/proba.py`) listens to the kept sound, writes it down with the running model and the named
  one, and prints the time and the text of each. It shares the processor with the service while it runs.
- **The live page for a keyboard and a screen reader** (20 Nov 2026, after the same look the site had). The page's
  part is replaced whole every five seconds, which took the keyboard's place away each time: the thing that had
  the focus (the same kind, the same one in order) has it again after the replacement. A line outside that part
  (`#ko`, `aria-live`, not shown) says the new speaker's name and list once when they change. "Dan u karticama"
  opens onto its close button, gives the focus back, and does not turn its cards by the clock for a reader who
  asked for less motion. No letters under 12 px; the "next line" button is 32 px high. The archive is named
  "Videonet", not by its address, which the Cyrillic page wrote in Cyrillic letters.
- **The agent tests and puts live itself** (20 Nov 2026, the maintainer's decision; it changes "Test first, then
  live" above, where the maintainer's own look came between the two). The agent that changed `live/` runs
  `mikrofon.ps1 test`, looks at the test page itself (a phone's width, both scripts, what the change was about),
  and after the merge builds the test from the main clone on a clean `origin/main`, looks again and runs
  `mikrofon.ps1 uzivo`; it checks first that nothing but its own change lies between the live image's commit and
  `main` (`mikrofon.ps1 stanje`, `git log <commit>..origin/main -- live/`), and afterwards that the public page
  answers with the change. The maintainer is not asked to run the Docker steps by hand. A principle, DNS or
  anything seen from outside beyond the page itself still waits for the maintainer.
- **Keeping visitors longer** (20 Nov 2026, the maintainer's choice of points 1, 3 and 4 of a plan drawn from the
  visits: 5.2 min a visit, 2.7 min at the peaks, when most arrive from a shared link). On a phone the head is short,
  so the broadcast is in the first screen; the page can go on a phone's home screen (a manifest, icons drawn from
  its microphone, the browser's own offer shown as our button, nothing else installed); between sittings the next
  sitting convened is counted down with its agenda (`page.countdown`; `pages_mikrofon.upcoming` adds the newest
  convocation's sittings, and `waiting` takes the first convened for today or later). The counter adds
  `mikrofon.ekran`, `dodaj`, `dodato` and `sledeca`; the footer and the method page say so. Measured over a full
  sitting day before the next points (the broadcast's ▶ pressed against pages opened, time in view). The other
  points (the tab's title, a vote on the item under way, "Pogodi", the day played, a way to the site from the box)
  were declined by the maintainer the same night.
- **A notification when a sitting begins** (20 Nov 2026, the maintainer's choice: only the broadcast's beginning,
  the addresses kept by the counter). "Obavesti me kad sednica počne" under the speaker's box asks the browser,
  registers the page's service worker (`/sw.js`, `page.service_worker`: it shows the notification and opens the
  page, and handles no requests) and sends the browser's push address to the counter (`POST /p`, from
  `mikrofon.` only, the table `push`; "Isključi" sends `/p/odjava`). The live service (`obavesti.Bell`), after three
  frames of a live broadcast in a row between 7 and 22 h, asks the counter once a day to send (`POST /p/salji` with
  the token `PUSH_TOKEN`, in `live/.env` and GitHub Secrets; the test's is empty); the counter keeps the day
  (`push_days`), sends a push with no content signed with the VAPID key (secret `VAPID_JWK`, its public half
  `push_key` in `data/settings.json`) to 30 addresses a call, its free plan's limit, forgets addresses the push
  service says are gone, and the service asks for the next 30 until none is left. On an iPhone it works once the
  page is on the home screen, which the page says. `GET /pregled` gives the number of addresses and what each day
  sent; `mikrofon.obavesti` and `odjavi` are counted as uses.
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
- **The chair gives the floor in more words than "reč ima"** (20 Nov 2026, the maintainer's request): Whisper writes
  it as one word ("Rečima narodna poslanica …"), and the chair also says "dajem reč", "pravo na repliku ima", or a
  title after "replika", "povreda Poslovnika", "izvolite", "sledeći je" (`hronika._FLOOR`); "replika gospodinu X"
  names whom it answers and is not taken.
- **The live page on the site's scale, its earlier turns folded** (20 Nov 2026, the maintainer's choice, with the
  same points for the site, after a look at the design). The page had twenty sizes of letters, a third of the text
  in 14.4 px grey; it now uses the site's eight steps (`--t-1` … `--t-8` and three for titles, in `page.CSS` and
  the shared `mikrofon.css`; a test checks that no other size is written). Between sittings half of a phone's ten
  screens was the list of the day's turns: the latest eight stand (`page.TURNS_SHOWN`), the earlier ones are folded
  under them and open by themselves when the day's strip or an address leads to one. Left as it is: the day's
  four numbers have nothing beside them to compare with (the service has no other day's sums; the sentence above
  them and the speaker's clock already compare).
- **The day's steps follow the order of the Assembly's work** (20 Nov 2026, the maintainer's request: "a vote
  cannot be closed before it began"). Within an agenda item (`page._in_order`): the debate is opened once and before
  it is closed (an item taken up with "nastavljamo pretres" counts as opened); a vote is closed only after one was
  put, and "put to the vote" while one is open is that vote (19 Nov: the roll call after the decision to vote by
  roll call); steps said in the same second are taken as an item, then its debate, then its vote (`_PHASE`). These
  steps are no longer cut to one a quarter of an hour: three votes in five minutes (19 Nov, 22:19–22:24) are three.
  A vote's result closes it ("za je glasalo", "glasalo je 97", "dobio je … glasova"), and "pristupili glasanju" in
  a result no longer reads as a vote begun; a kept step is shown under the name today's rules give it.
- **One Cyrillic for both** (20 Nov 2026, from a look at the project's structure): the live page had its own
  letter-by-letter converter and wrote "Цлоудфларе Wеб Аналyтицс", "иПхонеу" and the domain in Cyrillic. It now
  uses the site's (`zailiprotiv.cyrillic.cyr`, copied into the image as `uzivo/cirilica.py`), and both keep a word
  with w, q, x or y whole in Latin (no Serbian word has them), beside the names in `KEEP`. A test renders the
  Cyrillic page and finds no word half in one script.
- **The first list's colour is indigo** (20 Nov 2026, with the site: its blue stood too near the blue of "za" on
  the home page, and the two pages wear the same hues): `--c-av` and `page.HEX["c-av"]` are #3730a3 (#818cf8 in
  the dark theme); the pictures take it from `HEX`.
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
- **The model tells the day's steps and sums the day up** (20 Nov 2026, the maintainer's decision, after a trial on
  19 Nov read with Haiku: every break, election and result of the day found, the rules none of them, and 14 of the
  rules' 19 agenda items false; `C:\Users\marko\zailiprotiv-snimak\haiku-19\izvestaj.md`). It ends "nothing summed
  up or reworded by a model" and "a model as a judge, never the writer" above. `sudija.Judge` (`sudija.py`), started
  when `ANTHROPIC_API_KEY` is in `live/.env` (`config.MODEL_KEY`; the test has none unless `TEST_ANTHROPIC_API_KEY`
  is given), sends Claude Haiku (`HAIKU_MODEL`, `claude-haiku-5-5`) every ten minutes the transcript's pieces written
  since the last call, under the speakers' names, with the set list of the procedure's steps (`sudija.EVENTS`;
  a warning is no measure). A step is kept only when its sentence is in those pieces word for word
  (`check_events`), as a line of the day with `"izvor": "model"` and what it read besides (`vise`: the item's
  number, to whom, who was elected, the result, how long). With a model step today, `steps.model_steps` shows the
  model's steps and the Assembly's page, of the rules' steps only "Reč ima" (named by the list); a break or the
  day's end still waits for nobody at the rostrum, an item must be on the agenda and after the last, and a figure
  or a name the model read is shown only when the sentence holds it (`_borne`). No model step: the rules as before.
  At a break the model found (quiet for `STEP_QUIET`) the stretch since the last is summed up (`SUMMARY`), and with
  no broadcast for `END_QUIET` (20 min) the day (`DAY`) from the stretches: only what was said; no tone or verdict of
  the model's own, the speaker's own words kept as said, harsh ones too (the maintainer, 20 Nov 2026); no quotes;
  every speaker with two minutes or more, one line each, in the order they first spoke; numbers only as said; a
  misheard MP's name as the list writes it. A summary naming a speaker not of the stretch or a number not in the text
  is asked once more with what was wrong, then left out (`check_summary`). Kept in `/data/sazetak/<day>.json`;
  `/sazetak?k=<PREPIS_KLJUC>` shows it to the maintainer, and with `SAZETAK_PRIKAZ=1` it is on the page while nobody
  is on (`page.summary_box`, labelled: written by a model from the automatic transcript, may err in names and
  numbers, no quote, the notes are the source once published) and at `/sazetak/<day>.json`. The site takes that file
  in each hour (`uzivo.summary`, in `uzivo-pull`: today's and yesterday's, never one with the day's summary replaced
  by one without) into `data/<N>/sazetak/<day>.json`, and `govornici/<date>` opens with "Sažetak dana" (decisions,
  the paragraph, who spoke about what folded, the same label). Once the day's summary is on the page, the
  subscribers of the sitting's notification are told (`obavesti.Bell.summary`, the counter's `/p/salji` with
  `"vrsta": "sazetak"`, kept as `s:<day>` in `push_days`, once a day; the service worker writes "Sažetak dana je
  spreman"), only between 7 and 22 h and while the summary is under half a day old, so a day ended at midnight is
  told in the morning. A day ending after midnight is still summed up (`Judge.step`). E-mail may come later.
- **A vote in the summary adds up, and is told one way** (21 Nov 2026, the maintainer's request: the figures of a
  vote must make sense, for + against + abstained equal to those who voted, and the summary look right on the page).
  A step of the summary that reports a vote carries it as `glasanje` (`za`, `protiv`, `uzdrzano`, `nevazece`,
  `nije_glasalo`, `glasalo`, `prisutno`; only what was said, the rest null) and has no figures of votes in its words
  (`sudija.SUMMARY` rule 10, `DAY` rule 8; the day takes the votes from the stretches' summaries unchanged).
  `sudija.vote_errors` checks what was said: za + protiv + uzdržano (+ nevažeći) = glasalo, glasalo + nije glasalo =
  prisutno, no part above its whole (nothing is guessed when a figure was not said). A summary with a vote that
  fails is asked once more with what was wrong; after that (`settle_votes`) the vote goes without its figures and
  the step stays, or is dropped when its own words carry the figures: better a missing line than a wrong one. A vote
  that adds up gets `glasovi`, one line of words made by the code ("za 136, protiv 0, uzdržano 0, glasalo 136, nije
  glasalo 98, prisutno 234"), shown under its step on the live page and on the site's day page; the figures are never
  re-worded by the model. The live page's summary box had no style: it has one now, and shows the latest stretch's
  steps (`tok`) as well as the day's decisions.
- **What the Assembly wrote stands under the line of time, not on it** (20 Nov 2026, the maintainer: "ne sviđa mi
  se kako se zvanično meša sa drugim tačkama reda"; it changes the 'marked "Zvanično"' of "never shows the
  transcript's wording" above). On 19 Nov eleven of the Assembly's sentences stood on the line at 23:56, the minute
  we read them, among the steps of 23:50-23:57: paragraphs between one-line steps, telling again, hours late, what
  the line already had at its own hour. The line of time now holds only what was heard. The Assembly's sentences
  are in the same box (the maintainer: not too many separate blocks), folded under the line as "Šta je Skupština
  zapisala o ovom danu (N)": whole and word for word, in the order they stood, with one line saying where they are
  from, until when they were read, and that the Assembly writes after the event; open when nothing was heard.
  The mark "Zvanično", the hour's "objava" and the full dot with its key are gone. Not done yet: the same
  sentences in the day's mail and summary (the maintainer's other thought).
- **A step's line leads to what the Rules of Procedure say of it** (20 Nov 2026, the maintainer's choice, the Rules'
  step 4): `steps.STEP_TERM` gives each kind of step a term of `data/poslovnik/pojmovi.json`, and the line's name
  links `<site>[cir/]poslovnik-clanovi#pojam-<id>` (the sitting opened: the quorum, art. 88; work, a break, the
  day's end: 87 and 101; an agenda item: 92 and 93; a debate opened or closed: 96 and 98; a vote and its result: 87
  and 160; a measure: 108 to 114). "Reč ima" and an election have none. The lead under the heading says so. A test
  holds every term named to one the site explains. The order kept (`_in_order`) names the articles it rests on; the
  page never says a sitting broke the Rules.
- **"Sednica po Poslovniku" always on the page** (20 Nov 2026, the maintainer: the new convocation's readers will want
  the Rules): a box above the link to the site, between sittings too, leads to the terms on the site's page of the
  Rules (`rules_cta`, `rules_sub`); the steps' own links are as above.
- **"Dan u karticama" tells what happened before who spoke** (20 Nov 2026, the maintainer: the cards are to be
  made better and wider with what we now have from the different sources, the finished items that matter among
  it). The six cards told only the rostrum's time. After the first card now come, each from one source and saying
  which: the model's sentence of the day (`sazetak.kratko`, "napisao model … nije citat"); a card for each agenda
  item the sitting's page has as finished that day, with its sentence of fact (`data/<N>/tacke.json`; three at
  most, the rest as a list); the chair's measures among the day's shown steps, counted by kind and without names
  (heard automatically; the names wait for the stenographic notes); then the rostrum's cards as they were; "Šta
  sledi" (the Assembly's newest notice and the agenda's next item); and the last card also leads to the site's
  page of that day once the day is over. A card with a text stays longer (six seconds and one for every 22
  letters, 16 at most; `data-t`). Not on the cards: sentences from the automatic transcript as an MP's words
  (principle 6: a quote is word for word and checked against the notes, and the transcript errs); the way to
  the transcript is the day's page, where each is marked automatic.
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
- **Between sittings the notification's offer stands above the day** (20 Nov 2026, the maintainer's choice of three
  points drawn from the first week's visits: some 47,000 visits on the two sitting days, one device asking for the
  notification). "Obavesti me kad sednica počne" and "Dodaj na početni ekran" stood under the speaker's box, which
  between sittings is the last day's box with its summary, half a phone's screens down. With no broadcast
  (`nema_prenosa`) they now stand above that box, under the notice and the agenda; while a broadcast is on, under
  the speaker's box as before. The day's three with the most time in that box lead to their pages on the site, as
  the day's totals already did.
- **The notification's offer is counted step by step** (20 Nov 2026, the maintainer's choice; one device had
  asked after some 47,000 visits). Besides `mikrofon.obavesti` (turned on), once per page: `obavesti-moze` (the
  offer shown: the browser can push and this one has not asked yet), `obavesti-klik` (pressed), `obavesti-odbijeno`
  (the browser's question answered no or closed), `obavesti-greska` (failed on the way). So it can be seen whether
  people do not find the button, or refuse the browser's question.
- **The title says what people search for** (22 Nov 2026, the maintainer's decision): "Skupština uživo: ko sada
  govori", and the description begins "Prenos Narodne skupštine uživo". Google showed the page mostly to those who
  knew its name (14-20 Nov: "mikrofon za ili protiv" 129 times, "ko govori u skupstini" 20, "skupština uživo" and
  "prenos skupštine" not at all), while the page was already indexed and the site's most clicked (516 clicks a
  week of 982). Read the change in `visits` with search=true from early December.
- **The day is one list, and where a thing is from is a label** (22 Nov 2026, the maintainer's choice of points 1
  and 2 of a look at the page: the visits of 20 Nov, 2,055 pages opened, 83% gone before a minute in view; the page
  nine phone screens long between sittings, half its words in 13-14 px). It changes "What the Assembly wrote stands
  under the line of time" and the model's summary on the page above. The same day was told three times: the
  summary's decisions and paragraph, the line of steps, the Assembly's sentences folded under it. Now "Šta se
  desilo" (`page._steps`) is one list, newest first: what was decided (the day summary's decisions with a vote's
  figures under them once it is written, else the steps that report an election or a result), the moves to an
  agenda item, breaks and the day's end, and the chair's measures as one line counted by kind, without names. The
  steps that only say the work moved on (a debate opened or closed, a vote put; `page._MINOR`), the floor given, and
  each measure with what was heard of it are among all the steps, folded with their links to the Rules. The model's
  paragraph is not shown (it stays on the site's day page and in the cards' one sentence). The Assembly's sentences
  are not told a second time: its sentence per finished item is in the agenda (`tacke.json`), and its page of the
  sitting is linked under the list; only when nothing was heard are its sentences the list. The long notes on how a
  thing is computed are labels beside the heading that open to the sentence on a tap (`page._chip`: the day's list,
  the day read from the recording, the agenda); "Kako ovo radi" is folded; the notes that principle 5 wants on the
  page (the player and the archive load on a click, what a notification keeps, what is counted) stay, each in one
  short sentence, the method page saying the rest. A list of up to 11 lines is shown whole, a longer one folds
  after 8. Next: the first screen, the rows that open, colour.
- **The first screen says what is now; every row that opens is one kind of row** (22 Nov 2026, the maintainer's
  choice of point 3 of the same look, and their remark that the "+" was too small on a phone). The box under the
  title with its line of text and the black bar to the site is gone (the site's links stay lower on the page); the
  title stays (the search words, above). Under it one line (`page._status`): "Uživo" while the broadcast is on, "Ne
  zaseda" while it is not, and the agenda's item under way or next; the sentence "Skupština sada ne zaseda" is gone
  with it. The order (`live.css`, `order`): during a sitting the line, the notice, the broadcast, the speaker, the
  day's list, the agenda, the day in numbers; between sittings the line, the notice, when it goes on and the
  notification, the last day's list, the agenda, the recording, who spoke. The agenda stands open (of 2,055 pages
  on 20 Nov, 91 opened it); a done item says only its day and the Assembly's sentence, and "po rečima
  predsedavajućeg" when that is whose word it was (the rest in the label under the list). Since it is open, the
  counter's `tacke` now counts mostly closings. The recording's six parts are a row "Delovi dana (6)". Every fold
  (the agenda, the parts, all the steps, the earlier turns, the next sitting's agenda, "Kako ovo radi") is a row at
  least 44 px high, the whole row pressed, with a count and a chevron; the page's script keeps each one open or
  shut as the reader left it when the part is replaced (it had only kept the opened ones open).
- **Colour where it means something** (22 Nov 2026, the maintainer's choice of point 4 of the same look: "malo više
  boje"), with no new exception to the design rules. The speaker wears their list's colour, the same shade as in
  the day's bars (`page._shades`; a class `lc-<shade>` on `#deo` sets `--lc`): a band at the left and a light tint
  of the box with the name, a square before the list's name (its key), the dot before the name, which wore the
  orange of "protiv", and the dot of "Uživo" on top. A vote on the day's list with its figures (`glasanje`, checked
  to add up) has a bar of the present (or of those who voted), "za" blue and "protiv" orange, and those two
  figures in their colours (`page._votes`). Out of those two colours went what wore them with no vote: the agenda's
  marks (✓ and ●), the notice's "Novo" and the link to the site. The kinds of steps stay without colour (a new
  exception to rule 2, not asked for).
- **The day back on the line of time, a mark for each kind; when the Assembly goes on, on top** (22 Nov 2026, the
  maintainer, the same day, after the list above: "ne sviđa mi se ovo"; it changes "The day is one list" and
  part of "The first screen"). Everything is in the steps again, on the line of time with its marks, under "Šta se
  desilo danas" / "Šta se desilo 19. novembra": the day summary's decisions (a full dot, their sentence, a vote's
  figures and bar), and every step heard, each with a mark by its kind (`page._step_mark`): a ring for a step, the
  item's number in a larger ring for a move to an agenda item, a full dot for an election or a result, **a red
  square for each measure of the chair** (titled by its kind, "Opomena", whom under it; a heavier one ringed),
  a dashed ring for a break or the day's end. The first eight stand, the rest fold. The Assembly's sentences stay
  in the agenda as above. A done item of the agenda has **a green ✓**. Red and green are the maintainer's own
  choice, outside rule 2 like the lists' colours, with the kind always said in words beside them (`--stop`,
  `--ok`). **The recording is higher** between sittings, right under the line on top. **When the Assembly goes
  on** is said large on top ("Skupština nastavlja sa radom u utorak, 24. novembra, u 10.00.", `page._resumes`,
  from the notice in its set words, linked to the Assembly's site) in place of the notice's box, between sittings;
  a notice not in those words stands as before. **"Obavesti me kad sednica počne" and "Dodaj na početni ekran"
  are two buttons in one row with nothing under them** (the maintainer: the structure and the text under it were
  too much). On an iPhone the second button too, which on a press says where Safari keeps it. What the
  notification keeps is said once it is turned on ("kod nas ostaje samo adresa za njega") and on the method page;
  principle 5 asks the page to say it, and it does there.

**A shorter page between sittings (22 Nov 2026, the maintainer).** Taken off: the box of the day's sentence with
its three with the most time and its buttons ("Dan u karticama", "Podeli presek dana", "Uspravna slika za priču";
"sklonio bi ceo ovaj segment … sa sve tim za deljenje"); the day's time by list (still a card); the quiz at the
foot (the facts stay); the link to the Assembly's own live broadcast. "Ko je koliko govorio" shows five, the rest
under "Ostali govornici (N)". "Sednica po Poslovniku" stands under the agenda between sittings, and before the day
during one. The cards are reached only from the speaker's box now, so between sittings they are not in the page;
the link preview's picture (`/slika.png`) and the story picture stay. During a break only the next sitting
convened, if any, stands where the box was. Measured on the test page: 4.5 screens at 390 px (about 6.4 before).

**The speaker on the picture, the picture kept on top (22 Nov 2026, the maintainer; points 1 and 2 of the analysis
"Mikrofon, gledanje preko nas").** While YouTube's broadcast plays, a line over its top left corner gives the
speaker's name, list (in the list's colour) and clock, written by the script from the part (`#deo`) every second;
not over the archive's recording, whose moment is not the part's. Once a recording plays and its place has gone up
out of sight, the picture stands small in a band at the top with the speaker beside it, so the page is read while
it is watched; its place keeps its height, the player is not moved (an iframe moved reloads), and × puts it back
until the next ▶. To measure after a sitting week against 20 Nov: the share in view 5 and 15 minutes.

**Whisper on the graphics card (22 Nov 2026, the maintainer's choice).** The maintainer wants the automatic transcript
beside the picture, and found every model but `large-v3-turbo` too inaccurate. On the computer's CPU (Ryzen 5 7500F)
that model is 4.5x faster than speech on long sound, but costs some 4.5 s for any piece (Whisper works in 30 s
windows), so pieces of 5-10 s, which a line under the picture needs, barely keep up; tuning gave nothing (beam 1:
+13% and other words; 6 threads slower; batched: words lost). There is no NVIDIA card (faster-whisper's only GPU);
the Radeon RX 7600 runs whisper.cpp through Vulkan: 22x faster than speech, a 5 s piece in 0.4 s, 83% of the words
the same as the CPU's on 5 min of 19 Nov (each erred elsewhere). So `whisper-gpu.ps1` builds whisper.cpp at a pinned
commit with Vulkan, fetches the model and the VAD model checked by SHA-256, and runs its server on
`127.0.0.1:8178` from the user's Startup folder; `prepis.Writer` sends it the sound (`WHISPER_URL`, set in both
compose files to `host.docker.internal`) and writes on the CPU for five minutes whenever it does not answer, the
CPU's model loaded only then. A word repeated more than three times in a row is cut to three (`prepis.calm`: the
card once wrote "znaju" nine times over a noisy stretch). What is shown is unchanged: the transcript stays off the
page until the line beside the picture is made and the maintainer has seen it (principle 6).

**The automatic transcript under the broadcast's picture (22 Nov 2026, the maintainer: "probamo odmah pa ću videti
kako izgleda").** It changes, for this line only, "The transcript is written down but not shown" above. A thread of
its own (`prepis.Captions`) takes the newest kept sound, some eight seconds at a time (`CAPTION`; nothing older than
30 s), and has the graphics card's Whisper write it down for the page only: not kept, not read for the day's steps,
nobody's words by name, and the files left for the transcript (`Writer`), which goes on as it was. Without the card
there is no line (the CPU would not keep up). The tracker keeps the last four lines in memory; the snapshot gives
them as `titl` while a broadcast is on and they are a minute fresh, with the transcript's spelling corrections, and
the part carries them hidden (`cc-src`). Under YouTube's picture, while it plays, a black band shows the last two,
the newest at the bottom, and says "Automatski prepis: kasni i može da greši, nije citat." (principle 6: it is no
quote, and the site quotes the notes); in the band kept on top, under the picture. Each line is shown
`TITL_KASNJENJE` seconds after it first came (0 for now): the viewer's player is behind the broadcast by a time to
be measured on 24 Nov, and the line is to come with its picture. `TITL_PRIKAZ=0` turns it off.
- **The groups' time in the debate, an estimate** (22 Nov 2026, the maintainer, after readers asked how much time
  each party has left; `vreme.py`, `View._group_time`, `page._group_time`): while an agenda item is under way, a box
  under the day's steps shows, for each group the site names (the roster's lists of the sitting MPs, as the
  Assembly's site gives them), its share of five hours by its MPs (art. 97), the time used and what is left (or how
  far over the estimate). Counted: a sitting MP's turn of that group longer than `REPLY` (125 s: replies and points
  of order last two minutes at most, art. 103, 104), from the chair's move to the item (`tacka.json`, so over every
  day of the debate: the earlier days read from `dani/` and `hronika/`, once); a debate closed and another opened
  is the debate in detail, counted afresh with each group's chair's 15 minutes more (art. 158). Not known, and said
  on the page: the shortened procedure (half, art. 99), more time given to the groups, the Assembly's own clock (we
  count the caption's time). Labelled "procena"; its term `vreme-rasprave` on the site's page of the Rules.

**The line under the picture comes with the sound (22 Nov 2026, the maintainer: "da titl bude istovremen sa
zvukom").** Each viewer's YouTube player is behind the broadcast by its own time (16-20 s on a 24/7 news channel,
measured), so no fixed delay fits. The broadcast's playlist dates each segment (`#EXT-X-PROGRAM-DATE-TIME`), and the
embedded player, given `enablejsapi=1`, tells the page by its own messages which moment by that clock it shows
(`mediaReferenceTime`); nothing more is loaded from YouTube, and only after the press as before (principle 5).
`stream` keeps each segment's program time (`program_of`), the sound's file is named with it, whisper.cpp gives each
phrase its seconds (`verbose_json`), and each phrase is a line with its moment (`pt`); the page shows a phrase from
when the player reaches it, for 15 s, the last two together. A line without a moment, or a player that tells none,
falls back to `TITL_KASNJENJE`. The line takes one segment of sound at a time (`CAPTION` 4 s): measured on Sky
News through a test image for 90 s, 29 phrases, none late, each in the page 7-18 s (median 12) before the player
reached it; with two segments the least was 2.6 s. A broadcast with a low-latency player could leave less: a late
phrase is shown at once.

**When the player is close behind, it is set back a little** (22 Nov 2026, the maintainer's own first thought, "da
li moramo malo vratiti youtube snimak unazad"). On a Serbian channel the embedded player was only 6.5-10 s behind
the broadcast, and phrases came 2-5 s after the player had passed their moment. The page now notes how late a
phrase new to it is (not those there when the player started), and sets the player back by that and 3 s more by
YouTube's own `seekTo` message, once in 20 s at most and 30 s in all. Measured on that channel over two minutes:
after the first half minute the player stood 13.6 s behind, and no phrase was late (each in the page at least 1.8 s
before its moment). The test servers for this (a hand-run container on a 24/7 channel: `SOURCE_PAGE=`,
`YOUTUBE_URL=<its watch address>`, `CHANNEL_LIVE=`, port 8095) and `zailiprotiv-dizajn/sync/measure2.py` are the
way to look again without a sitting.

**A day's recording read on the graphics card too** (22 Nov 2026, the maintainer: "možeš prebaciti na karticu ako
ima mesta"). `zvuk_dana` (who spoke when, from what was said) writes on the card's server when it answers
(`WHISPER_URL`, else `host.docker.internal:8178`), on the CPU otherwise. The server gives tokens, not words: a token
with no space before it is the same word's. Its VAD cuts the silence out and gives a segment's times in the whole
sound but the tokens' in the shortened one, a minute off by the twentieth minute: each segment's words are laid
over its own span in proportion. Checked on the first 20 min of 19 Nov against what the CPU had written: 89% of the
words the same, a matched word's start 0.32 s apart at the median (0.84 s at the 90th percentile), the 20 min written
in 50 s.

**Who speaks without a caption: the chair's words and the voice, counted and labelled** (22 Nov 2026, the
maintainer: "da čitanje prepisa utiče na govornika ako prepoznamo uspešno", voices live, and the time so found
counted, labelled). It changes "Reč ima … from the chair's words" above, where no time was counted, and, for the live
service, "never live" of the voices in `docs/decisions/recordings.md`. The order: a caption names the speaker and
rules; while none does, (1) the chair giving the floor (`hronika.floor`, in the chair's sound or in a turn found this
way) makes that MP the speaker from the end of that piece (`Tracker.heard`, `"izvor": "prepis"`), until a caption, the
chair giving the floor to another, a voice, or `HEARD_LONGEST` (20 min); (2) the voice (`glas.py`): ERes2Net through
sherpa-onnx, the model the recordings are read with (its file checked by digest in the image), a window of 3 s every
1.5 s of the kept sound, and the site's rule (`ko.stretches`: 0.55 a window, 0.05 ahead of the next, 20 s at 0.68 on
average, 8 s of gap); a stretch so named makes that MP the speaker (`"izvor": "glas"`), and the turn ends when the
voice stops for 8 s or the chair's or another's voice is named (`unheard`, `voice_gone`). The presiding officers
(`GLAS_BEZ`: the Speaker, the six deputies, the two who chaired the first sitting) are never named by voice. The
samples are each MP's mean voice (`/data/glasovi.npz`, numbers only, never published): first from 17-18 Nov, placed
by the notes (27 MPs), then every turn the caption names adds its windows (from 5 s after its start to 5 s before its
end), so an MP is known by voice once the picture has named them. Such turns count in the day's totals and the
groups' time; the speaker's box says "Prepoznat po glasu" or "Po rečima predsedavajućeg …, automatski; može da
pogreši", and the list of turns "po glasu" / "po rečima predsedavajućeg"; `/dan/<date>.json` carries `izvor`.
Checked: samples from 17 Nov only, speeches of 18 Nov fed as the stream leaves them, 90 s each: the three MPs with a
sample named (Hubač, Brnabić, Vučić), the three without none; and four minutes of a Serbian TV talk show named
nobody. The hall's floor for "not silence" is the quietest fifth of the last ten minutes' tenths of a second, as
`lice_glas` does it (a first try against whole windows threw away continuous speech). `GLAS=0` turns voices off.
- **"Podrži sajt" on the page** (22 Nov 2026, the maintainer): a box like the Rules' above the link to the site,
  leading to the site's `podrzi` (`support_cta`, `support_sub`).
- **The page as an app: only the sound, and the lock screen's player** (22 Nov 2026, the maintainer, predlog 2 after
  readers asked to listen in the car). Beside "Pusti snimak dana" (an archive day's recording) "Slušaj samo zvuk"
  plays the same file in an `<audio>` (`data-zvuk`), which a phone keeps playing with the screen locked; over it who
  speaks at that moment and, where the page holds it, that turn's automatic transcript. For the archive's files the
  page sets the Media Session (`mikrofon.js`, `session`): the title is who speaks (the day's turns' "▶ snimak" of
  that file, as the page lists them), the artist their list or office, ⏮ ⏭ the turn before or after, ±15/30 s;
  the turn now playing is outlined in the list. A turn's ▶ keeps the way the day is played. The live broadcast
  stays YouTube's player (its iframe holds its own session; no sound of ours is relayed: rights, and the tunnel is
  not made for streams). The site's mikrofon page and day pages (`govornici/<date>`) have the same button.
- **The site's mark on the home screen, no microphone in the header, "Podrži sajt" on top** (22 Nov 2026, the
  maintainer: the microphone "looked too like a Google logo"). The home-screen icons (`picture.icon`) are the site's
  own mark, the two arcs of `favicon.svg`, as the site's apple-touch-icon; the header keeps the site's name and
  "Podrži sajt" beside the script's switch, and the microphone mark is gone from the page. A phone that added the
  page before keeps the old icon until it is added again.
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

**The presiding officers never named by voice, by their addresses** (22 Nov 2026, found while replaying 19 Nov). The
list (`GLAS_BEZ`) was compared with the list's names, which put the surname first, so it would never have matched,
and two of its names were wrong (the first sitting was chaired by Stojan Radenović and Nada Macura). It is now the
MPs' addresses on the site, as the voices are kept: `cupic-aleksandar`, the six deputies, `radenovic-stojan`,
`macura-nada`. None of them had a voice sample yet, so nothing was named wrongly.
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
- **The day's summary by mail** (22–23 Nov 2026, the maintainer's decisions: principle 5's exception as for the
  notifications, a mail every sitting day, the addresses kept by the maintainer, encrypted; the look chosen over
  three drafts). `mejl.build` makes the subject, text and HTML of a day (Latin or Cyrillic) from the day's summary,
  the chair's measures and the speakers' measured time: the decisions, the warnings and to whom, and what each
  speaker spoke about, on a line of time with the live page's marks; a speaker's list in its colour, a bar of the
  time, "opomena" by who got one and "najduže" by the three longest; no paragraph (the maintainer: "veliki blokovi
  teksta su loši"). The subject and the counts are the code's, and how the summary is made is on the method page
  linked at the foot, not in the mail. Tables and inline styles only: no picture, font or anything loaded, nothing
  tracked. `mejl.mixed_words` finds a word in two scripts (19 Nov: "iznео"). The counter sends what the service
  made (`POST /m/salji`, the push's token; Cloudflare Email Service from `sazetak@mikrofon.zailiprotiv.rs`, the
  only sending domain: the site's own keeps its mail at Loopia, whose MX records Email Routing would replace;
  answers go to `kontakt@zailiprotiv.rs`).
- **Who is who: the list's names and lists, never the model's** (23 Nov 2026, the maintainer: "Anji Brnabić",
  "Bakić" and MPs of the ruling group shown "bez liste" in the first draft). `mere.Roll` finds an MP in a sentence by
  the surname in any case ("Bakiću", "Milinku Jovanovu" → Milenko Jovanov), the given name or who had the floor
  deciding between MPs of one surname, nobody when still two; an MP's list is the group, else the party that
  proposed them (`data/<N>/members.json`), else "van poslaničkih grupa". `mere.measures` keeps only the chair's own
  words giving a measure (a sentence that speaks of one given before is none: of 19 Nov's 13, 8 were measures) and
  finds to whom, said so: a name in the chair's sentence; the stretch's summary naming who got one at that minute;
  the chair saying later whom he warned; for a word taken away over time, the MP with the floor. Never guessed
  otherwise. Written on 19 Nov alone: to be checked on the next days before the live page and the day's page use it.
- **Who gets the day's mail, and when** (23 Nov 2026, the maintainer's decisions: B, the maintainer first and all on
  his click; the addresses kept by him, encrypted, his name on the privacy page). "Sažetak dana na mejl" on the page
  (beside the notification's offer; a form to the counter that works without the script) asks the counter, which
  seals the address for the maintainer's key and mails a confirmation (`worker/mejl.js`). When the day's summary is
  on the page (`sudija.Judge._tell`), `pretplata.Mailer.ready` mails the day to `MEJL_UREDNIK` with a link
  (`/mejl/posalji?dan=&k=`, the day signed with `MEJL_KLJUC`) to a page with one button; the button sends the day to
  every confirmed address (`/m/spisak`, opened here with `MEJL_KLJUC`, each with its own unsubscribe link), once,
  until noon the next day (23 Nov 2026; first until 8). A word in two scripts stops it: the maintainer is told, nobody else gets the day. Both
  keys are in `live/.env` only; without them nothing is sent. What went is kept in `/data/mejl/<day>.json`.

**The floor given now, a voice that changes, and who presides** (22-23 Nov 2026, the maintainer: "napravi", after
19 Nov was replayed through the service's code with no caption at all). Three changes, each from a fault the replay
showed. (1) "Reč ima X, a posle njega ima reč Y" made Y the speaker: `hronika.floor(now_only=True)` leaves out a
floor announced for later (posle, nakon, zatim, potom, sledeći, pripremi among the four words before it), and the
speaker is the last floor given now in the piece. (2) A turn found by the chair's words, of an MP whose voice is not
known, went on while someone else spoke (a reply, the President): its own first seconds (3-15 s) are now its voice,
and when a later 15 s is on average under 0.45 alike them the turn ends after the last window still alike (set
against the notes of 18 Nov: a speech's own later 15 s fall under it in 10% of cases, ending it early with nobody
named; the next speaker's stay above in 4%). (3) The presiding officers' voices tell who presides: their samples are
the voice in the chair's own lines of 19 Nov's transcript ("reč ima", "zahvaljujem", "izvolite", "konstatujem"...),
in each one's hours (Radenović until the vote, Macura 12:40-13:38, Čupić after: 36, 8 and 145 windows, each 0.75-0.82
alike its mean, 0.15-0.33 alike each other). A stretch in a presiding officer's voice, unless they hold the floor,
sets "Predsedava: <ime> (po glasu)" in the line on top (shown while heard in the last quarter of an hour) and ends a
turn found without a caption. Replayed: 18 Nov against the notes (voices sampled on 17 Nov only), wrongly named
1.5% -> 0.4% of the MPs' speech, named rightly 76% -> 73%; 19 Nov's morning against its captions 6.7% -> 3.1% wrong,
the day against its reading by voice 6.3% -> 1.1%; the chair found as it was: Radenović, Macura from 12:42, Čupić
from 13:32. The deputies get their voices once they speak with a caption; a measure of the chair could carry who
presided (not done).

- **The day's mail loses nobody and goes to nobody twice** (23 Nov 2026, found by trying the sender with the counter
  replaced: two clicks sent everything twice; a break after the first batch left the rest without the mail, the next
  click saying "already sent"; a mail to the maintainer that failed was kept as sent; a word in two scripts blocked
  the day after it was mended too). `pretplata.Mailer` sends under a lock and keeps per reader (the counter's row
  id, never the address) who has it, written before and after every batch of 20: a click after a break goes on where
  it stopped. A batch whose call timed out or ended in a 5xx is "nesigurni" and is not sent again: better one batch
  without the mail than twice. The mail to the maintainer is tried every five minutes (`sudija.MAIL_EVERY`) until it
  goes, and again when a word in two scripts was mended (edit `/data/sazetak/<day>.json` and restart the service,
  which keeps the summary in memory). The link works until noon (the maintainer; a day ended late reaches them at 7).
  Without `MEJL_KLJUC` no code opens anything (an empty key signed codes anyone could compute).
- **Leaving the day's mail takes the reader's own press** (23 Nov 2026, found in a look at the code): the link in
  every mail deleted the address when merely opened, and mail scanners open links. It is now a page with one button,
  as the confirmation is; the mail reader's own button (List-Unsubscribe-Post) still leaves at once. The texts no
  longer say "jednim klikom". A confirming mail that failed to go lets the address ask again (it had been told all day to
  look in its box). `tests/test_pretplata.py` runs the worker's own code in Node against a table in memory.
- **The sound never holds up the picture** (23 Nov 2026, found in a look at the code): the reader fetched each
  segment's sound in the loop that reads the frames, up to three tries of ten seconds when YouTube's sound-only track
  was slow, and the frames meanwhile were skipped (`newest > nxt`). The sound is now taken by a thread of its own
  (`HlsPoller._hear_loop`), in order, with the moment its frame was read; two minutes of it may wait, beyond which
  the oldest is let go.
- **A test has none of the live service's secrets but the page's key** (23 Nov 2026: `env_file: .env` gave every test
  the bucket's keys and the mail's: during a sitting a test left running would have written its own segments over the
  live playlist in R2). `docker-compose.test.yml` empties each by name; `tests/test_live.py` reads the code for what
  looks like a secret and fails when one is not emptied there. A test container started by hand gets no `--env-file`.
