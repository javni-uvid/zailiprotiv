"""The model's writing: summaries of the memoranda, debates and MPs' overviews, by batch or by hand (export and
import)."""

from __future__ import annotations

import json
import os
from pathlib import Path

from zailiprotiv import jsonfile

from zailiprotiv.cli import common
from zailiprotiv.cli.common import _batch_client, _debated, _pending, _waiting


def summaries_cmd(args) -> int:
    """Claude's summary of each bill's memorandum not summarised yet (or whose memorandum changed), into
    data/summaries/<bill file>.json. Needs ANTHROPIC_API_KEY."""
    from zailiprotiv import summaries
    store = json.loads(Path(args.laws).read_text(encoding="utf-8"))
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    client = None
    done = failed = skipped = 0
    tokens = {"input": 0, "output": 0}
    todo, claimed = {}, set()
    waiting = _waiting(Path(args.laws))[2]  # bills in procedure first: they are what is about to be voted on
    everything = waiting + sorted(store["laws"].values(), key=lambda l: l.get("passed") or "", reverse=True)
    for law in everything:
        name = law.get("bill_file")
        if not name or not (Path(args.bills) / name).exists():
            continue
        memo = json.loads((Path(args.bills) / name).read_text(encoding="utf-8"))
        if not memo.get("sections"):
            skipped += 1
            continue
        if name in claimed:  # two laws linked to one memorandum: a linking error, and each would rewrite the other's
            print(f"  {name}: also linked to {law['title'][:80]} (skipped)")
            continue
        claimed.add(name)
        target = out_dir / name
        text = summaries.material(law, memo)
        if "\n## " not in text:  # a memorandum whose only section found is the constitutional basis: nothing to summarise
            skipped += 1
            continue
        if target.exists() and json.loads(target.read_text(encoding="utf-8")).get("fingerprint") == \
                summaries.fingerprint(text):
            continue
        if args.limit and done + len(todo) >= args.limit:
            break
        if getattr(args, "batch", False):
            todo[name] = (law, memo, target)
            continue
        if client is None:
            import anthropic
            client = anthropic.Anthropic()
        try:
            result = summaries.summarize(law, memo, client)
        except Exception as e:  # one bad reply mustn't stop the rest
            failed += 1
            print(f"  failed {law['title'][:90]}: {type(e).__name__}: {str(e)[:200]}")
            continue
        target.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        tokens["input"] += result["usage"]["input"]
        tokens["output"] += result["usage"]["output"]
        done += 1
    if getattr(args, "batch", False):
        from zailiprotiv import batch
        client, state = _batch_client(args)
        if client is None:
            return 0
        kind = f"summaries-{common.CONVOCATION}"
        pending = state.pending(kind)
        for name in (pending or {}).get("names", []):
            if name not in todo:
                law = next(l for l in everything if l.get("bill_file") == name)
                todo[name] = (law, json.loads((Path(args.bills) / name).read_text(encoding="utf-8")), out_dir / name)
        requests = {name: {"model": summaries.MODEL, "max_tokens": batch.ROOM, "system": batch.cached(summaries.SYSTEM),
                           "messages": [{"role": "user", "content": summaries.material(law, memo)}]}
                    for name, (law, memo, _) in todo.items()}
        replies = batch.run(client, state, kind, requests, args.wait)
        for name, text in sorted((replies or {}).items()):
            law, memo, target = todo[name]
            try:
                result = summaries.record(law, memo, summaries.parse(text), summaries.MODEL)
            except (ValueError, json.JSONDecodeError) as e:
                failed += 1
                print(f"  failed {law['title'][:90]}: {e}")
                continue
            target.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            done += 1
    print(f"summaries written: {done}, failed: {failed}, bills without a memorandum: {skipped}; "
          f"tokens in {tokens['input']:,}, out {tokens['output']:,}")
    return 1 if failed and not done else 0


