# Za ili protiv

A public site about the laws Serbia's National Assembly passes: what each law does, what its proposer says it will
change, and how every MP voted on it.

**Status:** skeleton. The probe that finds the Assembly's roll-call results comes first.

## Principles

1. **The same rules for every MP, club and party.** Nothing is computed differently for anyone.
2. **Primary sources only:** the Assembly's own roll-call results, bills and transcripts, and laws as published.
3. **A law's effects are its proposer's,** summarised from the bill's explanatory memorandum and analysis of
   effects, with a link. The site doesn't judge laws.
4. **MPs are public officials:** their names and votes are shown. Nothing about their private lives.
5. **Nothing from third parties** on the pages: no analytics, cookies, fonts or scripts from other servers.

## Source

The Assembly publishes each roll-call vote as a PDF under `https://www.parlament.gov.rs/upload/rezultati_glasanja/`:
the kind of vote, its date and time, and every MP with their vote and club.

## Commands

```sh
uv sync
uv run zailiprotiv probe --out probe   # reach the Assembly's site, find where it lists roll-call PDFs
uv run pytest
```

## Workflows

| Workflow | When | What |
|---|---|---|
| probe | by hand | can GitHub's runners reach parlament.gov.rs; which pages list roll-call PDFs; saves samples as an artifact |
| test | on push | the whole test suite |

## Layout

```
src/zailiprotiv/
  config.py      the Assembly's address, User-Agent, delay between requests
  skupstina.py   fetching pages, finding roll-call PDFs on the site
  cli.py         commands
  translit.py    Cyrillic → Latin
  jsonfile.py    JSON stores one entry per line, for small git diffs
tests/
```

## License

MIT
