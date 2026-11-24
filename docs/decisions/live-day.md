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
