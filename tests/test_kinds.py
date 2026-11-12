import pytest

from zailiprotiv import kinds


@pytest.mark.parametrize("title,expected", [
    ("Predlog zakona o potvrđivanju Ugovora između Republike Srbije i Republike Angole o otklanjanju dvostrukog "
     "oporezivanja", "treaty"),
    ("Предлог закона о потврђивању Измене и допуне бр. 2 Споразума о зајму", "treaty"),
    ("Закон о буџету Републике Србије за 2026. годину", "finance"),
    ("Предлог закона о изменама и допуни Закона о буџету Републике Србије за 2026. годину", "finance"),
    ("Предлог одлуке о давању сагласности на Финансијски план Републичког фонда за здравствено осигурање", "finance"),
    ("Предлог закона о изменама и допунама Кривичног законика", "change"),
    ("Предлог закона о оружју и муницији, који је поднела Влада", "law"),
    ("Предлог закона о заштити потрошача", "law"),
    ("Предлог да се за члана Већа Агенције изабере", "officials"),
    ("Предлог одлуке о престанку функције члана Републичке комисије", "officials"),
    ("Предлог одлуке о избору чланова и заменика чланова одбора Народне скупштине", "assembly"),
    ("Предлог одлуке о усвајању Декларације о заштити националних и политичких права", "declaration"),
])
def test_kind_from_title(title, expected):
    assert kinds.kind(title) == expected


def test_gazette_mark_makes_a_treaty():
    assert kinds.kind("Zakon o nečemu", treaty=True) == "treaty"


def test_areas_from_article_97_only():
    assert kinds.areas([{"article": 97, "paragraph": None, "points": [6, 15, 6, 99]},
                        {"article": 99, "paragraph": 1, "points": [4]}]) == [6, 15]
    assert set(kinds.AREAS) == set(range(1, 18))
