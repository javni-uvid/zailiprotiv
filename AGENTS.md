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
    `~/orca/workspaces/zailiprotiv/`. Short-lived: hours, a day at most. A new worktree needs `uv sync` (and on
    Windows `uv pip install tzdata`).
  - **Before starting, `gh pr list`:** when an open pull request touches the same files, build on it or wait
    (19 Nov 2026: two agents added the same setting to the live service in one evening).
  - **Before pushing,** `git rebase origin/main` and `uv run pytest -q`; then `gh pr create` (the template asks what,
    why, what was checked, and whether the maintainer must decide); `gh pr checks --watch` until **test** passes on
    it, then `gh pr merge --squash`: one commit on `main`, the branch deleted. A pull request that needs the
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
  - Dependabot's monthly pull requests: merge them once their checks pass.
- **Run `uv run pytest -q` before every push.** The **test** workflow runs it again on every pull request and on
  `main`; a red run is fixed first.
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

### Visitors' votes ("Glasaj i ti")

- **The counter** (`worker/`, a Cloudflare Worker with D1; README there): a vote is one device's vote on one law or
  bill (`POST /z`), replacing its last; quotes can be marked convincing (`POST /c`); the quiz sends its laws at once.
  Kept: the vote, a hash of a random mark the browser made (with the secret `SALT`), the day, a daily hash of the
  network. No cookies, no addresses. Only items the site lists (`glasanje.json`). No robot check: **watch** opens an
  issue when one network sends most of a law's votes; removing is the maintainer's decision, written on the method
  page. **Uses** (17 Nov 2026, `POST /e`): a sum per day of the quiz's result reached and the share pictures opened,
  shared, copied, saved; nothing beside it. `GET /pregled` shows both. **The live page's uses** (19 Nov 2026,
  the maintainer's request, to see how long people stay and what keeps them): the same sums from
  `mikrofon.zailiprotiv.rs` beside the broadcast's ▶ (`mikrofon.pusti`, below): opened; in view 1, 5, 15, 30 min,
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

## Broadcasts and recordings

The Assembly broadcasts its sittings live and keeps the recordings with its broadcaster (videonet.co.rs), linked
from its page "Prenosi". Since 17 Nov 2026: while the newest convocation's listing marks a plenary sitting
"(у току)", the home page and "Sednice" carry a bar linking to the live broadcast (`config.LIVE`) and to "Ko sada
govori" (`live_page`, see below); each sitting's page lists the recordings of its days (`videos.py`,
`data/<N>/videos.json`, read by **votes** for the current and the newest convocation; earlier ones by hand). Both
are links: the site plays nothing itself (principle 5). The notes carry no times, so a speech cannot be linked to
its minute.

### Who is speaking now (`live/`)

- **A page of its own at `mikrofon.zailiprotiv.rs`** (17 Nov 2026): who is speaking in the Assembly now, and who spoke
  today, read from the caption under the speaker in the live broadcast (README in `live/`). It grew out of the
  maintainer's page following one speaker; under the project it follows **every speaker by one rule** (principle
  1): nobody is followed, singled out or ranked; today's turns are listed by time.
- **Not static, so not on GitHub Pages:** a service watches the broadcast. It runs in Docker on the maintainer's
  computer behind a Cloudflare tunnel, because YouTube often refuses data centres' addresses (GitHub's runners
  among them) and a home address works. When the computer is off the page is down; **health** does not ask it.
  The tunnel's token lives in `live/.tunnel.env` (never committed) and in Cloudflare.
