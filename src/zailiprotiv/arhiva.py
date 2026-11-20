"""Each sitting day's recording in the Assembly's archive, lined up with the live page's record of who spoke when.

The broadcaster's archive (videos.py) holds a day in parts, MP4 files that start where the broadcast was when each
was cut, a time no page gives. The live page's record (uzivo.py) says, by the clock, from when to when each speaker's
name was in the caption. So a few frames of a file, their captions read the way the live page reads them, place the
file on the clock: the start that puts the most of the names read inside the turns of those speakers. With it, every
turn of the day gets its place in a file of the archive (`datoteka`, `snimak`), and the day's file in
data/<N>/snimak/ is made from the record, or a day read by hand gets the places it lacked (18 Nov 2026: the YouTube
video of the broadcast goes private once it is over, so the archive is where a turn can be watched).

The same rule for every file and every speaker; a file whose frames don't agree on one start, or agree on a wide
range of them (all in one long speech), gets none rather than a guess, and is tried again in a later run (at most TRIES
times). The record's clock is the service's: it sees the broadcast some 15-20 seconds late, so a file is placed on that
clock, which is also the clock of the turns it is linked from; a day read by hand from the YouTube video (17 and 18 Nov
2026, its own clock) was lined up by hand, and its entries in arhiva.json say so.
"""
from __future__ import annotations

import io
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

LIVE = Path(__file__).resolve().parents[2] / "live"  # the live page's own reading of captions (live/uzivo)
SLACK = 6  # seconds: a frame read a little before or after the turn the record has
STEP, FIRST, LAST = 30, 20, 3600  # frames read: every STEP seconds, from FIRST, up to LAST into a file
ENOUGH = 10  # named frames: enough to settle a start
SUPPORT, SHARE = 4, 0.6  # a start needs this many named frames inside their speakers' turns, and this share of them
TRIES = 3
LEAD = 5  # a turn's place in a file: this many seconds before its first frame, as everywhere on the site
MERGE = 120  # one speaker's turns in a row this close are one
WORKERS = 6  # frames read at once: each is an ffmpeg waiting on the network


def offset(samples: list[tuple[float, str]], turns: list[tuple[str, float, float]]) -> tuple[float, int] | None:
    """The clock time (unix) at which a file starts, from frames read in it, [(seconds into the file, speaker key)],
    and the day's turns, [(speaker key, from, to)]: the start that puts the most frames inside a turn of their speaker,
    the middle of the range of such starts. None when too few frames agree."""
    by_key: dict[str, list[tuple[float, float]]] = {}
    for k, a, b in turns:
        by_key.setdefault(k, []).append((a, b))
    named = [(t, k) for t, k in samples if k in by_key]
    if not named:
        return None
    candidates = sorted({a - t - SLACK for t, k in named for a, _ in by_key[k]}
                        | {b - t + SLACK for t, k in named for _, b in by_key[k]})

    def fits(o: float) -> int:
        return sum(any(a - SLACK <= o + t <= b + SLACK for a, b in by_key[k]) for t, k in named)

    scored = [(fits(o), o) for o in candidates]
    best = max(n for n, _ in scored)
    if best < SUPPORT or best < SHARE * len(named):
        return None
    tops = [o for n, o in scored if n == best]
    if max(tops) - min(tops) > 2 * STEP:  # the frames fit a wide range of starts (one long speech): no place
        return None
    return (min(tops) + max(tops)) / 2, best


def refine(start: float, got: list[tuple[float, str]], turns: list[tuple[str, float, float]], look) -> float:
    """The start to a few seconds: where two frames read in a row name different speakers, the frame where the second
    name comes up is looked for between them (look(t) → speaker key), and put at the beginning of that speaker's turn
    in the record. Unchanged when no such pair settles it."""
    begins: dict[str, list[float]] = {}
    for k, a, _ in turns:
        begins.setdefault(k, []).append(a)
    ordered = sorted(got)
    for (t1, k1), (t2, k2) in zip(ordered, ordered[1:]):
        if k1 == k2 or t2 - t1 > 2 * STEP or k2 not in begins:
            continue
        lo, hi = t1, t2  # the second name's first frame is after lo and at hi
        while hi - lo > 2:
            mid = (lo + hi) / 2
            if look(mid) == k2:
                hi = mid
            else:  # the first name still, or no caption (the chair speaks between them)
                lo = mid
        near = min(begins[k2], key=lambda a: abs(a - (start + hi)))
        if abs(near - hi - start) <= STEP:
            return near - hi
    return start


