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
    # An agenda given in a sentence, not a list.
    other = (PAGES / "sednica.53810.43.html").read_text(encoding="utf-8")
    assert skupstina.convened(other) == "2026-07-27T10:00"
    assert skupstina.agenda(other) == ["Предлог за гласање о неповерењу Влади, који су поднела 62 народна посланика у "
                                       "Народној скупштини Републике Србије"]


def test_every_form_in_which_a_sitting_was_convened():
    """25 Nov 2026: the Fourteenth's sittings whose agenda or day was not read, as their pages are."""
    read = lambda n: (PAGES / f"sednica.{n}.43.html").read_text(encoding="utf-8")
    numbered = skupstina.agenda(read("53692"))  # lines "1.Предлог …", one of them "8Предлог …", no list
    assert skupstina.convened(read("53692")) == "2026-07-06T10:00" and len(numbered) >= 11
    assert numbered[7].startswith("Предлог закона о изменама и допунама Закона о финансирању политичких активности")
    assert all(x[0].isalpha() for x in numbered)
    assert skupstina.agenda(read("53418")) == ["Обраћање Народној скупштини Њ. Е. Сакр Гобаша, председника Федералног "
                                               "Националног савета Уједињених Арапских Емирата"]
    assert skupstina.convened(read("53518")) == "2026-06-17T10:00"  # "за среду, 17. јун", the year the page's own
    assert skupstina.agenda(read("53518")) == ["Полагање заклетве председника Врховног суда"]
    assert skupstina.agenda(read("50913")) == ["Избор Владе и полагање заклетве председника и чланова Владе"]
    page = lambda words, posted="Среда, 25. новембар 2026.": f'<p class="posted">{posted}</p><p class="preamble">{words}</p>'
    said = lambda *a: skupstina.convened(page(*a))
    assert said("сазвао је Другу седницу за уторак, 1. децембар 2026. године, са почетком у 10 часова.") == "2026-12-01T10:00"
    assert said("сазвао је Другу седницу за уторак, 1. децембра 2026. године, са почетком у 10.30 часова.") == "2026-12-01T10:30"
    assert said("сазвао је седницу за среду, 1. децембар, са почетком у 10.00 часова.") == ""  # the day is not that date's


def test_a_script_on_the_page_is_no_agenda():
    page = '<p class="preamble">x</p><script>var a = "дневни ред: ништа";</script ><div>Дневни ред: Избор Владе.</div>'
    assert skupstina.agenda(page) == ["Избор Владе"]


def test_a_sitting_is_told_from_news_of_one():
    for t in ("Прва седница Народне скупштине Републике Србије у Петнаестом сазиву", "Друга посебна седница Народне скупштине",
              "Прва седница Другог редовног заседања Народне скупштине Републике Србије у 2026. години",
              "Десето ванредно заседање Народне скупштине Републике Србије у Четрнаестом сазиву",
              "Шесто ванредно заседање Народне скупштине Републике Србије у Чeтрнаестом сазиву"):  # a Latin "e"
        assert skupstina.sitting_title(t), t
    for t in ("Одржане консултације уочи конститутивне седнице Народне скупштине", "Одржана седница Одбора за правосуђе",
              "Чланови српске делегације учествовали на заседању Поткомитета Парламентарне скупштине Савета Европе"):
        assert not skupstina.sitting_title(t), t


def test_the_maintainer_is_told_of_a_sitting_newly_listed():
    first = {"title": "Прва седница Народне скупштине", "starts": "", "agenda": ["Избор"], "votes": [["x", "y"]]}
    second = {"title": "Друга седница Народне скупштине Републике Србије у Петнаестом сазиву", "starts": "2026-12-01T10:00",
              "agenda": ["Предлог закона @buduci"], "votes": []}
    news = {"title": "Одржане консултације уочи седнице Народне скупштине", "starts": "", "agenda": [], "votes": []}
    told = skupstina.news_of({"a": first}, {"a": first, "https://b/б": second, "c": news})
    assert len(told) == 1 and told[0][0] == "Sednica na sajtu Skupštine: Druga sednica"
    assert "Počinje: 2026-12-01T10:00" in told[0][1] and "1. Predlog zakona buduci" in told[0][1] and "https://b/б" in told[0][1]
    assert skupstina.news_of({"b": second}, {"b": second}) == [] and skupstina.news_of({}, {"b": second}) == []
    later = {**second, "agenda": ["Предлог закона", "Избор"]}
    assert "Promenjen dan ili dnevni red." in skupstina.news_of({"b": second}, {"b": later})[0][1]
    bare = skupstina.news_of({"a": first}, {"b": {**second, "starts": "", "agenda": []}})[0][1]
    assert "dan nije pročitan" in bare and "Dnevni red nije pročitan" in bare  # what our reading missed is said too


