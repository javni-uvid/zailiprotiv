"""The day's summary by mail (live/uzivo/mejl.py) and who is who in it (live/uzivo/mere.py), on 19 Nov 2026's cases."""
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "live"))

from uzivo import mejl, mere  # noqa: E402

TZ = ZoneInfo("Europe/Belgrade")
ROLL = mere.Roll([
    mere.MP("Brnabić Ana", group="Aleksandar Vučić - Srbija pobeđuje"),
    mere.MP("Jovanov Milenko", group="Aleksandar Vučić - Srbija pobeđuje"),
    mere.MP("Jovanović Nataša", group="Aleksandar Vučić - Srbija pobeđuje"),
    mere.MP("Bakić Jovo", group="Studentska lista"),
    mere.MP("Tandir Samir", group="Aleksandar Vučić - Srbija pobeđuje"),
    mere.MP("Stojković Miloš", group="Aleksandar Vučić - Srbija pobeđuje"),
    mere.MP("Stojković Ana", group="Studentska lista"),
    mere.MP("Dimović Feđa", group="Studentska lista"),
    mere.MP("Radeta Vjerica", group="Aleksandar Vučić - Srbija pobeđuje"),
    mere.MP("Pastor Balint", party="SVM-VMSZ"),
    mere.MP("Kamberi Šaip", party="-"),
])


def at(hhmm: str) -> float:
    h, m = map(int, hhmm.split(":"))
    return datetime(2026, 11, 19, h, m, tzinfo=TZ).timestamp()


def names(mps):
    return [p.name for p in mps]


def test_a_name_in_any_case_is_the_mp_as_the_list_writes_it():
    assert names(ROLL.find("opomene poslanici Anji Brnabić i poslaniku Milinku Jovanovu")) == ["Brnabić Ana", "Jovanov Milenko"]
    assert names(ROLL.find("Gospodine Bakiću, izričem opomenu")) == ["Bakić Jovo"]
    assert names(ROLL.find("Vjerici Radeti")) == ["Radeta Vjerica"]
    assert names(ROLL.find("Jovanović je govorila")) == ["Jovanović Nataša"]  # not Jovanov, a shorter name
    assert ROLL.find("Stojković je postavljao pitanja") == []  # two of the name: never guessed
    assert names(ROLL.find("Stojković je postavljao pitanja", prefer=ROLL.one("Stojković Miloš"))) == ["Stojković Miloš"]


def test_the_list_is_the_lists_never_the_models():
    assert ROLL.one("Pastor Balint").label == "SVM-VMSZ"
    assert ROLL.one("Kamberi Šaip").label == "van poslaničkih grupa"
    assert mere.roll_from([{"name": "ПАСТОР проф. др БАЛИНТ", "group": "", "party": "СВМ-VMSZ"},
                           {"name": "МРДИЋ УГЉЕША", "group": "Александар Вучић - Србија побеђује", "party": "СНС"}]).mps == [
        mere.MP("Pastor Balint", party="SVM-VMSZ"), mere.MP("Mrdić Uglješa", group="Aleksandar Vučić - Srbija pobeđuje", party="SNS")]


