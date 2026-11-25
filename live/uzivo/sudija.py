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
from .state_base import SAID_LEAD, _write, speakers_own

log = logging.getLogger("uzivo.sudija")

EVERY = 600  # seconds between calls while the broadcast is on
LAG = 45  # a piece younger than this may still be followed by its sentence's end: it waits for the next call
CLOSED_QUIET = 180  # no broadcast this long after the chair closed the day's work: the day is over (24 Nov 2026)
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
- "Izbor": predsedavajući saopštava da je Skupština nekoga izabrala ili imenovala (glasanje je završeno); "ko" = ime i
  funkcija kako su izgovoreni. Poslanik koji u govoru pominje predlog, kandidate ili raniji izbor NIJE izbor
- "Pauza": predsedavajući proglašava pauzu (ne najavu da će je proglasiti kasnije); "do" = do kada ili koliko, ako je rečeno
- "Nastavak rada": rad se nastavlja posle pauze ili sutradan
- "Mera predsedavajućeg": izrečena opomena, oduzimanje reči ili udaljenje sa sednice; "kome" = ime ako je izgovoreno;
  "napomena" = koja mera. UPOZORENJE NIJE MERA; najava ("dobićete opomenu") nije mera
- "Reč ima": predsedavajući daje reč; "kome" = ime kako je izgovoreno
- "Kraj rada": zaključenje rada za taj dan ili zaključenje sednice

PRAVILA
- Samo ono što je u datom delu izgovoreno; ništa iz znanja, ništa iz pretpostavke.
- Događaj izgovara predsedavajući. Ono što poslanik (red sa imenom) u svom govoru prepričava, najavljuje ili pominje
  nije događaj. U red sa imenom može ući i reč predsedavajućeg (opomena u toku govora): ona jeste događaj.
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

# A stretch's summary lists no speakers (24 Nov 2026): each speech has its own line (rezimei.py)
_STRETCH_RULES = _RULES[:_RULES.index("3. Isto pravilo")] + "3. Ne praviš spisak govornika i ne prepričavaš pojedine govore: to je posebno.\n" + _RULES[_RULES.index("4. Bez navodnika"):]

SUMMARY = f"""Pišeš sažetak dela sednice Narodne skupštine Srbije iz AUTOMATSKOG prepisa (Whisper). Prepis greši u
imenima, brojevima i rečima. Oznaka reda: [HH:MM:SS] Ime (lista): tekst; "{CHAIR}" je predsedavajući ili sala.

{_STRETCH_RULES}
8. "tok": šta je Skupština radila, hronološki: tačke dnevnog reda, pretres, glasanja i odluke (samo kako ih je saopštio
   predsedavajući, ne kako ih poslanik u govoru pominje; sa brojevima kako su
   saopšteni), pauze, mere predsedavajućeg (opomena, oduzimanje reči, udaljenje; upozorenje NIJE mera), svaka stavka
   sa vremenom [HH:MM].
9. Ako je dat "dosadašnji sažetak", ne ponavljaj ga: pišeš samo ovaj deo.
10. Stavka toka koja iznosi rezultat glasanja ima polje "glasanje" sa brojevima kako ih je predsedavajući izgovorio:
   {{"za": n, "protiv": n, "uzdrzano": n, "nevazece": n, "nije_glasalo": n, "glasalo": n, "prisutno": n}}; samo
   ono što je izgovoreno, ostalo null. Brojeve jednog glasanja ne mešaš s brojevima drugog. "glasalo" je broj onih koji
   su glasali: za + protiv + uzdržano (+ nevažeći); "nije_glasalo" nije deo toga. U "sta" nema brojeva glasova.

IZLAZ: samo JSON, bez ikakvog drugog teksta:
{{"od": "HH:MM", "do": "HH:MM", "ukratko": "2 do 4 rečenice: šta je Skupština u ovom delu radila i odlučila",
 "tok": [{{"vreme": "HH:MM", "sta": "...", "glasanje": null}}]}}"""