def export(args) -> int:
    """The material of laws still without a summary, one text file each, for summaries written by hand."""
    from zailiprotiv import summaries
    to = Path(args.to)
    to.mkdir(parents=True, exist_ok=True)
    if args.only:
        wanted = [n.strip() for n in Path(args.only).read_text(encoding="utf-8").split() if n.strip()]
        store = json.loads(Path(args.laws).read_text(encoding="utf-8"))
        by_bill = {l.get("bill_file"): l for l in store["laws"].values() if l.get("bill_file")}
        pending = [(by_bill[n], json.loads((Path(args.bills) / n).read_text(encoding="utf-8")), n)
                   for n in wanted if n in by_bill and (Path(args.bills) / n).exists()]
    else:
        pending = _pending(args)
    if args.kind:
        pending = [p for p in pending if p[0].get("kind") in args.kind.split(",")]
    chosen = pending[args.skip: args.skip + args.limit] if args.limit else pending[args.skip:]
    for law, memo, name in chosen:
        limits = summaries.DEEP_LIMITS if args.deep else None
        (to / (name.removesuffix(".json") + ".txt")).write_text(summaries.material(law, memo, limits),
                                                                 encoding="utf-8")
    (to / "RULES.txt").write_text(summaries.SYSTEM, encoding="utf-8")
    print(f"pending: {len(pending)}, exported: {len(chosen)} to {to}")
    return 0


def import_summaries(args) -> int:
    """Summaries written by hand (a JSON Lines file: {"bill_file", "summary"}), checked and saved like the
    API's, under the name of the model that wrote them."""
    from zailiprotiv import summaries
    store = json.loads(Path(args.laws).read_text(encoding="utf-8"))
    by_bill = {l.get("bill_file"): l for l in store["laws"].values() if l.get("bill_file")}
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    saved = refused = 0
    for line in Path(args.file).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        name = item["bill_file"] if item["bill_file"].endswith(".json") else item["bill_file"] + ".json"
        law = by_bill.get(name)
        try:
            if law is None:
                raise ValueError("no such bill")
            summary = summaries.parse(json.dumps(item["summary"], ensure_ascii=False))
        except ValueError as e:
            refused += 1
            print(f"  refused {name}: {e}")
            continue
        memo = json.loads((Path(args.bills) / name).read_text(encoding="utf-8"))
        (out_dir / name).write_text(json.dumps(summaries.record(law, memo, summary, args.model, deep=args.deep),
                                               ensure_ascii=False,
                                               indent=1) + "\n", encoding="utf-8")
        saved += 1
    print(f"summaries saved: {saved}, refused: {refused}")
    return 1 if refused and not saved else 0


def debates_export(args) -> int:
    """The debate material of the laws with most votes against whose notes were read, one text file each, for
    summaries of the debate written by hand."""
    from zailiprotiv import debates
    found, votes_, bills_ = _debated(args)
    seated, df = debates.seats(votes_), debates.document_frequency(bills_)
    to = Path(args.to)
    to.mkdir(parents=True, exist_ok=True)
    chosen = found[:args.top]
    for law, bill, n, final, item in chosen:
        text = debates.material(law, bill, n, final, seated, item, df)
        (to / (law["bill_file"].removesuffix(".json") + ".txt")).write_text(text, encoding="utf-8")
    (to / "RULES.txt").write_text(debates.SYSTEM, encoding="utf-8")
    print(f"exported: {len(chosen)} to {to}")
    return 0


def profiles_export(args) -> int:
    """The speeches of every MP with enough of them in the notes read, one JSON file each, for overviews written in
    a session (rules: data/profiles/RULES.md). MPs who have an overview are skipped unless --again."""
    from zailiprotiv import profiles
    to = Path(args.to)
    to.mkdir(parents=True, exist_ok=True)
    n = 0
    for key, own in sorted(profiles.speeches(common.ROOT).items()):
        long = [s for s in own if len(s["text"].split()) >= profiles.LONG]
        name = key.replace(" ", "-") + ".json"
        if len(long) < args.min or ((common.ROOT / "profiles" / name).exists() and not args.again):
            continue
        (to / name).write_text(json.dumps({"mp": key, "total_speeches": len(own), "speeches": profiles.selection(own)},
                                          ensure_ascii=False, indent=1), encoding="utf-8")
        n += 1
    print(f"exported: {n} to {to}")
    return 0


