# Za ili protiv

A public site about the laws Serbia's National Assembly passes: what each law does, what its proposer says it will
change, and how every MP voted on it.

**Site:** https://zailiprotiv.rs

**Status:** first version. The Fourteenth convocation's laws, each with its final roll call by group and by MP, and
every MP's votes, and Claude's summary of each law's memorandum, labelled as such.

## Principles

1. **The same rules for every MP, club and party.** Nothing is computed differently for anyone.
2. **Primary sources only:** the Assembly's own roll-call results, bills and transcripts, and laws as published.
   For the laws with most votes against, opinions of independent bodies and analyses by media and civil society
   appear as labelled notes with their source, never as a figure, a vote or a ranking.
3. **A law's effects are its proposer's,** summarised from the bill's explanatory memorandum and analysis of
   effects, with a link. The site doesn't judge laws.
4. **MPs are public officials:** their names and votes are shown. Nothing about their private lives.
5. **Nothing from third parties** on the pages: no analytics, cookies, fonts or scripts from other servers.

## Source

The Assembly publishes each roll-call vote as a PDF under `https://www.parlament.gov.rs/upload/rezultati_glasanja/`:
the kind of vote, its date and time, and every MP with their vote and club. The Cyrillic page of each sitting links
every agenda item to its roll call; the sittings are listed on the regular and extraordinary sessions' pages.

## Commands

```sh
uv sync
# Every command works on the current convocation, data/14/; `--convocation 13` before the command, on another.
uv run zailiprotiv index               # sittings of the convocation and their roll calls → data/14/index.json
uv run zailiprotiv laws                # laws the current convocation passed → data/14/laws.json
uv run zailiprotiv summaries           # Claude's summaries of the memoranda → data/14/summaries/ (ANTHROPIC_API_KEY)
uv run zailiprotiv export --to DIR      # material of laws without a summary, for summaries written in a session
uv run zailiprotiv import FILE --model M  # save such summaries (JSON Lines: bill_file, summary)
uv run zailiprotiv site --out _site   # build the static site
uv run zailiprotiv link                # each law's kind, roll calls and final vote, into data/14/laws.json
uv run zailiprotiv bills               # each law's bill: memorandum and constitutional basis → data/14/bills/
uv run zailiprotiv votes               # read every roll call not read yet → data/14/votes/<sitting>.json (needs pdftotext)
uv run pytest
```

## Pages

Laws (by convocation, area and sitting), a page per law (final vote by group and MP, summary of the memorandum, the
debate, a picture for sharing), a page per MP (key votes, activity, votes by area and period), a page per
parliamentary group, "Skupština u brojkama", "Glasaj i ti" (vote on the key laws and compare with groups and MPs, in
the browser), the week in the Assembly (pages and a feed a newsletter can be sent from), feeds (new laws, per area,
per MP) and downloads (CSV, JSON). Every page also in Cyrillic, under `cir/`.

## Workflows

| Workflow | When | What |
|---|---|---|
| votes | every morning, and by hand (choose the convocation) | index the sittings and laws, read the roll calls and bills not read yet, link them, commit `data/<N>/` |
| transcripts | after votes, and by hand | stenographic notes of the debates on the most contested laws |
| summaries | after transcripts, every six hours, and by hand | the model's writing through the Batch API: bill summaries, debate summaries, MP overviews (secret `ANTHROPIC_API_KEY`) |
| pages | on push, and after each data run | build the site and publish it on GitHub Pages |
| fixtures | by hand | add real roll-call PDFs to `tests/fixtures` |
| test | on push | the whole test suite |

## Layout

```
src/zailiprotiv/
  config.py      the Assembly's address, User-Agent, delay between requests
  skupstina.py   the Assembly's site: sittings and the roll-call PDF of each agenda item
  rollcall.py    reading a roll-call PDF: the vote, and each MP's vote and group
  laws.py        the adopted laws: title, bill, day passed, Official Gazette, international treaty or not
  bills.py       a bill's memorandum: constitutional basis (article, points), reasons, funds, effects
  kinds.py       an act's kind (from its title) and area (from Article 97 of the Constitution), with their labels
  link.py        which roll calls were on which law, and its final vote
  summaries.py   Claude's summary of a bill's memorandum: prompt, material, checks
  site.py        the static site, with templates/ and static/
  mps.py         who an MP is across roll calls: a name key without word order or titles
  cli.py         commands
  translit.py    Cyrillic → Latin
  jsonfile.py    JSON stores one entry per line, for small git diffs
data/<N>/        one folder per convocation (14, 13, 12)
  index.json     sittings and their roll calls (one sitting per line)
  laws.json      the convocation's adopted laws (one law per line)
  bills/         one file per bill: its memorandum's sections and the Constitution's articles it cites
  notes/         outside views on a law (independent bodies; media and civil society): source, date, link, note
  summaries/     one file per bill: the summary, the model, a fingerprint of what it read
  votes/         one file per sitting: each vote's date, item, kind, counts and rows (number, name, vote, group)
tests/
```

## License

MIT
