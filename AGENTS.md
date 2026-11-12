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
  site through `workflow_dispatch` (start with **probe**).
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

- **Roll calls:** the Assembly publishes each vote as a PDF under `/upload/rezultati_glasanja/` (by year, sometimes
  by sitting: `2026/20.pdf`, `2026/osma_sednica/1.pdf`). Each gives the kind of vote (e.g. on the act as a whole),
  the date and time, and every MP with their vote (for, against, abstained, did not vote, not present) and club.
- **Where they are listed is not known yet.** `zailiprotiv probe` walks the site from its home page, follows the
  links most likely to lead to sittings first, and reports every roll-call PDF found with the pages linking to it.

### Scope

- The current convocation first, then the older ones (the maintainer's decision, 12 Nov 2026).

## Known issues and open decisions

- The listing pages for roll calls, and whether GitHub's runners reach parlament.gov.rs: the **probe** answers both.
- How a vote is tied to its act (title, bill, memorandum) on the Assembly's site.
- Site layout, languages and hosting: to decide once the data is in.

## Decisions log

- **12 Nov 2026:** the project starts, named "Za ili protiv" (`zailiprotiv`): laws, their effects as their
  proposers state them, and how every MP voted. Names of MPs are public. The source is the Assembly's own site;
  Otvoreni parlament was looked at first (its "API" is HTML pages behind a Cloudflare check) and is not a source.
  The repo lives in the new organisation `javni-uvid` ("public inspection" of what institutions do), meant to hold
  the election repos too once their sites have a domain of their own (GitHub Pages addresses don't follow a
  renamed organisation).
