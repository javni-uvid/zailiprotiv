# The live page: how it looks

Decisions about the live page `mikrofon.zailiprotiv.rs` and its service: the order of things, the speaker's box, the cards, colours, words. Moved word for word from
`live/AGENTS.md` on 23 Nov 2026 (it had grown to 77 KB, read whole by every agent working in `live/`); what holds now,
in short, is there. **Keep it current:** a decision is added at the end of this file, in the same commit, and one that
changes an earlier one says so. Dates are the maintainer's decisions unless said otherwise.

**Changed since written:** Read it from the end: "A shorter page between sittings", "The day back on the line of time" and "Colour where it means something" (22 Nov) are how the page is now; "The day in one sentence", "The day is one list" and parts of "The first screen" stand as how it came to be.

- **A page of its own at `mikrofon.zailiprotiv.rs`** (17 Nov 2026): who is speaking in the Assembly now, and who spoke
  today, read from the caption under the speaker in the live broadcast (README in `live/`). It grew out of the
  maintainer's page following one speaker; under the project it follows **every speaker by one rule** (principle
  1): nobody is followed, singled out or ranked; today's turns are listed by time.
- **Visits counted as on the site** (18 Nov 2026, the maintainer's decision, once the page became the site's main way
  in): the live page carries the site's Cloudflare Web Analytics beacon (principle 5's first exception), its token
  read from `data/settings.json` copied into the image (`config.ANALYTICS_TOKEN`; `ANALYTICS_TOKEN=` empty turns it
  off); the footer says so. Until then only the site's page shown while the service is down was counted.
- **Nothing from elsewhere** (principle 5): the fonts are copied from `src/zailiprotiv/static/fonts` into the image,
  the one script is inline; the site's MP pages are linked.
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
- **The live page for a keyboard and a screen reader** (20 Nov 2026, after the same look the site had). The page's
  part is replaced whole every five seconds, which took the keyboard's place away each time: the thing that had
  the focus (the same kind, the same one in order) has it again after the replacement. A line outside that part
  (`#ko`, `aria-live`, not shown) says the new speaker's name and list once when they change. "Dan u karticama"
  opens onto its close button, gives the focus back, and does not turn its cards by the clock for a reader who
  asked for less motion. No letters under 12 px; the "next line" button is 32 px high. The archive is named
  "Videonet", not by its address, which the Cyrillic page wrote in Cyrillic letters.
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
- **The live page on the site's scale, its earlier turns folded** (20 Nov 2026, the maintainer's choice, with the
  same points for the site, after a look at the design). The page had twenty sizes of letters, a third of the text
  in 14.4 px grey; it now uses the site's eight steps (`--t-1` … `--t-8` and three for titles, in `page.CSS` and
  the shared `mikrofon.css`; a test checks that no other size is written). Between sittings half of a phone's ten
  screens was the list of the day's turns: the latest eight stand (`page.TURNS_SHOWN`), the earlier ones are folded
  under them and open by themselves when the day's strip or an address leads to one. Left as it is: the day's
  four numbers have nothing beside them to compare with (the service has no other day's sums; the sentence above
  them and the speaker's clock already compare).
- **The first list's colour is indigo** (20 Nov 2026, with the site: its blue stood too near the blue of "za" on
  the home page, and the two pages wear the same hues): `--c-av` and `page.HEX["c-av"]` are #3730a3 (#818cf8 in
  the dark theme); the pictures take it from `HEX`.
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
- **"Podrži sajt" on the page** (22 Nov 2026, the maintainer): a box like the Rules' above the link to the site,
  leading to the site's `podrzi` (`support_cta`, `support_sub`).
- **The site's mark on the home screen, no microphone in the header, "Podrži sajt" on top** (22 Nov 2026, the
  maintainer: the microphone "looked too like a Google logo"). The home-screen icons (`picture.icon`) are the site's
  own mark, the two arcs of `favicon.svg`, as the site's apple-touch-icon; the header keeps the site's name and
  "Podrži sajt" beside the script's switch, and the microphone mark is gone from the page. A phone that added the
  page before keeps the old icon until it is added again.
- **Before a sitting a pasted link announces it** (23 Nov 2026, the maintainer, before a post on Reddit: a link showed
  who spoke how long on the last day, the hook he had dropped). While nobody is on the air and the Assembly's notice
  names a day and an hour still to come (`page.announced`), the link's title and line and its picture say when the
  Assembly goes on, the item next on the agenda and what the page gives then; the picture's address changes with it
  (`?v=najava-…`). From that hour on the notice is no news, on the page's top either: the evening of a sitting would
  have said it goes on that morning. `page._now` is the clock, so that tests name their own day.
- **The two offers say what they give, with a mark each** (23 Nov 2026, the maintainer: that "Dodaj na početni ekran" means
  having the page as an app was not said). "Mikrofon kao aplikacija", with the app's own tile as it will stand among
  the others and "Dodaj na početni ekran: ikonica pored ostalih, bez prodavnice."; "Obavesti me kad sednica počne" with
  a bell and "I kad sažetak dana bude spreman." (the same address gets both). The iPhone's line opens with the mark of
  Safari's "Podeli". Icons are lines in the page itself; nothing is loaded.
