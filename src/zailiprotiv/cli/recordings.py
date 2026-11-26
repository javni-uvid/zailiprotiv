"""The broadcasts and recordings: the live service's records, the archive's files, who spoke when from the sound, the
automatic transcript."""

from __future__ import annotations

import datetime as dt
import json
import statistics
from pathlib import Path

from zailiprotiv import jsonfile, skupstina
from zailiprotiv.config import CONVOCATIONS

from zailiprotiv.cli import common


def videos_cmd(args) -> int:
    """The convocation's plenary recordings by day, from the broadcaster's archive page → data/<N>/videos.json."""
    from zailiprotiv import videos
    page = CONVOCATIONS[common.CONVOCATION].get("videos")
    if not page:
        print("no archive of recordings for this convocation")
        return 0
    found = videos.parse(skupstina.fetch(page).decode("utf-8", errors="replace"))
    days = videos.by_day(found)

    def exists(url: str) -> bool:  # a HEAD request: the file's headers, not the file
        import urllib.request
        from zailiprotiv.config import USER_AGENT
        try:
            req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.status == 200
        except OSError:
            return False

    for day in sorted(days)[-3:]:  # the latest days only: the archive adds a day's last parts within hours
        days[day] += videos.unlisted(days[day], exists)
    out = common.DATA / "videos.json"
    if out.exists() and jsonfile.shrank(len(days), len(jsonfile.load(out).get("days") or {})):
        print(f"::warning::videos: the archive gives {len(days)} days, fewer than the file; kept the file")
        return 0
    store = {"fetched": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(), "source": page,
             "days": days}
    out.parent.mkdir(parents=True, exist_ok=True)
    jsonfile.save(out, store, "days")
    print(f"recordings: {len(found)} on {len(days)} days")
    return 0


def uzivo_pull(args) -> int:
    """The live page's records of who spoke when (live/) → data/<N>/uzivo/<date>.json. The page runs on the
    maintainer's computer and may be off: then nothing changes and the run goes on."""
    from zailiprotiv import uzivo
    settings = jsonfile.load(common.ROOT / "settings.json", {})
    base = settings.get("live_page", "")
    if not base:
        print("no live_page in data/settings.json")
        return 0
    try:
        days = uzivo.pull(common.ROOT, base)
    except Exception as exc:  # the computer is off, or the page is down
        print(f"::notice::live records not taken: {exc}")
        days = None
    if days is not None:
        print(f"live records: {', '.join(days) or 'nothing new'}")
    try:  # a sitting on now, by the live page's reading: the site's bar (data/live.json)
        print(f"sitting on now (live page): {uzivo.live_mark(common.ROOT, base)}")
    except Exception as exc:
        (common.ROOT / "live.json").unlink(missing_ok=True)  # the page down says nothing of a sitting: the bar goes
        print(f"::notice::live state not read: {exc}")
    return 0


def arhiva_cmd(args) -> int:
    """The archive's recordings lined up with the live page's records (arhiva.py): each new file placed on the clock
    by the captions read in a few of its frames, and each sitting day's file in data/<N>/snimak/ written or given the
    places it lacked. Needs ffmpeg, Tesseract's Serbian, numpy and pytesseract; a day without them changes nothing."""
    from zailiprotiv import arhiva
    if args.waiting:
        for url in arhiva.waiting(common.ROOT, common.CONVOCATION):
            print(url)
        return 0
    changed = arhiva.run(common.ROOT, common.CONVOCATION)
    print(f"archive: {', '.join(changed) or 'nothing new'}")
    return 0


