"""The page shown at mikrofon.zailiprotiv.rs while "Ko sada govori" is down (pages_mikrofon, live/edge)."""
from zailiprotiv import pages_mikrofon


def _facts(days=21, word=("izdajnici", 145)):
    conv = {"n": "14", "years": "2024–2026"}
    numbers = [{"conv": conv, "with_bill": 395, "urgent": 66, "days": days, "voted": 394, "unopposed": 239}]
    law = {"slug": "rebalans", "law": {"short": "Rebalans"}, "final": {"counts": {"za": 136, "protiv": 51}}}
    totals = {"14": {"years": "2024–2026", "page": "varnice.html", "page_who": "varnice-ko.html", "sittings": 16,
                     "speeches": 7298, "measures": 38, "exchanges": 60, "harsh_word": word}}
    return pages_mikrofon.facts(stats={"all_laws": 2097, "all_mps": 995}, numbers=numbers, items=[law],
                                most_against=lambda items, k: items[:k], totals=totals, active="14")


def test_facts_come_from_the_sites_counts_each_with_its_page():
    facts = _facts()
    assert [f["href"] for f in facts] == ["zakoni.html", "brojke.html", "brojke.html", "brojke.html",
                                          "zakon/rebalans.html", "varnice.html", "varnice-ko.html"]
    text = " ".join(f["text"] for f in facts)
    for said in ("2097 zakona", "66 od 395", "za 21 dan ", "239 od 394", "136 za i 51 protiv", "7298 govora",
                 "„izdajnici“", "145 puta"):
        assert said in text


def test_facts_leave_out_what_is_not_known():
    facts = _facts(days=None, word=(None, 0))
    assert not any("Polovina" in f["text"] or "Teška reč" in f["text"] for f in facts)
    assert "za 22 dana " in _facts(days=22)[2]["text"]


def test_the_last_day_read_from_the_recording():
    day = {"dan": "2026-11-17", "govori": [
        {"ime": "Vučić Aleksandar", "adresa": "vucic-aleksandar", "grupa": "", "uloga": "Lista A", "od": 1794920657,
         "do": 1794926412, "okvira": 1152, "video": "qkm", "snimak": 14527},
        {"ime": "Jović Jova", "adresa": "", "grupa": "", "uloga": "", "od": 1794926500, "do": 1794926505, "okvira": 1,
         "video": "qkm", "snimak": 20370}]}
    out = pages_mikrofon.turns(day)
    assert out == [{"from": "14:04", "to": "15:40", "name": "Aleksandar Vučić", "slug": "vucic-aleksandar",
                    "side": "Lista A", "minutes": 96, "recording": "https://www.youtube.com/watch?v=qkm&t=14527s",
                    "file": "", "t": 14527}]


def _quiz():
    conv = {"n": "14", "years": "2024–2026"}
    numbers = [{"conv": conv, "with_bill": 395, "urgent": 66, "days": 21, "voted": 394, "unopposed": 239}]
    totals = {"14": {"years": "2024–2026", "page": "varnice.html", "page_who": "varnice-ko.html", "sittings": 16,
                     "speeches": 7298, "measures": 38, "exchanges": 60, "harsh_word": ("izdajnici", 145),
                     "harsh_top": [("izdajnici", 145), ("lopovi", 90), ("bitange", 12)]}}
    return pages_mikrofon.quiz(numbers=numbers, totals=totals, active="14")


def test_the_quiz_asks_for_the_sites_own_numbers_with_wrong_answers_by_a_fixed_rule():
    quiz = _quiz()
    assert len(quiz) == 5
    for q in quiz:
        assert len(q["options"]) == 3 and len(set(q["options"])) == 3 and 0 <= q["answer"] < 3 and q["href"]
    assert [q["options"][q["answer"]] for q in quiz] == ["66", "21", "239", "7298", "„izdajnici“"]
    assert [q["answer"] for q in quiz[:4]] == [0, 1, 2, 0]  # the right one now smallest, now middle, now largest
    assert all(int(o) <= 395 for o in quiz[0]["options"]) and all(int(o) <= 394 for o in quiz[2]["options"])
    assert quiz[4]["options"] == ["„bitange“", "„izdajnici“", "„lopovi“"]  # the three commonest, by the alphabet


def test_the_quiz_leaves_out_what_is_not_known_and_the_live_page_gets_plain_links():
    conv = {"n": "14", "years": "2024–2026"}
    numbers = [{"conv": conv, "with_bill": 0, "urgent": 0, "days": None, "voted": 10, "unopposed": 4}]
    quiz = pages_mikrofon.quiz(numbers=numbers, totals={}, active="14")
    assert [q["options"][q["answer"]] for q in quiz] == ["4"]
    w = pages_mikrofon.waiting([{"text": "x", "href": "zakon/a.html"}], _quiz())
    assert w["cinjenice"][0]["href"] == "zakon/a" and w["kviz"][0]["href"] == "brojke"
    # Beside the quiz, only the facts it does not ask about.
    assert [f["key"] for f in pages_mikrofon.besides(_facts(), _quiz())] == ["laws", "against"]


def test_a_turn_in_the_archive_links_to_its_second_in_the_file():
    day = {"dan": "2026-11-17", "govori": [{"ime": "Radeta Vjerica", "adresa": "radeta-vjerica", "grupa": "",
            "uloga": "", "od": 1794910712, "do": 1794910792, "okvira": 17, "video": "",
            "datoteka": "https://arhiva.videonet.co.rs/filesnsrs/zasedanja/zas2026111710.mp4", "snimak": 769}]}
    t = pages_mikrofon.turns(day)[0]
    assert t["recording"].endswith("zas2026111710.mp4#t=769") and t["file"].endswith("10.mp4") and t["t"] == 769
