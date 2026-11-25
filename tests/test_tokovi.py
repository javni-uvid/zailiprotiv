"""The data workflows: what must not drift in them (25 Nov 2026)."""
import json
import re
from pathlib import Path
from types import SimpleNamespace

from zailiprotiv import cli
from zailiprotiv.cli import assembly, common

FLOWS = Path(__file__).parents[1] / ".github" / "workflows"


def test_the_roll_calls_are_read_and_sent_before_the_recordings():
    text = (FLOWS / "votes.yml").read_text(encoding="utf-8")
    at = [text.index(x) for x in ("for what in laws votes link", "zailiprotiv $c votes ", "zailiprotiv $c bills",
                                  "name: Commit the roll calls", "zailiprotiv $c videos", "name: Commit the rest",
                                  "gh workflow run snimci.yml")]
    assert at == sorted(at)


def test_the_recordings_have_one_writer_and_never_two_at_once():
    for f in sorted(FLOWS.glob("*.yml")):
        runs = [x for x in f.read_text(encoding="utf-8").splitlines() if re.search(r"zailiprotiv .*\barhiva\b", x)]
        assert bool([x for x in runs if "--waiting" not in x]) == (f.name == "snimci.yml"), f.name
    text = (FLOWS / "snimci.yml").read_text(encoding="utf-8")
    assert "  group: snimci\n  cancel-in-progress: false\n" in text
    assert "git add -- 'data/*/arhiva.json' 'data/*/snimak/**'\n" in text


def test_no_command_is_skipped_in_silence_behind_another():
    """`laws && votes && link || true`: for a 1 of the first the others never ran, and the run was green."""
    for f in sorted(FLOWS.glob("*.yml")):
        for line in f.read_text(encoding="utf-8").splitlines():
            assert not re.search(r"zailiprotiv .*&& .*zailiprotiv .*\|\| *(true|:)", line), (f.name, line)


def test_a_roll_call_listed_and_not_read_is_said(tmp_path, monkeypatch, capsys):
    folder = tmp_path / "15"
    (folder / "votes").mkdir(parents=True)
    sitting = {"title": "x", "votes": [["Избор", "https://a/1 2.pdf"], ["Именовање", "https://a/3.pdf"]]}
    (folder / "index.json").write_text(json.dumps({"sittings": {"u": sitting}}), encoding="utf-8")
    monkeypatch.setattr(common, "DATA", folder)
    monkeypatch.setattr(common, "CONVOCATION", "15")
    assert cli.unread(None) == 0
    assert capsys.readouterr().out.splitlines() == ["- saziv 15: Izbor (https://a/1%202.pdf)",
                                                    "- saziv 15: Imenovanje (https://a/3.pdf)"]
    (folder / "votes" / "1.json").write_text(json.dumps({"pdfs": {"https://a/1 2.pdf": "", "https://a/3.pdf": ""}, "votes": {}}),
                                             encoding="utf-8")
    assert cli.unread(None) == 0 and not capsys.readouterr().out


def test_no_laws_yet_is_no_fault_in_a_convocation_newer_than_the_current_one(tmp_path, monkeypatch):
    monkeypatch.setattr(assembly.skupstina, "fetch", lambda url: b"<html></html>")
    monkeypatch.setattr(assembly, "CURRENT", "14")
    for conv, gives in (("15", 0), ("14", 1)):
        monkeypatch.setattr(common, "CONVOCATION", conv)
        (tmp_path / conv).mkdir()
        assert cli.adopted(SimpleNamespace(out=str(tmp_path / conv / "laws.json"))) == gives
