# The live page: the automatic transcript

Decisions about the live page `mikrofon.zailiprotiv.rs` and its service: Whisper, what is written down and kept, its corrections, the line under the picture. Moved word for word from
`live/AGENTS.md` on 23 Nov 2026 (it had grown to 77 KB, read whole by every agent working in `live/`); what holds now,
in short, is there. **Keep it current:** a decision is added at the end of this file, in the same commit, and one that
changes an earlier one says so. Dates are the maintainer's decisions unless said otherwise.

**Changed since written:** "What is being said" (19 Nov): the transcript is written down but not shown (the same day); only the line under the picture is on the page (22 Nov). The second reading by a
better model ("Corrections …", 19 Nov) is gone (23 Nov).

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
- **Trying another Whisper model** without touching the service: `python -m uzivo.proba <model> [seconds]` in the
  container (`live/uzivo/proba.py`) listens to the kept sound, writes it down with the running model and the named
  one, and prints the time and the text of each. It shares the processor with the service while it runs.
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
- **The second reading is gone** (23 Nov 2026, the maintainer's choice among the points of an analysis): since 20 Nov
  `large-v3-turbo` is the one model, so the better one's reading of a finished turn (`WHISPER_FINAL_MODEL`,
  `step_whole`, `say_whole`, the keys `k<second>`, `prepis_ceo` in the snapshot) could not run. Nothing that could be
  seen changed: every page and file the service writes for a made-up day compared before and after.
- **The sound not written down yet is on the volume** (24 Nov 2026, the cycle's finding): it was in the container's /tmp, so
  each restart lost the seconds not transcribed (the break to 15:10 was lost so). `SOUND_PATH=/data/zvuk`; a piece is deleted as
  soon as it is written down, and what a run left behind is taken up unless over 15 minutes old. A restart waits 20 s after a
  turn's end at most (`mikrofon.ps1`).
