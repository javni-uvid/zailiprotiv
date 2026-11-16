"""Claude's summary of a bill's memorandum: what the proposer says the law is for, what it changes and what it costs.

The summary restates the proposer's own memorandum, attributed to the proposer, and adds nothing: no judgement, no
facts from elsewhere (AGENTS.md, "Laws"). It is written once in Cyrillic, as all Serbian text on the site; the Latin
pages transliterate it. A summary is kept with the model that wrote it and a hash of the memorandum it read, and is
written again only when the memorandum changes.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.request

MODEL = os.environ.get("ZAILIPROTIV_MODEL", "claude-haiku-5-5")
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
# How much of each section the model reads: the reasons and effects matter most; the explanation of each article
# can be very long.
LIMITS = {"reasons": 12000, "explained": 8000, "funds": 3000, "effects": 12000, "urgency": 2000}
FIELDS = ("ukratko", "razlozi", "promene", "sredstva")
# For the laws that get a closer look (the most votes against): the memorandum nearly whole.
DEEP_LIMITS = {key: 60000 for key in LIMITS}

SYSTEM = """Ти си уредник јавног сајта који приказује законе Народне скупштине Србије. Пишеш сажетак образложења \
предлога закона: шта ПРЕДЛАГАЧ наводи као разлоге, шта закон мења и колико средстава је потребно.

Правила, без изузетка:
- Преносиш само оно што пише у датом образложењу. Не додајеш чињенице, бројке ни контекст са стране.
- Све приписујеш предлагачу („предлагач наводи“, „према образложењу“). Ништа не износиш као утврђену чињеницу.
- Не оцењујеш: без придева као што су добар, лош, важан, спорни, контроверзни, хитан (осим ако је реч о хитном \
поступку као процедури), без нагађања о последицама и без политичких оцена.
- Не помињеш странке, посланике ни личности, осим институција које образложење наводи.
- Пишеш српским језиком, ћирилицом, јасно и кратко, за грађанина без правног образовања. Без правничког жаргона \
где постоји обична реч.
- Ако образложење нешто не наводи, то поље остављаш празним (празан низ или празан текст). Не измишљаш.

Одговор је само JSON објекат, без иједне речи пре или после:
{"ukratko": "једна или две реченице: шта закон уређује, према предлагачу",
 "razlozi": ["до четири кратке тачке: разлози које предлагач наводи"],
 "promene": ["до пет кратких тачака: шта закон мења или уводи"],
 "sredstva": "једна реченица: шта предлагач наводи о потребним средствима из буџета"}"""


def material(law: dict, memo: dict, limits: dict | None = None) -> str:
    """What the model reads: the law's title and the memorandum's sections, each cut to its limit."""
    limits = limits or LIMITS
    parts = [f"Наслов закона: {law['title']}"]
    names = {"reasons": "Разлози за доношење", "explained": "Објашњење решења", "funds": "Финансијска средства",
             "effects": "Анализа ефеката", "urgency": "Разлози за хитан поступак"}
    for key, limit in limits.items():
        text = re.sub(r"[ \t]+", " ", memo.get("sections", {}).get(key, "")).strip()
        if text:
            parts.append(f"## {names[key]}\n{text[:limit]}")
    return "\n\n".join(parts)


def fingerprint(text: str) -> str:
    """What a summary was written from: the rules and the material. Not the model: a summary written in a Claude
    session is kept as long as the rules and the memorandum stay the same; its file still names who wrote it."""
    return hashlib.sha256((SYSTEM + "\n" + text).encode("utf-8")).hexdigest()


def record(law: dict, memo: dict, summary: dict, model: str, usage: dict | None = None, deep: bool = False) -> dict:
    """A summary file's content. The fingerprint is always the standard material's, so a deeper summary is kept
    as long as the memorandum and the rules stay the same; "depth" says which material it was written from."""
    return {"model": model, "fingerprint": fingerprint(material(law, memo)), "summary": summary,
            "usage": usage or {}, "law": law["title"], "depth": "deep" if deep else "standard"}


def parse(reply: str) -> dict:
    """The JSON object in the model's reply, with the expected fields only and of the expected types."""
    m = re.search(r"\{.*\}", reply, flags=re.S)
    if not m:
        raise ValueError("no JSON object in the reply")
    data = json.loads(m.group(0))
    out = {
        "ukratko": str(data.get("ukratko") or "").strip(),
        "razlozi": [str(x).strip() for x in data.get("razlozi") or [] if str(x).strip()][:4],
        "promene": [str(x).strip() for x in data.get("promene") or [] if str(x).strip()][:5],
        "sredstva": str(data.get("sredstva") or "").strip(),
    }
    if not out["ukratko"]:
        raise ValueError("empty summary")
    return out


