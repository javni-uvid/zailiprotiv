"""The measuring and the page as two: the moment's file and the lock (sada.py), the page's reader (citac.py)."""
import json
import re
import select
import subprocess
import sys
import threading
from pathlib import Path

import pytest

LIVE = Path(__file__).resolve().parents[1] / "live"
sys.path.insert(0, str(LIVE))

from uzivo import citac, config, sada, stream  # noqa: E402
from uzivo.names import Roster  # noqa: E402
from uzivo.state import NO_STREAM, SPEAKING, UNKNOWN, Tracker  # noqa: E402
from uzivo.state_base import _write  # noqa: E402

LIST = {"mps": [{"n": "Petrović Petar", "s": "petrovic-petar", "g": "PG A"},
                {"n": "Marković Marko", "s": "markovic-marko", "g": "PG B"}]}
FACTS = {"petrovic-petar": {"ime": "Petrović Petar", "lista": "PG A", "za": 3, "f": []},
         "markovic-marko": {"ime": "Marković Marko", "lista": "PG B", "za": 1, "f": []}}
NOW = 1795510000.0  # 24 Nov 2026


@pytest.fixture
def two(tmp_path, monkeypatch):
    """A measuring's tracker with its pulse, and a reader of its folder."""
    monkeypatch.setattr(config, "STATE_PATH", str(tmp_path / "stanje.json"))
    monkeypatch.setattr(stream, "VIDEO", {})
    monkeypatch.setattr(sada, "VIDEO", {})
    t = Tracker(config.STATE_PATH, "Europe/Belgrade")
    t.roster = Roster.from_json(json.dumps(LIST))
    t.roster.current = frozenset(FACTS)
    _write(tmp_path / "podaci.json", LIST)
    t.use_facts(FACTS)
    t.use_waiting({"kviz": [], "cinjenice": [], "obavestenja": [{"tekst": "Nastavak u 10", "od": "2026-11-24", "do": "2026-11-24"}],
                   "dnevni_red": [{"naslov": "Sednica", "url": "u", "tacke": [{"n": 1, "tekst": "Prvi zakon"}, {"n": 2, "tekst": "Drugi"}]}]})
    return t, sada.Pulse(t, threading.Event()), citac.Reader(config.STATE_PATH, "Europe/Belgrade"), tmp_path


