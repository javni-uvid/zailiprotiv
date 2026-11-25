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
    mere.MP("Bakić Jovo", group="Studentska lista", photo="1601.jpg"),
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
    assert "Opomena: Ana Brnabić, Milenko Jovanov" in m.html and "Anji" not in m.html and "opomena u 22:00" in m.html
    assert "https://x.test/o?k=1" in m.html and "https://x.test/o?k=1" in m.text
    cyr = mejl.build(date(2026, 11, 19), SUMMARY, measures, ROLL, cyr=True)
    assert cyr.subject.startswith("Скупштина, четвртак") and "/cir/govornici/2026-11-19" in cyr.html


def test_nothing_is_loaded_but_the_portraits_from_the_site_the_same_for_every_reader():
    import re
    a = mejl.build(date(2026, 11, 19), SUMMARY, [], ROLL, unsubscribe="https://x.test/o?k=1")
    b = mejl.build(date(2026, 11, 19), SUMMARY, [], ROLL, unsubscribe="https://x.test/o?k=2")
    assert not any(tag in a.html for tag in ("<script", "<link", "url(", "<iframe", "@import", "@font-face"))
    assert re.findall(r'<img src="([^"]+)"', a.html) == ["https://zailiprotiv.rs/foto/1601.jpg"]  # only who has a portrait
    assert re.findall(r"<img[^>]+>", a.html) == re.findall(r"<img[^>]+>", b.html)  # nothing of the reader in it
    assert "Portreti: Narodna skupština" in a.html and ">BP</div>" in a.html  # no portrait: the initials
    odd = mere.Roll([mere.MP("Bakić Jovo", group="Studentska lista", photo='x" onerror="y')])
    assert "<img" not in mejl.build(date(2026, 11, 19), SUMMARY, [], odd).html  # a file's name only


def test_a_word_in_two_scripts_is_caught():
    assert mejl.mixed_words("Čupić je iznео načela, a izneo ih je jasno.") == ["iznео"]


def test_every_mail_asks_for_support_in_its_middle_and_locks_nothing():
    import json
    amounts = json.loads((Path(__file__).parents[1] / "data" / "settings.json").read_text(encoding="utf-8"))["support"]["amounts"]
    m = mejl.build(date(2026, 11, 19), SUMMARY, [], ROLL)
    for a in amounts:  # each leads to its code on the site's page
        assert f'href="https://zailiprotiv.rs/podrzi#din-{a}"' in m.html
    assert m.html.count("Časlav") == 1 and "ili koliko želiš" in m.html
    for said, day_, who in ((m.html.split("</title>")[1], "PO SATU", "Govorili su"), (m.text, "DAN PO SATU", "GOVORILI SU")):
        assert said.index(day_) < said.index("Časlav") < said.index(who)  # after the day, before who spoke
    cyr = mejl.build(date(2026, 11, 19), SUMMARY, [], ROLL, cyr=True)
    assert "https://zailiprotiv.rs/cir/podrzi#din-" in cyr.html and "Часлава" in cyr.html
    bare = mejl.build(date(2026, 11, 19), {"kratko": "Sednica nije održana."}, [], ROLL)  # a day with nothing in it
    assert bare.html.count("Časlav") == 1 and "Govorili su" not in bare.html and "Sednica nije održana." in bare.html


def test_the_day_by_the_clock_has_the_steps_the_measures_and_the_decisions_once():
    day = {**SUMMARY, "naslov": "Čupić izabran za predsednika Skupštine.",
           "tok": [{"vreme": "10:04", "sta": "Otvoren je nastavak sednice."}, {"vreme": "13:27", "sta": "Izabran je predsednik."},
                   {"vreme": "17:03", "sta": "Izrečena opomena poslaniku."}, {"vreme": "00:40", "sta": "Kraj."}]}
    measures = mere.measures(LINES, STRETCHES, ROLL, TZ)
    m = mejl.build(date(2026, 11, 19), day, measures, ROLL)
    assert "Čupić izabran za predsednika Skupštine<" in m.html and m.html.count("Skupština je izabrala predsednika.") == 1  # the preview
    assert "Izabran je predsednik" not in m.html and "Izrečena opomena poslaniku" not in m.html  # said by the decision and the measure
    order = [m.html.index(x) for x in ("Otvoren je nastavak sednice", "Aleksandar Čupić izabran za predsednika", "Opomena: Samir Tandir", ">Kraj<")]
    assert order == sorted(order)  # by the clock, past midnight too
    assert ">140</span> za<" in m.html and ">0</span></td>" in m.html and "Dan u brojevima" not in m.html  # the vote in figures and a bar
    assert "Oduzimanje reči: Feđa Dimović" in m.html and "oduzimanje reči u 19:32" not in m.html  # Dimović did not speak in this summary
    plain = mejl.build(date(2026, 11, 19), {**SUMMARY, "naslov": "x" * 200}, [], ROLL)  # no title: the sentence, as before
    assert plain.html.count("Skupština je izabrala predsednika.") == 2
    cyr = mejl.build(date(2026, 11, 19), day, measures, ROLL, cyr=True)
    assert "ДАН У СКУПШТИНИ, ПО САТУ" in cyr.html and not mejl.mixed_words(cyr.text) and ">140</span> за<" in cyr.html


def test_who_spoke_is_by_lists_by_their_seats_and_the_longest_first():
    day = {**SUMMARY, "govornici": SUMMARY["govornici"] + [{"ime": "Brnabić Ana", "o_cemu": "Govorila je o odborima."},
                                                          {"ime": "Stojković Ana", "o_cemu": "Govorila je o školama."}]}
    m = mejl.build(date(2026, 11, 19), day, [], ROLL, {"Bakić Jovo": 60, "Stojković Ana": 600})
    part = m.html[m.html.index("Govorili su"):]
    order = [part.index(x) for x in ("Aleksandar Vučić - Srbija pobeđuje", "Ana Brnabić", "Studentska lista", "Ana Stojković", "Jovo Bakić",
                                     "Van poslaničkih grupa", "Balint Pastor")]
    assert order == sorted(order)  # six seats in the list, then four, then nobody's group; within a list by the time
    assert "4 poslanika, po listama" in part and "Studentska lista</span>" not in part and ">SVM-VMSZ</span>" in part


def test_the_maintainers_sentences_are_shown_only_when_added():
    quotes = [{"vreme": "12:38", "ime": "Jovo Bakić", "o_cemu": "o medijima", "tekst": "Mediji su <slobodni>.",
               "snimak": "https://arhiva.videonet.co.rs/x.mp4#t=5"},
              {"vreme": "12:40", "ime": "Pastor Balint", "o_cemu": "o manjinama", "tekst": "Manjine.", "snimak": "javascript:1"}]
    assert "Rečeno u sali" not in mejl.build(date(2026, 11, 19), SUMMARY, [], ROLL).html
    m = mejl.build(date(2026, 11, 19), SUMMARY, [], ROLL, quotes=quotes)
    assert "Rečeno u sali" in m.html and "izabrao i proverio urednik" in m.html and "REČENO U SALI" in m.text
    assert "Mediji su &lt;slobodni&gt;." in m.html and 'href="https://arhiva.videonet.co.rs/x.mp4#t=5"' in m.html and "Pusti od 12:38" in m.html
    assert "javascript" not in m.html and "„Manjine.“" in m.text  # a link only to a recording's address
