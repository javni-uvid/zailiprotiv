import pytest

from zailiprotiv import debates

NOTES = {"agenda": {"1": "Предлог закона о оружју", "2": "Предлог закона о лову"},
         "speeches": {"0": {"day": 1, "speaker": "ПРЕДСЕДНИК", "chair": True, "part": "general", "items": [1, 2],
                            "text": "Отварам заједнички начелни претрес."},
                      "1": {"day": 1, "speaker": "НЕНАД АБРАМОВИЋ", "chair": False, "part": "general", "items": [1, 2],
                            "text": "Оружје мора бити под контролом.\nЛов је друга тема о којој не говорим сада."},
                      "2": {"day": 2, "speaker": "ЈОВАН ЧОЛАКОВИЋ", "chair": False, "part": "detail", "items": [1],
                            "text": "Члан 3. о оружју не ваља јер ловцима отежава набавку пушака и муниције."}},
         "amendments": [], "days": []}
FINAL = {"when": "2026-07-10T15:55:01", "rows": [[1, "АБРАМОВИЋ НЕНАД", "za", "ПГ А"]]}


def test_material_attributes_and_filters():
    text = debates.material({"title": "Zakon o oružju"}, {"sections": {"reasons": "оружје оружја оружју"}}, NOTES,
                            FINAL, {}, 1)
    assert "[НЕНАД АБРАМОВИЋ | ПГ А | дан 1]\nОружје мора бити под контролом." in text
    assert "Лов је друга тема" not in text  # a joint debate: only paragraphs about this law
    assert f"[ЈОВАН ЧОЛАКОВИЋ | {debates.OUTSIDE} | дан 2]" in text


def test_quotes_checked_word_for_word():
    reply = {"predlagac": [], "podrska": ["Посланици групе ПГ А наводе да оружје мора бити под контролом."],
             "zamerke": [],
             "citati": [{"govornik": "ЈОВАН ЧОЛАКОВИЋ", "grupa": "", "dan": 2,
                         "tekst": "о оружју не ваља јер ловцима отежава набавку пушака"},
                        {"govornik": "НЕНАД АБРАМОВИЋ", "grupa": "ПГ А", "dan": 1,
                         "tekst": "Оружје мора бити строго под контролом државе."},
                        {"govornik": "НЕНАД АБРАМОВИЋ", "grupa": "ПГ А", "dan": 2,
                         "tekst": "о оружју не ваља јер ловцима отежава набавку пушака"}]}
    out, dropped = debates.parse(reply, NOTES)
    assert [q["govornik"] for q in out["citati"]] == ["ЈОВАН ЧОЛАКОВИЋ"]
    assert len(dropped) == 2  # words not said, and words said by someone else
    assert debates.silent(debates.parse({"predlagac": [], "podrska": [], "zamerke": [], "citati": []}, NOTES)[0])


def test_roles_from_the_chair():
    notes = {"speeches": {"0": {"chair": True, "text": "Реч има председник Владе, господин Милош Вучевић. "
                                                        "Реч има премијер, господин Милош Вучевић. "
                                                        "Реч има народни посланик Радомир Лазовић."}}}
    roles = debates.roles(notes)
    from zailiprotiv import mps
    assert roles[mps.key("МИЛОШ ВУЧЕВИЋ")] == "government" and roles[mps.key("РАДОМИР ЛАЗОВИЋ")] == "mp"


def test_resolve_typos_not_other_people():
    known = {debates.loose(k): k for k in ("александар марковић", "лазовић радомир", "јованов миленко")}
    assert debates.resolve("РАДОМИР ЛАЗОВЋ", known) == "лазовић радомир"
    assert debates.resolve("МИЛЕКО ЈОВАНОВ", known) == "јованов миленко"
    assert debates.resolve("АЛЕКСАНДАР МАРТИНОВИЋ", known) is None
