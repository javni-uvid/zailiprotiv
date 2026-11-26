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
GAP = 10         # seconds with no word heard: a speech's beginning or end is not counted over it (see place())
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
    all_runs = [by.get(s["key"], []) for s in speeches]
    ends = [r[-1][1] + ANCHOR - 1 if r else -1 for r in all_runs]   # the last heard word of each speech's runs
    for k, s in enumerate(speeches):
        runs = all_runs[k]
        s = dict(s, sidra=len(runs))
        if len(runs) >= MIN_ANCHORS:
            (i0, p0), (i1, p1) = runs[0], runs[-1]
            n = len(fold(s["text"]))
            # From the first run back to the speech's first word, and from the last run on to its last word, as many
            # words of the recording as of the notes (Whisper leaves words out and adds some, about as many), but
            # never over a hole of more than GAP seconds in the recording's words, nor into another speech's runs:
            # where Whisper missed a speech's first words, counting them back had taken the chair's words and the
            # speaker's before (25 Nov 2026: 18 Nov's Kamberi began 78 s early, over Vučić's end). What the recording
            # did not hear is not guessed: the speech begins at the first word heard after the hole.
            lo = max(ends[:k], default=-1) + 1
            hi = min((r[0][1] for r in all_runs[k + 1:] if r), default=len(got)) - 1
            need, a = i0 - first[s["key"]], p0
            while need > 0 and a > lo and got[a - 1][1] == got[a][1] and got[a][2] - got[a - 1][2] <= GAP:
                a, need = a - 1, need - 1
            need = first[s["key"]] + n - 1 - (i1 + ANCHOR - 1)  # under 0: the last run reaches into the next speech
            b, need = min(len(got) - 1, p1 + ANCHOR - 1 + min(need, 0)), max(need, 0)
            while b > p1 and got[b][1] != got[p1][1]:
                b -= 1
            while need > 0 and b < hi and got[b + 1][1] == got[b][1] and got[b + 1][2] - got[b][2] <= GAP:
                b, need = b + 1, need - 1
            if got[a][1] == got[b][1]:
                s.update(datoteka=got[a][1], od=got[a][2], do=got[b][2])
            else:  # from one file into the next (24 Nov 2026: an hour's speech of 19 Nov had no place, its last words
                # being the next file's): the part in each, when a run of it is in each and no file lies between
                turn_at = next(j for j in range(a, b + 1) if got[j][1] != got[a][1])
                if got[turn_at][1] == got[b][1] and any(p < turn_at for _, p in runs) and any(p >= turn_at for _, p in runs):
                    s.update(datoteka=got[a][1], od=got[a][2], do=got[turn_at - 1][2],
                             dalje={"datoteka": got[b][1], "od": got[turn_at][2], "do": got[b][2]})
        out.append(s)
    return between(out)


AGREE_TIMER = 1  # seconds: the frames of one reading must give the same start within this


def timer_starts(speeches: list[dict], got: list[tuple[str, str, float]], readings: list[dict]) -> list[dict]:
    """A speech's beginning from the speaker's own timer in the broadcast's caption, where Whisper missed its first
    words (26 Nov 2026; data/<N>/merac.json, read by hand for now). Each reading: the notes' key ("beleske"), the
    archive's file, the caption's name as read ("ime") and frames ({"sek": second in the file, "merac": "m:ss" as read,
    or null where the frame shows none}). A speech's start = a frame's second less its timer, taken only when:
    the name is the notes' speaker; two frames or more read a timer and give the same start within AGREE_TIMER; the
    reading's file is the speech's. The start only moves earlier, and never before the last word heard before it in
    that file (the end of the speech before, or the hole's beginning): a timer may start before the hole, when the
    floor is given while the chair still speaks, or run on from the same speaker's speech just before (19 and 24 Nov)."""
    by_key = {r["beleske"]: r for r in readings}
    times: dict[str, list[float]] = {}
    for _, url, t in got:
        times.setdefault(url, []).append(t)
    for s in speeches:
        r = by_key.get(s.get("key"))
        if not r or "datoteka" not in s or r.get("datoteka") != s["datoteka"] or s.get("chair"):
            continue
        if sorted(fold(r.get("ime") or "")) != sorted(fold(s["speaker"])):
            continue
        starts = []
        for f in r.get("okviri") or []:
            m = re.fullmatch(r"(\d{1,2}):(\d{2})", f.get("merac") or "")
            if m:
                starts.append(f["sek"] - (int(m.group(1)) * 60 + int(m.group(2))))
        if len(starts) < 2 or max(starts) - min(starts) > AGREE_TIMER:
            continue
        before = [t for t in times.get(s["datoteka"], []) if t < s["od"]]
        start = max(min(starts), before[-1] if before else 0.0)
        if start < s["od"]:
            s["od"] = start
            s["po_meracu"] = True
    return speeches


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


