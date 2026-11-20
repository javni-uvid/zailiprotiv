"""What happened in the sitting, and the day so far, told by a model from the automatic transcript (20 Nov 2026, the
maintainer's decision, after a trial on 19 Nov: the model found every break, election and result of that day, the
rules none of them, and 14 of the rules' 19 agenda items were false).

Every ten minutes while a broadcast is on (and once more after it ends), the pieces of the transcript written down
since the last call go to Claude Haiku with a fixed list of the procedure's steps (EVENTS). Each step must come with
the sentence it rests on copied from those pieces; a step whose sentence is not there word for word is dropped. The
steps are kept as the day's lines (`Tracker.note`, source "model") and are what the page's "Šta se desilo danas"
shows (steps.steps_shown); the rules of hronika.py stay as the fallback while the model gives nothing.

At a break the model found (once nobody has been at the rostrum for BREAK_QUIET, ten minutes, after it) the stretch since the
last summary is summed up (SUMMARY), and when the day ends (the end of work found, or no broadcast for END_QUIET after
a day with a transcript) the day as a whole (DAY), from the stretches' summaries. The rules: only what was said; no
tone or verdict of the model's own, the speaker's own words kept as said; no quotes (the transcript is not a source
for one); every speaker with two minutes or more, in the order they first spoke, one line each; numbers only as said.
Checked before kept: every speaker named is one of the stretch's, every number is in the text; a summary that fails
is asked once more with what was wrong, then left out. Kept in /data/sazetak/<day>.json.

The model's words are labelled on the page as written by a model from an automatic transcript, which may err. The
summary is on the page only with SAZETAK_PRIKAZ=1 (config.SHOW_SUMMARY); /sazetak?k=<PREPIS_KLJUC> shows it before.
No key (ANTHROPIC_API_KEY empty): nothing is sent, and the rules alone tell the steps."""
from __future__ import annotations

import datetime as dt
import json
import logging
import re
import threading
import time
import unicodedata
from pathlib import Path
from zoneinfo import ZoneInfo

from . import config
from .state_base import SAID_LEAD

log = logging.getLogger("uzivo.sudija")

EVERY = 600  # seconds between calls while the broadcast is on
LAG = 45  # a piece younger than this may still be followed by its sentence's end: it waits for the next call
END_QUIET = 1200  # no broadcast this long after a day with a transcript: the day is over
BREAK_QUIET = 600  # a stretch is summed up at a break with nobody at the rostrum this long (not at a five-minute one)
CHAIR = "bez potpisa (predsedavajući ili sala)"

KINDS = ("Tačka dnevnog reda", "Pretres otvoren", "Pretres zaključen", "Glasanje", "Rezultat glasanja", "Izbor",
         "Pauza", "Nastavak rada", "Mera predsedavajućeg", "Reč ima", "Kraj rada")

EVENTS = """Iz AUTOMATSKOG prepisa (Whisper; greši u imenima, brojevima i rečima) dela sednice Narodne skupštine
Srbije utvrđuješ SAMO proceduralne događaje sa ovog zatvorenog spiska:

- "Tačka dnevnog reda": prelazak na tačku ili nastavak rada na tački; "tacka" = broj tačke ako je izgovoren, inače null
- "Pretres otvoren" / "Pretres zaključen": otvaranje ili zaključenje pretresa (rasprave)
- "Glasanje": predsedavajući stavlja nešto na glasanje
- "Rezultat glasanja": izgovoren rezultat (za, protiv, uzdržano, nije glasalo) ili odluka (usvojeno, nije usvojeno);
  "napomena" = rezultat brojevima tačno kako su izgovoreni
- "Izbor": Skupština je nekoga izabrala ili imenovala; "ko" = ime i funkcija kako su izgovoreni
- "Pauza": predsedavajući proglašava pauzu (ne najavu da će je proglasiti kasnije); "do" = do kada ili koliko, ako je rečeno
- "Nastavak rada": rad se nastavlja posle pauze ili sutradan
- "Mera predsedavajućeg": izrečena opomena, oduzimanje reči ili udaljenje sa sednice; "kome" = ime ako je izgovoreno;
  "napomena" = koja mera. UPOZORENJE NIJE MERA; najava ("dobićete opomenu") nije mera
- "Reč ima": predsedavajući daje reč; "kome" = ime kako je izgovoreno
- "Kraj rada": zaključenje rada za taj dan ili zaključenje sednice

PRAVILA
- Samo ono što je u datom delu izgovoreno; ništa iz znanja, ništa iz pretpostavke.
- Svaki događaj ima "recenica": rečenicu ili deo rečenice iz prepisa PREPISAN SLOVO PO SLOVO (bez oznake vremena i
  imena), 5 do 40 reči. Ne ispravljaj greške prepisa u njoj.
- "vreme": oznaka [HH:MM:SS] reda u kom je ta rečenica.
- Nema događaja: prazna lista. Nikakve ocene ni komentar.

IZLAZ: samo JSON, bez ikakvog drugog teksta:
{"dogadjaji": [{"vrsta": "...", "vreme": "HH:MM:SS", "recenica": "...", "tacka": null, "kome": null, "ko": null,
"do": null, "napomena": null}]}"""

