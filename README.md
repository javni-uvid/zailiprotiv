# Za ili Protiv

A public site about the laws Serbia's National Assembly passes: what each law does, what its proposer says it will
change, and how every MP voted on it.

**Site:** https://zailiprotiv.rs

**Status:** live. Six convocations (9th to 14th, 2012 to now): about 2,100 laws, each with its final roll call by
group and by MP; about 1,000 MPs; the stenographic notes of every sitting since 2012, word for word, each speech
with its own address and searchable; bills in procedure; and visitors' own votes ("Glasaj i ti"). What an AI model
wrote (summaries of memoranda and debates, overviews of what an MP says) is labelled as such, with the model's
name. Every page is also in Cyrillic, under `cir/`.

## Principles

1. **The same rules for every MP, group and party.** Nothing is computed differently for anyone.
2. **Primary sources only:** the Assembly's own roll calls, bills and stenographic notes, and laws as published.
   For the laws with most votes against, opinions of independent bodies and analyses by media and civil society
   appear as labelled notes with their source, never as a figure, a vote or a ranking.
3. **A law's effects are its proposer's,** summarised from the bill's memorandum, with a link. The site doesn't
   judge laws.
4. **MPs are public officials:** their names and votes are shown. Nothing about their private lives.
5. **Nothing from third parties on the pages:** no cookies, fonts or scripts from other servers. The exceptions:
   visits counted by Cloudflare Web Analytics (no cookies, totals only), and visitors' votes sent to the project's
   own counter; a copy opened anywhere but on the project's own hosts sends neither.
6. **What MPs say is not censored and not shaped:** quotes word for word, every name as spoken, and no label or
   verdict of the site's own.

`AGENTS.md` holds the principles in full and the rules of work; the decisions with their dates are in
`docs/decisions/` by part; `live/AGENTS.md` says in short what holds for the live page.

## Pages

- **Zakoni:** laws by convocation, kind and area; bills in procedure and convened sittings. A law's page: the final
  vote by group and MP, the summary of the memorandum, the debate with verbatim quotes, the sparks in it, outside
  views, downloads, and the visitor's own vote.
- **Oblasti:** a page for each of the 17 areas of Article 97, with "Prati mejlom": a mail the morning after a bill of the
  area entered procedure, came on a sitting's agenda or was passed (`oblasti.py`, `prati-oblasti.json`,
  `oblasti-dogadjaji.json`; the counter and the live service's sender take it in their own steps).
- **A new convocation's MPs** before its first roll call: `poslanici-<N>.html`, from the Assembly's list (party, place, year of birth; who was an MP before), a page for each new one.
- **Poslanici:** a page per MP, opening with a card of facts by one rule for all (presence, votes unlike the group,
  hours spoken, the longest speech, exchange partners, the most alike group), then key votes, votes against the
  group, activity on the floor, what they say and every speech linked to its notes; every vote on a page of its own;
  a page per parliamentary group; presence ranked by one rule for all. **Funkcije u Skupštini** on every MP's page:
  Speaker, deputy Speaker, a group's chair, each committee and delegation with the role, as the Assembly's pages of
  its composition list them (`zailiprotiv offices`, beside the Assembly's news kept in `data/vesti.json`). The live page
  shows the speaker's under their portrait ("O govorniku").
- **Varnice:** from the notes, by rule, with no model: the chair's measures, exchanges of replies, harsh words, who
  speaks most; per convocation and over all of them.
- **Skupština:** weeks, sittings, convocations, the Assembly in numbers.
- **Podrži:** readers' support by bank transfer, NBS IPS QR codes drawn in the page (`podrzi.html`, `settings.json` `support`).
- **Poslovnik:** the Assembly's Rules of Procedure, article by article, every version kept (`data/poslovnik/`), for the
  articles invoked in the debates, the terms the site explains and the order of a sitting's steps.
  The page `poslovnik-clanovi` explains the site's terms from it (`data/poslovnik/pojmovi.json`: replika, the chair's
  measures, hitni postupak, načelni pretres, amandman, Dan za glasanje…, each with the articles' text; an index
  of them, a search over terms and articles; its link shows the Rules as an open book, `rules_card.py`), and the
  pages where a term appears link there.