# --- Checks on a finished summary (any model) -------------------------------------------------------------------
# Measured on the summaries already in the repository (Nov 2026, convocations 9-14, `zailiprotiv summaries-check`): the
# proposer's attribution is missing from 564 of Haiku's 2,402 reasons and 46 of the 4,480 Opus wrote in a session
# (a quarter and 1%); small local models also repeat items,
# copy the law's title into "ukratko" and, in two of 21 bills, turned "not in line with the EU's obligations" into
# "in line". Nothing of the last kinds appears in the Claude summaries, so those checks only report.
ATTRIBUTED = re.compile(r"[Пп]редлагач|[Pp]redlagač|[Пп]рема|[Pp]rema|навод|navod|образложењ|obrazloženj|"
                        r"тврди|истиче|сматра|указује")
NOT_IN_LINE = re.compile(r"(?:нису|није) у складу (?:са|с) ([^.,;]{3,80})", re.I)
NEGATION = re.compile(r"\b(?:нису|није|не|нема|непо\w*)\b", re.I)


def unattributed(summary: dict) -> list[str]:
    """The reasons that don't say the proposer states them (AGENTS.md: everything is attributed to the proposer)."""
    return [x for x in summary.get("razlozi", []) if not ATTRIBUTED.search(x)]


def negation_review(summary: dict, memo: dict, title: str = "") -> list[str]:
    """Items saying something is "у складу са X" where the memorandum says it is NOT in line with X: the one
    mistake of a small model that turns a proposer's argument round. Flagged for a person, never edited."""
    source = " ".join(memo.get("sections", {}).values()) + " " + title
    targets = [" ".join(t.lower().split()[:2]) for t in NOT_IN_LINE.findall(source)]
    items = summary.get("razlozi", []) + summary.get("promene", []) + [summary.get("ukratko", "")]
    return [i for i in items if "у складу" in i and not NEGATION.search(i) and any(t and t in i.lower() for t in targets)]


def attribute(summary: dict) -> tuple[dict, int]:
    """Puts "Према предлагачу, " before each reason that has no attribution. Returns the summary and how many."""
    added = 0
    out = []
    for x in summary["razlozi"]:
        if ATTRIBUTED.search(x):
            out.append(x)
        else:
            added += 1
            out.append("Према предлагачу, " + x[0].lower() + x[1:])
    return {**summary, "razlozi": out}, added


def dedupe(summary: dict) -> dict:
    """Each item once (a small model repeats itself); a sentence about funds belongs to "sredstva", not "promene"."""
    def once(items):
        seen, out = set(), []
        for x in items:
            key = re.sub(r"\W+", " ", x.lower()).strip()
            if key and key not in seen:
                seen.add(key)
                out.append(x)
        return out
    promene = [x for x in once(summary["promene"]) if "додатна средства" not in x]
    return {**summary, "razlozi": once(summary["razlozi"]), "promene": promene}


# --- Local models (Ollama), by hand: ZAILIPROTIV_MODEL="ollama:llama3.1:8b" ---------------------------------------
# Tried on the 21 summaries of the Fourteenth convocation that a local model rewrote (Nov 2026), against Haiku's.
# What worked: the memorandum without the EU statement of conformity that is stuck to the reasons (names of the
# signatories and OCR noise, half of the input); Latin script in and out (Cyrillic made the 7B model garble words
# and write Russian ones; the values are put back in Cyrillic, never the keys); no quotation marks in the input (the
# model copies a closing straight quote into the JSON and breaks it); no JSON mode (llama3.1 never stops in it);
# temperature 0 and a cap on the answer. None of this changes the fingerprint: the standard material still stands
# for it, so what the API wrote stays.
_C2L = dict(zip("абвгдђежзијклљмнњопрстћуфхцчџш", ["a", "b", "v", "g", "d", "đ", "e", "ž", "z", "i", "j", "k", "l",
                                                   "lj", "m", "n", "nj", "o", "p", "r", "s", "t", "ć", "u", "f", "h",
                                                   "c", "č", "dž", "š"]))
