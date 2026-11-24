"""The chair's measures in the stenographic notes (Rules of Procedure, Articles 108-111), by rule and with no model: a
warning (opomena), taking the floor away (oduzimanje reči), removal from the sitting (udaljenje), and to whom each
went. Read through in full on 23 Nov 2026 (the maintainer: "skeniraj ponovo kome su date opomene i ispravi gde treba"):
every measure the rules found in every convocation's notes, and what the rules missed.

- Each measure pronounced counts, several in one address of the chair too ("изричем опомену Бошку Обрадовићу, ви
  сте хтели, Ивану Костићу изричем опомену"; a list of names is a measure for each), and the same one told again in
  that address is not a new one ("…, тако да имате прву опомену"; "изричем вам опомену. Изричем вам опомену, зато
  што …"); another ordinal, another person or another heckler makes it new.
- It is a measure when said of now: "изричем", "имате (другу) опомену", "добијате опомену", "друга опомена" with
  a name before it, "морам да вам изрекнем опомену", "одузимам вам реч", "изричем / изрекнем … удаљења". Not when
  it is denied, a condition, a threat, a rule quoted or an earlier measure recalled (see the constants).
- To whom: the name the chair addresses in the measure's own part of the sentence or the sentence before (to_whom, the
  notes' "ime"); failing that, likely and with the reason (by_context): the notes themselves show whom the chair
  addresses, who heckles right before or after, whose floor is taken, or who speaks right before and right after.
"""
from __future__ import annotations

import re

from zailiprotiv import mps

_CAP = r"[А-ЯЈЉЊЂЋЏ][а-яјљњђћџ]+"
_END = re.compile(r"[.!?]+(?=[\s\"“”)]*(?:\n|$|\s+[A-ZА-ЯЈЉЊЂЋЏŠĐČĆŽ(„]))|\n")  # not the point in "300.000" or "чл. 106"


def sentence(text: str, start: int, end: int) -> str:
    """The sentence around text[start:end], word for word."""
    before = [m.end() for m in _END.finditer(text, 0, start)]
    after = _END.search(text, end)
    return text[before[-1] if before else 0:after.end() if after else len(text)].strip()


def sentences(text: str) -> list[str]:
    out, last = [], 0
    for m in _END.finditer(text):
        out.append(text[last:m.end()].strip())
        last = m.end()
    return [x for x in out + [text[last:].strip()] if x]


# What the chair says when pronouncing a measure, in the notes of every convocation read (23 Nov 2026). A measure is
# never the one of a rule quoted ("председник … изриче меру удаљења") or an earlier one recalled ("мера … је изречена").
_WARN = r"(?i:\b(?:имате|добијате)\s+(?:(?:прву|другу|трећу|четврту|још|једну|сада|и|две|три)\s+){0,3}опомен)"
_WHO = rf"(?:(?i:колега|колегинице|господине|госпођо|посланиче|посланице)\s+)?{_CAP}(?:\s+{_CAP})?,\s+(?:за вас\s+)?"
MEASURES = [
    ("udaljenje", "Udaljenje sa sednice", re.compile(r"\b(?i:изричем|изрекнем)[^.!?]{0,160}(?i:удаљењ)")),
    ("oduzimanje", "Oduzimanje reči", re.compile(r"(?i:изричем[^.!?]{0,120}одузимањ\w* речи)|(?i:(?:вам )?одузимам (?:вам )?реч)")),
    ("opomena", "Opomena", re.compile(
        r"(?i:изричем[^.!?]{0,60}опомен)|" + _WARN + r"|(?i:\bтако да сте добили\s+(?:\w+\s+)?опомен)"
        # "Колега Божићу, друга опомена.", "Миливојевићу, за вас прва опомена", "Друга опомена Бошку Обрадовићу."
        r"|" + _WHO + r"(?i:прва|друга|трећа|четврта) опомена\b|(?:(?<=[.!?)])\s+|^)(?i:друга|трећа|четврта) опомена\b"
        # "морам да вам изрекнем опомену због добацивања", "желим одмах да изрекнем опомену народном посланику …"
        r"|\b(?i:морам|дужн[аи]? сам|желим)\b[^.!?]{0,40}(?i:\bизрекнем)[^.!?]{0,60}(?i:опомен)")),
]
# Talk about measures is not a measure: "нећу да изричем опомене, нисмо деца", "шта очекујете - да изричем опомене?",
# "могу да почнем да опомињем, изричем опомене, али …", "боље да вас упозорим, него да вам изричем опомену". A denial or
# an unfinished "да" right before the verb, or reprimands in the plural with no number ("две опомене"), is talk.
_DENIED = re.compile(r"(?:\bне|\bнећу да|\bнећемо да|\bне желим да|\bнисам хте\w+ да|(?<!тако )\bда)(?:\s+(?:вам|му|јој|им|сад|сада|још))*\s+$", re.I)
_NONE = re.compile(r"изричем\s+(?:\w+\s+){0,3}(?:никакв|ниједн)", re.I)  # "… изричем сад никакву опомену"
_PLURAL = re.compile(r"изричем(?! (?:вам |му |јој |им )?(?:две|три|четири|\d))[^.!?]{0,30}\bопомене\b", re.I)
# A condition, a reason or a rule, not a measure, for the forms other than "изричем": "добаците још једном и добијате
# опомену", "зато што имате опомену", "Ако наставите …", "… па да вам одузимам реч", "дужна сам да вам изрекнем"
# under an "ако" in its sentence; the future too ("Мораћу …" is not "морам").
_IF = re.compile(r"(?:\bи|\bако|\bкад|\bкада|\bчим|\bзато што|\bјер|\bда ли|\bне|\bни|\bјош једном,?)\s+$"
                 r"|(?<!тако )\bда(?:\s+\w+){0,4}\s+$|\b(?:ако|уколико)\b[^.!?]*$", re.I)