- **Test first, then live** (19 Nov 2026, the maintainer's decision): two images. `live/mikrofon.ps1 test` builds
  the working tree as `mikrofon:test` and runs it at `127.0.0.1:8001` (`docker-compose.test.yml`: no tunnel, no
  visits counted, its own data); only after the maintainer has looked at it does `mikrofon.ps1 uzivo` tag that same
  image `mikrofon:uzivo` and run it with the tunnel (`docker-compose.yml`, which never builds); the image it
  replaces stays as `mikrofon:prethodni` (`nazad`). A change to `live/` is never put live without the test.
- **While it is down** (17 Nov 2026): a worker in front of the hostname (`live/edge/`, a route on the zone, published
  by the `worker` workflow) passes every request to the tunnel; on a 5xx (530 when the tunnel is down) it shows the
  site's `mikrofon` page (`pages_mikrofon.py`, noindex) under a `<base>` pointing to zailiprotiv.rs, and the live
  JSON answers `{"radi": false}`. The page says why it is off, links the broadcast and the next sitting, and lists a
  few facts from the site's own counts (laws, urgent procedure, days to adoption, the harsh word said most often),
  each linked to the page with its rule, about no MP in particular.
- **Read from the broadcast, matched to the roll calls:** a name counts when it matches an MP on the site's list
  (`podaci.json`, from the roll calls) on the caption's name line only, never the list line under it (a list's name
  often holds its leader's name). A name not on the list (ministers, guests) is shown only when read surely in two
  frames in a row; a half-read name is never shown. The page says it is read automatically and may err.
- **Visits counted as on the site** (18 Nov 2026, the maintainer's decision, once the page became the site's main way
  in): the live page carries the site's Cloudflare Web Analytics beacon (principle 5's first exception), its token
  read from `data/settings.json` copied into the image (`config.ANALYTICS_TOKEN`; `ANALYTICS_TOKEN=` empty turns it
  off); the footer says so. Until then only the site's page shown while the service is down was counted.
- **Nothing from elsewhere** (principle 5): the fonts are copied from `src/zailiprotiv/static/fonts` into the image,
  the one script is inline; the site's MP pages are linked.
- **Its tests** (`tests/test_live.py`) cover the names, the caption's lines, the turns and the page, with the
  standard library only; OCR and the stream are tried against the broadcast.
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
- **What is being said, the day in numbers and cards, the broadcast on the page** (19 Nov 2026, the maintainer's
  choices after a look at skupstina.live; its chat, muting and model-written summaries were left out).
  **Automatic transcript** (`live/uzivo/prepis.py`): each segment read for its frame leaves its sound (16 kHz), a
  thread gives the sound to the turn it falls in and has Whisper (faster-whisper on the maintainer's CPU,
  `WHISPER_MODEL`, `large-v3-turbo`, the one model since 20 Nov 2026, empty for off; the model is kept in `/data/hf`) write it down about a minute
  at a time while the speaker is on, the rest when the turn ends; turns under 20 s and sound in no turn (the chair)
  are thrown away unread. The text is kept per day (`/data/prepis/<day>.json`, `Tracker.say`), shown with the speaker
  as its last 400 characters and whole at `/prepis` (and `/cir/prepis`), always labelled automatic, may err, **not a
  quote**; nothing is summed up or reworded by a model (principle 6 stays: the site quotes the notes). The page's
  changing part carries only the tail and word counts, so it stays small. **Four numbers** of the day above the
  bars (time, turns, speakers, words written down). **"Dan u karticama"**: the day in cards to tap through, each by
  a rule (whole time, most time, time by list, longest turn, most turns from three on, the way to the site).
  **The broadcast is on the page while a sitting is on**, YouTube's player in its no-cookie mode, playing when
  pressed. Since the evening of 19 Nov 2026 (the maintainer's decision, point 4 of the analysis of how long visits
  last: 86% of them on phones, and no way to see whether anyone plays it) it is behind a **facade**: our own picture
  of the moment (`/slika.png`) with "▶ Gledaj prenos", and only the press loads YouTube's player, playing, so
  principle 5's "only on a click" holds again on this page. The press adds one to the counter's sum of the day
  (`mikrofon.pusti`, `POST /e`; the counter takes uses from `mikrofon.zailiprotiv.rs` too, only `mikrofon.` ones;
  the service reads `votes_api` from `data/settings.json`, `VOTES_API=` empty turns it off). The archive's
  recordings load on a click as before. **The site's live bar names the speaker** and since when (`site.js` reads the service's
  `stanje.js` every half a minute while the bar is on the page).
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
- **A name with nothing under it** (19 Nov 2026): the live page listed two turns of an MP who had not spoken, each
  read in two frames with no second line. `state.counted`: a turn goes into the day's list when read in two frames
  or more and either the line under the name (the list or office, which every real caption has) was read at least
  once, or it lasted four frames or more; the day's record gives a turn not counted as one frame, which the site
  drops. The same rule for every name.
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
- **A notice on top of the live page** (19 Nov 2026, the maintainer's request: the Speaker's election). What the
  Assembly has decided is written by hand into `data/obavestenja.json` (a sentence of fact as the Assembly's site
  says it, its source's address, the days it stands, the MP's page), published in `mikrofon-cekanje.json` and shown
  above the speaker from "od" until "do"; the service reads it with the hour's fetch, so a new notice needs no
  rebuild. No comment and nothing the source does not say.
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
- **Chance readings during a break** (19 Nov 2026: one MP's name kept flashing as the speaker while nobody was on
  the screen). Two causes, both mended. In `names.Roster` one word read could stand for two words of a name
  ("Сара" was both "Sarag" and "Sarah"): each word of the name now needs a word of its own (`_pair`). And in
  `Tracker.observe` a name with no line read under it, like a name not on the list, is taken only on its second
  frame in a row (within `HOLD_SECONDS`), the turn then counted from the first of the two; a whole caption, with its
  list or office, is taken at once as before.