DAY = f"""Pišeš sažetak celog dana sednice Narodne skupštine Srbije iz sažetaka njegovih delova, napisanih iz
AUTOMATSKOG prepisa. Ne dodaješ ništa čega nema u tim sažecima.

{_RULES}
8. Glasanja prepisuješ iz sažetaka delova sa njihovim poljem "glasanje", brojeve ne menjaš i ne mešaš: svako glasanje
   je odluka sa svojim "glasanje" (isti ključevi kao u delovima); u "sta" nema brojeva glasova.

IZLAZ: samo JSON, bez ikakvog drugog teksta:
{{"naslov": "najviše 60 znakova: JEDNA, glavna odluka dana (izbor ili usvojen akt pre odluke o toku sednice), kao cela
   kratka rečenica kojom bi je neko prepričao (na primer: Petar Petrović je novi ministar), bez nabrajanja, bez brojeva,
   bez ocene i bez tvrdnji govornika; kad odluke nema, tačka o kojoj se raspravljalo",
 "kratko": "jedna ili dve rečenice, najviše 280 znakova: šta je Skupština tog dana odlučila",
 "ukratko": "jedan pasus, 4 do 7 rečenica: tok dana i odluke",
 "odluke": [{{"vreme": "HH:MM", "sta": "odluka ili izbor, bez brojeva glasova", "glasanje": null}}],
 "tok": [{{"vreme": "HH:MM", "sta": "..."}}],
 "govornici": [{{"ime": "...", "lista": "...", "o_cemu": "jedna rečenica, do 35 reči, za ceo dan"}}]}}
"tok" ima najviše 20 stavki; u "govornici" je svaki govornik iz delova i iz spiska govora, jednom, redom prvog javljanja."""


WHOLE = f"""Pišeš sažetak celog dana sednice Narodne skupštine Srbije iz AUTOMATSKOG prepisa (Whisper) celog dana. Prepis
greši u imenima, brojevima i rečima. Oznaka reda: [HH:MM:SS] Ime (lista): tekst; red bez imena nastavlja prethodnog;
"{CHAIR}" je predsedavajući ili sala.

{_RULES}
8. U "govornici" su tačno oni sa datog spiska govornika, svaki jednom, istim imenom i redom.
9. Smisao je preči od kratkoće. Ko nešto poriče, piše se da poriče; ko odgovara na tuđu tvrdnju, piše se da odgovara i
   šta on sam kaže; tuđa tvrdnja o njemu nikad se ne piše kao njegova ni kao činjenica. U red sa imenom može ući i reč
   predsedavajućeg ili drugog poslanika na početku i kraju: ono što očigledno nije govornikovo ne pripisuješ mu. Kad iz
   prepisa nije jasno šta je rekao, piši samo temu.
10. Uz svakog govornika ide "oslonac": jedna ili dve rečenice iz NJEGOVIH redova na kojima tvoja rečenica počiva,
   prepisane SLOVO PO SLOVO, sa greškama prepisa, 8 do 60 reči ukupno, svaka posebno u listi. Samo u "oslonac" ide doslovan
   tekst.
11. Odluke i glasanja samo kako ih je saopštio predsedavajući, ne kako ih poslanik u govoru pominje. Upozorenje NIJE mera.
   Uz meru (opomena, oduzimanje reči) ime piši samo kad ga je predsedavajući izgovorio dok ju je izricao; inače "poslaniku
   ili poslanici" bez imena i bez pogađanja roda.
   Glasanje je stavka u "odluke" sa poljem "glasanje": {{"za": n, "protiv": n, "uzdrzano": n, "nevazece": n,
   "nije_glasalo": n, "glasalo": n, "prisutno": n}}, samo ono što je izgovoreno, ostalo null; brojevi jednog glasanja se ne
   mešaju s drugim. "glasalo" je za + protiv + uzdržano (+ nevažeći). U "sta" nema brojeva glasova.

IZLAZ: samo JSON, bez ikakvog drugog teksta:
{{"naslov": "najviše 60 znakova: JEDNA, glavna odluka dana (izbor ili usvojen akt pre odluke o toku sednice), kao cela
   kratka rečenica kojom bi je neko prepričao (na primer: Petar Petrović je novi ministar), bez nabrajanja, bez brojeva,
   bez ocene i bez tvrdnji govornika; kad odluke nema, tačka o kojoj se raspravljalo",
 "kratko": "jedna ili dve rečenice, najviše 280 znakova: šta je Skupština tog dana odlučila",
 "ukratko": "jedan pasus, 4 do 7 rečenica: tok dana i odluke",
 "odluke": [{{"vreme": "HH:MM", "sta": "odluka ili izbor, bez brojeva glasova", "glasanje": null}}],
 "tok": [{{"vreme": "HH:MM", "sta": "..."}}],
 "govornici": [{{"ime": "...", "lista": "...", "o_cemu": "jedna rečenica, do 35 reči, za ceo dan", "oslonac": ["..."]}}]}}
"tok" ima najviše 20 stavki."""
SPOKE = 120  # seconds on the floor in the day from which a speaker is in its summary


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
        for d in turns:
            if (speakers_own(ts, text, d["od"], d["do"]) if chair else d["od"] - SAID_LEAD - 1 <= ts <= d["do"]):
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


