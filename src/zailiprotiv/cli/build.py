"""Building the site, patching its static files, and what the data still lacks."""

from __future__ import annotations

import json
from pathlib import Path

from zailiprotiv.cli import common


def website(args) -> int:
    from zailiprotiv import site
    stats = site.build(common.ROOT, Path(args.out), args.domain or None, clean=not args.html_links, cyrillic=not args.latin_only)
    print(", ".join(f"{k}: {v}" for k, v in stats.items()))
    bad = site.check(Path(args.out))  # the site is not published while any page breaks the rules
    for b in bad:
        print(f"  {b}")
    return 1 if bad else 0


def static_patch(args) -> int:
    """static/ into a site built before: the pages workflow's fast path when a push changes nothing else."""
    from zailiprotiv import site
    got = site.patch_static(Path(args.site))
    print(f"static: version {got['was']} -> {got['version']}, {got['pages']} pages")
    bad = site.check(Path(args.site))
    for b in bad:
        print(f"  {b}")
    return 1 if bad else 0


def status(args) -> int:
    """What the data still lacks, per convocation: laws without a final vote, a memorandum, a summary or a debate
    summary; notes read; and the batches still running or refused. Read-only."""
    from zailiprotiv import batch, profiles, site
    rows = []
    for conv in sorted((d.name for d in common.ROOT.iterdir() if (d / "laws.json").exists()), key=int, reverse=True):
        d = common.ROOT / conv
        laws_ = json.loads((d / "laws.json").read_text(encoding="utf-8"))["laws"].values()
        names = {l.get("bill_file") for l in laws_ if l.get("bill_file")}
        have = lambda sub: {f.name for f in (d / sub).glob("*.json")} if (d / sub).is_dir() else set()
        memos = {n for n in names if (d / "bills" / n).exists() and
                 json.loads((d / "bills" / n).read_text(encoding="utf-8")).get("sections")}
        notes = have("transcripts")
        read = sum(1 for n in notes if json.loads((d / "transcripts" / n).read_text(encoding="utf-8")).get("speeches"))
        rows.append((conv, len(laws_), sum(1 for l in laws_ if not l.get("final_vote")), len(names - memos),
                     len(memos - have("summaries")), len(notes), read, len(have("debates"))))
    print(f"{'saziv':>5} {'zakona':>7} {'bez konačnog':>13} {'bez obrazl.':>11} {'bez sažetka':>11} "
          f"{'beleške':>8} {'sa govorima':>11} {'rasprave':>9}")
    for r in rows:
        print(f"{r[0]:>5} {r[1]:>7} {r[2]:>13} {r[3]:>11} {r[4]:>11} {r[5]:>8} {r[6]:>11} {r[7]:>9}")
    eligible = sum(1 for own in profiles.speeches(common.ROOT).values()
                   if len([s for s in own if len(s["text"].split()) >= profiles.LONG]) >= args.min)
    done = len([f for f in (common.ROOT / "profiles").glob("*.json")])
    print(f"pregledi poslanika: {done} (sa dovoljno govora: {eligible})")
    state = batch.State(common.ROOT / "batches.json")
    for kind, p in state.data["pending"].items():
        print(f"batch u toku: {kind} {p['id']} ({len(p['names'])})")
    for kind, names in state.data["refused"].items():
        print(f"odbijeno: {kind}: " + ", ".join(f"{n} ({r['tries']}x)" for n, r in sorted(names.items())))
    for kind, models in sorted(state.data["usage"].items()):
        for model, u in sorted(models.items()):
            print(f"potrošeno: {kind} {model}: {u['replies']} odgovora, ulaz {u['input']:,} (+ keš upis "
                  f"{u['cache_written']:,}, keš čitanje {u['cache_read']:,}), izlaz {u['output']:,} tokena")
    return 0
