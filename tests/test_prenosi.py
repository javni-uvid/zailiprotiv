"""The day on YouTube between the broadcast's end and the archive's file (live/uzivo/prenosi.py): one process and two."""
import json
import sys
import threading
import time
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "live"))

from uzivo import citac, config, prenosi, sada, stream  # noqa: E402
from uzivo.names import Roster  # noqa: E402
from uzivo.page import fragment, page  # noqa: E402
from uzivo.state import NO_STREAM, Tracker  # noqa: E402
from uzivo.state_base import _write  # noqa: E402

TZ = ZoneInfo("Europe/Belgrade")
NOW = 1795510000.0  # 24 Nov 2026
DAY, VIDEO = "2026-11-24", "RdPk6Vq7MJE"
SITE = "https://zailiprotiv.rs/"
LIST = {"mps": [{"n": "Petrović Petar", "s": "petrovic-petar", "g": "PG A"}, {"n": "Marković Marko", "s": "markovic-marko", "g": "PG B"}]}


@pytest.fixture
def day(tmp_path, monkeypatch):
    """A broadcast of ten minutes, over: the tracker, its keeper (with what YouTube says) and the page's reader."""
    monkeypatch.setattr(config, "STATE_PATH", str(tmp_path / "stanje.json"))
    for mod in (stream, sada):
        monkeypatch.setattr(mod, "VIDEO", {})
    clock = {"t": NOW}
    monkeypatch.setattr(time, "time", lambda: clock["t"])
    t = Tracker(config.STATE_PATH, "Europe/Belgrade")
    t.roster = Roster.from_json(json.dumps(LIST))
    _write(tmp_path / "podaci.json", LIST)
    asked, says = [], {"yes": True}
    k = prenosi.Keeper(t, threading.Event(), ask=lambda v: (asked.append(v), says["yes"])[1])
    petar, marko = t.roster.people
    for n in range(0, 600, 5):
        clock["t"] = NOW + n
        t.observe(petar if n < 300 else marko, "PG A" if n < 300 else "PG B", now=NOW + n, at={"video": VIDEO, "sq": 100 + n // 5, "seg": 5.0})
        k.note()
        k.look()
    assert asked == [] and t.broadcasts == {} and t.snapshot()["prenos"]["video"] == VIDEO  # nothing asked while it is on
    clock["t"] = NOW + 700
    t.tick(now=NOW + 700)
    assert t.status == NO_STREAM
    return t, k, citac.Reader(config.STATE_PATH, "Europe/Belgrade"), tmp_path, clock, asked, says


def links(snap):
    return [(d["video"], d["snimak"]) for d in snap["danas"] if d["snimak"] is not None]


def both(t, reader, clock):
    """The snapshot of one process and of two: the same."""
    sada.Pulse(t, threading.Event()).step(clock["t"])
    t._snap = None
    mine, theirs = t.snapshot(now=clock["t"]), reader.snapshot(now=clock["t"])
    assert mine == theirs
    return mine


def test_the_last_days_speeches_are_played_from_its_public_video_until_the_archive_has_it(day):
    t, k, reader, base, clock, asked, says = day
    assert links(both(t, reader, clock)) == []  # not before YouTube has said so
    k.look()
    snap = both(t, reader, clock)
    begun = json.loads((base / "prenosi" / f"{DAY}.json").read_text(encoding="utf-8"))["prenosi"][0]["pocetak"]
    assert asked == [VIDEO] and begun == NOW - (100 - config.RECORDING_LEAD) * 5
    assert links(snap) == [(VIDEO, int(NOW + 300 - begun)), (VIDEO, int(NOW - begun))]
    for cyr in (False, True):
        html = fragment(snap, cyr=cyr, site=SITE, tz=TZ)
        assert html.count('class="time tp" ') == 2 and f'data-yt="{VIDEO}" data-t="{int(NOW - begun)}"' in html
        whole = page(snap, cyr=cyr, site=SITE, tz=TZ)
        assert f'class="play" data-yt="{VIDEO}"' in whole and "<iframe" not in whole.split("<script>")[0]  # only a button
        assert ("са Јутјуба се ништа не учитава" if cyr else "sa Jutjuba se ništa ne učitava") in whole
    rec = {"dan": DAY, "izvor": "uzivo", "govori": [], "datoteke": [{"url": "https://arhiva.videonet.co.rs/x.mp4", "od": int(NOW) - 10, "trajanje": 900}]}
    t.use_recording(rec)
    k.look()
    snap = both(t, reader, clock)
    assert t.broadcasts == {} and snap["otvoreno"] == [] and all(d["datoteka"] for d in snap["danas"])
    clock["t"] += 10000
    k.look()
    assert asked == [VIDEO]  # and nothing is asked any more


def test_one_question_in_ten_minutes_a_no_drops_the_links_and_the_next_yes_brings_them_back(day):
    t, k, reader, base, clock, asked, says = day
    for _ in range(20):
        k.look()
        clock["t"] += 29
    assert len(asked) == 1 and len(links(both(t, reader, clock))) == 2
    says["yes"] = False
    clock["t"] += 60
    k.look()
    snap = both(t, reader, clock)
    assert len(asked) == 2 and links(snap) == [] and "data-yt" not in page(snap, cyr=False, site=SITE, tz=TZ).split("<script>")[0]
    says["yes"] = True
    clock["t"] += 300
    k.look()
    assert len(asked) == 2 and links(both(t, reader, clock)) == []
    clock["t"] += 301
    k.look()
    assert len(asked) == 3 and len(links(both(t, reader, clock))) == 2
    clock["t"] += prenosi.INTERVAL + prenosi.GRACE + 1  # nobody asks any more: the answer is old, for both
    assert links(both(t, reader, clock)) == []


def test_a_restart_does_not_ask_again_before_its_time(day):
    t, k, reader, base, clock, asked, says = day
    k.look()
    again = Tracker(config.STATE_PATH, "Europe/Belgrade")
    again.roster = t.roster
    k2 = prenosi.Keeper(again, threading.Event(), ask=k.ask)
    clock["t"] += 100
    k2.look()
    assert asked == [VIDEO] and len(links(both(again, reader, clock))) == 2  # the kept answer


def test_a_file_put_there_by_hand_is_enough_and_a_wrong_or_missing_one_leaves_the_page_as_it_was(day):
    t, k, reader, base, clock, asked, says = day
    f = base / "prenosi" / f"{DAY}.json"
    f.unlink()
    k.look()
    assert asked == [] and links(both(t, reader, clock)) == []
    row = {"video": VIDEO, "pocetak": NOW - 490.5, "od": NOW, "do": NOW + 600}
    for wrong in ("{", "[]", '"x"', "{}", json.dumps({"prenosi": {}}), json.dumps({"prenosi": [{**row, "video": "<b>script"}]}),
                  json.dumps({"prenosi": [{**row, "pocetak": "x"}]}), json.dumps({"prenosi": [{**row, "do": NOW - 5}]}),
                  json.dumps({"prenosi": [{"video": VIDEO}], "javni": {VIDEO: 1}})):
        f.write_text(wrong, encoding="utf-8")
        k.look()
        assert asked == [] and links(both(t, reader, clock)) == [], wrong
    f.write_text(json.dumps({"prenosi": [row]}), encoding="utf-8")
    k.look()
    assert asked == [VIDEO] and links(both(t, reader, clock)) == [(VIDEO, 790), (VIDEO, 490)]
    assert json.loads(f.read_text(encoding="utf-8"))["prenosi"] == [row]


def test_a_moment_outside_what_was_read_has_no_place_and_a_stopped_clock_begins_anew():
    a = {"video": "aaaaaaaaaaa", "pocetak": NOW - 100, "od": NOW, "do": NOW + 600}
    b = {"video": "aaaaaaaaaaa", "pocetak": NOW + 900, "od": NOW + 1200, "do": NOW + 1800}
    assert prenosi.place([a, b], NOW + 10) == {"video": "aaaaaaaaaaa", "snimak": 110}
    assert prenosi.place([a, b], NOW + 1300) == {"video": "aaaaaaaaaaa", "snimak": 400}
    assert prenosi.place([a, b], NOW + 900) is None and prenosi.place([], NOW) is None
    kept = {"dan": DAY, "prenosi": [{**a, "vazi": NOW + 5}]}
    assert prenosi.shown(kept, DAY, NOW) == [a]
    assert prenosi.shown(kept, DAY, NOW + 5) == prenosi.shown(kept, "2026-11-25", NOW) == prenosi.shown({}, DAY, NOW) == []


def test_only_a_clear_yes_is_a_yes(monkeypatch):
    import urllib.error
    import urllib.request
    seen = []

    class Answer:
        status = 200

        def __init__(self, body):
            self.body = body

        def read(self, n=-1):
            return self.body

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def opens(body):
        def f(req, timeout=0):
            seen.append(req)
            if isinstance(body, Exception):
                raise body
            return Answer(body)
        monkeypatch.setattr(urllib.request, "urlopen", f)
    opens(b'{"type": "video", "title": "x"}')
    assert prenosi.public(VIDEO)
    assert "zailiprotiv" in seen[0].get_header("User-agent") and seen[0].full_url.startswith("https://www.youtube.com/oembed?")
    for no in (b"", b"<html>", b"[]", b'{"type": "photo"}', TimeoutError(), urllib.error.HTTPError("u", 403, "x", {}, None)):
        opens(no)
        assert not prenosi.public(VIDEO)
    n = len(seen)
    assert not prenosi.public("x&y=1") and len(seen) == n


def test_the_keeper_stops_linking_when_it_fails(day, monkeypatch):
    t, k, reader, base, clock, asked, says = day
    k.look()
    assert t.broadcasts

    def broken(now=None):
        raise OSError("disk")
    monkeypatch.setattr(k, "look", broken)

    class Once(threading.Event):
        def wait(self, timeout=None):
            self.set()
            return True
    k.halt = Once()
    k.run()
    assert t.broadcasts == {}
