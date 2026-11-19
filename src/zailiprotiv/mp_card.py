"""The card at the top of an MP's page: a few facts, each one sentence with its number first.

Every fact is computed by the same rule for every MP and says only what the roll calls and the notes say: no label,
no rank of our own, no judgement (principles 1 and 6). A fact the MP's data can't support is left out, not shown as
zero. The sentences link to where the number comes from.
"""
from __future__ import annotations

from collections import Counter
from html import escape

from markupsafe import Markup

WORDS_PER_MINUTE = 130  # speech at an ordinary pace, to put the words read into hours; said on the card


def _n(x: int) -> str:
    return f"{x:,}".replace(",", ".")


def _plural(n: int, one: str, few: str, many: str) -> str:
    d, h = n % 10, n % 100
    return one if d == 1 and h != 11 else few if 2 <= d <= 4 and not 12 <= h <= 14 else many


def _end(text: str) -> str:
    """A sentence's end: a date already ends with its period."""
    return text if text.endswith(".") else text + "."


def _a(href: str, text: str, more: bool = True) -> str:
    """A link; `more` marks one that leads on from the sentence ("Koji su to zakoni"), which a plain copy of the
    sentence leaves out (the live page's lines), unlike a name inside it."""
    return f'<a{" class=\"more\"" if more else ""} href="{escape(href)}">{escape(text)}</a>' if href else escape(text)


def facts(*, slug: str, by_conv: list[dict], floor: list[dict], exchanges: list[dict], apart: int, voted: int,
          busiest: tuple[int, str, str] | None, words: list[str], day, given_first) -> list[dict]:
    """[{"n": the number, "text": the rest of the sentence (markup)}], in a fixed order."""
    out = []

    def add(n, text):
        out.append({"n": n, "text": Markup(text)})

    # Presence, in the newest convocation where the Assembly lists the absent.
    shown = [c for c in by_conv if c.get("present")]
    if shown:
        c = shown[0]
        here, of = c["present"]
        median = f"; polovina poslanika ima više od {round(100 * c['median'])}%" if c.get("median") else ""
        add(f"{round(100 * here / of)}%", f"prisustva na konačnim glasanjima ({escape(c['name'])} saziv: {_n(here)} od "
            f"{_n(of)}{median}).")
    # Votes unlike the group's majority.
    if voted >= 10 or apart:  # "never" said of one or two votes says nothing
        # worded without a verb in the past, which in Serbian would say whether the MP is a man or a woman
        if apart:
            add(_n(apart), f"{_plural(apart, 'glas drugačiji', 'glasa drugačija', 'glasova drugačijih')} od većine svoje "
                f"grupe, od {_n(voted)} glasova za, protiv ili uzdržan. {_a('#drugacije', 'Koji su to zakoni')}")
        else:
            add("Nijedan", f"glas drugačiji od većine svoje grupe ({_n(voted)} {_plural(voted, 'glas', 'glasa', 'glasova')} "
                f"za, protiv ili uzdržan).")
    # The floor: speeches, words, the longest speech, the busiest day, exchanges and with whom.
    speeches = sum(x["speeches"] for x in floor)
    words_ = sum(x["words"] for x in floor)
    if speeches:
        hours = words_ / WORDS_PER_MINUTE / 60
        span = f"oko {round(hours)} {_plural(round(hours), 'sat', 'sata', 'sati')}" if hours >= 1.5 else f"oko {round(hours * 60)} minuta"
        add(_n(speeches), f"{_plural(speeches, 'govor', 'govora', 'govora')} u sali, {_n(words_)} "
            f"{_plural(words_, 'reč', 'reči', 'reči')}: {span} govora, pri {WORDS_PER_MINUTE} reči u minuti.")
    longest = max((x["longest"] for x in floor if x.get("longest")), key=lambda l: l["words"], default=None)
    if longest and speeches > 1:
        when = f", {day(longest['date'])}" if longest.get("date") else ""
        text = escape(_end(f"{_plural(longest['words'], 'reč', 'reči', 'reči')} u najdužem govoru{when}"))
        add(_n(longest["words"]), f"{text} {_a(longest['url'], 'Pročitaj ga')}" if longest.get("url") else text)
    if busiest and busiest[0] > 1:
        n, date, url = busiest
        text = escape(_end(f"{_plural(n, 'govor', 'govora', 'govora')} u jednom danu, najviše: {day(date)}"))
        add(_n(n), f"{text} {_a(url, 'Ti govori')}" if url else text)
    if exchanges:
        partners = Counter()
        pages = {}
        for e in exchanges:
            other = e["b"] if e["a"].get("slug") == slug else e["a"]
            partners[other["name"]] += 1
            pages[other["name"]] = other.get("slug", "")
        top = sorted(partners.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
        names = ", ".join(f"{_a(f'{pages[n]}.html' if pages[n] else '', given_first(n), more=False)} ({k})" for n, k in top)
        add(_n(len(exchanges)), f"{_plural(len(exchanges), 'razmena', 'razmene', 'razmena')} replika; najviše sa: {names}. "
            f"{_a('#replike', 'Sve razmene')}")
    measures = sum(x["measures"] + x["measures_likely"] for x in floor)
    harsh = sum(x["harsh"] for x in floor)
    if measures:
        add(_n(measures), f"{_plural(measures, 'mera predsedavajućeg izrečena', 'mere predsedavajućeg izrečene', 'mera predsedavajućeg izrečenih')} ovom poslaniku. "
            f"{_a('#mere', 'Koje i zašto')}")
    if harsh:
        add(_n(harsh), f"{_plural(harsh, 'teška reč sa našeg spiska, izgovorena', 'teške reči sa našeg spiska, izgovorene', 'teških reči sa našeg spiska, izgovorenih')} u sali. "
            f"{_a('#reci', 'U kojim rečenicama')}")
    # The group, other than the MP's own, voting most alike, in the newest convocation with the count.
    for c in by_conv:
        others = [a for a in c.get("agree", []) if not a["own"]]
        if others:
            a = others[0]
            add(f"{round(100 * a['share'])}%", f"glasova isto kao većina grupe {escape(a['group'])}: od drugih grupa, "
                f"najsličnije ({escape(c['name'])} saziv). {_a('#slaganje', 'Sve grupe')}")
            break
    if words:
        out.append({"n": "", "text": Markup("Reči koje u raspravama koristi više od drugih poslanika: "
                                            + ", ".join(f"<i>{escape(w)}</i>" for w in words[:6]) + ".")})
    return out
