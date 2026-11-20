# The code

Decisions about how the code is laid out and built, moved word for word from AGENTS.md on 20 Nov 2026 (the
maintainer's decision, so that an agent reads the rules and only the decisions of the part it works on). **Keep it
current:** a decision made or changed is added here, at the end of the section it belongs to, in the same commit as
the change. The principles and the rules of work are in AGENTS.md.

## The code

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
