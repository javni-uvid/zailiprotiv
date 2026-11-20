# AGENTS.md for `live/`: "Ko sada govori"

The decisions about the live page `mikrofon.zailiprotiv.rs` and the service behind it. It continues the
repository's `AGENTS.md` (how to work, the principles, the architecture; "Broadcasts and recordings" there has what
the site makes of the service's records and of the recordings), which is read first; `README.md` here says how the
service works. **Keep it current** in the same way: a decision about `live/` is added at the end of this file, in
the same commit. Dates are the maintainer's decisions unless said otherwise.

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
