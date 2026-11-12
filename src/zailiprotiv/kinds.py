"""How an act is sorted: its kind, from its title (and the Official Gazette's treaty mark), and its area, from the
point of Article 97 of the Constitution its bill cites. The same rules for every act (AGENTS.md, "Laws").

Labels are written once in Cyrillic, as the site's Serbian text is; the Latin pages transliterate them.
"""

from __future__ import annotations

from zailiprotiv.translit import latin

KINDS = {
    "treaty": "Међународни уговор",
    "finance": "Буџет и јавне финансије",
    "change": "Измене закона",
    "law": "Нови закон",
    "officials": "Избор и разрешење функционера",
    "assembly": "Рад Народне скупштине",
    "declaration": "Декларација или резолуција",
    "other": "Остало",
}

# Article 97 of the Constitution: what the Republic of Serbia regulates and provides for, one area per point,
# named after the point's own words (Constitution of 2006, Official Gazette 98/2006, as amended in 2022; the
# amendments didn't touch Article 97). Checked against the text RIK publishes, 12 Nov 2026.
AREAS = {
    1: "Сувереност, територијална целина, безбедност и међународни односи",
    2: "Слободе и права грађана, уставност и законитост, поступци пред судовима",
    3: "Територијална организација и локална самоуправа",
    4: "Одбрана и безбедност, ванредне мере",
    5: "Прелазак границе, промет преко границе, положај странаца",
    6: "Тржиште, привредни, монетарни, банкарски, царински и порески систем",
    7: "Својински и облигациони односи",
    8: "Рад, запошљавање и социјално осигурање",
    9: "Одрживи развој и животна средина, оружје и опасне материје",
    10: "Здравство, социјална заштита, образовање, култура, спорт, јавно информисање",
    11: "Контрола средстава, ревизија јавних средстава, статистика",
    12: "Развој, простор, наука и технологија",
    13: "Саобраћај",
    14: "Празници и одликовања",
    15: "Финансирање Републике",
    16: "Органи Републике",
    17: "Други односи од интереса за Републику",
}

_FINANCE = ("budzet", "zavrsnom racunu", "zavrsni racun", "finansijsk plan", "finansijskog plana",
            "finansijski plan", "zaduzivanj", "garancij", "preuzimanju obaveza")
_OFFICIALS = ("izbor", "izabere", "razresenj", "imenovanj", "prestanku funkcije", "prestanak funkcije",
              "postavljenj", "prestanku mandata", "potvrdjivanju mandata", "potvrdjivanje mandata")
_ASSEMBLY = ("poslovnik", "dnevnom redu", "dnevni red", "sastavu", "clanova i zamenika clanova odbora",
             "stalnih delegacija", "odbora narodne skupstine", "spajanju rasprave", "hitnom postupku")


def _plain(text: str) -> str:
    """Latin, lowercased, without diacritics: "Буџет" and "Budžet" both become "budzet"."""
    t = latin(text).lower()
    return t.translate(str.maketrans({"č": "c", "ć": "c", "š": "s", "ž": "z", "đ": "dj"}))


def kind(title: str, treaty: bool = False) -> str:
    """The kind of act from its title: "Predlog zakona o potvrđivanju …" is a treaty, and so on."""
    t = _plain(title)
    if treaty or "o potvrdjivanju" in t and ("sporazum" in t or "ugovor" in t or "konvencij" in t
                                            or "protokol" in t or "memorandum" in t or "amandman" in t):
        return "treaty"
    if any(w in t for w in _FINANCE):
        return "finance"
    if "deklaracij" in t or "rezolucij" in t:
        return "declaration"
    is_law = "zakon" in t.split(" o ", 1)[0] or t.startswith(("zakon", "predlog zakona"))
    if is_law:
        if any(w in t for w in ("o izmenama", "o izmeni", "o dopunama", "o dopuni")):
            return "change"
        return "law"
    if any(w in t for w in _ASSEMBLY):
        return "assembly"
    if any(w in t for w in _OFFICIALS):
        return "officials"
    return "other"


def areas(articles: list[dict]) -> list[int]:
    """Article 97's points among a bill's constitutional basis, in order, each once."""
    out = []
    for a in articles:
        if a.get("article") == 97:
            for p in a.get("points", []):
                if p in AREAS and p not in out:
                    out.append(p)
    return out