_RULES = """PRAVILA (obavezna)
1. Samo ono što je u prepisu rečeno. Ništa iz sopstvenog znanja, ništa pretpostavljeno.
2. Ti ne dodaješ ocene ni ton ("oštro", "burno", "uspešno", "neprimereno"). Ali reči i teme koje je govornik sam
   upotrebio ostaju kako ih je rekao, i kad su teške ("napad", "laž", "kriminal", "nasilje"): ne ublažavaš ih, ne
   izostavljaš ih i ne zamenjuješ blažim. Stav govornika iznosi se kao njegova tvrdnja: "X je rekao da …".
3. Isto pravilo za svakog: u "govornici" je SVAKI govornik iz oznaka redova koji u ovom delu ima ukupno bar 2 minuta
   govora, redom prvog javljanja, svako jednom rečenicom (najviše 30 reči) o TEMI onoga što je govorio, ne o tonu.
   Ime piši tačno kako stoji u oznaci reda. Predsedavajući nije na tom spisku.
4. Bez navodnika i doslovnih citata (prepis nije izvor za citat).
5. Brojeve (glasovi, prisutni) piši samo kako su izgovoreni u prepisu; ako je broj nejasan, izostavi ga.
6. Ime poslanika koje prepis piše pogrešno piši kako stoji na datom spisku poslanika, ako je jasno koji je;
   inače ga izostavi.
7. Jezik: srpski, latinica, jednostavne rečenice."""

SUMMARY = f"""Pišeš sažetak dela sednice Narodne skupštine Srbije iz AUTOMATSKOG prepisa (Whisper). Prepis greši u
imenima, brojevima i rečima. Oznaka reda: [HH:MM:SS] Ime (lista): tekst; "{CHAIR}" je predsedavajući ili sala.

{_RULES}
8. "tok": šta je Skupština radila, hronološki: tačke dnevnog reda, pretres, glasanja i odluke (sa brojevima kako su
   saopšteni), pauze, mere predsedavajućeg (opomena, oduzimanje reči, udaljenje; upozorenje NIJE mera), svaka stavka
   sa vremenom [HH:MM].
9. Ako je dat "dosadašnji sažetak", ne ponavljaj ga: pišeš samo ovaj deo.

IZLAZ: samo JSON, bez ikakvog drugog teksta:
{{"od": "HH:MM", "do": "HH:MM", "ukratko": "2 do 4 rečenice: šta je Skupština u ovom delu radila i odlučila",
 "tok": [{{"vreme": "HH:MM", "sta": "..."}}], "govornici": [{{"ime": "...", "lista": "...", "o_cemu": "..."}}]}}"""

DAY = f"""Pišeš sažetak celog dana sednice Narodne skupštine Srbije iz sažetaka njegovih delova, napisanih iz
AUTOMATSKOG prepisa. Ne dodaješ ništa čega nema u tim sažecima.

{_RULES}

IZLAZ: samo JSON, bez ikakvog drugog teksta:
{{"kratko": "jedna ili dve rečenice, najviše 280 znakova: šta je Skupština tog dana odlučila",
 "ukratko": "jedan pasus, 4 do 7 rečenica: tok dana i odluke",
 "odluke": [{{"vreme": "HH:MM", "sta": "odluka ili izbor, sa brojem glasova kako je saopšten"}}],
 "tok": [{{"vreme": "HH:MM", "sta": "..."}}],
 "govornici": [{{"ime": "...", "lista": "...", "o_cemu": "jedna rečenica, do 35 reči, za ceo dan"}}]}}
"tok" ima najviše 20 stavki; u "govornici" je svaki govornik iz delova, jednom, redom prvog javljanja."""


def on() -> bool:
    return bool(config.MODEL_KEY)


def norm(s: str) -> str:
    """For comparing a sentence the model copied with the transcript: no punctuation, one space, lower case."""
    return re.sub(r"\s+", " ", re.sub(r"[„“”\"'’.,:;!?…\-–()]", " ", s)).strip().lower()


