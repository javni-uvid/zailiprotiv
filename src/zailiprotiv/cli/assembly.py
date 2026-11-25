"""Reading the Assembly's site: sittings, roll calls, laws, bills, members, offices, photos, the Rules, the notes of
debates."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import subprocess
import tempfile
import time
import urllib.parse
from pathlib import Path

from zailiprotiv import bills, jsonfile, kinds, laws, link, rollcall, skupstina, transcripts
from zailiprotiv.config import CONVOCATIONS, CURRENT
from zailiprotiv.translit import latin

from zailiprotiv.cli import common
from zailiprotiv.cli.common import _shrunk, _waiting, all_votes, file_name, sitting_id


def index(args) -> int:
    """The current convocation's sittings and the roll-call PDF of each agenda item, into data/index.json."""
    found, later = skupstina.index(convocation=common.CONVOCATION)
    store = {
        "fetched": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "sittings": {
            s.url: {"listed": i, "title": s.title, "votes": [[v.item, v.pdf] for v in s.votes],
                    "agenda": s.agenda, "starts": s.starts, **({"continues": s.continues} if s.continues else {})}
            for i, s in enumerate(found)
        },
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    total = sum(len(s.votes) for s in found)
    known = jsonfile.load(out, {}).get("sittings") or {}
    if _shrunk(out, "sittings", sum(1 for s in found if s.votes), lambda v: bool(v.get("votes"))):
        return 0
    jsonfile.save(out, store, "sittings")
    print(f"sittings: {len(found)}, roll calls: {total}")
    if getattr(args, "tell", ""):  # the votes workflow opens an issue of each file
        for i, (head, body) in enumerate(skupstina.news_of(known, store["sittings"])):
            Path(args.tell).mkdir(parents=True, exist_ok=True)
            (Path(args.tell) / f"{i}.txt").write_text(head + "\n" + body, encoding="utf-8", newline="\n")
            print(f"convened, new or changed: {head}")
    for title in later:  # the votes workflow opens an issue on this line
        print(f"::notice::A later convocation's sitting is listed: {title}")
    for s in found:
        print(f"  {len(s.votes):4}  {s.title[:100]}")
    # No roll call at all in the current convocation is a sign the page changed; a newer one may have none yet.
    if found and not total and common.CONVOCATION == CURRENT:
        print("no roll calls found: has the sittings' page layout changed?")
        return 1
    return 0


def adopted(args) -> int:
    """The laws the current convocation passed, from the Assembly's page of adopted laws, into data/laws.json."""
    source = CONVOCATIONS[common.CONVOCATION]["laws"]
    found = laws.parse(skupstina.fetch(source).decode("utf-8", "replace"), source)
    listed = len(found)
    found = [law for law in found if skupstina.within(law.passed or "", CONVOCATIONS[common.CONVOCATION])]  # the page may hold two
    store = {"fetched": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(), "source": source,
             "convocation": common.CONVOCATION,
             "laws": {law.pdf: law.as_dict() for law in found}}
    if _shrunk(Path(args.out), "laws", len(found)):
        return 0
    if Path(args.out).exists():
        laws.carry(json.loads(Path(args.out).read_text(encoding="utf-8")).get("laws") or {}, store["laws"])
    jsonfile.save(Path(args.out), store, "laws")
    print(f"laws: {len(found)} (of {listed} on the page), international treaties: {sum(l.treaty for l in found)}, "
          f"without a bill: {sum(not l.bill_pdf for l in found)}")
    # A page that lists nothing is broken, but for a convocation newer than the current one (config.CURRENT): the page
    # is empty until its first law, as it was from 17 Nov 2026.
    return 0 if found or listed or int(common.CONVOCATION) > int(CURRENT) else 1


def linked(args) -> int:
    """Each law's kind, roll calls and final vote, into data/laws.json."""
    path = Path(args.laws)
    store = json.loads(path.read_text(encoding="utf-8"))
    votes = all_votes(Path(args.votes))
    found = link.link(store["laws"], votes)
    # Links made by hand where the Assembly's PDF names the act otherwise (a wrong year, a typo, another word):
    # data/<N>/links.json, {law title: {"vote": vote key, "why": "…"}}, each checked to be a vote of that day.
    manual_path = path.parent / "links.json"
    manual = jsonfile.load(manual_path, {})
    for key, law in store["laws"].items():
        law["kind"] = kinds.kind(law["title"], law.get("treaty", False))
        law.update(found[key])
        m = manual.get(law["title"])
        if m and not law["final_vote"]:
            vote = votes.get(m["vote"])
            if not vote or vote["when"][:10] != law.get("passed"):
                print(f"  manual link refused (no such vote that day): {law['title'][:90]}")
                continue
            law.update(final_vote=m["vote"], matched="manual", votes=sorted(set(law.get("votes", [])) | {m["vote"]}))
    jsonfile.save(path, store, "laws")
    n = len(store["laws"])
    final = sum(1 for law in store["laws"].values() if law["final_vote"])
    print(f"laws: {n}, with their final vote: {final}, with some vote: "
          f"{sum(1 for law in store['laws'].values() if law['votes'])}; roll calls read: {len(votes)}")
    for law in store["laws"].values():
        if not law["final_vote"]:
            print(f"  no final vote: {law['passed']}  {law['title'][:110]}")
    return 0


def memoranda(args) -> int:
    """Each adopted law's bill, read once: its memorandum's sections and constitutional basis, into
    data/bills/<file>.json, and the law's area(s) into data/laws.json."""
    path = Path(args.laws)
    store = json.loads(path.read_text(encoding="utf-8"))
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    read = failed = 0
    proc_path, proc, waiting = _waiting(path)
    for law in list(store["laws"].values()) + waiting:
        url = law.get("bill_pdf")
        if not url:
            continue
        target = out_dir / (file_name(url).removesuffix(".pdf") + ".json")
        stale = False
        if target.exists() and not args.again:
            old = json.loads(target.read_text(encoding="utf-8"))
            # read again by a newer reader: a bill with no section found, or with nothing but its basis
            stale = set(old.get("sections") or {}) <= {"basis"} and old.get("reader", 1) < bills.READER
        if not target.exists() or args.again or stale:
            if args.limit and read >= args.limit:
                continue
            try:
                body = skupstina.fetch(url)
            except skupstina.FetchError as e:
                failed += 1
                print(f"  failed {urllib.parse.unquote(url)}: {e}")
                continue
            # closed before pdftotext opens it (Windows won't share an open file), removed when the block ends
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete_on_close=False) as f:
                f.write(body)
                f.close()
                try:
                    memo = bills.read(f.name)
                except subprocess.CalledProcessError:  # a file pdftotext can't open: the law goes without its bill
                    failed += 1
                    print(f"  unreadable {urllib.parse.unquote(url)}")
                    continue
            target.write_text(json.dumps({"bill": url, "sha256": hashlib.sha256(body).hexdigest(),
                                          "reader": bills.READER, **memo.as_dict()},
                                         ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            read += 1
        memo = json.loads(target.read_text(encoding="utf-8"))
        again_read = bills.articles(memo.get("sections", {}).get("basis", ""))  # rules may have changed
        if again_read != memo.get("articles"):
            memo["articles"] = again_read
            target.write_text(json.dumps(memo, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        law["bill_file"] = target.name
        law["constitution"] = memo["articles"]
        law["areas"] = kinds.areas(memo["articles"])
    jsonfile.save(path, store, "laws")
    if waiting:
        for b in waiting:
            b.pop("bill_pdf", None)
        jsonfile.save(proc_path, proc, "bills")
    all_laws = store["laws"].values()
    no_memo = [l for l in all_laws if l.get("bill_file") and not l.get("constitution")]
    print(f"bills read now: {read}, failed: {failed}; laws with an area: {sum(1 for l in all_laws if l.get('areas'))}, "
          f"treaties (Art. 99): {sum(1 for l in all_laws if any(a['article'] == 99 for a in l.get('constitution', [])))}, "
          f"no constitutional basis found: {len(no_memo)}")
    for l in no_memo[:30]:
        print(f"  no basis: {l['title'][:110]}")
    return 0


def in_procedure(args) -> int:
    """The bills waiting in the Assembly now, from its page "Zakoni u proceduri", into data/<N>/procedure.json, which
    also remembers the bills no longer listed and when each was first and last seen."""
    from zailiprotiv import procedure
    found = procedure.parse(skupstina.fetch(procedure.PAGE).decode("utf-8", "replace"))
    out = Path(args.out)
    store = jsonfile.load(out, {})
    today = dt.datetime.now(dt.timezone.utc).date().isoformat()
    before = {k for k, b in (store.get("bills") or {}).items() if b["last_seen"] == store.get("fetched")}
    store = procedure.merge(store, found, today)
    now = {b.pdf for b in found}
    jsonfile.save(out, store, "bills")
    print(f"bills in procedure: {len(found)}, new: {len(now - before)}, no longer listed: {len(before - now)}")
    return 0


def votes(args) -> int:
    """Read every roll call in data/index.json not read yet, into data/votes/<sitting>.json."""
    index = json.loads(Path(args.index).read_text(encoding="utf-8"))
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    read = failed = 0
    problems: list[str] = []
    for url, sitting in sorted(index["sittings"].items(), key=lambda kv: kv[1]["listed"]):
        if not sitting["votes"]:
            continue
        path = out_dir / f"{sitting_id(url)}.json"
        store = jsonfile.load(path, {})
        store.update({"sitting": url, "title": sitting["title"]})
        store.setdefault("pdfs", {})
        store.setdefault("votes", {})
        changed = False
        for item, pdf in sitting["votes"]:
            again = args.again or (args.reread and args.reread in urllib.parse.unquote(pdf))
            if pdf in store["pdfs"] and not again:
                continue
            if args.limit and read >= args.limit:
                break
            try:
                body = skupstina.fetch(pdf)
            except skupstina.FetchError as e:
                failed += 1
                print(f"  failed {urllib.parse.unquote(pdf)}: {e}")
                continue
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete_on_close=False) as f:  # closed first, as above
                f.write(body)
                f.close()
                found = rollcall.read(f.name)
            for key in [k for k in store["votes"] if k.split("#")[0] == pdf]:
                del store["votes"][key]
            # A sitting listed without a day can be another convocation's (the Eleventh's first, on the Tenth's
            # page, 17 Nov 2026): a roll call outside the convocation's dates is not its own.
            if any(not skupstina.within(v.when or "", CONVOCATIONS[common.CONVOCATION]) for v in found):
                print(f"  another convocation's (by its day): {urllib.parse.unquote(pdf)}")
                found = [v for v in found if skupstina.within(v.when or "", CONVOCATIONS[common.CONVOCATION])]
            for i, v in enumerate(found):
                store["votes"][f"{pdf}#{i}"] = {
                    "when": v.when, "item": v.item, "kind": v.kind, "session": v.session,
                    "listed_as": item, "counts": v.count(), "problems": v.problems,
                    "rows": [[r.number, r.name, r.vote, r.club] for r in v.rows],
                }
                problems += [f"{urllib.parse.unquote(pdf)} #{i}: {p}" for p in v.problems]
            if not found:
                problems.append(f"{urllib.parse.unquote(pdf)}: no vote read")
            store["pdfs"][pdf] = hashlib.sha256(body).hexdigest()
            read += 1
            changed = True
        if changed and (store["votes"] or path.exists()):
            jsonfile.save(path, store, "votes")
    total = sum(len(json.loads(p.read_text(encoding="utf-8"))["votes"]) for p in out_dir.glob("*.json"))
    print(f"PDFs read now: {read}, failed: {failed}; votes in the archive: {total}")
    for p in problems[:50]:
        print(f"  problem: {p}")
    return 1 if failed and not read else 0


def unread(args) -> int:
    """The roll calls the sittings' index lists and no file of votes has: one line each, nothing when all are read. A
    reading that a run skipped shows here (17-25 Nov 2026: the Fifteenth's, in silence)."""
    have: set[str] = set()
    for path in sorted((common.DATA / "votes").glob("*.json")):
        have |= set(jsonfile.load(path)["pdfs"])
    for sitting in jsonfile.load(common.DATA / "index.json", {}).get("sittings", {}).values():
        for item, pdf in sitting["votes"]:
            if pdf not in have:
                print(f"- saziv {common.CONVOCATION}: {latin(item)} ({urllib.parse.quote(urllib.parse.unquote(pdf), safe=':/')})")
    return 0


def download(args) -> int:
    """Save each URL into a folder, named by file_name: to add real roll calls to the tests."""
    to = Path(args.to)
    to.mkdir(parents=True, exist_ok=True)
    for url in args.urls:
        body = skupstina.fetch(url)
        (to / file_name(url)).write_bytes(body)
        print(f"{len(body):9,}  {file_name(url)}")
    return 0


def notes_of_debate(args) -> int:
    """The stenographic notes of the sittings where the laws with the most votes against (or the ones named) had
    their final vote, into data/<N>/transcripts/<sitting>.json: the agenda, every speech with the part of the debate
    it was given in, and the amendments announced. A sitting already read is skipped unless --again, or --more and its
    page links notes of a day the record lacks (the Assembly adds a sitting's days as they are ready)."""
    import hashlib
    from zailiprotiv.site import against_share
    store = json.loads(Path(args.laws).read_text(encoding="utf-8"))
    votes_ = all_votes(Path(args.votes))
    finals = [(law, votes_[law["final_vote"]]) for law in store["laws"].values()
              if law.get("final_vote") in votes_]
    if args.law:
        chosen = [(l, v) for l, v in finals if l.get("bill_file") in args.law or l["title"] in args.law]
    else:
        chosen = sorted((x for x in finals if x[1]["counts"]["protiv"]),
                        key=lambda x: (against_share(x[1]["counts"]), x[1]["counts"]["protiv"]), reverse=True)
        chosen = chosen[:args.top]
    sittings = sorted({v["sitting"] for _, v in chosen})
    if args.all:  # every sitting of the convocation the index knows, not only those of the contested laws
        sittings = sorted(json.loads(Path(args.index).read_text(encoding="utf-8"))["sittings"])
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    until = time.time() + args.minutes * 60 if args.minutes else None
    read = failed = 0
    for url in sittings:
        path = out / f"{sitting_id(url)}.json"
        if path.exists() and not args.again and not getattr(args, "more", False):
            continue
        if until and time.time() > until:  # the rest next run: what was read is kept
            print(f"time is up; {sum(1 for u in sittings if not (out / (sitting_id(u) + '.json')).exists())} sittings left for the next run")
            break
        try:
            page = skupstina.fetch(url).decode("utf-8", "replace")
            listed = transcripts.days(page, url)
            if path.exists() and not args.again:  # --more: only when a day's notes are new
                had = {d["url"] for d in json.loads(path.read_text(encoding="utf-8")).get("days", [])}
                if {d["url"] for d in listed} <= had:
                    continue
            if not listed:
                print(f"{url}: no stenographic notes linked")
                if args.all:  # written down as read and empty, so the next run does not ask again
                    jsonfile.save(path, {"sitting": url, "days": [], "agenda": {}, "amendments": [], "speeches": {}},
                                  "speeches")
                continue
            days, meta = [], []
            for d in sorted(listed, key=lambda d: d["day"]):
                body = skupstina.fetch(d["url"])
                try:
                    paras = transcripts.paragraphs(body)
                except transcripts.Unreadable as e:  # the day is left out, and the log says why
                    print(f"  {d['url']}: {e}")
                    paras = []
                days.append(paras)
                meta.append({**d, **transcripts.heading(paras), "sha256": hashlib.sha256(body).hexdigest()})
            found = transcripts.debate(days)
        except Exception as e:  # one sitting that cannot be fetched or read does not stop the others
            if not args.all:
                raise
            failed += 1
            print(f"{url}: not read ({type(e).__name__}: {e})")
            continue
        record = {"sitting": url, "days": meta, "agenda": {str(k): v for k, v in found["agenda"].items()},
                  "amendments": found["amendments"],
                  "speeches": {f"{i:05d}": s for i, s in enumerate(found["speeches"])}}
        jsonfile.save(path, record, "speeches")
        read += 1
        print(f"{path}: {len(meta)} days, {len(found['speeches'])} speeches, {len(found['amendments'])} amendments", flush=True)
    if args.all:
        print(f"transcripts: {read} sittings read, {failed} not read")
    return 0


def members_cmd(args) -> int:
    """The sitting MPs from the Assembly's list → data/<N>/members.json (members.py), for the newest convocation
    before its first roll call. A page with far fewer MPs than the file keeps the file."""
    from zailiprotiv import members
    from zailiprotiv.config import NEWEST
    conv = NEWEST
    page = skupstina.fetch(members.URL).decode("utf-8", "replace")
    found = members.read(page)
    by_group = {}
    for value, label in members.groups(page):  # each group's MPs: the page filtered by it (members.py)
        by_group[label] = members.read(skupstina.fetch(members.group_url(value)).decode("utf-8", "replace"))
        print(f"  {label}: {len(by_group[label])}")
    found = members.with_groups(found, by_group)
    path = common.ROOT / conv / "members.json"
    old = jsonfile.load(path, {"members": []})["members"]
    if len(found) < 200 or jsonfile.shrank(len(found), len(old)):
        print(f"members: {len(found)} read, {len(old)} kept; the file stays")
        return 0 if old else 1
    # Each MP's occupation, from the MP's own page at the Assembly: read once, then kept (members.py).
    had = {(m["name"], m["year"]): m["occupation"] for m in old if "occupation" in m}
    links, read_now = members.pages(page), 0
    for m in found:
        if (m["name"], m["year"]) in had:
            m["occupation"] = had[(m["name"], m["year"])]
        elif m["name"] in links:
            try:
                m["occupation"] = members.occupation(skupstina.fetch(links[m["name"]]).decode("utf-8", "replace"))
                read_now += 1
            except skupstina.FetchError as e:  # tried again at the next run
                print(f"  {m['name']}: {e}")
    print(f"members: occupations read now: {read_now}, known: {sum('occupation' in m for m in found)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(members.dumps(dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(), found),
                    encoding="utf-8")
    print(f"members: {len(found)} MPs of convocation {conv}")
    return 0


def _government(get) -> None:
    """The newest convocation's decisions electing or dismissing the Government's members (vlada.py), those not in
    data/vlada.json yet; one that can't be read is named and left for the next reading."""
    from zailiprotiv import bills, vlada
    from zailiprotiv.config import NEWEST
    path = common.ROOT / "vlada.json"
    old = jsonfile.load(path, {}).get("decisions", [])
    have = {d["url"] for d in old}
    new = []
    for title, url in vlada.decisions(get(vlada.LISTS[NEWEST])) if NEWEST in vlada.LISTS else []:
        url = url.replace(" ", "%20")
        if url in have:
            continue
        try:
            with tempfile.TemporaryDirectory() as tmp:
                pdf = os.path.join(tmp, "odluka.pdf")
                with open(pdf, "wb") as f:
                    f.write(skupstina.fetch(url))
                got = vlada.parse(bills.text_of(pdf))
        except Exception as exc:  # a scan, or a wording not met before: for a person to look at
            print(f"vlada: not read: {title} ({url}): {exc}")
            continue
        if got:
            new.append({**got, "title": title, "url": url})
        else:
            print(f"vlada: not read: {title} ({url})")
    if new:
        path.write_text(vlada.dumps(vlada.merge(old, new)), encoding="utf-8")
    print(f"vlada: {len(new)} new decisions, {len(old) + len(new)} in all")


def offices_cmd(args) -> int:
    """Who holds which office in the newest convocation (the Speaker, the deputy Speakers, the groups' chairs, the
    committees, the delegations) → data/<N>/offices.json, and the Assembly's news → data/vesti.json (offices.py). The
    committees' and delegations' own pages are read when their lists changed (a body, or its number of members), when
    a relevant news item is new, or once a week (once a day while a body's page gives nobody); an earlier
    convocation's (offices.ARCHIVE) once. With --unread, only what the kept file shows was not read: nothing is asked."""
    from zailiprotiv import offices
    from zailiprotiv.config import NEWEST
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    if args.unread:
        for line in offices.unread(jsonfile.load(common.ROOT / NEWEST / "offices.json", {}), now):
            print(line)
        return 0
    today = now.date().isoformat()

    def get(url):
        return skupstina.fetch(url).decode("utf-8", "replace")

    news_path = common.ROOT / "vesti.json"
    old_news = jsonfile.load(news_path, {"items": []})["items"]
    found_news = offices.news(get(offices.NEWS))
    items, fresh = offices.merge_news(old_news, found_news, today)
    if found_news:
        news_path.write_text(offices.dumps_news(now.isoformat(), items), encoding="utf-8")
    print(f"news: {len(found_news)} listed, {len(items) - len(old_news)} new, {len(fresh)} relevant new")
    for x in fresh:
        print(f"  relevant: {x['title']} ({x['url']})")
    if fresh and os.environ.get("GITHUB_STEP_SUMMARY"):  # on the run's page, for whoever looks at it
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write("### Nove vesti Skupštine o izboru i funkcijama\n\n"
                    + "".join(f"- [{x['title']}]({x['url']})\n" for x in fresh) + "\n")

    def read_parts(bodies):
        return [(t, url, offices.members(get(url))) for t, url in bodies]  # named as the list names it

    for conv, pages in offices.ARCHIVE.items():  # an earlier convocation's: its archive doesn't change
        path = common.ROOT / conv / "offices.json"
        if path.exists() or not path.parent.exists():  # a convocation the site doesn't cover isn't asked for
            continue
        bodies = {k: offices.parts(get(u), u) for k, u in pages.items()}
        found = offices.offices_of(speaker=None, vice=[], chairs=[], committees=read_parts(bodies["committees"]),
                                   delegations=read_parts(bodies["delegations"]), sources={})
        if found:
            path.write_text(offices.dumps(now.isoformat(), [{**o, "since": ""} for o in found], now.isoformat()),
                            encoding="utf-8")
        print(f"offices: {len(found)} in convocation {conv}'s archive")
    # The Speakers and deputies of every convocation, with their days (one page; 23 Nov 2026): an earlier one's are
    # added to its file, the newest's get the day they took office.
    past = offices.history(get(offices.HISTORY))
    for conv in offices.ARCHIVE:
        path = common.ROOT / conv / "offices.json"
        if past and path.exists():
            kept = json.loads(path.read_text(encoding="utf-8"))
            rows = offices.with_history([o for o in kept["offices"] if not o.get("dated")], past, conv)
            if rows != kept["offices"]:
                path.write_text(offices.dumps(kept["fetched"], rows, kept["parts_read"]), encoding="utf-8")

    conv = NEWEST
    path = common.ROOT / conv / "offices.json"
    old = jsonfile.load(path, {"offices": [], "parts_read": ""})
    sources = {"speaker": offices.SPEAKER, "vice": offices.VICE, "group": offices.GROUP_CHAIRS}
    speaker = offices.person(get(offices.SPEAKER))
    vice, chairs = offices.blocks(get(offices.VICE)), offices.blocks(get(offices.GROUP_CHAIRS))
    lists = {k: (u, get(u)) for k, u in (("committee", offices.COMMITTEES), ("delegation", offices.DELEGATIONS))}
    bodies = {k: offices.parts(page, u) for k, (u, page) in lists.items()}
    said = {}  # every body listed, with the number of members the list gives (0: none given)
    for k, (u, page) in lists.items():
        many = offices.numbers(page, u)
        said.update({url: many.get(url, 0) for _, url in bodies[k]})
    last = dt.datetime.fromisoformat(old["parts_read"]) if old.get("parts_read") else None
    missed = old.get("unread", {})
    again = (fresh or last is None or said != old.get("listed")
             or (now - last).total_seconds() > (offices.DAY if missed else offices.WEEK))
    if again:
        parts = {k: read_parts(bodies[k]) for k in bodies}
        missed = {url: said[url] for k in parts for _, url, got in parts[k] if said[url] and not got}
        for k in parts:
            for t, url, got in parts[k]:
                n = sum(m["role"] != "заменик члана" for m in got)  # the committees' lists count no deputies
                if n != said[url]:
                    print(f"  {t}: {n} read, {said[url]} listed ({url})")
        parts = {k: offices.keep_unread(old["offices"], said, parts[k], k) for k in parts}
        read_at = now.isoformat()
    else:  # the committees and delegations as last read
        parts = {k: [] for k in bodies}
        for o in old["offices"]:
            if o["kind"] in parts:
                body = next((p for p in parts[o["kind"]] if p[1] == o["source"]), None)
                if not body:
                    body = (o["body"], o["source"], [])
                    parts[o["kind"]].append(body)
                body[2].append({k: o[k] for k in ("name", "role", "group") if k in o})
        read_at = old["parts_read"]
    if again:
        _government(get)
    found = offices.offices_of(speaker=speaker, vice=vice, chairs=chairs, committees=parts["committee"],
                               delegations=parts["delegation"], sources=sources)
    if not found and old["offices"]:
        print(f"offices: none read, {len(old['offices'])} kept; the file stays")
        return 1
    found = offices.with_history(offices.keep_since(old["offices"], found, today), past, conv)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(offices.dumps(now.isoformat(), found, read_at, said, missed), encoding="utf-8")
    by = {}
    for o in found:
        by[o["kind"]] = by.get(o["kind"], 0) + 1
    print(f"offices: convocation {conv}: " + ", ".join(f"{k} {n}" for k, n in by.items())
          + ("" if again else " (committees and delegations as last read)"))
    return 0


def mp_years_cmd(args) -> int:
    """The year of birth of every MP from the Assembly's archive of convocations → data/mp_years.json, and the check:
    a name whose year differs between convocations is two people (split by hand in data/mp_splits.json)."""
    from zailiprotiv import mp_years, mps
    mps.load_aliases(common.ROOT / "mp_aliases.json")
    pages, todo, listed = {}, [mp_years.START], {}
    while todo:  # the start page links the archive's other pages
        url = todo.pop()
        if url in pages:
            continue
        rows, links = mp_years.parse(skupstina.fetch(url).decode("utf-8", "replace"))
        pages[url] = rows
        todo += [u for u in links if u not in pages and mp_years.convocation(u)]
    for url, rows in pages.items():
        conv = mp_years.convocation(url)
        if conv and rows:
            listed[conv] = rows
            print(f"convocation {conv}: {len(rows)} MPs listed ({url})")
    if not listed:
        print("no archive page read")
        return 1
    seated = {}
    for conv in listed:
        keys = set()
        for f in sorted((common.ROOT / conv / "votes").glob("*.json")):
            for v in json.loads(f.read_text(encoding="utf-8"))["votes"].values():
                keys |= {mps.key(mps.split(r[1], conv)) for r in v["rows"]}
        seated[conv] = keys
    found = mp_years.check(listed, seated)
    jsonfile.save(common.ROOT / "mp_years.json", {"check": found, "listed": listed}, "listed")
    print(f"\nthe same name, another year of birth ({len(found['differ'])}):")
    for d in found["differ"]:
        print(f"  {d['key']}: " + ", ".join(f"{c}: {'/'.join(map(str, y))}" for c, y in d["years"].items()))
    print(f"\none name twice in one convocation ({len(found['twice'])}):")
    for t in found["twice"]:
        print(f"  {t['convocation']}: " + "; ".join(f"{r['name']} {r['party']} {r['place']} {r['year']}" for r in t["rows"]))
    print("\non the roll calls, not in the archive's list (left mid-term, or spelled otherwise):")
    for conv, keys in sorted(found["missing"].items(), key=lambda c: int(c[0])):
        print(f"  {conv}: {len(keys)}: " + ", ".join(keys[:40]) + (" …" if len(keys) > 40 else ""))
    return 0


def poslovnik_cmd(args) -> int:
    """The Rules of Procedure from the Assembly's consolidated text into data/poslovnik/ (poslovnik.py): a new version
    only when the articles' text changed. Asked at most once a day (index.json's "provereno")."""
    from zailiprotiv import poslovnik
    folder = common.ROOT / "poslovnik"
    today = dt.date.today().isoformat()
    index_path = folder / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {}
    if index.get("provereno") == today and not args.again:
        print("poslovnik: checked today already")
        return 0
    doc = poslovnik.parse(skupstina.fetch(poslovnik.PAGE).decode("utf-8", "replace"))
    if len(doc["clanovi"]) < 250:  # a page that came out short: keep what is there
        print(f"::warning::poslovnik: only {len(doc['clanovi'])} articles read; nothing kept")
        return 0
    written = poslovnik.store(folder, doc, today)
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["provereno"] = today
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"poslovnik: {len(doc['clanovi'])} articles, {len(doc['glave'])} chapters; " + (f"new version {written}" if written else "unchanged"))
    return 0


def photos_cmd(args) -> int:
    """MPs' portraits from the Assembly's list of MPs into data/photos/; only those not there yet are downloaded."""
    from zailiprotiv import photos
    found = photos.parse(skupstina.fetch(photos.PAGE).decode("utf-8", "replace"))
    folder = common.ROOT / "photos"
    folder.mkdir(parents=True, exist_ok=True)
    index_file = folder / "index.json"
    index = jsonfile.load(index_file, {})
    new = 0
    for number, mp in sorted(found.items()):
        k, name = photos.key(mp["name"]), f"{number}.jpg"
        if index.get(k, {}).get("source") == mp["src"] and (folder / name).exists():
            continue
        try:
            data = skupstina.fetch(mp["src"])
        except skupstina.FetchError as e:
            print(f"  {mp['name']}: {e}")
            continue
        if data[:2] != b"\xff\xd8":  # not a JPEG: a placeholder or an error page
            continue
        (folder / name).write_bytes(data)
        index[k] = {"file": name, "source": mp["src"], "page": mp["page"]}
        new += 1
    index_file.write_text(json.dumps(index, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"portraits listed: {len(found)}, new: {new}, kept: {len(index)}")
    return 0
