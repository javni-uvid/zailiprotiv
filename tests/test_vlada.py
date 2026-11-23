"""Who the Assembly elected to the Government (vlada.py), and an MP's offices as cards (office_cards.py)."""
import json
from pathlib import Path

import pytest

from zailiprotiv import office_cards, offices, vlada
from zailiprotiv.translit import latin

ROOT = Path(__file__).resolve().parents[1]

ELECTION = """       На основу члана 99. став 2. тачка 1. Устава Републике Србије, члана 15. Закона о Влади
      Народна скупштина Републике Србије, на Деветој посебној седници у
Једанаестом сазиву, одржаној 29. јуна 2017. године, донела је
                              ОДЛУКУ
                           О ИЗБОРУ ВЛАДЕ
                                       I
      За председника Владе бира се Ана Брнабић.
                                      II
      За чланове Владе бирају се:
      1.   Ивица Дачић, за првог потпредседника Владе и министра спољних
послова,
      2. Јадранка Јоксимовић, за министра за европске интеграције,
\f                                    2
     3.   проф. др Славица Ђукић - Дејановић, за министра без портфеља и
     4.   др Ненад Поповић, за министра без портфеља.
                                    III
      Ову одлуку објавити у "Службеном гласнику Републике Србије".
""".replace("\\f", "\f")


def test_a_governments_election_is_read_whole():
    d = vlada.parse(ELECTION)
    assert d["date"] == "2017-06-29" and d["kind"] == "izbor" and vlada.conv_of(d["date"]) == "11"
    assert [(p["name"], latin(vlada.say(p["post"]))) for p in d["people"]] == [
        ("Ана Брнабић", "Predsednik Vlade"),
        ("Ивица Дачић", "Prvi potpredsednik Vlade i ministar spoljnih poslova"),
        ("Јадранка Јоксимовић", "Ministar za evropske integracije"),  # a name in Ј begins an item too
        ("проф. др Славица Ђукић - Дејановић", "Ministar bez portfelja"),  # after the page's break
        ("др Ненад Поповић", "Ministar bez portfelja")]


def test_one_minister_elected_and_one_dismissed():
    d = vlada.parse("на седници одржаној 6. септембра 2023. године, донела је ОДЛУКУ\n"
                    "1. За министра привреде у Влади Републике Србије бира се Слободан\nЦветковић.\n2. Ову одлуку објавити")
    assert d["people"] == [{"name": "Слободан Цветковић", "post": "министра привреде"}]
    d = vlada.parse("на седници одржаној 11. јула 2023. године, донела је\n"
                    "1. Разрешава се Раде Баста функције члана Владе – министра привреде.\n2. Ову одлуку")
    assert d["kind"] == "razresenje" and d["people"] == [{"name": "Раде Баста", "post": "министра привреде"}]
    d = vlada.parse("одржаној 16. априла 2025. године\nЗа председника Владе бира се проф. др Ђуро Мацут.\n")
    assert d["people"][0]["name"] == "проф. др Ђуро Мацут"
    assert vlada.parse("Одлука о нечем другом") is None


def test_a_list_read_short_is_refused():
    with pytest.raises(ValueError):
        vlada.parse("одржаној 2. маја 2024. године\nЗа чланове Владе бирају се: 1. Ивица Дачић, за министра одбране; "
                    "3. Маја Поповић, за министра правде. Ову одлуку објавити")


def test_the_end_only_from_a_decision_that_says_it():
    d = json.loads((ROOT / "data" / "vlada.json").read_text(encoding="utf-8"))["decisions"]
    rows = vlada.offices(d)
    ended = {(latin(o["name"]), o["until"]) for o in rows if o["until"]}
    assert ended == {("Bratislav Gašić", "2016-02-05"), ("Rade Basta", "2023-07-11")}
    sizes = {x["date"]: len(x["people"]) for x in d}
    assert sizes["2012-07-27"] == 19 and sizes["2022-10-26"] == 29 and sizes["2024-05-02"] == 32  # whole lists