def roll_call(text: str) -> bool:
    """A list read out (a vote by name: "Абрамовић Ненад – Стојан Раденовић; …"), no speech: it holds its place among
    the others and is not listed as anyone's (19 Nov 2026: the secretary read for 75 minutes)."""
    return text.count(";") >= 15 and text.count("–") >= 15


def nearest(name: str, keys: dict) -> str | None:
    """The key of the one listed name the notes' misspelt name is near ("Јова Бакић", "Петар Митев"): as many words, each
    at least 0.75 alike, clearly nearer than any other; None when no listed name is, or two are. Two letters exchanged
    ("Брбанић") are one slip, whatever their share of a short word (25 Nov 2026)."""
    from difflib import SequenceMatcher

    def alike(a: str, b: str) -> float:
        off = [i for i in range(len(a)) if a[i] != b[i]] if len(a) == len(b) else []
        swapped = len(off) == 2 and a[off[0]] == b[off[1]] and a[off[1]] == b[off[0]]
        return max(SequenceMatcher(None, a, b).ratio(), 0.9 if swapped else 0)
    mine = sorted(name.lower().split())
    scored = []
    for k in keys:
        theirs = sorted(k.lower().split())
        if len(theirs) == len(mine):
            scored.append((min(alike(a, b) for a, b in zip(mine, theirs)), k))
    scored.sort(reverse=True)
    if scored and scored[0][0] >= 0.75 and (len(scored) == 1 or scored[0][0] - scored[1][0] >= 0.05):
        return scored[0][1]
    return None


LEAD = 5     # a turn's place in its file: this many seconds before its first word, as everywhere on the site
MERGE = 120  # one speaker's speeches with only the chair's words between them, this close: one turn
# A turn ends, though the same speaker goes on, where the chair's words between give the floor anew (to anyone, the same
# speaker too: a reply and then the debate are two, 26 Nov 2026, the maintainer), or declare a break; or where the notes
# say the microphone was cut. A warning, an explanation or an argument while the speaker keeps the floor ends nothing.
FLOOR_GIVEN = ("реч има", "има реч", "дајем реч", "реч дајем", "дајем вам реч", "право на реплику")
FLOOR_KEPT = ("има реч, да заврши", "има реч да заврши", "има реч, да настави", "има реч да настави")  # "let him finish"
BREAK = ("пауз",)
CUT = ("искључен микрофон",)
ANSWER = 20  # words: a member's piece this short right after the chair's question is an answer to the chair, no speech


def _answer(s: dict, asked: bool, goes_on: bool) -> bool:
    """A very short answer to the chair (26 Nov 2026, the maintainer, of case 3.16: "drugu istancu ne bih klasifikovao
    kao govor, samo je odgovor predsedavajucem koji je jako kratak"; of the rule: "slazem se"): a member's piece of at
    most ANSWER words right after the chair's words that end in a question, where it would end a turn or stand alone. It
    is no speech: joined to no turn and no turn of its own. Where the same speaker goes on after it (`goes_on`) it stays
    in the turn: inside a speech an exchange with the chair is part of it (2.9, 2.12), and nothing an MP says is left out
    of the record of the speech. The same for everyone; the notes' pages keep every piece."""
    return asked and not goes_on and len(fold(s.get("text") or "")) <= ANSWER


def _says(text: str, words: tuple) -> bool:
    t = re.sub(r"\s+", " ", text.lower())
    for w in FLOOR_KEPT:
        t = t.replace(w, "")
    return any(w in t for w in words)

NOTE = ("Ko je kad govorio, iz stenografskih beleški Skupštine poravnatih sa zvukom snimka dana u arhivi "
        "videonet.co.rs: snimak je automatski zapisan reč po reč (Whisper), a svaki govor iz beleški nađen u tom zapisu "
        "po nizovima od četiri reči koji se jednom javljaju i u beleškama i u zapisu, istim redom; govor traje od "
        "prve do poslednje svoje reči. Isto pravilo za svakog govornika; govor za koji nisu nađena bar dva takva niza "
        "nema mesto, osim sasvim kratkog (manje od osam reči, kao „Ne želim.“) između dva govora koji ga imaju: on stoji "
        "odmah posle prethodnog. Predsedavajući nije u spisku. 'datoteka' je snimak u arhivi, 'snimak' mesto u njemu u sekundama, "
        "pet sekundi pre prve reči. ")


