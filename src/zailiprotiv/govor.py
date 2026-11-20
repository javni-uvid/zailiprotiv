"""Who spoke when, from what was said: the Assembly's notes of a day lined up with that day's recording written down
word by word (20 Nov 2026: from the afternoon of 19 Nov the broadcast showed no speaker's caption, so the picture
could no longer say who was at the rostrum).

The notes say who spoke and what, in order, with no times; the recording written down by Whisper (live/uzivo/
zvuk_dana.py: each file of the archive, every word with its second) says when, but errs in words and knows no names.
So the notes' words are found in the written-down words: runs of ANCHOR words that occur once in each and stand in the
same order in both (the longest such chain), and each speech gets its place from the first and last of its runs.
A speech with fewer than MIN_ANCHORS runs gets no place rather than a guess. The same rule for every speaker; the
chair's speeches are lined up too (they hold the speeches between them in place) but are not listed, as everywhere.
"""
from __future__ import annotations

import bisect
import json
import re
import unicodedata
from pathlib import Path

from zailiprotiv.translit import latin

ANCHOR = 4       # words in a run
MIN_ANCHORS = 2  # runs a speech needs to be placed
SHORT = 2 * ANCHOR  # a speech with fewer words than this cannot hold two runs ("Ne želim.", "Hvala."): see between()
RATE = 2.5       # words a second, to give such a speech its length
_WORD = re.compile(r"[a-z0-9]+")


def fold(text: str) -> list[str]:
    """Words compared letter by letter: Latin, lower case, no diacritics (Whisper writes đ as "dj" or "gj")."""
    t = latin(text).lower().replace("đ", "dj")
    t = "".join(c for c in unicodedata.normalize("NFD", t) if not unicodedata.combining(c))
    return [w.replace("gj", "dj") for w in _WORD.findall(t)]


def heard(folder: Path, files: list[str]) -> list[tuple[str, str, float]]:
    """The day's written-down words in the order of its files: (word, file's address, second in the file)."""
    out = []
    for url in files:
        path = folder / (url.rsplit("/", 1)[1].removesuffix(".mp4") + ".jsonl")
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            seg = json.loads(line)
            for a, _b, w in seg.get("reci") or []:
                for x in fold(w):
                    out.append((x, url, a))
    return out