def unsupported(s: dict, said: dict[str, str]) -> list[str]:
    """The speakers of a whole day's summary whose line rests on no sentence of their own: none given, or one not in
    what was heard in their turns, word for word (`said`: by name, all their pieces joined)."""
    out = []
    for g in s.get("govornici") or []:
        if not isinstance(g, dict):
            continue
        given = [norm(str(x)) for x in g.get("oslonac") or []] if isinstance(g.get("oslonac"), list) else []
        body = norm(said.get(g.get("ime"), ""))
        if not given or any(len(x) < 12 or x not in body for x in given):
            out.append(str(g.get("ime")))
    return out


VOTE_KEYS = ("za", "protiv", "uzdrzano", "nevazece", "nije_glasalo", "glasalo", "prisutno")
VOTE_WORDS = (("za", "za"), ("protiv", "protiv"), ("uzdrzano", "uzdržano"), ("nevazece", "nevažeći"),
              ("glasalo", "glasalo"), ("nije_glasalo", "nije glasalo"), ("prisutno", "prisutno"))


def vote_of(raw) -> dict | None:
    """A vote as the model gave it, kept to the known keys with whole non-negative numbers; None when nothing is left."""
    if not isinstance(raw, dict):
        return None
    got = {k: raw[k] for k in VOTE_KEYS if isinstance(raw.get(k), int) and not isinstance(raw.get(k), bool) and raw[k] >= 0}
    return got or None


def vote_errors(v: dict) -> list[str]:
    """What does not add up in one vote (21 Nov 2026, the maintainer: for + against + abstained must equal those who
    voted). Checked only with the numbers that were said: za + protiv + uzdrzano (+ nevazece) = glasalo; glasalo +
    nije_glasalo = prisutno; no part is more than the whole it belongs to."""
    parts = [v.get(k) for k in ("za", "protiv", "uzdrzano", "nevazece")]
    said = sum(x for x in parts if x is not None)
    errs = []
    if v.get("glasalo") is not None:
        if None not in parts[:3] and said != v["glasalo"]:
            errs.append("za + protiv + uzdržano" + (" + nevažeći" if parts[3] is not None else "")
                        + f" je {said}, a glasalo je {v['glasalo']}")
        elif said > v["glasalo"]:
            errs.append(f"delovi glasanja ({said}) su veći od broja glasalih ({v['glasalo']})")
    if v.get("prisutno") is not None:
        if v.get("glasalo") is not None and v.get("nije_glasalo") is not None \
                and v["glasalo"] + v["nije_glasalo"] != v["prisutno"]:
            errs.append(f"glasalo {v['glasalo']} + nije glasalo {v['nije_glasalo']} nije prisutno {v['prisutno']}")
        elif v["prisutno"] < max(said, v.get("glasalo") or 0):
            errs.append("prisutnih je manje nego glasalih")
    return errs


