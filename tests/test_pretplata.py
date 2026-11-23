"""The subscribers of the day's mail: sealed by the counter (worker/mejl.js), opened only with the maintainer's key
(live/uzivo/pretplata.py), and the day's mail to all only on his link, once."""
import base64
import json
import os
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "live"))

from uzivo import mejl, pretplata  # noqa: E402

KEY = base64.b64encode(bytes(range(32))).decode()


@pytest.mark.skipif(not shutil.which("node"), reason="needs Node, as the worker's code is JavaScript")
def test_an_address_sealed_by_the_worker_opens_with_the_maintainers_key_only():
    script = ("import { seal } from " + json.dumps((ROOT / "worker" / "mejl.js").as_uri()) + ";\n"
              "const jwk = JSON.parse(process.argv[1]);\n"
              "console.log(await seal(jwk, 'citalac@primer.rs'));\n")
    sealed = subprocess.run(["node", "--input-type=module", "-e", script, json.dumps(pretplata.public_jwk(KEY))],
                            capture_output=True, text=True, check=True).stdout.strip()
    assert "citalac" not in sealed
    assert pretplata.unseal(KEY, sealed) == "citalac@primer.rs"
    other = base64.b64encode(bytes(range(1, 33))).decode()
    with pytest.raises(Exception):
        pretplata.unseal(other, sealed)


def test_the_public_key_in_the_workers_settings_is_a_p256_key():
    toml = (ROOT / "worker" / "wrangler.toml").read_text(encoding="utf-8")
    jwk = json.loads(toml.split("MEJL_JAVNI = '", 1)[1].split("'", 1)[0])
    assert jwk["kty"] == "EC" and jwk["crv"] == "P-256" and "d" not in jwk  # never the private half


class FakeMail:
    def __init__(self):
        self.calls = []

    def __call__(self, day, cyr, out):
        return mejl.Mail("Skupština, četvrtak 19. novembar: 6 odluka", "tekst " + out, "<html><body>" + out + "</body></html>")


def test_to_all_only_with_the_days_code_once_and_never_after_noon(tmp_path, monkeypatch):
    monkeypatch.setattr(pretplata.config, "MAIL_KEY", KEY)
    sent = []
    monkeypatch.setattr(pretplata, "send", lambda msgs: (sent.extend(msgs), (len(msgs), []))[1])
    people = [{"id": "a", "adresa": "x", "cir": False, "odjava": "https://glasovi.zailiprotiv.rs/m/odjava?i=a&k=1"},
              {"id": "b", "adresa": "y", "cir": True, "odjava": "https://glasovi.zailiprotiv.rs/m/odjava?i=b&k=2"},
              {"id": "c", "adresa": "z", "cir": False, "odjava": "https://glasovi.zailiprotiv.rs/m/odjava?i=c&k=3"}]
    monkeypatch.setattr(pretplata, "_call", lambda path, body=None: {"primaoci": people})
    monkeypatch.setattr(pretplata, "unseal", lambda key, s: {"x": "a@primer.rs", "y": "b@primer.rs", "z": "A@primer.rs"}[s])
    day = date(2026, 11, 19)
    m = pretplata.Mailer(tmp_path, FakeMail())
    monkeypatch.setattr(pretplata, "deadline", lambda d: pretplata.datetime(2999, 1, 1, tzinfo=pretplata.TZ))
    assert m.to_all(day, "pogresan") == ("kod", 0)
    assert m.to_all(day, pretplata.link_key(day)) == ("ok", 2)  # the same address twice goes once
    assert [s["to"] for s in sent] == ["a@primer.rs", "b@primer.rs"] and sent[0]["odjava"].endswith("k=1")
    assert m.to_all(day, pretplata.link_key(day)) == ("vec", 2) and len(sent) == 2  # a second click sends nothing
    monkeypatch.setattr(pretplata, "deadline", lambda d: pretplata.datetime(2000, 1, 1, tzinfo=pretplata.TZ))
    assert pretplata.Mailer(tmp_path / "drugi", FakeMail()).to_all(day, pretplata.link_key(day)) == ("kasno", 0)


