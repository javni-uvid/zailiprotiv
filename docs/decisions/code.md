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
- **The build's slowest counts made cheaper, the pages unchanged** (20 Nov 2026, from a profile of the build on a
  runner, 265 s): four counts done one after another took some 80 s. Two names' letters are compared with difflib
  only when its `quick_ratio`, never below the full ratio, reaches the line (`link.closeness`, `debates._near`); a
  speech is searched for harsh words only when it holds one of the list's stems as plain text (`pages_floor.harsh`);
  an MP's words are counted once each before their stems (`profiles.distinctive`). Built before and after on the
  same data: all 19,180 files the same but for the time of building (538 s → 407 s on the maintainer's computer).
- **The site's size** (23 Nov 2026, the maintainer's request): GitHub Pages publishes no site over 1 GB, and the site
  was 833 MB (748 MiB on 18 Nov, 793 on 23 Nov), half of it the Cyrillic twins. Nothing is taken off the pages:
  - every page without indentation and without the end tags of table cells and rows, which the HTML standard lets go
    (`publish.lighter`; not in scripts and styles, not list items, whose spaces show). A step of its own after the
    search index (`zailiprotiv lighten`): Pagefind runs the cells' words together without their end tags ("117SPS"),
    found by comparing the two indexes;
  - the chamber's seats in a group per vote, the vote written once (`site.chamber_groups`): drawn the same, byte for
    byte in Edge at three densities; a path with round ends was a quarter of the size and left out, as its points are
    drawn rougher;
  - the roll call's rows without `data-g` and `data-v`, which its cells say already: the script reads the cells. The
    filter by group had found nothing on the Cyrillic pages, where the cells and the filter are Cyrillic and `data-g`
    was not;
  - an MP's every vote without a class on the day and the vote that the stylesheet can give.

  The day written once for a day's laws was tried and left out: on a phone it goes out of sight.

  Together 112 MB fewer (a build of the repository's own data: 727 to 615 MB of pages; every page's words and links,
  the search index and 900 pages read as a browser reads them the same, the pictures the same in Edge to the
  pixel). The search engines are told of a page when its words or links changed (`tools/indexnow.py`,
  `said`), no longer its markup. **pages** warns over 850 MB. The next steps, if it grows on: the `-glasovi` pages
  (noindex, some 250 MB) to a bucket with the notes' pages, or the Cyrillic edition elsewhere; both change addresses, so
  the maintainer decides.
- **No ARIA roles where a table stays a table** (27 Nov 2026, the conductor, from the size note: the site near the 850 MB
  warning). The record tables of an MP's "-glasovi" page (every final vote, by convocation; some 500,000 rows with the
  Cyrillic twins) said `role="row"`/`"cell"`/`"rowgroup"`/`"columnheader"` on every element, which a native table already
  says; they keep their layout on every screen. Left out there, 23 bytes a row; the "group-votes" tables, whose cells
  become blocks on a phone, keep theirs. Nothing seen or heard changes.
- **A branch's real pages without a build here: pregled** (27 Nov 2026, the conductor: the workers' computer, 16 GB with
  other workers on it, has no room for a build). `pregled` (workflow_dispatch on the branch, `--ref`, with the pages) builds the branch on
  a runner over the repository's data as **pages** does (the share pictures and downloads moved out as there, the search
  index made, the pages lightened), with `--html-links`, and uploads the pages asked for with what they load
  (`tools/pregled.py`: only files of the built site, no path outside it) for three days; it prints the site's size and
  where the bytes are by folder. Without secrets it lacks the notes that only the bucket holds, so its size and an MP's
  speeches are of the repository's notes: compare two of its runs, not one of its with **pages**.
