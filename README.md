# Za ili protiv

A public site about the laws Serbia's National Assembly passes: what each law does, what its proposer says it will
change, and how every MP voted on it.

**Status:** first version. The Fourteenth convocation's roll calls are indexed and read; joining MPs across
votes and the laws' summaries come next.

## Principles

1. **The same rules for every MP, club and party.** Nothing is computed differently for anyone.
2. **Primary sources only:** the Assembly's own roll-call results, bills and transcripts, and laws as published.
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
uv run zailiprotiv index               # sittings of the current convocation and their roll calls → data/index.json
uv run zailiprotiv laws                # laws the current convocation passed → data/laws.json
uv run zailiprotiv link                # each law's kind, roll calls and final vote, into data/laws.json
uv run zailiprotiv bills               # each law's bill: memorandum and constitutional basis → data/bills/
uv run zailiprotiv votes               # read every roll call not read yet → data/votes/<sitting>.json (needs pdftotext)
uv run pytest
```

## Workflows

| Workflow | When | What |
|---|---|---|
| votes | by hand | index the sittings and laws, read the roll calls and bills not read yet, link them, commit `data/` |
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
  mps.py         who an MP is across roll calls: a name key without word order or titles
  cli.py         commands
  translit.py    Cyrillic → Latin
  jsonfile.py    JSON stores one entry per line, for small git diffs
data/
  index.json     sittings and their roll calls (one sitting per line)
  laws.json      the convocation's adopted laws (one law per line)
  bills/         one file per bill: its memorandum's sections and the Constitution's articles it cites
  votes/         one file per sitting: each vote's date, item, kind, counts and rows (number, name, vote, group)
tests/
```

## License

MIT
