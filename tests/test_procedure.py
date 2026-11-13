from pathlib import Path

from zailiprotiv import procedure, skupstina

PAGES = Path(__file__).parent / "fixtures" / "pages"


def test_bills_in_procedure_from_the_assemblys_page():
    bills = procedure.parse((PAGES / "akti_zakoni-u-proceduri_zakoni-u-proceduri.1037.html").read_text(encoding="utf-8"))
    assert len(bills) == 91 and len({b.pdf for b in bills}) == 91
    first = bills[0]
    assert first.title == "Predlog zakona o odgovornosti nosilaca javnih funkcija i zaštiti javnog interesa"
    assert first.submitted == "2026-09-03" and first.proposer.startswith("narodni poslanici mr Vladimir Đorđević")
    assert first.pdf.endswith("/predlozi_zakona/14_saziv/011-2803_26.pdf")
    assert all(b.submitted and b.proposer for b in bills)
    kinds = {procedure.proposer_kind(b.proposer) for b in bills}
    assert kinds == {"vlada", "poslanici"} and procedure.proposer_kind("Zaštitnik građana") == "drugi"
    assert procedure.proposer_kind("Poslanička grupa SRBIJA CENTAR - SRCE") == "poslanici"


def test_the_store_remembers_bills_no_longer_listed():
    a, b = procedure.Bill("A", "a.pdf", "2026-01-01", "Vlada"), procedure.Bill("B", "b.pdf", "2026-01-02", "Vlada")
    store = procedure.merge({}, [a, b], "2026-11-13")
    store = procedure.merge(store, [b], "2026-11-14")
    assert store["bills"]["a.pdf"]["last_seen"] == "2026-11-13" and store["bills"]["b.pdf"]["last_seen"] == "2026-11-14"
    assert store["bills"]["b.pdf"]["first_seen"] == "2026-11-13" and store["fetched"] == "2026-11-14"


def test_a_sittings_agenda_and_the_day_it_was_convened_for():
    page = (PAGES / "sednica.53893.43.html").read_text(encoding="utf-8")
    agenda = skupstina.agenda(page)
    assert skupstina.convened(page) == "2026-08-24T10:00" and len(agenda) == 59
    assert agenda[1].startswith("Предлог закона о ублажавању последица енергетске кризе") and agenda[1].endswith("поднела Влада")
    # An agenda given in a sentence, not a list: none read, the day still is.
    other = (PAGES / "sednica.53810.43.html").read_text(encoding="utf-8")
    assert skupstina.agenda(other) == [] and skupstina.convened(other) == "2026-07-27T10:00"


def test_a_reading_with_far_fewer_entries_does_not_replace_the_file(tmp_path, capsys):
    import json

    from zailiprotiv import cli
    path = tmp_path / "laws.json"
    path.write_text(json.dumps({"laws": {str(i): {} for i in range(100)}}))
    assert cli._shrunk(path, "laws", 0) and cli._shrunk(path, "laws", 79) and "::warning::" in capsys.readouterr().out
    assert not cli._shrunk(path, "laws", 80) and not cli._shrunk(path, "laws", 130)
    assert not cli._shrunk(tmp_path / "none.json", "laws", 0)
