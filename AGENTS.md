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
  - Practice in the session summaries (12 Nov 2026), to be confirmed by the maintainer:
    - no sums or figures the memorandum doesn't state (two added-up totals were taken out);
    - the proposer's charged terms are quoted and attributed ("„НАТО агресија“, како наводи образложење"),
      never replaced by a softer word of ours; evaluative phrases of the proposer's ("од изузетног значаја") are
      left out; legal statuses ("пројекат од посебног значаја") stay, attributed;
    - no persons: signatories, MPs who proposed a bill, appointees, people named in court cases;
    - in the visa and other bilateral agreements, the memoranda's passages on how the other country stands on
      Kosovo or voted on the Srebrenica resolution are left out under the no-politics rule;
    - a malformed figure in a memorandum is quoted as written, never corrected.
  - In large laws the explanation of individual articles is cut at the material's limit (8,000 characters), so
    their summaries cover the reasons and the first articles. To revisit with a higher limit for those laws.

### Links between laws and votes

- `link.py`: a roll call's act is named by its **PDF**, never by the sitting page's link text, which is sometimes
  out of step with the PDF behind it (on 13 March 2025 the link for the visa agreement with Venezuela opens the
  vote on Guatemala's). Names are compared by their words only (no quotes, dashes, commas, item numbers or
  proposer); Latin look-alikes are read as Cyrillic only in words that mix the scripts.
- A vote is on a law when its name is the law's (or starts with it) between the bill's submission and the law's
  passing; the final vote is that on the day passed, on the act as a whole where the PDF says so. A law left
  without one takes that day's vote sharing 90% of its words, or 95% of its letters (typos), when unambiguous and
  not taken by another law: marked `"matched": "close"`.
- Fourteenth convocation (12 Nov 2026): 394 of 395 laws have their final vote (388 exact, 6 close). The Venezuela
  visa agreement (passed 13 March 2025) has no roll call among the PDFs the Assembly links for that day.

### Site

- **Static pages in Latin script** (`site.py`, Jinja2 templates): home, laws by kind, a page per law (facts,
  documents, an excerpt of the proposer's memorandum labelled as such, the final vote by group and by MP, the other
  votes on the act), MPs, a page per MP (their final votes on laws). Cyrillic from the Assembly's documents is
  transliterated; a test checks no Cyrillic is left. A Cyrillic edition can follow, as in the election site.
- **No scripts at all**, nothing from other servers. Colours mean kinds of vote (for, against, …), never a group.
- **Home page:** "Najviše glasova protiv" first (the maintainer's request, 12 Nov 2026): the laws whose final
  vote had the largest share against among votes for and against, ties to more votes against, then newer. Named
  for what it measures; "controversial" would be a judgement. Then the newest laws.
- **Neutral order:** groups by the number of their MPs on the roll, then alphabetically; names in Serbian
  alphabetical order (`collate`: č, ć after c; dž, lj, nj as one letter).
- **Groups as the Assembly writes them:** abbreviations ("ПГ АВ-СНСДС") in the report layout, list names in the
  listinzi. An MP's name is the report layout's ("Surname Given") where they have one.
- **Hosting:** GitHub Pages through Actions at zailiprotiv.rs (domain bought 12 Nov 2026). The custom domain is
  set in the repository's Pages settings and DNS by the maintainer; the build also writes `CNAME`. The votes
  workflow starts **pages** after committing data, as pushes by the workflows' token start no other workflow.

### Scope

- The current convocation first, then the older ones (the maintainer's decision, 12 Nov 2026).

## Known issues and open decisions

- The Fifteenth convocation was convened in November 2026, after the October elections. The listings show the
  Fourteenth's sittings (2024–2026). Earlier convocations' sittings are in the archive pages, likely with their
  own `Listinzi` links: still to check.
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
