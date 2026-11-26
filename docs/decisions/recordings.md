# Broadcasts and recordings

Decisions about the broadcasts and recordings on the site; the live service's own are in live-*.md, moved word
for word from AGENTS.md on 20 Nov 2026 (the maintainer's decision, so that an agent reads the rules and only the
decisions of the part it works on). **Keep it current:** a decision made or changed is added here, at the end of the
section it belongs to, in the same commit as the change. The principles and the rules of work are in AGENTS.md.

## Broadcasts and recordings

The Assembly broadcasts its sittings live and keeps the recordings with its broadcaster (videonet.co.rs), linked
from its page "Prenosi". Since 17 Nov 2026: while the newest convocation's listing marks a plenary sitting
"(у току)", the home page and "Sednice" carry a bar linking to the live broadcast (`config.LIVE`) and to "Ko sada
govori" (`live_page`, see below); each sitting's page lists the recordings of its days (`videos.py`,
`data/<N>/videos.json`, read by **votes** for the current and the newest convocation; earlier ones by hand). Both
are links: the site plays nothing itself (principle 5). The notes carry no times, so a speech cannot be linked to
its minute.

### Who is speaking now (`live/`)

`mikrofon.zailiprotiv.rs`: who is speaking in the Assembly now and who spoke today, read from the live broadcast by a
service in Docker on the maintainer's computer, behind a Cloudflare tunnel (`live/`), with a worker in front of it
(`live/edge/`). **Its decisions are in `live-*.md`**, in short in `live/AGENTS.md` (20 Nov 2026: moved there, as this file had grown to
85 KB, more than half of it about that service, read by every agent whatever its task): the page and what it shows,
the captions and names, the automatic transcript, the day's steps, notifications, testing and putting live. Read it
before changing `live/`, the site's `mikrofon` page or the counter's push. What the site makes of the broadcast's
records and recordings stays here:

- **Who spoke when, kept** (17 Nov 2026): the service keeps a record per day (`/dan/<date>.json`: each turn, how
  many frames named the speaker, its YouTube video and HLS segments, and the spans when the broadcast was seen at
  all); **votes** takes the records in each hour (`uzivo-pull` → `data/<N>/uzivo/<date>.json`, the convocation by
  date). A run that can't reach the computer changes nothing; records alone are committed without starting the
  chain, as they change every hour of a sitting. Planned on them, in this order (the maintainer): each speech in
  the notes linked to its minute in the recording; speaking time by MP and group; the records as downloads. Outside
  `pokriveno` there is no record, and whatever uses them says so.