def test_the_reader_shows_a_day_as_the_tracker_does_step_by_step(two):
    t, pulse, reader, base = two
    petar, marko = t.roster.people
    seen = []

    def at(sec, call, *args, **more):
        if call in ("observe", "tick"):
            more["now"] = NOW + sec
        getattr(t, call)(*args, **more)
        t.looped = NOW + sec
        pulse.step(NOW + sec)
        mine, theirs = reader.snapshot(now=NOW + sec + 0.5), t.snapshot(now=NOW + sec + 0.5)
        assert mine == theirs, (sec, call)
        assert reader.alive(NOW + sec + 0.5)
        seen.append(mine["stanje"])
    place = lambda n: {"video": "abc", "sq": 100 + n, "seg": 5.0}
    at(0, "observe", None, at=place(0))
    at(5, "observe", petar, "PG A", at=place(1))
    at(6, "caption", NOW + 4, NOW + 6, "Poštovana predsednice")
    at(7, "presides", marko, NOW - 20, NOW + 1)
    for sec in range(10, 60, 5):
        at(sec, "observe", petar, "PG A", at=place(sec // 5))
    at(62, "say", NOW + 20, "Poštovani narodni poslanici, predlažem da glasamo.")
    at(63, "note", NOW + 60, "Tačka dnevnog reda", "Prelazimo na drugu tačku dnevnog reda.", "prepis")
    at(65, "observe", marko, "PG B", at=place(13))       # another speaker: the turn and the day's list change at once
    at(70, "observe", marko, "PG B", at=place(14))
    at(80, "unheard", NOW + 75)                          # nothing: a caption rules
    for sec in range(100, 135, 5):
        at(sec, "observe", None, at=place(sec // 5))     # the caption gone: nobody known
    at(140, "heard", petar, "prepis", NOW + 138, NOW + 140)
    at(150, "heard", petar, "glas", NOW + 140, NOW + 150, tracked={"petrovic-petar"})
    at(155, "unheard", NOW + 152)                        # the measuring says "unknown" after it has kept the day's file
    kept = {"vidjeno": [], "delovi": [{"ukratko": "Govorili su.", "do": "12:00"}], "dan": None}
    _write(base / "sazetak" / "2026-11-24.json", kept)
    at(156, "use_summary", "2026-11-24", kept)
    rows = [{"ime": "Petrović Petar", "od": int(NOW + 5), "do": int(NOW + 55), "rezime": "O glasanju."}]
    _write(base / "rezimei" / "2026-11-24.json", rows)
    at(157, "use_lines", "2026-11-24", rows)
    at(158, "use_recording", {"dan": "2026-11-23", "govori": []})
    at(230, "tick")                                      # the broadcast over
    assert {NO_STREAM, SPEAKING, UNKNOWN} <= set(seen) and seen[-1] == NO_STREAM
    assert [d["ime"] for d in reader.snapshot(now=NOW + 231)["danas"]][-1] == "Petrović Petar"
    assert reader.record("2026-11-24") == t.record("2026-11-24") and reader.days_kept() == t.days_kept()
    assert reader.summary_of("2026-11-24") == kept and reader.summary_of("../../x") == {}
    assert reader.transcript()["dan"] == t.transcript()["dan"]
    assert reader.roster.current == t.roster.current and [p.name for p in reader.roster.people] == [p.name for p in t.roster.people]


def test_the_reader_writes_nothing(two):
    t, pulse, reader, base = two
    petar, _ = t.roster.people
    t.observe(petar, "PG A", now=NOW)
    pulse.step(NOW)
    before = {p: p.read_bytes() for p in base.rglob("*") if p.is_file()}
    for sec in (1, 40, 100, 90000):
        reader.snapshot(now=NOW + sec)
        reader.alive(NOW + sec)
    reader.record("2026-11-24"), reader.days_kept(), reader.transcript(), citac.Reader(config.STATE_PATH)
    assert {p: p.read_bytes() for p in base.rglob("*") if p.is_file()} == before


def test_a_loop_that_stands_names_nobody_though_the_heart_beats(two):
    """25 Nov 2026, the conductor: yt-dlp (or a frame's reading) hung while the pulse's thread goes on. The tracker's
    own tick is not called then, so the tracker still says somebody speaks; the page must not."""
    t, pulse, reader, _ = two
    petar, _m = t.roster.people
    t.observe(petar, "PG A", now=NOW)
    t.looped = NOW
    pulse.step(NOW)
    assert reader.snapshot(now=NOW + 1)["sada"]["ime"] == "Petrović Petar"
    late = NOW + config.STALE_SECONDS + 1
    pulse.step(late)
    assert t.snapshot(now=late)["stanje"] == SPEAKING  # what is known not to be checked any more
    snap = reader.snapshot(now=late)
    assert snap["stanje"] == NO_STREAM and snap["sada"] is None and reader.alive(late)
    pulse.step(NOW + citac.LOOP_OLD + 1)
    assert not reader.alive(NOW + citac.LOOP_OLD + 1)  # and standing that long, the page is not served at all


def test_the_page_is_not_served_without_a_heartbeat(two):
    t, pulse, reader, base = two
    assert not reader.alive(NOW)  # no file yet
    t.looped = NOW
    pulse.step(NOW)
    assert reader.alive(NOW + citac.BEAT_OLD) and not reader.alive(NOW + citac.BEAT_OLD + 1)
    m = json.loads((base / "sada.json").read_text(encoding="utf-8"))
    _write(base / "sada.json", m | {"format": sada.FORMAT + 1})  # a measuring this page cannot read
    assert not reader.alive(NOW)
    (base / "sada.json").write_text('{"t": "x"}', encoding="utf-8")
    assert not reader.alive(NOW + 1)


def test_the_moment_is_written_when_it_changes_and_every_few_seconds(two):
    t, pulse, _, base = two
    assert pulse.step(NOW) and not pulse.step(NOW + 1)
    t.looped = NOW + 2
    assert not pulse.step(NOW + 2)  # only a clock moved
    t.caption(NOW, NOW + 2, "Reč")
    assert pulse.step(NOW + 3) and not pulse.step(NOW + 4) and pulse.step(NOW + 3 + sada.BEAT)
    m = json.loads((base / "sada.json").read_text(encoding="utf-8"))
    assert m["format"] == sada.FORMAT and m["t"] == NOW + 3 + sada.BEAT and m["petlja"] == NOW + 2


def test_after_a_restart_with_nothing_taken_up_nobody_is_shown(two):
    """The day's file still says who spoke when the run before was stopped; the new run has not taken that up."""
    t, pulse, reader, _ = two
    petar, _m = t.roster.people
    t.observe(petar, "PG A", now=NOW)
    pulse.step(NOW)
    again = Tracker(config.STATE_PATH, "Europe/Belgrade")
    again._load("2026-11-24")
    assert again.status == NO_STREAM
    sada.Pulse(again, threading.Event()).step(NOW + 20)
    snap = reader.snapshot(now=NOW + 20)
    assert snap["stanje"] == NO_STREAM and snap["sada"] is None


def test_a_file_that_cannot_be_read_leaves_what_was_read(two):
    t, pulse, reader, base = two
    t.observe(t.roster.people[0], "PG A", now=NOW)
    pulse.step(NOW)
    assert len(reader.snapshot(now=NOW + 1)["obavestenja"]) == 1
    (base / "cekanje.json").write_text("{", encoding="utf-8")
    assert len(reader.snapshot(now=NOW + 2)["obavestenja"]) == 1
    (base / "cekanje.json").write_text("[1]", encoding="utf-8")  # of another kind
    assert len(reader.snapshot(now=NOW + 3)["obavestenja"]) == 1


@pytest.mark.skipif(sada.fcntl is None, reason="no flock on Windows")
def test_two_services_never_write_in_one_folder(tmp_path):
    code = ("import sys, time; sys.path.insert(0, sys.argv[1])\n"
            "from pathlib import Path\nfrom uzivo import sada\n"
            "sada.only_writer(Path(sys.argv[2])); print('ima', flush=True); time.sleep(60)")
    run = lambda: subprocess.Popen([sys.executable, "-c", code, str(LIVE), str(tmp_path)], stdout=subprocess.PIPE, text=True)
    first = run()
    assert first.stdout.readline().strip() == "ima"
    second = run()
    try:
        assert not select.select([second.stdout], [], [], 3)[0]  # it waits
        first.kill()                      # however the first ends
        assert second.stdout.readline().strip() == "ima"
    finally:
        first.kill(), second.kill()
        first.wait(), second.wait()


def test_the_page_s_folder_is_made_before_anything_is_read(tmp_path):
    sada.prepare(tmp_path / "stanje.json")
    assert (tmp_path / "mejl").is_dir()
    sada.prepare(tmp_path / "nema" / "stanje.json")  # no volume (the tests, a trial by hand): nothing made
    assert not (tmp_path / "nema").exists()


def test_the_reader_loads_no_model_stream_or_ocr():
    code = ("import sys; sys.path.insert(0, sys.argv[1])\nfrom uzivo import citac\n"
            "print([m for m in ('numpy','yt_dlp','faster_whisper','ctranslate2','sherpa_onnx','anthropic','pytesseract','PIL') "
            "if m in sys.modules])")
    out = subprocess.run([sys.executable, "-c", code, str(LIVE)], capture_output=True, text=True)
    assert out.stdout.strip() == "[]", out.stdout + out.stderr


def test_the_mail_to_the_maintainer_goes_by_the_kept_summary(two, monkeypatch):
    """25 Nov 2026: until then asked from the model's loop, which a restart of the measuring begins anew."""
    import datetime as dt
    from uzivo import pretplata
    t, pulse, reader, base = two
    t.observe(t.roster.people[0], "PG A", now=NOW)
    pulse.step(NOW)
    asked = []

    class Mailer:
        def ready(self, day):
            asked.append(day)
            return True
    w = pretplata.Watch(reader, Mailer(), threading.Event())
    at = dt.datetime(2026, 11, 24, 20, 0, tzinfo=pretplata.TZ).timestamp()
    monkeypatch.setattr(config, "SHOW_SUMMARY", True)
    assert not w.step(at) and not asked  # no summary yet
    kept = {"delovi": [], "dan": {"ukratko": "Govorili su.", "t": at - 60}}
    _write(base / "sazetak" / "2026-11-24.json", kept)
    assert w.step(at) and asked == [dt.date(2026, 11, 24)]
    assert not w.step(at + 3.5 * 3600)        # 23:30: nobody is woken
    assert not w.step(at + 13 * 3600)         # 9:00 the next day: half a day old
    monkeypatch.setattr(config, "SHOW_SUMMARY", False)
    assert not w.step(at) and len(asked) == 1


def test_the_page_knows_of_the_live_sound_by_what_the_measuring_said(tmp_path, monkeypatch):
    from uzivo import slusaj
    said = {"t": 1000.0, "url": "https://zvuk.zailiprotiv.rs/uzivo/z.m3u8"}
    monkeypatch.setattr(slusaj, "told", lambda: said)
    assert slusaj.fresh(1059) and not slusaj.fresh(1061) and slusaj.address() == said["url"]
    monkeypatch.setattr(slusaj, "PLAYLIST", slusaj.Playlist(tmp_path))
    (tmp_path / "z.m3u8").write_text("#EXTM3U\n", encoding="utf-8")
    monkeypatch.setattr(slusaj.time, "time", lambda: 1010.0)
    assert slusaj.playlist() == "#EXTM3U\n"
    monkeypatch.setattr(slusaj.time, "time", lambda: 2000.0)
    assert slusaj.playlist() == ""            # of a broadcast that is over


def test_the_measuring_s_check_goes_by_the_page_s_own_rule(two, monkeypatch):
    from uzivo import merenje
    t, pulse, _, _b = two
    assert not merenje.healthy()
    t.looped = NOW
    pulse.step(NOW)
    monkeypatch.setattr(citac.time, "time", lambda: NOW + 10)
    assert merenje.healthy()
    monkeypatch.setattr(config, "VERSION", "novi")  # what the run before left is not this one's, however fresh
    assert not merenje.healthy()
    pulse.step(NOW + 10)
    assert merenje.healthy()
    monkeypatch.setattr(citac.time, "time", lambda: NOW + 10 + citac.BEAT_OLD + 1)
    assert not merenje.healthy()


def test_the_page_s_modules_load_no_model_stream_or_ocr():
    """The models must not be loaded twice: what main.py imports for the page alone (picture, which needs Pillow, is the
    only other)."""
    code = ("import sys; sys.path.insert(0, sys.argv[1])\nfrom uzivo import citac, config, obavesti, page, pretplata, slusaj\n"
            "print([m for m in ('numpy','yt_dlp','faster_whisper','ctranslate2','sherpa_onnx','anthropic','pytesseract','uzivo.worker',"
            "'uzivo.merenje') if m in sys.modules])")
    out = subprocess.run([sys.executable, "-c", code, str(LIVE)], capture_output=True, text=True)
    assert out.stdout.strip() == "[]", out.stdout + out.stderr
    code = (LIVE / "uzivo" / "main.py").read_text(encoding="utf-8")
    apart = code[:code.index("else:\n    from . import merenje")]
    imported = set(re.findall(r"\w+", " ".join(re.findall(r"^ *(?:from|import) (.+)$", apart, re.M))))
    assert {"pretplata", "Reader"} <= imported
    assert not imported & {"worker", "prepis", "glas", "sudija", "hronika", "ocr", "numpy", "stream", "sada"}


def test_the_test_as_two_gives_the_page_only_what_went_by_mail_to_write():
    """live/docker-compose.test.dva.yml: the measuring takes the test's service as it is (its secrets emptied there), and
    the page reads the volume and writes its `mejl` alone."""
    two = (LIVE / "docker-compose.test.dva.yml").read_text(encoding="utf-8")
    measuring, page = two[two.index("  merenje:"):].split("\n  uzivo:\n")
    assert "extends:" in measuring and "service: uzivo" in measuring and "ports: !reset []" in measuring
    assert "ULOGA: merenje" in measuring and '"uzivo.merenje"]' in measuring
    assert "ULOGA: strana" in page and "volumes: !override" in page
    assert re.search(r"target: /data\n +read_only: true", page) and re.search(r"target: /data/mejl.*\n +volume:\n +subpath: mejl", page)
    assert not re.search(r"^ +\w*(KEY|TOKEN|KLJUC|TAJNA|SECRET|R2_|MEJL_)\w*:", two, re.M) and "env_file" not in two


def _services(name: str) -> dict[str, str]:
    """A compose file's services, each as its text."""
    text = (LIVE / name).read_text(encoding="utf-8").split("\nservices:\n")[1].split("\nvolumes:\n")[0]
    parts = re.split(r"^  (\w+):.*$", text, flags=re.M)
    return {k: v.strip() for k, v in zip(parts[1::2], parts[2::2])}


def test_each_of_the_two_has_only_the_secrets_it_uses():
    """25 Nov 2026, the maintainer's answer on the keys ("3 stranica, svejedno mi je"): the page alone opens the readers'
    addresses, the measuring alone asks the model and fills the live sound's bucket. Both read one .env, so what one must
    not have is emptied by name; a new secret is given its place here and there."""
    empty = {"merenje": {"MEJL_KLJUC", "MEJL_UREDNIK"},
             "uzivo": {"ANTHROPIC_API_KEY", "ZVUK_R2_ENDPOINT", "ZVUK_R2_BUCKET", "ZVUK_R2_KLJUC", "ZVUK_R2_TAJNA"}}
    both = {"PUSH_TOKEN", "PREPIS_KLJUC"}  # the counter's word (the bell; the mail), and the maintainer's pages' key
    read = set()
    for f in (LIVE / "uzivo").glob("*.py"):
        read |= set(re.findall(r'environ(?:\.get\(|\[)"([A-Z0-9_]+)"', f.read_text(encoding="utf-8")))
    secret = {n for n in read if re.search(r"KEY|TOKEN|KLJUC|TAJNA|SECRET|LOZINKA|R2_(ENDPOINT|BUCKET)|MEJL", n)}
    assert secret == both.union(*empty.values())
    services = _services("docker-compose.yml")
    for name, mine in empty.items():
        assert set(re.findall(r'^ {6}([A-Z0-9_]+): ""$', services[name], re.M)) == mine, name


def test_the_live_page_writes_only_what_went_by_mail_and_takes_nothing_of_the_measuring_s():
    two, one = _services("docker-compose.yml"), _services("docker-compose.jedan.yml")
    assert set(two) == {"merenje", "uzivo", "tunel"} and set(one) == {"uzivo", "tunel"}
    measuring, page = two["merenje"], two["uzivo"]
    assert "ULOGA: merenje" in measuring and '"uzivo.merenje"]' in measuring and "ports:" not in measuring
    assert "ULOGA: strana" in page and '"127.0.0.1:8000:8000"' in page and "mikrofon:strana" in page
    assert re.search(r"target: /data\n +read_only: true", page) and re.search(r"target: /data/mejl.*\n +volume:\n +subpath: mejl", page)
    assert "podaci:/data" not in page and "whisper" not in page
    assert "mem_limit: 300m" in page and not re.search(r"^ +mem_limit", measuring, re.M) and "stop_grace_period: 120s" in page
    for service in (measuring, page):
        assert "no-new-privileges:true" in service and "cap_drop: [ALL]" in service and "build:" not in service
    assert "ULOGA" not in one["uzivo"] and "mikrofon:uzivo" in one["uzivo"]
    assert two["tunel"] == one["tunel"]  # so that going from one form to the other does not restart the tunnel


def test_the_image_says_the_format_its_page_reads():
    label = re.search(r"^LABEL zailiprotiv\.format=(\d+)$", (LIVE / "Dockerfile").read_text(encoding="utf-8"), re.M)
    assert label and int(label[1]) == sada.FORMAT


def test_the_release_script_knows_which_modules_are_whose():
    """`mikrofon.ps1 stanje` says which commits wait for the page and which for the measuring, by these lists."""
    import ast
    folder = LIVE / "uzivo"
    names = {f.stem for f in folder.glob("*.py")}

    def imports(m: str) -> set[str]:
        out: set[str] = set()
        for n in ast.walk(ast.parse((folder / f"{m}.py").read_text(encoding="utf-8"))):
            if isinstance(n, ast.ImportFrom) and n.level == 1:
                out |= {n.module.split(".")[0]} if n.module else {a.name for a in n.names}
        return out & names

    def reached(root: str, without: str = "") -> set[str]:
        seen, todo = set(), [root]
        while todo:
            m = todo.pop()
            if m not in seen and m != without:
                seen.add(m)
                todo += imports(m)
        return seen
    page, measuring = reached("main", without="merenje"), reached("merenje")
    script = (LIVE / "mikrofon.ps1").read_text(encoding="utf-8")
    listed = {k: set(re.findall(r'"(\w+)"', re.search(rf"^\${k} = @\((.+)\)$", script, re.M)[1])) for k in ("OnlyPage", "OnlyMeasuring")}
    assert listed["OnlyPage"] == page - measuring and listed["OnlyMeasuring"] == measuring - page
