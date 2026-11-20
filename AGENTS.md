# AGENTS.md

How to work on this repository, what must not change, and why things are as they are. Written for coding agents
and for people. This file holds the rules of work and the principles; the decisions of each part of the project
are in the files the map below names (20 Nov 2026: this file had grown to 73 KB, read whole by every agent).
**Keep them current:** when a decision is made or changed, add it to its part's file in the same commit; a rule
of work or a principle, here. README.md describes the project for its users; these files are for those who change
it. Dates are the maintainer's decisions unless said otherwise.

## How to work here

- **A branch and a pull request per task** (20 Nov 2026, the maintainer's decision, as several agents now work at
  once; until then everything was committed straight to `main`):
  - **Each agent in an Orca worktree** of its own (`orca worktree create --name <task> --no-parent`, from the main
    clone): Orca makes the branch, `<the maintainer's GitHub login>/<task>`, from `origin/main`, and the folder under
    `~/orca/workspaces/zailiprotiv/`. Short-lived: hours, a day at most. Orca runs `uv sync` in a new worktree itself
    (`orca.yaml`, 20 Nov 2026); `tzdata`, which Windows lacks, is a dependency there.
  - **Before starting, `gh pr list`:** when an open pull request touches the same files, build on it or wait
    (19 Nov 2026: two agents added the same setting to the live service in one evening).
  - **Before pushing,** `git rebase origin/main` and `uv run pytest -q`; then `gh pr create` (the template asks what,
    why, what was checked, and whether the maintainer must decide); `gh pr checks --watch` until **test** passes on
    it, then `gh pr merge --squash`: one commit on `main`, the branch deleted. `sh tools/posalji.sh <body file>` does all of it
    in this order and waits for **test** to start before it counts as passed (20 Nov 2026: a pull request was
    merged before its test began); `--ne-spajaj` stops before the merge. A pull request that needs the
    maintainer (a principle, something seen from outside, DNS) says so and is left for them to merge.
  - **A merged task's worktree is removed** (20 Nov 2026, the maintainer's decision: 23 merged ones were left,
    each a full copy with `data/` and a `.venv`). `tools/pocisti.sh`, run by `posalji.sh` after its merge, removes
    every worktree with no changes whose pull request was merged on exactly its commit over ten minutes ago
    (`orca worktree rm --delete-branch`); an agent's own goes in the next agent's run, as Orca would stop its
    terminal. A pull request merged by hand on GitHub: `sh tools/pocisti.sh` (`--proba` only lists).
  - **The workflows still commit data straight to `main`** (votes, transcripts, notes, summaries…): a branch will
    lag behind in `data/`, which is fine while a task doesn't change `data/`.
  - **`main` is guarded on our side:** GitHub's rulesets can't exempt the workflows' own token (GitHub Actions can't
    be a ruleset's bypass actor), so a ruleset requiring pull requests would stop the hourly data runs. The
    repository's ruleset only forbids deleting `main` and force-pushes; `tools/hooks/pre-push` refuses a push to
    `main` from a clone set with `git config core.hooksPath tools/hooks` (its worktrees share it). For the same
    reason GitHub's auto-merge can't be used (it needs a required check, which would stop the workflows' pushes too),
    so the agent waits for **test** and merges. Squash is the only merge; merged branches are deleted.
  - **A decision goes at the end of the section it belongs to** in its part's file (the map below), rather than
    inside another's paragraph.
  - **`live/AGENTS.md` holds the live service's decisions** (20 Nov 2026): a decision about `live/` or the live
    page goes at the end of that file, not here. Agents get it when they work in `live/`; read it too before
    changing what the service takes from the site (`pages_mikrofon.py`, `mikrofon.js`, the counter's push).
  - Dependabot's monthly pull requests: merge them once their checks pass.
- **Run `uv run pytest -q` before every push.** The **test** workflow runs it again on every pull request and on
  `main`; a red run is fixed first. On Windows the roll-call and bill tests need poppler's `pdftotext` (`winget install
  oschwartz10612.Poppler`), named by `PDFTOTEXT` where Git's (xpdf's, whose columns fall elsewhere) is first on the PATH,
  and `PYTHONUTF8=1`; the maintainer's computer has both set for the user (20 Nov 2026), and then every test passes. An agent's shell may lack them although they are set: `posalji.sh` reads just these two from the user's Windows
  settings when unset (20 Nov 2026, PR #79 stopped on 44 failures for it); for `uv run pytest -q` alone, export them.
- **Explain why in commit messages**: what changed for the site or the data, and the reason.
- **Update README.md with every feature**, and this file with every decision.
- **Talk to the maintainer in Serbian** (Latin script), briefly. Code, comments and docs are in English.
- **A development environment may not reach parlament.gov.rs, the subdomains or the buckets; GitHub's runners can.**
  Read the outside through workflows: **peek** (a page's text), **health**, **visits** (Cloudflare's counts, how long
  the live page is in view (`tools/watching.py`: its part asked every 5 s while in view, summed per hour), what
  Cloudflare stopped, Google Search), **dns-check**, **probe**. Never ask the maintainer to paste secrets in chat.
- **Ask the Assembly little.** Requests name the project in the User-Agent and wait a second between pages;
  recurring reads are incremental.
- **Secrets live in GitHub Secrets and Cloudflare only**; `data/settings.json` holds public addresses and keys that
  are public by design (the analytics token, the IndexNow key).
- **Pages have a size limit and a guard.** `zailiprotiv site` fails when a page is over 1 MB or loads anything from
  another site (`publish.check`); **pages** then publishes nothing and the last site stays up. A list that can grow
  without bound (an MP's speeches, exchanges) gets a page of its own rather than growing the MP's page.
- **Workflows, safely** (17 Nov 2026): every action pinned to a commit with its version beside it (Dependabot moves
  them); inputs and context reach scripts through `env`, never pasted into `run:`; a checkout keeps no token unless
  the job pushes; each workflow (or job) asks for the least permissions. **security** checks all of this (zizmor,
  `.github/zizmor.yml` lists the accepted findings), the Python packages (pip-audit) and the code (CodeQL).
- **Links have no ".html"** (13 Nov 2026): files keep their names, GitHub Pages serves `page.html` at `/page`, and
  `publish.clean_urls` rewrites links after the build. A page named like a folder (`podaci.html`) keeps its ending.
  `zailiprotiv site --html-links` keeps the endings, to open the built pages from disk.
- **`zailiprotiv status`** says what the data still lacks per convocation; look before and after a data run.
- **How fast the pages are, measured before any work on speed** (20 Nov 2026): **visits** also prints the Core Web
  Vitals Cloudflare Web Analytics measured (`tools/vitals.py`: LCP, INP and CLS as shares of loads good, middling
  and poor, by host and device and for the most opened pages; for a page good in fewer than three loads of four,
  the elements that jumped or were drawn late). The first reading, of the site's first week: every page well over
  the line but the quiz, whose note at the foot jumps while the script lays the questions out.
- **A search by meaning, on trial** (20 Nov 2026, the maintainer's decision, to be judged after a day or two of
  use). On the maintainer's computer an MCP server, `cognee-zailiprotiv`, holds two sets of texts taken from
  `origin/main` (kept outside the repository, nothing sent out). **When the tool is there, ask it first**, with
  `recall`, `search_type: "CHUNKS"`, `top_k` 5 or more, the question in Serbian or English:
  - `datasets: "zailiprotiv"`, how the project is made: every decision of this file and of `live/AGENTS.md`, every
    commit message on `main`, the issues, and a map of the code (each module's docstring with its functions' first
    lines, each workflow's header, the READMEs by section). For why something is as it is, whether something was
    tried, and where the code for something is.
  - `datasets: "skupstina"`, what the site holds, in Latin script: every law and bill of every convocation with the
    summary of its memorandum, the debates' summaries, the other voices' notes, what an MP says. For finding laws
    by subject when the title doesn't say it (a quiz, public names, notes).
  A hit begins with where it is from (a commit, a section, a file under `data/`): **read that in the repository
  before relying on it.** The store lags behind `main` until refreshed, these files stay the truth, and a hit from
  `skupstina` is a pointer and never a source: a figure, a vote or a quote comes from the document (principles 2
  and 6). For an exact word or a rare name use `grep` and `git log -S`; it finds by meaning and misses those.
  **A hit that doesn't say where it is from** (most of a law's: the store cuts a text into pieces of some 400
  characters and only the first keeps that line; and the summaries under `data/` are in Cyrillic, so `grep` for
  the Latin words finds nothing): ask with `include_references: true`, and
  `python C:/Users/marko/cognee-zailiprotiv/odakle.py text_<md5> …` turns each hit's `document=text_<md5>` into
  that line. (20 Nov 2026, tried on 120 laws with 14 questions whose law was known: the model in use had the
  right law in the first five for 13 and named it for one; two models that read a whole summary at once found no
  better, 13 of 14, named 13, and cost 2 to 3 GB of memory more and a store built anew, so the model stays.)
  Never call its `forget`. Where the tool is missing (another machine, the server off), work as before.
  **Agents add to it themselves** (20 Nov 2026, the maintainer's decision), with `remember`,
  `dataset_name: "beleske"`, `self_improvement: false`:
  - **Always that name, never a new one** (cognee's own advice for a rules file): the other two sets are rebuilt
    from `main` and lose whatever else is put in them; `beleske` is never emptied and is copied at every refresh.
  - **What:** what cost time to learn and no file here says. Something tried that failed and why, how a source or
    a tool behaves, where a thing is found, what a text from outside the repository says (with its address).
  - **How:** one fact a note, a few sentences: the model reads some 400 characters at a time, and a longer text
    comes back in pieces of which only the first says where it is from. The first line, in brackets, says what it
    is, the date and the task or pull request (`[beleška, 20 Nov 2026, PR #65]`). In Serbian or English.
  - **Never** a secret, an address or a key that isn't public, or anything of a person's private life
    (principle 4). A decision still goes in its part's file: a note is no place for it, and another agent's note
    is a pointer to check like any other hit.
  - **To find them** name both sets: `datasets: "zailiprotiv,beleske"`. A note that proved wrong is answered by a
    new note saying so.
  - A kind of text to be collected from `main` at every refresh, as the laws are, is asked of the maintainer in
    the pull request: what is collected is decided on their computer (`collect.py` beside the store).

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
     video of it (`youtube-nocookie.com`); between sittings, the last day's recording from the broadcaster's archive
     (videonet.co.rs, a plain `<video>`), from where a turn's "▶ snimak" says. Until the click the page shows our own
     button and loads nothing from either; the page and "O projektu" say so. The links work without the script;
     the script plays only archive files and YouTube ids it recognises;
   - **notifications from `mikrofon.zailiprotiv.rs`, only to who asks** (20 Nov 2026): one when a sitting's
     broadcast begins, at most once a day, carried by the browser's own push service (Google, Apple, Mozilla).
     The push has no content (the page's service worker writes the words), and the counter keeps only the
     address the browser gave, until it is turned off; the page and the method page say so;
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
| The live service `mikrofon.zailiprotiv.rs` (`live/`), its edge worker, notifications | `live/AGENTS.md` |
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
