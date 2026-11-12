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
    assert link.link(laws, votes) == {"L": {"votes": ["a", "b", "c"], "final_vote": "c"}}