- **Corrections to the automatic transcript: first out, then corrected** (19 Nov 2026, the maintainer's decision).
  Before a piece Whisper is told the Assembly's set terms and today's speakers' names (`prepis.Writer.hint_for`, as
  the model's `initial_prompt`). The text is kept as written; what is shown is that text with the corrections
  (`live/uzivo/ispravke.py`, applied when shown, so a new correction mends what is already out): the site's list
  `data/prepis-ispravke.json` (as Whisper writes it → as it is written, whole words; published as `ispravke`), and a
  sitting MP's name written without its diacritics, in any case, gets them. Only spellings: nothing is reworded, no
  model rewrites it, and a word a letter away from a name is left for the list. Each speech on `/prepis` has
  "Prijavi grešku u prepisu" (a letter to the site's address, filled in with the speaker and the time); what the
  maintainer accepts goes into the list. A finished turn can be read again by a better model and shown in place of
  the first reading, marked as such (`WHISPER_FINAL_MODEL`, off by default: it runs only while the first reading
  has nothing to do, and still keeps the computer busy long after a sitting). When the Assembly's notes of the day
  come, they are what the site quotes; the transcript stays with the recording as what it is.
- **The chair's words are shown too, as no one's by name** (19 Nov 2026, the maintainer's remark that the transcript
  stops while the chair speaks). Sound in no turn is written down in shorter pieces (`CHAIR_PIECE`, after
  `CHAIR_WAIT`), kept apart in the day's record (keys `p<second>`), shown under "Bez potpisa: predsedavajući ili
  sala" while nobody's caption is on (snapshot `bez_potpisa`) and on `/prepis` in its place in time. It is never put
  to an MP, never counted in anyone's time, and the day's steps are still read from it.
- **The transcript is written down but not shown** (19 Nov 2026, the maintainer's decision: it errs too much and
  does more harm than good). `PREPIS_PRIKAZ=1` shows it again (`config.SHOW_TRANSCRIPT`); off, the page has no
  "Šta govori", no "Bez potpisa", no words tile, no links to `/prepis`, and `/prepis` leads back to the page. The
  writing goes on: the day's steps and the agenda's progress are read from it.
  With it off, `/prepis?k=<PREPIS_KLJUC>` still shows it to whoever has the key from `live/.env` (the maintainer,
  to see what is being written down): at least 12 characters, answered with no-store and no referrer; without the
  key the address leads back to the page.
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
- **The speakers' sound is written down too, and a heard step is shown only when something else bears it out**
  (19 Nov 2026, the maintainer's decision). For a few hours only the chair's sound was written down, so that a
  slower model (`WHISPER_MODEL=large-v3-turbo`, about real time on the maintainer's computer) kept up; the same
  evening the maintainer asked for the MPs' speeches to be kept as well. Now everything is written down and kept
  (off the page, as above), the chair's sound first (`prepis.choose`), so the day's steps keep up while the
  speakers' waits; the computer may fall behind during a sitting and catch up after. `PREPIS_SAMO_PREDSEDAVAJUCI=1`
  (`config.CHAIR_ONLY`) writes only the chair's again, with the second reading off. `page.steps_shown` shows a step
  from the chair's words only when confirmed: an agenda item the agenda has, with a higher number than the last
  heard; a break or the day's end when nobody is at the rostrum for `STEP_QUIET` after it; work resumed after a
  shown break, before anyone spoke, or (once) after ten minutes with nobody at the rostrum (`STEP_IDLE`: a break
  need not have been heard); a vote or a debate's opening or closing while an agenda item is under way. A kept
  step is checked against today's rules again when shown, so a mended rule also clears what it had found.
  Measures and anything else wait for the Assembly's page. Next, once a day of this has been looked at: a model
  over an API as a judge of the chair's words (a step's kind from the set list, the item's number, till when the
  break is), never as the writer of what the page says.
- **"Reč ima: …" from the chair's words, while the picture names nobody** (19 Nov 2026: that afternoon the
  broadcast showed no captions at all, the frame checked). `hronika.floor`: after "reč ima" / "ima reč" the next
  seven words must name one sitting MP: every word of the name whole but for diacritics, or, as a guess the
  maintainer allowed after that phrase, the clearly nearest MP by every word of the name (`FLOOR_NEAR`,
  `FLOOR_CLEAR`; "Jova Bakič", "Krko Babić"), or a surname alone that only one MP has, right after a title
  ("kolega Jovanov") and never after a given name we do not know. Two MPs fitting: nobody. Shown in the day's steps as a lighter line with a link to the MP's page, and not where a turn read from
  the picture stands. No time at the rostrum is counted from it (the end of the speech is not known), and nobody
  is ever named from a face.
- **Trying another Whisper model** without touching the service: `python -m uzivo.proba <model> [seconds]` in the
  container (`live/uzivo/proba.py`) listens to the kept sound, writes it down with the running model and the named
  one, and prints the time and the text of each. It shares the processor with the service while it runs.
- **Linked from the live bar** (17 Nov 2026, the maintainer's decision): while a plenary sitting is in progress the
  bar carries "Ko sada govori" beside the Assembly's broadcast, to `live_page` in `data/settings.json` (its `cir/`
  in the Cyrillic edition, through `data-cir-href`, which `cyrillic.page` follows). Accepted: the link leads to an
  error while the maintainer's computer is off.
- **The live page for a keyboard and a screen reader** (20 Nov 2026, after the same look the site had). The page's
  part is replaced whole every five seconds, which took the keyboard's place away each time: the thing that had
  the focus (the same kind, the same one in order) has it again after the replacement. A line outside that part
  (`#ko`, `aria-live`, not shown) says the new speaker's name and list once when they change. "Dan u karticama"
  opens onto its close button, gives the focus back, and does not turn its cards by the clock for a reader who
  asked for less motion. No letters under 12 px; the "next line" button is 32 px high. The archive is named
  "Videonet", not by its address, which the Cyrillic page wrote in Cyrillic letters.
- **The agent tests and puts live itself** (20 Nov 2026, the maintainer's decision; it changes "Test first, then
  live" above, where the maintainer's own look came between the two). The agent that changed `live/` runs
  `mikrofon.ps1 test`, looks at the test page itself (a phone's width, both scripts, what the change was about),
  and after the merge builds the test from the main clone on a clean `origin/main`, looks again and runs
  `mikrofon.ps1 uzivo`; it checks first that nothing but its own change lies between the live image's commit and
  `main` (`mikrofon.ps1 stanje`, `git log <commit>..origin/main -- live/`), and afterwards that the public page
  answers with the change. The maintainer is not asked to run the Docker steps by hand. A principle, DNS or
  anything seen from outside beyond the page itself still waits for the maintainer.
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
- **A notification when a sitting begins** (20 Nov 2026, the maintainer's choice: only the broadcast's beginning,
  the addresses kept by the counter). "Obavesti me kad sednica počne" under the speaker's box asks the browser,
  registers the page's service worker (`/sw.js`, `page.service_worker`: it shows the notification and opens the
  page, and handles no requests) and sends the browser's push address to the counter (`POST /p`, from
  `mikrofon.` only, the table `push`; "Isključi" sends `/p/odjava`). The live service (`obavesti.Bell`), after three
  frames of a live broadcast in a row between 7 and 22 h, asks the counter once a day to send (`POST /p/salji` with
  the token `PUSH_TOKEN`, in `live/.env` and GitHub Secrets; the test's is empty); the counter keeps the day
  (`push_days`), sends a push with no content signed with the VAPID key (secret `VAPID_JWK`, its public half
  `push_key` in `data/settings.json`) to 30 addresses a call, its free plan's limit, forgets addresses the push
  service says are gone, and the service asks for the next 30 until none is left. On an iPhone it works once the
  page is on the home screen, which the page says. `GET /pregled` gives the number of addresses and what each day
  sent; `mikrofon.obavesti` and `odjavi` are counted as uses.
- **A new image put live without a break** (20 Nov 2026, the maintainer's choice of three layers; a blue/green pair
  of services was left out: two would read the same broadcast and write the same files). The restart takes some
  5 s, and finding the stream again 15-30 s more. (1) The edge worker keeps the shared answers on its routes (`/`,
  `/cir/`, `stanje.json`) a second time for two minutes and gives them, marked `x-mikrofon: poslednje`, while the
  service answers 5xx; the site's page for a service that is off only after that. The part an open page asks for
  (`/deo`) is not on the worker's routes (the free plan's requests) and gets Cloudflare's 502 for those seconds,
  which the page's script answers by keeping what it shows; an address with a query (`?fbclid=…`) matches no
  route either and goes straight to the tunnel (checked 20 Nov 2026 by stopping the service at night). (2) The service writes with every
  frame whether a broadcast is on and who is speaking (`state._save`); a new run within `RESUME_SECONDS` (90) of the
  last frame takes that up (`Tracker._resume`), counting the waits for a frame from the restart, so the page does
  not say "no sitting" while the stream is found again, and the same speaker read again is the same turn.
  (3) `mikrofon.ps1 uzivo` waits for the turn on to end (`-Cekaj`, 10 minutes at most; `-Odmah` at once).
- **What goes live is known** (20 Nov 2026, the maintainer's choice; the night before, other agents' worktrees had
  built `mikrofon:test` too, so `uzivo` would have put live whatever was built last). `mikrofon.ps1` passes the
  commit, branch and whether the tree was clean to the build (labels `zailiprotiv.*`, `VERZIJA` in the image:
  `/stanje.json` and the footer show it). A worktree's test is `mikrofon:test-<branch>` on a port and volume of its
  own; `uzivo` runs from the main clone on `main` and takes only an image of a clean `origin/main` (`-Ipak`
  overrides), waits until the new one answers with its commit and puts the one before back if it doesn't in 90 s.
  A Docker healthcheck, `logovi`, `ocisti`, `.env` taken from the main clone, and `mikrofon-whisper` as an external
  volume.
- **The maintainer is told when the live page is down during a sitting** (20 Nov 2026, the maintainer's choice of a
  phone notification over an issue). The counter's cron, every five minutes on weekdays 6-19 UTC (`watch`), asks
  the service for `stanje.json` (the edge's copy, `x-mikrofon`, doesn't count as an answer); only when it doesn't
  answer does it read the Assembly's two listings for a sitting marked "(у току)" (at most once in 30 minutes:
  ask the Assembly little). Down in two checks in a row while one is on, the maintainer's devices (table
  `push_admin`) get one notification, and one more when it answers again. A device is put on that list from
  `mikrofon.zailiprotiv.rs/upozorenja?k=<PREPIS_KLJUC>`, which hands its push address to the service, and the
  service to the counter with its token (`/p/admin`). A push carries nothing, so the service worker asks the
  counter which it was (`/p/vrsta`, by its own push address): the watch's for the maintainer's devices, the
  sitting's for everyone else. The Assembly marks a sitting of several days "in progress" on its days off too, so
  a computer turned off on such a day is told about as well.
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
- **The chair gives the floor in more words than "reč ima"** (20 Nov 2026, the maintainer's request): Whisper writes
  it as one word ("Rečima narodna poslanica …"), and the chair also says "dajem reč", "pravo na repliku ima", or a
  title after "replika", "povreda Poslovnika", "izvolite", "sledeći je" (`hronika._FLOOR`); "replika gospodinu X"
  names whom it answers and is not taken.
- **A day's parts the archive's page does not list yet** (20 Nov 2026: `zas2026111910e.mp4`, the end of 19 Nov, was
  there hours before the page named it): `videos` tries the next letter after each of the latest three days' last
  file (a HEAD request) and keeps what is there, marked `"nenavedeno": true`.

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
