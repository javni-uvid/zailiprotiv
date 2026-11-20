# AGENTS.md

How to work on this repository, what must not change, and why things are as they are. Written for coding agents
and for people. **Keep it current:** when a decision is made or changed, update this file in the same commit.
README.md describes the project for its users; this file is for those who change it. Dates are the maintainer's
decisions unless said otherwise.

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
  - **The workflows still commit data straight to `main`** (votes, transcripts, notes, summaries…): a branch will
    lag behind in `data/`, which is fine while a task doesn't change `data/`.
  - **`main` is guarded on our side:** GitHub's rulesets can't exempt the workflows' own token (GitHub Actions can't
    be a ruleset's bypass actor), so a ruleset requiring pull requests would stop the hourly data runs. The
    repository's ruleset only forbids deleting `main` and force-pushes; `tools/hooks/pre-push` refuses a push to
    `main` from a clone set with `git config core.hooksPath tools/hooks` (its worktrees share it). For the same
    reason GitHub's auto-merge can't be used (it needs a required check, which would stop the workflows' pushes too),
    so the agent waits for **test** and merges. Squash is the only merge; merged branches are deleted.
  - **In `AGENTS.md`,** add a decision at the end of the section it belongs to rather than inside another's
    paragraph: it is the file every task changes.
  - **`live/AGENTS.md` holds the live service's decisions** (20 Nov 2026): a decision about `live/` or the live
    page goes at the end of that file, not here. Agents get it when they work in `live/`; read it too before
    changing what the service takes from the site (`pages_mikrofon.py`, `mikrofon.js`, the counter's push).
  - Dependabot's monthly pull requests: merge them once their checks pass.
- **Run `uv run pytest -q` before every push.** The **test** workflow runs it again on every pull request and on
  `main`; a red run is fixed first. On Windows the roll-call and bill tests need poppler's `pdftotext` (`winget install
  oschwartz10612.Poppler`), named by `PDFTOTEXT` where Git's (xpdf's, whose columns fall elsewhere) is first on the PATH,
  and `PYTHONUTF8=1`; the maintainer's computer has both set for the user (20 Nov 2026), and then every test passes.
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
  Never call its `forget`. Where the tool is missing (another machine, the server off), work as before.

### The data runs

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

### The code

- **Build time** (18 Nov 2026): the steps that change each file on its own (the Cyrillic twins, `clean_urls`,
  `check`) share the files among the processors (`publish._pool_map`; the output is the same, checked byte for
  byte). A push that changes only `src/zailiprotiv/static/` takes the pages workflow's fast path: the site the last
  successful run published (its Pages artifact, kept seven days) gets `static-patch` (static/ copied as the build
  copies it, the scripts' links cleaned, every page's `?v=`/`data-v` moved to the new `asset_version()`), checked to
  equal a full build. Day counts in pages ("u proceduri N dana") then stay as the last full build left them, until
  the next data run. Any other change takes the full build.
- `site.py` loads the data, works out what pages share (groups, lines, key votes) and renders the law and MP pages;
  the rest is in modules called from `site.build` with what they need: `pages_groups`, `pages_quiz`,
  `pages_procedure`, `pages_ballot`, `pages_lists`, `pages_floor`, `pages_presence`, `digest`, `downloads`, `feeds`,
  `cyrillic`, `publish`. New kinds of page go in a module of their own; a move is checked by building before and
  after and comparing every file.
- **Shared helpers** (20 Nov 2026): a JSON file that may be missing is read with `jsonfile.load(path, default)`
  and a store written with `jsonfile.save` (one entry per line); the month names (nominative, genitive, Cyrillic)
  and `day`/`day_of` are in `months.py`; "keep the file when a new reading shrank" is `jsonfile.shrank`.
- **`site.build` in three steps** (20 Nov 2026): `site.read` reads `data/` into `Sources`, each file once (the
  notes, the newest convocation's notes, the days read from the recordings, which `pages_govornici.render` and the
  live page's files take from it); then what the pages share is worked out, the newest convocation's `newer15`
  whole (what its notes count included, from `pages_floor.count`); then every template global is set at once and
  the pages are written. Nothing is put into a page after it is written, and no module hands data back through an
  attribute of its function: `pages_floor.count` returns a `Floor` (`pages_floor.render` writes its pages),
  `pages_quiz.render` a `Quiz` (its themes reach the areas' pages and "Glasaj i ti" as an argument),
  `pages_procedure.render` the bills no longer listed, `skupstina.index` the later convocation's titles.
- **The commands in a package** (20 Nov 2026, from a look at the project's structure): `cli.py` (1,672 lines) is
  `cli/`: `assembly` (reading the Assembly's site), `recordings`, `writing` (the model's), `buckets`, `build`, and
  `common`, which holds the convocation worked on (`common.DATA`, `ROOT`, `CONVOCATION`, set by `main` from
  `--convocation`) and the helpers the commands share; `__init__` builds the parser. A test that points the
  commands elsewhere patches `cli.common`. Moved unchanged and checked: every command's `--help` (both with and
  without `--convocation`) and `status` give the same text. It found `statistics` never imported in `govor`.

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

## Architecture

### Source: the Assembly's site

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

### Laws

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

### Debates and the notes

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
- **Varnice** (13 Nov 2026; `pages_floor.py`, no model): the chair's measures (warning, taking the floor away,
  removal; `MEASURES`, with talk about measures left out), exchanges of replies (two speakers taking turns four times
  or more, no speech over 400 words), points of order, harsh words (a fixed list), who speaks most. A measure goes to
  an MP only when the chair's sentence names a speaker of the sitting: addressed ("господине …", "посланику …") or
  right after the measure ("изричем опомену Стефану Јовановићу", 17 Nov 2026); a first name said must fit; several
  named at once count for none. Otherwise the context may make it "likely", said so. The rule can't tell whether an
  exchange is personal and the page doesn't claim it. Rankings count only MPs of that convocation (`as_mp`), not
  ministers or guests.

### The site

- **Static pages** (`site.py`, Jinja2), Latin script; Cyrillic from the documents is transliterated (a test checks
  none is left). **The Cyrillic edition** (13 Nov 2026; `cyrillic.py`) writes every page again under `cir/`, letter by
  letter back from Latin except what is Latin by nature (`KEEP`) and words where nj, lj, dž are two sounds
  (`_APART`: add to it when one is found); scripts' output is converted by `site.js`; share pictures and feeds stay
  Latin.
- **Design** (12 Nov 2026, chosen from three mock-ups): newspaper look, white page, Literata headlines (served from
  the site), colour only for "za" (blue) and "protiv" (orange), never for a group. The mark is the chamber as one arc.
  Neutral order everywhere: groups by seats then alphabet; names in Serbian order (`collate`). MPs are written
  "Surname Given" in lists and given name first where people search or say it (titles, the quiz, 17 Nov 2026).
- **One script of our own** (`static/site.js`): search and filters over `podaci.json`, stems for case endings,
  the Cyrillic observer, an MP's speech links. Pages work without it.
- **Pages:** laws by convocation (`zakoni.html`, `zakoni-<N>.html`), a page per law (`zakon/<slug>`), per bill in
  procedure, per area (`oblast/`), per sitting (`sednica/`), per week (`nedelja/`, `digest.py`, by rule), per
  convocation (`saziv-<N>`), per group and convocation (`grupa/<N>-<slug>`; a renamed group is followed by rule,
  `renamed`), MPs (`poslanici.html`, `poslanik/<slug>`), presence (`prisustvo`), Varnice (`replike`, `razmene`,
  `ko-najvise`, `varnice-svi`), "Skupština u brojkama" (`brojke`), downloads (`podaci.html`), method (`kako-racunamo`,
  a section per figure, linked from each label: keep it in step with any change to how a figure is computed).
  Feeds: new laws, bills, per area, per MP, weeks. A law's address is its title, current convocation first, so it
  never changes when an older one is added.
- **An MP's page:** opens with a card ("Ukratko", `mp_card.py`, 17 Nov 2026): a few facts, each one sentence with
  its number first and a link to where it comes from (presence, votes unlike the group's majority, speeches and
  hours at 130 words a minute, the longest speech, the busiest day, the three most frequent exchange partners,
  measures, harsh words, the most alike other group, distinctive words); a fact the data can't support is left out,
  not shown as zero. Then key votes (a rule: laws with a public name, then the most divided), votes against the
  group's majority, activity on the floor, what they say, quotes from debates, who they vote with. Every vote (for
  and against, by area and kind, by period and convocation) is on `poslanik/<slug>-glasovi` (`mp_votes.html`, the
  lists shared through `mp_macros.html`): those lists grow with every sitting and made the page 300 KB. **Speeches** (17 Nov 2026): the
  latest six sittings on the MP's page, every one on `poslanik/<slug>-govori` (by sitting and day, each speech a
  numbered link to its page in the notes; the links are kept short in the page and made whole by `site.js`). An MP
  with no vote on any list gets `noindex` and is left out of the sitemap. Same-person spellings are joined by hand
  in `data/mp_aliases.json` (candidates: names one letter or word apart that never appear in one vote).
- **One name, two people** (17 Nov 2026): an MP is known by the words of the name, so namesakes in different
  convocations became one MP (Aleksandar Jovanović of PUPS, 2020, and Aleksandar Jovanović Ćuta; two Nenad
  Mitrović). `data/mp_splits.json` (by hand, with the reason) renames the name in the convocations listed: to the
  name that person has elsewhere in the roll calls (`"as"`: "Ненад А. Митровић", "Наташа Ст. Јовановић"), or else
  with a mark, the year of birth the Assembly gives ("Александар Јовановић (1968)"); applied where roll calls and
  notes are loaded (`mps.split` in `site.load` and `site.load_transcripts`). The person of the newest convocation
  keeps the plain name and its address. Candidates come from **mp-years** (`mp_years.py`): every MP's year of birth
  (and town) in the Assembly's archive of convocations, compared across convocations (`data/mp_years.json`); a year
  off by one counts only with another town; two namesakes in one convocation are listed apart (the archive gives no
  father's initial, the roll calls do). Six names split on 17 Nov 2026; the check then found none left.
- **A father's initial stays with the given name** (17 Nov 2026): "Nenad A. Mitrović" is "Mitrović Nenad A."
  (`mitrovic-nenad-a`); until then the initial came first ("A. Mitrović Nenad"). An MP's earlier addresses (that
  order, and spellings joined by hand in `data/mp_moved.json`) are small pages that send on to the MP's, with its
  canonical address and `noindex`, as a bill's page does to its law's; `publish` keeps a canonical address a page
  names itself.
- **Downloads and share pictures in a bucket** (14 Nov 2026): every law's CSV, JSON and picture, MPs' pictures and
  `podaci/` would be thousands of files on the host; **pages** moves them out of the built site (`files-split`),
  makes the bucket behind `podaci.zailiprotiv.rs` hold exactly them (`files-upload`) and only then publishes the
  pages, which link there. Data are CC BY 4.0 (17 Nov 2026), said on the data page; code is MIT.
- **Hosting:** GitHub Pages at zailiprotiv.rs, behind Cloudflare's proxy; **pages** purges the cache after publishing.
  DNS is the maintainer's; DNS changes only with the maintainer's confirmation.
- **Read and worked without sight or a pointer** (20 Nov 2026, after a look at the site against WCAG 2.2 and NN/g):
  white text stands only on colours kept dark in both themes (`--za-on`, `--protiv-on`, `--uzdrzan-on`: the vote
  buttons and the chips of a vote cast; in the dark theme `--za` and `--protiv` are light, and white on them was
  2:1), and "uzdržan" as text has a grey of its own (`--uzdrzan-text`, 4.5:1 or more). On a phone the heading of
  a folded section of an MP's page is a button that says whether it is open (`site.js`, `.fold-btn`), so a keyboard
  and a screen reader open it too. Every page begins with "Preskoči na sadržaj" (`.skip`, seen when it has the
  focus). A new colour under text is checked for 4.5:1 in both themes.
- **The phone's menu and things to press** (20 Nov 2026; of a week's visits 83% were on phones, most on the
  Cyrillic pages): the menu's row is one line that fits, so its letters are as large as the row lets them be. On
  a phone the button reads "Glasaj" ("i ti" is `.wide-only`), which lets the letters grow from 13 to 15.5 px at
  360 px in Latin and from 11 to 13 px in Cyrillic (`4.3vw` and `3.55vw`, measured to fit from 320 px up: a new
  word in the menu means measuring again). The numbered links to speeches, the turns on the floor, the parts of a
  recording, the new convocation's links and the foot's links are 44 px high there (WCAG 2.5.5).
- **The search field never ends in nothing** (20 Nov 2026): the field on the home page and on "Poslanici" finds
  names and titles only, the search page the whole text, and of a week's visits almost none opened the search
  page. So the field's list always ends with "Traži u celom tekstu sajta" (the words go to `pretraga.html?q=`),
  Enter with nothing chosen does the same, and "nothing found" says what was looked through. The field is a
  combobox (arrows, Enter, `aria-activedescendant`). The two searches stay two until visits say otherwise.
- **Smaller things from the same look** (20 Nov 2026): the quiz's clock is stopped by a swipe or the wheel anywhere
  on the page, not only by a touch of the result (a time limit the reader can turn off, WCAG 2.2.1); on a phone a
  row of an MP's counts by convocation is a card with each count under its column's name (`.mp-floor`, `.th`),
  not a table dragged sideways; text is at most 42rem wide (about 88 letters; it was 46rem); a table's column
  that holds only a bar has a name for a screen reader. Left as they are, on purpose: the pale greys for "did
  not vote" and "not present" in a vote's bar (the numbers stand beside it in words), law titles as links with
  no underline in lists, and the home page's order on a phone (its parts stand on their own, so either order reads).
- **Offices in the Assembly, and its news** (20 Nov 2026, the maintainer's request: "the election of committee
  members, deputy Speakers and so on", each on the MP's profile; `offices.py`, `zailiprotiv offices`, run by
  **votes** each hour). Read from the Assembly's pages of its composition, not from the wording of its news: the
  Speaker (the biography, an MP's page with "Функција"), the deputy Speakers, the groups' chairs, every committee's
  table (председник, заменик председника, члан, заменик члана) and every standing delegation's (шеф, члан…), into
  `data/<N>/offices.json` for the newest convocation, each office with its page and the day first seen there (the
  pages give no day of election, and the site says so); the Fourteenth's committees and delegations once from its
  archive (`offices.ARCHIVE`). Committees' and delegations' own pages are read when their lists change, when a
  relevant news item is new, or weekly; the rest (five pages) every run. The news: the list on "Активности" (one
  page) into `data/vesti.json`, every item kept with the day first seen, `relevant` by a fixed rule on the title
  (elections, appointments, resignations, mandates, plenary sittings); new relevant ones are named in the run's log
  and summary. Shown: "Funkcije u Skupštini" on every MP's page, new or returning, by convocation, each linked to
  its page at the Assembly, in one order for all (the Assembly's own offices, groups, committees, delegations;
  chairs first); on the live page, the first line about the speaker. A name two MPs of the newest convocation share
  gets no office. The Assembly's own words, its masculine titles included ("predsednik"), as for every MP.
- **One scale of letter sizes; a number beside what it is compared with** (20 Nov 2026, the maintainer's choice of
  points 1–5 of a look at the design against portals of this kind: TheyWorkForYou, ProPublica's Represent and its
  principles for news graphics, Stanford's credibility guidelines, GOV.UK, NN/g). A page had 16–24 sizes of
  letters, eight of them between 12.8 and 15.7 px; every `font-size` in `style.css` is now one of eight steps
  (`--t-1` … `--t-8`: 12.8, 14, 16, 18, 20, 24, 30, 36 px) or of three for titles and big numbers (`--t-h1`,
  `--t-d1`, `--t-d2`), and a test refuses any other (the menu's and the tabs' letters, sized to fit a phone's row,
  are the exceptions): a new size is a step added to the scale, not a number in a rule. "Skupština u brojkama"
  opens with its four numbers each beside the convocation before and over every convocation as columns from zero
  (`pages_groups.trends`), and the earlier convocations' group tables are folded. On an MP's card "no vote unlike
  the group's" says for how many MPs that holds (of those with ten such votes or more since 2012), and the count
  of votes for and against is a headline's size, no longer the largest thing on the page: for most MPs it tells
  them apart least. The home page's card of the law that divided the chamber has no quotes (they are on the
  law's page), so it is as tall as the headline beside it; on a phone the first sitting's agenda, the box that
  repeats "no laws yet", the earlier convocation's "Varnice" and the list of laws that divided the chamber are
  left to their own pages, and two picked votes follow the card's one (9.3 screens became 7.2).
- **Labels are black; blue and orange mean a vote** (20 Nov 2026, the maintainer's "sort out the rest" of the look
  at the design). The small labels over a block ("Novi saziv", "Novo"), the mark of the new convocation and the
  accent of "Varnice" on a law's page wore the orange of "protiv"; they are black. Left: a link under the pointer
  turns blue and the live dot is orange, and the groups keep their colours on the home page and the live page
  (the maintainer's exception of 19 Nov), where the blue of one list stands near the blue of "za".
- **The laws' list sooner on a phone** (20 Nov 2026): the convocations are one row that scrolls sideways (the
  page's own brought into sight by `site.js`), and the line to the quiz follows the laws that divided the
  convocation, so the list no longer begins at the foot of the first screen.
- **Who stands behind the site, and its corrections** (20 Nov 2026, after Stanford's credibility guidelines and
  the Trust Project's indicators): "O projektu" says who makes the site as far as is public (the organisation,
  the open code and data, no advertising) and lists corrections from `data/ispravke.json` (by hand: `date`,
  `text`, `url`, `where`; newest first; empty until the first). Who pays for it and the names of people are the
  maintainer's to write.
- **The groups keep their colours, the first list's moved from blue to indigo** (20 Nov 2026, the maintainer:
  the colours may be fitted to the rest, and the pages are better with what moves a reader). On the home page the
  blue of "Aleksandar Vučić - Srbija pobeđuje" stood a few degrees of hue from the blue of "za" right under it;
  it is now indigo (`--g-av`: #3730a3, #818cf8 in the dark theme), as far from "za" as the red of "Studentska
  lista" is from the orange of "protiv", and the three still differ in lightness for colour-blind readers. The
  live page wears the same (`--c-av`, `page.HEX`). "O projektu" says the project is independent (the
  maintainer's words); the names of the people behind it wait.

### Design rules

What the pages keep to, from the looks at the site against WCAG 2.2, NN/g, GOV.UK, Stanford's credibility
guidelines, the Trust Project, ProPublica's principles for news graphics and TheyWorkForYou (20 Nov 2026, the
maintainer's request that they be written down "for now": they are working rules, changed as visits and readers
show otherwise, unlike the six principles above). A change to a page is checked against them.

1. **One scale of letter sizes.** A size is a step of the scale (`--t-*`); body text is 16 px; grey is for what is
   secondary. A test refuses a size outside the scale, on the site and on the live page.
2. **Colour means a vote.** Blue is "za", orange "protiv", and nothing else wears them (the exceptions are
   listed above). White text only on colours dark in both themes; any text 4.5:1 or more.
3. **The most important first.** A page says what it is and gives its main fact in the first screen; then the
   reasons, then the details and documents. The home page shows what the site holds by a few examples and
   leaves the lists to their own pages ("do less").
4. **A number never stands alone.** It has what it is counted of, something to compare it with (the convocation
   before, the half of MPs, how many others the same holds for), and a link to how it is computed. The largest
   thing on a page is what tells its subject apart, not what is the same for most.
5. **A trend is drawn, a table is kept.** Where the point is how something changed, columns or bars from zero
   come first, in black and grey, and the table follows (folded when long). No chart without its numbers.
6. **Asked after it is shown.** The visitor votes after what the law changes; a question never precedes what is
   needed to answer it.
7. **The phone first.** Four visits in five are on phones, most on the Cyrillic pages: every change is looked at
   at 320 and 390 px in both scripts, no page is wider than its screen, things to press are 44 px high, and a
   list shows its first rows and a way to the rest.
8. **Everything can be checked.** Each figure links its source and its rule; what a model wrote says so; what was
   corrected is listed. No rating of an MP and no ranking by preference (principle 1).
9. **For every reader.** Keyboard and screen reader reach everything; nothing moves by the clock that the reader
   cannot stop; the visitor is not addressed as a man or a woman.
10. **Measured, then changed.** Visits and the pages' speed are read before a change to how a page is laid out,
    and after it.
11. **What moves a reader stays** (20 Nov 2026, the maintainer: the pages are better with what draws a reader in).
    Faces, names, a speaker's clock, a sentence said in the hall and the groups' colours are kept where they
    lead into the page, and a tidier look is no reason to take them out. The groups' colours are an exception to
    rule 2 on the home page and the live page only: each hue stands apart from blue and orange (the first list's
    is indigo for that reason), the same hues on both pages, a key always names them, and they differ in
    lightness for colour-blind readers. They follow the same rules as everything else: the same for every group
    (principle 1), no judgement in the words beside them, and never the only way a fact is told.

### Visitors' votes ("Glasaj i ti")

- **The counter** (`worker/`, a Cloudflare Worker with D1; README there): a vote is one device's vote on one law or
  bill (`POST /z`), replacing its last; quotes can be marked convincing (`POST /c`); the quiz sends its laws at once.
  Kept: the vote, a hash of a random mark the browser made (with the secret `SALT`), the day, a daily hash of the
  network. No cookies, no addresses. Only items the site lists (`glasanje.json`). No robot check: **watch** opens an
  issue when one network sends most of a law's votes; removing is the maintainer's decision, written on the method
  page. **Uses** (17 Nov 2026, `POST /e`): a sum per day of the quiz's result reached and the share pictures opened,
  shared, copied, saved; nothing beside it. `GET /pregled` shows both. **The live page's uses** (19 Nov 2026,
  the maintainer's request, to see how long people stay and what keeps them): the same sums from
  `mikrofon.zailiprotiv.rs` beside the broadcast's ▶ (`mikrofon.pusti`, `live/AGENTS.md`): opened; in view 1, 5, 15, 30 min,
  time out of sight not counted; a recording of the archive played (`mikrofon.snimak`); the agenda, the speaker's
  lines, a share, the day in cards, a way to the site; each at most once per page opened. Same counter and switch
  as `mikrofon.pusti` (`config.VOTES_API`); the page's footer and the method page say so.
- **The page** (`glasaj.html`, `pages_ballot.py`, `listic.js`): the visitor's ballot ("Moj listić", kept in the
  browser only) beside the Assembly's results, the MPs and groups that voted alike, one law picked by a stated rule;
  the newest bill in procedure to vote on, and the next. **The quiz** (`kviz/podelili-salu`, `pages_quiz.py`,
  `glasaj.js`): the laws in `data/quiz.json` (chosen by the maintainer, 13 Nov 2026, each with a plain description;
  the page says so), or by rule without it. **Quizzes by theme** (17 Nov 2026, `kviz/<theme>`): per area of the
  current convocation with five or more laws with votes against, the most divided ten, by the same rule; areas get
  short names (`pages_quiz.THEMES`); Article 97's "other matters" gets none.
- **The quiz keeps a screen's height** (20 Nov 2026): the first reading of the pages' speed (`tools/vitals.py`)
  had the quiz as the one page under the line, its layout shift good in half of the loads. The cause: when one law
  gives way to the next by the clock (not on a tap, so the browser counts it), the note under the quiz jumped up,
  0.31 a time on a phone (0.1 is good). The list now holds the screen's height from the first paint and the strip
  of numbers is in its place before the script, so nothing under the quiz is in sight to jump (0.001 after).
- **The visitor is not addressed as a man** (20 Nov 2026; the MP's card lost its gender on 19 Nov). The question is
  "Kako ti glasaš?" (it was "Kako bi ti glasao?"), a vote cast is "Tvoj glas: za" ("Glasao si za"), and the
  counts speak in the present ("Kao većina u sali glasaš na 4 od 10 zakona") or of the vote ("tvoj glas", in the
  shared text "moj glas"). "Uzdržan" stays: it is the vote's name in the roll calls. New text for the visitor
  keeps to this: the present tense or "tvoj glas", no past participle.
- **The vote is asked after what the law changes** (20 Nov 2026, the maintainer's choice): on a law's page the box
  stood right under the result and asked the visitor to read first what was below it. It now follows "Šta zakon
  menja" and the voices from the debate. The result still stands above it: the page is the record of the vote
  first, and the visitors' sum is no poll, as the box says.

### Search engines

- **Allowed, AI training not** (16–17 Nov 2026): Cloudflare's AI Crawl Control blocks training crawlers and its
  managed robots.txt says so; Googlebot and Bingbot are let through by hand there (Cloudflare
  counts Googlebot as an AI crawler; blocked, Google could read nothing). Our `robots.txt` keeps `/pagefind/` out.
  `tools/blocked.py` (**visits**, `blocked`) shows what Cloudflare stopped and by which rule.
- **Each page:** a title of its own (a long one drops the site's name), a description of its own cut between words
  at 160 characters (`publish.fit_head`), a canonical address, its twin in the other script (`hreflang`, Latin the
  default), large image previews allowed, the place in the site as BreadcrumbList made from its crumbs; the home page
  names the site and its publisher (WebSite, Organization), the data page its downloads (Dataset). A 404 page of its
  own (`noindex`). Favicon also as PNG (Google shows no SVG).
- **The sitemap** lists every indexed page in both scripts with the day its main text last changed and its pictures;
  **IndexNow** tells Bing and others which pages changed after each publishing (`tools/indexnow.py`; the hashes in
  the build's cache; `indexnow_all` sends all). Search Console and Bing Webmaster Tools are the maintainer's;
  `tools/search.py` (**visits**, `search`) reads Search Console with a service account key in `GSC_KEY`.

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
  "Svaki glas i svaka reč iz Skupštine" (his choice of four). While the newest convocation has passed no law
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

## Broadcasts and recordings

The Assembly broadcasts its sittings live and keeps the recordings with its broadcaster (videonet.co.rs), linked
from its page "Prenosi". Since 17 Nov 2026: while the newest convocation's listing marks a plenary sitting
"(у току)", the home page and "Sednice" carry a bar linking to the live broadcast (`config.LIVE`) and to "Ko sada
govori" (`live_page`, see below); each sitting's page lists the recordings of its days (`videos.py`,
`data/<N>/videos.json`, read by **votes** for the current and the newest convocation; earlier ones by hand). Both
are links: the site plays nothing itself (principle 5). The notes carry no times, so a speech cannot be linked to
its minute.

### Who is speaking now (`live/`)

`mikrofon.zailiprotiv.rs`: who is speaking in the Assembly now and who spoke today, read from the live broadcast by a
service in Docker on the maintainer's computer, behind a Cloudflare tunnel (`live/`), with a worker in front of it
(`live/edge/`). **Its decisions are in `live/AGENTS.md`** (20 Nov 2026: moved there, as this file had grown to
85 KB, more than half of it about that service, read by every agent whatever its task): the page and what it shows,
the captions and names, the automatic transcript, the day's steps, notifications, testing and putting live. Read it
before changing `live/`, the site's `mikrofon` page or the counter's push. What the site makes of the broadcast's
records and recordings stays here:

- **Who spoke when, kept** (17 Nov 2026): the service keeps a record per day (`/dan/<date>.json`: each turn, how
  many frames named the speaker, its YouTube video and HLS segments, and the spans when the broadcast was seen at
  all); **votes** takes the records in each hour (`uzivo-pull` → `data/<N>/uzivo/<date>.json`, the convocation by
  date). A run that can't reach the computer changes nothing; records alone are committed without starting the
  chain, as they change every hour of a sitting. Planned on them, in this order (the maintainer): each speech in
  the notes linked to its minute in the recording; speaking time by MP and group; the records as downloads. Outside
  `pokriveno` there is no record, and whatever uses them says so.
- **A speech's minute in the recording** (17 Nov 2026, `uzivo.minutes`, `notes_site._clip`): a day's speeches (the
  chair's left out, one speaker's in a row as one) are lined up with the day's turns (named in two frames or more)
  by the order of the speakers' names, difflib's matching blocks; a speech gets its turn's place, the first of a
  run only, and where the record has a gap or the order disagrees it gets nothing. The link is the YouTube video at
  (first segment − 1) × segment length, labelled as found automatically. **Off until checked:** the notes show the
  links only with `recording_links` in `data/settings.json`, to be set once a few links from a real sitting have
  been opened by hand and land on the speaker. The time is right (checked 18 Nov 2026 against that day read from the
  recording: 19 morning turns land within 25 s of the speaker's first caption, most of them 7 s before it), but the
  YouTube video went private the evening of the same day, so the links wait for the archive's files (below).
- **A sitting day read afterwards from the recording** (18 Nov 2026, the maintainer's request): the live service read
  only the end of 17 Nov (it was started late, and the caption has a second layout, one line in the middle, that it
  does not read). The day was read again from the whole YouTube recording, a frame every 5 s, the name line of the
  caption matched to each speaker's own caption (the names read by eye), and kept as `data/<N>/snimak/<date>.json`
  (the shape of a live record, with `snimak` the second in the video and `uloga` the caption's list line; the
  chair has no caption and is not listed). The newest such day is listed on the site's `mikrofon` page and published
  as `mikrofon-dan.json`; between sittings the live service shows it in place of its own record of that day or an
  earlier one, and says it was read from the recording. Its own `/dan/<date>.json` (and so `data/<N>/uzivo/`) is
  unchanged. Reading a day this way is by hand for now; a script for it (the recording, the caption in both layouts,
  OCR) is the next step.
- **The live broadcast's YouTube video goes private** (18 Nov 2026: 17 Nov's, a day after). The broadcaster's archive
  (videonet.co.rs, `videos.json`) keeps the day as MP4 files, so a day read from the recording links each turn to its
  file and second (`datoteka`, `snimak`; a `#t=` fragment, which browsers follow for a video file). Where each file
  begins in the day was found by lining up a caption's first frame in the file and in the video. The live record's
  links (`video`, YouTube) will go private the same way: moving them to the archive's files is to do, and
  `recording_links` stays off until then.
- **The archive's files placed by their captions** (18 Nov 2026, the maintainer's request; `arhiva.py`, run by
  **votes** each hour): for every new file in `videos.json` of a day with a live record, ffmpeg reads a frame every
  30 s (over the network, only those bytes), the live page's own OCR reads the caption, and the start that puts the
  most names inside their speakers' turns is the file's (then to a few seconds where two names change); frames that
  fit a wide range of starts (one long speech) or disagree place nothing, tried again up to three times. Kept in
  `data/<N>/arhiva.json`. A day with no file in `snimak/` gets one written from the live record (`"izvor": "uzivo"`:
  turns in one frame left out, one speaker's turns within two minutes joined), written again while the record grows;
  a day read by hand only gets the places it lacks. The record's clock is the service's, some 15–20 s behind the
  broadcast, and turns and files share it; 17 and 18 Nov were lined up by hand on YouTube's clock
  (`"rucno": true`). Needs ffmpeg, Tesseract's Serbian, numpy and pytesseract on the runner.
- **Who spoke how long** (18 Nov 2026, the maintainer's request; `pages_govornici.py`): `govornici/<date>` per day in
  `snimak/` (each speaker's time and speeches, the time per list, the time between turns, quick exchanges, every
  turn with its place in the archive and "podeli", a picture of the day as the share picture) and `govornici.html`
  (the newest convocation's days summed). Ordered by time, ties by name. The time between turns counts stretches up
  to five minutes (mostly the chair, who has no caption); quick exchanges are two speakers taking turns three times
  or more, each within two minutes: by order only, the page claims nothing about what was said. Method:
  `kako-racunamo#govornici`.
- **An automatic transcript until the notes** (18 Nov 2026, the maintainer's request; `prepis.py`, the **prepis**
  workflow, by hand per day): each turn of 30 s or more cut out of the archive's file as sound and written down by
  Whisper (faster-whisper on the runner's CPU, `large-v3-turbo`, the one model since 20 Nov 2026; a run stops after `minutes` and the next goes on).
  Shown under the turn on the day's page, folded, as an automatic transcript that may err and is not a quote
  (principle 6 is about the notes, which the site quotes); not shown once the day's notes are read.
- **"Dok čekate"** (18 Nov 2026, the maintainer's request: "more fun", on both pages, "like the voting quiz"):
  between sittings the live page, and the site's `mikrofon` page, carry a quiz and the facts
  (`pages_mikrofon.quiz`, `facts`), published for the service as `mikrofon-cekanje.json` (so a change needs no rebuild
  of the image). Ten questions, one at a time as in the site's quiz (a strip of numbers, big answers, the answer and
  its source, on by itself after four seconds, a score to share at the end). They ask for what the site computes:
  urgent procedure, days to adoption, laws with no vote against, the most laws passed in one day, speeches, the chair's
  measures, harsh words (how many, the commonest and how often, the day with most), and one sentence said in the hall
  with its harsh word left out (`pages_floor.harsh_quote`, chosen by rule: the commonest word alone in a sentence of
  40–170 characters, the latest said; its answer links the speech). Wrong numbers are the right one times fixed
  factors picked by the question's key, unrounded like it (`SCALES`); words and days offered are the three with the
  most. About no MP in particular; a fact the quiz asks about is not listed beside it. Black and white only, not the
  colours of "za" and "protiv". The script and styles (`templates/mikrofon.js`, `.css`) are one file each, inline in
  both pages; the image copies them.
- **After a day of visits** (19 Nov 2026; 28,000 visits to the live page in a day, 86% on phones, 77% of them the
  Cyrillic page, one in nine going on to the site, most to the page of the MP then speaking, where a new MP's page
  was all but empty). **An MP's page, new or returning, lists the MP's turns on the floor in the newest
  convocation** from the days read from the recordings (`pages_govornici.per_speaker`, `macros.floor_now_part`: the
  sum, then each turn by day, linked to its place on the day's page with the recording and the automatic
  transcript), says "Sada je za govornicom" while the live service names them (`site.js`), and ends with the way on
  (`macros.next_steps`: who else spoke that day, the MPs' list, the quiz, the live page); a new MP's occupation is
  on the page. **"Ukratko" is always first on an MP's page and always open** (the maintainer's decision the same day:
  "sažetija i zabavnija"): a tile a number with a few words under it (`macros.brief`; `mp_card.facts` gives each fact
  its `short`, `sub` and `href`), the time on the floor in the newest convocation as the first tile, the whole
  sentences and how they are computed folded below; a new MP's tiles are year, occupation and place. Still no rating
  and the same tiles for everyone. The turns on the floor are a card of days with a pill a turn. **The live page's order** (changed the same evening at the maintainer's request) is a short head (what
  the page is in a line, and one button to the site), the newest notice alone, the broadcast, the name and clock,
  the box about the speaker, what is being said, the day's steps, the day. **While nobody is on** the summary also names the next sitting convened (`sazvano` in
  `mikrofon-cekanje.json`, as the Assembly lists it) and offers the day in cards. **An upright picture**
  (`/prica.png`, 1080×1920, `picture.render_tall`) for a phone's story. **The Cyrillic page is checked first** when
  anything is added (this time it showed "YоуТубе" and hours as "х": foreign names are written as said, "Jutjub").
  The clock's hourly run named the current convocation by number, so the newer one's MPs, occupations and recordings
  went unread for a day: `votes.yml` now reads the newer one whenever the current one is read.
- **Linked from the live bar** (17 Nov 2026, the maintainer's decision): while a plenary sitting is in progress the
  bar carries "Ko sada govori" beside the Assembly's broadcast, to `live_page` in `data/settings.json` (its `cir/`
  in the Cyrillic edition, through `data-cir-href`, which `cyrillic.page` follows). Accepted: the link leads to an
  error while the maintainer's computer is off.
- **Who spoke when, from what was said** (20 Nov 2026, the maintainer's decision: from the afternoon of 19 Nov the
  broadcast showed no speaker's caption, so reading the picture no longer works). `live/uzivo/zvuk_dana.py`, run in
  the live image on the maintainer's computer (which reaches the archive), writes each archive file of a day down
  word by word with its second (Whisper, `large-v3-turbo`, told the day's speakers' names; ten minutes of sound at a time, as a whole file does not fit in
  memory); `zailiprotiv govor <day> <folder>` (`govor.py`) finds each speech of the day's notes in those words by
  runs of four words found once in each, in the same order, and writes `snimak/<day>.json` with `"izvor": "govor"`:
  a speech lasts from its first word to its last, gets no place with fewer than two runs, and the name is the
  notes'. Nothing of the automatic words is shown or quoted. Each file's start on the clock is from `arhiva.json`,
  or from the live record's turns of the same speakers; a file with neither is reported and its turns are left out
  (its start is then set by hand in `arhiva.json`, `"rucno": true`, with how). Checked on 18 Nov against the turns
  read from the captions: a speech begins up to half a minute before its caption appears and ends with it. It waits
  for the day's notes, which the Assembly publishes a day or more later.
- **Faces and voices, only where there are no notes** (20 Nov 2026, the maintainer's decisions: faces and voices
  may be used, the recordings being public and MPs public officials; and they are the fallback). The sources of who
  spoke when, in this order: the caption while the broadcast shows it; the day's notes lined up with the sound
  (above), which once published replace whatever else the day had; and only for a day, or a part of one, with no
  notes yet, faces and voices (`live/uzivo/lice_glas.py` in `live/Dockerfile.analiza`, an image of its own on the
  tested one, never live: YuNet and SFace for faces, 3D-Speaker's ERes2Net through sherpa-onnx for voices; only the
  numbers are kept, no picture). `ko.py` matches a voice for every speaker by one rule: a stretch of sound is named
  when its windows are on average 0.68 alike the mean of a speaker's windows in turns known by caption or notes
  (`STRETCH_MIN`; checked on 18 Nov, each file left out of the samples in turn: every stretch so named was right).
  Faces do not name anyone by themselves: the camera often shows someone behind the speaker or listening (19 Nov:
  Vučević and Lalošević behind Brnabić), and the Assembly's portraits matched 4 of 49 turns. They group the close
  shots of the parts no voice named, and the maintainer labels the groups by hand (a private page of crops); a label
  becomes a voice sample only when the sound in that group's frames is one voice (0.65), and a chair (19 Nov:
  Radenović, then Macura during the vote, then Čupić) is a sample that is never listed. `zailiprotiv glas-dan <day>
  <stretches>` writes such a day (`"izvor": "glas"`): the captions' turns, the voices' where there were none, each
  part of the recording placed on the clock by captions read in passing (`govor.clock`; 19 Nov's afternoon by hand,
  three of Pastor's captions in three parts agreeing). It is incomplete, and says so: a speaker with no sample is not
  named. Written again from the notes when they come; the analysis's files stay on the maintainer's computer.
- **`large-v3-turbo` is the one Whisper model** (20 Nov 2026, the maintainer's decision): the live service, the
  **prepis** workflow and the recordings read afterwards; the second reading by a better model is gone with it.
- **A day's parts the archive's page does not list yet** (20 Nov 2026: `zas2026111910e.mp4`, the end of 19 Nov, was
  there hours before the page named it): `videos` tries the next letter after each of the latest three days' last
  file (a HEAD request) and keeps what is there, marked `"nenavedeno": true`.
- **The last sitting day's steps between sittings, and the Assembly's dates kept whole** (20 Nov 2026, the
  maintainer's report: the agenda was wrong and the day's steps were gone). The steps were kept per day, so after
  midnight the page had none; now, while it shows the last sitting day, it shows that day's steps under its date
  ("Šta se desilo, …"). 19 Nov's steps, kept on the computer the service ran on that day, were made again from the
  day's recording written down (`large-v3-turbo`) by the same rules, and from the Assembly's report of the sitting.
  `hronika._SENTENCE` no longer ends a sentence at a number followed by a small letter ("19. novembra", "24.
  novembra"): the Assembly's "Trećeg dana rada, 19. novembra …" had been cut at the date and dropped. Items 3 and 4
  of the first sitting were added to `data/15/tacke.json` from the Assembly's page, and the next day of work to
  `data/obavestenja.json`.
- **A day's record only grows** (20 Nov 2026: a restart of the live service served 19 Nov with no turn and three
  minutes seen, and the hourly run wrote it over the 28 turns kept). `uzivo.pull` never replaces a kept record with
  one that has fewer turns or less time seen (`uzivo.smaller`), and says so in the run's log; 19 Nov's was put back.
- **The model tells the day's steps and sums the day up** (20 Nov 2026, the maintainer's decision after a trial on
  19 Nov): Claude Haiku over the automatic transcript is the source of "Šta se desilo danas", the rules the fallback,
  and writes a summary at each break and of the day, labelled as a model's from an automatic transcript; how, in
  `live/AGENTS.md` ("The model tells the day's steps"). The key is in `live/.env` only.

## Open questions

- Interaction for readers beyond votes (questions to MPs, comments) needs a server or a third party, which
  principle 5 rules out as it stands: decide with the maintainer first.
- Amendments by MP; votes on amendments aren't among the published roll calls.
- Summaries of large laws cover the reasons and the first articles (the 8,000-character limit).
- Speakers who spoke mostly for the Government are left out of "what an MP says" by hand: a rule is needed first.
- The newsletter is the weeks' feed sent by a mailing service; `newsletter_url` in `settings.json` stays empty until
  the maintainer picks one.

## Decisions log

- **12 Nov 2026:** the project starts as "Za ili protiv" (`zailiprotiv`) in the organisation `javni-uvid`
  ("public inspection" of what institutions do). The source is the Assembly's own site; Otvoreni parlament's "API"
  is HTML behind a Cloudflare check and is not a source.
- **13 Nov 2026:** six convocations read (9th to 14th); the model's writing moved to Actions; the worker became the
  clock; the Cyrillic edition, Varnice, bills in procedure, weeks, group pages, visitors' votes.
- **14 Nov 2026:** every sitting's notes read; notes and downloads moved to buckets on subdomains.
- **16–17 Nov 2026:** search engines (Search Console, Bing, IndexNow, structured data); quizzes by theme; an MP's
  speeches; the Thirteenth's chair's measures attributed; GitHub hardened (security checks, pinned actions, least
  permissions); the cognee and sign-in trials removed.
- **17 Nov 2026:** namesakes in different convocations split into separate MPs (`mp_splits.json`), checked by
  year of birth (**mp-years**).
- **17 Nov 2026:** "Ko sada govori" (`live/`, `mikrofon.zailiprotiv.rs`): the current speaker read from the live
  broadcast's caption, every speaker by one rule, run at the maintainer's home behind a Cloudflare tunnel.
- **17 Nov 2026:** while "Ko sada govori" is down, `mikrofon.zailiprotiv.rs` shows the site's `mikrofon` page (a worker
  in front of the tunnel, `live/edge/`) instead of Cloudflare's error.
- **18 Nov 2026:** the Fifteenth's MPs listed before its first roll call (`members.json`, `poslanici-15.html`).
- **18 Nov 2026:** the archive's files placed by their captions (`arhiva.py`); who spoke how long per day and per
  convocation (`govornici`); an automatic transcript (Whisper) until the notes; the live page kept a few seconds at
  the edge and in the service after it stopped answering under the day's visits.
- **18 Nov 2026:** the first sitting day of the Fifteenth read afterwards from the whole recording
  (`data/15/snimak/2026-11-17.json`), shown on `mikrofon.zailiprotiv.rs` as the last sitting day; "Dok čekate" (a
  quiz and the facts) on both versions of that page.