def _fold(s: str) -> str:
    s = s.lower().replace("đ", "dj")
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def reply_json(text: str) -> dict | None:
    """The JSON object in a reply: from its first brace to its last (a model sometimes puts a word before it)."""
    if "{" in text and "}" in text:
        try:
            got = json.loads(text[text.index("{"):text.rindex("}") + 1])
            if isinstance(got, dict):
                return got
        except ValueError:
            pass
    for m in reversed(list(re.finditer(r"\{", text))):
        try:
            got = json.loads(text[m.start():text.rindex("}") + 1])
            return got if isinstance(got, dict) else None
        except ValueError:
            continue
    return None


def pieces(said: dict[str, str]) -> list[tuple[int, str, bool]]:
    """The transcript's pieces in time order: (second, text, the chair's or the hall's sound)."""
    out = []
    for k, v in said.items():
        if k.isdigit():
            out.append((int(k), v, False))
        elif k[:1] == "p" and k[1:].isdigit():
            out.append((int(k[1:]), v, True))
    return sorted(out)


def lines(rows: list[tuple[int, str, bool]], turns: list[dict], tz: ZoneInfo, shown=lambda s: s) -> list[tuple[int, str]]:
    """[(second, "[HH:MM:SS] Name (list): text")]: each piece under the turn it falls in, the chair's sound and sound
    in no turn as CHAIR; the name only where the speaker changes, as the 19 Nov trial had it."""
    out, last = [], None
    for ts, text, chair in rows:
        who = CHAIR
        if not chair:
            for d in turns:
                if d["od"] - SAID_LEAD - 1 <= ts <= d["do"]:
                    who = f'{d["ime"]} ({d.get("lista") or "bez liste"})'
                    break
        clock = dt.datetime.fromtimestamp(ts, tz).strftime("%H:%M:%S")
        out.append((ts, f"[{clock}] {who}: {shown(text)}" if who != last else f"[{clock}] {shown(text)}"))
        last = who
    return out


def check_events(found: list, block: list[tuple[int, str]]) -> list[dict]:
    """The steps whose sentence is in the block word for word, each with its second (the line it is in)."""
    kept = []
    for e in found if isinstance(found, list) else []:
        if not isinstance(e, dict) or e.get("vrsta") not in KINDS:
            continue
        s = norm(str(e.get("recenica") or ""))
        if len(s) < 12:
            continue
        hit = next((ts for ts, line in block if s in norm(line)), None)
        if hit is None:  # a sentence over two lines: the block joined
            joined, at = "", []
            for ts, line in block:
                body = norm(re.sub(r"^\[\d\d:\d\d:\d\d\]( [^:]*\([^)]*\):| " + re.escape(CHAIR) + ":)?", "", line))
                at.append((len(joined), ts))
                joined += body + " "
            i = joined.find(s)
            if i < 0:
                continue
            hit = max((ts for pos, ts in at if pos <= i), default=block[0][0])
        kept.append({**{k: e.get(k) for k in ("vrsta", "recenica", "tacka", "kome", "ko", "do", "napomena")}, "t": hit})
    return kept


def check_summary(s: dict | None, speakers: set[str], text: str) -> list[str]:
    """What is wrong with a summary: a speaker not of the stretch, a number not in the text. [] when it is fine."""
    if not isinstance(s, dict) or not s.get("ukratko"):
        return ["nema polja ukratko"]
    errs = [f"govornik {g.get('ime')!r} nije među govornicima ovog dela" for g in s.get("govornici") or []
            if isinstance(g, dict) and g.get("ime") not in speakers]
    body = set(re.findall(r"\d+", text))
    words = json.dumps({k: v for k, v in s.items() if k not in ("od", "do")}, ensure_ascii=False)
    words = re.sub(r"\b\d\d?:\d\d\b", " ", words)  # the times
    errs += [f"broj {n} nije u prepisu" for n in sorted(set(re.findall(r"\d+", words)) - body, key=int)]
    return errs


def ask_claude(system: str, user: str, max_tokens: int = 16000, effort: str = "low") -> str:
    """One call to the model: the rules as a cached system prompt, the material as the message."""
    import anthropic
    client = anthropic.Anthropic(api_key=config.MODEL_KEY, max_retries=3, timeout=120)
    reply = client.messages.create(
        model=config.MODEL, max_tokens=max_tokens,
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user}], output_config={"effort": effort})
    if reply.stop_reason == "refusal":
        raise RuntimeError("the model declined")
    if reply.stop_reason == "max_tokens":  # cut off: no whole JSON to read (the 19 Nov replay, long stretches at 6000)
        raise RuntimeError(f"the reply was cut off at {max_tokens} tokens")
    log.info("model: %s in, %s out", reply.usage.input_tokens, reply.usage.output_tokens)
    return "".join(b.text for b in reply.content if b.type == "text")


