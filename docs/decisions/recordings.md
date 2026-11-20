# Broadcasts and recordings

Decisions about the broadcasts and recordings on the site; the live service's own are in live/AGENTS.md, moved word
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
(`live/edge/`). **Its decisions are in `live/AGENTS.md`** (20 Nov 2026: moved there, as this file had grown to
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
  tested one, never live: YuNet and SFace for faces, 3D-Speaker's ERes2Net through sherpa-onnx for voices; only the
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
  `live/AGENTS.md` ("The model tells the day's steps"). The key is in `live/.env` only.