def govor_cmd(args) -> int:
    """Who spoke when on a sitting day, from the notes lined up with the recording written down word by word
    (govor.py; the words from live/uzivo/zvuk_dana.py in args.heard). Writes data/<N>/snimak/<day>.json; each file's
    start on the clock comes from data/<N>/arhiva.json, or else from the live page's record of that day (the
    speakers it read in captions), and a file with neither is reported and its turns left out."""
    from zailiprotiv import govor, mps, translit
    from zailiprotiv.cyrillic import cyr
    from zailiprotiv.site import slug as site_slug
    conv_dir = common.ROOT / common.CONVOCATION
    day_files = [p["url"] for p in sorted(json.loads((conv_dir / "videos.json").read_text(encoding="utf-8"))["days"]
                                          .get(args.day, []), key=lambda p: p["part"])]
    speeches = []
    for path in sorted((conv_dir / "transcripts").glob("*.json")):
        notes = json.loads(path.read_text(encoding="utf-8"))
        day_no = {d["day"] for d in notes.get("days", []) if d.get("listed_date") == args.day}
        speeches += [{"key": f"{path.stem}/{k}", **s} for k, s in sorted(notes.get("speeches", {}).items())
                     if s.get("day") in day_no]
    if not speeches or not day_files:
        print(f"govor {args.day}: {len(speeches)} speeches in the notes, {len(day_files)} files: nothing to do")
        return 1
    for s in speeches:
        if not s.get("chair") and govor.roll_call(s["text"]):
            s["chair"] = s["prozivka"] = True  # a vote read out by name is no speech
    words = govor.heard(Path(args.heard), day_files)
    placed = govor.place(speeches, words)
    # Beginnings Whisper missed, from the speaker's timer in the caption, read by hand (data/<N>/merac.json, 26 Nov 2026)
    readings = [r for r in jsonfile.load(conv_dir / "merac.json", {}).get("citanja", []) if r.get("dan") == args.day]
    placed = govor.timer_starts(placed, words, readings)
    # Each speaker as the site names them: the newest convocation's list of MPs, else the name as the notes give it.
    members = {mps.key(m["name"]): m for m in json.loads((conv_dir / "members.json").read_text(encoding="utf-8"))["members"]}
    known = {}
    for f in list((conv_dir / "snimak").glob("*.json")) + list((conv_dir / "uzivo").glob("*.json")):
        for t in json.loads(f.read_text(encoding="utf-8")).get("govori", []):
            if t.get("adresa"):
                known.setdefault(mps.key(cyr(" ".join(t["ime"].split(" ", 1)[::-1]))), t)

    def who(speaker: str) -> dict:
        k = mps.key(speaker)
        if k not in known and k not in members:  # misspelt in the notes: the one listed name near it
            k = govor.nearest(k, {**known, **members}) or k
        m = members.get(k)
        if k in known:
            t = known[k]
            # A day before the groups were formed gives none: the list of MPs' then (25 Nov 2026: Vjerica Radeta's 12
            # minutes of the 24th would have stood under no list, for the 17th).
            group = t.get("grupa", "") or ("" if t.get("uloga") or not m else translit.latin(m["group"]))
            return {"ime": t["ime"], "adresa": t["adresa"], "grupa": group, "uloga": t.get("uloga", "")}
        words = translit.latin(speaker).title().split()
        name = " ".join(words[-1:] + words[:-1])
        return {"ime": name, "adresa": site_slug(name, 60) if m else "", "grupa": translit.latin(m["group"]) if m else "",
                "uloga": translit.latin(m["group"]) if m else ""}

    kept = jsonfile.load(conv_dir / "arhiva.json", {})
    record_path = conv_dir / "uzivo" / f"{args.day}.json"
    record = jsonfile.load(record_path, {}).get("govori", [])
    seen = [(mps.key(cyr(" ".join(t["ime"].split(" ", 1)[::-1]))), t["od"]) for t in record if t.get("okvira", 0) >= 2]
    files = []
    for url in day_files:
        if "od" in kept.get(url, {}):
            files.append({"url": url, "od": kept[url]["od"], "kako": "arhiva.json", "delovi": kept[url].get("delovi")})
            continue
        # Every start the file could have by a speech placed in it and a turn of the same speaker in the live record;
        # the file's start is where most of them agree (within 30 s), from two speakers' speeches on.
        diffs = sorted(od - s["od"] for s in placed if s.get("datoteka") == url and not s.get("chair")
                       for key, od in seen if key == mps.key(s["speaker"]))
        good = max(([d for d in diffs if a <= d <= a + 30] for a in diffs), key=len, default=[])
        if len(good) >= 2:
            files.append({"url": url, "od": int(statistics.median(good)), "kako": f"zapis uživo, {len(good)} govora"})
        else:
            files.append({"url": url, "od": None, "kako": "nepoznato"})
    for f in files:
        n = sum(1 for s in placed if s.get("datoteka") == f["url"] and not s.get("chair"))
        print(f"  {f['url'].rsplit('/', 1)[1]}: start {f['od']} ({f['kako']}), {n} speeches placed")
    turns = [t for t in govor.day(placed, files, who) if t["od"] is not None]
    left = [s for s in placed if not s.get("chair") and "datoteka" not in s]
    print(f"govor {args.day}: {len(speeches)} speeches, {len(turns)} turns written, "
          f"{len(left)} speeches of MPs and guests with no place: {', '.join(sorted({s['speaker'] for s in left}))}")
    out = {"dan": args.day, "izvor": "govor", "napomena": govor.NOTE + (args.note or ""),
           "pokriveno": [{"od": min(t["od"] for t in turns), "do": max(t["do"] for t in turns)}] if turns else [],
           "govori": turns,
           # the chair's own stretches between turns, of CHAIR_CARD seconds or more: the role's, no one's time
           "predsedavajuci": govor.chair_stretches(placed, files, turns),
           "datoteke": [p for f in files if f["od"] is not None
                        for p in govor.stretches(f, int(kept.get(f["url"], {}).get("trajanje") or 0))]}
    if args.dry_run:
        return 0
    path = conv_dir / "snimak" / f"{args.day}.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {path.relative_to(common.ROOT.parent).as_posix()}")
    return 0


