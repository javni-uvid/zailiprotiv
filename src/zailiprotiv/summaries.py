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

MODEL = os.environ.get("ZAILIPROTIV_MODEL", "claude-sonnet-5-5")
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


def summarize(law: dict, memo: dict, client=None) -> dict:
    """Ask the model for the summary of one bill's memorandum."""
    if client is None:
        import anthropic
        client = anthropic.Anthropic()
    text = material(law, memo)
    reply = client.messages.create(model=MODEL, max_tokens=1500, system=SYSTEM,
                                   messages=[{"role": "user", "content": text}])
    answer = "".join(b.text for b in reply.content if getattr(b, "type", "") == "text")
    return record(law, memo, parse(answer), MODEL,
                  {"input": reply.usage.input_tokens, "output": reply.usage.output_tokens})
