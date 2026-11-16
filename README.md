# Za ili protiv

A public site about the laws Serbia's National Assembly passes: what each law does, what its proposer says it will
change, and how every MP voted on it.

**Site:** https://zailiprotiv.rs

**Status:** live. Six convocations (9th to 14th, 2012 to now): about 2,100 laws, each with its final roll call by
group and by MP; about 1,000 MPs; the stenographic notes of every sitting since 2012, word for word and searchable;
bills in procedure; and visitors' own votes ("Glasaj i ti"). What an AI model wrote (summaries of memoranda and
debates, overviews of what an MP says) is labelled as such, with the model's name.

## Principles

1. **The same rules for every MP, club and party.** Nothing is computed differently for anyone.
2. **Primary sources only:** the Assembly's own roll-call results, bills and transcripts, and laws as published.
   For the laws with most votes against, opinions of independent bodies and analyses by media and civil society
   appear as labelled notes with their source, never as a figure, a vote or a ranking.
3. **A law's effects are its proposer's,** summarised from the bill's explanatory memorandum and analysis of
   effects, with a link. The site doesn't judge laws.
4. **MPs are public officials:** their names and votes are shown. Nothing about their private lives.
5. **Nothing from third parties** on the pages: no cookies, fonts or scripts from other servers. The maintainer's
   listed exceptions: visits are counted with Cloudflare Web Analytics (no cookies, no tracking of individuals), and
   the notes' pages, downloads and share pictures are served from the project's own buckets on its own subdomains.
6. **What MPs say is not censored and not shaped:** quotes word for word, every name as spoken, nothing left out
   for being harsh or personal, and no label or verdict of the site's own.

`AGENTS.md` holds the principles in full, with the maintainer's decisions and their dates.

## Source

The Assembly publishes each roll-call vote as a PDF under `https://www.parlament.gov.rs/upload/rezultati_glasanja/`:
the kind of vote, its date and time, and every MP with their vote and club. The Cyrillic page of each sitting links
every agenda item to its roll call; the sittings are listed on the regular and extraordinary sessions' pages.

## Commands

```sh
uv sync
# Every command works on the current convocation, data/14/; `--convocation 13` before the command, on another.
uv run zailiprotiv status              # what the data still lacks, per convocation; batches running or refused
uv run zailiprotiv index               # sittings of the convocation and their roll calls → data/14/index.json
uv run zailiprotiv laws                # laws the convocation passed → data/14/laws.json
uv run zailiprotiv procedure           # bills in procedure now → data/14/procedure.json
uv run zailiprotiv votes               # read every roll call not read yet → data/14/votes/ (needs pdftotext)
uv run zailiprotiv bills               # each bill's memorandum → data/14/bills/ (scanned bills by OCR: tesseract, srp)
uv run zailiprotiv link                # each law's kind, roll calls and final vote, into data/14/laws.json
uv run zailiprotiv transcripts         # stenographic notes of the sittings → data/14/transcripts/
uv run zailiprotiv summaries --batch   # the model's summaries of the memoranda, through the Batch API
uv run zailiprotiv summaries-check     # reasons without the proposer's attribution, in any model's summaries (reads only)
ZAILIPROTIV_MODEL=ollama:llama3.1:8b uv run zailiprotiv summaries --limit 5   # by hand, a local model, no key
uv run zailiprotiv debates-batch       # the model's summaries of the debates on the most contested laws
uv run zailiprotiv profiles-batch      # the model's overviews of what an MP says → data/profiles/
uv run zailiprotiv site --out _site    # build the static site
uv run zailiprotiv notes-site --out _beleske   # the notes as pages of their own (for the bucket)
uv run pytest
```

The sandbox of a coding session usually cannot reach parlament.gov.rs; GitHub's runners can. Everything that reads
the Assembly's site runs through the workflows below.

## Pages

- **Zakoni:** adopted laws by convocation, bills in procedure (a page per bill, with the summary of its memorandum
  where one is written), areas. A law's page: the final vote by group and MP, the summary of the memorandum, the
  debate with verbatim quotes, the sparks in its debate, downloads, a picture for sharing, and the visitor's own vote.
- **Poslanici:** a page per MP (votes, key votes, activity on the floor, what they say, replies and measures) and per
  parliamentary group.
