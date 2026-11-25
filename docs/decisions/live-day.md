# The live page: what happened in the day

Decisions about the live page `mikrofon.zailiprotiv.rs` and its service: the day's steps, the agenda, the model's steps and summary, the groups' time. Moved word for word from
`live/AGENTS.md` on 23 Nov 2026 (it had grown to 77 KB, read whole by every agent working in `live/`); what holds now,
in short, is there. **Keep it current:** a decision is added at the end of this file, in the same commit, and one that
changes an earlier one says so. Dates are the maintainer's decisions unless said otherwise.

**Changed since written:** How the day looks on the page is in `live-page.md` ("The day back on the line of time", 22 Nov); the Assembly's sentences folded under the line (20 Nov) are no longer there. "Nothing summed up by a model" (19 Nov): the model tells the steps and sums the day up since 20 Nov.

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
- **The day's steps follow the order of the Assembly's work** (20 Nov 2026, the maintainer's request: "a vote
  cannot be closed before it began"). Within an agenda item (`page._in_order`): the debate is opened once and before
  it is closed (an item taken up with "nastavljamo pretres" counts as opened); a vote is closed only after one was
  put, and "put to the vote" while one is open is that vote (19 Nov: the roll call after the decision to vote by
  roll call); steps said in the same second are taken as an item, then its debate, then its vote (`_PHASE`). These
  steps are no longer cut to one a quarter of an hour: three votes in five minutes (19 Nov, 22:19–22:24) are three.
  A vote's result closes it ("za je glasalo", "glasalo je 97", "dobio je … glasova"), and "pristupili glasanju" in
  a result no longer reads as a vote begun; a kept step is shown under the name today's rules give it.
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
  **Small, under the speaker, since 24 Nov 2026** (the maintainer, in place of the box under the steps, off the page
  for an hour before): a line and a thin bar a group with what is left, the label "procena" and no other words; how it
  is counted is under "Kako ovo radi"; gone once the debate is closed. Counted from the debate's opening: a point of
  order before it had been counted that day. That day the chair told the same rule for the election of the committees
  (five hours, art. 97; art. 24, 192, 193), whose one debate has none in detail. `VREME_GRUPA_PRIKAZ=0` takes it off.
- **A step is the chair's word, never an MP's** (24 Nov 2026, the maintainer, when "Izbor: gospodina Mavrića i Saru
  Valentika" stood on the page with no vote held: an MP at the rostrum had told what the proposal of the committees
  held). `steps._mps_words`: a model's step whose sentence falls more than 30 s inside an MP's turn is none, but for a
  measure, which comes in the middle of a turn, and the giving of the floor. The prompts say the same. Of the 53 steps
  of 19 Nov the rule drops one, a move to an item an MP spoke of. Measures an MP only spoke of are still kept
  (four that day) and are to be judged apart.
- **A reply longer than two minutes is not the group's time** (24 Nov 2026): one of 142 s had been counted. A turn heard to
  be a reply or a point of order (`rok.short`) is left out up to 180 s.
- **The groups' time, checked against the day's turns** (24 Nov 2026, the maintainer: "proveri da li je tačna
  informacija koliko koja lista ima vremena"; the page said 7 minutes left for one list while its MPs kept getting the
  floor). The frame held: the chair told the same five hours by art. 97 at the debate's opening. Two things counted
  too much, both mended by one rule for every group. **The chair's "po kom osnovu?"** when giving the floor tells a
  reply or a point of order as the words themselves do (`rok._BASIS`, for the groups' time only; the clock by the
  speaker still wants the kind heard): four turns of 126 to 145 s had been the group's. **The representative's 20
  minutes** (art. 96) are apart from the group's time by the Assembly's own clock, as its notes show ("iskoristili ste
  vreme ovlašćenog predstavnika. Imate još od vremena grupe 7,24"); we do not hear which turn uses them, so each
  group has them added to its share (`vreme.REPRESENTATIVE`), as the 15 minutes of the debate in detail are. Still
  not known: a reply let run past three minutes, one with no word of the chair's heard, two short replies in a row
  shown as one turn (`MERGE_SECONDS`); the Assembly said no figure that day to check the sum against.
- **The time the chair says is where the count goes on from** (24 Nov 2026, the maintainer the same evening: the
  groups' time is to be measured as carefully as who speaks). At 18:43:40 the chair gave the floor with "po pretresu,
  sad ću vam reći vreme, 23 minuta 21 sekunda"; our count for that list stood at 3 minutes left and a quarter of an
  hour later at "preko za 16 min", while the MP still spoke by the Assembly's clock: 20 minutes too much counted.
  `vreme.told`: a piece of the chair's that gives one sitting MP the floor and says the time left (minutes with
  seconds, or minutes after "još"/"preostalo"; three minutes at the least, no more than the group can have) sets
  that group's count: what was said, less its turns since. The Assembly's own figure, so it stands over ours; the
  row carries `receno` (when, how much). The other check found the same day, in the notes of 19 Nov ("Osamnaest
  minuta imate još", the debate on the vice-presidents): by the notes' words, the group's speeches but for the
  proposer's and the replies come to 100-116 minutes (150-130 words a minute) against 108 by the chair's word, so
  the rule counts the right speeches; counted in seconds of the record it was far over, the placed speeches holding
  the chair's interruptions and the hall's noise too. Of a turn that began before the word (the page joins a
  speaker's turns two minutes apart) the part after it counts: put live without that, the list stood at the whole
  23 minutes while its MP had spoken them. **The proposer's word is none of the group's time, an MP's too**
  (`rok.proposer`: the chair gives the floor "predlagaču"; art. 96, and the check on 19 Nov's notes above: with the
  proposer's speeches the sum is 130-150 minutes, far over the chair's figure). **Our own count at the moment of the
  chair's figure is kept beside it** (`receno.nase`, in `/stanje.json`): each such word is a reading of how far off
  the estimate runs (24 Nov: ours about 3 minutes, the chair's 23:21). Open: how our seconds run over the Assembly's clock (which
  stops when the microphone does), to be measured on the kept days.
- **A measure an MP only speaks of is no step** (24 Nov 2026, the maintainer): the mail's rule (`mere.given`) holds for the
  page's steps too. On 19 Nov's 13 model's measures it keeps the eight given and drops the five not.
- **A warning with its reason, by the Rules' list** (24 Nov 2026, the maintainer, of three ways shown to make "Šta se
  desilo danas" fuller once the transcript's sentences were off: "uradi samo 2"). `mere.reason`: where the sentence that
  gives the measure says exactly one of the reasons art. 109 lists (at the rostrum without leave, speaking without the
  floor, off the item, heckling, addressing another MP, insults, private life), the step says it in our words ("zbog
  govora bez date reči"), never the transcript's; none heard, or two, and nothing is said. By rule, not by the model:
  a set list, the same for everybody, and a misheard word cannot come out. The chair saying the measure again with
  its reason within a minute (`WHY_SOON`) is the same step; a measure for another reason is another. Of the 13
  measures given on 19 and 24 Nov five have a reason, each read against its sentence. To whom is as before (a name
  the sentence bears). "Kako ovo radi" says so.
- **The day's summary, and so the mail, by a stronger model from the whole transcript** (24 Nov 2026, the maintainer:
  "držimo haiku u toku sednice, kada pravimo sažetak za mejl to ide preko opusa"). Haiku's line on one MP that day said
  the opposite of what was said, and the day's summary, made of the stretches' summaries, would only have copied it. Now
  `sudija._whole` sends the day's whole transcript to `DAY_MODEL` (Claude Opus 5.5; `DAN_MODEL` empty turns it off)
  once, after the sitting (END_QUIET), in place of the call on the stretches; the steps and the breaks' summaries stay
  Haiku's. Each speaker's line must rest on a sentence of their own, copied word for word and found by the code in their
  turns (`sudija.unsupported`); a reply that fails is asked once more, and a line whose sentence is still not found
  stays, marked to the maintainer. The sentences are in `/data/osnova` and on top of the maintainer's own mail, never on
  a page or in a reader's mail (the automatic transcript is never a quote). Finding the sentence does not prove the line
  says the same: the maintainer reads it before the click. When the call fails or the summary names a speaker or a
  number wrongly twice, the day is told from the stretches as before and the maintainer's mail says so. What wrote it is
  kept (`model`) and said on the live page and the day page. Measured 24 Nov to 14:10: 62,688 tokens; a day costs some
  0.8-1.6 $ by estimate (the output not measured).
- **"Rad je nastavljen" after a break** (24 Nov 2026, the cycle's finding: the model told no end of the break to 15:10): where no
  step was told within five minutes of it, at the chair's words that move the work on or the first turn after the break. And
  a turn found by the chair's words alone, under five seconds, is none (`counted`): the floor passed on at once.
- **Words in the steps** (24 Nov 2026): see `live-page.md`, "The page as the maintainer chose it".
- **A day ends after a restart too** (24 Nov 2026): the service was restarted two minutes after the broadcast ended, so it had
  read no frame of it, and `_summaries` took "no frame" for now: the day never ended, no summary and no mail. With no
  frame known it is END_QUIET after the last word written down, and after the run began (so a restart in a break does
  not end the day).
- **An earlier copy of the service's own day does not take its place** (24 Nov 2026, the cycle's finding; `state_view._older`):
  between sittings the page lists the day the site holds; while that is the service's own record copied by the data run
  ("izvor": "uzivo") and ends over two minutes before the record does now, the record stands. After the sitting the copy of
  17:56 was on the page, 33 turns short and with a name corrected at 18:10, and the next copy was hours away (the run
  takes an hour and a half, and one was waiting behind another). A day read from the whole recording stands as before.
- **The day's summary sooner** (24 Nov 2026, the maintainer: can the mail be made faster; that evening it came 50 minutes
  after the end, three restarts each beginning the 20 minutes anew). When the chair closed the day's work (the model's
  "Kraj rada", nobody at the rostrum and under 40 words after it) and the broadcast is off, the day ends after `CLOSED_QUIET`
  (3 min); otherwise after END_QUIET as before, so a break is not taken for the end. The wait counts from the last frame kept
  with the day (`Tracker.frame_before`), whatever restarts come after. Agreed among the sessions too: nothing is put live
  between a sitting's end and the day's mail.
- **A summary already in the day's file is taken, not written again** (24 Nov 2026, the maintainer): the service kept the day
  in memory, so a summary made by hand while it ran would have been written over at the day's end. Before the model is
  asked for the day, the file is read (`Judge._written`).
- **The record that stands keeps the archive's files** (24 Nov 2026, the maintainer asked why the recordings had gone;
  `state_view._filed`): with the earlier copy set aside the page had no file of the archive and no "▶" beside a turn (the
  broadcast's video is private once it ends). The files the site's copy knows are shown, and each turn begun inside one
  has its place in it; a turn outside them has no link until the site has read that part.
- **The whole day's reply has room** (24 Nov 2026): the first real call was cut off at 32,000 tokens (effort "high", 39 speakers
  with their sentences), so that evening's summary and mail were Haiku's from the stretches, with the wrong line the change was
  made for. Now 100,000 and "medium": tried by hand on that day, 152,000 tokens in and 20,000 out a call, two calls (a number not
  in the transcript the first time), 5.5 minutes. A measure's name only when the chair said it in giving it.
- **The groups' time is said to be a rough estimate** (25 Nov 2026, the maintainer, asked whether to show it only once the
  chair's own figure confirms it: "ne, samo izrazi da je gruba procena"). On 24 Nov our count stood 20 minutes off the
  chair's 23:21. The label is "gruba procena", and "Kako ovo radi" says it may be off by some twenty minutes.
- **The chair's own figure stands under a group's time** (25 Nov 2026, the maintainer: "može"): "predsedavajući u 18:43:
  još 23 min 21 s" under the bar of the group it was said for (`receno`), so the reader sees what the estimate goes
  on from and when that was. "Kako ovo radi" says so.
- **The next sitting is announced from the Assembly's listing, one begun by the same rule as one convened** (25 Nov 2026, the
  maintainer: "Zašto automatski ne pripremamo stranicu prema skupštinskom kalendaru?"). That morning the page said
  only "Ne zaseda" an hour before the first sitting went on; why the listing missed it and where it is read from now is in
  `data.md` ("When a sitting already begun goes on"). `sazvano` in `mikrofon-cekanje.json` carries such a sitting too (`"nastavak": true`,
  no agenda of its own). The card on top, the link's line and picture, which came only from the notice by hand, come from `sazvano` as well
  (`page.announcement`, the nearest still to come); a convened sitting's card has its own first items and says
  "Skupština u …", as it goes on with nothing. Where the card says it, the countdown stands only for what it adds: a
  convened sitting's agenda, a day with no hour, the hour come and no broadcast yet; of a sitting begun it is called
  "Nastavak sednice". Once a frame was read since its hour it is nobody's next sitting (`state_view._begun`): in the
  break and on the evening the page would have said "Počinje uskoro". The notice by hand stays for what the Assembly
  has decided, and for a day said in words `skupstina.continues` does not read; "nastavlja rad …, sa početkom u", the
  words of that morning, put the card on top too. How fast: **votes** reads the page hourly (6:47 to 22:47), a build takes 8
  minutes or twice that behind another, the service takes the file every ten: between 20 and 90 minutes; on a
  sitting's evening a run waits for the one before it to end, so up to some two and a half hours.
- **Each sitting has its own agenda, and its own item heard** (25 Nov 2026, found before the Second sitting). The page took the
  first agenda in the site's list for everything, and `tacka.json` (the last item heard) only goes up and is kept across days:
  with the Second sitting listed, its items 1 to 5 would have stood as done by the chair's word before it began, and the First's
  last day would have named its steps by the Second's items. Now the sitting of a day is the latest convened for it or before
  (`Tracker._sitting`, `pocinje` from the site); an item heard counts only at the sitting it was heard at; the page shows, between sittings,
  the agenda of the one convened next, and the steps of the day shown keep that day's (`dnevni_red_dana`). Two sittings
  begun on one day are not told apart. The Assembly's page is read during a broadcast only of the sitting last begun
  and those to come (`read_live`).
- **"Nastavak sednice sutra" is the day's end, not a break** (25 Nov 2026, the conductor; found on 24 Nov 19:29). The rule on
  the chair's words took any "nastavak sednice" and "nastavljamo sutra" for "Pauza"; with "sutra" it is "Kraj rada" now, with
  the page's own words for it ("Kraj rada za danas"), shown as before only when nobody is at the rostrum for four minutes
  after. A day of steps with no model step, kept before, is read again by it. The rule is loaded by both containers: what
  it notes while a sitting is on changes with the measuring's release. The model called the same sentence "Nastavak rada":
  its own text, left. A break said with an hour or a length stays one.
