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
                    "side": "Lista A", "minutes": 96, "recording": "https://www.youtube.com/watch?v=qkm&t=14527s"}]