LINES = [
    {"t": at("17:00"), "vrsta": "Reč ima", "izvor": "prepis", "tekst": "Sledeći je narodni poslanik Samir Tandir."},
    {"t": at("17:03"), "vrsta": "Mera predsedavajućeg", "izvor": "model", "tekst": "Izliče vam opomenu.", "vise": {"napomena": "opomena"}},
    {"t": at("17:17"), "vrsta": "Reč ima", "izvor": "prepis", "tekst": "Sljedeći govornik je narodni poslanik Miloš Stojković."},
    {"t": at("17:21"), "vrsta": "Mera predsedavajućeg", "izvor": "model", "tekst": "Ja sam vam upravo izvrkao prvi opomen.", "vise": {"napomena": "opomena"}},
    {"t": at("17:47"), "vrsta": "Mera predsedavajućeg", "izvor": "model", "tekst": "vi ste njega opomenuli pa ste ga opomenuli i drugi put", "vise": {"napomena": "opomena"}},
    {"t": at("17:54"), "vrsta": "Mera predsedavajućeg", "izvor": "model", "tekst": "Izričem opomenu i vama, prišli ste bez poziva.", "vise": {"napomena": "opomena"}},
    {"t": at("18:24"), "vrsta": "Mera predsedavajućeg", "izvor": "model", "tekst": "ja sam dao opomene poslanici Anji Brnabić i poslaniku Milinku Jovanovu",
     "vise": {"kome": "Anji Brnabić i Milinku Jovanovu", "napomena": "opomena"}},
    {"t": at("19:05"), "vrsta": "Mera predsedavajućeg", "izvor": "model", "tekst": "I moram da vam čestitam, ali u negativnom kontekstu", "vise": {"napomena": "opomena"}},
    {"t": at("19:29"), "vrsta": "Reč ima", "izvor": "prepis", "tekst": "Dimović Feđa"},
    {"t": at("19:32"), "vrsta": "Mera predsedavajućeg", "izvor": "model", "tekst": "Oduzao sam vam reć zato što ste probili vreme.", "vise": {"napomena": "oduzimanje reči"}},
    {"t": at("19:58"), "vrsta": "Mera predsedavajućeg", "izvor": "model", "tekst": "Samiru Tandiru ste dali opomenu, ovom čoveku niste.", "vise": {"kome": "Samir Tandir", "napomena": "opomena"}},
    {"t": at("22:00"), "vrsta": "Mera predsedavajućeg", "izvor": "prepis", "tekst": "Gospodine Bakiću, izričajam opomenu"},
    {"t": at("22:00"), "vrsta": "Mera predsedavajućeg", "izvor": "model", "tekst": "Gospodine Bakiću, izričajam opomenu", "vise": {"kome": "Bakić", "napomena": "opomena"}},
]
STRETCHES = [{"tok": [
    {"vreme": "17:01", "sta": "Tandir je postavljao pitanja kandidatima. Predsedavajući je zbog toga izrekao opomene, u 17:03 i 17:05."},
    {"vreme": "17:18", "sta": "Stojković je postavljao pitanja. Predsedavajući mu je izrekao opomenu u 17:21 i drugu opomenu u 17:23."},
    {"vreme": "18:05", "sta": "Predsedavajući je pitao da li su Jovanov i Brnabić dobili opomene u 18:05."},
]}]


def test_the_chairs_measures_and_to_whom():
    got = [(m.vreme, m.mera, names(m.kome), m.kako) for m in mere.measures(LINES, STRETCHES, ROLL, TZ)]
    assert got == [
        ("17:03", "opomena", ["Tandir Samir"], "sažetak"),              # the stretch's summary at that minute
        ("17:21", "opomena", ["Stojković Miloš"], "sažetak"),           # of two Stojković, the one with the floor
        ("17:54", "opomena", ["Brnabić Ana", "Jovanov Milenko"], "kasnije"),  # the chair saying it at 18:24
        ("19:32", "oduzimanje reči", ["Dimović Feđa"], "za govornicom"),  # over time: who had the floor
        ("22:00", "opomena", ["Bakić Jovo"], "ime"),                     # once, though the line came twice
    ]  # 17:47, 19:05 and 19:58 only speak of warnings, and 18:24 names whom; none of them is one


SUMMARY = {"kratko": "Skupština je izabrala predsednika.",
           "odluke": [{"vreme": "13:27", "sta": "Aleksandar Čupić izabran za predsednika.", "glasovi": "za 140, protiv 0"}],
           "tok": [{"vreme": "10:04", "sta": "Otvoren je nastavak sednice."}, {"vreme": "23:57", "sta": "Kraj."}],
           "govornici": [{"ime": "Pastor Balint", "lista": "bez liste", "o_cemu": "Govorio je o manjinama."},
                         {"ime": "Bakić Jovo", "lista": "Studentska lista", "o_cemu": "Govorio je o medijima."}]}


def test_the_mail_says_who_and_which_list_from_the_list_and_nothing_of_a_model():
    measures = mere.measures(LINES, STRETCHES, ROLL, TZ)
    m = mejl.build(date(2026, 11, 19), SUMMARY, measures, ROLL, {"Bakić Jovo": 19 * 60}, unsubscribe="https://x.test/o?k=1")
    assert m.subject == "Skupština, četvrtak 19. novembar: šta je odlučeno i ko je dobio opomenu"
    assert "bez liste" not in m.html and "SVM-VMSZ" in m.html and "Balint Pastor" in m.html
    assert "AI model" not in m.html and "Kako nastaje ovaj sažetak" in m.html and "kako-racunamo#sazetak-dana" in m.html
    assert "Ana Brnabić" in m.html and "Anji" not in m.html and "opomena" in m.html and "najduže" in m.html
    assert "https://x.test/o?k=1" in m.html and "https://x.test/o?k=1" in m.text
    assert not any(tag in m.html for tag in ("<img", "<script", "<link", "url("))  # nothing loaded, nothing tracked
    cyr = mejl.build(date(2026, 11, 19), SUMMARY, measures, ROLL, cyr=True)
    assert cyr.subject.startswith("Скупштина, четвртак") and "/cir/govornici/2026-11-19" in cyr.html


def test_a_word_in_two_scripts_is_caught():
    assert mejl.mixed_words("Čupić je iznео načela, a izneo ih je jasno.") == ["iznео"]


