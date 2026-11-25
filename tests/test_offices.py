import datetime as dt
import json
from pathlib import Path
from types import SimpleNamespace

from zailiprotiv import offices
from zailiprotiv.cli import assembly, common
from zailiprotiv.translit import latin

# The Assembly's pages of 25 Nov 2026, their own part as the server gives it (peek).
PAGES = Path(__file__).parent / "fixtures" / "pages"
COMMITTEES15, COMMITTEE15, DELEGATIONS15, DELEGATION15 = ((PAGES / n).read_text(encoding="utf-8") for n in (
    "odbori.13.html", "odbor-spoljni.176.13.html", "delegacije.14.html", "delegacija-savet-evrope.83.14.html"))

WRAP = "<div>menu <a href='/x.5.43.html'>Прва седница Народне скупштине</a></div><!-- OCP content start -->{}<!-- OCP content end -->"

SPEAKER = WRAP.format("""<div class="block single_member"><div class="optimize"> <h2> АЛЕКСАНДАР <span>ЧУПИЋ</span> </h2>
<h4>Изборна листа</h4><p>„Студентска листа“</p> <h4>Занимање</h4><p>Доцент</p>
<h4>Функција у Народној скупштини Републике Србије</h4> <ul> <li>Председник Народне скупштине</li> </ul>
<h4>Место пребивалишта</h4><p>Сопот</p>""")

VICE = WRAP.format("""<a name="628"></a><div class="block"><div class="image_holder Left"><a href="x"><img src="y"/></a></div>
<h2>Јелена Петровић</h2><h3>Посланичка група „Студентска листа“</h3><div class="optimize"></div></div>
<div class="block"><div class="image_holder Left"></div><h2>Тибор Лазар</h2><h3>Посланичка група „Студентска листа“</h3></div>""")

LISTING = WRAP.format("""<h3 class="title_actualities">Одбори</h3><table>
<tr><td><a href="/народна-скупштина/састав/радна-тела/сазив-од-6-фебруара-2024-године.156.5177.html">Одбор за спољне послове</a></td><td>17</td></tr>
<tr><td><a href="/народна-скупштина/састав/радна-тела/сазив-од-6-фебруара-2024-године.157.5177.html">Одбор за финансије</a></td></tr>
<tr><td><a href="/народна-скупштина/састав/радна-тела/сазив-од-6-фебруара-2024-године.157.5177.html">Погледајте детаљније</a></td></tr>
<tr><td><a href="/other.12.99.html">Друго</a></td></tr></table>""")

COMMITTEE = WRAP.format("""<h3 class="title_actualities">Одбори</h3><div class="delegate_list"> <table>
<tr> <td align="left"> <strong> АЛЕКСИЋ МИРОСЛАВ </strong> (члан)<br />Посланичка група Народни покрет Србије<br />
 ЂОКИЋ УРОШ (заменик члана) <br/> Посланичка група Народни покрет Србије </td> </tr>
<tr> <td align="left"> <strong> ЈОВАНОВ МИЛЕНКО </strong> (<strong>председник</strong>) <br />Посланичка група А<br />
 МАРКОВИЋ АЛЕКСАНДАР (заменик члана) <br/> Посланичка група А </td> </tr>
<tr> <td align="left"> <strong> ЈОВАНОВИЋ БРАНИМИР </strong> (<strong>заменик председника</strong>) <br />Посланичка група Б<br />
 КАРАНАЦ ЈАСМИНА (заменик члана) <br/> Посланичка група Б </td> </tr></table></div>""")

DELEGATION = WRAP.format("""<div class="delegate_list"> <table> <tr> <th>Име</th></tr>
<tr> <td align="left"><strong> БРНАБИЋ АНА </strong> <br/>шеф Делегације </td> <td nowrap>СНС</td></tr>
<tr> <td align="left"><strong> ГРБОВИЋ ПАВЛЕ </strong> <br/>члан Делегације </td> <td nowrap>ГДП</td></tr></table></div>""")

