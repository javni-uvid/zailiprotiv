from pathlib import Path

import pytest

from zailiprotiv import bills

FIXTURES = Path(__file__).parent / "fixtures"
TREATY = FIXTURES / "bills" / "2560-26_treaty_angola.pdf"


def test_treaty_memorandum():
    m = bills.read(TREATY)
    assert m.articles == [{"article": 99, "paragraph": 1, "points": [4]}]
    assert set(m.sections) >= {"basis", "reasons", "funds", "effects"}
    assert m.sections["funds"].startswith("Ocena potrebnih finansijskih sredstava")
    assert "nisu potrebna finansijska sredstva" in m.sections["funds"]


MEMO = """
                      I. ОСНОВНЕ ОДРЕДБЕ
Члан 1. Овим законом уређује се ...
                          ОБРАЗЛОЖЕЊЕ
                I. УСТАВНИ ОСНОВ ЗА ДОНОШЕЊЕ ЗАКОНА
Уставни основ за доношење овог закона садржан је у члану 97. тачка 6. и 15.
Устава Републике Србије, према коме Република Србија уређује и обезбеђује ...
                II. РАЗЛОЗИ ЗА ДОНОШЕЊЕ ЗАКОНА
Разлог за доношење закона је ...
и наставак реченице у новом реду.
                VI. ПРЕГЛЕД ОДРЕДБИ ЗАКОНА КОЈЕ СЕ МЕЊАЈУ
Члан 5. ...
                VII. РАЗЛОЗИ ЗА ДОНОШЕЊЕ ЗАКОНА ПО ХИТНОМ ПОСТУПКУ
Хитно је јер ...
"""


def test_domestic_memorandum_from_text():
    m = bills.memorandum(MEMO)
    assert m.articles == [{"article": 97, "paragraph": None, "points": [6, 15]}]
    assert m.sections["reasons"].endswith("и наставак реченице у новом реду.")
    assert "Члан 5" not in m.sections["reasons"]  # the overview of changed provisions isn't kept
    assert m.sections["urgency"].startswith("РАЗЛОЗИ ЗА ДОНОШЕЊЕ ЗАКОНА ПО ХИТНОМ ПОСТУПКУ")


def test_no_memorandum():
    assert bills.memorandum("Члан 1. Текст закона.").sections == {}


def test_bills_command(tmp_path, monkeypatch):
    import json
    from zailiprotiv import cli, skupstina
    url = "https://www.parlament.gov.rs/upload/archive/files/lat/pdf/predlozi_zakona/14_saziv/2560-26%20LAT.pdf"
    monkeypatch.setattr(skupstina, "fetch", lambda u: TREATY.read_bytes())
    monkeypatch.setattr(cli, "DELAY", 0)
    laws = tmp_path / "laws.json"
    laws.write_text(json.dumps({"laws": {"L": {"title": "Zakon o potvrđivanju Ugovora", "bill_pdf": url}}}))
    assert cli.main(["bills", "--laws", str(laws), "--out", str(tmp_path / "bills")]) == 0
    law = json.loads(laws.read_text())["laws"]["L"]
    assert law["bill_file"] == "14_saziv_2560-26_lat.json"
    assert law["constitution"] == [{"article": 99, "paragraph": 1, "points": [4]}] and law["areas"] == []


@pytest.mark.parametrize("basis,expected", [
    ("Ustavni osnov za donošenje ovog zakona sadržan je u članu 97. Ustava Republike Srbije, kojim je između ostalog, "
     "u tački 2. predviđeno da Republika Srbija uređuje", [{"article": 97, "paragraph": None, "points": [2]}]),
    ("Ustavni osnov sadržan je u članu 97. stav 1. tač. 6, 13. i 17. Ustava Republike Srbije",
     [{"article": 97, "paragraph": 1, "points": [6, 13, 17]}]),
    ("Ustavni osnov sadržan je u odredbama člana 97. tač. 6, 7, 12. i 17. Ustava Republike Srbije",
     [{"article": 97, "paragraph": None, "points": [6, 7, 12, 17]}]),
    ("Ustavni osnov sadržan je u članu 97. stav 10. Ustava Republike Srbije", [{"article": 97, "paragraph": None,
                                                                              "points": [10]}]),
    ("Уставни основ садржан је у члану 99. став 1. тачка 4. Устава", [{"article": 99, "paragraph": 1, "points": [4]}]),
    ("Ustavni osnov sadržan je u članu 100. stav 1. i članu 102. stav 4. Ustava",
     [{"article": 100, "paragraph": 1, "points": []}, {"article": 102, "paragraph": 4, "points": []}]),
])
def test_constitutional_basis_in_its_many_spellings(basis, expected):
    assert bills.articles(basis) == expected


def test_arabic_numbered_headings():
    m = bills.read(FIXTURES / "bills" / "14_saziv_2249-25_-_lat..pdf")
    assert m.articles == [{"article": 97, "paragraph": None, "points": [10]}]
    assert {"basis", "reasons", "funds"} <= set(m.sections)
    assert m.sections["reasons"].startswith("RAZLOZI ZA DONOŠENjE ZAKONA")
    assert "Prioritetni razlog za izradu predmetnog propisa" in m.sections["reasons"]


def test_a_bill_without_a_memorandum():
    assert bills.read(FIXTURES / "bills" / "14_saziv_1242-24_-_lat..pdf").sections == {}
