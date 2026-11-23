# Decisions log

Decisions about the project's course, day by day, moved word for word from AGENTS.md on 20 Nov 2026 (the
maintainer's decision, so that an agent reads the rules and only the decisions of the part it works on). **Keep it
current:** a decision made or changed is added here, at the end of the section it belongs to, in the same commit as
the change. The principles and the rules of work are in AGENTS.md.

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
- **20 Nov 2026:** the rules of work, the guards and the scripts this project shares with the organization's others
  come from `javni-uvid/osnova` (the maintainer's decision): the **osnova** workflow copies them into `osnova/`,
  `tools/posalji.sh`, `tools/pocisti.sh` and the pre-push hook only call the copy's, and AGENTS.md keeps what is
  this project's own. The principles here stay whole and in force; `osnova/principles.md` is the common core.
- **22 Nov 2026:** the search by meaning (a local cognee server over the decisions, the commits, the laws and the
  agents' own notes, 20-22 Nov) removed at the maintainer's decision; it was the second cognee trial (the first, on 16-17 Nov,
  was removed too). In about 14 hours of agents' work they asked it 6 times and wrote 3 notes; on the full store
  the right law was among the first five hits for 7 of 12 questions with a known answer (13 of 14 on a sample of 120
  laws: it falls as the store grows), and a hit often came without the line saying where it is from, which `grep`
  could not trace because the summaries under `data/` are in Cyrillic and the store was in Latin. It cost 14 hours of
  the computer to fill, 2 GB of memory kept, and a refresh by hand; without an LLM only the search of pieces of text
  worked, which a plain index does as well. Before a third try: a lighter index of the same kind, each piece carrying
  its own source line, and a reason the agents would ask it more than they grep.
- **23 Nov 2026:** `live/AGENTS.md` (77 KB, read whole by every agent in `live/`) split: the decisions word for word
  into `docs/decisions/live-*.md` by part, what holds now in short in `live/AGENTS.md`.
