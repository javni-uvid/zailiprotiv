"""The measuring that ends itself when its loop stands (live/uzivo/cuvar.py), and the limits on what may hold the loop."""
import json
import re
import subprocess
import sys
import threading
import time
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

LIVE = Path(__file__).resolve().parents[1] / "live"
sys.path.insert(0, str(LIVE))

from uzivo import cuvar, obavesti, pretplata, stream  # noqa: E402

NOW = 1795613900.0


@pytest.fixture
def guard(tmp_path):
    left = []
    g = cuvar.Guard(SimpleNamespace(looped=1.0), threading.Event(), leave=lambda: left.append(1), path=tmp_path / "cuvar.json")
    g.left = left
    assert not g.step(cuvar.LOOK, NOW)  # the first look: the clock is seen for the first time
    return g


def stand(g, seconds, now=NOW):
    """Looks for so many seconds with the loop's clock still; whether the process was ended by one of them."""
    return any(g.step(cuvar.LOOK, now) for _ in range(int(seconds / cuvar.LOOK)))


def test_the_process_ends_once_the_loop_has_stood_long_enough_and_not_before(guard):
    assert not stand(guard, cuvar.STANDS - cuvar.LOOK) and guard.left == []
    assert stand(guard, cuvar.LOOK) and guard.left == [1]
    assert json.loads(guard.path.read_text(encoding="utf-8")) == {"izlasci": [NOW]}


def test_a_loop_that_turns_however_slowly_is_not_standing(guard):
    for _ in range(5):  # between sittings: 60 s waited, and YouTube asked
        assert not stand(guard, cuvar.STANDS - cuvar.LOOK)
        guard.tracker.looped += 1
        assert not guard.step(cuvar.LOOK, NOW)
    assert guard.left == []


def test_a_computer_that_slept_is_not_a_loop_that_stands(guard):
    assert not guard.step(8 * 3600, NOW)
    assert guard.stood <= 2 * cuvar.LOOK


def test_what_is_being_made_is_not_cut(guard, monkeypatch):
    with cuvar.making("the day's summary"):
        assert not stand(guard, cuvar.STANDS + 60) and guard.left == [] and not guard.path.exists()
    assert guard.step(cuvar.LOOK, NOW)
    since = time.monotonic()
    with cuvar.making("the day's summary"):
        monkeypatch.setattr(cuvar.time, "monotonic", lambda: since + cuvar.MADE_MOST + 60)
        assert cuvar._made(cuvar.time.monotonic()) == ""  # an hour of it hangs too
    monkeypatch.undo()
    assert cuvar._making == {}


def test_it_ends_three_times_in_an_hour_at_most_and_the_next_run_knows(guard):
    for n in range(cuvar.MOST):
        assert stand(guard, cuvar.STANDS, NOW + 300 * n)
        guard = cuvar.Guard(guard.tracker, threading.Event(), leave=guard.leave, path=guard.path)  # the next run
        assert not guard.step(cuvar.LOOK, NOW)
    assert not stand(guard, 3 * cuvar.STANDS, NOW + 1000)
    assert guard.step(cuvar.LOOK, NOW + cuvar.WITHIN + 1)  # the first is an hour old


def test_an_end_that_cannot_be_counted_is_not_made(guard, monkeypatch):
    guard.path.write_text('{"izlasci": "x', encoding="utf-8")
    assert not stand(guard, 2 * cuvar.STANDS)
    guard.path.unlink()

    def full(*_):
        raise OSError("no space left on device")
    monkeypatch.setattr(cuvar, "_write", full)
    assert not stand(guard, 2 * cuvar.STANDS) and guard.left == []


def test_the_log_says_once_where_the_loop_stands(guard, caplog):
    release = threading.Event()

    def a_reading_that_hangs():
        release.wait(30)
    guard.loop = threading.Thread(target=a_reading_that_hangs, daemon=True)
    guard.loop.start()
    with cuvar.making("the mail to the maintainer"):
        assert not stand(guard, cuvar.STANDS + 120)
    assert len(caplog.records) == 1 and "the mail to the maintainer" in caplog.text and "a_reading_that_hangs" in caplog.text
    assert guard.step(cuvar.LOOK, NOW) and "this process ends, 1. of at most 3" in caplog.text
    release.set()


