"""The page shown at mikrofon.zailiprotiv.rs while "Ko sada govori" is down (pages_mikrofon, live/edge)."""
import json

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
                     "speeches": 7298, "measures": 38, "exchanges": 60, "harsh": 412, "harsh_word": ("izdajnici", 145),
                     "harsh_top": [("izdajnici", 145), ("lopovi", 90), ("bitange", 12)],
                     "harsh_days": [("2025-03-04", 40), ("2024-11-20", 31), ("2025-06-10", 25)],
                     "harsh_quote": {"text": "Vi ste izdajnici ovog naroda i to svi znaju.", "word": "izdajnici",
                                     "who": "Petrović Petar", "slug": "petrovic-petar", "date": "2025-03-04",
                                     "url": "https://beleske.zailiprotiv.rs/a#g12"}}}
    items = [{"law": {"passed": d}} for d in ("2025-03-04", "2025-03-04", "2025-03-04", "2025-05-01", "2025-05-01")]
    return pages_mikrofon.quiz(numbers=numbers, totals=totals, active="14", items=items)


def test_the_quiz_asks_for_the_sites_own_numbers_with_wrong_answers_by_a_fixed_rule():
    quiz = _quiz()
    assert [q["key"] for q in quiz] == ["quote", "urgent", "harsh", "per_day", "days", "harsh_all", "measures",
                                        "unopposed", "harsh_day", "speeches"]
    for q in quiz:
        assert len(q["options"]) == 3 and len(set(q["options"])) == 3 and 0 <= q["answer"] < 3 and q["href"]
    right = [q["options"][q["answer"]] for q in quiz]
    assert right == ["„izdajnici“", "66", "145", "3", "21", "412", "38", "239", "4. marta 2025", "7298"]
    assert quiz[0]["q"] == "Koja reč nedostaje? „Vi ste _____ ovog naroda i to svi znaju.“"
    assert quiz[0]["options"] == ["„bitange“", "„izdajnici“", "„lopovi“"] and quiz[0]["more"] == "Ceo govor"
    assert quiz[0]["href"].startswith("https://beleske.") and quiz[0]["why"].endswith("Rečeno 4. marta 2025.")
    numeric = [q for q in quiz if q["options"][0].isdigit()]
    assert len({q["answer"] for q in numeric}) == 3  # the right one now smallest, now middle, now largest
    assert all(int(o) <= 395 for o in quiz[1]["options"]) and all(int(o) <= 394 for o in quiz[7]["options"])
    assert quiz[8]["options"] == ["20. novembra 2024", "4. marta 2025", "10. juna 2025"]  # by date


def test_the_quiz_leaves_out_what_is_not_known_and_the_live_page_gets_plain_links():
    conv = {"n": "14", "years": "2024–2026"}
    numbers = [{"conv": conv, "with_bill": 0, "urgent": 0, "days": None, "voted": 10, "unopposed": 4}]
    quiz = pages_mikrofon.quiz(numbers=numbers, totals={}, active="14")
    assert [q["options"][q["answer"]] for q in quiz] == ["4"]
    w = pages_mikrofon.waiting([{"text": "x", "href": "zakon/a.html"}], _quiz())
    assert w["cinjenice"][0]["href"] == "zakon/a" and w["kviz"][1]["href"] == "brojke"
    assert w["kviz"][0]["href"] == "https://beleske.zailiprotiv.rs/a#g12"  # an address elsewhere stays whole
    # Beside the quiz, only the facts it does not ask about.
    assert [f["key"] for f in pages_mikrofon.besides(_facts(), _quiz())] == ["laws", "against"]


def test_a_turn_in_the_archive_links_to_its_second_in_the_file():
    day = {"dan": "2026-11-17", "govori": [{"ime": "Radeta Vjerica", "adresa": "radeta-vjerica", "grupa": "",
            "uloga": "", "od": 1794910712, "do": 1794910792, "okvira": 17, "video": "",
            "datoteka": "https://arhiva.videonet.co.rs/filesnsrs/zasedanja/zas2026111710.mp4", "snimak": 769}]}
    t = pages_mikrofon.turns(day)[0]
    assert t["recording"].endswith("zas2026111710.mp4#t=769") and t["file"].endswith("10.mp4") and t["t"] == 769


def test_the_next_sitting_is_one_convened_for_today_or_later_with_its_agenda(tmp_path):
    from datetime import datetime as dt_
    (tmp_path / "15").mkdir()
    (tmp_path / "15" / "index.json").write_text(json.dumps({"sittings": {
        "https://a/druga": {"title": "Друга седница", "starts": "2026-11-24T10:00", "agenda": ["Избор судија"], "votes": []},
        "https://a/prva": {"title": "Прва седница", "starts": "", "agenda": ["Избор председника"], "votes": []},
        "https://a/vest": {"title": "Вест", "starts": "", "agenda": [], "votes": []}}}), encoding="utf-8")
    coming = [{"title": "Стара седница", "url": "https://a/stara", "starts": "2026-11-02", "agenda": ["x"]}]
    every = pages_mikrofon.upcoming(tmp_path, coming, "15")
    assert [c["url"] for c in every] == ["https://a/stara", "https://a/druga", "https://a/prva"]
    w = pages_mikrofon.waiting([], [], every, now=dt_(2026, 11, 20, 1, 0, tzinfo=pages_mikrofon.TZ))
    assert w["sazvano"] == {"naslov": "Druga sednica", "url": "https://a/druga", "pocinje": "2026-11-24T10:00",
                            "tacke": ["Izbor sudija"]}
    assert "sazvano" not in pages_mikrofon.waiting([], [], coming, now=dt_(2026, 11, 20, tzinfo=pages_mikrofon.TZ))