def start_at(f: dict, second: float) -> int | None:
    """The clock time (unix) a file's second 0 would have for what it shows at `second`: its start, or, for a file the
    archive cut inside ("delovi": [{"sek", "od"}], the second each stretch begins at and that stretch's start), the
    stretch's own (24 Nov 2026: a break of 70 minutes is cut out of one file)."""
    own = [d for d in f.get("delovi") or [] if d["sek"] <= second]
    return own[-1]["od"] if own else f.get("od")


def stretches(f: dict, length: int) -> list[dict]:
    """A file as the day's file lists it, a stretch each: {"url", "od", "trajanje"}, where a moment's place in the file
    is the moment less "od". A later stretch's "od" is therefore before its first picture, by "preskoceno" seconds."""
    parts = f.get("delovi") or []
    if not parts:
        return [{"url": f["url"], "od": f["od"], "trajanje": length}]
    ends = [d["sek"] for d in parts[1:]] + [length]
    return [{"url": f["url"], "od": d["od"], "trajanje": end, **({"preskoceno": d["sek"]} if d["sek"] else {})}
            for d, end in zip(parts, ends)]


def day(speeches: list[dict], files: list[dict], who) -> list[dict]:
    """The day's turns as data/<N>/snimak/ holds them, from placed speeches (place()) in the notes' order. files:
    [{"url", "od"}], each file's start on the clock (unix), or None where it is not known; who(speaker in the notes)
    → {"ime", "adresa", "grupa", "uloga"}. The chair is left out; a speaker's speeches with only the chair between
    them, within MERGE seconds, are one turn, unless the chair gives the floor anew or declares a break between them, or
    the microphone was cut (FLOOR_GIVEN, BREAK, CUT)."""
    by_url = {f["url"]: f for f in files}
    out: list[dict] = []
    last_speaker = None
    ended = False  # since the speaker's last piece: the floor given anew, a break, or the microphone cut
    asked = False  # the chair's last words end in a question
    members = [i for i, s in enumerate(speeches) if not s.get("chair")]
    after = {i: speeches[j]["speaker"] for i, j in zip(members, members[1:])}  # the next member's piece's speaker
    for i, s in enumerate(speeches):
        if s.get("chair"):
            ended |= _says(s.get("text") or "", FLOOR_GIVEN + BREAK)
            asked = (s.get("text") or "").rstrip().endswith("?")
            continue
        if _answer(s, asked, after.get(i) == s["speaker"]):
            continue
        asked = False
        if "datoteka" not in s:
            ended |= _says(s.get("text") or "", CUT)
            # A piece of the same speaker with no place (too short for two runs) does not end the turn: with only the
            # chair's words around it, the speaker who goes on after it never lost the floor (26 Nov 2026, the
            # maintainer: "svo vreme treba biti kartica za tandira"). Another speaker's piece does.
            if s["speaker"] != last_speaker:
                last_speaker = None
            continue
        for part in [s] + ([s["dalje"]] if s.get("dalje") else []):
            f = by_url.get(part["datoteka"], {})
            base, end = start_at(f, part["od"]), start_at(f, part["do"])
            t = {**who(s["speaker"]), "od": int(base + part["od"]) if base is not None else None,
                 "do": int(end + part["do"]) if base is not None else None, "okvira": s["sidra"], "video": "",
                 "snimak": int(max(0, part["od"] - LEAD)), "datoteka": part["datoteka"], "beleske": [s["key"]],
                 "_od": part["od"], "_do": part["do"], "_s": base, "_e": end}
            prev = out[-1] if out else None
            if (prev and last_speaker == s["speaker"] and prev["datoteka"] == t["datoteka"] and prev["_e"] == t["_s"]
                    and t["_od"] - prev["_do"] <= MERGE and not ended):
                prev["do"], prev["_do"], prev["_e"] = t["do"], t["_do"], t["_e"]
                prev["okvira"] += t["okvira"]
                prev["beleske"] += t["beleske"]
            else:
                out.append(t)
            last_speaker, ended = s["speaker"], False
        ended = _says(s.get("text") or "", CUT)
    for t in out:
        for k in ("_od", "_do", "_s", "_e"):
            t.pop(k)
    return out


CHAIR_CARD = 30  # seconds: a stretch of the chair's words between two turns this long or longer gets a card of its own
JOIN_CHAIR = 30  # seconds: the chair's pieces this close, with no member's placed piece between, are one stretch