def test_a_real_process_whose_loop_hangs_is_ended(tmp_path):
    """The main thread waits for a stop, as in merenje.main; a thread that is no daemon would hold an orderly exit."""
    code = """
import sys, threading
sys.path.insert(0, sys.argv[1])
from pathlib import Path
from types import SimpleNamespace
from uzivo import cuvar
cuvar.LOOK, cuvar.STANDS = 0.05, 0.4
lock, stop = threading.Lock(), threading.Event()
lock.acquire()
loop = threading.Thread(target=lock.acquire)
loop.start()
cuvar.Guard(SimpleNamespace(looped=1.0), stop, loop, path=Path(sys.argv[2])).start()
stop.wait()
"""
    kept = tmp_path / "cuvar.json"
    out = subprocess.run([sys.executable, "-c", code, str(LIVE), str(kept)], capture_output=True, text=True, timeout=30)
    assert out.returncode == 1 and "this process ends" in out.stderr, out.stderr
    assert len(json.loads(kept.read_text(encoding="utf-8"))["izlasci"]) == 1


def test_the_summary_the_mail_and_the_notifications_are_said_to_be_made(tmp_path, monkeypatch):
    from uzivo import sudija
    made = []

    def look(*_, **__):
        made.append(cuvar._made(time.monotonic()))
        return {}
    obavesti.Bell(str(tmp_path / "o.json"), token="t", api="https://b.rs", post=look).send()
    tracker = SimpleNamespace(snapshot=lambda now=None: {"dan": "2026-11-25", "ranije": False, "stanje": "nema_prenosa"},
                              summary_of=lambda day: {"dan": {"ukratko": "x"}})
    monkeypatch.setattr(pretplata, "to_tell", lambda *_: True)
    pretplata.Watch(tracker, SimpleNamespace(ready=look), threading.Event()).step(NOW)
    mailer = pretplata.Mailer(tmp_path, lambda *_: None)
    monkeypatch.setattr(pretplata.config, "MAIL_KEY", "k")
    monkeypatch.setattr(mailer, "_to_all", look)
    mailer.to_all(date(2026, 11, 25), pretplata.link_key(date(2026, 11, 25)))
    judge = sudija.Judge(tracker, threading.Event())
    judge.kept = {"vidjeno": []}
    monkeypatch.setattr(judge, "_load", lambda *_: None)
    monkeypatch.setattr(judge, "_tell", lambda *_: None)
    monkeypatch.setattr(judge, "_material", lambda snap: ([], []))
    monkeypatch.setattr(judge, "_summaries", look)
    judge.step(NOW)
    assert made == ["a notification", "the mail to the maintainer", "the day's mail to all", "the day's summary"]
    assert cuvar._making == {}


def test_the_loop_s_clock_turns_before_each_ask_of_youtube(monkeypatch):
    """With the net gone each ask may take 80 s and there are up to four: slow, not standing."""
    said = []

    def resolve(url):
        said.append(url)
        raise stream.NotLive("no")
    monkeypatch.setattr(stream, "_resolve_youtube", resolve)
    monkeypatch.setattr(stream, "_last_live", "")
    monkeypatch.setattr(stream, "_last_youtube_url", "")
    for name, value in (("STREAM_URL", ""), ("SOURCE_PAGE", ""), ("YOUTUBE_URL", "a"), ("CHANNEL_LIVE", "b")):
        monkeypatch.setattr(stream.config, name, value)
    with pytest.raises(stream.NotLive):
        stream.resolve_input(lambda: said.append("turned"))
    assert said == ["turned", "a", "turned", "b"]
    assert 8 * stream.NET < cuvar.STANDS / 2  # eight answers are waited for in one ask (measured, the net gone)


def test_what_the_loop_calls_has_a_time_limit():
    ocr = (LIVE / "uzivo" / "ocr.py").read_text(encoding="utf-8")
    assert ocr.count("pytesseract.image_to_") == 2 == ocr.count("timeout=LIMIT)")
    docker = (LIVE / "Dockerfile").read_text(encoding="utf-8")
    assert "live/deno.sh /usr/local/bin/deno" in docker and "/deno /usr/local/lib/deno/deno" in docker
    script = (LIVE / "deno.sh").read_bytes()
    assert b"\r" not in script and b'exec timeout -k 5 30 /usr/local/lib/deno/deno "$@"' in script
    assert '"socket_timeout": NET' in (LIVE / "uzivo" / "stream.py").read_text(encoding="utf-8")


def test_docker_starts_an_ended_measuring_again():
    for name in ("docker-compose.yml", "docker-compose.jedan.yml"):
        ours = (LIVE / name).read_text(encoding="utf-8").split("\n  tunel:")[0]
        assert len(re.findall(r"^ +restart: unless-stopped$", ours, re.M)) == len(re.findall(r"^ +image: mikrofon:", ours, re.M)), name
