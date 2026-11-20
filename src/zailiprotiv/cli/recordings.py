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
    placed = govor.place(speeches, govor.heard(Path(args.heard), day_files))
    # Each speaker as the site names them: the newest convocation's list of MPs, else the name as the notes give it.
    members = {mps.key(m["name"]): m for m in json.loads((conv_dir / "members.json").read_text(encoding="utf-8"))["members"]}
    known = {}
    for f in list((conv_dir / "snimak").glob("*.json")) + list((conv_dir / "uzivo").glob("*.json")):
        for t in json.loads(f.read_text(encoding="utf-8")).get("govori", []):
            if t.get("adresa"):
                known.setdefault(mps.key(cyr(" ".join(t["ime"].split(" ", 1)[::-1]))), t)

    def who(speaker: str) -> dict:
        k = mps.key(speaker)
        if k in known:
            t = known[k]
            return {"ime": t["ime"], "adresa": t["adresa"], "grupa": t.get("grupa", ""), "uloga": t.get("uloga", "")}
        words = translit.latin(speaker).title().split()
        name = " ".join(words[-1:] + words[:-1])
        m = members.get(k)
        return {"ime": name, "adresa": site_slug(name, 60) if m else "", "grupa": translit.latin(m["group"]) if m else "",
                "uloga": translit.latin(m["group"]) if m else ""}

    kept = jsonfile.load(conv_dir / "arhiva.json", {})
    record_path = conv_dir / "uzivo" / f"{args.day}.json"
    record = jsonfile.load(record_path, {}).get("govori", [])
    seen = [(mps.key(cyr(" ".join(t["ime"].split(" ", 1)[::-1]))), t["od"]) for t in record if t.get("okvira", 0) >= 2]
    files = []
    for url in day_files:
        if "od" in kept.get(url, {}):
            files.append({"url": url, "od": kept[url]["od"], "kako": "arhiva.json"})
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
           "datoteke": [{"url": f["url"], "od": f["od"], "trajanje": int(kept.get(f["url"], {}).get("trajanje") or 0)}
                        for f in files if f["od"] is not None]}
    if args.dry_run:
        return 0
    path = conv_dir / "snimak" / f"{args.day}.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {path.relative_to(common.ROOT.parent).as_posix()}")
    return 0