def profiles_import(args) -> int:
    """Overviews written by hand (DIR/out/<name>.json beside the exported DIR/<name>.json), checked and saved to
    data/profiles/. With --check FILE: only say what is wrong with one reply."""
    from zailiprotiv import profiles
    src = Path(args.dir)
    files = [Path(args.check)] if args.check else sorted((src / "out").glob("*.json"))
    saved = refused = 0
    for f in files:
        try:
            reply, material = json.loads(f.read_text(encoding="utf-8")), json.loads((src / f.name).read_text(encoding="utf-8"))
            bad = profiles.check(reply, material)
        except (ValueError, KeyError, TypeError, OSError) as e:
            bad = [f"nečitljivo: {e}"]
        if bad:
            refused += 1
            print(f"  {f.name}: " + "; ".join(bad))
        elif not args.check:
            (common.ROOT / "profiles").mkdir(exist_ok=True)
            (common.ROOT / "profiles" / f.name).write_text(json.dumps(profiles.record(reply, material, args.model), ensure_ascii=False,
                                                               indent=1) + "\n", encoding="utf-8")
            saved += 1
    print("OK" if args.check and not refused else f"saved: {saved}, refused: {refused}")
    return 1 if refused else 0


def debates_import(args) -> int:
    """Debate summaries written by hand (JSON Lines: {"bill_file", "debate"}): quotes checked against the notes
    word for word, saved to data/<N>/debates/<bill file>.json."""
    from zailiprotiv import debates
    found, votes_, bills_ = _debated(args)
    seated, df = debates.seats(votes_), debates.document_frequency(bills_)
    by_bill = {law["bill_file"]: (law, bill, n, final, item) for law, bill, n, final, item in found}
    out = common.DATA / "debates"
    out.mkdir(parents=True, exist_ok=True)
    saved = refused = 0
    for line in Path(args.file).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        name = entry["bill_file"] if entry["bill_file"].endswith(".json") else entry["bill_file"] + ".json"
        if name not in by_bill:
            print(f"  refused {name}: no notes read for its sitting")
            refused += 1
            continue
        law, bill, n, final, item = by_bill[name]
        try:
            debate, dropped = debates.parse(entry["debate"], n, debates.speaker_groups(n, final, seated))
        except (ValueError, AttributeError) as e:
            print(f"  refused {name}: {e}")
            refused += 1
            continue
        text = debates.material(law, bill, n, final, seated, item, df)
        (out / name).write_text(json.dumps(debates.record(law, text, debate, args.model, dropped), ensure_ascii=False,
                                           indent=1) + "\n", encoding="utf-8")
        print(f"  {name}: {len(debate['citati'])} quotes kept, {len(dropped)} dropped" +
              "".join(f"\n    dropped: {d[:90]}" for d in dropped))
        saved += 1
    print(f"debates saved: {saved}, refused: {refused}")
    return 1 if refused and not saved else 0


def profiles_batch(args) -> int:
    """Overviews of what MPs most often say, for every MP with enough speeches and no overview yet, written through
    the Batch API, checked like a session's (quotes word for word) and saved to data/profiles/."""
    from zailiprotiv import batch, profiles, summaries
    client, state = _batch_client(args)
    if client is None:
        return 0
    kind, system = "profiles", profiles.system(common.ROOT)
    materials = {}
    model = (state.pending(kind) or {}).get("model") or summaries.MODEL
    replace = set(filter(None, os.environ.get("ZAILIPROTIV_REPLACE", "").split(",")))  # see debates_batch
    for key, own in sorted(profiles.speeches(common.ROOT).items()):
        long = [s for s in own if len(s["text"].split()) >= profiles.LONG]
        name = key.replace(" ", "-") + ".json"
        there = common.ROOT / "profiles" / name
        again = args.again or (replace and there.exists() and json.loads(there.read_text(encoding="utf-8")).get("model") in replace)
        if len(long) < args.min or (there.exists() and not again) or state.gave_up(kind, name):
            continue
        materials[name] = {"mp": key, "total_speeches": len(own), "speeches": profiles.selection(own)}
        if args.limit and len(materials) >= args.limit:
            break
    pending = state.pending(kind)
    if pending:  # the material of a batch already sent, so its replies can be checked
        for name in pending["names"]:
            if name not in materials:
                key = name.removesuffix(".json").replace("-", " ")
                own = profiles.speeches(common.ROOT).get(key, [])
                materials[name] = {"mp": key, "total_speeches": len(own), "speeches": profiles.selection(own)}
    requests = {n: {"model": model, "max_tokens": batch.ROOM, "system": batch.cached(system),
                    "messages": batch.messages(kind, n, json.dumps(m, ensure_ascii=False), state)}
                for n, m in materials.items()}
    replies = batch.run(client, state, kind, requests, args.wait)
    if replies is None:
        return 0
    saved = refused = 0
    for name, text in sorted(replies.items()):
        material = materials[name]
        try:
            reply = profiles.reply_json(text)
            bad = profiles.check(reply, material)
            result = None if bad else profiles.record(reply, material, model)
        except (ValueError, KeyError, TypeError, AttributeError) as e:
            bad = [f"nečitljivo: {type(e).__name__}: {e}"]
        if bad:
            state.refuse(kind, name, text, bad)
            refused += 1
            print(f"  refused {name}: " + "; ".join(bad)[:300])
            continue
        (common.ROOT / "profiles" / name).write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        state.accept(kind, name)
        saved += 1
    state.save()
    print(f"profiles saved: {saved}, refused: {refused} (sent again next run, at most {batch.TRIES} tries)")
    return 0