- **Ko koliko govori:** per sitting day read from the recording (`govornici/<date>`), each speaker's time and the
  time per list, the time between turns, quick exchanges, every speech with its place in the Assembly's archive, a
  link to share it (opened, it starts the recording there where the browser lets it) and, until the notes, an automatic transcript; the convocation's days summed (`govornici.html`). While the
  recording plays, a card under it says who spoke at that place ("Na snimku"), as on the live page. The speeches
  are drawn as the live page draws them (its cards, its styles). On top, the day's summary as the day's mail tells it
  ("Sažetak dana", labelled, from the same file): its title and paragraph open, "Dan u Skupštini, po satu" (steps and
  decisions, each time a link to the recording) and "Govorili su" (by list, with portraits) folded, and under it the
  mail's offer. A chair's measure is never drawn as a decision. A day the live service never heard is summed up from the
  notes, and a day again from its kept transcript, by `tools/sazetak_dana.py` (the service's own call and checks). A day whose broadcast shows no speaker's caption is read from what was said: the notes lined up with the
  recording written down word by word (`zailiprotiv govor <day> <folder>`, the words from `live/uzivo/zvuk_dana.py`). How right the live record of who spoke when was on such a day: `zailiprotiv tacnost [day]`. Until the notes, a day can be read from its recording (`zailiprotiv glas-dan <day> <folder> --uzorci <folders of other days>`, with numpy): the sound cut where the voice changes, each piece named by the caption, the chair's words or a known voice.
- **Glasaj i ti:** the visitor's ballot ("Moj listić", kept in the browser) beside the Assembly's results and the
  MPs and groups that voted the same; a quiz on the laws that divided the chamber and one per area; the newest bills
  to vote on before the Assembly does.
- **Javni uvid** on every page: the family's bar at the top (its page and its other sites) and its block in the
  footer, in the family's look (`osnova/design/`, `family.py`).
- **The live page on every page**: "Uživo" in the menu (red while a sitting is on), a strip on the home page with
  who speaks now, the next sitting's day and hour (one convened, or one begun going on, as the Assembly's page of it says) or the last day with its recording, and an announcement on the
  other pages from the day before a sitting until it starts.
- **On a phone** the menu is a bar at the bottom (Zakoni, Poslanici, Uživo, Glasaj, Još), always there: a row of
  icons while a page is read down, with its words again at the first move up.
- **Sections** (Zakoni, Poslanici, Skupština): their pages share a heading and a switch between them, and the
  section is marked in the top bar and in the phone's bar on each of its pages.
- **Search** over the site and every speech; **feeds** (new laws, bills, per area, per MP, weeks); **downloads**
  (CSV, JSON) under CC BY 4.0; **method** ("Kako računamo"): how every figure is made.

## Where things are served from