- **A speech's minute in the recording** (17 Nov 2026, `uzivo.minutes`, `notes_site._clip`): a day's speeches (the
  chair's left out, one speaker's in a row as one) are lined up with the day's turns (named in two frames or more)
  by the order of the speakers' names, difflib's matching blocks; a speech gets its turn's place, the first of a
  run only, and where the record has a gap or the order disagrees it gets nothing. The link is the YouTube video at
  (first segment − 1) × segment length, labelled as found automatically. **Off until checked:** the notes show the
  links only with `recording_links` in `data/settings.json`, to be set once a few links from a real sitting have
  been opened by hand and land on the speaker. The time is right (checked 18 Nov 2026 against that day read from the
  recording: 19 morning turns land within 25 s of the speaker's first caption, most of them 7 s before it), but the
  YouTube video went private the evening of the same day, so the links wait for the archive's files (below).
- **A sitting day read afterwards from the recording** (18 Nov 2026, the maintainer's request): the live service read
  only the end of 17 Nov (it was started late, and the caption has a second layout, one line in the middle, that it
  does not read). The day was read again from the whole YouTube recording, a frame every 5 s, the name line of the
  caption matched to each speaker's own caption (the names read by eye), and kept as `data/<N>/snimak/<date>.json`
  (the shape of a live record, with `snimak` the second in the video and `uloga` the caption's list line; the
  chair has no caption and is not listed). The newest such day is listed on the site's `mikrofon` page and published
  as `mikrofon-dan.json`; between sittings the live service shows it in place of its own record of that day or an
  earlier one, and says it was read from the recording. Its own `/dan/<date>.json` (and so `data/<N>/uzivo/`) is
  unchanged. Reading a day this way is by hand for now; a script for it (the recording, the caption in both layouts,
  OCR) is the next step.
- **The live broadcast's YouTube video goes private** (18 Nov 2026: 17 Nov's, a day after). The broadcaster's archive
  (videonet.co.rs, `videos.json`) keeps the day as MP4 files, so a day read from the recording links each turn to its
  file and second (`datoteka`, `snimak`; a `#t=` fragment, which browsers follow for a video file). Where each file
  begins in the day was found by lining up a caption's first frame in the file and in the video. The live record's
  links (`video`, YouTube) will go private the same way: moving them to the archive's files is to do, and
  `recording_links` stays off until then.
  (Changed 25 Nov 2026 for the time until the archive's file: see the end of this file.)
- **The archive's files placed by their captions** (18 Nov 2026, the maintainer's request; `arhiva.py`, run by
  **votes** each hour): for every new file in `videos.json` of a day with a live record, ffmpeg reads a frame every
  30 s (over the network, only those bytes), the live page's own OCR reads the caption, and the start that puts the
  most names inside their speakers' turns is the file's (then to a few seconds where two names change); frames that
  fit a wide range of starts (one long speech) or disagree place nothing, tried again up to three times. Kept in
  `data/<N>/arhiva.json`. A day with no file in `snimak/` gets one written from the live record (`"izvor": "uzivo"`:
  turns in one frame left out, one speaker's turns within two minutes joined), written again while the record grows;
  a day read by hand only gets the places it lacks. The record's clock is the service's, some 15–20 s behind the
  broadcast, and turns and files share it; 17 and 18 Nov were lined up by hand on YouTube's clock
  (`"rucno": true`). Needs ffmpeg, Tesseract's Serbian, numpy and pytesseract on the runner.
- **Who spoke how long** (18 Nov 2026, the maintainer's request; `pages_govornici.py`): `govornici/<date>` per day in
  `snimak/` (each speaker's time and speeches, the time per list, the time between turns, quick exchanges, every
  turn with its place in the archive and "podeli", a picture of the day as the share picture) and `govornici.html`
  (the newest convocation's days summed). Ordered by time, ties by name. The time between turns counts stretches up
  to five minutes (mostly the chair, who has no caption); quick exchanges are two speakers taking turns three times
  or more, each within two minutes: by order only, the page claims nothing about what was said. Method:
  `kako-racunamo#govornici`.
- **An automatic transcript until the notes** (18 Nov 2026, the maintainer's request; `prepis.py`, the **prepis**
  workflow, by hand per day): each turn of 30 s or more cut out of the archive's file as sound and written down by
  Whisper (faster-whisper on the runner's CPU, `large-v3-turbo`, the one model since 20 Nov 2026; a run stops after `minutes` and the next goes on).
  Shown under the turn on the day's page, folded, as an automatic transcript that may err and is not a quote
  (principle 6 is about the notes, which the site quotes); not shown once the day's notes are read.
- **"Dok čekate"** (18 Nov 2026, the maintainer's request: "more fun", on both pages, "like the voting quiz"):
  between sittings the live page, and the site's `mikrofon` page, carry a quiz and the facts
  (`pages_mikrofon.quiz`, `facts`), published for the service as `mikrofon-cekanje.json` (so a change needs no rebuild
  of the image). Ten questions, one at a time as in the site's quiz (a strip of numbers, big answers, the answer and
  its source, on by itself after four seconds, a score to share at the end). They ask for what the site computes:
  urgent procedure, days to adoption, laws with no vote against, the most laws passed in one day, speeches, the chair's
  measures, harsh words (how many, the commonest and how often, the day with most), and one sentence said in the hall
  with its harsh word left out (`pages_floor.harsh_quote`, chosen by rule: the commonest word alone in a sentence of
  40–170 characters, the latest said; its answer links the speech). Wrong numbers are the right one times fixed
  factors picked by the question's key, unrounded like it (`SCALES`); words and days offered are the three with the
  most. About no MP in particular; a fact the quiz asks about is not listed beside it. Black and white only, not the
  colours of "za" and "protiv". The script and styles (`templates/mikrofon.js`, `.css`) are one file each, inline in
  both pages; the image copies them.
- **After a day of visits** (19 Nov 2026; 28,000 visits to the live page in a day, 86% on phones, 77% of them the
  Cyrillic page, one in nine going on to the site, most to the page of the MP then speaking, where a new MP's page
  was all but empty). **An MP's page, new or returning, lists the MP's turns on the floor in the newest
  convocation** from the days read from the recordings (`pages_govornici.per_speaker`, `macros.floor_now_part`: the
  sum, then each turn by day, linked to its place on the day's page with the recording and the automatic
  transcript), says "Sada je za govornicom" while the live service names them (`site.js`), and ends with the way on
  (`macros.next_steps`: who else spoke that day, the MPs' list, the quiz, the live page); a new MP's occupation is
  on the page. **"Ukratko" is always first on an MP's page and always open** (the maintainer's decision the same day:
  "sažetija i zabavnija"): a tile a number with a few words under it (`macros.brief`; `mp_card.facts` gives each fact
  its `short`, `sub` and `href`), the time on the floor in the newest convocation as the first tile, the whole
  sentences and how they are computed folded below; a new MP's tiles are year, occupation and place. Still no rating
  and the same tiles for everyone. The turns on the floor are a card of days with a pill a turn. **The live page's order** (changed the same evening at the maintainer's request) is a short head (what
  the page is in a line, and one button to the site), the newest notice alone, the broadcast, the name and clock,
  the box about the speaker, what is being said, the day's steps, the day. **While nobody is on** the summary also names the next sitting convened (`sazvano` in
  `mikrofon-cekanje.json`, as the Assembly lists it) and offers the day in cards. **An upright picture**
  (`/prica.png`, 1080×1920, `picture.render_tall`) for a phone's story. **The Cyrillic page is checked first** when
  anything is added (this time it showed "YоуТубе" and hours as "х": foreign names are written as said, "Jutjub").
  The clock's hourly run named the current convocation by number, so the newer one's MPs, occupations and recordings
  went unread for a day: `votes.yml` now reads the newer one whenever the current one is read.
- **Linked from the live bar** (17 Nov 2026, the maintainer's decision): while a plenary sitting is in progress the
  bar carries "Ko sada govori" beside the Assembly's broadcast, to `live_page` in `data/settings.json` (its `cir/`
  in the Cyrillic edition, through `data-cir-href`, which `cyrillic.page` follows). Accepted: the link leads to an
  error while the maintainer's computer is off.
- **Who spoke when, from what was said** (20 Nov 2026, the maintainer's decision: from the afternoon of 19 Nov the
  broadcast showed no speaker's caption, so reading the picture no longer works). `live/uzivo/zvuk_dana.py`, run in
  the live image on the maintainer's computer (which reaches the archive), writes each archive file of a day down
  word by word with its second (Whisper, `large-v3-turbo`, told the day's speakers' names; ten minutes of sound at a time, as a whole file does not fit in
  memory); `zailiprotiv govor <day> <folder>` (`govor.py`) finds each speech of the day's notes in those words by
  runs of four words found once in each, in the same order, and writes `snimak/<day>.json` with `"izvor": "govor"`:
  a speech lasts from its first word to its last, gets no place with fewer than two runs, and the name is the
  notes'. Nothing of the automatic words is shown or quoted. Each file's start on the clock is from `arhiva.json`,
  or from the live record's turns of the same speakers; a file with neither is reported and its turns are left out
  (its start is then set by hand in `arhiva.json`, `"rucno": true`, with how). Checked on 18 Nov against the turns
  read from the captions: a speech begins up to half a minute before its caption appears and ends with it. It waits
  for the day's notes, which the Assembly publishes a day or more later.
- **Faces and voices, only where there are no notes** (20 Nov 2026, the maintainer's decisions: faces and voices
  may be used, the recordings being public and MPs public officials; and they are the fallback). The sources of who
  spoke when, in this order: the caption while the broadcast shows it; the day's notes lined up with the sound
  (above), which once published replace whatever else the day had; and only for a day, or a part of one, with no
  notes yet, faces and voices (`live/uzivo/lice_glas.py` in `live/Dockerfile.analiza`, an image of its own on the
  tested one, never live (voices live since 22 Nov 2026: live-speaker.md): YuNet and SFace for faces, 3D-Speaker's ERes2Net through sherpa-onnx for voices; only the
  numbers are kept, no picture). `ko.py` matches a voice for every speaker by one rule: a stretch of sound is named
  when its windows are on average 0.68 alike the mean of a speaker's windows in turns known by caption or notes
  (`STRETCH_MIN`; checked on 18 Nov, each file left out of the samples in turn: every stretch so named was right).
  Faces do not name anyone by themselves: the camera often shows someone behind the speaker or listening (19 Nov:
  Vučević and Lalošević behind Brnabić), and the Assembly's portraits matched 4 of 49 turns. They group the close
  shots of the parts no voice named, and the maintainer labels the groups by hand (a private page of crops); a label
  becomes a voice sample only when the sound in that group's frames is one voice (0.65), and a chair (19 Nov:
  Radenović, then Macura during the vote, then Čupić) is a sample that is never listed. `zailiprotiv glas-dan <day>
  <stretches>` writes such a day (`"izvor": "glas"`): the captions' turns, the voices' where there were none, each
  part of the recording placed on the clock by captions read in passing (`govor.clock`; 19 Nov's afternoon by hand,
  three of Pastor's captions in three parts agreeing). It is incomplete, and says so: a speaker with no sample is not
  named. Written again from the notes when they come; the analysis's files stay on the maintainer's computer.
- **A very short speech between two placed ones gets a place** (21 Nov 2026, the maintainer's request: one speech of
  17 Nov had none). A speech under `SHORT` words (eight: "Ne želim.", "Hvala.") cannot hold two runs of four, so it
  never had a place by runs. `govor.between`: an MP's speech like that, with a placed speech before it and one after,
  both in one file, stands just after the one before and lasts as long as its words take at `RATE` (2.5 words a
  second); it has no runs of its own (`sidra` 0), so it is never a voice sample, and joins the turn before it when
  the speaker is the same. The same rule for every speaker; a longer speech with no runs still has no place. 17 Nov:
  Milenko Jovanov's "Ne želim." is in his turn (+13 s); 18 Nov had none unplaced.
- **`large-v3-turbo` is the one Whisper model** (20 Nov 2026, the maintainer's decision): the live service, the
  **prepis** workflow and the recordings read afterwards; the second reading by a better model is gone with it.
- **A day's parts the archive's page does not list yet** (20 Nov 2026: `zas2026111910e.mp4`, the end of 19 Nov, was
  there hours before the page named it): `videos` tries the next letter after each of the latest three days' last
  file (a HEAD request) and keeps what is there, marked `"nenavedeno": true`.
- **The last sitting day's steps between sittings, and the Assembly's dates kept whole** (20 Nov 2026, the
  maintainer's report: the agenda was wrong and the day's steps were gone). The steps were kept per day, so after
  midnight the page had none; now, while it shows the last sitting day, it shows that day's steps under its date
  ("Šta se desilo, …"). 19 Nov's steps, kept on the computer the service ran on that day, were made again from the
  day's recording written down (`large-v3-turbo`) by the same rules, and from the Assembly's report of the sitting.
  `hronika._SENTENCE` no longer ends a sentence at a number followed by a small letter ("19. novembra", "24.
  novembra"): the Assembly's "Trećeg dana rada, 19. novembra …" had been cut at the date and dropped. Items 3 and 4
  of the first sitting were added to `data/15/tacke.json` from the Assembly's page, and the next day of work to
  `data/obavestenja.json`.
- **A day's record only grows** (20 Nov 2026: a restart of the live service served 19 Nov with no turn and three
  minutes seen, and the hourly run wrote it over the 28 turns kept). `uzivo.pull` never replaces a kept record with
  one that has fewer turns or less time seen (`uzivo.smaller`), and says so in the run's log; 19 Nov's was put back.
- **The model tells the day's steps and sums the day up** (20 Nov 2026, the maintainer's decision after a trial on
  19 Nov): Claude Haiku over the automatic transcript is the source of "Šta se desilo danas", the rules the fallback,
  and writes a summary at each break and of the day, labelled as a model's from an automatic transcript; how, in
  `live-day.md` ("The model tells the day's steps"). The key is in `live/.env` only.
- **How right "who spoke when" is, measured** (24 Nov 2026, the maintainer: "kreni od merila", after a day of rules
  for the live record each changed on one to three examples). `zailiprotiv tacnost [day] [--zapis file]`
  (`tacnost.py`): a day's live record against the notes' speeches placed in the recording (`snimak/<day>.json`,
  `"izvor": "govor"`), second by second inside what both cover: right, under a wrong name, missing, and named where
  the notes place no speech; the speeches found (half of one right), and how far a found speech's beginning and end
  are. The record's clock is shifted to where it agrees best (it runs behind the recording's) and the shift is told.
  `--zapis` scores any record of either shape, the service's own file of a day too: **a rule for who speaks is tried
  on the kept days and its score told in the pull request before it runs live; one that lowers a day's score does
  not go in without the maintainer.** The first reading, of the records as the service made them then: 18 Nov 89.0%
  right (293 s under a wrong name, 33 min missing, 33 of 43 speeches found, ends off by 8 s), 19 Nov 29.9% (the
  captions stopped that afternoon; 73 s under a wrong name). A day has no truth until its notes are out and
  `govor` has run: 24 Nov is to be read then. Known limits: a short speech the notes' words could not place counts
  as "extra"; a name the record spells as another MP's is counted wrong, which it is.
- **A day cut where the voice changes, each piece named by its best sign** (25 Nov 2026, the maintainer: "izaberi
  najtačniji metod, da li još nekako možemo poboljšati?"; `live/uzivo/komadi.py`, `ko.named`, the command `glas-dan
  <day> <folder> --uzorci …`). It changes "Faces and voices, only where there are no notes" above: windows alike a voice
  for 20 s no longer make a turn; the sound is cut where the 20 s before and after a place are under 0.65 alike (the least
  alike near), and where no voice is heard for 30 s, and a piece is one speaker's whole: by the caption the live service
  read in it, else the chair's floor-giving in the 45 s before and 12 s after its start (`hronika.floor` on the
  recording's words), else a known voice (0.80 alike, 0.10 ahead of the next). **A caption or a name heard is not taken
  where the voice says otherwise:** the piece is surely another's known voice, or, from 30 s, under 0.60 alike the named
  MP's. A piece of 60 s named by a caption or the chair is that MP's sample from then on. The captions' clock is set
  beside the files' by the sound itself (`clock_shift`). The presiding officers are not named by voice.
  **The face is out:** `check_faces` (a face seen mostly another's dropped a stretch) is gone, on 19 Nov it dropped 1242 s
  of which 1184 were right; a face confirming a doubtful voice is not used either. Samples are taken only of days known by
  the notes or by hand, not from a day whose names are voices'.
  Measured (`tacnost`; seconds right / under a wrong name / missing / extra; voices of earlier days only, so 17 Nov has
  none; the variants measured on 25 Nov first use every other day's voices for 17 and 18 Nov):

  | | 17 Nov | 18 Nov | 19 Nov |
  |---|---|---|---|
  | the live record as made then | 78.9% of 22 min | 89.0%, wrong 293 | 29.9%, wrong 73 |
  | voice alone (`ko.py` until now) | 81.5%, wrong 121 | 65.1%, wrong 177 | 46.7%, wrong 334 |
  | captions, then voice | 81.5%, wrong 121 | 87.7%, wrong 388 | 67.4%, wrong 387 |
  | captions, voice, chair's words (I) | 89.9%, wrong 121 | 89.8%, wrong 411 | 77.5%, wrong 616 |
  | the same, chair's words first (K) | 90.2%, wrong 81 | 89.8%, wrong 416 | 77.6%, wrong 612 |
  | b3's: cut, best sign, 0.62 | 85.0%, wrong 0 | 95.3%, wrong 441 | 90.9%, wrong 1812 |
  | **this rule** | **85.2%, 0/1906/65** | **94.9%, 269/847/528** | **91.4%, 34/2390/794** |
  | this rule, voices of all other days | 99.6%, 2/49/140 | 95.8%, 182/743/1172 | the same |

  Of 18 Nov's 269 s under a wrong name 166 are spellings (112 s Šoškić/Stošić in the old record, 54 s of "Mitev", as the
  notes misspell Petar Mitov). b3's design put 557 s of Balać's under Vučić (a misread caption), 477 s of Stojković's and
  366 s of Tandir's under Bakić (a sample spoilt by a misheard name): the voice's check stops all three.
  **How far it is fitted:** the bars are on the plateau of what 17-19 Nov showed, so they were seen on the days they are
  scored on. Choosing them on two days and scoring the third (108 settings): 99.6% and 2 s wrong on 17, 96.1% and 182 s
  (or 95.2% and 396 s, if a wrong second weighs 1 to 3 right ones) on 18, 91.1% and 51 s on 19. Of
  all 108 (likeness 0.75-0.85, lead 0.05-0.15, unlike 0.5-0.7, cut 0.5-0.7) 19 Nov had 85.0 to 91.7% right, half of them
  under 89.8%, and 32 to 734 s wrong, half of them under 51 s.
  Tried and not kept: the chair's own voice as a known voice (18 Nov: extra 529 to 519 s, 50 right seconds lost; 17 and 19 Nov no
  second changed); the face confirming a voice of 0.60 to 0.80 of a piece nothing named (18 Nov nothing, 19 Nov 74 s right for 7 wrong and 78 extra); score normalisation against the other MPs (s-norm, as-norm, centring; a bar that lets none of 204
  false matches through keeps 78, 75 and 94% of the true seconds, the plain likeness 95%); joining a day's later pieces
  to voices learnt that day (18 Nov: 401 s wrong); trimming a piece's ends to its own voice (18 Nov 0.9 points less right);
  a bar of 0.75 (18 Nov: 1017 s wrong). Not measured: a day whose captions stand for ten seconds (24 Nov: no notes yet),
  and Whisper was told the names of 17-18 Nov's speakers when those recordings were written down.
- **A caption's name of no sitting MP is the near sitting one's** (25 Nov 2026; `cli/recordings._sitting`). In a kept
  record, a caption with a sitting list under it and a name of an MP not sitting (18 Nov, before the service had the new
  list: Šoškić read as Stošić, a former MP) is the sitting MP of that list the name is near by the live page's own matching; a
  minister or a guest has no list under the name and stays as read. Scored with the rule above, voices of earlier days
  only: 17 and 19 Nov unchanged, 18 Nov 94.9 to 95.4% right and 269 to 157 s wrong (54 of them the notes' own "Mitev" for
  Petar Mitov: `govor` run again on 18 Nov would place him, not done here). Of all other days' voices: 182 to 157 s.
- **A day's recording as sound only** (22 Nov 2026): the day pages (`govornici/<date>`) have "Slušaj samo zvuk" and
  the lock screen's player with who speaks, as the live page (`live-sound.md`).
- **The last day's broadcast can be played until the archive's file, while its video is public** (25 Nov 2026, the maintainer, when the
  times had lost their links with the broadcast's end: "Trebamo ostaviti i opciju da klikom na vreme sam odeš na tu poziciju"; on
  the proposal: "Može"). It changes the rule of 18 Nov ("The live broadcast's YouTube video goes private") and of 24 Nov in
  `live-page.md` ("Gone with the broadcast"): measured on 25 Nov, that day's video and 24 Nov's were public, 18 and 19 Nov's
  were not (403, 404), so the rule had dropped links that would have worked for a day. `live/uzivo/prenosi.py`, a thread of
  the measuring: keeps per day the video, when its first second was and from when to when it was read
  (`/data/prenosi/<day>.json`, written whole; a clock that moved by over 20 s is a new row, so a moment is never counted
  across a stop), and, only with no broadcast on and no file of the archive for the day shown, asks YouTube's oEmbed whether the video
  is public: one question in ten minutes at most, kept over a restart. Anything but a clear yes drops the links until the next yes; an answer
  nobody renews is dropped too. With one file of the archive for the day, the archive's places alone, as before. The page's process
  has it from `sada.json` (`citac`). The turns' times, the steps' times, the player's button and a link to a speech take the
  same place; nothing loads before a press but for a link to a speech. A wrong or missing file leaves the page with no links.
- **The files of 24 Nov are placed by what was said, not by captions** (25 Nov 2026; the conductor, when the maintainer
  asked whether the archive is available). Two of five had no place: a caption stands some ten seconds at a turn's start
  that day, a frame is read every 30 s of a file's first hour, and 3 and 4 frames were named. The day's notes were found
  in the files' words (`govor.place`: 164 of 182 MPs' speeches) and each speech's beginning set against its speaker's turn
  in the record; a file begins at the median. The first begins at 11:10:59 (32 speeches, 13 speakers), the fourth at
  17:12:18 (14, 9). The neighbours were a check only: the first ends 1 s before the second begins, the third 2 s before
  the fourth. The picture agrees: the caption's name and the speech's running clock ("0:26" at 28 s of Vujadinović's) in
  ten speeches, one to five a file. A frame of the whole hall, with no caption, says nothing (Đajić, Šćepanović, Tasić
  Knežević and others looked at so).
  - **The other three were off and are corrected by the same measure**: the second by +14 s, the third by +18 s, the
    fifth by -64 s. Their links opened 11 and 14 s into a speech and a minute before it; now 5 s before its first word.
  - Suspected, not proven: since the record's turns begin with the sound, `refine` puts a caption's first frame, some 15
    s into a speech, at the turn's beginning. (It does not explain the fifth's minute.) A file placed by few frames since
    24 Nov is suspect for it: the 25th's, by four.
- **24 Nov is written from the notes** (25 Nov 2026, by the rule of 20 Nov: notes lined up with the sound replace whatever
  the day had). 103 turns of 43 speakers for 95 of 41; 364 minutes for 357; 18 short speeches (147 words) have no place. A
  speaker whose first turn anywhere gives no list (a day before the groups were formed) has the one the list of MPs gives
  now: Vjerica Radeta's would have left her list's sum. 25 Nov waits: its recording is not written down.
- **17 and 19 Nov written again for one speaker's list** (25 Nov 2026, the conductor): only Vjerica Radeta's list changes
  (none before, the list of MPs' now), and the lists' sums with it; every turn, name and time is the same.
- **18 Nov written again: "Петар Митев" is Petar Mitov** (25 Nov 2026, the conductor). The notes write it so once
  (54098/00138), Митов everywhere else; the list of MPs has only Mitov; the broadcast's caption inside that turn (16:30:20)
  is his. No entry by hand: `govor.nearest`, the rule for every name the notes misspell (the one listed name near it,
  clearly nearer than any other; its test has this very name), gives the turn to him; that one turn changes. Not put into
  `data/mp_aliases.json`: the notes' page in Latin would then write "Petar Mitov" over the speech, and the notes stay as
  the Assembly wrote them. Until then the notes' own count of speeches (`debates.resolve`) gives that one speech to nobody.
- **An archive file may be cut inside; its clock is then a stretch's** (25 Nov 2026, found by the live page's worker from YouTube's
  uncut video). The first file of 24 Nov holds the sitting's beginning (from 10:00:39), and at second 735-736 jumps over the
  break to 11:23: placed as one stretch that evening, its first 12 minutes were published 70 minutes late (Milenko Jovanov at
  11:13:15 for 10:02:55) for some two hours. 32 speeches had agreed on one start, and the one that stood far from any of them
  was not looked at. `delovi` in `arhiva.json` gives each stretch its start, `govor.start_at` reads it.
  - **How a file is looked at for a cut:** its words against the service's own transcript of the day, in windows of five minutes:
    one offset all along, or a jump. On 24 and 25 Nov (every file) one offset within 2 s (a last window 7 s), but for this jump.
    On 19 Nov the service wrote almost nothing: the fourth file agrees within 32 s (late by that much), which leaves no
    room for a longer cut in the two before it that it follows without a break; the first agrees with the record's turns
    along its length (some 35 s); the second and the last have only the picture, hall in every frame of their silences.
    18 Nov: the record's turns along each file, and in the first the clock in the picture. 17 Nov: no
    transcript and one record's end; its silences over a minute are one, the anthem and the ceremony in every frame; a cut
    inside speech is not ruled out by anything but the notes, whose speeches are all there in order.
  - Placing by the median alone hides such a part: look at each speech that does not agree.
- **25 Nov is written from the notes, its file placed as the 24th's** (25 Nov 2026, by the rule of 20 Nov; the maintainer had
  the recording written down the same evening). The file begins at 10:03:06, 8 s before where four frames had put it (12
  of 25 speeches agree, 9 speakers; caption and running clock seen in five speeches; in Stevanović's the clock starts 17 s
  after his first words; by the service's transcript 10:03:05, one offset all along, the break in the file). 22 turns of 14 speakers for 14 of 11; the live record had 83.5% of the time under the right name,
  22 s of Vučić's under Aleksandra Štimac's.
- **Two letters exchanged are one slip** (the same day): the notes write АНА БРБАНИЋ once (54098/00948), and `govor.nearest` let
  it by, 0.71 alike in a word of seven letters: a speaker who is nobody, under no list. Exchanged letters count as 0.9 now, for
  every name. Days 17 to 24 come out the same. That it is Ana Brnabić the picture says: the speaker captioned so at 1388 s
  of the file stands at the same microphone, in one shot, through that speech.
- **A shared link may now say another speaker** (measured by `deljenje.turn_at` after the fact for the 24th): of the links the
  live page could have given, 113 of 118 on the 24th and 16 of 18 on the 25th lead to the same speaker. Measure it before a
  day is written again, not after.
- **The live record says what it is** (25 Nov 2026, the maintainer: "može"; 25 Nov's record has a speech of 10:16 the notes gave
  to another speaker). `/dan/<day>.json` carries `"zapis": "uzivo"`: the record as read, never mended by hand, no name taken out;
  and, once the site's day is made from the notes, `"ispravljeno": {"izvor": "beleske", "dan": "<the site's govornici/<day>>"}`,
  by the days the site lists so (`iz_beleski` in `mikrofon-cekanje.json`). Fields for a machine; no sentence of it is shown
  to readers. Who reads the file: `uzivo.pull` (into `data/<N>/uzivo/`, so the copy there gains the fields with the next pull
  of a recent day), `tacnost` and `arhiva` (they read `govori`), and anyone outside.
- **A speech's beginning is not counted back over a hole in the recording's words** (25 Nov 2026, the conductor, from the
  maintainer's reading of the doubtful cases: 18 Nov's Kamberi, Fric and Vučić at 15:45:48 began over the words of the
  speaker before). `govor.place` steps from a speech's first run back to its first word, and from its last run on to its
  last, a word heard for a word of the notes. Where Whisper missed a speech's first words (silence in its words of 28 to 42
  s in all three), that count ran over the chair's words into the speech before. Now it never steps over a hole of more
  than `GAP` (10 s) with no word heard, nor into another speech's runs, and what the recording did not hear is not guessed:
  the speech begins at the first word heard after the hole. The end the same way: it stops at the speaker's last word
  heard, not over applause into the chair's words (18 Nov, Vučić's end at 13:31:52 for 13:32:40). A last run that reaches
  into the next speech's words no longer moves the end on. Measured on 17-25 Nov, old code giving every day byte for byte
  as kept: 26 turns move by over 10 s (starts only later, ends only earlier), 31 by less; 18 Nov 448 s less in all, 24 Nov
  196 s. The live record scored against the days (`tacnost`): 18 Nov 89.0 to 90.3% right and 283 to 190 s under a wrong
  name (the 97 s the doubtful cases blamed on our placing); 24 Nov 92.3 to 92.8%. A `GAP` of 5 and of 20 s was tried
  too: the five cases come out the same in all three (5 moves a few more ends, 20 misses holes of 10 to 20 s).
  **What it costs:** where Whisper missed a speech's first or last words, those seconds are now counted for nobody (they
  are no longer under another speaker's name), so such a speech's time is a little short. The days' totals: 17 Nov 11 s
  less, 18 Nov 448 s, 19 Nov 171 s, 24 Nov 196 s, 25 Nov 2 s. Less is said, nothing false, the same for everyone (the
  conductor, approving it).
- **Applause after a speech's last sentence is not its speaker's time** (26 Nov 2026, the maintainer, of the doubtful
  cases: "zavrsni aplauz se zaista ne racuna u vreme, jedino ako aplauz bude tokom govora samog"; of applause inside a
  speech: "dok ide aplauz vreme i dalje tece za tog govornika"). So a speech ends at its speaker's last word, as `govor`
  does since the rule above; applause, noise, waiting for the hall and the chair's short words inside a speech, after
  which the same speaker goes on, are the speaker's time, one turn ("svo vreme treba biti kartica za tandira"), until the
  chair speaks at length and gives the floor on ("za rec su se javili"). His words in full are kept with the doubtful
  cases (`ko-govori-primeri/ODLUKE-ODRZAVAOCA.md`). How far the day files keep this is measured next.
- **A piece of the same speaker with no place does not end the turn** (26 Nov 2026, the conductor, by the maintainer's
  ruling above: one card "sve dok predsedavajuci ne krene duze da prica"; `govor.day`). One speaker's speeches with only
  the chair's words between them, in one stretch of a file and within `MERGE` (120 s), were one turn, but a piece of the
  same speaker that the recording could not place (too short for two runs) ended it, so a speech broken by the chair's
  short words came out as several turns (19 Nov 24 times, 24 Nov 21, 25 Nov 9; the doubtful case 2.12 is one). Now only
  another speaker's piece ends it. Turns 19 Nov 92 to 81, 24 Nov 103 to 98, 25 Nov 22 to 19; 17 and 18 Nov the same.
  Time +139, +104 and +19 s, all of it the gaps between the joined pieces: the unplaced pieces' own words and the
  chair's short words, no other speaker's (19 Nov Vučić +74, Jovanov, Bakić and Stojković +16 each, Balać +11, Tandir +6;
  24 Nov Vučić +90, Radeta +9, Kokanović +5; 25 Nov Vučić +11, Radeta +10, Đukanović -2 by rounding). Every old link to a
  joined turn's later part now opens the same speaker, from the turn's beginning. The 120 s limit itself is still
  arbitrary.
- **A beginning Whisper missed, from the speaker's timer in the caption: hand readings for now** (26 Nov 2026, the conductor;
  `govor.timer_starts`, `data/15/merac.json`). Where the recording's words have a hole at a speech's beginning, the speech
  begins at the first word heard after it (above), so the seconds Whisper missed counted for nobody. The broadcast's caption
  carries the speaker's own running timer (top right): a frame's second less the timer is the speech's beginning, from the
  source. Of the 7 speeches of 17-25 Nov whose start follows a real hole, it was read for 4 (the 24 Nov 12:21 speech has no
  caption in six frames, and two holes of 2 words were left), **by eye, by a worker, on two frames or more from the
  archive** (ranged reads, no whole file), as the files placed by hand are (`"rucno"`). The readings: Kamberi 0:33 at 6785
  and 0:39 at 6791 (began 6752; our start 6777), Vučić 18 Nov 0:43 and 0:49 (2761; 2796), Vučić 19 Nov 0:27 and 0:33
  (1831; 1869), Vučić 24 Nov 18:44 0:24, 0:30 and 0:38 (1185; 1233). **Fric's, a control with no hole, matched our first
  word to the second** (0:08 at 4101, 0:14 at 4107: 4093). A start is taken only when the caption's name is the notes'
  speaker and two frames or more agree within a second; it only moves earlier, and **never before the last word heard
  before it**: a timer may start before the hole, as the floor is given while the chair still speaks (19 Nov: 9 s of the
  chair's would have gone to Vučić) or run on from the same speaker's speech just before (24 Nov: 20 s of his reply). So
  19 Nov's start is the hole's beginning (1840), and 24 Nov's changes nothing on the page, being inside his turn. The pages:
  Kamberi −24 s, Vučić −35 s (18 Nov) and −29 s (19 Nov) at their beginnings, 88 s returned (89 less a second of rounding);
  nothing else moves, and the old links open the same speakers.
  - **Next, on the runner** (not started): for each such hole, the step that places the archive's files (`arhiva.py`, which
    has ffmpeg and Tesseract there) reads two frames a few seconds after the first word heard, the caption's name by the
    live page's OCR and the timer by a digits-only read, and writes them into `merac.json` (`"procitao": "OCR"`); `govor`
    applies them by the same safeguards, and a reading by hand is kept over one by OCR.
- **A turn ends where the chair gives the floor anew, or the microphone is cut** (26 Nov 2026, the conductor, by the
  maintainer's rulings on the doubtful cases 2.8-2.14, quoted: 2.13 "ovo su tehnicki dva govora - replika i posle kad dobije
  rec - jeste jedna osoba ali su odvojene stavke"; 2.12 "tehnicki i dalje ovo tretiramo kao govor vucica - jer cak i
  predsedavajuci kaze ajde nastavite a i nigde nije oduzimanje reci ili gasenje mikrofona"; 2.10 and 2.11, the speech ends
  when the microphone is cut; 2.9 "govori budu neke upadice, rasprava sa predsedavajucim, ali vreme tece"). One speaker's
  pieces with only the chair between them were one turn within 120 s, so on 24 Nov a reply and the speech in the debate
  after it, the floor given anew between them ("Дајем реч народном посланику Александру Вучићу. … По претресу."), stood as
  one turn of 26 minutes. Now `govor.day` ends a turn, though the same speaker goes on, where the chair's words between
  the pieces hold one of `FLOOR_GIVEN` ("реч има", "има реч", "дајем реч", "реч дајем", "дајем вам реч", "право на
  реплику") or `BREAK` ("пауз"), or where the notes end the speaker's piece before with `CUT` ("искључен микрофон"). Not
  `FLOOR_KEPT`: "има реч, да заврши / да настави" lets the speaker finish (19 Nov 00356, the one false match found). A
  warning, an explanation or an argument while the speaker keeps the floor ends nothing; the 120 s stays until the
  maintainer rules on the chair speaking at length (group 3: on 17 Nov, with no time limit, Hubač's two speeches across
  134 and 166 s of the chair's words would be one). The turns it splits: 19 Nov Dimović 19:27:58 twice (his point of order
  given after his reply, and after "(Искључен микрофон.)" the floor given again); 24 Nov Vučić 17:12:36 ("Даћу вам право
  на реплику") and 18:40:55 (2.13); 25 Nov Vučić 10:11:18 (the floor given to Aleksandra Štimac by mistake, then back) and
  10:50:43 (as representative after the proposals). Turns 19 Nov 81 to 83 (-73 s), 24 Nov 98 to 100 (-84 s), 25 Nov 19 to
  21 (-205 s); 17 and 18 Nov the same. The seconds that leave the speakers are the chair's words between the two parts,
  now counted for nobody. Every old link opens the same turn: they all pointed at a turn's beginning, which stays.
  (Measured first with a pattern that missed the cut microphone by a letter: it gave 19 Nov 82 turns and -57 s.)
- **The bar from the director is the authority for a speech's beginning and length** (26 Nov 2026, the maintainer, of
  2.14: "tehnicki govor ovde krene tek kada rezija stavi traku za govornika mada je i rasprava pre toga bitna i mozemo
  obeleziti kao da je vucic govorio - kada izadje traka iz rezije svakako trebamo osveziti karticu sa time koliko neko
  prica prema tome"). The timer readings above follow it; for the live page it is the live page's worker's part.
- **A very short answer to the chair is no speech** (26 Nov 2026, the maintainer, of case 3.16: "drugu istancu ne bih
  klasifikovao kao govor, samo je odgovor predsedavajucem koji je jako kratak"; of the rule: "slazem se"; `govor._answer`).
  A member's piece of at most `ANSWER` (20) words right after the chair's words that end in a question, where it would end
  a turn or stand alone, is joined to no turn and is no turn of its own. Where the same speaker goes on after it, it stays
  in the turn: inside a speech an exchange with the chair is part of it (2.9, 2.12), and nothing an MP says is left out of
  the record of the speech (the conductor). The notes' pages keep every such piece under its speaker; only the day's turns
  change. On 17-25 Nov seven pieces, -101 s: 17 Nov Jovanov "Не желим." (-13 s); 18 Nov Mitov "Нисам задовољан …" (-35 s)
  and Brnabić "Не желим да се изјасни, али …" (-34 s); 19 Nov Dimović "Да." (-12 s); and three that stood alone, 19 Nov
  Mavrić (4 s) and Đajić (2 s), 25 Nov Mikitišin's "Повреда Пословника, члан 107." (1 s), which the chair refused. An old
  link to Mavrić's 16:30:27 now opens Mitov's turn of 16:30:35; the other two open none.
- **The chair's own words between speeches, as a card of the role** (26 Nov 2026, the maintainer, of case 3.17: "to je
  govor predsedavajuceg"; of 3.15: "nekada mozda treba prepoznati i kada predsedavajuci drzi duzi govor i to isto da
  belezimo"; of the length: "spustio bih prag na 30 sekundi"; and his condition: "ako ubacujemo karticu za
  predsedavajuceg, moramo se postarati da ne razbijamo tudje govore, moramo se postarati da ne oduzimamo vreme pogresnoj
  poslanickoj grupi ako je on clan njen, jer on je predsedavajuci"). `govor.chair_stretches` writes into the day file
  (`"predsedavajuci"`) each stretch of the chair's placed words between two turns, the pieces joined while no member's
  placed piece comes between, cut to the gap between the turns, of `CHAIR_CARD` (30 s) or more; never inside a member's
  turn; a roll call read out is none. The day page shows each among the turns as "Predsedavajući · 2 min 14 s", "Vodi
  sednicu. Ovo vreme ne pripada nijednoj poslaničkoj grupi." (approved): the role, as the notes head it, naming no
  person, in no list's sum and in nobody's time as an MP; a presiding officer who speaks from the floor that day keeps
  that as his own turn under his group, and nothing moves between them. With no `data-od`, a shared link or the player's
  ⏮ ⏭ never lands on one. The page's "između govora" sum and "Predsedavajući nema potpis i nije uračunat" stay as they
  are, still true. **The card's length is the seconds the chair is heard**, from the first word to the last, less every
  silence of over 10 s (`GAP`: a minute of silence, a quorum count, a vote, the start of a break), so it can be shorter
  than the card's span (from–to); a stretch heard under 30 s is no card (the conductor, after measuring: 7 of 76 spans
  were more than half silence, e.g. 19 Nov 18:05:54 "Проглашавам паузу од десет минута." 86%, 25 Nov 10:07:04 a minute of
  silence 77%). On 17-25 Nov: 9, 14, 21, 17 and 10 cards, 8,436 s heard; every turn the same. Inside a member's speech
  (3.18) the maintainer has not chosen: "ovo zavisi da li predsedavajuci vraca vreme ili ne".

