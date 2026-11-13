"""What an MP most often says in the debates read: the material for a model's overview, and the check of its reply.

Only speeches made as an MP count: the speaker is on a roll call within two months of the day (a minister is not).
The rules the model writes under are in data/profiles/RULES.md.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from collections import defaultdict
from pathlib import Path

from zailiprotiv import debates, mps

MODEL_WORDS, CUT, LONG = 18000, 700, 120


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[„“”\"'’]", "", text)).strip().lower()


def speeches(root: Path) -> dict[str, list[dict]]:
    """Every speech made as an MP in the notes read, by the speaker's name key (words sorted)."""
    seated: dict[str, list[str]] = defaultdict(list)
    for f in root.glob("*/votes/*.json"):
        votes = json.loads(f.read_text(encoding="utf-8"))["votes"]
        for v in (votes.values() if isinstance(votes, dict) else votes):
            if isinstance(v, dict):
                for _, name, _, _ in v["rows"]:
                    seated[debates.loose(mps.key(name))].append(v["when"][:10])
    days_of = {k: sorted({dt.date.fromisoformat(d) for d in v}) for k, v in seated.items()}
    out: dict[str, list[dict]] = defaultdict(list)
    for f in sorted(root.glob("*/transcripts/*.json")):
        notes = json.loads(f.read_text(encoding="utf-8"))
        conv, sitting = f.parent.parent.name, f.stem
        days = {d["day"]: d for d in notes["days"]}
        iso = lambda d: next((x for x in (d.get("listed_date"), d.get("date")) if re.fullmatch(r"\d{4}-\d\d-\d\d", x or "")), None)
        any_date = next((iso(d) for d in notes["days"] if iso(d)), None)
        for i, s in notes["speeches"].items():
            if s.get("chair"):
                continue
            day = days.get(s["day"]) or (notes["days"][s["day"] - 1] if 0 < s["day"] <= len(notes["days"]) else None)
            date = (day and iso(day)) or any_date
            key = debates.loose(mps.key(s["speaker"]))
            if not date or key not in days_of:
                continue
            at = dt.date.fromisoformat(date)
            if min(abs((d - at).days) for d in days_of[key]) > 60:
                continue  # not seated then: spoke as a member of the Government, or as a guest
            out[key].append({"id": f"{conv}/{sitting}/{i}", "date": (day and iso(day)), "url": day["url"] if day else notes["sitting"],
                             "part": s["part"], "items": [notes["agenda"].get(str(x), "")[:160] for x in s["items"][:3]],
                             "text": s["text"]})
    return out


def selection(own: list[dict]) -> list[dict]:
    """The longest speeches of each sitting in turn, up to MODEL_WORDS, each cut at CUT words."""
    by: dict[str, list[dict]] = defaultdict(list)
    for s in own:
        if len(s["text"].split()) >= LONG:
            by[s["id"].rsplit("/", 1)[0]].append(s)
    for v in by.values():
        v.sort(key=lambda s: -len(s["text"].split()))
    chosen, words = [], 0
    while words < MODEL_WORDS and any(by.values()):
        for v in by.values():
            if v and words < MODEL_WORDS:
                s = dict(v.pop(0))
                w = s["text"].split()
                if len(w) > CUT:
                    s["text"], s["cut"] = " ".join(w[:CUT]), True
                chosen.append(s)
                words += min(len(w), CUT)
    return sorted(chosen, key=lambda s: s["id"])


def check(reply: dict, material: dict) -> list[str]:
    """What is wrong with a model's reply: every point in two speeches or more, its quote word for word in one."""
    by_id = {s["id"]: s for s in material["speeches"]}
    bad = []
    if not 1 <= len(reply.get("tacke", [])) <= 5:
        bad.append("1 do 5 tačaka")
    for t in reply.get("tacke", []):
        ids, q = t.get("govori", []), t.get("citat", {})
        if len(set(ids)) < 2 or any(i not in by_id for i in ids):
            bad.append(f"govori: {ids}")
        if q.get("govor") not in ids or norm(q.get("tekst", "")) not in norm(by_id.get(q.get("govor"), {}).get("text", "")):
            bad.append(f"citat nije doslovan: {q.get('tekst', '')[:60]}")
        elif not 12 <= len(q["tekst"].split()) <= 60:
            bad.append(f"dužina citata: {len(q['tekst'].split())}")
    return bad


