# The live page: who is speaking

Decisions about the live page `mikrofon.zailiprotiv.rs` and its service: the caption, the chair's words, the voice, who presides. Moved word for word from
`live/AGENTS.md` on 23 Nov 2026 (it had grown to 77 KB, read whole by every agent working in `live/`); what holds now,
in short, is there. **Keep it current:** a decision is added at the end of this file, in the same commit, and one that
changes an earlier one says so. Dates are the maintainer's decisions unless said otherwise.

**Changed since written:** "Reč ima …" (19 Nov): time is now counted from it ("Who speaks without a caption", 22 Nov).

- **Read from the broadcast, matched to the roll calls:** a name counts when it matches an MP on the site's list
  (`podaci.json`, from the roll calls) on the caption's name line only, never the list line under it (a list's name
  often holds its leader's name). A name not on the list (ministers, guests) is shown only when read surely in two
  frames in a row; a half-read name is never shown. The page says it is read automatically and may err.
- **A name with nothing under it** (19 Nov 2026): the live page listed two turns of an MP who had not spoken, each
  read in two frames with no second line. `state.counted`: a turn goes into the day's list when read in two frames
  or more and either the line under the name (the list or office, which every real caption has) was read at least
  once, or it lasted four frames or more; the day's record gives a turn not counted as one frame, which the site
  drops. The same rule for every name.
- **Chance readings during a break** (19 Nov 2026: one MP's name kept flashing as the speaker while nobody was on
  the screen). Two causes, both mended. In `names.Roster` one word read could stand for two words of a name
  ("Сара" was both "Sarag" and "Sarah"): each word of the name now needs a word of its own (`_pair`). And in
  `Tracker.observe` a name with no line read under it, like a name not on the list, is taken only on its second
  frame in a row (within `HOLD_SECONDS`), the turn then counted from the first of the two; a whole caption, with its
  list or office, is taken at once as before.
- **"Reč ima: …" from the chair's words, while the picture names nobody** (19 Nov 2026: that afternoon the
  broadcast showed no captions at all, the frame checked). `hronika.floor`: after "reč ima" / "ima reč" the next
  seven words must name one sitting MP: every word of the name whole but for diacritics, or, as a guess the
  maintainer allowed after that phrase, the clearly nearest MP by every word of the name (`FLOOR_NEAR`,
  `FLOOR_CLEAR`; "Jova Bakič", "Krko Babić"), or a surname alone that only one MP has, right after a title
  ("kolega Jovanov") and never after a given name we do not know. Two MPs fitting: nobody. Shown in the day's steps as a lighter line with a link to the MP's page, and not where a turn read from
  the picture stands. No time at the rostrum is counted from it (the end of the speech is not known), and nobody
  is ever named from a face.