def tacnost_cmd(args) -> int:
    """How right the live page's record of who spoke when is (tacnost.py): each day that has the notes' speeches placed
    in its recording (snimak/<day>.json, "izvor": "govor") against the live record of that day, or against args.zapis
    (a record made by a rule being tried). Prints the score; changes nothing."""
    from zailiprotiv import tacnost
    conv_dir = common.ROOT / common.CONVOCATION
    days = [args.day] if args.day else sorted(f.stem for f in (conv_dir / "snimak").glob("*.json"))
    seen = 0
    for d in days:
        s = tacnost.day(conv_dir, d, Path(args.zapis) if args.zapis else None)
        if s or args.day:
            print(tacnost.told(d, s))
            seen += bool(s)
    return 0 if seen else 1


def glas_dan_cmd(args) -> int:
    """A sitting day with no notes yet, read from its recording (ko.named, 25 Nov 2026): each piece of its sound named by
    the captions the live service read, the chair's words giving the floor, or a known voice. args.folder holds the
    day's numbers and words (lice_glas.py, zvuk_dana.py); the voices are those of the turns of other days kept in
    args.uzorci. Each file's clock from arhiva.json or from captions read in passing (govor.clock); a file with neither
    is reported and left out. Writes data/<N>/snimak/<day>.json unless the day has been read from its notes;
    args.zapis writes the record there instead (to be scored: `zailiprotiv tacnost <day> --zapis`)."""
    from zailiprotiv import govor, ko, translit
    from uzivo import config as live_config, hronika  # ko.py puts live/ on the path
    from uzivo.names import Person, person_key
    from zailiprotiv.site import slug as site_slug
    conv_dir = common.ROOT / common.CONVOCATION
    path = conv_dir / "snimak" / f"{args.day}.json"
    if not args.zapis and path.exists() and json.loads(path.read_text(encoding="utf-8")).get("izvor") == "govor":
        print(f"glas-dan {args.day}: read from the notes already; the notes win")
        return 0
    folder, kept = Path(args.folder), jsonfile.load(conv_dir / "arhiva.json", {})
    rec = json.loads((conv_dir / "uzivo" / f"{args.day}.json").read_text(encoding="utf-8")).get("govori", [])
    urls = [p["url"] for p in sorted(json.loads((conv_dir / "videos.json").read_text(encoding="utf-8"))["days"]
                                     .get(args.day, []), key=lambda p: p["part"])]
    sound = {u: got for u in urls if (got := ko.load(folder, u, "glas")) is not None}
    if not sound:
        print(f"glas-dan {args.day}: no voices in {folder}")
        return 1

    # The voices known from other days: their turns that have a place in a file whose numbers are kept. Not those of a
    # day known from the live record or from this reading: some of its names are voices', which would teach themselves.
    other_days = [json.loads(d.read_text(encoding="utf-8")) for d in sorted((conv_dir / "snimak").glob("*.json"))
                  if d.stem != args.day and (not args.pre or d.stem < args.day)]
    spans = [s for d in other_days if d.get("izvor") not in ("uzivo", "glas") for s in ko.known_spans(d)]
    where = {url: next((Path(u) for u in args.uzorci if ko.load(Path(u), url, "glas") is not None), folder)
             for url in {s[1] for s in spans}}
    refs = ko.voices(spans, where.get)

    files = [{"url": u, "trajanje": kept.get(u, {}).get("trajanje") or float(got[0][-1]) + ko.WIN} for u, got in sound.items()]
    starts = govor.clock(files, {u: ko.stretches(*got, refs) for u, got in sound.items()}, rec,
                         {u: kept[u]["od"] for u in sound if "od" in kept.get(u, {})})
    for f in files:
        print(f"  {f['url'].rsplit('/', 1)[1]}: {starts.get(f['url'], ('?', 'not placed'))}")
    files = [f for f in files if f["url"] in starts]

    named, people = {}, []
    for p in list((conv_dir / "snimak").glob("*.json")) + list((conv_dir / "uzivo").glob("*.json")):
        if p == path:  # not the file this writes: a name it got wrong would come back
            continue
        for t in json.loads(p.read_text(encoding="utf-8")).get("govori", []):
            if t.get("adresa"):
                named.setdefault(t["adresa"], {k: t.get(k, "") for k in ("ime", "adresa", "grupa", "uloga")})
    for m in json.loads((conv_dir / "members.json").read_text(encoding="utf-8"))["members"]:
        # "Surname Given", as the site lists names, without the degree the list puts in some ("ДРЕЦУН мр МИЛОВАН")
        name = " ".join(w for w in translit.latin(m["name"]).split() if w.lower().rstrip(".") not in {"mr", "dr", "prof"}).title()
        group = translit.latin(m.get("group") or "")
        s = site_slug(name, 60)
        people.append(Person(person_key(name), name, s, group))
        named.setdefault(s, {"ime": name, "adresa": s, "grupa": group, "uloga": group})
        if not named[s].get("uloga"):  # a caption read with no list line: the list the Assembly gives
            named[s] = {**named[s], "grupa": named[s].get("grupa") or group, "uloga": group}

    def who(address: str) -> dict:
        return named.get(address) or {"ime": address, "adresa": address, "grupa": "", "uloga": ""}

    words = {f["url"]: [w for line in _lines(folder / (f["url"].rsplit("/", 1)[1].removesuffix(".mp4") + ".jsonl"))
                        for w in line.get("reci") or []] for f in files}

    def floor(url: str, a: float, b: float) -> str:
        hit = hronika.floor(" ".join(w for s, _, w in words[url] if a <= s < b), people, now_only=True)
        return hit[-1].slug if hit else ""

    # The captions' turns, by the live page's rule (okvira 2 or more: counted); of a caption that stands for seconds
    # only its first seconds are a caption seen. What the live service found by voice or the chair's words is no caption.
    caps = [_sitting(t, people) for t in rec
            if t.get("okvira", 0) >= 2 and t.get("adresa") and t.get("izvor") in (None, "potpis")]
    seen = [(t["adresa"], t["od"], min(t["do"], t["od"] + CAPTION_STANDS) if t.get("izvor") else t["do"]) for t in caps]
    got = ko.named([{"url": f["url"], "od": starts[f["url"]][0], "t": sound[f["url"]][0], "f": sound[f["url"]][1]} for f in files],
                   refs, seen, floor, live_config.VOICE_SKIP)
    by_file: dict[str, list] = {}
    for r in got:
        by_file.setdefault(r["datoteka"], []).append((r["adresa"], r["od"], r["do"], r["po"]))
    turns = govor.voice_day(files, by_file, starts, who)
    read = [(starts[f["url"]][0], starts[f["url"]][0] + f["trajanje"]) for f in files]
    turns += [{**{k: t.get(k, "") for k in ("ime", "adresa", "grupa", "uloga", "od", "do", "okvira")}, "video": "", "po": "potpis"}
              for t in caps if not any(a <= t["od"] < b for a, b in read)]  # a caption in a part whose sound was not read
    turns.sort(key=lambda t: t["od"])
    how = "; ".join(f"{f['url'].rsplit('/', 1)[1]}: {starts[f['url']][1]}" for f in files)
    out = {"dan": args.day, "izvor": "glas", "napomena": govor.VOICE_NOTE + f"Sat delova snimka: {how}.",
           "pokriveno": [{"od": int(a), "do": int(b)} for a, b in read], "govori": turns,
           "datoteke": [{"url": f["url"], "od": int(starts[f["url"]][0]), "trajanje": int(f["trajanje"])} for f in files]}
    print(f"glas-dan {args.day}: {len(refs)} voices known, {len(turns)} turns; minutes named by "
          + ", ".join(f"{k} {sum(r['do'] - r['od'] for r in got if r['po'] == k) / 60:.0f}" for k in ("potpis", "prepis", "glas")))
    target = Path(args.zapis) if args.zapis else path
    if not args.dry_run:
        target.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"wrote {target.as_posix()}")
    return 0


