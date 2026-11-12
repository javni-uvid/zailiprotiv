"""The roll-call reader on real PDFs from the Assembly (tests/fixtures), one of each known layout."""

import re
from pathlib import Path

import pytest

from zailiprotiv import rollcall

FIXTURES = Path(__file__).parent / "fixtures"


def read(name):
    return rollcall.read(FIXTURES / name)


def test_report_layout_since_2025():
    [v] = read("2026_20.pdf")
    assert v.when == "2026-06-25T11:17:12"
    assert v.kind == "Гласање о предлогу акта у целини"
    assert v.item.startswith("20. Предлог закона о потврђивању Измене и допуне бр. 2 Споразума о зајму")
    assert v.session == "Седмо ванредно заседање Народне скупштине Републике Србије у Четрнаестом сазиву"
    assert v.count() == {"za": 137, "protiv": 5, "uzdrzan": 0, "nije_glasao": 29, "nije_prisutan": 79}
    assert len(v.rows) == 250 and not v.problems
    first = v.rows[0]
    assert (first.number, first.name, first.vote, first.club) == (1, "АБРАМОВИЋ НЕНАД", "za", "ПГ АВ-СНСДС")


def test_votes_agree_with_the_rows_own_words():
    """Where a row carries its vote word, it is the section's: counted straight from the text, independently."""
    text = rollcall.text_of(FIXTURES / "2026_1-31.08.2026..pdf")
    [v] = rollcall.parse(text)
    rows = [l for l in text.splitlines() if re.match(r"^\s*\d+\.?\s+\S", l)]
    said_for = sum(1 for l in rows if re.search(r"\s{2,}За\s{2,}", l))
    said_against = sum(1 for l in rows if re.search(r"\s{2,}Против\s{2,}", l))
    assert v.count()["za"] == said_for == 137
    assert v.count()["protiv"] == said_against == 36
    assert v.count()["uzdrzan"] == 2


def test_a_wrapped_session_year_stays_in_the_session():
    [v] = read("2025_1._izvestaj_sa_rezultatima_glasanja_03_12_2025_14_20.pdf")
    assert v.session.endswith("у 2025. години")
    assert v.item.startswith("1. Предлог закона о буџету Републике Србије за 2026. годину")
    assert sum(v.count().values()) == 250


def test_sub_vote_without_kind():
    [v] = read("2026_29.11.pdf")
    assert v.when == "2026-06-25T11:54:04" and v.kind == ""
    assert v.item.startswith("28. 11. Предлог да се за члана Већа Агенције")
    assert v.count()["za"] == 0 and sum(v.count().values()) == 250


def test_listinzi_2024_hold_several_votes_and_omit_the_absent():
    votes = read("2024_2024.09.30_1.pdf")
    assert [v.item[:4] for v in votes] == ["1.1.", "1.2.", "1.3.", "1.4.", "1.5."]
    v = votes[0]
    assert v.when == "2024-09-30T17:53:17" and v.kind == ""
    assert v.count() == {"za": 136, "protiv": 51, "uzdrzan": 0, "nije_glasao": 6, "nije_prisutan": 0}
    assert all(not x.problems for x in votes)
    assert {r.club for r in v.rows} >= {"А. ВУЧИЋ - Србија не сме да стане", "СВМ", ""}


def test_listinzi_2025_columns():
    [v] = read("2024_2025.03.06_1._predlog_zakona_o_izmenama_i_dopunama_zakona_o_visokom_obrazovanju.pdf")
    assert v.when == "2025-03-06T15:10:40"
    assert v.item == "1. Предлог закона о изменама и допунама Закона о високом образовању"
    assert v.count()["za"] == 163 and not v.problems
    assert v.rows[0].club == ""  # "-": no group


@pytest.mark.parametrize("name", sorted(p.name for p in FIXTURES.glob("*.pdf")))
def test_every_fixture_reads_cleanly(name):
    votes = read(name)
    assert votes
    for v in votes:
        assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d", v.when)
        assert v.item and v.rows and not v.problems
        assert len({r.name for r in v.rows}) == len(v.rows)


def test_lookalike_letters():
    assert rollcall.vote_word("Ниje гласао") == "nije_glasao"
    assert rollcall.section_of("  НИСУ ПРИСУТНИ:") == "nije_prisutan"
    assert rollcall.section_of(" ГЛАСАЛИ ЗА") == "za"


def test_votes_command_reads_new_pdfs_once(tmp_path, monkeypatch):
    import json
    from zailiprotiv import cli, skupstina
    base = "https://www.parlament.gov.rs/upload/rezultati_glasanja/2026/"
    files = {base + "20.pdf": "2026_20.pdf", base + "29.11.pdf": "2026_29.11.pdf"}
    asked = []

    def fetch(url):
        asked.append(url)
        return (FIXTURES / files[url]).read_bytes()

    monkeypatch.setattr(skupstina, "fetch", fetch)
    monkeypatch.setattr(cli, "DELAY", 0)
    sitting = "https://www.parlament.gov.rs/Седмо_ванредно_заседање_Народне.53524.43.html"
    index = tmp_path / "index.json"
    index.write_text(json.dumps({"sittings": {sitting: {"listed": 0, "title": "Седмо ванредно заседање",
                                                        "votes": [["20. Предлог", base + "20.pdf"],
                                                                  ["28. 11. Предлог", base + "29.11.pdf"]]}}}))
    args = ["votes", "--index", str(index), "--out", str(tmp_path / "votes")]
    assert cli.main(args) == 0
    store = json.loads((tmp_path / "votes" / "53524.json").read_text())
    assert set(store["pdfs"]) == set(files)
    v = store["votes"][base + "20.pdf#0"]
    assert v["counts"]["za"] == 137 and len(v["rows"]) == 250 and v["listed_as"] == "20. Предлог"
    assert cli.main(args) == 0 and len(asked) == 2  # nothing read twice