# --- reading a file ----------------------------------------------------------------------------------------------

def duration(url: str) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", url],
                         capture_output=True, text=True, timeout=120)
    return float(out.stdout.strip())


def frame(url: str, t: float):
    """One frame, t seconds into a file read over the network (ffmpeg asks only for the bytes around it)."""
    from PIL import Image
    out = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", url, "-frames:v", "1",
                          "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True, timeout=120)
    if out.returncode or not out.stdout:
        return None
    return Image.open(io.BytesIO(out.stdout)).convert("RGB")


def reader(names: list[tuple[str, str]]):
    """A function from a frame to the speaker key its caption names, among the day's speakers [(name, slug)]: the live
    page's own reading (needs numpy, pytesseract and Tesseract's Serbian)."""
    if str(LIVE) not in sys.path:
        sys.path.insert(0, str(LIVE))
    from uzivo import config
    from uzivo.caption import who
    from uzivo.names import Person, Roster, person_key
    from uzivo.ocr import caption
    roster = Roster([Person(person_key(n), n, s) for n, s in names])
    keys = {person_key(n) for n, _ in names}

    def read(img) -> str | None:
        p = who(caption(img), roster, config.MATCH)
        return p.key if p and p.key in keys else None
    return read


def _named(grab, url: str, read, t: float):
    """A frame's speaker key (or None), or the exception reading it raised, kept to be raised in its turn."""
    try:
        img = grab(url, t)
        return read(img) if img is not None else None
    except Exception as exc:  # noqa: BLE001: raised again by samples, where the serial reading would have met it
        return exc


def samples(url: str, read, dur: float, *, grab=None, workers: int = WORKERS) -> list[tuple[float, str]]:
    """The frames read every STEP seconds and the speakers their captions name, until ENOUGH are named. Frames are
    read `workers` at a time (each an ffmpeg over the network, waiting mostly), and taken in order exactly as one at a
    time would take them: the frames of a batch after the one that made ENOUGH are dropped, and an error is raised
    only when the reading in order reaches its frame."""
    grab = grab or frame
    times = []
    t = FIRST
    while t < min(dur, LAST):
        times.append(t)
        t += STEP
    got: list[tuple[float, str]] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for i in range(0, len(times), workers):
            batch = times[i:i + workers]
            for t, k in zip(batch, pool.map(lambda t: _named(grab, url, read, t), batch)):
                if len(got) >= ENOUGH:
                    return got
                if isinstance(k, Exception):
                    raise k
                if k:
                    got.append((t, k))
            if len(got) >= ENOUGH:
                break
    return got


# --- the day's file ------------------------------------------------------------------------------------------------

def _key(name: str) -> str:
    if str(LIVE) not in sys.path:
        sys.path.insert(0, str(LIVE))
    from uzivo.names import person_key
    return person_key(name)


def turns_of(record: dict) -> list[dict]:
    """The record's turns as a day's file holds them: those named in two frames or more, one speaker's turns in a row
    taken as one."""
    out: list[dict] = []
    for t in record.get("govori", []):
        if t.get("okvira", 0) < 2:
            continue
        last = out[-1] if out else None
        if last and last["ime"] == t["ime"] and t["od"] - last["do"] <= MERGE:
            last["do"] = max(last["do"], t["do"])
            last["okvira"] += t["okvira"]
            last["uloga"] = last["uloga"] or t.get("uloga", "")
            continue
        out.append({"ime": t["ime"], "adresa": t.get("adresa", ""), "grupa": t.get("grupa", ""),
                    "uloga": t.get("uloga", ""), "od": int(t["od"]), "do": int(t["do"]), "okvira": t["okvira"],
                    "video": "", "snimak": None})
    return out


def place(turns: list[dict], files: list[dict]) -> int:
    """Each turn's place in the archive file that holds its start, for turns that have none yet; how many got one."""
    n = 0
    for t in turns:
        if t.get("datoteka"):
            continue
        start = t["od"] - LEAD
        for f in files:
            if f["od"] <= start < f["od"] + f["trajanje"] or f["od"] <= t["od"] < f["od"] + f["trajanje"]:
                t["datoteka"], t["snimak"], t["video"] = f["url"], int(max(0, start - f["od"])), ""
                n += 1
                break
    return n


