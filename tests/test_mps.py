from zailiprotiv import mps


def test_one_key_for_both_layouts():
    assert mps.key("АТЛАГИЋ проф. др МАРКО") == mps.key("проф. др Марко Атлагић")
    assert mps.key("БЕЛОИЦА МАРТАЋ АНА") == mps.key("Ана Белоица Мартаћ")
    assert mps.key("ИЛИЋ-СТОШИЋ БИЉАНА") == mps.key("Биљана Илић-Стошић")
    assert mps.key("ЗДРАВКОВИЋ проф. др сц. мед. МАРИЈА") == mps.key("проф. др сц. мед. Марија Здравковић")
    assert mps.key("ЈОВАНОВИЋ НАТАША") != mps.key("ИВАНОВИЋ НАТАША")


def test_clashes():
    votes = [{"rows": [[1, "ЈОВАНОВИЋ ДАРКО", "za", "ПГ А"], [2, "Дарко Јовановић", "za", "Б"]]}]
    assert mps.clashes(votes) == {mps.key("Дарко Јовановић"): {"ЈОВАНОВИЋ ДАРКО", "Дарко Јовановић"}}


def test_split_one_name_two_people(tmp_path):
    (tmp_path / "mp_aliases.json").write_text("{}", encoding="utf-8")
    (tmp_path / "mp_splits.json").write_text(
        '[{"name": "Ненад Митровић", "convocations": ["11"], "mark": "1973", "why": "two people"}]', encoding="utf-8")
    mps.load_aliases(tmp_path / "mp_aliases.json")
    try:
        assert mps.split("Ненад Митровић", "11") == "Ненад Митровић (1973)"
        assert mps.split("НЕНАД МИТРОВИЋ", "11") == "НЕНАД МИТРОВИЋ (1973)"  # the notes' capitals
        assert mps.split("МИТРОВИЋ др НЕНАД", "14") == "МИТРОВИЋ др НЕНАД"  # other convocations: the other person
        assert mps.key(mps.split("Ненад Митровић", "11")) != mps.key("МИТРОВИЋ др НЕНАД")
        assert mps.key(mps.split("Ненад Митровић", "11")) == mps.key(mps.split("НЕНАД МИТРОВИЋ", "11"))
    finally:
        mps.load_aliases(tmp_path / "none.json")


def test_registry_keeps_the_mark_last():
    from zailiprotiv import site
    votes = {"a": {"key": "a", "when": "2021-01-01T10:00:00", "counts": {"nije_prisutan": 0},
                   "rows": [[1, "Александар Јовановић (1968)", "za", "ПУПС"]]},
             "b": {"key": "b", "when": "2025-01-01T10:00:00", "counts": {"nije_prisutan": 1},
                   "rows": [[1, "ЈОВАНОВИЋ АЛЕКСАНДАР", "protiv", "ПГ ЕУ"]]}}
    people = site.registry(votes)
    assert sorted(m.name for m in people.values()) == ["Jovanović Aleksandar", "Jovanović Aleksandar (1968)"]
    assert sorted(m.slug for m in people.values()) == ["jovanovic-aleksandar", "jovanovic-aleksandar-1968"]


ARCHIVE_PAGE = """<html><body>
<a href="/narodna-skupstina-/sastav/narodni-poslanici/arhiva-saziva/saziv-od-3-avgusta-2020.4557.html">2020</a>
<a href="/narodna-skupstina-/sastav/radna-tela/saziv-od-3-avgusta-2020-godine/odbori.4560.html">odbori</a>
<table><tr><th>Ime i prezime narodnog poslanika</th><th>Politička stranka</th><th>Mesto</th><th>Godište</th></tr>
<tr><td>ACKOVIĆ dr DRAGOLjUB </td><td>SNS</td><td>Beograd</td><td>1952.</td></tr>
<tr><td>JOVANOVIĆ ALEKSANDAR</td><td>PUPS</td><td>Beograd</td><td>1968.</td></tr>
</table></body></html>"""


def test_mp_years_parse():
    from zailiprotiv import mp_years
    rows, links = mp_years.parse(ARCHIVE_PAGE)
    assert rows == [{"name": "ACKOVIĆ dr DRAGOLjUB", "party": "SNS", "place": "Beograd", "year": 1952},
                    {"name": "JOVANOVIĆ ALEKSANDAR", "party": "PUPS", "place": "Beograd", "year": 1968}]
    assert links == ["https://www.parlament.gov.rs/narodna-skupstina-/sastav/narodni-poslanici/arhiva-saziva/"
                     "saziv-od-3-avgusta-2020.4557.html"]
    assert mp_years.convocation(links[0]) == "12"
    assert mp_years.convocation(mp_years.START) == "14"
    assert mp_years.key("ACKOVIĆ dr DRAGOLjUB", "12") == mps.key("др Драгољуб Ацковић")


def test_mp_years_check():
    from zailiprotiv import mp_years
    listed = {"12": [{"name": "JOVANOVIĆ ALEKSANDAR", "party": "PUPS", "place": "Beograd", "year": 1968}],
              "13": [{"name": "JOVANOVIĆ ALEKSANDAR", "party": "-", "place": "Beograd", "year": 1966},
                     {"name": "ANTIĆ IVAN", "party": "SNS", "place": "Novi Sad", "year": 1978},
                     {"name": "ANTIĆ IVAN", "party": "SPS", "place": "Niš", "year": 1990}],
              "14": [{"name": "ANTIĆ IVAN", "party": "SNS", "place": "Novi Sad", "year": 1979}]}
    seated = {"13": {mps.key("Иван Антић"), mps.key("Петар Петровић")}}
    found = mp_years.check(listed, seated)
    assert [d["key"] for d in found["differ"]] == [mps.key("Александар Јовановић"), mps.key("Иван Антић")]
    assert found["differ"][0]["years"] == {"12": [1968], "13": [1966]}
    assert [t["convocation"] for t in found["twice"]] == ["13"]
    assert found["missing"] == {"13": [mps.key("Петар Петровић")]}
