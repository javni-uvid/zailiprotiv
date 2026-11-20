from zailiprotiv import offices
from zailiprotiv.translit import latin

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