_COND = re.compile(r"\b(?:ако|уколико|ћу|ћете|ћемо|бих|би|нећу|не желим|кад|када|следећи|следећем)\b", re.I)
_OBLIGED = re.compile(r"морам|дужн|желим|треба", re.I)
# "Имам опомену, у реду је" the MP, "Све је у реду, имате опомену" the chair: the earlier one told, not a new one
_CONFIRMS = re.compile(r"имам опомену[^.!?]{0,60}[.!?]?\s*$", re.I)
_ORDINAL = re.compile(r"\b(?:друг[ауе]\b|трећ[ауе]\b|четврт[ауе]\b|поново|још једну|две|три)", re.I)
_ALSO = re.compile(r"\bи (?:вама|вас|њему|њој|њима)\b", re.I)  # the measure goes to another one too
_HECKLE = re.compile(rf"\(((?:{_CAP}[ -]?){{2,4}}):")
_NEAR_HECKLE = re.compile(rf"\(((?:{_CAP}[ -]?){{2,4}}):[^()]{{0,200}}\)[^()]{{0,90}}$")  # the last heckle, right before the measure
_AFTER_HECKLE = re.compile(rf"^[\s.!?…\"“”]*\(((?:{_CAP}[ -]?){{2,4}}):")  # the first heckle right after the measure
_SEVERAL = re.compile(rf"((?:{_CAP}\s+{_CAP}(?:-{_CAP})?(?:,\s*|\s+и\s+)){{1,5}}{_CAP}\s+{_CAP}(?:-{_CAP})?)")
_FLOOR = re.compile(r"реч има|реч дајем|дајем реч|реч добија|пријавите се|изволите", re.I)


def pronouncements(text: str, pattern, kind: str = "opomena"):
    """Every place where a measure is pronounced in the chair's words; not where they only talk of measures."""
    for m in pattern.finditer(text):
        before = text[max(0, m.start() - 80):m.start()]
        said = m.group(0).strip().lower()
        own = text[max([x.end() for x in _END.finditer(text, 0, m.start())], default=0):m.start()]  # the sentence before it
        if said.startswith(("изричем", "вам изричем")):
            if _DENIED.search(before) or _PLURAL.match(text, m.start()) or _NONE.match(text, m.start()):
                continue
        elif _OBLIGED.match(said):  # "морам да вам изрекнем опомену": not under a condition or in the future
            if _COND.search(own) or _DENIED.search(before):
                continue
        elif said.startswith("изрекнем"):  # a removal "осим да … изрекнем меру удаљења"
            if _COND.search(own):
                continue
        else:  # имате / добијате / тако да сте добили / друга опомена / одузимам реч
            if _IF.search(before) or (said.startswith(("имате", "добијате")) and _CONFIRMS.search(text[:m.start()])):
                continue
        yield m


