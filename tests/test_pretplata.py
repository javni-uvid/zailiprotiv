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


def test_to_all_only_with_the_days_code_once_and_never_after_eight(tmp_path, monkeypatch):
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