NEWS = WRAP.format("""<div class="main_left"><a title="t" href="/Прва_седница.54098.43.html"><img src="a.jpg"></a>
<h3> <a title="t" href="/Прва_седница.54098.43.html">Прва седница Народне скупштине Републике Србије у Петнаестом сазиву</a> </h3>
<div class="clear"></div> <p class="posted">Уторак, 17. новембар 2026. |</p></div>
<ul><li><h4><a href="/Потпредседница.54080.43.html">Парламентарна делегација Азербејџана на састанку са потпредседницом</a></h4></li>
<li><h4><a href="/Председница.54068.43.html">Председница Народне скупштине састала се са делегацијом</a></h4></li>
<li><h4><a href="/Изабрани.54100.43.html">Изабрани чланови радних тела</a></h4></li></ul>""")


def test_person():
    assert offices.person(SPEAKER) == ("АЛЕКСАНДАР ЧУПИЋ", ["Председник Народне скупштине"])


def test_blocks():
    assert offices.blocks(VICE) == [("Јелена Петровић", "Посланичка група „Студентска листа“"),
                                    ("Тибор Лазар", "Посланичка група „Студентска листа“")]


def test_parts_once_and_only_the_listings():
    found = offices.parts(LISTING, offices.ARCHIVE["14"]["committees"])
    assert [t for t, _ in found] == ["Одбор за спољне послове", "Одбор за финансије"]
    assert found[0][1].startswith("https://www.parlament.gov.rs/")


def test_committee_roles_and_deputies():
    rows = offices.committee(COMMITTEE)
    assert [(r["name"], r["role"]) for r in rows] == [
        ("АЛЕКСИЋ МИРОСЛАВ", "члан"), ("ЂОКИЋ УРОШ", "заменик члана"),
        ("ЈОВАНОВ МИЛЕНКО", "председник"), ("МАРКОВИЋ АЛЕКСАНДАР", "заменик члана"),
        ("ЈОВАНОВИЋ БРАНИМИР", "заменик председника"), ("КАРАНАЦ ЈАСМИНА", "заменик члана")]
    assert rows[0]["group"] == "Народни покрет Србије"


def test_delegation():
    assert offices.delegation(DELEGATION) == [{"name": "БРНАБИЋ АНА", "role": "шеф Делегације"},
                                              {"name": "ГРБОВИЋ ПАВЛЕ", "role": "члан Делегације"}]


def test_news_and_the_rule():
    items = offices.news(NEWS)
    assert [x["id"] for x in items] == ["54098", "54080", "54068", "54100"]  # the margin's link is not the page's
    assert items[0]["date"] == "17. новембар 2026."
    # "Председница Народне скупштине" is no sitting; a sitting and an election are relevant
    assert [offices.relevant(x["title"]) for x in items] == [True, False, False, True]


def test_merge_news_keeps_the_day_first_seen():
    first, new = offices.merge_news([], offices.news(NEWS), "2026-11-20")
    assert len(new) == 2 and all(x["seen"] == "2026-11-20" for x in first)
    again, new = offices.merge_news(first, offices.news(NEWS), "2026-11-21")
    assert new == [] and all(x["seen"] == "2026-11-20" for x in again)
    assert [x["id"] for x in again] == ["54100", "54098", "54080", "54068"]  # newest first