def pronounced(text: str, pattern) -> re.Match | None:
    """The first place where a measure is pronounced in the chair's words, or None."""
    return next(pronouncements(text, pattern), None)


def _stems(word: str) -> set[str]:  # the word as it may stand in another case: "Живковићу", "Јованове", "Марији"
    w = word.lower()
    return {w, w[:-1], w[:-2]} if len(w) > 4 else {w}


def present(speeches: list[dict]) -> dict[str, str]:
    """Who was there, by name with the surname in lower case: the sitting's speakers, as the notes write them, and those
    whose interjections the notes record in brackets and who did not speak (23 Nov 2026: a warning to one of them was
    put to the MP who spoke before)."""
    out = {s["speaker"]: s["speaker"].split()[-1].lower() for s in speeches if not s.get("chair") and s["speaker"].split()}
    have = {mps.key(n) for n in out}
    for s in speeches:
        for name in _HECKLE.findall(s["text"]):
            name = " ".join(name.split())
            if len(name.split()) >= 2 and mps.key(name) not in have:
                have.add(mps.key(name))
                out[name] = name.split()[-1].lower()
    return out


def resolve(words: list[str], people: dict[str, str], measure: dict | None = None) -> list[str]:
    """Whose name the words are (people: name → surname, the surname in lower case), the first name deciding between
    people of one surname when one is said; and, with the surname alone, whoever speaks right before the measure."""
    if not words:
        return []
    said = set().union(*(_stems(w) for w in words))
    named = [n for n, surname in people.items() if surname in said]
    if len(words) > 1:
        # a short first name in another case keeps all but its last letter ("Ани Брнабић" is Ана)
        first = lambda n: {n.split()[0].lower()[:4]} | ({n.split()[0].lower()[:-1]} if 3 <= len(n.split()[0]) <= 4 else set())
        named = [n for n in named if first(n) & ({w.lower()[:4] for w in words} | {w.lower()[:-1] for w in words if 3 <= len(w) <= 4})]
        if len(named) > 1 and len({n.split()[-1].lower() for n in named}) == 1:  # one misspelt: "АЛЕКСАНДР ЈОВАНОВИЋ"
            longest = max(named, key=len)
            if all(abs(len(n) - len(longest)) <= 1 for n in named):
                named = [longest]
    elif len(named) > 1 and measure and measure.get("before") and measure.get("adjacent") and measure["before"]["speaker"] in named:
        named = [measure["before"]["speaker"]]
    return named


# A title the chair addresses someone with; a title in the dative ("колеги Филиповићу") may be whom the speech was
# about, so it counts only right after the measure ("изричем опомену госпођи Радовановић").
_ADDRESSED = re.compile(r"(?i:господине|госпођо|госпођице|колега|колегинице|посланиче|посланице|посланику|посланици|посланик|"
                        r"посланица|(?:опомену|опомене|опомена|речи|седнице),?(?:\s+(?:госпођи|господину|колеги|колегиници|народном посланику|"
                        r"народној посланици|посланику|посланици))?),?\s+"
                        rf"((?:{_CAP}[ -]?){{1,3}})")
_NOMINATIVE = re.compile(r"(?i:посланик|посланица),?\s")  # "народни посланик Миленко Јованов": who, not to whom
# A name and surname right before the measure, in the dative or as the one addressed ("Бошку Обрадовићу изричем
# опомену", "Александар Јовановић Ћута, имате опомену"): two words at least, so that "Дакле, имате" names nobody.
_BEFORE = re.compile(rf"((?:{_CAP}[ -]){{1,2}}{_CAP}),?\s+(?i:(?:(?:вам|сада|сад)\s+)*(?:изричем|имате|добијате|одузимам))")
_TITLES = {"колега", "колегинице", "господине", "госпођо", "госпођице", "посланиче", "посланице", "посланику", "посланици",
           "народни", "народном", "народној", "дакле", "сада", "добро", "молим"}
_VOC_START = re.compile(rf"^\s*({_CAP}(?:\s+{_CAP})?),\s+(?:за вас\s+)?(?i:прва|друга|трећа|четврта) опомена\b")
_STAGE = re.compile(rf"\((?:(?:Народни|Народна)\s+(?:посланик|посланица)\s+)((?:{_CAP}\s+){{1,2}}{_CAP})[^():]*\)")  # "(Народни посланик Борко Пушкић држи …)"


