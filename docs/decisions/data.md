# The data: sources, laws, debates, convocations

Decisions about where the data come from and how they are read, moved word for word from AGENTS.md on 20 Nov 2026
(the maintainer's decision, so that an agent reads the rules and only the decisions of the part it works on). **Keep
it current:** a decision made or changed is added here, at the end of the section it belongs to, in the same commit
as the change. The principles and the rules of work are in AGENTS.md.

## Source: the Assembly's site

- **Roll calls** are PDFs: under `/upload/rezultati_glasanja/` since autumn 2025 (`2026/20.pdf`,
  `2026/osma_sednica/1.pdf`), before that under `/upload/archive/files/cir/doc/Listinzi/<year>/`. Names are
  irregular, so a vote is known by its link, never by a name built from a pattern.
- **Only the Cyrillic sitting pages** (`….43.html`) link each agenda item to its roll call; the Latin ones (`.941`)
  don't. The current convocation's sittings are listed on two Cyrillic pages (regular `.34`, extraordinary `.35`)
  whose margins carry other news too: a sitting is a `.43.html` link naming a sitting or session. **Earlier
  convocations** are on Latin archive pages (`?offset=N`) linking each sitting's Latin page, whose Cyrillic twin has
  the next lower number. Everything is in `config.CONVOCATIONS`, each with its dates (`skupstina.within`).
- **The PDFs have a text layer**, read with `pdftotext -layout` (`rollcall.py`). Three layouts: since autumn 2025 one
  vote per file, sections ЗА/ПРОТИВ/УЗДРЖАНИ/НИСУ ГЛАСАЛИ/НИСУ ПРИСУТНИ, rows "SURNAME Given, vote, group", the
  absent listed; listinzi 2024 several votes per file, "Given Surname (list)", the absent **not** listed; listinzi
  2025 the same with the list in a column. A row's vote must agree with its section and numbers run from 1; anything
  else is a recorded problem. Latin look-alike letters in Cyrillic words are mapped before matching. A roll call
  outside the convocation's dates is not kept, nor are notes of such a sitting loaded (17 Nov 2026: the Eleventh's
  first sitting, listed without a day on the Tenth's archive page, had put its votes and speeches in the Tenth).
- `index` → `data/<N>/index.json`; `votes` reads every roll call not yet read into `data/<N>/votes/<sitting>.json`
  with each PDF's SHA-256.

- **The Rules of Procedure** (20 Nov 2026, the maintainer's decision: link the articles MPs and the chair invoke,
  explain the site's terms from them, check a sitting's order of steps against them, and follow amendments;
  `poslovnik.py`, `zailiprotiv poslovnik`, in **votes** once a day): from the Assembly's consolidated text, the page
  "Цео Пословник", 298 articles in 21 chapters, each chapter linked to its own page there. Kept in `data/poslovnik/`
  as the Assembly writes it (Cyrillic), one file per version, written only when the articles' text changes, with the
  day it was first seen (not the day it came into force; the consolidated text gives none) and `poslovnik.load(day)`
  for the version of a day. Quirks of the source: chapters IX and X numbered with a Cyrillic Х, the menu's "Уводнa
  одредбa" with a Latin a, article 261 one paragraph of lines broken by `<br/>`. Two proposals to amend it are in
  procedure in the Fifteenth (02-3333/26, 02-3761/26).
- **The articles invoked in the debates** (20 Nov 2026, the maintainer's choice; `poslovnik.cited`): in a speech
  pointing out a breach of the Rules, the articles named in its first 400 characters; anywhere, an article named
  with "Poslovnik"; one "of the Constitution" or "of the law" is not the Rules'. One count a speech an article.
  "Varnice u sali: svi sazivi" lists them, most first, each with its count per convocation, its text (folded) and
  its chapter at the Assembly (`pages_floor.invoked_articles`, `#clan-<n>`); in the notes' pages each such mention
  leads there. The text shown is the Rules as now consolidated (the page says an older sitting may have known
  another wording). Method: `kako-racunamo#poslovnik`.
  **On a page of their own** (20 Nov 2026, the same day): with every convocation's notes the list made the
  Cyrillic `varnice-svi` 1.1 MB, over the pages' limit, and no build was published for two hours. It is
  `poslovnik-clanovi` (`pages_floor.RULES`, `rules_cited.html`); "Varnice u sali: svi sazivi" names how many
  articles and the one invoked most, and links there; the notes' pages link `poslovnik-clanovi#clan-<n>`.
- **The site's terms explained from the Rules** (20 Nov 2026, the maintainer's choice, step 3): replika, the chair's
  three measures and their fines, ukazivanje na povredu Poslovnika, hitni postupak, načelni pretres, pretres u
  pojedinostima, amandman, Dan za glasanje. In `data/poslovnik/pojmovi.json`, written by hand: each term the
  articles it rests on, a short retelling of them checked against their text (only what the articles say, no view of
  whether they are kept), how the site itself counts it where it does (`na_sajtu`, `kako`: the method's section),
  and `verzija`, the Rules' version it was written against. Shown on `poslovnik-clanovi#pojam-<id>` (the page is now
  "Poslovnik Narodne skupštine", terms first, then the articles invoked), each with the articles' full text folded,
  so an article nobody invoked has a place too; an article also in the invoked list links there. Once an article of
  a term reads otherwise in a newer version (`poslovnik.terms`, `changed`), the retelling is dropped and only the
  articles' text is shown, open, until written again. The pages link a term where it appears
  (`macros.term`, only for terms the file has): the floor pages, a law's debate and measures, the convocation and
  numbers pages (hitni postupak), the method page.
- **The sitting's steps by the Rules** (20 Nov 2026, the maintainer's choice, step 4): four terms more, for what a
  sitting day goes through: otvaranje sednice i kvorum (88, 90), radno vreme, pauza i prekid (87, 101), dnevni red
  (92, 93), tok pretresa (96, 98); first in `pojmovi.json`, in the order a day takes them. Each kind of step on the
  live page leads to its term (`live-day.md`), and the order the live page keeps (`steps._in_order`) cites the
  articles it rests on. The site shows what the Rules say and when a step was heard; it does not say whether a
  sitting kept them (principle 3; a breach is for MPs to point out, art. 103).
