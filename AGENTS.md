# AGENTS.md

How to work on this repository, what must not change, and the architecture decisions with their reasons. It is
written for coding agents and for people. **Keep it current:** when a decision is made or changed, update this file
in the same commit. README.md describes the project for its users; this file is for those who change it.

## How to work here

- **Commit straight to `main`.** No feature branches or pull requests, as in the sibling repos (`izborna-analiza`, `izborna-analiza-hr`).
- **Run the whole test suite before every push:** `uv run pytest -q`. The **test** workflow runs it again on every
  push; a red run is fixed before anything else.
- **Explain why in commit messages.** Say what changed for the site or the data, and the reason.
- **Update README.md with every feature.**
- **Ask the Assembly little.** Requests identify the project in the User-Agent and wait a second between pages.
  Recurring reads are incremental.
- **The development sandbox may not reach parlament.gov.rs; GitHub's runners may.** Run anything that needs the
  site through `workflow_dispatch`.
- **Only one pending run per workflow.** Each workflow has a concurrency group.
- **Talk to the maintainer in Serbian** (Latin script), briefly and to the point. Code, comments and docs are in
  English.

## Principles

These are the project's promises to its readers. Never change them without the maintainer.

1. **The same rules for every MP, club and party.** No party is hardcoded or singled out; every measure is computed
   the same way for all, and lists are ordered by neutral rules (number of seats, alphabet), never by preference.
2. **Facts from primary sources only:** the National Assembly's own publications (roll-call results, bills with
   their explanatory memoranda, transcripts), laws as published in the Official Gazette. Otvoreni parlament
   (CRTA) and news reports may help find or check something, but never supply a figure or a vote.
   - **Other voices, labelled** (the maintainer, 12 Nov 2026): for the laws with most votes against, opinions of
     independent bodies (Fiscal Council, Protector of Citizens, Commissioner, Venice Commission, ODIHR, European
     Commission) and analyses by media and civil society may be shown as notes, each with its source named, its
     date and a link, summarised in a sentence or two and attributed ("Fiskalni savet ocenjuje …"). A note never
     supplies a figure, a vote or a ranking, and the site doesn't take its side. Independent bodies and media or
     civil society are shown apart, so readers can weigh them.
   - **How notes are kept:** `data/<N>/notes/<bill file>.json` (`checked`, `by`, `independent`, `media`; each note
     `source`, `date`, `url`, `title`, `note`), gathered by an AI model from pages it fetched, then reviewed. In the
     review: professional associations (bar, judges' and prosecutors' associations) go with civil society, not
     independent bodies; a source reported second-hand says so ("(преноси N1)"); a note about another act (a later
     amendment, an unrelated procurement) is dropped; supportive views are kept when found, never invented to
     balance; private persons are named by role only. Pilot: 10 of the laws with most votes against (12 Nov 2026).