def _addressed_names(text: str) -> list[tuple[re.Match, list[str]]]:
    found = list(_ADDRESSED.finditer(text))
    to_one = [m for m in found if not _NOMINATIVE.match(m.group(0))]
    if to_one and len(to_one) < len(found):
        found = to_one
    return [(m, re.findall(_CAP, m.group(1))) for m in found]


def measures(speeches: list[dict]) -> list[dict]:
    """Every measure pronounced, each on its own. Each has its `span`, the part of its sentence that is its own (up to
    the next measure in the sentence), where its name is looked for; a list of names makes one for each (`name`)."""
    out = []
    for i, s in enumerate(speeches):
        if not s.get("chair"):
            continue
        text = s["text"]
        found, taken = [], set()
        for k, label, pattern in MEASURES:
            for m in pronouncements(text, pattern, k):
                verb = m.start()
                if verb not in taken and not any(a <= m.start() < b for _, _, a, b in found):
                    taken.add(verb)
                    found.append((k, label, m.start(), m.end()))
        found.sort(key=lambda x: x[2])
        kept = []  # the same measure told again in this address is not another one
        for f in found:
            again = next((g for g in reversed(kept) if g[0] == f[0]), None)
            if again and _same(text, again, f):
                continue
            kept.append(f)
        before = next((p for p in reversed(speeches[max(0, i - 6):i]) if not p.get("chair")), None)
        if before and re.search(r"имам опомену", before["text"][-160:], re.I):
            kept = [f for f in kept if not re.match(r"(?:имате|добијате)", text[f[2]:f[2] + 10], re.I)]
        after = speeches[i + 1] if i + 1 < len(speeches) and not speeches[i + 1].get("chair") else None
        if i and kept and out and out[-1]["chair"] is speeches[i - 1] and _told_again(out[-1], text, kept[0]):
            out.pop()  # the notes cut one address in two at a heckle, and the measure is told again with the name
        for j, (k, label, a, b) in enumerate(kept):
            whole = sentence(text, a, b)
            start = text.find(whole, max(0, a - len(whole)))
            start = start if start >= 0 else a
            lo = max(start, kept[j - 1][3]) if j and kept[j - 1][2] >= start else start
            hi = min(start + len(whole), kept[j + 1][2]) if j + 1 < len(kept) else start + len(whole)
            row = {"kind": k, "label": label, "chair": s, "before": before, "after": after,
                   "adjacent": i > 0 and not speeches[i - 1].get("chair"), "at": a,
                   "sentence": whole.lstrip(')"“” '), "span": (lo, hi), "first_in_sentence": lo == start}
            several = _SEVERAL.search(text[a:hi])  # "изричем опомену Александру Јовановићу, Бориславу Новаковићу, …"
            if several:
                for name in re.findall(rf"{_CAP}\s+{_CAP}(?:-{_CAP})?", several.group(1)):
                    out.append({**row, "name": name})
            elif _ALSO.search(text[a:hi]) and (told := _account(speeches, i)):
                # "изричем вам и сад опомену и вама": to more than one, whom the chair names in his own account soon
                # after ("Ја сам дао опомене посланици Ани Брнабић и посланику Миленку Јованову", 19 Nov 2026)
                out.extend({**row, "name": name} for name in told)
            else:
                out.append(row)
    return out


_ACCOUNT = re.compile(rf"(?:(?:[Дд]ао|[Дд]ала|[Ии]зрекао|[Ии]зрекла) сам|[Сс]ам (?:дао|дала|изрекао|изрекла)) опомене\s+((?:(?:народн\w+\s+)?(?:посланици|посланику|посланицима)\s+)?"
                      rf"{_CAP}\s+{_CAP}(?:-{_CAP})?(?:(?:,\s*|\s+и\s+)(?:(?:народн\w+\s+)?(?:посланици|посланику)\s+)?{_CAP}\s+{_CAP}(?:-{_CAP})?){{1,4}})")
ACCOUNT_WITHIN = 30  # speeches after the measure in which the chair's own account of it is looked for, the same day


