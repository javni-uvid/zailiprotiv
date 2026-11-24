"""dnevnik.py: what the tracker was told, kept and gone through again."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "live"))

from uzivo import dnevnik, state, state_view  # noqa: E402
from uzivo.names import Roster  # noqa: E402
from uzivo.state import Tracker  # noqa: E402

ROSTER = Roster.from_json(json.dumps({"mps": [
    {"n": "Petrović Petar", "s": "petrovic-petar", "g": "PG A"}, {"n": "Marković Marko", "s": "markovic-marko", "g": "PG B"}]}))


def test_a_day_told_again_comes_to_the_same_record(tmp_path, monkeypatch):
    """24 Nov 2026: a rule for who speaks is tried on a kept day before it runs live. The lines hold every call as it
    came, a Person and a set among them, and the same rules told the same lines make the same turns."""
    clock = dnevnik._Clock()
    monkeypatch.setattr(state, "time", clock)
    monkeypatch.setattr(state_view, "time", clock)
    petar, marko = ROSTER.people
    base = 1795510000.0
    t = Tracker(None, "Europe/Belgrade")
    dnevnik.attach(t, tmp_path / "ulazi", clock=clock.time)

    def at(sec, call, *args, **more):
        clock.now = base + sec
        getattr(t, call)(*args, **more)
    at(0, "observe", None)
    at(5, "observe", petar, "PG A")
    at(10, "observe", None)
    at(15, "observe", petar, "PG A")
    for sec in range(20, 200, 5):  # the broadcast goes on, no caption
        at(sec, "observe", None)
    at(200, "say", base + 180, "Reč ima narodni poslanik Marko Marković.", chair=True)
    at(205, "heard", marko, "prepis", base + 200, base + 200)
    at(260, "heard", marko, "glas", base + 205, base + 255, tracked={"markovic-marko"})
    at(300, "note", base + 290, "Pauza", "Određujem pauzu.", "prepis")
    at(305, "tick")
    f = tmp_path / "ulazi" / "2026-11-24.jsonl"
    with open(f, "a", encoding="utf-8") as torn:
        torn.write('{"t": 17955103')  # a stop in the middle of a line
    told = dnevnik.lines(f)
    assert [r["m"] for r in told] == ["observe"] * 40 + ["say", "heard", "heard", "note", "tick"]
    assert told[1]["a"][0] == {"__p": [petar.key, "Petrović Petar", "petrovic-petar", "PG A"]} and told[42]["k"] == {"tracked": {"__s": ["markovic-marko"]}}
    monkeypatch.undo()
    again = dnevnik.again(told)
    turns = lambda x: [(d["name"], round(d["start"]), round(d["seen"]), d.get("izvor")) for d in x.turns]
    assert turns(again) == turns(t) and [d[0] for d in turns(t)] == ["Petrović Petar", "Marković Marko"]
    assert again.cover == t.cover and state.time is __import__("time")  # the clock put back


def test_a_line_that_cannot_be_kept_is_never_in_the_calls_way(tmp_path):
    t = Tracker(None, "Europe/Belgrade")
    dnevnik.attach(t, tmp_path / "ulazi", clock=lambda: 1 / 0)
    t.observe(None, now=1795510000.0)
    assert t.status != "" and not list((tmp_path / "ulazi").glob("*.jsonl"))