NOTE = ("Iz zapisa stranice „Ko sada govori“ (potpis u prenosu, kadar na oko 5 sekundi), isto pravilo za svakog "
        "govornika: govor traje od prvog do poslednjeg kadra s imenom govornika u potpisu; uzastopni govori istog "
        "govornika spojeni, govori pročitani u samo jednom kadru izostavljeni. Predsedavajući nema potpis i nije u "
        "spisku. 'datoteka' je snimak dana u arhivi videonet.co.rs, poravnat sa zapisom po imenima pročitanim u "
        "njegovim kadrovima; 'snimak' je mesto u njemu u sekundama, pet sekundi pre prvog kadra. Automatsko čitanje "
        "može da pogreši.")


def run(root: Path, conv: str, *, now: str | None = None, read_frames=None, probe=duration) -> list[str]:
    """Line up the archive's files with the live page's records, for every day that has both, and write each day's
    file. read_frames(url, names, dur) → samples, and probe(url) → seconds, are for the tests. Returns what changed."""
    videos = root / conv / "videos.json"
    if not videos.exists():
        return []
    days = json.loads(videos.read_text(encoding="utf-8")).get("days", {})
    kept_path = root / conv / "arhiva.json"
    kept = json.loads(kept_path.read_text(encoding="utf-8")) if kept_path.exists() else {}
    now = now or datetime.now(timezone.utc).isoformat(timespec="seconds")
    changed = []
    for day, parts in sorted(days.items()):
        rec_path = root / conv / "uzivo" / f"{day}.json"
        if not rec_path.exists():
            continue
        record = json.loads(rec_path.read_text(encoding="utf-8"))
        rec_turns = [(_key(t["ime"]), t["od"], t["do"]) for t in record.get("govori", []) if t.get("okvira", 0) >= 2]
        names = sorted({(t["ime"], t.get("adresa", "")) for t in record.get("govori", []) if t.get("okvira", 0) >= 2})
        if not rec_turns:
            continue
        for p in parts:
            url = p["url"]
            k = kept.get(url, {})
            if "od" in k or k.get("pokusaja", 0) >= TRIES:
                continue
            began = time.monotonic()
            try:
                dur = probe(url)
                if read_frames:
                    got = read_frames(url, names, dur)
                    found = offset(got, rec_turns)
                else:
                    read = reader(names)
                    got = samples(url, read, dur)
                    found = offset(got, rec_turns)
                    if found:
                        look = lambda t: (lambda img: read(img) if img is not None else None)(frame(url, t))
                        found = (refine(found[0], got, rec_turns, look), found[1])
            except Exception as exc:  # a file not there yet, a network hiccup, no OCR: tried again later
                print(f"::notice::arhiva {url}: {exc}")
                found, got, dur = None, [], 0
            print(f"arhiva {url}: {len(got)} frames named, start {found[0] if found else None}, "
                  f"{time.monotonic() - began:.0f} s")
            if found:
                kept[url] = {"od": int(round(found[0])), "trajanje": int(dur), "kadrova": len(got), "slaze_se": found[1]}
            else:
                kept[url] = {"pokusaja": k.get("pokusaja", 0) + 1, "kadrova": len(got), "provereno": now}
            changed.append(url)
        files = [{"url": p["url"], "od": kept[p["url"]]["od"], "trajanje": kept[p["url"]]["trajanje"]}
                 for p in parts if "od" in kept.get(p["url"], {})]
        if not files:
            continue
        path = root / conv / "snimak" / f"{day}.json"
        by_hand = path.exists() and json.loads(path.read_text(encoding="utf-8")).get("izvor") != "uzivo"
        if by_hand:  # a day read by hand from the recording: only the places it lacks
            out = json.loads(path.read_text(encoding="utf-8"))
            had = {f["url"] for f in out.get("datoteke") or []}
            n = place(out["govori"], files)
            out["datoteke"] = sorted((out.get("datoteke") or []) + [f for f in files if f["url"] not in had],
                                     key=lambda f: f["od"])
            if not n and had >= {f["url"] for f in files}:
                continue
        else:  # written from the record each time: it grows while the day's sitting lasts
            turns = turns_of(record)
            place(turns, files)
            out = {"dan": day, "izvor": "uzivo", "napomena": NOTE, "pokriveno": record.get("pokriveno", []),
                   "govori": turns, "datoteke": sorted(files, key=lambda f: f["od"])}
        text = json.dumps(out, ensure_ascii=False, indent=1) + "\n"
        if path.exists() and path.read_text(encoding="utf-8") == text:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        changed.append(path.relative_to(root).as_posix())
    if changed:
        kept_path.write_text(json.dumps(kept, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return changed