def vote_text(v: dict) -> str:
    """One vote told the same way every time: "za 136, protiv 0, uzdržano 0, glasalo 136, nije glasalo 98, prisutno 234"."""
    return ", ".join(f"{label} {v[k]}" for k, label in VOTE_WORDS if k in v)


def _loose(v: dict, e: dict) -> list[str]:
    """Figures of a vote that stand in the entry's words as well (they belong in the vote's own field only)."""
    return sorted({str(n) for n in v.values() if n > 9} & set(re.findall(r"\d+", str(e.get("sta") or ""))))


def vote_entries(s: dict) -> list[dict]:
    """The entries of a summary ("odluke", "tok") that carry a vote."""
    return [e for k in ("odluke", "tok") for e in (s.get(k) if isinstance(s.get(k), list) else [])
            if isinstance(e, dict) and e.get("glasanje") is not None]


def check_votes(s: dict | None) -> list[str]:
    """Votes that do not add up, or whose figures stand in the entry's words too. [] when all is well."""
    errs = []
    for e in vote_entries(s or {}):
        v = vote_of(e["glasanje"])
        if v is None:
            continue
        where = f"glasanje u {e.get('vreme')!r}: "
        errs += [where + x for x in vote_errors(v)]
        if _loose(v, e):
            errs.append(where + f"brojevi glasova {', '.join(_loose(v, e))} su u tekstu stavke, a treba samo u polju glasanje")
    return errs


def settle_votes(s: dict) -> dict:
    """The summary with its votes made fit to show: the figures normalised and a line of words for each vote that
    adds up (`glasovi`); one that still does not goes without its figures, and the entry is dropped when its own words
    carry them (better no line than a wrong one)."""
    for key in ("odluke", "tok"):
        if not isinstance(s.get(key), list):
            continue
        kept = []
        for e in s[key]:
            if not isinstance(e, dict) or e.get("glasanje") is None:
                kept.append(e)
                continue
            v = vote_of(e["glasanje"])
            bad = v is None or vote_errors(v)
            e.pop("glasanje", None)
            if not bad:
                e["glasanje"], e["glasovi"] = v, vote_text(v)
            elif v and _loose(v, e):
                continue
            kept.append(e)
        s[key] = kept
    return s


