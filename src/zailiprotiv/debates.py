"""What was said in the Assembly about a law: the arguments for and against, attributed, and verbatim quotes.

The material is the stenographic notes of the law's sitting (transcripts.py): every speech on the law's amendments,
and, from the debate in principle, the whole of it when the law was debated alone, or, when it was debated together
with other items, the paragraphs that name the law or its subject. Each speaker is given with their parliamentary
group as in the roll call nearest in time (ministers and others on no roll call apart). A model writes the summary;
each quote it gives is checked against the notes word for word and dropped if not found.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from collections import Counter, defaultdict

from zailiprotiv import mps
from zailiprotiv.translit import latin

OUTSIDE = "није на списку гласања (члан Владе или други)"
LIMIT = 30000  # words of material at most, half for each part
FIELDS = ("predlagac", "podrska", "zamerke", "citati")

SYSTEM = """Ти си уредник јавног сајта који приказује законе Народне скупштине Србије. Из стенографских белешки \
расправе пишеш кратак преглед: шта су у расправи о ОВОМ закону рекли предлагач и представници Владе, шта посланици \
који закон подржавају, а шта посланици који му се противе.

Правила, без изузетка:
- Само оно што пише у датим белешкама и што се тиче овог закона. Ако је расправа била заједничка са другим \
тачкама, изоставиш све што се тиче других закона.
- Све приписујеш: свака тачка почиње тиме ко то тврди („Предлагач наводи…“, „Посланици групе X оцењују…“), са \
називом посланичке групе тачно како је дат уз говорника. Ништа не износиш као утврђену чињеницу.
- Не оцењујеш ко је у праву, не додајеш контекст са стране, не преносиш увреде, лична препуцавања ни оцене о \
личностима; само аргументе о закону: шта мења, коме и зашто то помаже или штети, шта није у реду са поступком.
- Обе стране добијају исту пажњу. Ако нека страна у белешкама не износи аргументе о закону, њено поље остаје празно.
- Цитати су ДОСЛОВНИ: реч по реч из белешки, 10 до 40 речи, о закону (не увреде). Највише један цитат по \
посланичкој групи; бираш цитате са обе стране, и предлагача ако је говорио. Уз цитат је говорник, група и дан, \
тачно како пише у материјалу.
- Српски језик, ћирилица, јасно и кратко, за грађанина.

Одговор је само JSON објекат, без иједне речи пре или после:
{"predlagac": ["до три тачке: шта предлагач и Влада наводе у расправи"],
 "podrska": ["до три тачке: аргументи посланика који подржавају закон, са групом"],
 "zamerke": ["до пет тачака: замерке посланика који се противе, са групом"],
 "citati": [{"govornik": "ИМЕ ПРЕЗИМЕ", "grupa": "група", "dan": 1, "tekst": "дословни цитат"}]}"""

# Words of every bill's name, which say nothing about its subject (Latin, cut to five letters).
STOP = {w[:5] for w in "zakon zakona zakonom predlog predloga predlogu izmenama izmeni dopunama dopuni republike srbije "
        "godine potvrđivanju sporazuma između vlade kojim kojih ovog ovoga narodne skupštine".split()}


def seats(votes: dict) -> dict[str, list[tuple[str, str]]]:
    """Each MP's group at each roll call: key → [(when, group as written)], in time order."""
    out: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for v in sorted(votes.values(), key=lambda v: v["when"]):
        for _, name, _, group in v["rows"]:
            out[mps.key(name)].append((v["when"], group or "без посланичке групе"))
    return out


def group_at(seated: list[tuple[str, str]], when: str, days: int = 60) -> str | None:
    """The group of the roll call nearest in time, if within `days`: a minister who was an MP before is not one now."""
    at = dt.datetime.fromisoformat(when[:19])
    near = [(abs(dt.datetime.fromisoformat(w[:19]) - at), g) for w, g in seated]
    best = min(near, default=None)
    return best[1] if best and best[0].days <= days else None


def speaker_groups(notes: dict, final: dict, seated: dict) -> dict[str, str]:
    groups = {mps.key(r[1]): r[3] or "без посланичке групе" for r in final["rows"]}
    for sp in notes["speeches"].values():
        k = mps.key(sp["speaker"])
        if k not in groups:
            groups[k] = group_at(seated.get(k, []), final["when"]) or OUTSIDE
    return groups


def stems(text: str) -> set[str]:
    """Words of five letters or more, in Latin, cut to five letters: "Генералштаба", "Generalštab" → "gener"."""
    return {w[:5] for w in re.findall(r"[a-zčćšžđ]{5,}", latin(text).lower()) if w[:5] not in STOP}


def document_frequency(bills: dict) -> tuple[Counter, int]:
    """In how many bills' reasons each stem appears, to tell a law's own subject from words every memorandum uses."""
    df: Counter = Counter()
    for bill in bills.values():
        df.update(stems(bill.get("sections", {}).get("reasons", "")[:5000]))
    return df, max(1, len(bills))


