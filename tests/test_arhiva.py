import json

from zailiprotiv import arhiva


def test_a_file_is_placed_where_the_names_read_in_it_fit_the_turns():
    start = 1_794_992_595  # the file's first second, by the clock
    turns = [("a", start + 100, start + 400), ("b", start + 420, start + 900), ("a", start + 950, start + 2000)]
    def who(t):
        at = start + t
        return next((k for k, a, b in turns if a <= at <= b), None)
    seen = [(t, who(t)) for t in range(20, 1500, 30) if who(t)]
    found = arhiva.offset(seen, turns)
    assert found and abs(found[0] - start) <= arhiva.STEP / 2 + arhiva.SLACK and found[1] == len(seen)
    # then to a few seconds, where the names change between two frames
    assert abs(arhiva.refine(found[0], seen, turns, who) - start) <= 2


def test_frames_that_dont_agree_place_nothing():
    assert arhiva.offset([(t, "a") for t in range(20, 600, 30)], [("a", 1000, 9000)]) is None  # all in one long speech
    turns = [("a", 1000, 1100), ("b", 5000, 5100)]
    assert arhiva.offset([(10, "a"), (20, "b"), (30, "a"), (40, "b")], turns) is None
    assert arhiva.offset([(10, "x")], turns) is None


def test_a_day_is_written_from_the_record_with_its_places_in_the_archive(tmp_path):
    root, start = tmp_path, 1_794_992_595
    (root / "15" / "uzivo").mkdir(parents=True)
    url = "https://arhiva.example/zas2026111910.mp4"
    (root / "15" / "videos.json").write_text(json.dumps({"days": {"2026-11-19": [{"part": 1, "title": "", "url": url}]}}))
    rec = {"dan": "2026-11-19", "pokriveno": [{"od": start, "do": start + 3000}], "govori": [
        {"ime": "Petrović Petar", "adresa": "petrovic-petar", "uloga": "Lista", "od": start + 100, "do": start + 400, "okvira": 60},
        {"ime": "Jović Jova", "adresa": "jovic-jova", "uloga": "", "od": start + 405, "do": start + 405, "okvira": 1},
        {"ime": "Petrović Petar", "adresa": "petrovic-petar", "uloga": "", "od": start + 410, "do": start + 600, "okvira": 38},
        {"ime": "Nikolić Nina", "adresa": "nikolic-nina", "uloga": "", "od": start + 700, "do": start + 1500, "okvira": 160}]}
    (root / "15" / "uzivo" / "2026-11-19.json").write_text(json.dumps(rec))
    def frames(u, names, dur):
        return [(t, arhiva._key("Petrović Petar") if 100 <= t <= 600 else arhiva._key("Nikolić Nina"))
                for t in range(110, 1500, 30) if not 600 < t < 700]
    changed = arhiva.run(root, "15", read_frames=frames, probe=lambda u: 2000.0)
    day = json.loads((root / "15" / "snimak" / "2026-11-19.json").read_text())
    assert "15/snimak/2026-11-19.json" in changed and day["izvor"] == "uzivo"
    assert [t["ime"] for t in day["govori"]] == ["Petrović Petar", "Nikolić Nina"]  # a one-frame reading left out
    first = day["govori"][0]
    assert first["datoteka"] == url and abs(first["snimak"] - 95) <= arhiva.STEP / 2 + arhiva.SLACK and first["do"] == start + 600
    kept = json.loads((root / "15" / "arhiva.json").read_text())
    assert abs(kept[url]["od"] - start) <= arhiva.STEP / 2 + arhiva.SLACK
    assert arhiva.run(root, "15", read_frames=frames, probe=lambda u: 2000.0) == []  # once placed, not again


def test_a_day_read_by_hand_only_gets_the_places_it_lacks(tmp_path):
    root, start = tmp_path, 1_794_992_595
    (root / "15" / "uzivo").mkdir(parents=True)
    (root / "15" / "snimak").mkdir(parents=True)
    old, new = "https://arhiva.example/a.mp4", "https://arhiva.example/b.mp4"
    (root / "15" / "videos.json").write_text(json.dumps({"days": {"2026-11-18": [
        {"part": 1, "title": "", "url": old}, {"part": 2, "title": "", "url": new}]}}))
    (root / "15" / "arhiva.json").write_text(json.dumps({old: {"od": start - 5000, "trajanje": 4000}}))
    rec = {"dan": "2026-11-18", "govori": [{"ime": "Nikolić Nina", "adresa": "nikolic-nina", "od": start + 700,
                                           "do": start + 1500, "okvira": 160},
                                          {"ime": "Petrović Petar", "adresa": "", "od": start + 1530,
                                           "do": start + 2200, "okvira": 130}]}
    (root / "15" / "uzivo" / "2026-11-18.json").write_text(json.dumps(rec))
    by_hand = {"dan": "2026-11-18", "izvor": "snimak", "govori": [
        {"ime": "Petrović Petar", "od": start - 4000, "do": start - 3000, "okvira": 20, "datoteka": old, "snimak": 995},
        {"ime": "Nikolić Nina", "od": start + 700, "do": start + 1500, "okvira": 80, "video": "", "snimak": None}],
        "datoteke": [{"url": old, "od": start - 5000, "trajanje": 4000}]}
    (root / "15" / "snimak" / "2026-11-18.json").write_text(json.dumps(by_hand))
    arhiva.run(root, "15", read_frames=lambda u, n, d: [(t, arhiva._key("Nikolić Nina" if t < 1500 else "Petrović Petar"))
                                                       for t in range(720, 2200, 30)], probe=lambda u: 3000.0)
    day = json.loads((root / "15" / "snimak" / "2026-11-18.json").read_text())
    assert day["izvor"] == "snimak" and day["govori"][0]["snimak"] == 995
    assert day["govori"][1]["datoteka"] == new and abs(day["govori"][1]["snimak"] - 695) <= arhiva.STEP / 2 + arhiva.SLACK
    assert [f["url"] for f in day["datoteke"]] == [old, new]