def test_when_a_sitting_goes_on_as_its_page_says():
    """25 Nov 2026: the first sitting's page as the Assembly had it that morning, and the words of 20 November."""
    page = (PAGES / "sednica.54098.43.html").read_text(encoding="utf-8")
    assert skupstina.continues(page) == "2026-11-25T10:00" and skupstina.convened(page) == ""
    said = skupstina.continues
    assert said("<div>Народна скупштина наставља са радом у уторак, 24.&nbsp;новембра 2026. године, у 10.00 часова.</div>") == "2026-11-24T10:00"
    assert said("наставља рад у суботу, 5. децембра 2026. године.") == "2026-12-05"  # a day with no hour
    assert said("наставља рад у уторак, 24. новембра 2026. године, у 10 часова. … наставља рад у среду, 25. новембра "
                "2026. године, у 9.30 часова.") == "2026-11-25T09:30"  # the latest
    # what has been, a day of the week that is not the date's, a comment of the page's: nothing
    assert said("Другог дана рада, 18. новембра 2026. године, Народна скупштина наставила је претрес.") == ""
    assert said("наставља рад у четвртак, 25. новембра 2026. године, у 10.00 часова") == ""
    assert said("<!-- наставља рад у среду, 25. новембра 2026. године -->") == ""
    for older in ("sednica.53893.43.html", "sednica.53810.43.html"):
        assert said((PAGES / older).read_text(encoding="utf-8")) == ""


def test_a_reading_with_far_fewer_entries_does_not_replace_the_file(tmp_path, capsys):
    import json

    from zailiprotiv import cli
    path = tmp_path / "laws.json"
    path.write_text(json.dumps({"laws": {str(i): {} for i in range(100)}}))
    assert cli._shrunk(path, "laws", 0) and cli._shrunk(path, "laws", 79) and "::warning::" in capsys.readouterr().out
    assert not cli._shrunk(path, "laws", 80) and not cli._shrunk(path, "laws", 130)
    assert not cli._shrunk(tmp_path / "none.json", "laws", 0)


def test_the_site_shows_the_newer_convocations_bills_beside_the_current_ones(tmp_path):
    """The Assembly's page lists the newest convocation's bills only; they are read into its folder, and the site shows
    them with the current one's, waiting when listed at the newest reading (28 Nov 2026)."""
    import json
    for conv, fetched, bills in (("14", "2026-11-27", {"a.pdf": {"title": "A", "last_seen": "2026-11-17"}}),
                                 ("15", "2026-11-28", {"b.pdf": {"title": "B", "last_seen": "2026-11-28"}})):
        (tmp_path / conv).mkdir()
        (tmp_path / conv / "procedure.json").write_text(json.dumps({"fetched": fetched, "bills": bills}), encoding="utf-8")
    shown = procedure.shown(tmp_path, "14", "15")
    assert shown["fetched"] == "2026-11-28" and set(shown["bills"]) == {"a.pdf", "b.pdf"}
    assert [k for k, b in shown["bills"].items() if b["last_seen"] == shown["fetched"]] == ["b.pdf"]
    # Before the newer one's first reading, and once it is the current one: its own store alone, as before.
    (tmp_path / "15" / "procedure.json").unlink()
    assert procedure.shown(tmp_path, "14", "15")["fetched"] == "2026-11-27"
    assert set(procedure.shown(tmp_path, "14", "14")["bills"]) == {"a.pdf"}


def test_votes_reads_the_bills_in_procedure_for_the_newest_convocation():
    text = (Path(__file__).parents[1] / ".github/workflows/votes.yml").read_text(encoding="utf-8")
    assert 'uv run zailiprotiv --convocation "$beside" procedure' in text
    assert 'uv run zailiprotiv --convocation "$beside" bills' in text
    assert '[ "$conv" = "$newest" ]; then uv run zailiprotiv $c procedure' in text