| Address | What | From |
|---|---|---|
| zailiprotiv.rs | the site's pages and search; a sitting MP's page offers a mail when the MP speaks in the hall | GitHub Pages, behind Cloudflare |
| beleske.zailiprotiv.rs | the notes' pages and their search index; the notes as read (`sirovo/`) | R2 bucket `zailiprotiv-beleske` |
| podaci.zailiprotiv.rs | every law's CSV, JSON and picture, MPs' pictures, `podaci/` | R2 bucket `zailiprotiv-podaci` |
| glasovi.zailiprotiv.rs | the visitors' votes counter, and the project's clock | Cloudflare Worker with D1 (`worker/`) |
| mikrofon.zailiprotiv.rs | who is speaking now, read from the live broadcast's caption, with the speaker's day so far, that a break is on (by the chair's words and the broadcast's graphic) and in it a paragraph of what happened until it (the model's, labelled), under each speech its topic when it ends (the model's, checked, labelled), lines about the MP from the site (`mikrofon-poslanici.json`), the day in one sentence, in numbers and in cards, a picture of the moment (`/slika.png`, the link preview too), the broadcast itself and an automatic transcript of what is said (Whisper on the same computer, `/prepis`), and while an item is debated an estimate of each group's time left by the Rules (art. 97); between sittings when the Assembly sits next, from its own listing (one convened with its agenda, in every form its pages have used, or one begun that goes on; a sitting newly listed also opens an issue for the maintainer), the last sitting day (read afterwards from the whole recording when the site has it, `mikrofon-dan.json`) and "Da li ste znali", facts from the site's counts (`mikrofon-cekanje.json`); the day's summary by mail to who signs up, offered under the player in a break, when the day is over and at a shared speech, after each sitting day (the maintainer first, all on his click; a correction on top when an earlier mail said something false about a person; `live/uzivo/pretplata.py`, `worker/mejl.js`, the privacy page `privatnost`); while it is down, the same page drawn by the site's build from its last day (`mikrofon.html`) | Docker on the maintainer's computer, Cloudflare tunnel (`live/`); a worker in front (`live/edge/`) |

Secrets live in GitHub Secrets and Cloudflare, never in the repository; `data/settings.json` holds the public
addresses.

## Commands

```sh
uv sync
# Every command works on the current convocation (data/14/); `--convocation 13` before the command for another.
uv run zailiprotiv status              # what the data still lacks, per convocation; batches running or refused
uv run zailiprotiv index               # the convocation's sittings and their roll calls → index.json
uv run zailiprotiv laws                # the laws it passed → laws.json
uv run zailiprotiv procedure           # bills in procedure now → procedure.json (the newest convocation's)
uv run zailiprotiv votes               # every roll call not read yet → votes/ (needs pdftotext)
uv run zailiprotiv unread              # the roll calls listed and not read, if any
uv run zailiprotiv offices --unread    # the committees and delegations whose members were not all read
uv run zailiprotiv bills               # each bill's memorandum → bills/ (scans by OCR: tesseract, srp)
uv run zailiprotiv link                # each law's kind, area, roll calls and final vote
uv run zailiprotiv transcripts         # the stenographic notes → transcripts/
uv run zailiprotiv uzivo-pull          # who spoke when, from the live page's day records → data/<N>/uzivo/
uv run zailiprotiv arhiva              # the archive's recordings placed by their captions → arhiva.json, snimak/ (ffmpeg, OCR)
uv run --with faster-whisper zailiprotiv prepis 2026-11-18   # an automatic transcript of a day's speeches → prepis/
uv run zailiprotiv summaries --batch   # the model's summaries of the memoranda (Batch API)
uv run zailiprotiv debates-batch       # the model's summaries of the debates
uv run zailiprotiv profiles-batch      # the model's overviews of what an MP says → data/profiles/
uv run zailiprotiv site --out _site    # build the site (fails on a page over 1 MB or anything loaded from elsewhere)
uv run zailiprotiv notes-site --out _beleske   # the notes as pages of their own
uv run pytest -q
```

A development environment may not reach parlament.gov.rs; GitHub's runners can. Everything that reads the
Assembly's site runs through the workflows.

## Workflows

What a workflow read or wrote is committed with `tools/predaj.sh`, which ends red when the commit is not on `main`.