def _account(speeches: list[dict], i: int) -> list[str]:
    """The names in the chair's own account, soon after, of the warnings just given: "дао сам опомене … и …"."""
    for s in speeches[i + 1:i + 1 + ACCOUNT_WITHIN]:
        if s.get("chair") and s.get("day") == speeches[i].get("day"):
            m = _ACCOUNT.search(s["text"])
            if m:
                return [n for n in re.findall(rf"{_CAP}\s+{_CAP}(?:-{_CAP})?", m.group(1))
                        if not re.match(r"(?i:народн|посланиц|посланик)", n)]
    return []


def _same(text: str, first: tuple, second: tuple) -> bool:
    """Whether the second measure in one address is the first one told again: no other ordinal, no other person
    addressed and no other heckler right before it. (kind, label, start, end) each."""
    if second[0] == "oduzimanje":
        return True
    # the ordinal in the measure's own words, up to the next point or comma ("изричем опомену поново.")
    ordinal = lambda f: (m.group(0).lower()[:4] if (m := _ORDINAL.search(
        text[f[2]:f[3] + len(re.match(r"[^.!?,]*", text[f[3]:]).group(0))])) else "")
    a, b = ordinal(first), ordinal(second)
    if b and b != a:
        return False  # "другу опомену", "још једну": a new one
    if _ALSO.search(text[second[2]:second[3] + len(re.match(r"[^.!?]*", text[second[3]:]).group(0))]):
        return False  # "изричем вам и сад опомену и вама": to someone else as well (19 Nov 2026)
    def own(f):  # its own part of the sentence, up to the other measure when the two are in one ("изричем … Обрадовићу, … Костићу изричем")
        whole = sentence(text, f[2], f[3])
        start = text.find(whole, max(0, f[2] - len(whole)))
        a_, b_ = max(start, 0), max(start, 0) + len(whole)
        other = second if f is first else first
        if other[2] > f[2]:
            b_ = min(b_, other[2])
        else:
            a_ = max(a_, other[3])
        if f is first and second[2] < b_:
            b_ = second[2]
        return text[a_:b_]
    near = lambda f: {mps.key(x.group(1)) for x in [_NEAR_HECKLE.search(text[:f[2]])] if x}
    if near(first) and near(second) and near(first) != near(second):
        return False  # another heckler right before it
    named = lambda f: {w.lower()[:5] for _, ws in _addressed_names(own(f)) + [(m, re.findall(_CAP, m.group(1)))
                                                                             for m in _BEFORE.finditer(own(f))]
                       for w in ws if len(w) > 3}
    x, y = named(first), named(second)
    if y and not x and (near(second) or second[2] - first[3] > 120):
        return False  # named only the second time, some way on: another one ("… (Бошко Обрадовић: …) Бошку Обрадовићу изричем")
    return not (x and y and not (x & y))  # another person named


def _told_again(last: dict, text: str, first: tuple) -> bool:
    """Whether a chair's address begins with the measure the one right before ended with, now with the name of who
    protested: "Изричем вам опомену. (Марко Ђуришић: …)" | "Господине Ђуришићу, изричем вам опомену."."""
    if last["kind"] != first[0] or last.get("name") or _ORDINAL.search(text[first[2]:first[3] + 12]):
        return False
    chair = last["chair"]["text"]
    end = chair.find(last["sentence"], max(0, last["at"] - len(last["sentence"])))
    protest = _AFTER_HECKLE.search(chair[(end if end >= 0 else last["at"]) + len(last["sentence"]):])
    if not protest or _addressed_names(last["sentence"]):
        return False
    said = {w for _, ws in _addressed_names(sentence(text, first[2], first[3])) for w in ws}
    surname = protest.group(1).split()[-1].lower()
    return any(surname in _stems(w) for w in said)


