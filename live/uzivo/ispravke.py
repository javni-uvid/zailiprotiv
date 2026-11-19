"""Corrections to the automatic transcript, made after it is out (19 Nov 2026, the maintainer's decision: first
publish, then correct). The text is kept as Whisper wrote it; what is shown is that text with:

- the site's list of corrections (data/prepis-ispravke.json, published in mikrofon-cekanje.json as `ispravke`):
  a word or phrase as Whisper keeps writing it → as it is written ("oktober" → "oktobar"), whole words only, the
  first letter's case kept. Readers' reports go into that list once the maintainer has looked at them;
- names: a capitalised word that is a sitting MP's name but for its diacritics ("Vucic", "Brnabič", in any case:
  "Vučiću") gets them as the Assembly's list writes the name. Only that: a word a letter away from a name may be
  another word or another name, and is left for the list above.
Nothing is reworded; a change is a spelling. `apply` is pure, for tests.
"""
from __future__ import annotations

import re
import unicodedata

# the endings a Serbian name takes in its cases (Vučić, Vučića, Vučiću, Vučićem, Vučićeva…; Ana, Ane, Ani, Anu, Anom)
_ENDINGS = ("", "a", "u", "e", "i", "o", "om", "em", "ev", "eva", "evu", "eve", "ov", "ova", "ovu", "ove", "ima")
_WORD = re.compile(r"[^\W\d_]+", re.U)


def fold(word: str) -> str:
    """A word without its diacritics, in lower case ("Vučić" → "vucic"; "đ" → "dj" as it is often typed)."""
    word = word.lower().replace("đ", "dj")
    return "".join(c for c in unicodedata.normalize("NFD", word) if unicodedata.category(c) != "Mn")


def name_forms(names: list[str]) -> dict[str, str]:
    """Every form of every word of the names (five letters or more), by its folded spelling: {"vucicu": "Vučiću"}.
    A folded spelling that two different words share is left out (no telling which was meant)."""
    out: dict[str, str] = {}
    twice: set[str] = set()
    for name in names:
        for w in _WORD.findall(name):
            if len(w) < 5:
                continue
            stems = {w} | ({w[:-1]} if w[-1] in "aeo" else set())  # Ana → An-e, Marko → Mark-a
            for stem in stems:
                for end in _ENDINGS:
                    form = stem + end
                    k = fold(form)
                    if k in out and out[k] != form:
                        twice.add(k)
                    out.setdefault(k, form)
    for k in twice:
        out.pop(k, None)
    return out


def apply(text: str, rules: dict[str, str] | None = None, forms: dict[str, str] | None = None) -> str:
    """The text as shown: the list's corrections, then the names' diacritics."""
    if not text:
        return text
    for wrong, right in sorted((rules or {}).items(), key=lambda kv: -len(kv[0])):
        if not wrong.strip() or not isinstance(right, str):
            continue
        rx = re.compile(r"(?<![^\W\d_])" + re.escape(wrong) + r"(?![^\W\d_])", re.I | re.U)
        text = rx.sub(lambda m: right[:1].upper() + right[1:] if m.group()[:1].isupper() else right, text)
    if forms:
        def name(m: re.Match) -> str:
            w = m.group()
            if not w[:1].isupper() or len(w) < 5:
                return w
            right = forms.get(fold(w))
            return right if right and right != w and fold(right) == fold(w) else w
        text = _WORD.sub(name, text)
    return text