def test_a_member_of_the_government_is_an_mp_only_when_confirmed():
    d = [{"date": "2014-04-27", "kind": "izbor", "url": "u", "people": [
        {"name": "Александар Антић", "post": "министра рударства и енергетике"},
        {"name": "Марко Благојевић", "post": "министра за јавна улагања"}]}]
    listed = {"10": [{"name": "ANTIĆ ALEKSANDAR", "place": "16.04.2014 - 27.04.2014."}],
              "11": [{"name": "BLAGOJEVIĆ MARKO", "place": "03.06.2016 - 19.04.2017."}]}
    antic, blagojevic = offices.mp_key("Александар Антић"), offices.mp_key("Марко Благојевић")
    assert vlada.confirmed(d, listed, {}) == {antic}  # the mandate ended the day of the election; a name alone is none
    assert vlada.confirmed(d, listed, {"isti": ["Марко Благојевић"]}) == {antic, blagojevic}
    assert vlada.confirmed(d, listed, {"drugi": ["Александар Антић"]}) == set()


def test_cards_one_an_office_with_its_convocations_in_one_order():
    day = lambda d: {"2024-03-20": "20. marta 2024.", "2016-02-05": "5. februara 2016."}[d]  # noqa: E731
    rows = [
        {"kind": "committee", "role": "члан", "body": "Одбор за одбрану", "source": "c", "conv": "13"},
        {"kind": "committee", "role": "члан", "body": "Одбор за одбрану", "source": "d", "conv": "14"},
        {"kind": "delegation", "role": "шеф Делегације", "body": "Делегација у Интерпарламентарној унији", "source": "e", "conv": "14"},
        {"kind": "vlada", "post": "председника Владе", "since": "2017-06-29", "until": "", "conv": "11", "source": "a"},
        {"kind": "vlada", "post": "председника Владе", "since": "2020-10-28", "until": "", "conv": "12", "source": "b"},
        {"kind": "vlada", "post": "министра одбране", "since": "2014-04-27", "until": "2016-02-05", "conv": "10", "source": "f"},
        {"kind": "speaker", "role": "Председник Народне скупштине", "body": "Народна скупштина", "source": "s", "conv": "14",
         "since": "2024-03-20", "until": "", "dated": True}]
    got = [(c["label"], c["text"], c["when"], c["source"]) for c in office_cards.cards(rows, latin, day)]
    assert got == [
        ("Skupština", "Predsednik Narodne skupštine", "od 20. marta 2024. · 14. saziv", "s"),
        ("Vlada", "Predsednik Vlade", "izbor 2017. i 2020. · 11. i 12. saziv", "b"),
        ("Vlada", "Ministar odbrane", "izbor 2014. · 10. saziv · razrešenje 5. februara 2016.", "f"),
        ("Delegacija", "Delegacija u Interparlamentarnoj uniji: šef", "14. saziv", "e"),
        ("Odbor", "Odbor za odbranu: član", "13. i 14. saziv", "d")]
    assert office_cards.listed(["11", "12", "13"]) == "11, 12. i 13."
    assert office_cards.cards([], latin, day) == []


def test_the_built_page_shows_the_government_of_a_confirmed_mp_only(tmp_path):
    """On the whole build (23 Nov 2026: every unit test passed while no page showed the Government, a name used twice
    in the build's one function)."""
    from test_site import data
    from zailiprotiv import site
    d = data(tmp_path)
    d.rename(tmp_path / "one")
    root = tmp_path / "data"
    root.mkdir()
    (tmp_path / "one").rename(root / "14")
    (root / "vlada.json").write_text(json.dumps({"decisions": [{"date": "2025-04-16", "kind": "izbor", "url": "https://x.test/o.pdf",
        "people": [{"name": "Ненад Абрамовић", "post": "министра правде"}, {"name": "Јован Чолаковић", "post": "министра одбране"}]}]}),
        encoding="utf-8")
    (root / "vlada_isti.json").write_text(json.dumps({"isti": ["Ненад Абрамовић"], "drugi": []}), encoding="utf-8")
    out = tmp_path / "site"
    site.build(root, out)
    mp = (out / "poslanik" / "abramovic-nenad.html").read_text(encoding="utf-8")
    assert '<a href="https://x.test/o.pdf">Ministar pravde</a>' in mp and "izbor 2025. · 14. saziv" in mp
    other = next(p for p in (out / "poslanik").glob("colakovic-jovan*.html") if not p.stem.endswith(("-glasovi", "-govori")))
    assert "Ministar odbrane" not in other.read_text(encoding="utf-8")  # the name alone is not enough