def to_whom(measure: dict, speakers: dict[str, str], everyone: dict[str, str] | None = None) -> str | None:
    """The person a measure went to, when the chair's own sentence names them: someone who spoke or heckled at the
    sitting whose surname stands in the sentence that pronounces the measure ("Господине Живковићу, … изричем вам
    опомену", "Народном посланику Александру Јовановићу изричем опомену"), or failing that in the sentence before
    it. When two share the surname, the first name must be there too, or it is whoever spoke right before. None when
    nobody or more than one fits: the page then shows the chair's words only. `everyone`: everybody who spoke or
    heckled in the convocation, for a name and surname said of someone not at this sitting ("удаљења … Драгану Нинковићу")."""
    everyone = everyone or {}
    if measure.get("name"):
        for people in (speakers, everyone):
            named = resolve(re.findall(_CAP, measure["name"]), people, measure)
            if named:
                return named[0] if len(named) == 1 else None
        return None
    text = measure["chair"]["text"]
    pattern = next(p for k, _, p in MEASURES if k == measure["kind"])
    parts = re.split(r"(?<=[.!?])\s+", text)
    at = next((i for i, x in enumerate(parts) if pattern.search(x)), 0)
    if measure.get("span"):  # the measure's own part of its sentence; the sentence before only for its first measure
        own = text[measure["span"][0]:measure["span"][1]]
        # without the heckles in brackets ("(Милош Парандиловић: Вратите ми време.)"), but with what the notes say of
        # someone ("(Народни посланик Борко Пушкић држи раширен транспарент.)")
        prev = re.sub(r"\([^():]{2,60}:[^()]*\)", " ", text[:measure["span"][0]]) if measure.get("first_in_sentence") else ""
        prev = re.split(r"(?<=[.!?])\s+", prev.strip())[-1] if prev.strip() else ""
        parts, at = [prev, own], 1
    voc = _VOC_START.match(parts[at])
    if voc:
        named = resolve(re.findall(_CAP, voc.group(1)), speakers, measure)
        if len(named) == 1:
            return named[0]
    for part in (parts[at], parts[at - 1] if at else ""):
        # Only a name the chair addresses ("господине …", "посланику …") counts: another name in the sentence may be
        # the person the speech was about ("зато што сте колеги Филиповићу рекли …").
        found = list(_ADDRESSED.finditer(part)) + [m for m in _BEFORE.finditer(part)
                                                    if not _NOMINATIVE.search(part[max(0, m.start() - 12):m.start()])]
        # The case decides: a measure goes to someone in the dative or the vocative ("посланику Новаковићу",
        # "господине Живковићу"). A name in the nominative beside one of those is the next speaker given the floor
        # ("По Пословнику, народни посланик Миленко Јованов, а народном посланику Новаковићу изричем опомену").
        to_one = [m for m in found if not _NOMINATIVE.match(m.group(0))]
        if to_one and len(to_one) < len(found):
            found = to_one
        fits = []
        for m in found:
            if re.match(rf"\s*(?:,|и)\s+{_CAP}\s+{_CAP}", part[m.end():]):
                return None  # several named at once: not one
            words = re.findall(_CAP, m.group(1))
            if m.re is _BEFORE:  # "Колега Милојичићу, изричем": the title is no name, and a surname alone is the other pattern's
                words = [w for w in words if w.lower() not in _TITLES]
                if len(words) < 2:
                    continue
            named = resolve(words, speakers, measure) or (resolve(words, everyone, measure) if len(words) > 1 else [])
            fits += named
        if len(set(fits)) == 1:
            return fits[0]
        if fits or to_one:  # several, or the one addressed is no speaker of the sitting: not someone else instead
            return None
    return None


def _voc(text: str) -> re.Match | None:
    """The last person the chair addresses by name in a text ("Господине Лазовићу, …", "посланика Бошка Обрадовића")."""
    last = None
    for m in re.finditer(r"(?i:господине|госпођо|колега|колегинице|посланиче|посланице|народни посланиче|посланика)\s+"
                         rf"((?:{_CAP}[ -]?){{1,3}})", text):
        last = m
    return last