- **Varnice:** from the notes, by rule and with no model: the chair's measures, exchanges of replies, harsh words,
  who speaks most; per convocation and over all of them.
- **Skupština:** weeks, sittings, convocations, the Assembly in numbers.
- **Glasaj i ti:** the visitor's ballot ("Moj listić"): everything they voted on (laws, bills before the Assembly
  votes, the quiz) beside the Assembly's result, with the MPs and groups that voted the same. The ballot stays in
  the browser. Votes are also counted anonymously by the project's own counter (`worker/`); the method page says
  what is kept.
- **Search** over the site and every speech in the notes (Pagefind; Latin without its marks finds the words with
  them), feeds (new laws, bills, per area, per MP), downloads (CSV, JSON). Every page also in Cyrillic, under `cir/`.

## Where things are served from

| Address | What | From |
|---|---|---|
| zailiprotiv.rs | the site's pages | GitHub Pages, behind Cloudflare's proxy |
| beleske.zailiprotiv.rs | the notes' pages and their search index; the notes as read (`sirovo/`) | R2 bucket `zailiprotiv-beleske` |
| podaci.zailiprotiv.rs | every law's CSV, JSON and picture, MPs' pictures, `podaci/` | R2 bucket `zailiprotiv-podaci` |
| glasovi.zailiprotiv.rs | the visitors' votes counter | Cloudflare Worker with D1 (`worker/`) |

Secrets and tokens live in GitHub Secrets and Cloudflare, never in the repository. `data/settings.json` holds the
public addresses.

## Workflows

| Workflow | When | What |
|---|---|---|
| votes | hourly by day, and by hand (choose the convocation) | index the sittings and laws, the bills in procedure, read the roll calls and bills not read yet, link them, commit `data/<N>/` |
| transcripts | after votes, and by hand | the stenographic notes of the sittings; the raw notes go to the bucket |
| summaries | after transcripts, every six hours, and by hand | the model's writing through the Batch API: bill summaries, debate summaries, MP overviews. The first pass is always the cheapest model; a stronger one only by hand |
| pages | on push, and after each data run | build the site, its search index, send downloads to the bucket, publish on GitHub Pages, purge the cache |
| notes | after transcripts, and by hand | build the notes' pages and their search index, send what changed to the bucket |
| files | by hand | make the downloads' bucket hold exactly what the site has |
| worker | on push to `worker/` | deploy the votes counter and its schema |
| health | hourly | ask the site, the buckets and the counter from outside; an issue when one does not answer |
| watch | four times a day | do visitors' votes look inflated? An issue when one network sends most of a law's votes |
| test | on push | the whole test suite |
| trial, probe, sample, dns-check, fixtures | by hand | a build with all notes and a profile; what is inside scanned bill PDFs; a sample of another model's writing; DNS; test fixtures |

## Layout

```
src/zailiprotiv/
  config.py, skupstina.py     the Assembly's site: addresses, sittings, the roll-call PDF of each agenda item
  rollcall.py, laws.py        reading a roll-call PDF; the adopted laws
  bills.py, procedure.py      a bill's memorandum (OCR for scans); bills in procedure
  kinds.py, link.py, mps.py   an act's kind and area; which roll calls were on which law; who an MP is across rolls
  transcripts.py, debates.py  the stenographic notes; what was said about a law
  summaries.py, profiles.py, batch.py, federated.py   the model's writing: prompts, checks, the Batch API
  site.py, pages_*.py         the static site, with templates/ and static/
  pages_floor.py              "Varnice", by rule from the notes
  pages_ballot.py, pages_quiz.py   "Glasaj i ti": the ballot and the quiz
  notes_site.py, files_site.py     the notes' pages and the downloads, for the buckets
  cyrillic.py, translit.py    the Cyrillic edition; Cyrillic → Latin
  digest.py, feeds.py, downloads.py, card.py, photos.py, publish.py
  cli.py                      commands
worker/                       the visitors' votes counter (Cloudflare Worker, D1)
data/<N>/                     one folder per convocation (9 to 14)
  index.json, laws.json, procedure.json
  votes/, bills/, summaries/, debates/, transcripts/, notes/
data/profiles/, data/photos/  MPs' overviews and portraits
data/quiz.json, settings.json, batches.json
tests/
```

## License

MIT