- **The Rules shown where readers come** (20 Nov 2026, the maintainer: the new convocation's readers will want them):
  the home page's box of the new convocation has "Sednica po Poslovniku" (kvorum, replika, opomena, hitni postupak,
  and that the live page's steps lead to their articles), the footer's "Skupština" column links "Poslovnik", the
  page shown at mikrofon while the service is down links it, and the live page has a box of its own.
- **The groups' time for debate** (22 Nov 2026): term `vreme-rasprave` (97, 99, 158), the rule behind the live
  page's estimate of each group's time left (`live-day.md`).
- **When a sitting already begun goes on** (25 Nov 2026, the maintainer: "Zašto automatski ne pripremamo stranicu prema
  skupštinskom kalendaru?"; that morning the live page said only "Ne zaseda"). Two reasons it was missed: the notice of a day was sought only in
  the preamble and only as "за среду, 25. …" (what convenes a sitting), while a continuation is the last sentence of
  the sitting's page ("Народна скупштина наставља рад у среду, 25. новембра 2026. године, са почетком у 10.00
  часова"); and a sitting with a roll call was taken as over, which the first sitting had since 19 Nov. Now
  `skupstina.continues` reads that sentence into the sitting's `continues`: the Assembly's own words only (the two forms
  it has used so far and their slips of "са почетком", "се", "наставиће"), with a date and a year, the named day of the
  week being the date's; the latest when there are several; a sentence worded otherwise is not guessed at and the notice by
  hand (`data/obavestenja.json`) still stands for it. `next_start` takes it beside a sitting convened, the nearest still to
  come first. **Not from the Assembly's calendar**: its page gives the entries of one chosen day only (today's), the
  rest by a script, and the calendar in the margin of every page the same; the sitting's page is read every hour anyway.
- **The Rules end with their last block** (25 Nov 2026, found by the worker on the Rules' page). The reading took
  every paragraph of the page after the first chapter began, so the margin's calendar and news and the foot of the page were
  kept as paragraphs of article 298, from the first version on; the margin changed, and 24 and 25 Nov each got a "version".
  `poslovnik._Parser` takes only what stands inside a `<div class="block">`: on the page of 25 Nov nothing of the Rules is
  outside one and nothing else inside, and read so it is the version of 20 Nov in 297 articles and all the chapters,
  298 being its one paragraph. The two files are removed (compared field by field, nothing but 298's tail differed),
  that tail is off 20 Nov's, and its fingerprint is counted again. No retelling had been hidden: no term rests on 298.
  But article 298 is among those invoked, so from 20 to 25 Nov `poslovnik-clanovi#clan-298` showed the margin as the
  Rules' text. A term resting on it would have lost its retelling at the first news item.
- **A sitting convened is read in every form the Assembly has used, and told of at once** (25 Nov 2026, the maintainer: "čim
  se objavi", before the Second sitting; tried on the Fourteenth's sittings whose agenda or day was not read, kept as
  fixtures). Read besides the list: lines numbered from 1 (the Eighth extraordinary session), the one item said in the line
  of "дневни ред … :" (the Ninth, the Third and Fourth special sittings), a notice with no year (the Fourth special one: the
  page's own date gives it, when the weekday fits), an hour with no minutes, a month in either case. A sitting is known by
  its title (`sitting_title`), so one whose agenda is not read is still announced (`pages_mikrofon._called`), with no items
  rather than another's. The agenda given to the live page is of the newest convocation whatever the current one is
  (it would have gone with the Fifteenth's first law), each sitting with the day it was convened for; the home page
  names the sitting by its title, not "Prva sednica". Bills in procedure are tied to the newest convocation's agenda too.
  **The alert:** a sitting newly listed, or a day or agenda that came or changed before a vote at it, opens an issue in the
  repository (`news_of`, `index --tell`, the first step of **votes**), which GitHub mails the maintainer; it says also when
  the day or the agenda could not be read. No secret and nothing on the site.

## Laws

- **The adopted laws** come from "Донети закони" (`laws.py`): title and PDF, the bill (title, PDF, day submitted),
  the day passed, the Gazette issue, "(MU)" for treaties. `index` and `laws` keep the file when a reading has far
  fewer entries (`cli._shrunk`), so an empty page can't wipe a convocation's data; `laws` keeps what `link` and
  `bills` added to a law whose bill is unchanged (`laws.carry`, 17 Nov 2026: a **votes** run for the Eleventh that
  failed after `laws` committed its laws without a single final vote, and the site showed none).
- **Two sortings, both from the documents** (12 Nov 2026): the kind of act (treaty; budget and public finance; a law
  or changes to one; elections and dismissals; the Assembly's own work; declarations) from the title and the Gazette's
  mark; the area, from the point of Article 97 of the Constitution the bill's "Уставни основ" names. No area of our
  own choosing.
- **Linking laws and votes** (`link.py`): an act is named by its roll call's PDF, never the sitting page's link text
  (sometimes out of step). A vote is on a law when its name is the law's (or starts with it) between submission and
  passing; the final vote is the one on the day passed, on the act as a whole. Otherwise that day's vote sharing 90 %
  of the words or 95 % of the letters, when unambiguous (`"matched": "close"`); or by hand in `data/<N>/links.json`
  (`{law title: {"vote", "why", "item"}}`, `"matched": "manual"`).
- **Short names** for lists and headlines (`data/<N>/short_titles.json`), written by a model from the title and the
  summary, reviewed: the subject, then the main change after a colon; neutral, no nicknames, persons or claimed
  benefits; unique within a convocation. The official title is always on the law's page. **Public names** of a law
  (`data/aliases.json`, each with a press link) are searched and shown as "U javnosti i: …".
- **Summaries of the memoranda** (12 Nov 2026; `summaries.py`): from the memorandum's sections, each cut to a limit
  (8,000 characters: in large laws the article-by-article part is cut). Rules in the system prompt: only what the
  memorandum says, attributed; no judgement, parties or persons; plain words; the proposer's charged terms quoted,
  never softened; the proposer's political reasons given as theirs; figures only as stated (a malformed one quoted as
  written). JSON (`ukratko`, `razlozi`, `promene`, `sredstva`), kept in `data/<N>/summaries/<bill file>.json` with
  the model and a fingerprint of prompt and material (written again only when one changes). The page names the model
  and links the bill. A bill PDF holding another act's memorandum is listed in `data/<N>/wrong_bills.json`.
- **Bills in procedure** (13 Nov 2026; `procedure.py`): "Zakoni u proceduri" into `data/<N>/procedure.json` (current
  convocation), remembering when each was first and last listed; read and summarised like adopted laws, a page each
  (`predlog/<slug>.html`); one no longer listed and not adopted is "no longer listed", with no reason given.
  Convened sittings: a sitting with an agenda and no roll calls yet (`u-proceduri.html`, `u-proceduri.xml`).

## Debates and the notes

- **Stenographic notes** are Word files per day of work (provisional, unauthorised); `transcripts` reads them into
  `data/<N>/transcripts/<sitting>.json`. Each speech starts with the speaker in capitals and a colon; the chair is
  ПРЕДСЕДНИК or ПРЕДСЕДАВАЈУЋИ (typos included); page marks are skipped; the part of the debate comes from the
  chair's words (joint debate in principle, then each bill's amendments; MPs' questions pause it).
- **Every sitting since 2012 is read** (14 Nov 2026; `transcripts --all`, about 350 sittings, 194,000 speeches). As
  read they are about 560 MB: kept whole in the notes' bucket under `sirovo/` (gzipped); the repository keeps those of
  the contested laws; **pages** and **notes** bring the rest first (`notes-raw --pull`, when `notes_all` is set).
- **Speakers' names are mended** (`debates.mend`): a rare spelling close to a name on the roll calls is that name.
- **The notes as pages** (14 Nov 2026; `notes_site.py`): every speech with its own address, in the R2 bucket behind
  `beleske.zailiprotiv.rs` (too much for GitHub Pages). `notes-site` builds them (Latin at the root, Cyrillic under
  `cir/`, each with canonical and language links, a sitemap and robots.txt), `notes-upload` sends only what changed
  (`data/notes_manifest.json`); the **notes** workflow runs both after each transcripts run. The site links to a
  speech only when its page is in the bucket.
- **A law's debate** (12 Nov 2026; `debates.py`): a model's summary from the notes only (the law's amendments, and
  the debate in principle, or in a joint one the paragraphs naming the law's subject), in three parts (the proposer
  and the Government, those for, those against), each point with the speaker's group (the roll call nearest in
  time); verbatim quotes, at most one per group per side, each checked word for word and linked to the speech.
- **What an MP says** (12 Nov 2026; `data/profiles/`): three to five points from a selection of the MP's speeches,
  under `data/profiles/RULES.md`: only what recurs in two or more speeches, as the MP's claim, content not tone, no
  labels, one checked quote per point. Labels for MPs ("populist") were rejected as judgements. **Distinctive
  words** (`profiles.distinctive`, no model): a smoothed log-odds ratio over stems against all MPs.
- **Every measure read again, the rules in `measures.py`** (23 Nov 2026, the maintainer: "skeniraj ponovo kome su date
  opomene i ispravi gde treba"). Each measure the rules found in the notes of every convocation was read with its
  context by an agent (a model; the rules themselves stay without one, and the method page says both), and the chair's other mentions of a warning looked through for what they missed. Published and wrong: a
  warning put "by context" to Nikola Selaković (the chair said "Изричем опомену Добрици Веселиновићу") and a removal
  to Radomir Lazović (an earlier measure recalled); both are the first entries of `data/ispravke.json`. Missed: every
  measure of an address but its first, a list of names, "имате / добијате (другу) опомену", "Колега Божићу, друга
  опомена", "морам да вам изрекнем опомену", a name before the verb ("Бошку Обрадовићу изричем"). Not measures:
  a condition or a threat, "него да вам изричем", a rule quoted, an earlier one recalled, the same one told again in
  one address. To whom: those who only heckled count too; a name misspelt by a letter is one person; someone named and
  not found is never replaced by whoever spoke before; the likely ones by the order in `by_context`. Before: 100
  measures, 42 with a name, 36 likely, 22 nobody's; after: 139, 70, 66 and 3. Counts per MP change with it.
- **The measures of 19 Nov 2026 read from its notes** (24 Nov 2026, the maintainer; the notes came that day): the six the
  rules found read with their context, all to whom the notes show. One missed: "Изричем вам и сад опомену и вама, пришли
  сте без позива", taken for the one before told again; a measure that says it goes to another too ("и вама", `_ALSO`) is its
  own, by context Ana Brnabić's (her heckle right before; the chair said after the break that he had warned her and
  Milenko Jovanov, and that both would be taken back if he had called the break first, which the notes do not settle).
  Of the 145 measures of all convocations it changes only this. Jovanov's is not put to him: nothing in the measure's
  own sentence names him, and a rule taking names from the chair's later account is not made yet.
- **A measure to more than one, named by the chair's own account** (24 Nov 2026, the maintainer: "da i da"; `_account`): a measure
  that says it goes to another too and names nobody takes its names from the chair's account in the next 30 speeches of
  that day ("Ја сам дао опомене посланици Ани Брнабић и посланику Миленку Јованову"): one each. Of the 146 measures of
  every convocation it changes this one alone (Brnabić by name instead of by context, and Jovanov's). A short first name in
  another case is the same person ("Ани" is Ана). The chair said both would be taken back had he called the break first;
  the notes do not settle it, and the measures stand as pronounced.
- **A sentence of the model's summary of 19 Nov corrected by hand against the notes** (24 Nov 2026, the maintainer): it said the
  chair asked whether the two had got warnings, and a break of ten minutes; he gave them, and the break was of fifteen.
  In `data/ispravke.json`. The service's own copy (`/sazetak/2026-11-19.json`) is as it was.
- **Varnice** (13 Nov 2026; `pages_floor.py`, no model): the chair's measures (warning, taking the floor away,
  removal; `MEASURES`, with talk about measures left out), exchanges of replies (two speakers taking turns four times
  or more, no speech over 400 words), points of order, harsh words (a fixed list), who speaks most. A measure goes to
  an MP only when the chair's sentence names a speaker of the sitting: addressed ("господине …", "посланику …") or
  right after the measure ("изричем опомену Стефану Јовановићу", 17 Nov 2026); a first name said must fit; several
  named at once count for none (since 23 Nov 2026 a measure each: below). Otherwise the context may make it "likely", said so. The rule can't tell whether an
  exchange is personal and the page doesn't claim it. Rankings count only MPs of that convocation (`as_mp`), not
  ministers or guests.

## The data runs

- **A chain** (13 Nov 2026): **votes** → **transcripts** → **summaries** → **pages**; a run by hand of any link goes
  on from there. Pushes by the workflows' own token start no workflow, so each link starts the next.
- **The clock is the counter's worker** (13 Nov 2026; GitHub's schedule never started the workflows): a Cloudflare
  cron dispatches **votes** every hour of the working day (`scheduled: true`: nothing new stops the chain) and
  **summaries** every six hours. **worker** publishes `worker/` with CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID and
  DISPATCH_TOKEN.
- **The model's writing runs in Actions** (13 Nov 2026), not by hand.
  `summaries --batch`, `debates-batch` and `profiles-batch` send Message Batches, check every reply (quotes word for
  word) and keep running batches and refused replies in `data/batches.json`; a refused reply is sent once more with
  what was wrong, then left for a person. The first pass is always the cheapest model (Haiku); a stronger one only by
  hand. The `export`/`import` commands (and `*-export`/`*-import`) stay for work by hand.
- **Signing in to the Anthropic API without a key** (13 Nov 2026, `federated.py`): **summaries** asks GitHub for the
  repository's identity token (`id-token: write`) and exchanges it, under a federation rule for this repository's
  main branch, for a short-lived token. The rule's ids are repository variables (`vars.ANTHROPIC_*`) and grant nothing by themselves. A secret
  `ANTHROPIC_API_KEY`, if set, is used instead.
- **One pending run per workflow** (concurrency groups). A failed **votes**, **transcripts** or **summaries** run
  opens (or comments on) one issue.
- **Two slow steps made faster, their output unchanged** (20 Nov 2026, measured on the runs of 19-20 Nov). In
  **votes**, `arhiva` spent some 14 minutes on a file whose captions name nobody (120 frames, one ffmpeg at a time):
  `arhiva.samples` reads six frames at once and takes them in order as one at a time would (the same stop at
  `ENOUGH`, an error raised only where that reading would meet it; a test compares the two). Caching the apt
  packages was left out: they take 10-40 s, once 13 minutes (a slow mirror). In **notes**, of some 900 s Pagefind
  took 470 and wrote a new index from the same pages each time (its files' names change), so every run sent and
  removed some 630 files (the removals one at a time, 4 minutes; now as many at once as are sent) and emptied the
  bucket's cache. The index is kept with `actions/cache` under a key that is the SHA-256 of every Latin page it is
  made of, with Pagefind's version and pattern: the same pages take the index made of them, any page changed makes
  a new one, so a stale index can't be published. The pages are still built whole (some 65 s; `notes-site` reads
  each convocation's roll calls once), so they stay exactly what a full build makes.
- **What reads the older notes is installed when the first such file comes** (20 Nov 2026): **transcripts**
  installed LibreOffice (for .doc and RTF) and poppler (for the PDFs of 2016-2017) on every run, though today's
  notes are .docx and most hourly runs find nothing new. It cost some 20 s a run, and at 10:49 UTC on 20 Nov, 21
  minutes: 92 MB from a slow mirror, for a run with nothing to read, while the notes' pages and the summaries
  waited behind it. Now `transcripts.tool` runs the workflow's `NOTES_TOOLS_INSTALL` the first time a program is
  asked for and missing; where the variable isn't set (a developer's computer) nothing is installed and a missing
  program fails as before.
- **When the Assembly sits next is read first, and a run begins from the branch as it is** (25 Nov 2026). On the evening
  of a sitting a **votes** run takes 80 to 95 minutes (`arhiva`, the day's recordings) and all it read was committed at its end, so
  the sitting's page saying when the Assembly goes on would have waited for that. Now the newest convocation's `index`
  is the run's first reading, and when anything in it is new it is committed and **pages** started at once; the same
  requests to the Assembly as before, in another order. And a run that waited behind another checked out the state of when it was
  asked for: on 24 Nov the one of 20:47 UTC met the conflict in `index.json` and seven files more, the rebase stopped
  half way, `git status -sb` had no "ahead" to show, and the run was green with its hour's reading lost. It checks out
  `github.ref` now, takes an unfinished rebase back before it tries again, and is red when the push did not go. The
  other data workflows share the loop without the check and are as they were.

## Changing convocation

The Fifteenth convocation was constituted on 17 November 2026. `config.CONVOCATIONS["15"]` (from 2026-11-17) and
the Fourteenth's end; both read the same listings and keep only their own dates. `config.CURRENT` is the newest
convocation with a law that has its final vote, so the Fifteenth becomes the current one by itself with its first
law, and the site never opens on a convocation with no MPs (17 Nov). Until then **votes** reads `config.NEWEST`
beside the current one each hour (no bills in procedure, no notes), and the "no roll calls" check applies to the
current one only. On 17 Nov the Assembly's listings of sittings and laws and its page of bills in procedure began
showing the Fifteenth only (the Fourteenth's 91 waiting bills are no longer listed); the files keep the Fourteenth's
data. **Its MPs before its first roll call** (18 Nov 2026, the maintainer's request; `members.py`, `pages_members.py`):
**votes** reads the Assembly's list of sitting MPs ("Aktuelni saziv", the Cyrillic page: the Latin one misspells some
names) into `data/<N>/members.json` for the newest convocation (`zailiprotiv members`; a page with far fewer rows keeps
the file). The site lists them on `poslanici-<N>.html` (party that put them forward, place, year of birth, the
convocations they were on a roll call of), linked from `poslanici.html`. One already on the site by roll calls is the
same MP unless the archive gives another year of birth (mp_years; one year off counts as a typo): their page says
they sit in the new convocation. A new one gets a page of their own (noindex, as any MP's page with no vote) under
the name written as the roll calls write names, a namesake's address getting the year after it; their search entry
is in `podaci.json`, so "Ko sada govori" matches them too. **Groups** (18 Nov 2026): not in the list's table, but its
form filters it by group (`?submitted=true&group=<value>`), so `members` reads each group's page and keeps the group
on each MP ("" for the form's "not members of a group"). The list goes group by group, largest first, then by name;
the pages and `podaci.json` (so the live page too) give an MP of the newest convocation their group there.
Left to do: give the Fourteenth its "archive" and archived "laws" pages once the Assembly publishes them; close
issue #7 once the Fifteenth is current.

- **The home page for a new convocation** (19 Nov 2026, shown to the maintainer before it went out). The headline is
  "Svaki glas i svaka reč iz Skupštine" (his choice of four). Since 23 Nov 2026 "Za ili Protiv:
  svaki glas i svaka reč iz Skupštine" (the maintainer's decision): Google titles the page by its h1, which had no name in it. While the newest convocation has passed no law
  (`newer` in `site.py`), a block right under the search, across the page (first on a phone): how many MPs and how
  many with no vote since 2012, the seats by group in the groups' colours (`site.GROUP_COLOURS`, the live page's
  hues: the second place the exception to "colour only for za and protiv" holds), the five longest on the floor by
  the recordings (three on a phone), the first sitting's agenda as the Assembly lists it, the ways to the MPs' list
  and the live page. What is the earlier convocation's wears "prethodni saziv" (the law that divided the chamber,
  the last adopted, the picked votes, "Varnice u sali", which moved below them), and a dashed box holds the place of
  the new one's first laws and of its replies and measures. All by rule; the block goes when the new convocation
  becomes the current one.
- **The new convocation on every page with a place for it** (19 Nov 2026, the maintainer's request). `newer15` in
  `site.py` (computed before any of these pages is rendered, and a global): the groups with seats, new MPs and time
  on the floor, the sittings as the Assembly lists them with their agenda, the days read from the recordings and the
  quick exchanges on them. The MPs' pages have its **tab first** (`macros.tabs`; a template that uses it imports it
  `with context`, since a macro imported without sees the globals as they were when first imported), the new
  convocation's list page wears the section's head and tabs, and **the menu's "Poslanici" leads to it** while it is
  the sitting one. `macros.newer_panel(part)`: on "Grupe" the groups' table and seats bar, on "Sednice" the agenda
  and the days, on "Varnice" the quick exchanges by the order of turns (the notes' replies, measures and harsh words
  come when the notes are counted for it: `pages_floor` still counts only convocations with laws), elsewhere in the
  Assembly's pages and on "Prisustvo" a line and the links. It rides in `assembly_tabs`, so every page of that
  section has it. Gone when the convocation becomes the current one.
- **The new convocation's notes are counted before it has a law** (19 Nov 2026). `site.build` gives `pages_floor`
  the newest convocation's notes (brought from the bucket at build) ahead of the others', so "Varnice" opens on it
  once its notes hold a reply or a measure; its new MPs, on no roll call yet, get their names and pages from the
  Assembly's list (`extra`). The home page shows its counts in place of the dashed box, and a new MP's "Ukratko"
  has a tile of speeches in the notes. The newest convocation's notes are kept in the repository whole while it is not
  the current one (`transcripts.yml`), so the counts can be checked against them: the first sitting's two days hold
  no measure and no exchange of replies (read through: the reprimands in them are spoken of, none pronounced), so
  "Varnice" has no page of its own for it yet, and its panel there and the home page give what the notes do count
  (speeches, points of order, harsh words, who leads in each; `newer15.counted`, put into the panel's mark after
  the counting, since those pages are made during it).
- **The newest convocation's notes are asked for three times a day** (24 Nov 2026, the maintainer): the hourly **votes**
  asks **transcripts** only for `config.CURRENT` (14), so the notes of 19 November, up on the Assembly's page, were never
  read. **votes** now starts **transcripts** for `config.NEWEST` too, over every sitting with `--more`: the page is asked,
  and the notes read again only when it links a day the record lacks. No model's writing follows (a run over every
  sitting starts none).
- **The clock's runs read the current convocation, whatever number the clock names** (25 Nov 2026, found before the Second
  sitting). The counter's worker starts **votes** with convocation "14": with the Fifteenth's first law `config.CURRENT` is 15,
  and such a run would have read the Fourteenth alone, every hour, with nobody told. `scheduled` now means the current
  one; a run by hand is for the convocation it names. The first step (the sittings, the alert, the early commit) goes on when
  the newest is the current one, and its listing is not asked for twice.
