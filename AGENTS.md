# AGENTS.md

How to work on this repository, what must not change, and why things are as they are. Written for coding agents
and for people. This file holds the rules of work and the principles; the decisions of each part of the project
are in the files the map below names (20 Nov 2026: this file had grown to 73 KB, read whole by every agent).
**Keep them current:** when a decision is made or changed, add it to its part's file in the same commit; a rule
of work or a principle, here. README.md describes the project for its users; these files are for those who change
it. Dates are the maintainer's decisions unless said otherwise.

## How to work here

- **The rules every javni-uvid project shares are in `osnova/`: read `osnova/work.md` before anything else**
  (20 Nov 2026, the maintainer's decision; until then each project kept a hand-made copy of them here). A branch
  and a pull request per task in an Orca worktree, `gh pr list` before starting, `sh tools/posalji.sh <body file>`
  to ship, the decision written down in the same commit, why in the commit message, Serbian with the maintainer.
  `osnova/security.md` holds the guards and `osnova/principles.md` the promises every project makes. The folder is
  a copy the **osnova** workflow brings from `javni-uvid/osnova`: a rule that should hold for every project is
  changed there, never in `osnova/` here. What follows is only this project's.
- **One conductor, and workers under it** (25 Nov 2026, the maintainer, after a sitting day on which three sessions
  changed the live service at once: 67 pull requests, restarts that held the day's mail back 50 minutes). One session
  is the conductor ("dirigent"), on Claude Fable 5.2; the agents it starts are Claude Opus 5.5 (the Agent tool's
  `model: "opus"`, or `orca worktree create --agent claude --model claude-opus-5-5`). **Only the conductor puts
  anything live** (`mikrofon.ps1 uzivo`, `nazad`) **and changes what the service keeps** (`/data`); a worker works in
  its own worktree up to a merged pull request and tells the conductor. Workers go by part (who speaks; the mail and
  the day's summary; the live page and the site), one at a part. During a sitting a release goes in a break, once a
  break, but for mending a false statement about a person. The maintainer's word holds in the session it was said
  in: that session passes it on with his words quoted, and a worker's or another session's word is never his.
- **A worktree** is under `~/orca/workspaces/zailiprotiv/`; Orca runs `uv sync` in a new one itself (`orca.yaml`);
  `tzdata`, which Windows lacks, is a dependency there. The workflows that commit data straight to `main` are
  votes, transcripts, notes, summaries and the like.
- **A decision goes at the end of the section it belongs to** in its part's file (the map below), rather than
  inside another's paragraph. A rule of work or a principle of this project, here.
- **`live/AGENTS.md` says in short what holds for the live service** (23 Nov 2026), and its map names the file of
  each part's decisions (`docs/decisions/live-*.md`): a decision about `live/` or the live page goes at the end of
  that file. Agents get the short one when they work in `live/`; read it too before changing what the service takes
  from the site (`pages_mikrofon.py`, `mikrofon.js`, the counter's push).
- **The tests are `uv run pytest -q`.** The **test** workflow runs them again on every pull request and on
  `main`; a red run is fixed first. On Windows the roll-call and bill tests need poppler's `pdftotext` (`winget install
  oschwartz10612.Poppler`), named by `PDFTOTEXT` where Git's (xpdf's, whose columns fall elsewhere) is first on the PATH,
  and `PYTHONUTF8=1`; the maintainer's computer has both set for the user (20 Nov 2026), and then every test passes. An agent's shell may lack them although they are set: `posalji.sh` reads just these two from the user's Windows
  settings when unset (20 Nov 2026, PR #79 stopped on 44 failures for it); for `uv run pytest -q` alone, export them.
- **Update README.md with every feature**, and this file with every decision.
- **A development environment may not reach parlament.gov.rs, the subdomains or the buckets; GitHub's runners can.**
  Read the outside through workflows: **peek** (a page's text), **health**, **visits** (Cloudflare's counts; which site sent
  readers to which page on which day, never the other site's page, as browsers send only its host; how long
  the live page is in view (`tools/watching.py`: its part asked every 5 s while in view, summed per hour), what was started on it by hour (`tools/uses.py`), what
  Cloudflare stopped, Google Search), **dns-check**, **probe**. Never ask the maintainer to paste secrets in chat.
- **Ask the Assembly little.** Requests name the project in the User-Agent and wait a second between pages;
  recurring reads are incremental.
- **Secrets live in GitHub Secrets and Cloudflare only**; `data/settings.json` holds public addresses and keys that
  are public by design (the analytics token, the IndexNow key).
- **Pages have a size limit and a guard.** `zailiprotiv site` fails when a page is over 1 MB or loads anything from
  another site (`publish.check`); **pages** then publishes nothing and the last site stays up. A list that can grow
  without bound (an MP's speeches, exchanges) gets a page of its own rather than growing the MP's page.
- **Workflows, safely:** the rules are in `osnova/security.md`; what this project guards besides, and what it
  accepts as it is, in `docs/decisions/security.md`. `.github/zizmor.yml` lists the accepted findings.
- **Links have no ".html"** (13 Nov 2026): files keep their names, GitHub Pages serves `page.html` at `/page`, and
  `publish.clean_urls` rewrites links after the build. A page named like a folder (`podaci.html`) is no exception (26 Nov 2026): GitHub
  Pages serves it at `/podaci` too, and only `/podaci/` is the folder.
  `zailiprotiv site --html-links` keeps the endings, to open the built pages from disk.
- **`zailiprotiv status`** says what the data still lacks per convocation; look before and after a data run.
- **How fast the pages are, measured before any work on speed** (20 Nov 2026): **visits** also prints the Core Web
  Vitals Cloudflare Web Analytics measured (`tools/vitals.py`: LCP, INP and CLS as shares of loads good, middling
  and poor, by host and device and for the most opened pages; for a page good in fewer than three loads of four,
  the elements that jumped or were drawn late). The first reading, of the site's first week: every page well over
  the line but the quiz, whose note at the foot jumps while the script lays the questions out.

## Principles

The project's promises to its readers. Never change them without the maintainer.

1. **The same rules for every MP, group and party.** Nothing is hardcoded or singled out; every measure is computed
   the same way for all; lists are ordered by neutral rules (number of seats, alphabet), never by preference.
2. **Facts from primary sources only:** the Assembly's own publications (roll calls, bills with their memoranda,
   stenographic notes) and laws as published. Otvoreni parlament (CRTA) and news may help find or check something,
   never supply a figure or a vote.
   - **Other voices, labelled** (12 Nov 2026): for the laws with most votes against, opinions of independent bodies
     (Fiscal Council, Protector of Citizens, Commissioner, Venice Commission, ODIHR, European Commission) and analyses
     by media and civil society, as notes with source, date and link, summarised and attributed ("Fiskalni savet
     ocenjuje …"); independent bodies apart from media and civil society. A note never supplies a figure, a vote or
     a ranking, and the site takes no side. Kept in `data/<N>/notes/<bill file>.json` (`checked`, `by`,
     `independent`, `media`; each note `source`, `date`, `url`, `title`, `note`), gathered by a model from pages it
     fetched, then reviewed: professional associations count as civil society; a source reported second-hand says
     so; a note about another act is dropped; supportive views are kept when found, never invented to balance;
     private persons by role only.
3. **A law's effects are its proposer's,** summarised from the bill's memorandum and analysis of effects, linked
   and labelled as the proposer's assessment. The site adds no judgement of whether a law is good (12 Nov 2026).
4. **MPs are public officials: their names and votes are public** (12 Nov 2026). Only what they do in office;
   nothing about their private lives of the site's own finding.
5. **Nothing from third parties on the pages:** no cookies, external fonts or scripts. The maintainer's exceptions:
   - **visits counted** by Cloudflare Web Analytics (13 Nov 2026; no cookies, totals per page) when `settings.json`
     has `analytics_token`; `publish.check` lets this one script through; the footer and "O projektu" say so;
   - **visitors' votes** sent to the project's own counter (`worker/`; 13 Nov 2026) when `votes_api` is set; what is
     kept is on the method page (see "Visitors' votes" below);
   - **a player on `mikrofon.zailiprotiv.rs`, only on a click** (18 Nov 2026): while the broadcast is on, the YouTube
     video of it (`youtube-nocookie.com`); after it, the same video for the last day while it is public and the archive
     has no file of that day yet (25 Nov 2026, the maintainer: "Može"; until then the links went with the broadcast);
     between sittings, the last day's recording from the broadcaster's archive
     (videonet.co.rs, a plain `<video>`), from where a turn's "▶ snimak" says. Until the click the page shows our own
     button and loads nothing from either; the page and "O projektu" say so. The links work without the script;
     the script plays only archive files and YouTube ids it recognises;
   - **a link to a speech starts by itself** (25 Nov 2026, the maintainer: "Prenos kreće sam"): opening a link to a
     finished speech that a reader chose to open (`/govor/<second>`, `#govor-<second>`) loads that player and starts
     it at the speech, only where the browser lets a page sound without a press; elsewhere its button waits for one
     and nothing is loaded. Every other player still only on a click;
   - **notifications from `mikrofon.zailiprotiv.rs`, only to who asks** (20 Nov 2026): one when a sitting's
     broadcast begins, once a day; one each time it goes on after a break of over 20 minutes (24 Nov
     2026, no limit); one when the day's summary is out; carried by the browser's own push service (Google, Apple, Mozilla).
     The push has no content (the page's service worker writes the words), and the counter keeps only the
     address the browser gave, until it is turned off; the page and the method page say so;
   - **the day's summary by mail, only to who asks** (22–23 Nov 2026): after a sitting day, from
     `sazetak@mikrofon.zailiprotiv.rs` through Cloudflare Email Service, confirmed by a click; the address kept
     sealed for the maintainer's key until the reader leaves (one click in every mail), nothing about opening it; the
     one thing a mail loads is the MPs' portraits from the site itself, at the same address for every reader (25 Nov
     2026);
     the maintainer, Marko Pomorišac, is the controller, as "Politika o privatnosti" (`privatnost`) says;
   - **following a sitting MP by mail, only to who asks** (25 Nov 2026, the maintainer, of the proposal's decisions 3–11: "Po preporuci
     za sad"; of the built step: "moze"): the morning after a day on which the MP spoke in the hall, by the broadcast's caption only,
     at most one mail a day, from the same address and through the same service as the day's summary; explicit consent by a click in
     a mail that names the MP, for each one; the address and whom it follows kept sealed for the maintainer's key, padded to one
     length, with no hash or count per MP, until the reader ends it (one press in every mail); no name in a subject, no picture; the
     links to speeches are the same for every reader and counted as one sum a day. What Cloudflare keeps of a mail it carries is on
     `privatnost`;
   - things of others' making **served from the project itself**: the search (Pagefind), MPs' portraits from the
     Assembly (`photos.py`, `data/photos/`), and the project's own subdomains for the notes' pages and the downloads.
6. **What MPs say is not censored and not shaped** (13 Nov 2026). Quotes are word for word, checked against the
   notes, never cut inside, softened or cleaned; every name an MP says stays as said; nothing is left out for being
   harsh, personal or uncomfortable (a summary keeps what recurs and what is about the law, by rules that don't look
   at whom it favours; charged words in quotation marks as the speaker's); the site adds no label, tone or verdict
   and says so. Texts written before this keep their form until written again.

## Where the decisions are

Read the file of the part you work on before you start; each keeps its sections' names as they were here.

| Part | File |
|---|---|
| Sources (the Assembly's site, roll calls), laws, bills, summaries, debates and the notes, the data runs and their clock, a new convocation | `docs/decisions/data.md` |
| The code's layout, the build's steps, the commands (`cli/`) | `docs/decisions/code.md` |
| The site: pages, design rules, accessibility, visitors' votes and quizzes, search engines | `docs/decisions/site.md` |
| Broadcasts and recordings on the site: who spoke when and how long, the archive, transcripts | `docs/decisions/recordings.md` |
| The live service `mikrofon.zailiprotiv.rs` (`live/`), its edge worker, notifications, the day's mail | `live/AGENTS.md` (in short, and the map of `docs/decisions/live-*.md`) |
| The visitors' counter (`worker/`) | `worker/README.md`, and "Visitors' votes" in `docs/decisions/site.md` |
| Security: what is guarded against per part, what is checked before a merge, what is accepted | `docs/decisions/security.md` |
| The project's course, day by day | `docs/decisions/log.md` |

## Open questions

- Interaction for readers beyond votes (questions to MPs, comments) needs a server or a third party, which
  principle 5 rules out as it stands: decide with the maintainer first.
- Amendments by MP; votes on amendments aren't among the published roll calls.
- Summaries of large laws cover the reasons and the first articles (the 8,000-character limit).
- Speakers who spoke mostly for the Government are left out of "what an MP says" by hand: a rule is needed first.
- The newsletter is the weeks' feed sent by a mailing service; `newsletter_url` in `settings.json` stays empty until
  the maintainer picks one.