def record(reply: dict, material: dict, model: str) -> dict:
    by_id = {s["id"]: s for s in material["speeches"]}
    points = [{"tekst": t["tekst"].strip(), "govora": len(set(t["govori"])),
               "sazivi": sorted({i.split("/")[0] for i in t["govori"]}, key=int),
               "citat": {"tekst": t["citat"]["tekst"].strip(), "date": by_id[t["citat"]["govor"]]["date"],
                         "url": by_id[t["citat"]["govor"]]["url"]}} for t in reply["tacke"]]
    return {"mp": material["mp"], "model": model, "read": len(material["speeches"]), "speeches": material["total_speeches"],
            "sittings": len({s["id"].rsplit("/", 1)[0] for s in material["speeches"]}), "points": points}


# Words an MP uses more than MPs as a whole (no model): a crude stem (the first seven letters) shown by its most
# frequent form, ranked by a smoothed log-odds ratio against all speeches, used in five speeches or more.
STOP = set("""који која које којих којим којима коју којег којем што шта јер али или ако када кад док пре после
још само већ тако такође овај ова ово ови ове оних овог овом овим овде тамо него нити ниједан нико ништа увек никада
сада данас јуче сутра хоћу хоће хоћемо хоћете могу може можемо можете мора морамо морате треба требало требају
бити биће били била било будем будемо будете буде јесте јесу нису нисам ниси нисмо нисте немам нема немамо имамо
имате имају имам имао имала имали имало каже кажем кажемо кажете рекао рекла рекли рећи говорим говори говоримо
говорите говорили говорио питање питања питам одговор господине господо госпођо госпођа поштовани поштоване
поштована колеге колега колегинице колегиница председниче председнице председавајући народни народне народних
посланик посланици посланика посланицима посланичке посланичка скупштина скупштине скупштини скупштину министре
министар министра министарка хвала молим реч речи реплику реплика пословник пословника члан члана чланом став става
амандман амандмана амандмане тачке тачка дневног дневни редa реда закона закон закону законом законе предлог предлога
предлогу републике републици република србије србији србија србију државе држави држава државу грађана грађани
грађанима година године годину годинама један једна једно једног једном једне двеста хиљада милиона милијарди евра
динара процената одсто човек људи људе много мало више мање веома врло највише најмање управо заиста стварно
нешто неко некога некога ниједна свих свима сваки свака свако сваког свој своја своје свога својим своју својих
нашег наша наше наши нашу нашим наших ваша ваше ваши вашу вашим ваших њихов њихова њихове њихових њега њему њима
њихово онда тада овако онако зато зашто због око између према против изнад испод поред уместо осим током кроз
дакле видите најзад значи односно наравно погледајте замислите прича причу причате
""".split())


def stem(w: str) -> str:
    return w[:7]


def words_of(text: str) -> list[str]:
    return [w for w in re.findall(r"[а-яђјљњћџшжчћ]+", text.lower()) if len(w) >= 5 and w not in STOP]


def distinctive(by_mp: dict[str, list[dict]], top: int = 12, min_speeches: int = 5) -> dict[str, list[str]]:
    import math
    from collections import Counter
    total, forms = Counter(), Counter()
    per_mp: dict[str, Counter] = {}
    docs: dict[str, Counter] = {}
    for key, own in by_mp.items():
        c, d = Counter(), Counter()
        for s in own:
            ws = words_of(s["text"])
            for w in ws:
                c[stem(w)] += 1
                forms[(stem(w), w)] += 1
            for st in {stem(w) for w in ws}:
                d[st] += 1
        per_mp[key], docs[key] = c, d
        total.update(c)
    n_all = sum(total.values())
    best_form = {}
    for (st, w), n in forms.items():
        if n > best_form.get(st, ("", 0))[1]:
            best_form[st] = (w, n)
    out = {}
    for key, c in per_mp.items():
        n_mp = sum(c.values())
        if n_mp < 1000:
            continue
        scores = []
        for st, k in c.items():
            if docs[key][st] < min_speeches:
                continue
            rest, n_rest = total[st] - k, n_all - n_mp
            lo = math.log((k + 0.5) / (n_mp - k + 0.5)) - math.log((rest + 0.5) / (n_rest - rest + 0.5))
            scores.append((lo * math.sqrt(k), st))
        out[key] = [best_form[st][0] for _, st in sorted(scores, reverse=True)[:top]]
    return out