def test_the_maintainer_gets_the_day_first_and_a_word_in_two_scripts_stops_it(tmp_path, monkeypatch):
    monkeypatch.setattr(pretplata.config, "MAIL_KEY", KEY)
    monkeypatch.setattr(pretplata.config, "MAIL_EDITOR", "urednik@primer.rs")
    monkeypatch.setattr(pretplata.config, "PUSH_TOKEN", "t")
    sent = []
    monkeypatch.setattr(pretplata, "send", lambda msgs: (sent.extend(msgs), (len(msgs), []))[1])
    slip = lambda day, cyr, out: mejl.Mail("Skupština", "Čupić je iznео načela", "<html><body>x</body></html>")  # noqa: E731
    m = pretplata.Mailer(tmp_path, slip)
    assert m.ready(date(2026, 11, 19)) and not m.ready(date(2026, 11, 19))  # once a day
    assert sent[0]["to"] == "urednik@primer.rs" and "NE MOŽE SVIMA" in sent[0]["text"] and "Pošalji svima" not in sent[0]["html"]
    assert m.to_all(date(2026, 11, 19), pretplata.link_key(date(2026, 11, 19))) == ("dvopis", 0)


@pytest.fixture
def outbox(tmp_path, monkeypatch):
    """A mailer with fifty readers and the counter replaced: what it was asked to send, and how it answers."""
    monkeypatch.setattr(pretplata.config, "MAIL_KEY", KEY)
    monkeypatch.setattr(pretplata.config, "MAIL_EDITOR", "urednik@primer.rs")
    monkeypatch.setattr(pretplata.config, "PUSH_TOKEN", "t")
    monkeypatch.setattr(pretplata, "unseal", lambda key, s: s)
    monkeypatch.setattr(pretplata, "deadline", lambda d: pretplata.datetime(2999, 1, 1, tzinfo=pretplata.TZ))

    class Box:
        got: list = []
        fail = None  # how the next calls fail: called with the batch's number and messages
        calls = 0
        mailer = pretplata.Mailer(tmp_path, FakeMail())

    box = Box()
    box.got = []

    def call(path, body=None):
        if path == "/m/spisak":
            import time
            time.sleep(0.1)
            return {"primaoci": [{"id": f"r{i}", "adresa": f"c{i}@primer.rs", "odjava": "https://x"} for i in range(50)]}
        box.calls += 1
        wrong = (box.fail(box.calls) if box.fail else None) or []
        box.got += [m["to"] for i, m in enumerate(body["poruke"]) if i not in wrong]
        return {"poslato": len(body["poruke"]) - len(wrong), "greske": [{"i": i, "code": "X"} for i in wrong]}

    monkeypatch.setattr(pretplata, "_call", call)
    return box


DAY = date(2026, 11, 24)


