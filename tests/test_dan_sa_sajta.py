"""The site's files asked for while no broadcast is on (worker.run, 25 Nov 2026): a day corrected from the notes reached the
page only at a restart."""
import json
import socket
import sys
import threading
import time as clock_
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "live"))

from uzivo import config, mreza  # noqa: E402
from uzivo.state import Tracker  # noqa: E402

DAY = {"dan": "2026-11-25", "izvor": "govor", "govori": []}


@pytest.fixture
def worker(monkeypatch):
    """worker.py without OCR (Tesseract is not where the tests run) and without the net."""
    ocr = ModuleType("uzivo.ocr")
    ocr.caption = ocr.clock = ocr.outlined = None
    monkeypatch.setitem(sys.modules, "uzivo.ocr", ocr)
    monkeypatch.delitem(sys.modules, "uzivo.worker", raising=False)
    from uzivo import worker as w

    def none(turned):
        raise w.NotLive("none")
    monkeypatch.setattr(w, "resolve_input", none)
    yield w
    sys.modules.pop("uzivo.worker", None)


def going(w, monkeypatch, hours, site, tracker=None):
    """The loop with no broadcast for so many hours of a clock of its own; the seconds at which each file was asked for,
    and at which the loop's clock stood furthest behind."""
    now, asked, behind = [1795600000.0], [], []
    began = now[0]
    t = tracker or Tracker(None, "Europe/Belgrade")
    t.tick = lambda *a, **k: behind.append(now[0] - t.looped)

    def got(url, **kw):
        asked.append((round(now[0] - began), url, kw))
        return site(url, now)
    monkeypatch.setattr(w, "time", SimpleNamespace(time=lambda: now[0]))
    monkeypatch.setattr(w.mreza, "site", got)
    stop = SimpleNamespace(is_set=lambda: now[0] - began >= hours * 3600, wait=lambda s: now.__setitem__(0, now[0] + s))
    w.run(t, stop)
    return t, asked, behind


def files(url, now):
    return json.dumps(DAY if url == config.DAY_URL else {"mps": []} if url == config.ROSTER_URL else {})


def test_with_no_broadcast_the_site_is_asked_after_an_hour_and_not_before(worker, monkeypatch, tmp_path):
    monkeypatch.setattr(config, "STATE_PATH", str(tmp_path / "stanje.json"))
    _, asked, _ = going(worker, monkeypatch, 2.5, files)
    days = [at for at, url, _ in asked if url == config.DAY_URL]
    assert len(days) == 3 and days[0] == 0 and all(3600 < b - a <= 3600 + 2 * worker.WAIT for a, b in zip(days, days[1:]))
    assert len(asked) == 12  # the four files each time
    assert all(kw == {"timeout": worker.ASK, "whole": worker.READ} for _, _, kw in asked)


def test_a_day_the_site_corrected_comes_with_no_restart(worker, monkeypatch, tmp_path):
    monkeypatch.setattr(config, "STATE_PATH", str(tmp_path / "stanje.json"))
    old = {**DAY, "izvor": "uzivo"}
    begun = []

    def site(url, now):
        begun.append(now[0])
        return json.dumps(old if now[0] - begun[0] < 1800 else DAY) if url == config.DAY_URL else files(url, now)
    t, _, _ = going(worker, monkeypatch, 0.6, site)
    assert t.recording["izvor"] == "uzivo"  # within the hour it stands
    begun.clear()
    t, _, _ = going(worker, monkeypatch, 1.2, site)
    assert t.recording["izvor"] == "govor"


def test_a_site_that_does_not_answer_costs_its_time_and_is_asked_again_next_hour(worker, monkeypatch, tmp_path):
    monkeypatch.setattr(config, "STATE_PATH", str(tmp_path / "stanje.json"))
    worst = 4 * worker.ASK + worker.ASK + worker.READ + worker.ASK  # every address tried, the answer, the reading's last piece
    looped = []
    t = Tracker(None, "Europe/Belgrade")
    t.recording = {**DAY, "izvor": "uzivo"}

    def down(url, now):
        looped.append(now[0] - t.looped)  # since when the loop's clock stands as this file is asked for
        now[0] += worst
        looped.append(now[0] - t.looped)
        raise TimeoutError("no answer")
    t, asked, behind = going(worker, monkeypatch, 2.5, down, t)
    from uzivo import cuvar
    assert len(asked) == 12 and t.recording["izvor"] == "uzivo"  # three rounds, the last good copy kept
    assert max(looped) <= worst + worker.WAIT < cuvar.STANDS and max(behind) == 0


def test_an_error_nobody_thought_of_does_not_end_the_loop(worker, monkeypatch, tmp_path):
    monkeypatch.setattr(config, "STATE_PATH", str(tmp_path / "stanje.json"))
    calls = []

    def get(self):
        calls.append(1)
        if len(calls) > 1:
            raise RuntimeError("x")
        return self.roster
    monkeypatch.setattr(worker.RosterKeeper, "get", get)
    _, _, behind = going(worker, monkeypatch, 0.5, files)
    assert len(calls) > 20 and len(behind) > 20


def test_a_file_that_comes_drop_by_drop_is_given_up():
    s = socket.create_server(("127.0.0.1", 0))

    def drip():
        c, _ = s.accept()
        try:
            c.recv(4096)
            c.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 1000\r\n\r\n")
            for _ in range(100):
                c.sendall(b"x")
                clock_.sleep(0.05)
        except OSError:
            pass
        finally:
            c.close()
    threading.Thread(target=drip, daemon=True).start()
    began = clock_.monotonic()
    with pytest.raises(TimeoutError):
        mreza.site(f"http://127.0.0.1:{s.getsockname()[1]}/x", timeout=1, whole=0.4)
    assert clock_.monotonic() - began < 2
    s.close()


def test_a_whole_file_is_read_as_before():
    s = socket.create_server(("127.0.0.1", 0))
    body = ("ж" * 200_000).encode()

    def whole():
        c, _ = s.accept()
        c.recv(4096)
        c.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: %d\r\n\r\n" % len(body) + body)
        c.close()
    threading.Thread(target=whole, daemon=True).start()
    assert mreza.site(f"http://127.0.0.1:{s.getsockname()[1]}/x", timeout=5) == "ж" * 200_000
    s.close()


def test_a_file_cut_short_is_not_taken_for_whole():
    s = socket.create_server(("127.0.0.1", 0))

    def cut():
        c, _ = s.accept()
        c.recv(4096)
        c.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 10\r\n\r\n{}")
        c.close()
    threading.Thread(target=cut, daemon=True).start()
    with pytest.raises(OSError):
        mreza.site(f"http://127.0.0.1:{s.getsockname()[1]}/x", timeout=5)
    s.close()