def keywords(law: dict, bill: dict, others: list[str], df: Counter, n: int, top: int = 25) -> set[str]:
    """Stems that name this law's subject: its title's words not shared with other items on the agenda, and the
    words of its memorandum's reasons that few other memoranda use."""
    common = Counter(s for t in others for s in stems(t))
    title = {s for s in stems(law.get("item") or "") | stems(law["title"]) if common[s] <= 1}
    reasons = bill.get("sections", {}).get("reasons", "")[:5000]
    tf = Counter(w[:5] for w in re.findall(r"[a-zčćšžđ]{5,}", latin(reasons).lower()) if w[:5] not in STOP)
    rare = sorted((s for s in tf if df[s] <= max(2, n // 40) and tf[s] >= 2), key=lambda s: (-tf[s], s))[:top]
    return title | set(rare)


def material(law: dict, bill: dict, notes: dict, final: dict, seated: dict, item: int,
             df: tuple[Counter, int] = (Counter(), 1)) -> str:
    """What the model reads: the law, and the speeches about it, each with speaker, group and day: the debate in
    principle first (where the proposer presents the bill), then the amendments, each part up to half the limit."""
    groups = speaker_groups(notes, final, seated)
    others = [t for n, t in notes["agenda"].items() if int(n) != item]
    keys = keywords({**law, "item": notes["agenda"].get(str(item), "")}, bill, others, *df)
    detail = [s for s in notes["speeches"].values() if s["part"] == "detail" and s["items"] == [item]]
    general = [s for s in notes["speeches"].values() if s["part"] == "general" and item in s["items"]]
    alone = all(s["items"] == [item] for s in general)
    parts = [f"Закон: {law['title']}", f"Тачка дневног реда {item}: {notes['agenda'].get(str(item), '')}"]
    if not alone:
        parts.append(f"Начелна расправа била је заједничка за тачке {min(general[0]['items'])}–"
                     f"{max(general[0]['items'])}; из ње су дати само пасуси који помињу овај закон или његову тему.")
    def add(section: str, speeches: list[dict], whole: bool) -> None:
        words = 0
        parts.append(f"\n## {section}")
        for s in speeches:
            if s["chair"]:
                continue
            paras = s["text"].split("\n")
            if not whole:
                paras = [p for p in paras if stems(p) & keys]
            if not paras or words > LIMIT // 2:
                continue
            text = "\n".join(paras)
            words += len(text.split())
            who = groups.get(mps.key(s["speaker"]), OUTSIDE)
            parts.append(f"[{s['speaker']} | {who} | дан {s['day']}]\n{text}")

    add("Начелна расправа", general, alone)
    add("Расправа о амандманима на овај закон", detail, True)
    return "\n".join(parts)


def fingerprint(text: str) -> str:
    return hashlib.sha256((SYSTEM + "\n" + text).encode("utf-8")).hexdigest()


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[„“”\"'’]", "", text)).strip().lower()


def parse(reply: str | dict, notes: dict) -> tuple[dict, list[str]]:
    """The model's answer with the expected fields, and the quotes it gave that are not in the notes word for word
    (those are dropped)."""
    data = reply if isinstance(reply, dict) else json.loads(re.search(r"\{.*\}", reply, flags=re.S).group(0))
    said = {s["day"]: [] for s in notes["speeches"].values()}
    for s in notes["speeches"].values():
        said[s["day"]].append((s["speaker"], norm(s["text"])))
    out = {k: [str(x).strip() for x in data.get(k) or [] if str(x).strip()][:n]
           for k, n in (("predlagac", 3), ("podrska", 3), ("zamerke", 5))}
    quotes, dropped = [], []
    for q in data.get("citati") or []:
        text, who = str(q.get("tekst", "")).strip().strip("„“\""), str(q.get("govornik", "")).strip()
        day = int(q.get("dan") or 0)
        found = next((d for d in ([day] if day in said else []) + sorted(said)
                      for sp, t in said[d] if norm(text) in t and mps.key(sp) == mps.key(who)), None)
        if found is None or not 6 <= len(text.split()) <= 60:
            dropped.append(text)
            continue
        quotes.append({"govornik": who, "grupa": str(q.get("grupa", "")).strip(), "dan": found, "tekst": text})
    out["citati"] = quotes[:6]
    if not (out["predlagac"] or out["podrska"] or out["zamerke"]):
        raise ValueError("empty")
    return out, dropped


def record(law: dict, text: str, debate: dict, model: str, dropped: list[str]) -> dict:
    return {"law": law["title"], "model": model, "fingerprint": fingerprint(text), "debate": debate,
            "dropped_quotes": len(dropped)}


def speaker_name(name: str) -> str:
    """"МИЛЕНКО ЈОВАНОВ" → "Milenko Jovanov"."""
    return " ".join(w if not w.isupper() else "-".join(p.capitalize() for p in w.split("-"))
                    for w in latin(name).split())