def _chain(pairs: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """The longest chain of (notes position, heard position) rising in both (pairs come sorted by the first)."""
    tails, tail_at, back = [], [], [-1] * len(pairs)
    for i, (_, p) in enumerate(pairs):
        k = bisect.bisect_left(tails, p)
        if k == len(tails):
            tails.append(p)
            tail_at.append(i)
        else:
            tails[k], tail_at[k] = p, i
        back[i] = tail_at[k - 1] if k else -1
    out, i = [], tail_at[-1] if tail_at else -1
    while i >= 0:
        out.append(pairs[i])
        i = back[i]
    return out[::-1]


def anchors(said: list[str], got: list[str], n: int = ANCHOR) -> list[tuple[int, int]]:
    """Runs of n words found once in the notes and once in the recording, kept in the order both agree on."""
    def once(words):
        seen: dict[tuple, int] = {}
        for i in range(len(words) - n + 1):
            g = tuple(words[i:i + n])
            seen[g] = -1 if g in seen else i
        return {g: i for g, i in seen.items() if i >= 0}
    a, b = once(said), once(got)
    return _chain(sorted((i, b[g]) for g, i in a.items() if g in b))


def place(speeches: list[dict], got: list[tuple[str, str, float]]) -> list[dict]:
    """Each speech ({"key", "text", ...}) with "datoteka", "od" and "do" (seconds in that file) and "sidra" (the runs
    found), when MIN_ANCHORS runs of it were found and its first and last fall in one file; the rest without them."""
    said, owner, first = [], [], {}
    for s in speeches:
        first[s["key"]] = len(said)
        ws = fold(s["text"])
        said += ws
        owner += [s["key"]] * len(ws)
    by = {}
    for i, p in anchors(said, [w for w, _, _ in got]):
        by.setdefault(owner[i], []).append((i, p))
    out = []
    for s in speeches:
        runs = by.get(s["key"], [])
        s = dict(s, sidra=len(runs))
        if len(runs) >= MIN_ANCHORS:
            (i0, p0), (i1, p1) = runs[0], runs[-1]
            n = len(fold(s["text"]))
            # from the first run back to the speech's first word, and from the last run on to its last word, as many
            # words of the recording as of the notes (Whisper leaves words out and adds some, about as many)
            a = max(0, p0 - (i0 - first[s["key"]]))
            b = min(len(got) - 1, p1 + ANCHOR - 1 + (first[s["key"]] + n - 1 - (i1 + ANCHOR - 1)))
            while a < p0 and got[a][1] != got[p0][1]:
                a += 1
            while b > p1 and got[b][1] != got[p1][1]:
                b -= 1
            if got[a][1] == got[b][1]:
                s.update(datoteka=got[a][1], od=got[a][2], do=got[b][2])
        out.append(s)
    return between(out)


def between(speeches: list[dict]) -> list[dict]:
    """A speech too short to hold two runs (fewer than SHORT words: an answer, a "Hvala"), with no place, gets one
    where the notes put it: just after the speech before it, which must be placed, in the same file as the one after
    (21 Nov 2026, the maintainer's request: 17 Nov's two-word "Ne želim" of an MP, between the chair's two turns,
    had none). It lasts as long as its words take at RATE; it has no runs of its own (`sidra` 0), so it is never a voice
    sample. The same rule for every speaker; a longer speech with no runs still gets no place."""
    for i, s in enumerate(speeches):
        if s.get("chair") or "datoteka" in s or s.get("sidra", 0) >= MIN_ANCHORS or i == 0 or i + 1 >= len(speeches):
            continue
        before, after = speeches[i - 1], speeches[i + 1]
        words = len(fold(s["text"]))
        if (words and words < SHORT and "datoteka" in before and before.get("datoteka") == after.get("datoteka")):
            s.update(datoteka=before["datoteka"], od=before["do"], do=before["do"] + words / RATE)
    return speeches


LEAD = 5     # a turn's place in its file: this many seconds before its first word, as everywhere on the site
MERGE = 120  # one speaker's speeches with only the chair's words between them, this close: one turn

NOTE = ("Ko je kad govorio, iz stenografskih beleški Skupštine poravnatih sa zvukom snimka dana u arhivi "
        "videonet.co.rs: snimak je automatski zapisan reč po reč (Whisper), a svaki govor iz beleški nađen u tom zapisu "
        "po nizovima od četiri reči koji se jednom javljaju i u beleškama i u zapisu, istim redom; govor traje od "
        "prve do poslednje svoje reči. Isto pravilo za svakog govornika; govor za koji nisu nađena bar dva takva niza "
        "nema mesto, osim sasvim kratkog (manje od osam reči, kao „Ne želim.“) između dva govora koji ga imaju: on stoji "
        "odmah posle prethodnog. Predsedavajući nije u spisku. 'datoteka' je snimak u arhivi, 'snimak' mesto u njemu u sekundama, "
        "pet sekundi pre prve reči. ")


def day(speeches: list[dict], files: list[dict], who) -> list[dict]:
    """The day's turns as data/<N>/snimak/ holds them, from placed speeches (place()) in the notes' order. files:
    [{"url", "od"}], each file's start on the clock (unix), or None where it is not known; who(speaker in the notes)
    → {"ime", "adresa", "grupa", "uloga"}. The chair is left out; a speaker's speeches with only the chair between
    them, within MERGE seconds, are one turn."""
    start = {f["url"]: f.get("od") for f in files}
    out: list[dict] = []
    last_speaker = None
    for s in speeches:
        if s.get("chair"):
            continue
        if "datoteka" not in s:
            last_speaker = None
            continue
        base = start.get(s["datoteka"])
        t = {**who(s["speaker"]), "od": int(base + s["od"]) if base is not None else None,
             "do": int(base + s["do"]) if base is not None else None, "okvira": s["sidra"], "video": "",
             "snimak": int(max(0, s["od"] - LEAD)), "datoteka": s["datoteka"], "beleske": [s["key"]],
             "_od": s["od"], "_do": s["do"]}
        prev = out[-1] if out else None
        if (prev and last_speaker == s["speaker"] and prev["datoteka"] == t["datoteka"]
                and t["_od"] - prev["_do"] <= MERGE):
            prev["do"], prev["_do"] = t["do"], t["_do"]
            prev["okvira"] += t["okvira"]
            prev["beleske"] += t["beleske"]
        else:
            out.append(t)
        last_speaker = s["speaker"]
    for t in out:
        t.pop("_od"), t.pop("_do")
    return out


VOICE_NOTE = ("Ko je kad govorio: dok je prenos prikazivao potpis, iz potpisa (zapis stranice „Ko sada govori“); posle "
              "toga, dok Skupština ne objavi stenografske beleške ovog dana, po glasu: svaki deo zvuka snimka u arhivi "
              "upoređen je sa glasom govornika iz govora čije je ime poznato iz potpisa ovog saziva, isto pravilo za "
              "svakoga, a ime stoji samo kad je glas dovoljno sličan (provereno na 18. novembru: svaki tako imenovan "
              "deo bio je tačan). Govornik bez uzorka glasa ostaje neimenovan, pa vreme dana nije potpuno. Kad beleške "
              "budu objavljene, dan se piše ponovo iz njih. Predsedavajući nije u spisku. 'datoteka' je snimak u "
              "arhivi videonet.co.rs, 'snimak' mesto u njemu u sekundama, pet sekundi pre početka. ")
AGREE = 60  # seconds: a file placed by one caption read in passing, when the file before or after agrees this closely


def clock(files: list[dict], stretches: dict, record: list[dict], known: dict) -> dict:
    """Each file's start on the clock (unix), where it can be told: `known` ({url: start}); else from the captions the
    live service read in passing (record turns of any number of frames) that fall inside a stretch of the same
    speaker's voice: a start two such readings agree on (within 30 s), or one reading that the file before or after
    agrees with to AGREE seconds (the files follow each other unless there was a break). files: [{"url",
    "trajanje"}] in order. {url: (start, how)}."""
    single: dict[str, list[tuple[float, float]]] = {}
    out: dict[str, tuple[float, str]] = {u: (tuple(s) if isinstance(s, (list, tuple)) else (s, "poznato"))
                                         for u, s in known.items()}
    bound = None  # a part starts no earlier than the one before it ends
    for f in files:
        if f["url"] in out:
            bound = out[f["url"]][0] + f["trajanje"]
            continue
        # a reading at r.od inside the stretch [a, b] of the same speaker: the file starts between r.od - b and r.od - a
        spans = [(r["od"] - b, r["od"] - a) for w, a, b, _ in stretches.get(f["url"], []) for r in record
                 if r.get("adresa") == w and (bound is None or r["od"] - a >= bound - AGREE)]
        spans = [(max(lo, bound - AGREE) if bound is not None else lo, hi) for lo, hi in spans]
        best = []
        for lo, hi in spans:
            agree = [(l, h) for l, h in spans if l <= hi + 30 and h >= lo - 30]
            if len(agree) > len(best):
                best = agree
        if len(best) >= 2:
            lo, hi = max(l for l, _ in best), min(h for _, h in best)
            out[f["url"]] = ((lo + hi) / 2 if lo <= hi else (best[0][0] + best[0][1]) / 2, f"{len(best)} potpisa")
        elif spans:
            single[f["url"]] = spans
        if bound is not None:
            bound = (out[f["url"]][0] if f["url"] in out else bound) + f["trajanje"]
    # One reading, where the next part starts as this one ends (no break between them), within AGREE seconds: the
    # place both ranges allow, its middle.
    for _ in range(len(files)):
        for i, f in enumerate(files[:-1]):
            nxt = files[i + 1]
            if f["url"] in out and nxt["url"] in out:
                continue
            mine = [(out[f["url"]][0],) * 2] if f["url"] in out else single.get(f["url"], [])
            theirs = [(out[nxt["url"]][0],) * 2] if nxt["url"] in out else single.get(nxt["url"], [])
            for lo, hi in mine:
                for l2, h2 in theirs:
                    a, b = max(lo, l2 - f["trajanje"] - AGREE), min(hi, h2 - f["trajanje"] + AGREE)
                    if a <= b:
                        s = (a + b) / 2
                        out.setdefault(f["url"], (s, "1 potpis, potvrđen susednim delom"))
                        out.setdefault(nxt["url"], (s + f["trajanje"], "1 potpis, potvrđen susednim delom"))
                        break
                else:
                    continue
                break
    return out


def voice_day(files: list[dict], stretches: dict, starts: dict, who) -> list[dict]:
    """The turns a day's voices give: stretches ([(address, from, to, likeness)], seconds in the file) of files with a
    start, one speaker's stretches within MERGE seconds joined. who(address) → {"ime", "adresa", "grupa", "uloga"}."""
    out: list[dict] = []
    for f in files:
        if f["url"] not in starts:
            continue
        base = starts[f["url"]][0]
        for w, a, b, s in stretches.get(f["url"], []):
            prev = out[-1] if out else None
            if prev and prev["adresa"] == w and prev["datoteka"] == f["url"] and base + a - prev["do"] <= MERGE:
                prev["do"] = int(base + b)
                continue
            out.append({**who(w), "od": int(base + a), "do": int(base + b), "okvira": 2, "video": "",
                        "snimak": int(max(0, a - LEAD)), "datoteka": f["url"], "po": "glas"})
    return out