def test_every_mail_asks_for_support_in_its_middle_and_locks_nothing():
    import json
    amounts = json.loads((Path(__file__).parents[1] / "data" / "settings.json").read_text(encoding="utf-8"))["support"]["amounts"]
    m = mejl.build(date(2026, 11, 19), SUMMARY, [], ROLL)
    for a in amounts:  # each leads to its code on the site's page
        assert f'href="https://zailiprotiv.rs/podrzi#din-{a}"' in m.html
    assert m.html.count("Časlav") == 1 and "ili koliko želiš" in m.html
    for said in (m.html.split("</title>")[1], m.text):  # after the decisions, before what was said
        assert said.upper().index("ODLUKE") < said.index("Časlav") < said.upper().index("KO JE ŠTA REKAO")
    cyr = mejl.build(date(2026, 11, 19), SUMMARY, [], ROLL, cyr=True)
    assert "https://zailiprotiv.rs/cir/podrzi#din-" in cyr.html and "Часлава" in cyr.html
    bare = mejl.build(date(2026, 11, 19), {**SUMMARY, "odluke": []}, [], ROLL)  # nothing decided: after what was said
    assert bare.html.index("Ko je šta rekao") < bare.html.index("Časlav") and bare.text.count("Časlav") == 1


def test_the_day_in_figures_is_counted_only_from_a_whole_transcript():
    from uzivo import brojevi
    day, flow = date(2026, 11, 19), [{"vreme": "10:04"}, {"vreme": "23:57"}]
    t0 = int(at("10:05"))
    said = {("p" if i % 2 else "") + str(t0 + i * 60): "Hvala, po Poslovniku. Izvinite, molim vas." for i in range(120)}
    t1 = int(at("14:04"))  # after a break of two hours, called at 12:04
    said |= {str(t1 + i * 60): "Poslovnik ove reči." for i in range(593)}
    pause = [{"t": at("12:04"), "vrsta": "Pauza"}]
    n = brojevi.count(day, flow, said, pause, TZ)
    assert n["traje"] == 833 and n["pauza"] == 120 and n["pauza_od"] == "12:04"
    assert n["poslovnik"] == 120 + 593 and n["hvala"] == n["izvinite"] == n["molim"] == 120
    assert "reci" not in brojevi.count(day, flow, said, [], TZ)  # a silence nobody called: the transcript was off
    assert "reci" not in brojevi.count(day, flow, {k: v for k, v in said.items() if int(k.lstrip("p")) >= t1}, pause, TZ)  # begun late
    assert brojevi.count(day, [{"vreme": "18:00"}, {"vreme": "01:30"}], {}, [], TZ)["traje"] == 450  # past midnight
    n |= {"reci": 69132, "strana": 230}
    got = brojevi.tiles(n, day, "17:03")
    assert got[0] == ("13 h 53 min", "od prve do poslednje reči, kao 9 fudbalskih utakmica")
    assert got[1] == ("69.000", "reči izgovoreno, kao knjiga od 230 strana") and len(got) == 4
    seen = {x for d in range(1, 8) for x in brojevi.tiles(n, date(2026, 12, d), "17:03")[2:]}
    assert len(seen) == 6 and ("6 h 59 min", "do prve opomene, u 17:03") in seen  # others by the date
    assert brojevi.tiles({}, day) == [] and brojevi.tiles({"traje": 100, "od": 600}, day) == []  # one figure is no strip


def test_the_top_says_the_day_in_one_line_and_not_how_many_decisions():
    with_title = {**SUMMARY, "naslov": "Čupić izabran za predsednika Skupštine."}
    m = mejl.build(date(2026, 11, 19), with_title, [], ROLL, numbers={"traje": 833, "od": 604, "reci": 69132, "strana": 230})
    assert "Čupić izabran za predsednika Skupštine<" in m.html and m.html.count("Skupština je izabrala predsednika.") == 1  # the preview
    assert "Dan u brojevima" in m.html and "69.000" in m.html and "DAN U BROJEVIMA" in m.text and "govornika</div>" not in m.html
    assert ">140 za</b>" in m.html and ">0 protiv</b>" in m.html  # the vote as a bar and its figures
    plain = mejl.build(date(2026, 11, 19), {**SUMMARY, "naslov": "x" * 200}, [], ROLL)  # no title: the sentence, as before
    assert plain.html.count("Skupština je izabrala predsednika.") == 2 and "Dan u brojevima" not in plain.html
    cyr = mejl.build(date(2026, 11, 19), with_title, [], ROLL, numbers={"traje": 833, "od": 604, "reci": 69132, "strana": 230}, cyr=True)
    assert "Дан у бројевима" in cyr.html and not mejl.mixed_words(cyr.text) and "140 за" in cyr.html
