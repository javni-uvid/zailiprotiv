"""Who spoke when, from the live page's records (src/zailiprotiv/uzivo.py)."""
import json

from zailiprotiv import uzivo


def record(day, n=1):
    return {"dan": day, "pokriveno": [], "govori": [{"ime": "Petrović Petar", "od": n}]}


def test_records_are_kept_by_convocation_and_the_recent_ones_taken_again(tmp_path):
    served = {"https://m.example/dani.json": {"dani": ["2026-11-10", "2026-11-16", "2026-11-17"]},
              "https://m.example/dan/2026-11-10.json": record("2026-11-10"),
              "https://m.example/dan/2026-11-16.json": record("2026-11-16"),
              "https://m.example/dan/2026-11-17.json": record("2026-11-17")}
    asked = []
    get = lambda url: (asked.append(url), served[url])[1]
    assert uzivo.pull(tmp_path, "https://m.example", today="2026-11-17", get=get) == ["2026-11-10", "2026-11-16", "2026-11-17"]
    assert (tmp_path / "14" / "uzivo" / "2026-11-10.json").exists()       # before the Fifteenth began
    assert json.loads((tmp_path / "15" / "uzivo" / "2026-11-17.json").read_text())["dan"] == "2026-11-17"
    asked.clear()
    served["https://m.example/dan/2026-11-17.json"] = record("2026-11-17", 2)  # today's record grew
    assert uzivo.pull(tmp_path, "https://m.example/", today="2026-11-17", get=get) == ["2026-11-17"]
    assert "https://m.example/dan/2026-11-10.json" not in asked              # an old day kept is not asked again
    assert uzivo.pull(tmp_path, "https://m.example/", today="2026-11-17", get=get) == []  # nothing changed


def test_a_record_that_shrank_never_replaces_the_kept_one(tmp_path):
    kept = {"dan": "2026-11-19", "pokriveno": [{"od": 0, "do": 50000}],
            "govori": [{"ime": "A", "od": 1}, {"ime": "B", "od": 2}]}
    lost = {"dan": "2026-11-19", "pokriveno": [{"od": 40000, "do": 40200}], "govori": []}
    path = tmp_path / "15" / "uzivo" / "2026-11-19.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(kept), encoding="utf-8")
    served = {"https://m.example/dani.json": {"dani": ["2026-11-19"]}, "https://m.example/dan/2026-11-19.json": lost}
    assert uzivo.pull(tmp_path, "https://m.example", today="2026-11-20", get=served.get) == []
    assert json.loads(path.read_text(encoding="utf-8")) == kept
    grown = {**kept, "govori": kept["govori"] + [{"ime": "C", "od": 3}]}
    served["https://m.example/dan/2026-11-19.json"] = grown
    assert uzivo.pull(tmp_path, "https://m.example", today="2026-11-20", get=served.get) == ["2026-11-19"]


def test_a_day_belongs_to_the_convocation_of_its_dates():
    assert uzivo.convocation("2026-11-17") == "15" and uzivo.convocation("2026-11-16") == "14"
    assert uzivo.convocation("2001-01-01") is None


def test_speeches_are_lined_up_with_the_record_by_the_order_of_names():
    say = lambda who, day=1, chair=False: {"speaker": who, "day": day, "chair": chair, "text": "…"}
    notes = {"days": [{"day": 1, "listed_date": "2026-11-17"}, {"day": 2, "listed_date": "2026-11-18"}],
             "speeches": {"00": say("ПРЕДСЕДНИК", chair=True), "01": say("ПЕТАР ПЕТРОВИЋ"),
                          "02": say("ПРЕДСЕДНИК", chair=True), "03": say("ПЕТАР ПЕТРОВИЋ"),  # his again: one run
                          "04": say("МАРКО ЈОВАНОВИЋ"), "05": say("НИНА НИКОЛИЋ"), "06": say("ЛАЗАР ЛАЗИЋ"),
                          "07": say("МАРКО ЈОВАНОВИЋ", day=2)}}
    turn = lambda name, sq, n=3: {"ime": name, "od": 1794920000 + sq * 5, "okvira": n, "video": "v1", "sq_od": sq,
                                  "segment": 5.0}
    rec = {"dan": "2026-11-17", "govori": [
        turn("Petrović Petar", 100), turn("Petrović Petar", 130),     # one run, as in the notes
        turn("Jovanović Marko", 200), turn("Šum Neki", 250, n=1),      # read in one frame: left out
        turn("Lazić Lazar", 300)]}                                       # Nina's turn was in a gap
    got = uzivo.minutes(notes, {"2026-11-17": rec})
    assert got["01"] == {"video": "v1", "t": 495, "at": 1794920500}     # (100 - 1) segments of 5 s
    assert set(got) == {"01", "04", "06"}                               # no guess for Nina, none for day 2
    assert "03" not in got                                              # within Petar's turn


def test_a_sitting_is_on_while_the_live_page_reads_someone(tmp_path):
    from zailiprotiv import uzivo
    now = 1_795_000_000
    reading = {"stanje": "nepoznato", "provereno": now - 60, "sada": None, "ranije": False,
               "danas": [{"ime": "A", "do": now - 600}]}
    assert uzivo.live_now(reading, now)
    assert not uzivo.live_now({**reading, "provereno": now - 3600}, now)  # the page stopped reading
    assert not uzivo.live_now({**reading, "danas": [{"do": now - 3 * 3600}]}, now)  # a broadcast with nobody in it
    assert not uzivo.live_now({**reading, "ranije": True}, now)  # the list of an earlier day
    assert uzivo.live_mark(tmp_path, "https://m/", now, get=lambda url: reading) and (tmp_path / "live.json").exists()
    assert not uzivo.live_mark(tmp_path, "https://m/", now + 4 * 3600, get=lambda url: reading)
    assert json.loads((tmp_path / "live.json").read_text()) == {"live": False}