| Workflow | When | What |
|---|---|---|
| votes | hourly by day (started by the worker), and by hand | sittings, laws, bills in procedure, roll calls and bills not read yet, links, committed first (an issue when a roll call listed is not read); commits `data/<N>/`; `data/live.json` while the live page reads a sitting (the bar "Skupština sada zaseda" when the Assembly marks none "(у току)") |
| snimci | after votes when there is something to do, and by hand | the archive's new recordings placed on the clock and each day's speeches linked into them (`arhiva.json`, `snimak/`); asks the broadcaster's archive only |
| transcripts | after votes, and by hand | the stenographic notes; the raw notes go to the bucket |
| summaries | after transcripts, every six hours, and by hand | the model's writing through the Batch API; the cheapest model first, a stronger one only by hand |
| pages | on push, and after each data run | build the site and its search index, send downloads to the bucket, publish, purge the cache, tell search engines what changed (about seven minutes); a push that changes only `static/` puts it into the site published last instead (`static-patch`, about two) |
| prepis | by hand, per sitting day | an automatic transcript of the day's speeches from the archive's recording (Whisper); stops after a set time, the next run goes on |
| notes | after transcripts, and by hand | the notes' pages and their search index; send what changed to the bucket |
| worker | on push to `worker/` | deploy the votes counter and its schema |
| health | hourly | ask the site, the buckets and the counter from outside; an issue when one does not answer |
| watch | four times a day | do visitors' votes look inflated? An issue when one network sends most of a law's votes |
| test | on push | the whole test suite |
| security | on code or workflow changes, Mondays, by hand | zizmor (the workflows), pip-audit (the packages), CodeQL (the code) |
| visits | by hand | Cloudflare's counts; the live page's uses by hour, from our counter; with options, what Cloudflare stopped, Google Search's numbers and which kinds of page Google indexed |
| peek, dns-check | by hand | a page's text as seen from outside; DNS and the buckets |
| files, trial, probe, sample, fixtures | by hand | the downloads' bucket; a build with all notes; inside scanned bill PDFs; another model's writing; test fixtures |

Dependabot proposes updates to the actions and the Python packages once a month.

## Layout

```
src/zailiprotiv/
  config.py, skupstina.py     the Assembly's site: convocations, sittings, the roll call of each agenda item
  rollcall.py, laws.py        reading a roll-call PDF; the adopted laws
  bills.py, procedure.py      a bill's memorandum (OCR for scans); bills in procedure
  kinds.py, link.py, mps.py   an act's kind and area; which roll calls were on which law; who an MP is
  transcripts.py, debates.py  the stenographic notes; what was said about a law
  summaries.py, profiles.py, batch.py, federated.py   the model's writing: prompts, checks, the Batch API
  site.py, pages_*.py         the static site, with templates/ and static/
  pages_floor.py              "Varnice", by rule from the notes
  measures.py                 the chair's measures in the notes, by rule, and to whom each went
  pages_ballot.py, pages_quiz.py   "Glasaj i ti": the ballot and the quizzes
  notes_site.py, files_site.py     the notes' pages and the downloads, for the buckets
  cyrillic.py, translit.py    the Cyrillic edition; Cyrillic → Latin
  family.py                   Javni uvid's look and links from osnova/design/: the stylesheet served, the bar, the footer block
  digest.py, feeds.py, downloads.py, card.py, photos.py, publish.py
  cli/                        commands, by what they work on: assembly, recordings, writing, buckets, build
tools/                        reports run by the workflows: visits, blocked, search; indexnow (sitemap dates);
                              pretplate: subscribers counted by sitting day, run by hand
worker/                       the visitors' votes counter (Cloudflare Worker, D1)
live/                         "Ko sada govori": the live broadcast's caption read, a page of its own (Docker; README there)
data/<N>/                     one folder per convocation (9 to 15)
  index.json, laws.json, procedure.json, short_titles.json; links.json, wrong_bills.json where needed
  votes/, bills/, summaries/, debates/, transcripts/, notes/; uzivo/ (who spoke when, from the live page, by day)
data/profiles/, data/photos/  MPs' overviews and portraits
data/quiz.json, aliases.json, mp_aliases.json, settings.json, batches.json, notes_manifest.json
data/mp_splits.json, mp_years.json  one name, two people (by hand); years of birth from the Assembly's archive
data/mp_moved.json            MPs' earlier page addresses, sent on to their pages
tests/
```

## License

Code: MIT (`LICENSE`). Data the site publishes (pages and downloads): CC BY 4.0, naming the source as
„Za ili Protiv (zailiprotiv.rs), prema podacima Narodne skupštine".