def ask_claude(system: str, user: str, max_tokens: int = 16000, effort: str = "low", model: str = "") -> str:
    """One call to the model: the rules as a cached system prompt, the material as the message. A long one (the whole
    day, DAY_MODEL) is streamed, as it takes minutes."""
    import anthropic
    long = bool(model)
    client = anthropic.Anthropic(api_key=config.MODEL_KEY, max_retries=3, timeout=600 if long else 120)
    call = dict(model=model or config.MODEL, max_tokens=max_tokens,
                system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": user}], output_config={"effort": effort})
    if long:
        with client.messages.stream(**call) as stream:
            reply = stream.get_final_message()
    else:
        reply = client.messages.create(**call)
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
        self.began = time.time()  # when this run began: after a restart the last frame is not known (_summaries)

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
        whole = self.kept.get("dan")
        self.kept["model"] = (whole.get("model") if isinstance(whole, dict) else "") or config.MODEL
        f = self._file(self.day)
        if f:
            try:
                _write(f, self.kept)
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
        from .obavesti import to_tell
        if not (self.bell and to_tell(self.kept.get("dan"), now, self.tz)):
            return
        if not self.kept.get("javljeno"):
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
        wrong = check_votes(reply) if not errs else []
        if errs or wrong:
            reply = self._summary(user + "\n\nPrethodni odgovor nije prošao proveru: " + "; ".join(errs + wrong)
                                  + ". Napiši ga ponovo po pravilima.", set(talk))
            errs = check_summary(reply, set(talk), text)
        if not errs:
            settle_votes(reply)  # a vote that still does not add up goes out without its figures, not the summary
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

    def _whole(self, rows, turns) -> dict | None:
        """The day's summary by DAY_MODEL from the whole transcript; None when it is off or did not work (the day is
        then told from the stretches, as before). What each speaker's line rests on is kept apart, for the maintainer's
        mail only (/data/osnova): the automatic transcript is never a quote, so it goes to no page and no reader."""
        if not config.DAY_MODEL:
            return None
        block = lines(rows, turns, self.tz, self.tracker.shown)
        text = "\n".join(l for _, l in block)
        talk: dict[str, int] = {}
        for d in turns:
            talk[d["ime"]] = talk.get(d["ime"], 0) + max(0, d["do"] - d["od"])
        first = {d["ime"]: d["od"] for d in sorted(turns, key=lambda d: -d["od"])}
        need = sorted((n for n, s in talk.items() if s >= SPOKE), key=lambda n: first[n])
        lists = {d["ime"]: d.get("lista") or "" for d in turns}
        said: dict[str, str] = {}
        for ts, piece, chair in rows:
            who = next((d["ime"] for d in turns if (speakers_own(ts, piece, d["od"], d["do"]) if chair
                                                    else d["od"] - SAID_LEAD - 1 <= ts <= d["do"])), None)
            if who:
                said[who] = said.get(who, "") + " " + self.tracker.shown(piece)
        user = (self._roster() + "Govornici za spisak \"govornici\":\n" + "\n".join(f"- {n} ({lists[n] or 'bez liste'})" for n in need)
                + "\n\nPrepis dana:\n" + text)

        def look(s):
            hard = check_summary({k: v for k, v in (s or {}).items() if k != "govornici"} | {"govornici": [
                {k: v for k, v in g.items() if k != "oslonac"} for g in (s or {}).get("govornici") or [] if isinstance(g, dict)]}, set(need), text) if s else ["nema odgovora"]
            names = [g.get("ime") for g in (s or {}).get("govornici") or [] if isinstance(g, dict)]
            soft = [f"govornik {n!r} nije na spisku" for n in need if n not in names]
            weak = unsupported(s, said) if s else []
            soft += [f"oslonac za {n!r} nije doslovno u njegovim redovima" for n in weak]
            return hard, soft + check_votes(s), weak

        best = None
        note = ""
        for _ in range(2):
            try:
                # 100,000 and "medium": on 24 Nov 2026 the reply was cut off at 32,000 with "high" (the reasoning counts), and the
                # day fell back to the stretches; with these it took 20,000
                s = reply_json(self.ask(WHOLE, user + note, 100000, "medium", config.DAY_MODEL))
            except Exception as exc:
                log.warning("the whole day not written (%s)", exc)
                break
            hard, soft, weak = look(s)
            if not hard and (best is None or len(soft) < best[1]):
                best = (s, len(soft), weak)
            if not hard and not soft:
                break
            note = "\n\nPrethodni odgovor nije prošao proveru: " + "; ".join(hard + soft) + ". Napiši ga ponovo po pravilima."
        if best is None:
            log.warning("the whole day's summary left out")
            return None
        s, _, weak = best
        basis = {g["ime"]: g.get("oslonac") or [] for g in s.get("govornici") or [] if isinstance(g, dict)}
        for g in s.get("govornici") or []:
            if isinstance(g, dict):
                g.pop("oslonac", None)
                g["lista"] = lists.get(g.get("ime"), g.get("lista", ""))
        f = self._file(self.day)
        if f:
            try:
                _write(f.parent.parent / "osnova" / f.name, {"model": config.DAY_MODEL, "oslonac": basis, "bez_oslonca": weak})
            except OSError:
                pass
        return s

    def _written(self) -> None:
        """The day's summary taken from the day's file when one stands there that this run did not write (made by hand,
        or by a run before): looked for before the model is asked, so the day is not written twice nor a written one
        lost (24 Nov 2026)."""
        f = self._file(self.day)
        try:
            kept = json.loads(f.read_text(encoding="utf-8")) if f and f.exists() else {}
        except (OSError, ValueError):
            return
        if isinstance(kept.get("dan"), dict):
            self.kept["dan"] = kept["dan"]
            if len(kept.get("delovi") or []) >= len(self.kept["delovi"]):
                self.kept["delovi"] = kept["delovi"]
            self.tracker.use_summary(self.day, self.kept)

    def _summaries(self, snap, rows, turns, now: float, live: bool) -> None:
        if not rows:
            return
        start = self.kept["delovi"][-1]["t_do"] if self.kept["delovi"] else rows[0][0]
        on = [(d["od"], d["do"]) for d in turns]
        quiet = lambda t: now >= t + BREAK_QUIET and not any(a < t + BREAK_QUIET and b > t + 30 for a, b in on)
        breaks = [e["t"] for e in list(self.tracker.events) if e.get("izvor") == "model"
                  and e.get("vrsta") in ("Pauza", "Kraj rada") and e["t"] >= start and quiet(e["t"])
                  and any(start <= r[0] <= e["t"] for r in rows)]
        # A run begun after the broadcast ended knows no frame of it (24 Nov 2026: restarted at 19:31, two minutes after the
        # end; "no frame yet" was taken for now, so the day would never have ended, nor its mail gone): then the day ends
        # END_QUIET after the last word written down, and no sooner than END_QUIET after the run began (a restart in a break
        # finds its stream again within that).
        # The last frame is the run before's when this one read none (kept with the day): a restart after the end does not
        # begin the wait anew. And when the chair closed the day's work (the model's "Kraj rada", nobody at the rostrum and
        # nearly nothing said after it), CLOSED_QUIET is enough (the maintainer: the mail sooner).
        last = snap.get("provereno") or getattr(self.tracker, "frame_before", 0) or max(rows[-1][0], self.began)
        closed = next((e["t"] for e in reversed(list(self.tracker.events))
                       if e.get("izvor") == "model" and e.get("vrsta") == "Kraj rada"), None)
        if closed is not None and (any(b > closed + 60 for _, b in on)
                                   or sum(len(r[1].split()) for r in rows if r[0] > closed + 60) > 40):
            closed = None  # the work went on after it
        ended = not live and now - last >= (CLOSED_QUIET if closed is not None else END_QUIET)
        if ended and self.kept.get("dan") is None:
            self._written()
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
            whole = self._whole(rows, turns)
            if whole:
                self.kept["dan"] = {**settle_votes(whole), "t": int(now), "model": config.DAY_MODEL}
                self._save()
                return
            parts = [p for p in self.kept["delovi"] if not p.get("izostavljen")]
            if parts:
                lined = [{"ime": d["ime"], "lista": d.get("lista") or "", "o_cemu": d["rezime"]}
                         for d in sorted(turns, key=lambda d: d["od"]) if d.get("rezime")]
                speakers = {g["ime"] for p in parts for g in p.get("govornici") or []} | {g["ime"] for g in lined}
                user = "Sažeci delova dana:\n" + json.dumps(
                    [{k: v for k, v in p.items() if not k.startswith("t_")} for p in parts], ensure_ascii=False)
                if lined:  # what each spoke about, speech by speech (rezimei.py): the stretches list no speakers
                    user += "\nGovori, redom:\n" + json.dumps(lined, ensure_ascii=False)
                try:
                    reply = reply_json(self.ask(DAY, user, 16000, "medium"))
                except Exception as exc:
                    log.warning("the day's summary not written (%s)", exc)
                    reply = None
                errs = check_summary(reply, speakers, user)
                wrong = check_votes(reply) if not errs else []
                if wrong:
                    log.warning("the day's votes asked again: %s", "; ".join(wrong))
                    try:
                        reply = reply_json(self.ask(DAY, user + "\n\nPrethodni odgovor nije prošao proveru: "
                                                    + "; ".join(wrong) + ". Napiši ga ponovo po pravilima.", 16000, "medium"))
                    except Exception as exc:
                        log.warning("the day's summary not written (%s)", exc)
                        reply = None
                    errs = check_summary(reply, speakers, user)
                if not errs:
                    self.kept["dan"] = {**settle_votes(reply), "t": int(now)}
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