class Judge(threading.Thread):
    """The model's calls (EVENTS every ten minutes, SUMMARY at a break, DAY at the end), from the tracker's day."""

    def __init__(self, tracker, stop: threading.Event, ask=None, bell=None) -> None:
        super().__init__(daemon=True)
        self.tracker, self.halt, self.bell = tracker, stop, bell
        self.ask = ask or ask_claude
        self.tz = ZoneInfo(config.TZ)
        self.day, self.kept = "", {}
        self.last_call = 0.0

    # --- what is kept per day: the pieces already read, the stretches summed up, the day ---
    def _file(self, day: str) -> Path | None:
        base = Path(config.STATE_PATH).parent if config.STATE_PATH else None
        return base / "sazetak" / f"{day}.json" if base else None

    def _load(self, day: str) -> None:
        if day == self.day:
            return
        self.day, self.kept = day, {"vidjeno": [], "delovi": [], "dan": None, "greske": 0}
        f = self._file(day)
        try:
            if f and f.exists():
                self.kept.update(json.loads(f.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass
        self.tracker.use_summary(day, self.kept)

    def _save(self) -> None:
        self.kept["model"] = config.MODEL
        f = self._file(self.day)
        if f:
            try:
                f.parent.mkdir(parents=True, exist_ok=True)
                tmp = f.with_suffix(".tmp")
                tmp.write_text(json.dumps(self.kept, ensure_ascii=False), encoding="utf-8")
                tmp.replace(f)
            except OSError:
                pass
        self.tracker.use_summary(self.day, self.kept)

    def _material(self, snap: dict) -> tuple[list[tuple[int, str, bool]], list[dict]]:
        with self.tracker._lock:
            said = dict(self.tracker._said_of(snap["dan"]))
        turns = list(snap.get("danas") or []) + ([snap["sada"]] if snap.get("sada") else [])
        return pieces(said), turns

    def _roster(self) -> str:
        r = self.tracker.roster
        if r is None:
            return ""
        names = sorted(p.name for p in r.people if not r.current or p.slug in r.current)
        return "Spisak poslanika: " + "; ".join(names) + "\n\n"

    # --- one look ---
    def step(self, now: float | None = None) -> None:
        now = time.time() if now is None else now
        snap = self.tracker.snapshot(now=now)
        if not snap.get("dan"):
            return
        self._load(snap["dan"])
        if snap.get("ranije") and self.kept.get("dan") is not None:  # an earlier day, done: told in the morning
            self._tell(now)
            return  # (a day ending after midnight is still finished: its last pieces read, the day summed up)
        rows, turns = self._material(snap)
        seen = set(self.kept["vidjeno"])
        fresh = [r for r in rows if r[0] not in seen and r[0] <= now - LAG]
        live = snap.get("stanje") != "nema_prenosa"
        if fresh and (now - self.last_call >= EVERY or not live):
            self._events(fresh, rows, turns)
            self.last_call = now
        self._summaries(snap, rows, turns, now, live)
        self._tell(now)

    def _tell(self, now: float) -> None:
        """The day's summary out on the page: the subscribers told once (obavesti.Bell.summary), in the hours a
        notification may wake someone (obavesti.HOURS; a day ended at midnight is told in the morning)."""
        from .obavesti import HOURS
        whole = self.kept.get("dan")
        if not (self.bell and config.SHOW_SUMMARY and isinstance(whole, dict) and whole.get("ukratko")) or self.kept.get("javljeno"):
            return
        if not HOURS[0] <= dt.datetime.fromtimestamp(now, self.tz).hour < HOURS[1]:
            return
        if now - whole.get("t", now) > 12 * 3600:  # news no more: a summary half a day old is not pushed
            return
        self.kept["javljeno"] = int(now)
        self._save()
        self.bell.summary(self.day)

    def _events(self, fresh, rows, turns) -> None:
        block = lines(fresh, turns, self.tz, self.tracker.shown)
        reply = reply_json(self.ask(EVENTS, "\n".join(l for _, l in block)))
        found = check_events((reply or {}).get("dogadjaji"), block)
        for e in found:
            more = {k: self.tracker.shown(e[k]) if isinstance(e[k], str) else e[k]  # names as the corrections mend them
                    for k in ("tacka", "kome", "ko", "do", "napomena") if e.get(k) not in (None, "")}
            self.tracker.note(e["t"], e["vrsta"], e["recenica"], "model", more=more)
        self.kept["vidjeno"] = sorted(set(self.kept["vidjeno"]) | {r[0] for r in fresh})
        self._save()
        log.info("model: %d pieces read, %d steps kept", len(fresh), len(found))

    def _stretch(self, rows, turns, a: int, b: int, before: str) -> dict | None:
        block = lines([r for r in rows if a <= r[0] < b], turns, self.tz, self.tracker.shown)
        if not block:
            return None
        text = "\n".join(l for _, l in block)
        talk: dict[str, int] = {}
        for d in turns:
            if d["od"] < b and d["do"] > a:  # a turn begins a little before its first piece (SAID_LEAD)
                talk[d["ime"]] = talk.get(d["ime"], 0) + max(0, min(d["do"], b) - max(d["od"], a))
        user = self._roster() + (f"Dosadašnji sažetak: {before}\n\n" if before else "") + "Deo sednice:\n" + text
        reply = self._summary(user, set(talk))
        errs = check_summary(reply, set(talk), text)
        if errs:
            reply = self._summary(user + "\n\nPrethodni odgovor nije prošao proveru: " + "; ".join(errs)
                                  + ". Napiši ga ponovo po pravilima.", set(talk))
            errs = check_summary(reply, set(talk), text)
        if errs:
            self.kept["greske"] = self.kept.get("greske", 0) + 1
            log.warning("summary left out: %s", "; ".join(errs))
            return None
        return {**reply, "t_od": a, "t_do": b}

    def _summary(self, user: str, speakers: set[str]) -> dict | None:
        """One summary asked for. A speaker named who has no turn of their own in the stretch (one the picture did
        not name, given the floor by the chair) is left out of its list rather than the summary thrown away."""
        try:
            reply = reply_json(self.ask(SUMMARY, user, 16000, "medium"))
        except Exception as exc:
            log.warning("summary not written (%s)", exc)
            return None
        if isinstance(reply, dict) and isinstance(reply.get("govornici"), list):
            reply["govornici"] = [g for g in reply["govornici"] if isinstance(g, dict) and g.get("ime") in speakers]
        return reply

    def _summaries(self, snap, rows, turns, now: float, live: bool) -> None:
        if not rows:
            return
        start = self.kept["delovi"][-1]["t_do"] if self.kept["delovi"] else rows[0][0]
        on = [(d["od"], d["do"]) for d in turns]
        quiet = lambda t: now >= t + BREAK_QUIET and not any(a < t + BREAK_QUIET and b > t + 30 for a, b in on)
        breaks = [e["t"] for e in list(self.tracker.events) if e.get("izvor") == "model"
                  and e.get("vrsta") in ("Pauza", "Kraj rada") and e["t"] >= start and quiet(e["t"])
                  and any(start <= r[0] <= e["t"] for r in rows)]
        ended = not live and now - (snap.get("provereno") or now) >= END_QUIET
        done = self.kept.get("dan") is not None
        cut = None
        if breaks:
            cut = breaks[0] + 1
        elif ended and not done and any(r[0] >= start for r in rows):
            cut = rows[-1][0] + 1
        if cut:
            before = " ".join(p["ukratko"] for p in self.kept["delovi"])
            part = self._stretch(rows, turns, start, cut, before)
            # a stretch that could not be summed up is passed over, so that the next one is not stuck behind it
            self.kept["delovi"].append(part or {"t_od": start, "t_do": cut, "ukratko": "", "izostavljen": True})
            self._save()
        if not done and ended and self.kept["delovi"]:
            parts = [p for p in self.kept["delovi"] if not p.get("izostavljen")]
            if parts:
                speakers = {g["ime"] for p in parts for g in p.get("govornici") or []}
                user = "Sažeci delova dana:\n" + json.dumps(
                    [{k: v for k, v in p.items() if not k.startswith("t_")} for p in parts], ensure_ascii=False)
                try:
                    reply = reply_json(self.ask(DAY, user, 16000, "medium"))
                except Exception as exc:
                    log.warning("the day's summary not written (%s)", exc)
                    reply = None
                errs = check_summary(reply, speakers, user)
                if not errs:
                    self.kept["dan"] = {**reply, "t": int(now)}
                    self._save()
                else:
                    log.warning("the day's summary left out: %s", "; ".join(errs))
                    self.kept["dan"] = {"izostavljen": True, "t": int(now)}
                    self._save()

    def run(self) -> None:
        while not self.halt.is_set():
            try:
                self.step()
            except Exception:
                log.exception("the model's look")
            self.halt.wait(60)