def test_the_button_pressed_twice_at_once_sends_once(outbox):
    import threading
    out = []
    ts = [threading.Thread(target=lambda: out.append(outbox.mailer.to_all(DAY, pretplata.link_key(DAY)))) for _ in range(2)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert sorted(out) == [("ok", 50), ("u_toku", 0)] and len(outbox.got) == 50


def test_a_sending_broken_in_the_middle_goes_on_where_it_stopped(outbox):
    def timeout(n):
        if n == 2:
            raise TimeoutError("timed out")
    outbox.fail = timeout
    assert outbox.mailer.to_all(DAY, pretplata.link_key(DAY)) == ("deo", 20)
    # a new run of the service; the batch whose call timed out may have gone, so it is not sent again
    outbox.mailer = pretplata.Mailer(outbox.mailer.folder, FakeMail())
    assert outbox.mailer.to_all(DAY, pretplata.link_key(DAY)) == ("nesigurno", 30)
    assert len(outbox.got) == len(set(outbox.got)) == 30
    assert outbox.mailer.to_all(DAY, pretplata.link_key(DAY)) == ("vec", 30)


def test_a_batch_the_counter_refused_and_a_message_that_failed_are_sent_on_the_next_click(outbox):
    import urllib.error

    def refuse(n):
        if n == 1:
            return [3]
        if n == 2:
            raise urllib.error.HTTPError("u", 429, "limit", None, None)
    outbox.fail = refuse
    assert outbox.mailer.to_all(DAY, pretplata.link_key(DAY)) == ("deo", 19)
    assert outbox.mailer.to_all(DAY, pretplata.link_key(DAY)) == ("ok", 50)
    assert sorted(outbox.got) == sorted(f"c{i}@primer.rs" for i in range(50))
    kept = (outbox.mailer.folder / f"{DAY}.json").read_text(encoding="utf-8")
    assert "@" not in kept  # readers are kept by the counter's row, never by address


def test_the_maintainers_mail_that_did_not_go_is_tried_again(outbox):
    outbox.fail = lambda n: [0]
    assert not outbox.mailer.ready(DAY)
    outbox.fail = None
    assert outbox.mailer.ready(DAY) and not outbox.mailer.ready(DAY)


def test_a_word_in_two_scripts_mended_frees_the_day(outbox):
    good = outbox.mailer.build
    outbox.mailer.build = lambda day, cyr, out: mejl.Mail("Skupština", "Čupić je izn\u0435o načela", "<html><body>x</body></html>")
    assert outbox.mailer.ready(DAY) and not outbox.mailer.ready(DAY)
    assert outbox.mailer.to_all(DAY, pretplata.link_key(DAY)) == ("dvopis", 0)
    outbox.mailer.build = good
    assert outbox.mailer.ready(DAY) and not outbox.mailer.ready(DAY)
    assert outbox.mailer.to_all(DAY, pretplata.link_key(DAY)) == ("ok", 50)


def test_no_key_no_code_and_a_day_without_a_summary_is_not_marked_as_sent(outbox, monkeypatch):
    good = outbox.mailer.build
    outbox.mailer.build = lambda day, cyr, out: None
    assert outbox.mailer.to_all(DAY, pretplata.link_key(DAY)) == ("prazno", 0)
    outbox.mailer.build = good
    assert outbox.mailer.to_all(DAY, pretplata.link_key(DAY)) == ("ok", 50)
    monkeypatch.setattr(pretplata.config, "MAIL_KEY", "")
    assert outbox.mailer.to_all(DAY, pretplata.link_key(DAY)) == ("kod", 0)


def test_the_days_mail_goes_until_noon_the_next_day():
    assert pretplata.deadline(DAY).isoformat()[:16] == "2026-11-25T12:00"


def test_the_worker_serves_sign_up_confirmation_and_unsubscription():
    js = (ROOT / "worker" / "worker.js").read_text(encoding="utf-8")
    assert 'import * as mejl from "./mejl.js"' in js and "mejl.cleanup(env)" in js and "mejl: await mejl.count(env)" in js
    schema = (ROOT / "worker" / "schema.sql").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS mejl" in schema
    m = (ROOT / "worker" / "mejl.js").read_text(encoding="utf-8")
    assert '<form method="post" action="/m/potvrdi">' in m  # a button confirms, never the link alone
    assert "if (from !== LIVE)" in m and "env.LIMIT" in m


def test_the_live_page_offers_the_mail_and_the_form_works_without_the_script():
    from zoneinfo import ZoneInfo

    from uzivo import page
    from uzivo.state import Tracker
    snap = Tracker(None).snapshot()
    html = page.page(snap, cyr=False, site="https://zailiprotiv.rs/", tz=ZoneInfo("Europe/Belgrade"),
                     api="https://glasovi.zailiprotiv.rs")
    assert '<form class="ml-box" method="post" action="https://glasovi.zailiprotiv.rs/m">' in html
    assert 'name="adresa"' in html and 'name="pismo" value="lat"' in html and "https://zailiprotiv.rs/privatnost" in html
    assert "<form class=\"ml-box\"" not in page.page(snap, cyr=False, site="https://zailiprotiv.rs/", tz=ZoneInfo("Europe/Belgrade"))
    cyr = page.page(snap, cyr=True, site="https://zailiprotiv.rs/", tz=ZoneInfo("Europe/Belgrade"), api="https://glasovi.zailiprotiv.rs")
    assert 'name="pismo" value="cir"' in cyr and "Сажетак дана на мејл" in cyr


def test_the_site_publishes_each_mps_name_and_party_for_the_mail():
    from zailiprotiv import pages_mikrofon
    # the rows as pages_members.match gives them: the name already as the site writes it (23 Nov 2026: a test of
    # Cyrillic capitals here passed while the site published no name at all)
    rows = [{"slug": "pastor-balint", "new": False, "name": "Pastor Balint", "group": "", "party": "СВМ-VMSZ"},
            {"slug": "kamberi-saip", "new": True, "name": "Kamberi Šaip", "group": "", "party": "-"},
            {"slug": "jovanovic-aleksandar-1968", "new": True, "name": "Jovanović Aleksandar (1968)", "group": "Studentska lista", "party": "-"}]
    from zailiprotiv.translit import latin
    known = {"pastor-balint": {"tally": {}, "facts": [], "convs": ["14"]}}
    out = pages_mikrofon.speakers(rows, known, conv="15", spoken_={}, plain=str, latin=latin, day=str)
    assert out["jovanovic-aleksandar-1968"]["ime"] == "Jovanović Aleksandar"
    assert out["pastor-balint"]["ime"] == "Pastor Balint" and out["pastor-balint"]["stranka"] == "SVM-VMSZ"
    assert "stranka" not in out["kamberi-saip"]
    roll = pretplata.roll_of(out)
    assert roll.one("Pastor Balint").label == "SVM-VMSZ" and roll.one("Kamberi Šaip").label == "van poslaničkih grupa"