def debates_batch(args) -> int:
    """Debate summaries for the laws with most votes against whose notes were read and that have none (or whose
    material changed), written through the Batch API; quotes not in the notes word for word are dropped."""
    from zailiprotiv import batch, debates, summaries
    client, state = _batch_client(args)
    if client is None:
        return 0
    # A sample (--only, with --out): the named laws written again by the model in ZAILIPROTIV_MODEL into a folder
    # of their own, to compare models without touching the published texts.
    only = set(filter(None, (args.only or "").split(",")))
    kind = f"sample-{common.CONVOCATION}" if only else f"debates-{common.CONVOCATION}"
    found, votes_, bills_ = _debated(args)
    seated, df = debates.seats(votes_), debates.document_frequency(bills_)
    out = Path(args.out) if args.out else common.DATA / "debates"
    if only and not args.out:
        raise SystemExit("--only needs --out: a sample must not replace the published texts")
    out.mkdir(parents=True, exist_ok=True)
    chosen, pending = {}, state.pending(kind)
    wanted = set(pending["names"]) if pending else set()
    model = (pending or {}).get("model") or summaries.MODEL
    # ZAILIPROTIV_REPLACE names a model whose texts are to be written again by the model of this run (a run by hand,
    # to move from a weaker model to a stronger one); the old text stays until the new one passes the checks.
    replace = set(filter(None, os.environ.get("ZAILIPROTIV_REPLACE", "").split(",")))
    for i, (law, bill, n, final, item) in enumerate(found):
        name = law["bill_file"]
        text = debates.material(law, bill, n, final, seated, item, df)
        saved = jsonfile.load(out / name, {})
        done = saved.get("fingerprint") == debates.fingerprint(text) and saved.get("model") not in replace
        if only:
            if name in only and not done:
                chosen[name] = (law, n, final, text)
        elif name in wanted or (i < args.top and not done and not state.gave_up(kind, name)):
            chosen[name] = (law, n, final, text)
    requests = {name: {"model": model, "max_tokens": batch.ROOM, "system": batch.cached(debates.SYSTEM),
                       "messages": batch.messages(kind, name, text, state)}
                for name, (law, n, final, text) in chosen.items()}
    replies = batch.run(client, state, kind, requests, args.wait, force=bool(only))
    if replies is None:
        return 0
    saved = refused = 0
    for name, reply in sorted(replies.items()):
        law, n, final, text = chosen[name]
        try:
            debate, dropped = debates.parse(reply, n, debates.speaker_groups(n, final, seated))
        except (ValueError, AttributeError, TypeError) as e:
            state.refuse(kind, name, reply, [str(e) or type(e).__name__])
            refused += 1
            print(f"  refused {name}: {e}")
            continue
        (out / name).write_text(json.dumps(debates.record(law, text, debate, model, dropped),
                                           ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        state.accept(kind, name)
        saved += 1
        print(f"  {name}: {len(debate['citati'])} quotes kept, {len(dropped)} dropped")
    state.save()
    print(f"debates saved: {saved}, refused: {refused}")
    return 0
