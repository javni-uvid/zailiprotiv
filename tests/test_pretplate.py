"""tools/pretplate.py: how many asked to be called back, as numbers only."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "tools" / "pretplate.py"
spec = importlib.util.spec_from_file_location("pretplate", TOOL)
pretplate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pretplate)

OVER = {"uses": {"2026-11-23": {"mikrofon.otvori": 1000, "mikrofon.mejl": 4}, "2026-11-24": {"mikrofon.obavesti": 2}},
        "mejl": {"potvrdjeno": 4, "ceka": 1}, "push": {"devices": 7, "sent": [{"day": "s:2026-11-24", "sent": 6, "gone": 1}]}}


def keep(folder, day, **state):
    (folder / f"{day}.json").write_text(json.dumps({"uredniku": "x", **state}), encoding="utf-8")


def test_new_and_gone_are_counted_from_one_mail_to_the_next(tmp_path):
    keep(tmp_path, "2026-11-19")  # to the maintainer alone: no mail to all
    keep(tmp_path, "2026-11-24", svima="x", poslati=["a", "b", "c"], nesigurni=[], greske=[])
    keep(tmp_path, "2026-11-25", svima="x", poslati=["b", "d"], nesigurni=["e"], greske=[{"id": "c", "code": "q"}])
    keep(tmp_path, "2026-11-26", svima="x", poslati=["a", "b", "c", "d", "e"], nesigurni=[], greske=[])
    (tmp_path / "ispravke-2026-11-25.json").write_text("[]", encoding="utf-8")
    first, second, third = pretplate.mails(tmp_path)
    assert first == {"dan": "2026-11-24", "poslato": 3, "novi": 3, "otisli": None, "greske": 0, "nesigurno": 0}
    assert second == {"dan": "2026-11-25", "poslato": 2, "novi": 2, "otisli": 1, "greske": 1, "nesigurno": 1}  # c's mail failed: not gone
    assert third["novi"] == 0 and third["otisli"] == 0  # a was counted once, and c with it


def test_run_in_the_container_it_prints_numbers_and_no_id(tmp_path):
    keep(tmp_path, "2026-11-24", svima="x", poslati=["deadbeef"], nesigurni=[], greske=[])
    code = TOOL.read_text(encoding="utf-8").replace('"/data/mejl"', repr(tmp_path.as_posix()))
    out = subprocess.run([sys.executable, "-", "--zbir"], input=code, capture_output=True, text=True, encoding="utf-8", check=True).stdout
    assert json.loads(out)[0]["poslato"] == 1 and "deadbeef" not in out
    assert list(tmp_path.iterdir()) == [tmp_path / "2026-11-24.json"]  # it only reads


def test_the_report_says_what_is_known_and_no_share_once_the_first_days_are_out_of_the_overview(tmp_path):
    sent = [{"dan": "2026-11-24", "poslato": 3, "novi": 3, "otisli": None, "greske": 0, "nesigurno": 0}]
    text = "\n".join(pretplate.report(OVER, sent))
    assert "4 potvrdjenih, 1 ceka" in text and "7 uredjaja" in text and "+1 potvrdjenih" in text
    assert "4 od 4 poslatih prijava (100%" in text
    later = {**OVER, "uses": {"2026-12-20": {"mikrofon.mejl": 4}}}
    assert "udeo" not in "\n".join(pretplate.report(later, sent))
    assert "ne odgovara" in pretplate.report(OVER, None)[-1]
    assert "poslatih prijava" in "\n".join(pretplate.report(OVER, []))  # before any mail to all