3. **A law's effects are its proposer's, quoted with the source.** What a law is expected to do comes from the
   bill's explanatory memorandum (obrazloženje) and its analysis of effects (analiza efekata), summarised and
   linked, and labelled as the proposer's assessment. The site adds no judgement of its own about whether a law
   is good or bad (the maintainer's decision, 12 Nov 2026).
4. **MPs are public officials: their names and votes are public** (the maintainer's decision, 12 Nov 2026). The
   site shows each MP's name, club, party and every recorded vote. Only what they do in office: nothing about
   their private lives, and no other person's personal data (staff, citizens named in debates).
5. **Nothing from third parties on the pages:** no analytics scripts, cookies, external fonts or scripts.

## Architecture decisions

### Source

- **Roll calls:** the Assembly publishes each vote as a PDF under `/upload/rezultati_glasanja/` since autumn 2025
  (by year, sometimes by sitting: `2026/20.pdf`, `2026/osma_sednica/1.pdf`), and before that under
  `/upload/archive/files/cir/doc/Listinzi/<year>/` ("листинзи": `2024/2024.09.30 1.pdf`). Each gives the kind of vote (e.g. on the act as a whole),
  the date and time, and every MP with their vote (for, against, abstained, did not vote, not present) and club.
- **Only the Cyrillic pages of the sittings link to them** (`….43.html`): each agenda item's text is a link to its
  roll call. The Latin pages (`….941.html`) have the agenda without links. The current convocation's sittings are
  listed on two Cyrillic pages, regular (`заседања/редовна.34.html`) and extraordinary (`заседања/ванредна.35.html`),
  whose margins also carry other news: a sitting is a `.43.html` link whose text names a sitting or session.
- **Earlier convocations** are on archive pages in Latin (`arhiva-aktivnosti/saziv-od-1-avgusta-2022/zasedanja.4921.html`
  for the Thirteenth, `…saziv-od-3-avgusta-2020-godine/zasedanja.4620.html` for the Twelfth, more pages with
  `?offset=N`). They link each sitting's Latin page; its Cyrillic twin, which links the roll calls, has the next
  lower number (`….53525.941.html` → `sednica.53524.43.html`; the words before the number are ignored). Each
  convocation has its own page of adopted laws. All of this is in `config.CONVOCATIONS`; a sitting whose title names
  another convocation is left out.
- **PDF names are irregular** (`2026/20.pdf`, `2026/29.11.pdf` for a sub-vote, `2026/osma_sednica/1.pdf`,
  `2026/19. Izveshtaj_sa_rezultatima_glasanja_24_04_2026_09_27.pdf`): a vote is known by its link, never by a
  name built from a pattern.
- **The PDFs have a text layer** (no OCR), read with poppler's `pdftotext -layout` (`rollcall.py`), which keeps
  the columns apart. Three layouts:
  - since autumn 2025 ("Извештај са резултатима гласања"): one vote per file; session, agenda item, the kind of
    vote with date and time ("Гласање о предлогу акта у целини - 25.06.2026 / 11:17:12"), then sections ГЛАСАЛИ
    ЗА, ГЛАСАЛИ ПРОТИВ, УЗДРЖАНИ, НИСУ ГЛАСАЛИ, НИСУ ПРИСУТНИ numbered from 1; a row is "SURNAME Given, vote,
    group" ("ПГ АВ-СНСДС"); the absent are listed (250 rows, fewer with a vacancy);
  - listinzi 2024: one file may hold several votes (items 1.1, 1.2, …); a row is "Given Surname (list)"; the
    absent are **not** listed;
  - listinzi 2025: as 2024, the list in a column ("-" for none).
  Every page repeats its header, so a vote is known by its date and time and its agenda item. A row's own vote
  word must agree with its section, and numbers run from 1 in each section; anything else is a recorded problem.
  The PDFs write some Cyrillic words with Latin look-alike letters ("Ниje гласао"): matched after mapping them.
- **Not yet joined:** names are "SURNAME Given" in one layout and "Given Surname" in the others, with titles
  (проф., др, мр); groups are abbreviations in one and list names in the others. Who an MP is across votes, and
  who was absent from a 2024–2025 vote, need the convocation's roster.
- `zailiprotiv index` writes the sittings and their roll calls to `data/index.json`; `zailiprotiv votes` reads every
  roll call not read yet into `data/votes/<sitting>.json` (the sitting page's number), keeping each PDF's SHA-256.
  The **votes** workflow runs both and commits.

### Laws

- **The adopted laws** come from the Assembly's page "Донети закони" (`laws.py`): per law its title and PDF, the
  bill it came from (title, PDF, day submitted), the day passed and the Official Gazette's issue, marked "(MU)" when
  published among international treaties. 395 laws in the Fourteenth convocation, 171 of them treaties (Nov 2026).
  `zailiprotiv laws` writes them to `data/laws.json`.
- **Two ways of sorting laws, both read from the documents themselves** (the maintainer's decision, 12 Nov 2026),
  the same rules for every law:
  1. the kind of act, from its title and the Gazette's mark: international treaty; budget and public finance
     (budget, final account, financial plans, borrowing, guarantees); a new law or changes to one; election or
     dismissal of officials; the Assembly's own work (rules of procedure, committees, agenda); declarations and
     resolutions;
  2. the area, from the bill's "Уставни основ": the point of Article 97 of the Constitution the proposer relies
     on, each point being one area of the Republic's competence. No area of our own choosing; "political" is not
     a category.
- **A law's summary is Claude's summary of the proposer's memorandum** (reasons, analysis of effects, funds
  needed), labelled as such and linked to the bill (the maintainer's decision, 12 Nov 2026).
  - Written through the Anthropic API (the maintainer's decision, 12 Nov 2026) by `summaries.py` with
    `claude-sonnet-5-5` (override: `ZAILIPROTIV_MODEL`), from the memorandum's sections, each cut to a limit.
  - The system prompt holds the rules: only what the memorandum says, attributed to the proposer, no judgement,
    no parties or persons, Cyrillic, plain words; empty where the memorandum says nothing. The reply is a JSON
    object (ukratko, razlozi, promene, sredstva); anything else in it is dropped.
  - Kept in `data/summaries/<bill file>.json` with the model, token usage and a fingerprint of model, prompt and
    material: a summary is written again only when one of those changes.
  - The page labels it as an AI model's summary of the proposer's memorandum, names the model, and keeps an
    excerpt of the memorandum itself one click away.
  - The **summaries** workflow (by hand, and started by the votes workflow) needs the secret `ANTHROPIC_API_KEY`.
  - Summaries may also be written in a Claude session, from the same material under the same rules (the
    maintainer's choice for the Fourteenth convocation, 12 Nov 2026): `zailiprotiv export` writes each pending
    law's material and the rules, `zailiprotiv import FILE --model …` checks and saves the summaries under the
    name of the model that wrote them. The fingerprint covers the rules and the material, not the model, so the
    API run leaves them alone until either changes.
  - Practice in the session summaries (12 Nov 2026, confirmed by the maintainer the same day, with one change:
    the proposer's political reasons are given, attributed, not left out):
    - no sums or figures the memorandum doesn't state (two added-up totals were taken out);
    - the proposer's charged terms are quoted and attributed ("„НАТО агресија“, како наводи образложење"),
      never replaced by a softer word of ours; evaluative phrases of the proposer's ("од изузетног значаја") are
      left out; legal statuses ("пројекат од посебног значаја") stay, attributed;
    - no persons: signatories, MPs who proposed a bill, appointees, people named in court cases;
    - the proposer's stated reasons are given as the proposer's, political ones too (in bilateral agreements, the
      other country's stance on Kosovo or its vote on the Srebrenica resolution), the proposer's terms quoted;
      factual conditions and budget items stay (a loan's condition of dialogue with Pristina);
    - a malformed figure in a memorandum is quoted as written, never corrected.
  - **A bill PDF holding another act's memorandum** (the Assembly's upload; two in the Twelfth convocation) is
    listed in `data/<N>/wrong_bills.json` with what it holds: no summary or excerpt for that law, and the page says
    why and links the PDF.
  - In large laws the explanation of individual articles is cut at the material's limit (8,000 characters), so
    their summaries cover the reasons and the first articles. To revisit with a higher limit for those laws.

### Debates

- **Stenographic notes:** a sitting's Cyrillic page links one Word file per day of work under
  `/stenografske_beleske/`, provisional, unedited and unauthorised. `zailiprotiv transcripts` reads them for the
  sittings of the laws with most votes against (`--top`, default 20) into `data/<N>/transcripts/<sitting>.json`.
- **Each speech starts a paragraph** with the speaker in capitals and a colon ("МИЛЕНКО ЈОВАНОВ: …"); the chair is
  ПРЕДСЕДНИК or ПРЕДСЕДАВАЈУЋИ/-А (typos included). Page marks ("1/2МТ/ ВЗ") are skipped. The agenda follows
  "Д н е в н и р е д", numbered by hand or by Word's list numbering, which leaves no number in the text.
- **The part of the debate comes from the chair's words:** a joint debate in principle on several items ("отварам
  заједнички начелни и јединствени претрес … тачака 1. до 58."), then each bill's amendments ("Прелазимо на трећу
  тачку …", "Претрес у појединостима о 4. тачки …"); the hour of MPs' questions (Article 287) pauses the debate,
  which resumes where it was. Speeches in a joint debate in principle can't be told apart by bill, and the law
  page says so.
- **On the law page** (the maintainer's choice, 12 Nov 2026; word counts by group were dropped as meaningless): the
  course of the debate (days, items debated with it, amendments), then a summary of what was said, in three parts:
  the proposer and the Government, those who supported the law, those against it; each point attributed with the
  speaker's group; and verbatim quotes, at most one per group, from both sides, each linked to its day's notes.
- **The summary** (`debates.py`) is written by a model from the notes only: the speeches on the law's amendments,
  and from the debate in principle all of it, or, when it was joint, the paragraphs naming the law's subject
  (words of its title and rare words of its memorandum). A speaker's group is the one in the roll call nearest in
  time, within two months; ministers and others on no roll call are marked. Every quote is checked word for word
  against the notes, and against its speaker, and dropped if not found. `zailiprotiv debates-export` / `debates-import`
  for summaries written in a session; kept in `data/<N>/debates/<bill file>.json`.

- **What an MP most often says** (the maintainer, 12 Nov 2026; a first batch of nine MPs, the ones who spoke most in the
  notes read, as a trial): `data/profiles/<name>.json`, three to five points a model wrote from a selection of the MP's
  speeches (the longest from each sitting in turn, up to about 18,000 words, each cut at 700), under
  `data/profiles/RULES.md`: only what recurs in two or more speeches, as the MP's claim ("Navodi da …"), content not
  tone, no labels or assessments, charged terms quoted; what the MP says about persons is given like anything else
  (the maintainer, 12 Nov 2026: such points are not left out), public figures by name (office holders, party leaders, judges and prosecutors, media
  owners, businesspeople: "we don't censor what MPs said", the maintainer, 13 Nov 2026), ordinary citizens by role only; one verbatim quote per point checked word for word.
  The page says how many speeches were read and that the site doesn't judge the claims. Labels for MPs ("populist",
  "pro-European") were considered and rejected as judgements. Speakers who spoke mostly as members of the Government
  are left out (by hand so far: a rule is needed before this is widened). The MP page also shows the quotes chosen
  for the laws' debates ("Iz rasprava") and, from the roll calls, how often the MP voted as most of each group did
  ("Sa kim glasa isto": votes where both voted, ten or more).

### Links between laws and votes

- `link.py`: a roll call's act is named by its **PDF**, never by the sitting page's link text, which is sometimes
  out of step with the PDF behind it (on 13 March 2025 the link for the visa agreement with Venezuela opens the
  vote on Guatemala's). Names are compared by their words only (no quotes, dashes, commas, item numbers or
  proposer); Latin look-alikes are read as Cyrillic only in words that mix the scripts.
- A vote is on a law when its name is the law's (or starts with it) between the bill's submission and the law's
  passing; the final vote is that on the day passed, on the act as a whole where the PDF says so. A law left
  without one takes that day's vote sharing 90% of its words, or 95% of its letters (typos), when unambiguous and
  not taken by another law: marked `"matched": "close"`.
- **Links by hand** where the Assembly's PDF names the act otherwise (a wrong year, a typo, another word):
  `data/<N>/links.json`, `{law title: {"vote", "why", "item"}}`, applied only to a law left without a final vote
  and only to a vote of the day it passed; marked `"matched": "manual"`. Six in the Twelfth convocation.
- Eleventh convocation (2016–2020, read 13 Nov 2026): 617 of 617 (594 exact, 17 close, 6 by hand), 983 roll calls, none with a
  problem; the absent are not listed. No summaries, short names or debates yet.
- Thirteenth convocation: 197 of 197. Twelfth: 255 of 257; the Hilandar law and the anti-corruption amendments
  (both passed 23 Sept 2021) have no roll call among the PDFs indexed for that day.
- Fourteenth convocation (12 Nov 2026): 394 of 395 laws have their final vote (388 exact, 6 close). The Venezuela
  visa agreement (passed 13 March 2025) has no roll call among the PDFs the Assembly links for that day.

### Site

- **Static pages in Latin script** (`site.py`, Jinja2 templates): home, laws by kind, a page per law (facts,
  documents, an excerpt of the proposer's memorandum labelled as such, the final vote by group and by MP, the other
  votes on the act), MPs, a page per MP (their final votes on laws). Cyrillic from the Assembly's documents is
  transliterated; a test checks no Cyrillic is left. A Cyrillic edition can follow, as in the election site.
- **Nothing from other servers.** Colours mean kinds of vote (for, against, …), never a group.
- **Home page:** "Najviše glasova protiv" first (the maintainer's request, 12 Nov 2026): the laws whose final
  vote had the largest share against among votes for and against, ties to more votes against, then newer. Named
  for what it measures; "controversial" would be a judgement. Then the newest laws.
- **Design** (the maintainer chose it from three mock-ups, 12 Nov 2026): a newspaper look — white page, serif
  headlines (Source Serif 4, served from the site, OFL), a black rule under the header, colour only for "za" (blue)
  and "protiv" (orange). The wordmark is "Za ili Protiv", "Za" and "Protiv" in their colours. Little text: one line
  of facts per law.
  - home: the law with most votes against as the lead (short name, the proposer's gist, the count, groups against);
    a quote from each side of the first such law that has both; the list of the next ones; search for a law or an
    MP, filters (most against, newest, urgent procedure, budget, treaties) and a choice of convocation; an MP finder;
  - a law: its short name as the headline with the official title under it; then as before (count, groups against,
    a quote from each side, what it changes, groups' votes, the debate, outside views, "Detaljnije" folded);
  - an MP: the counts for and against; "Glasovi protiv" and "Glasovi za" (six each, the rest folded); "Drugačije od
    većine svoje grupe" (their vote for, against or abstained differs from what most of their group did in that
    vote: three or more voting, a clear majority); a table by kind of law; every vote by convocation, folded.
    All computed from the roll calls by one rule for everyone; no assessment of an MP in words.
- **Lists:** "Zakoni" and "Poslanici" are one page per convocation with tabs by years (2024–2026 …); rows can be
  searched, filtered (kind of law, urgent procedure, parliamentary group) and sorted in place by the script. The
  home list ranks the laws of every convocation by default. MPs are shown "Surname Given" without titles in every
  convocation (the older lists write "Given Surname"); "(NADA …)" and "NADA …" are one group.
- **One script of our own** (`static/site.js`, the maintainer, 12 Nov 2026; before that none): search and filters
  over `podaci.json` (every law and MP), fetched on first use. Pages work without it: the search box and filters
  appear only when it runs. Still nothing from other servers; a test checks each page has that one script only.
- **Short names of laws** for lists and headlines (`data/<N>/short_titles.json`, by the law's key): written by an AI
  model from the official title and the summary of the proposer's memorandum, reviewed. Rules: the subject first,
  then the main change after a colon; neutral and factual, no nicknames or labels from either side, no persons, no
  claimed benefits; unique within a convocation (same names get the year). The official title is always shown on
  the law's page, and the home page says the short names are ours.
- **Each law's page** gives its share of votes against and its place in the convocation by that share, and the
  course of its passing: submitted, days to passing, urgent procedure (proposed when the memorandum gives reasons
  for it), the sitting. The roll calls published are the final votes only; votes on amendments aren't among them.
- **A closer look at the laws with most votes against** (the maintainer, 12 Nov 2026): the debate from the
  Assembly's transcripts, the course of passing, independent bodies' opinions, and media and civil society's
  analyses. A separate page for them was tried and dropped at the maintainer's wish; the home page section stays.
- **`robots.txt` allows everything** and points to `sitemap.xml`: the site wants to be read, by search engines and
  AI crawlers alike (the maintainer, 12 Nov 2026). A block seen from outside comes from the host's settings, not
  the site.
- **Neutral order:** groups by the number of their MPs on the roll, then alphabetically; names in Serbian
  alphabetical order (`collate`: č, ć after c; dž, lj, nj as one letter).
- **Groups as the Assembly writes them:** abbreviations ("ПГ АВ-СНСДС") in the report layout, list names in the
  listinzi. An MP's name is the report layout's ("Surname Given") where they have one.
- **Hosting:** GitHub Pages through Actions at zailiprotiv.rs (domain bought 12 Nov 2026). The custom domain is
  set in the repository's Pages settings and DNS by the maintainer; the build also writes `CNAME`. The votes
  workflow starts **pages** after committing data, as pushes by the workflows' token start no other workflow.

### Scope

- The current convocation first, then the older ones (the maintainer's decision, 12 Nov 2026).
- **Each convocation has its own folder**, `data/<N>/` (index, laws, votes, bills, summaries, notes), and every
  command takes `--convocation N` before the command (default: the current one). The site is built from all of
  them: `zakoni.html` is the current convocation, `zakoni-<N>.html` an earlier one; a law's address is its title,
  the current convocation's laws first, so they never change when an older one is added (an older law of the same
  title gets `-2`). An MP's page lists their final votes in every convocation.

## Known issues and open decisions

- **Next, chosen by the maintainer (13 Nov 2026), after looking at TheyWorkForYou, abgeordnetenwatch, GovTrack,
  NosDéputés and Parlameter:**
  1. votes by topic, not only by law (done 13 Nov 2026, from TheyWorkForYou): "Po oblasti" on the MP page, the areas
     with five laws or more, each with its votes and the laws voted against, folded;
  2. a short note of method on every page that shows a figure, linked to one page "Kako računamo" (done 13 Nov
     2026: `kako-racunamo.html`, a section per figure, linked from each label and the footer; keep it in step with
     any change to how a figure is computed);
  3. following an MP or the laws: RSS feeds (done 13 Nov 2026: Atom, `zakoni.xml` with the 50 newest laws and
     `poslanik/<slug>.xml` with an MP's 40 newest final votes, linked from the pages); e-mail needs a sending service;
  4. an MP's activity (done 13 Nov 2026, from NosDéputés): presence at final votes where the absent are listed (the
     report layout, twenty or more), against the convocation's median; speeches in the notes read. The method page
     says absence can be justified, or a walkout in protest. Amendments by MP still to do;
  5. the words an MP uses most, against all MPs (done 13 Nov 2026, from Parlameter; no model): `profiles.distinctive`,
     a smoothed log-odds ratio over seven-letter stems, a stop list, twelve words used in five speeches or more;
  6b. design taken from TheyWorkForYou (done 13 Nov 2026): records in words, not only numbers ("dosledno za",
     "uglavnom", "češće", "mešovito", `site.leaning`; "skoro uvek isto" … in "Sa kim glasa isto"), the MP's group's
     record beside theirs in "Po oblasti", a menu of the page's sections, the date of the last vote. A page per area
     (`oblast/<slug>.html`, every convocation, and `oblasti.html`), linked as tags from the law page, the home list
     and the MP's table, from abgeordnetenwatch's topic tags. Tabs by period on the MP page (done 13 Nov 2026): "Svi sazivi"
     and one per convocation over the votes for and against, "Drugačije", "Po oblasti" and "Po vrsti", each panel
     built on the server (`view` in `site.build`), switched by the page's script; without it, every convocation shows.
  6c. from HowTheyVote, Parlametar, Datan and abgeordnetenwatch (done 13 Nov 2026): a page per sitting
     (`sednica/<title>-<Assembly number>.html`, `sednice.html`); downloads (`podaci.html`: `podaci/zakoni.csv`,
     `podaci/glasovi-<N>.csv`, and each law's roll call as `zakon/<slug>.csv` and `.json`; free use with credit); a
     "Prijavi grešku" link on every page, a prefilled GitHub issue (no script); filters by area and year on the laws
     list; treaties counted but left out of the words in "Po oblasti" (TheyWorkForYou's informative votes). MP page
     lists show six rows and link to the full table at the bottom, to keep pages light (tabs had made them 2 MB).
  6. some interaction for readers (questions to MPs, or comments): needs a server or a third party, which principle 5
     rules out for the pages as they are — to be decided with the maintainer before building.

- The Fifteenth convocation was convened in November 2026, after the October elections. The listings show the
  Fourteenth's sittings (2024–2026). When the Fifteenth's appear there, the Fourteenth moves to the archive:
  add its archive page to `config.CONVOCATIONS`, the Fifteenth's listings and laws page, and set `CURRENT`.
- How a vote is tied to its act (title, bill, memorandum) on the Assembly's site.
- Summaries of the laws (Claude's, from the memorandum) and a Cyrillic edition of the site.
- MPs whose name is spelled differently across layouts (Ana/Anna Oreg, middle initials) appear twice: a manual
  joining file is still to add.

## Decisions log

- **12 Nov 2026:** the project starts, named "Za ili protiv" (`zailiprotiv`): laws, their effects as their
  proposers state them, and how every MP voted. Names of MPs are public. The source is the Assembly's own site;
  Otvoreni parlament was looked at first (its "API" is HTML pages behind a Cloudflare check) and is not a source.
  The repo lives in the new organisation `javni-uvid` ("public inspection" of what institutions do), meant to hold
  the election repos too once their sites have a domain of their own (GitHub Pages addresses don't follow a
  renamed organisation).
  A probe confirmed that GitHub's runners reach parlament.gov.rs (the sandbox doesn't, nor can it download
  workflow artifacts, so workflows print what needs reviewing to their log).
