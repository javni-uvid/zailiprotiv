from zailiprotiv import link


def test_act_names_meet():
    assert link.act_name("20. Предлог закона о оружју и муницији, који је поднела Влада;") == "zakon o oruzju i municiji"
    assert link.act_name("Zakon o oružju i municiji") == "zakon o oruzju i municiji"
    assert link.act_name("1.1. Предлог закона о изменама и допунама Закона о буџету") == \
        "zakon o izmenama i dopunama zakona o budzetu"


def test_matches_a_joined_item_but_not_a_longer_title():
    budget = "Zakon o budžetu Republike Srbije za 2026. godinu"
    assert link.matches("1. Предлог закона о буџету Републике Србије за 2026. годину, са Предлогом одлуке о давању "
                        "сагласности на Финансијски план", budget)
    assert not link.matches("1. Предлог закона о буџету Републике Србије за 2026. годину",
                            "Zakon o budžetu Republike Srbije za 2026. godinu i nešto još")
    assert not link.matches("Предлог закона о оружју", "Zakon o oružju i municiji")


def test_final_vote_is_on_the_day_passed_as_a_whole():
    laws = {"L": {"title": "Zakon o oružju i municiji", "submitted": "2026-06-01", "passed": "2026-07-10"}}
    votes = {
        "a": {"when": "2026-07-08T12:00:00", "item": "1. Предлог закона о оружју и муницији", "kind": "Гласање о предлогу закона у начелу"},
        "b": {"when": "2026-07-10T15:50:00", "item": "1. Предлог закона о оружју и муницији", "kind": "Гласање о амандману"},
        "c": {"when": "2026-07-10T15:55:01", "item": "1. Предлог закона о оружју и муницији", "kind": "Гласање о предлогу акта у целини"},
        "d": {"when": "2026-07-10T15:56:00", "item": "2. Предлог закона о изменама Кривичног законика", "kind": ""},
        "e": {"when": "2025-01-10T10:00:00", "item": "Предлог закона о оружју и муницији", "kind": ""},  # before submission
    }
    assert link.link(laws, votes) == {"L": {"votes": ["a", "b", "c"], "final_vote": "c", "matched": "exact"}}


def test_typography_doesnt_part_a_law_from_its_vote():
    assert link.matches("Предлог закона о давању гаранције у корист „Електромрежа Србије” - Рготина - Неготин",
                        'Zakon o davanju garancije u korist "Elektromreža Srbije"-Rgotina-Negotin')
    assert link.matches("Предлог закона о потврђивању Споразума о сарадњи у области заштите биља и xpане",
                        "Zakon o potvrđivanju Sporazuma o saradnji u oblasti zaštite bilja i hrane")
    assert link.act_name("Zakona o izmenama Zakona o sprečavanju dopinga u sportu") == \
        "zakon o izmenama zakona o sprecavanju dopinga u sportu"


def test_close_names_are_linked_once_and_marked():
    laws = {"A": {"title": "Zakon o zaduživanju Republike Srbije kod AIKbank akcionarsko društvo Beograd, OTP banka "
                           "Srbija akcionarsko društvo Novi Sad i Banca Intesa akcionarsko društvo Beograd za potrebe "
                           "finansiranja projekta",
                  "passed": "2026-08-31"},
            "B": {"title": "Zakon o nečemu sasvim drugom", "passed": "2026-08-31"}}
    votes = {"v": {"when": "2026-08-31T10:00:00", "kind": "Гласање о предлогу акта у целини",
                   "item": "5. Предлог закона о задуживању Републике Србије код AIKBANKA акционарско друштво Београд, "
                           "OTP банка Србија акционарско друштво Нови Сад и Banca Intesa акционарско друштво Београд за "
                           "потребе финансирања пројекта"}}
    out = link.link(laws, votes)
    assert out["A"] == {"votes": ["v"], "final_vote": "v", "matched": "close"}
    assert out["B"]["final_vote"] is None


def test_the_pdfs_own_name_wins_over_the_link_text():
    laws = {"V": {"title": "Zakon o potvrđivanju Sporazuma sa Venecuelom", "passed": "2025-03-13"},
            "G": {"title": "Zakon o potvrđivanju Sporazuma sa Gvatemalom", "passed": "2025-03-13"}}
    votes = {"g": {"when": "2025-03-13T17:29:51", "kind": "",
                   "item": "5. Предлог закона о потврђивању Споразума са Гватемалом",
                   "listed_as": "Предлог закона о потврђивању Споразума са Венецуелом"}}
    out = link.link(laws, votes)
    assert out["G"]["final_vote"] == "g" and out["V"]["final_vote"] is None


def test_a_typo_in_a_long_name_is_close_but_another_country_isnt():
    a = link.act_name("Zakon o zaduživanju Republike Srbije kod AikBank akcionarsko društvo Beograd, OTP Banka Srbija "
                      "akcionarsko društvo Novi Sad, Banca Intesa a.d. Beograd i UniCredit Bank Srbija")
    b = link.act_name("Предлог закона о задуживању Републике Србије код AikBanka аksionarsko друштво Београд, OTP Banka "
                      "Србија акционарско друштво Нови Сад, Banca Intesa a.d. Београд и UniCredit Bank Srbija")
    assert link.closeness(a, b) >= link.CLOSE
    v = link.act_name("Zakon o potvrđivanju Sporazuma između Republike Srbije i Bolivarske Republike Venecuele o "
                      "ukidanju viza za nosioce običnih pasoša")
    g = link.act_name("Zakon o potvrđivanju Sporazuma između Vlade Republike Srbije i Vlade Republike Gvatemale o "
                      "ukidanju viza za nosioce običnih pasoša")
    assert link.closeness(v, g) < link.CLOSE


def test_bullet_before_the_number():
    from zailiprotiv import link
    assert link.act_name(" 26. Предлог закона о изменама и допунама Закона о уџбеницима, у целини").startswith(
        link.act_name("Zakon o izmenama i dopunama Zakona o udžbenicima"))