def _sitting(turn: dict, people: list) -> dict:
    """A caption's turn under the name of an MP not sitting, with a sitting list under it, as the sitting MP the name is
    near (25 Nov 2026: before the service had the new list, 18 Nov's Šoškić was read as a former MP, Stošić). By the live
    page's own matching; a minister or a guest has no list under the name and is left as read."""
    from uzivo import config as live_config
    from uzivo.names import Roster
    if any(p.slug == turn["adresa"] for p in people) or turn.get("uloga") not in {p.group for p in people}:
        return turn
    roster = Roster([p for p in people if p.group == turn["uloga"]])
    roster.current = frozenset(p.slug for p in roster.people)
    hit = roster.match(turn["ime"], live_config.MATCH)
    return {**turn, "ime": hit.name, "adresa": hit.slug, "grupa": hit.group} if hit else turn


CAPTION_STANDS = 40  # seconds: a caption that comes up at a turn's start only (24 Nov 2026) is of these (glas.LEARN_ON)


def _lines(f: Path) -> list[dict]:
    """The lines of a recording written down (zvuk_dana.py); none when it has not been."""
    return [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines() if x.strip()] if f.exists() else []


def prepis_cmd(args) -> int:
    """An automatic transcript of a sitting day's speeches from the archive's recording (prepis.py; Whisper)."""
    from zailiprotiv import prepis
    prepis.run(common.ROOT, common.CONVOCATION, args.day, model=args.model, minutes=args.minutes)
    return 0