_L2C = {v: k for k, v in _C2L.items() if len(v) == 1}


def to_latin(text: str) -> str:
    return "".join((_C2L[ch.lower()].capitalize() if ch.isupper() else _C2L[ch.lower()]) if ch.lower() in _C2L else ch
                   for ch in text)


def to_cyrillic(text: str) -> str:
    """Latin back to Cyrillic, letter by letter. Right for the values the model writes; the few words where nj, lj
    or dž are two sounds (injekcija) are not told apart, as in the Cyrillic edition of the site (`cyrillic.py`)."""
    for lat, cyr in (("lj", "љ"), ("nj", "њ"), ("dž", "џ")):
        text = text.replace(lat, cyr).replace(lat.capitalize(), cyr.upper()).replace(lat.upper(), cyr.upper())
    out = []
    for ch in text:
        c = _L2C.get(ch.lower())
        out.append((c.upper() if ch.isupper() else c) if c else ch)
    return "".join(out)


LOCAL_RULES = (" Dodatna pravila: Polje ukratko NIKAD ne sme biti naslov zakona niti njegov prepis. Napiši jednu do dve "
               "cele rečenice koje počinju sa „Predlagač predlaže“ i kažu šta zakon uređuje i koji je glavni razlog "
               "koji predlagač navodi. Stavke u razlozi i promene ne smeju se ponavljati (svaka stavka kaže nešto "
               "drugo). Rečenicu o sredstvima piši samo u polju sredstva, nikad u promene.")


def local_system() -> str:
    return to_latin(SYSTEM).replace("ćirilicom", "latinicom") + LOCAL_RULES


def local_material(law: dict, memo: dict) -> str:
    """What a local model reads: the standard material without the statement of conformity, in Latin, no quotes."""
    sections = dict(memo.get("sections", {}))
    sections["reasons"] = re.split(r"ИЗЈАВА О УСКЛАЂЕНОСТИ", sections.get("reasons", ""))[0]
    return re.sub(r"[„“”\"]", "", to_latin(material(law, {**memo, "sections": sections})))


def ollama_summarize(law: dict, memo: dict, urlopen=urllib.request.urlopen) -> dict:
    """The summary of one bill's memorandum by a local Ollama model, with the checks above applied: repeated items
    removed, missing attributions added, and what a person should look at under "review" (not shown on the site)."""
    model = MODEL.split(":", 1)[1]
    payload = {"model": model, "stream": False, "keep_alive": "30s",
               "options": {"num_ctx": 8192, "temperature": 0, "num_predict": 1200},
               "messages": [{"role": "system", "content": local_system()},
                            {"role": "user", "content": local_material(law, memo)}]}
    req = urllib.request.Request(f"{OLLAMA_BASE_URL}/api/chat", data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=300) as r:
        result = json.loads(r.read().decode("utf-8"))
    answer = result.get("message", {}).get("content", "")
    data = json.loads(re.search(r"\{.*\}", answer, flags=re.S).group(0)) if "{" in answer else {}
    values = {k: ([to_cyrillic(str(x)) for x in v] if isinstance(v, list) else to_cyrillic(str(v)))
              for k, v in data.items() if k in FIELDS}
    summary = dedupe(parse(json.dumps(values, ensure_ascii=False)))
    summary, added = attribute(summary)
    out = record(law, memo, summary, MODEL, {"input": result.get("prompt_eval_count", 0),
                                             "output": result.get("eval_count", 0)})
    review = {"attribution_added": added, "negation": negation_review(summary, memo, law["title"])}
    if added or review["negation"]:
        out["review"] = review
    return out


def summarize(law: dict, memo: dict, client=None) -> dict:
    """Ask the model for the summary of one bill's memorandum (a local one when MODEL starts with "ollama:")."""
    if MODEL.startswith("ollama:"):
        return ollama_summarize(law, memo)
    if client is None:
        import anthropic
        client = anthropic.Anthropic()
    text = material(law, memo)
    reply = client.messages.create(model=MODEL, max_tokens=1500, system=SYSTEM,
                                   messages=[{"role": "user", "content": text}])
    answer = "".join(b.text for b in reply.content if getattr(b, "type", "") == "text")
    return record(law, memo, parse(answer), MODEL,
                  {"input": reply.usage.input_tokens, "output": reply.usage.output_tokens})