def test_offices_said_and_ordered():
    found = offices.offices_of(
        speaker=offices.person(SPEAKER), vice=offices.blocks(VICE), chairs=[("Јово Бакић", 'Посланичка група "Студентска листа"')],
        committees=[("Одбор за спољне послове", "u", offices.committee(COMMITTEE))],
        delegations=[("Делегација у Интерпарламентарној унији", "d", offices.delegation(DELEGATION))],
        sources={"speaker": "s", "vice": "v", "group": "g"})
    said = {o["name"]: offices.say(o, latin) for o in found}
    assert said["АЛЕКСАНДАР ЧУПИЋ"] == "Predsednik Narodne skupštine"
    assert said["Јелена Петровић"] == "Potpredsednik Narodne skupštine"
    assert said["Јово Бакић"] == "Poslanička grupa Studentska lista: predsednik"
    assert said["ЈОВАНОВ МИЛЕНКО"] == "Odbor za spoljne poslove: predsednik"
    assert said["ЂОКИЋ УРОШ"] == "Odbor za spoljne poslove: zamenik člana"
    assert said["БРНАБИЋ АНА"] == "Delegacija u Interparlamentarnoj uniji: šef"
    one = [{"kind": "delegation", "role": "члан Делегације", "body": "Д"}, {"kind": "committee", "role": "члан", "body": "Б"},
           {"kind": "committee", "role": "председник", "body": "Ш"}, {"kind": "vice", "role": "потпредседник", "body": "Н"}]
    assert [o["kind"] + "/" + o["role"] for o in sorted(one, key=offices.order)] == [
        "vice/потпредседник", "committee/председник", "committee/члан", "delegation/члан Делегације"]


def test_since_kept():
    o = {"name": "A", "kind": "vice", "role": "потпредседник", "body": "Н"}
    assert offices.keep_since([{**o, "since": "2026-11-19"}], [o], "2026-11-20")[0]["since"] == "2026-11-19"
    assert offices.keep_since([], [o], "2026-11-20")[0]["since"] == "2026-11-20"


HISTORY_PAGE = """<!-- OCP content start --><table>
<tr><th>СКУПШТИНА</th><th>ПРЕДСЕДНИК</th><th>ПОТПРЕДСЕДНИЦИ</th><th>ГЕНЕРАЛНИ СЕКРЕТАР</th></tr>
<tr><td>Народна скупштина Републике Србије <b>XI сазив</b> (3. јун 2016. године - 3. август 2020. године)</td>
<td><b>од 6. јуна 2016.</b> Маја Гојковић</td>
<td><b>од 6. јуна 2016.</b> Константин Арсеновић <b>(до 30. јануара 2017. године)</b>, Верољуб Арсић, проф. др Владимир Маринковић и Гордана Чомић</td>
<td><b>од 6. јуна 2016. до 9. марта 2018.</b> Светислава Булајић</td></tr>
<tr><td>Народна скупштина Републике Србије <b>XIV сазив</b> (од 6. фебруара 2024. године)</td>
<td><b>од 20. марта 2024.</b> Ана Брнабић</td>
<td><b>од 20. марта 2024.</b> Сандра Божић (до 7. маја 2024. године), Един Ђерлек, Невена Ђурић (од 19. марта 2025. године) и Дуња Симоновић Братић (од 16. јуна 2025. године)</td>
<td>Срђан Смиљанић</td></tr></table><!-- OCP content end -->"""


def test_speakers_and_deputies_of_every_convocation_with_their_days():
    got = {(h["conv"], h["kind"], h["name"]): (h["since"], h["until"]) for h in offices.history(HISTORY_PAGE)}
    assert got[("11", "speaker", "Маја Гојковић")] == ("2016-06-06", "")
    assert got[("11", "vice", "Константин Арсеновић")] == ("2016-06-06", "2017-01-30")
    assert got[("11", "vice", "проф. др Владимир Маринковић")] == ("2016-06-06", "")
    assert got[("14", "vice", "Сандра Божић")] == ("2024-03-20", "2024-05-07")
    assert got[("14", "vice", "Невена Ђурић")] == ("2025-03-19", "")  # later than the others
    assert got[("14", "vice", "Дуња Симоновић Братић")] == ("2025-06-16", "")
    assert len(got) == 10 and not any("Булајић" in k[2] for k in got)  # secretaries are not offices of MPs