def chair_stretches(speeches: list[dict], files: list[dict], turns: list[dict],
                    got: list[tuple[str, str, float]] | None = None) -> list[dict]:
    """The chair's own stretches between members' turns (26 Nov 2026, the maintainer, of case 3.17 "to je govor
    predsedavajuceg", and of the card's length "spustio bih prag na 30 sekundi"): the chair's placed pieces with no
    member's placed piece between them, from the first word to the last, kept where they last CHAIR_CARD seconds or more,
    cut to the gap between the turns around them and never inside a turn. A roll call read out (`prozivka`) is none.
    Its length ("trajanje") is the seconds the chair is heard (`got`, the recording's words): from the first word to the
    last, less every hole of over GAP seconds (a minute of silence, a quorum count, a break begun); under CHAIR_CARD
    heard, no card. Each: {"od", "do", "trajanje", "datoteka", "snimak", "beleske"}. It belongs to the role, not to a
    person or a group."""
    by_url = {f["url"]: f for f in files}
    out: list[dict] = []
    cur = None
    for s in speeches:
        if not s.get("chair") or s.get("prozivka"):
            if "datoteka" in s or s.get("prozivka"):
                cur = None  # a member's placed piece, or a roll call, ends the stretch
            continue
        if "datoteka" not in s:
            continue
        f = by_url.get(s["datoteka"], {})
        base, end = start_at(f, s["od"]), start_at(f, s["do"])
        if base is None:
            cur = None
            continue
        a, b = base + s["od"], end + s["do"]
        if cur and cur["datoteka"] == s["datoteka"] and a - cur["_do"] <= JOIN_CHAIR:
            cur["_do"], cur["beleske"] = b, cur["beleske"] + [s["key"]]
        else:
            cur = {"_od": a, "_do": b, "datoteka": s["datoteka"], "_sek": s["od"], "beleske": [s["key"]]}
            out.append(cur)
    kept = []
    spans = sorted((t["od"], t["do"]) for t in turns if t.get("od") is not None)
    for c in out:
        a, b = c["_od"], c["_do"]
        if any(x < a and b < y for x, y in spans):
            continue  # inside a member's turn: that turn's
        before = [y for x, y in spans if x <= a]
        after = [x for x, y in spans if x >= a]
        a = max([a] + [y for y in before if y > a and y <= b])
        b = min([b] + [x for x in after if a <= x < b])
        sek = c["_sek"] + (a - c["_od"])  # the stretch's start, in its file
        words = sorted(t for _, u, t in got or [] if u == c["datoteka"] and sek <= t <= sek + (b - a))
        heard = sum(y - x for x, y in zip(words, words[1:]) if y - x <= GAP) if got is not None else b - a
        if heard >= CHAIR_CARD:
            kept.append({"od": int(a), "do": int(b), "trajanje": int(round(heard)), "datoteka": c["datoteka"],
                         "snimak": int(max(0, sek - LEAD)), "beleske": c["beleske"]})
    return kept


VOICE_NOTE = ("Ko je kad govorio, dok Skupština ne objavi stenografske beleške ovog dana: zvuk snimka u arhivi podeljen je "
              "na delove gde se glas menja, a deo dobija ime po potpisu u prenosu (zapis stranice „Ko sada govori“), gde ga "
              "nije bilo po rečima predsedavajućeg kad daje reč (automatski zapis zvuka), a gde nema ni njih po glasu, "
              "upoređenom sa glasom govornika iz govora čije je ime poznato; ime iz potpisa ili iz reči ne stoji gde glas "
              "kaže drugačije. Isto pravilo za svakoga; deo bez jasnog znaka ostaje neimenovan, pa vreme dana nije potpuno, "
              "a automatsko čitanje može da pogreši. Kad beleške budu objavljene, dan se piše ponovo iz njih. "
              "Predsedavajući nije u spisku. 'datoteka' je snimak u "
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
    """The turns a day's pieces give: stretches ([(address, from, to, what named it)], seconds in the file) of files with a
    start, one speaker's within MERGE seconds, nobody else's between, joined. who(address) → {"ime", "adresa", "grupa", "uloga"}."""
    out: list[dict] = []
    for f in files:
        if f["url"] not in starts:
            continue
        base = starts[f["url"]][0]
        for w, a, b, how in stretches.get(f["url"], []):
            prev = out[-1] if out else None
            if prev and prev["adresa"] == w and prev["datoteka"] == f["url"] and base + a - prev["do"] <= MERGE:
                prev["do"] = int(base + b)
                continue
            out.append({**who(w), "od": int(base + a), "do": int(base + b), "okvira": 2, "video": "",
                        "snimak": int(max(0, a - LEAD)), "datoteka": f["url"], "po": how})
    return out
