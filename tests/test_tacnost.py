"""tacnost.py: the live record of who spoke when, scored against the notes' speeches."""
from zailiprotiv import tacnost


def said(*rows):
    return {"izvor": "govor", "pokriveno": [{"od": 0, "do": 2000}],
            "govori": [{"ime": n, "adresa": a, "od": od, "do": do} for n, a, od, do in rows]}


TRUTH = said(("Petrović Petar", "petrovic-petar", 100, 400), ("Marković Marko", "markovic-marko", 420, 620),
             ("Jović Jova", "jovic-jova", 700, 1000))


def test_seconds_right_wrong_missing_and_extra():
    # the record's clock 10 s late; Petar's end given to Marko, Jova not seen at all, a name during the chair's words
    live = {"pokriveno": [{"od": 0, "do": 2000}], "govori": [
        {"ime": "Petrović Petar", "adresa": "petrovic-petar", "od": 110, "do": 360},
        {"ime": "Marković Marko", "adresa": "markovic-marko", "od": 360, "do": 410},
        {"ime": "Marković Marko", "adresa": "markovic-marko", "od": 430, "do": 630},
        {"ime": "Marković Marko", "adresa": "markovic-marko", "od": 1200, "do": 1260}]}
    s = tacnost.score(TRUTH, live)
    assert s["pomak"] == -10 and s["tacno"] == 250 + 200 and s["pogresno"] == 50 and s["nedostaje"] == 300
    assert s["visak"] == 60 and s["sekundi"] == 800 and s["udeo"] == 56.2
    assert s["govora"] == 3 and s["nadjeno"] == 2 and s["kraj_preko_30"] == 1
    assert s["zamene"] == [(50, "Petrović Petar", "Marković Marko")]
    assert "56.2%" in tacnost.told("2026-11-18", s) and "under the name of Marković Marko" in tacnost.told("2026-11-18", s)


def test_the_services_own_file_is_scored_too_and_only_what_both_cover():
    turn = lambda key, name, a, b, n=4: {"key": key, "name": name, "slug": key, "start": a, "seen": b, "n": n}
    live = {"cover": [[0, 650]], "turns": [turn("petrovic-petar", "Petrović Petar", 100, 400),
                                           turn("markovic-marko", "Marković Marko", 420, 620),
                                           turn("jovic-jova", "Jović Jova", 300, 310, n=1)]}  # one frame: no turn
    s = tacnost.score(TRUTH, live)
    assert s["udeo"] == 100.0 and s["sekundi"] == 500 and s["govora"] == 2 and s["nadjeno"] == 2 and s["pocetak"] == 0
    assert tacnost.score(TRUTH, {"govori": []}) is None
    assert tacnost.score(TRUTH, {"pokriveno": [{"od": 5000, "do": 6000}], "govori": [
        {"ime": "Jović Jova", "adresa": "jovic-jova", "od": 5100, "do": 5200}]}) is None


def test_a_day_without_notes_has_no_truth(tmp_path):
    import json
    for part in ("snimak", "uzivo"):
        (tmp_path / part).mkdir()
    (tmp_path / "uzivo" / "2026-11-24.json").write_text(json.dumps({"govori": TRUTH["govori"]}), encoding="utf-8")
    (tmp_path / "snimak" / "2026-11-24.json").write_text(json.dumps({**TRUTH, "izvor": "uzivo"}), encoding="utf-8")
    assert tacnost.day(tmp_path, "2026-11-24") is None and tacnost.day(tmp_path, "2026-11-25") is None
    (tmp_path / "snimak" / "2026-11-24.json").write_text(json.dumps(TRUTH), encoding="utf-8")
    assert tacnost.day(tmp_path, "2026-11-24")["udeo"] == 100.0
