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


def test_a_day_belongs_to_the_convocation_of_its_dates():
    assert uzivo.convocation("2026-11-17") == "15" and uzivo.convocation("2026-11-16") == "14"
    assert uzivo.convocation("2001-01-01") is None