def by_context(measure: dict, speakers: dict[str, str] | None = None) -> tuple[str, str] | None:
    """Whom a measure without a name is most likely for, with the reason, from the notes themselves, in this order:
    - someone the chair addresses by name in the words before the measure, with no floor given in between;
    - the one person whose interjections the notes record in brackets in the chair's words up to the measure, or the
      one whose interjection stands right before it ("(Борко Пушкић: Желим.) Добро. Изричем вам опомену …"), or the one
      whose protest stands right after it;
    - whose floor is taken: the speaker right before;
    - the speaker right before, when the chair pronounces the measure in the first sentences after them, addressing
      them, with nobody else named and no floor given;
    - the MP who speaks right before the chair's words and goes on right after them.
    Likely, not certain: shown as such, with the reason, and counted apart. None when somebody else is named in the
    chair's words before the measure (it may be theirs)."""
    chair = measure["chair"]["text"]
    at = measure["at"]
    if measure.get("name"):
        return None
    upto = chair[:at + len(measure["sentence"])]
    pre = chair[:at]
    lead = " ".join(sentences(pre)[-3:])[-500:]
    before, adjacent, after = measure.get("before"), measure.get("adjacent"), measure.get("after")
    if speakers:
        m = _voc(lead)
        if m and not _FLOOR.search(lead[m.end():]):
            named = resolve(re.findall(_CAP, m.group(1)), speakers, measure)
            if len(named) == 1:
                return named[0], "predsedavajući ga neposredno pre mere oslovljava po imenu"
            hecklers = {n.strip() for n in _HECKLE.findall(upto)}
            one = [n for n in named if mps.key(n) in {mps.key(x) for x in hecklers}]
            if len(one) == 1:
                return one[0], "predsedavajući ga neposredno pre mere oslovljava po imenu"
            if named or len(re.findall(_CAP, m.group(1))) > 1:
                return None  # somebody is addressed, and who cannot be told
        stage = _STAGE.findall(pre[-400:])
        if len({mps.key(x) for x in stage}) == 1:
            named = resolve(re.findall(_CAP, stage[-1]), speakers, measure)
            if len(named) == 1:
                return named[0], "u beleškama je neposredno pre mere zapisano šta radi"
    heckles = [n.strip() for n in _HECKLE.findall(upto)]
    def whose(name: str) -> bool:
        """Whether the chair pronounces another measure on this person by name later in the same address: this one,
        without a name, is then someone else's ("Изричем вам опомену за ово понашање. … Бошку Обрадовићу изричем опомену.")."""
        if not speakers:
            return False
        later = [m for m in _BEFORE.finditer(chair) if m.start() > at]
        later += [m for m in _ADDRESSED.finditer(chair) if m.start() > at and m.group(0).lower().startswith("опомен")]
        for m in later:
            found = resolve(re.findall(_CAP, m.group(1)), speakers, measure)
            if any(mps.key(x) == mps.key(name) for x in found):
                return True
        return False

    if len({mps.key(n) for n in heckles}) == 1 and not whose(heckles[-1]):
        return heckles[-1], "u beleškama je zapisano da dobacuje dok predsedavajući govori, neposredno pre mere"
    near = _NEAR_HECKLE.search(pre)
    if near and not whose(near.group(1).strip()):
        return near.group(1).strip(), "u beleškama je zapisano da dobacuje neposredno pre nego što predsedavajući izrekne meru"
    end = chair.find(measure["sentence"], max(0, at - len(measure["sentence"])))
    end = (end if end >= 0 else at) + len(measure["sentence"])
    protest = _AFTER_HECKLE.search(chair[end:end + 200])
    if protest:
        return protest.group(1).strip(), "u beleškama je zapisano da se odmah posle mere javlja sa mesta"
    later = _HECKLE.search(chair[end:end + 320])  # not at once, but someone who was already heckling
    if later and not _FLOOR.search(chair[end:end + later.start()]) and before and any(
            mps.key(later.group(1)) == mps.key(n) for n in _HECKLE.findall(before["text"][-200:])):
        return later.group(1).strip(), "u beleškama je zapisano da dobacuje pre mere i javlja se posle nje"
    if not before or not adjacent:
        return None
    # someone named in the measure's own words and not found ("Народном посланику Александру Јовановићу изричем …"):
    # not the one who spoke before
    if speakers and any(len(ws) > 1 and not resolve(ws, {before["speaker"]: before["speaker"].split()[-1].lower()}, measure)
                        for _, ws in _addressed_names(chair[measure["span"][0]:measure["span"][1]])):
        return None
    others = {mps.key(n) for n in heckles} - {mps.key(before["speaker"])}
    if measure["kind"] == "oduzimanje" and not others and not _FLOOR.search(lead):
        return before["speaker"], "reč mu se oduzima odmah posle njegovog govora"
    if not others and not _FLOOR.search(pre) and len(sentences(pre)) <= 9 and len(pre) < 1100:
        return before["speaker"], "mera je izrečena u obraćanju odmah posle ovog govora, pre nego što je reč data drugom"
    if after and not heckles and mps.key(after["speaker"]) == mps.key(before["speaker"]):
        return before["speaker"], "govori neposredno pre i odmah posle obraćanja predsedavajućeg u kom je mera izrečena"
    return None