def test_an_earlier_convocations_offices_get_its_speaker_and_deputies():
    past = offices.history(HISTORY_PAGE)
    committee = {"name": "АНТИЋ ЗОРАН", "kind": "committee", "role": "члан", "body": "Одбор", "source": "x", "since": ""}
    rows = offices.with_history([committee], past, "14")
    assert [r["kind"] for r in rows].count("vice") == 4 and rows[-1] == committee
    speaker = next(r for r in rows if r["kind"] == "speaker")
    assert speaker["dated"] and speaker["since"] == "2024-03-20" and offices.say(speaker, lambda s: s) == "Председник Народне скупштине"
    # the newest's, read from their own pages, keep their source and get the day of the office
    now = [{"name": "АНА БРНАБИЋ", "kind": "speaker", "role": "Председник Народне скупштине", "body": "Народна скупштина",
            "source": "своја страница", "since": "2026-11-20"}]
    merged = offices.with_history(now, past, "14")
    assert merged[0]["source"] == "своја страница" and merged[0]["since"] == "2024-03-20"
    assert offices.with_history([committee], past, "12") == [committee]  # nothing known of it


def test_the_archives_cover_every_convocation_before_the_newest():
    assert sorted(offices.ARCHIVE, key=int) == ["9", "10", "11", "12", "13", "14"]


def test_names_that_are_links_to_the_mps_pages():
    rows = offices.committee(COMMITTEE15)
    assert len(rows) == 20 and [r["role"] for r in rows] == ["члан", "заменик члана"] * 10
    assert rows[0] == {"name": "ЗУКОРЛИЋ УСАМЕ", "role": "члан",
                       "group": "Народни посланици који нису чланови посланичких група"}
    assert rows[1] == {"name": "ФРИЦ САЊА", "role": "заменик члана", "group": "„Студентска листа“"}
    rows = offices.delegation(DELEGATION15)
    assert len(rows) == 14 and rows[0] == {"name": "ВУЈИЧИЋ ЈОВАН", "role": "шеф Делегације"}
    assert rows[2] == {"name": "ВУЧИЋЕВИЋ ВУКАШИН", "role": "заменик члана Делегације"}
    assert offices.committee(DELEGATION15) == [] and offices.members(DELEGATION15) == rows


def test_the_numbers_the_lists_give():
    for page, listing, many in ((COMMITTEES15, offices.COMMITTEES, 20), (DELEGATIONS15, offices.DELEGATIONS, 12)):
        assert list(offices.numbers(page, listing)) == [u for _, u in offices.parts(page, listing)]
        assert len(offices.numbers(page, listing)) == many
    n = {u.rsplit("/", 1)[1]: k for u, k in (offices.numbers(COMMITTEES15, offices.COMMITTEES)
                                             | offices.numbers(DELEGATIONS15, offices.DELEGATIONS)).items()}
    assert n["одбори.176.13.html"] == 10 and n["делегације.83.14.html"] == 14


def test_a_row_the_archive_breaks_is_read():
    """A second <tr> inside a cell (the archive, 25 Nov 2026): of a committee the list gives 17 members, 14 were read."""
    page = WRAP.format("""<tr><td align="left"> <strong> ЛАКИЋ  САЊА </strong> (члан)<br />Посланичка група А<br />
<tr> <td align="left"> ВАСИЉЕВИЋ  БРАТИМИР (заменик члана) <br/> Посланичка група А </td> </tr>""")
    assert [(r["name"], r["role"], r["group"]) for r in offices.committee(page)] == [
        ("ЛАКИЋ САЊА", "члан", "А"), ("ВАСИЉЕВИЋ БРАТИМИР", "заменик члана", "А")]


def test_members_without_a_deputy_stand_in_cells_never_closed():
    """"Одбор за права детета", 25 Nov 2026: 10 listed, the last one was not read."""
    link = '<tr><td align="left"><strong> <a href="/x.1.245.html">{}</a> </strong> (члан)<br />Посланичка група „А“<br />'
    page = WRAP.format("<table>" + link.format("БЈЕЛОБРК  МАРИЈА") + link.format("МИЛОВАНОВИЋ  МАРИЈА")
                       + '<a href="/y.2.245.html"> ПУРИЋ  ДАЛИБОРКА </a> (заменик члана) <br/> Посланичка група „А“ </td></tr>'
                       + link.format("ЧУПИЋ  АЛЕКСАНДАР") + "</table><p>Активности</p>")
    assert [(r["name"], r["role"], r["group"]) for r in offices.committee(page)] == [
        ("БЈЕЛОБРК МАРИЈА", "члан", "„А“"), ("МИЛОВАНОВИЋ МАРИЈА", "члан", "„А“"),
        ("ПУРИЋ ДАЛИБОРКА", "заменик члана", "„А“"), ("ЧУПИЋ АЛЕКСАНДАР", "члан", "„А“")]