- **The chair gives the floor in more words than "reč ima"** (20 Nov 2026, the maintainer's request): Whisper writes
  it as one word ("Rečima narodna poslanica …"), and the chair also says "dajem reč", "pravo na repliku ima", or a
  title after "replika", "povreda Poslovnika", "izvolite", "sledeći je" (`hronika._FLOOR`); "replika gospodinu X"
  names whom it answers and is not taken.
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
**The presiding officers never named by voice, by their addresses** (22 Nov 2026, found while replaying 19 Nov). The
list (`GLAS_BEZ`) was compared with the list's names, which put the surname first, so it would never have matched,
and two of its names were wrong (the first sitting was chaired by Stojan Radenović and Nada Macura). It is now the
MPs' addresses on the site, as the voices are kept: `cupic-aleksandar`, the six deputies, `radenovic-stojan`,
`macura-nada`. None of them had a voice sample yet, so nothing was named wrongly.
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
- **No box under the speaker** (24 Nov 2026, the maintainer: needless): the day's numbers, the lines about the MP with
  their turning, the way to the page and the pictures to share are off; the name, list, clock and the words being said
  stay, and the name is the way to the MP's page. The counts behind it (`danas`, `saziv`, `duze`) stay in `stanje.json`.
- **How long the turn may last, where heard** (24 Nov 2026, the maintainer; `rok.py`): a reply or a point of order has two
  minutes (art. 103, 104), told by the chair's words when giving the floor or the speaker's first ones; "/ 2 min ·
  replika" by the clock, "povreda Poslovnika", or the minutes alone when both words are heard; gone half a minute past
  the limit. Other turns have none we know. On 24 Nov's first 18 turns: nine told, all of
  136 s or less, and none of the three of 206 to 578 s; of the short ones not told some were cut in two by a reading.
- **The caption of 24 Nov 2026** (the maintainer asked why no name was read; checked on the broadcast's frames): two
  lines of white letters with a dark ring and a light one, for about ten seconds at a turn's start, higher than before
  (0.81 to 0.94 of the height; the crop begins at 0.86), so the name line was cut off and only the list came through.
  `ocr.outlined` reads that place too when the first reading names nobody, at two sizes after taking the light ring off;
  it counts only a sitting MP whose own list is under the name (`caption.sure`); a list read alone names nobody: of
  120 frames after the chair's words the old crop read Vučić in two captions of other MPs of the list (one frame each,
  so no turn came of it). It is taken as found, like
  the chair's words (`heard`, "potpis"), since it goes after ten seconds and the turn goes on. On those frames it named
  eight turns' speakers (12 readings), none wrong. Each caption's clock ("0:15") is not read.
- **A voice that ended before the floor passed on** (24 Nov): the windows lag, so the last seconds of the speaker before
  came after the chair's "reč ima" and ended the new turn in its first second (12:18:54). Such a voice now only
  lengthens the turn it was of (`Tracker.heard`).
- **"(po glasu)" off the presiding line** (24 Nov, the maintainer): how it is known is under "Kako ovo radi".
- **"prepoznavanje govornika može da pogreši"**, small, in place of the sentence on how the speaker was known (24 Nov 2026,
  the maintainer); how is under "Kako ovo radi". A name read off a caption has no such line.
- **Who speaks is known for too few voices** (24 Nov 2026, the maintainer: "dosta slabo nam radi prepoznavanje po glasu";
  measured by then: 30 of 250 MPs, 77% of the day's words in a turn, eleven minutes of one MP's in none). Voices are
  learnt only from captions, and no caption was read until `ocr.outlined`: the windows of `natpis` seconds on are learnt
  too (`LEARN_ON`). The chair's "ima narodni poslanik X" at a piece's beginning gives the floor (`hronika._FLOOR`), and so
  does a given name heard whole with the surname near (`GIVEN_SURNAME`).
- **A turn is not ended because its speaker's voice was not recognised** (24 Nov 2026, the maintainer: "popravi sve te
  stvari"): `voice_gone` took anyone whose voice is on the list as known, so a speaker named by a caption or the chair's
  words, whose voice was not recognised, had 0 s (Andrić 14:02, 80 s), 9 s and 15 s. Only a voice recognised in the turn counts.
- **The day's record filled by one rule** (`popuna.py`, by hand, the service stopped, the file kept beside as it was): where the
  chair gave the floor by name, the turn runs to the next floor given or another's turn, if less than 0.4 of it
  is there and at least 45 s are missing (25 s for a turn not there at all); the rest is left as it was, as the chair's own
  words stand before the next floor. Run on 24 Nov for what had been missed before that day's fixes.
- **"Zlatko Kokanović, reč. Izvolite."** gives the floor (the name before the word, only with "izvolite" after it).
- **The day's whole look-over of 24 Nov** (the maintainer: "napravi ciklus u kojem ćeš ispravljati sve nepravilnosti"): the
  floor given right after "povredu poslovnika, Ime Prezime" (whole words) and by "prvo dajem Ime Prezime"; no turn runs
  into the next; the archive's reading (`arhiva.reader`) reads the caption of 24 Nov too, else tomorrow's placing of
  the day's recording would have named nobody; a restart waits for the chair's words to end too (`mikrofon.ps1`,
  `titl`); and `popuna --reci` adds words a restart missed, as Whisper wrote them from the broadcast.
- **The broadcast's clock beside the caption** (24 Nov 2026, the maintainer: "1, 2 i 3 odmah"; `ocr.clock`, `Tracker.clocked`):
  "0:15", how long the turn has gone on, so when it began; the chair's words had put starts 30 s early or 15 s late. Two
  of four readings agree, and two frames' within 3 s. On 120 frames 36 were read, all in order with the time. Read
  only with a caption read (four OCR passes).
- **Voices of 19 November** (24 Nov 2026): from the notes lined up with that day's recording (`govor`), 16 MPs not known
  before; the samples of the windows within each turn, the stray ones left out. A turn held out and named by the others'
  voices: 126 right, none wrong, 3 undecided (44 MPs, 144 turns of the three days). `/data/glasovi.npz` then 51 MPs.
- **The same speaker named again after speech that went on is the same turn** (24 Nov 2026, the cycle's finding: Aleksandra
  Ilić's speech cut in two, 139 s nobody's): within 200 s, at least 1.2 words a second written down between, no floor given to
  another (`Tracker._went_on`). A voice not recognised or the chair's had ended it.
  Not when a word only the chair says is between (`CHAIRS`), nor a floor passed on by name before the next begins: a dry run
  over the day had joined 104 s of the chair's to the next speaker and given one MP 63 s of the chair's. Neither was live.
- **A voice known from under 20 windows (30 s) is not used** (24 Nov 2026, the cycle's finding; `glas.LEAST`): Milena
  Đorđijević's, known from two windows of the same speech, matched those seconds and then no more, and a speech of ten minutes
  ended at 56 s. Of the 55 voices known ten had 2–16 windows, most of them of the speeches cut short that day. The
  windows go on being gathered; until then the turn goes as of a voice not known.
- **The broadcast's clock joins a speech cut in two** (24 Nov 2026, the maintainer: "iz režije bio sat … ali mi nismo
  ispravili od kad je govorila"). Milena Đorđijević had the floor from 16:57 and on; her turn ended at 16:57:46 (a caption
  gone, nothing naming her) and began again at 17:08:32, 646 s of it nobody's. `ocr.clock` had read 11:15, 11:21 and 11:26, right, and
  `Tracker.clocked` threw them away: more than two minutes were not believed. Two readings that agree and say the speech
  began within the same speaker's turn before (`CLOCK_JOIN`), no other's turn between, make one turn of them.
- **The chair's pieces inside a mended turn are its speaker's** (24 Nov 2026, with the joining above): a piece written down
  while the turn was cut is kept under the chair's key, so the day's summary (`sudija.lines`, the whole day's) and the
  topic (`rezimei.spoken`) would have read the MP's words as the chair's. Well inside the turn and with no word only the
  chair says, it is the speaker's (`state_base.speakers_own`). The kept transcript is not changed.
- **And joined once the words between are written** (24 Nov 2026, the maintainer, of Vjerica Radeta: "popravi po istom
  principu"): the same speaker found again by voice 14 s after her turn's end began a new one, as the words between
  come half a minute later and `_went_on` had nothing to judge by. After each piece of the transcript the last two turns are
  judged by the same rule (`Tracker._mend`): within 200 s, at least 1.2 words a second, no word only the chair says, no
  floor given to another.
- **A voice merely alike another does not take the floor** (24 Nov 2026, the cycle's finding; `glas.JUMP`): Nikola Selaković's,
  not yet known, was some 0.58 like Miroslav Petrašinović's through the whole speech and 0.68 for 24 s, which stood as Petrašinović's.
  In a turn whose own voice is not known, another's is taken only when the sound is liker it than the turn's before was,
  by 0.12; the chair's too. Tried on 17–19 Nov (142 speeches of 44 MPs): no real change of 83 refused, the one false
  change refused; on the broadcast's own sound of 17:24–17:26 the likeness grew by 0.07 at most.