def glas_dan_cmd(args) -> int:
    """A sitting day with no notes yet, from captions and voices (govor.voice_day; 20 Nov 2026): the live record's
    turns the caption gave, and where there were none, the stretches ko.py named by voice (args.stretches, written
    in the analysis image: {"files": [{"url", "trajanje"}], "stretches": {url: [[address, from, to, likeness]]},
    "known": {url: start}}). Each file's clock from `known` or from captions read in passing (govor.clock); a file
    with neither is reported and its stretches left out. Writes data/<N>/snimak/<day>.json unless the day has been
    read from its notes."""
    from zailiprotiv import govor, translit
    conv_dir = common.ROOT / common.CONVOCATION
    path = conv_dir / "snimak" / f"{args.day}.json"
    if path.exists() and json.loads(path.read_text(encoding="utf-8")).get("izvor") == "govor":
        print(f"glas-dan {args.day}: read from the notes already; the notes win")
        return 0
    data = json.loads(Path(args.stretches).read_text(encoding="utf-8"))
    record = json.loads((conv_dir / "uzivo" / f"{args.day}.json").read_text(encoding="utf-8"))
    rec = record.get("govori", [])
    files = data["files"]
    starts = govor.clock(files, data["stretches"], rec, data.get("known", {}))
    for f in files:
        print(f"  {f['url'].rsplit('/', 1)[1]}: {starts.get(f['url'], ('?', 'not placed'))}")
    named = {}
    for p in list((conv_dir / "snimak").glob("*.json")) + list((conv_dir / "uzivo").glob("*.json")):
        if p == path:  # not the file this writes: a name it got wrong would come back
            continue
        for t in json.loads(p.read_text(encoding="utf-8")).get("govori", []):
            if t.get("adresa"):
                named.setdefault(t["adresa"], {k: t.get(k, "") for k in ("ime", "adresa", "grupa", "uloga")})

    from zailiprotiv.site import slug as site_slug
    for m in json.loads((conv_dir / "members.json").read_text(encoding="utf-8"))["members"]:
        # "Surname Given", as the site lists names, without the degree the list puts in some ("ДРЕЦУН мр МИЛОВАН")
        name = " ".join(w for w in translit.latin(m["name"]).split() if w.lower().rstrip(".") not in {"mr", "dr", "prof"}).title()
        group = translit.latin(m.get("group") or "")
        s = site_slug(name, 60)
        named.setdefault(s, {"ime": name, "adresa": s, "grupa": group, "uloga": group})
        if not named[s].get("uloga"):  # a caption read with no list line: the list the Assembly gives
            named[s] = {**named[s], "grupa": named[s].get("grupa") or group, "uloga": group}

    def who(address: str) -> dict:
        return named.get(address) or {"ime": address, "adresa": address, "grupa": "", "uloga": ""}

    # The captions' turns, by the live page's rule (okvira 2 or more: counted); then the voices where no caption was.
    caps = [{**t, "po": "potpis"} for t in rec if t.get("okvira", 0) >= 2]
    all_voiced = govor.voice_day(files, data["stretches"], starts, who)
    # A caption read with no list line under it, where the voice is surely someone else's, is a misreading (19 Nov
    # 2026, 20:58: "Vučić" in four frames while Petrašinović spoke): the voice stands.
    caps = [c for c in caps if c.get("uloga") or not any(
        v["adresa"] != c.get("adresa") and v["od"] <= c["od"] and c["do"] <= v["do"] for v in all_voiced)]
    for c in caps:  # a caption read with no list line: the list the Assembly gives
        if not c.get("uloga") and c.get("adresa") in named:
            c["uloga"] = named[c["adresa"]].get("uloga", "")
    voiced = [t for t in all_voiced
              if not any(c["od"] - 30 <= t["od"] <= c["do"] + 30 or t["od"] <= c["od"] <= t["do"] for c in caps)]
    for c in caps:  # the captions' turns get their place in the archive's files too
        for f in files:
            if f["url"] in starts and starts[f["url"]][0] <= c["od"] < starts[f["url"]][0] + f["trajanje"]:
                c.update(datoteka=f["url"], snimak=int(max(0, c["od"] - starts[f["url"]][0] - govor.LEAD)), video="")
    turns = sorted(caps + voiced, key=lambda t: t["od"])
    how = "; ".join(f"{f['url'].rsplit('/', 1)[1]}: {starts[f['url']][1]}" for f in files if f["url"] in starts)
    out = {"dan": args.day, "izvor": "glas", "napomena": govor.VOICE_NOTE + f"Sat delova snimka: {how}.",
           "pokriveno": [{"od": int(starts[f["url"]][0]), "do": int(starts[f["url"]][0] + f["trajanje"])}
                         for f in files if f["url"] in starts],
           "govori": turns,
           "datoteke": [{"url": f["url"], "od": int(starts[f["url"]][0]), "trajanje": int(f["trajanje"])}
                        for f in files if f["url"] in starts]}
    print(f"glas-dan {args.day}: {len(caps)} turns by caption, {len(voiced)} by voice, "
          f"{sum(t['do'] - t['od'] for t in voiced) // 60} min by voice")
    if not args.dry_run:
        path.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"wrote {path.as_posix()}")
    return 0


def prepis_cmd(args) -> int:
    """An automatic transcript of a sitting day's speeches from the archive's recording (prepis.py; Whisper)."""
    from zailiprotiv import prepis
    prepis.run(common.ROOT, common.CONVOCATION, args.day, model=args.model, minutes=args.minutes)
    return 0