def test_fewer_members_than_listed_are_said():
    now = dt.datetime(2026, 11, 25, tzinfo=dt.timezone.utc)
    kept = json.loads(offices.dumps("f", [], now.isoformat(), {"u": 10, "v": 9}, {"u": 1}))
    assert offices.unread(kept, now) == ["- u (na spisku 10, nije pročitano 1)"]


def test_bodies_are_not_asked_for_every_hour_and_those_unread_are_said(tmp_path, monkeypatch, capsys):
    from zailiprotiv.config import NEWEST
    kept = tmp_path / NEWEST / "offices.json"
    kept.parent.mkdir()
    asked, shape = [], {"committee": COMMITTEE15}
    clock = {"now": dt.datetime(2026, 11, 25, 20, 0, tzinfo=dt.timezone.utc)}

    class Clock(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return clock["now"]

    def fetch(url):
        asked.append(url)
        page = {offices.COMMITTEES: COMMITTEES15, offices.DELEGATIONS: DELEGATIONS15, offices.VICE: VICE,
                offices.SPEAKER: SPEAKER}.get(url, "")
        if not page and url.endswith(".13.html"):
            page = shape["committee"]
        if not page and url.endswith(".14.html"):
            page = DELEGATION15
        return page.encode("utf-8")

    def run(hours=0):
        asked.clear()
        clock["now"] += dt.timedelta(hours=hours)
        assert assembly.offices_cmd(SimpleNamespace(unread=False)) == 0
        return sum(u.endswith((".13.html", ".14.html")) for u in asked) - 2  # but for the two lists

    def said():
        capsys.readouterr()
        assert assembly.offices_cmd(SimpleNamespace(unread=True)) == 0
        return capsys.readouterr().out.splitlines()

    monkeypatch.setattr(common, "ROOT", tmp_path)
    monkeypatch.setattr(assembly.skupstina, "fetch", fetch)
    monkeypatch.setattr(assembly, "_government", lambda get: None)
    monkeypatch.setattr(assembly.dt, "datetime", Clock)
    assert run() == 32 and said() == [] and run(1) == 0 and run(24) == 0
    before = [o for o in json.loads(kept.read_text(encoding="utf-8"))["offices"] if o["kind"] == "committee"]
    assert len(before) == 400

    # the shape changes: the pages give nobody; those read before stay, it is said, and asked for again once a day
    shape["committee"] = WRAP.format("<table><tr><td><p>ФРИЦ САЊА, члан</p></td></tr></table>")
    assert run(7 * 24) == 32 and run(1) == 0 and run(22) == 0
    lines = said()
    assert len(lines) == 20 and lines[0].startswith("- https://www.parlament.gov.rs/") and "(na spisku 10, nije pročitano 10)" in lines[0]
    after = json.loads(kept.read_text(encoding="utf-8"))
    assert [o for o in after["offices"] if o["kind"] == "committee"] == before
    assert run(2) == 32

    shape["committee"] = COMMITTEE15
    assert run(25) == 32 and said() == [] and run(1) == 0
    clock["now"] += dt.timedelta(days=9)  # never read again: each reading failed
    assert len(said()) == 1 and "nisu čitani" in said()[0]


def test_what_was_listed_stands_on_lines_of_its_own():
    """The workflow's commit passes over a change of "fetched" alone; a reading of the bodies must be kept."""
    text = offices.dumps("f", [{"name": "А"}], "r", {"u": 10}, {"u": 10})
    assert json.loads(text) == {"fetched": "f", "parts_read": "r", "listed": {"u": 10}, "unread": {"u": 10}, "offices": [{"name": "А"}]}
    assert [line for line in text.splitlines() if "fetched" in line] == ['{"fetched": "f",']


def _archive_run(tmp_path, monkeypatch, capsys, kept: dict[str, list[dict]]):
    """`offices` with archives whose lists name one committee each, with the Fifteenth's page; what it printed."""
    from zailiprotiv.config import NEWEST
    for c, rows in kept.items():
        (tmp_path / c).mkdir(exist_ok=True)
        if not (tmp_path / c / "offices.json").exists():
            (tmp_path / c / "offices.json").write_text(offices.dumps("f", rows, "r"), encoding="utf-8")
    (tmp_path / NEWEST).mkdir(exist_ok=True)
    asked = []

    def fetch(url):
        asked.append(url)
        for c, pages in offices.ARCHIVE.items():
            if url == pages["committees"]:
                number = url.split(".")[-2]
                return WRAP.format(f'<table><tr><td><a href="/a.7.{number}.html">Одбор</a></td>'
                                   '<td class="members_number"><b>10</b></td></tr></table>').encode()
        return (COMMITTEE15 if "/a.7." in url else "").encode()
    monkeypatch.setattr(common, "ROOT", tmp_path)
    monkeypatch.setattr(assembly.skupstina, "fetch", fetch)
    monkeypatch.setattr(assembly, "_government", lambda get: None)
    capsys.readouterr()
    assert assembly.offices_cmd(SimpleNamespace(unread=False)) == 0
    return capsys.readouterr().out, sum("/a.7." in u for u in asked)


def test_an_archive_is_read_again_once_one_a_run_and_only_gains(tmp_path, monkeypatch, capsys):
    def rows(c):
        url = f"https://www.parlament.gov.rs/a.7.{offices.ARCHIVE[c]['committees'].split('.')[-2]}.html"
        return [{"name": m["name"], "kind": "committee", "role": m["role"], "body": "Одбор", "group": m["group"],
                 "source": url, "since": ""} for m in offices.committee(COMMITTEE15)]
    speaker = {"name": "Ана Брнабић", "kind": "speaker", "role": "Председник Народне скупштине", "body": "Народна скупштина",
               "source": "x", "since": "2024-03-20", "until": "", "dated": True}
    kept = {"13": rows("13")[:-2], "14": [speaker] + rows("14")}
    out, n = _archive_run(tmp_path, monkeypatch, capsys, kept)
    assert "convocation 13's archive: 18 kept before, 20 read, 2 added, 0 lost" in out and n == 1
    assert "added: Одбор: СИБИНОВИЋ МИКИЦА, члан" in out
    out, n = _archive_run(tmp_path, monkeypatch, capsys, kept)
    assert "convocation 14's archive: 20 kept before, 20 read, 0 added, 0 lost" in out and n == 1
    got = json.loads((tmp_path / "14" / "offices.json").read_text(encoding="utf-8"))
    assert got["offices"] == [speaker] + rows("14") and got["unread"] == {} and list(got["listed"].values()) == [10]
    assert _archive_run(tmp_path, monkeypatch, capsys, kept)[1] == 0


def test_an_archive_that_would_lose_a_row_keeps_its_own_and_stops_the_rest(tmp_path, monkeypatch, capsys):
    mine = [{"name": "АНТИЋ ЗОРАН", "kind": "committee", "role": "члан", "body": "Одбор", "source": "x", "since": ""}]
    out, n = _archive_run(tmp_path, monkeypatch, capsys, {"13": mine, "14": mine})
    assert "::warning::offices: would be lost in convocation 13: Одбор: АНТИЋ ЗОРАН, члан" in out and n == 1
    got = json.loads((tmp_path / "13" / "offices.json").read_text(encoding="utf-8"))
    assert got["offices"] == mine and got["lost"] == mine
    assert _archive_run(tmp_path, monkeypatch, capsys, {"13": mine, "14": mine})[1] == 0
    assert "listed" not in json.loads((tmp_path / "14" / "offices.json").read_text(encoding="utf-8"))
