"""A sitting's summary from its days' summaries (tools/sazetak_sednice.py, 28 Nov 2026): the days' files are the only
material, and a reply with a figure or a name the days do not have is asked again, then not written."""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "live"), str(REPO / "tools")]

import sazetak_sednice as tool  # noqa: E402
from uzivo import sudija  # noqa: E402


def _days(conv: Path):
    (conv / "sazetak").mkdir(parents=True)
    for d, naslov, text in (("2026-11-17", "Narodna skupština je konstituisana", "Skupština je potvrdila mandate 250 poslanika."),
                            ("2026-11-19", "Aleksandar Čupić je novi predsednik Skupštine", "Skupština je izabrala Aleksandra Čupića.")):
        (conv / "sazetak" / f"{d}.json").write_text(json.dumps({"dan": {"naslov": naslov, "kratko": text, "ukratko": text,
            "odluke": [{"vreme": "12:00", "sta": text}]}}, ensure_ascii=False), encoding="utf-8")


def test_the_material_is_the_days_files_only(tmp_path):
    _days(tmp_path)
    text, source = tool.material(tmp_path, ["2026-11-19", "2026-11-17"])
    assert text.index("Dan 2026-11-17") < text.index("Dan 2026-11-19") and "Odluke:" in text and "Čupića" in source


def test_a_name_or_figure_not_in_the_days_is_refused_and_asked_again(tmp_path):
    _days(tmp_path)
    text, source = tool.material(tmp_path, ["2026-11-17", "2026-11-19"])
    good = {"naslov": "Skupština je konstituisana", "kratko": "Skupština je potvrdila mandate 250 poslanika i izabrala Aleksandra Čupića.",
            "ukratko": "Za predsednika je izabran Aleksandar Čupić."}
    assert tool.unfounded(good, source) == []
    bad = dict(good, kratko="Skupština je izabrala Petra Petrovića sa 180 glasova.")
    assert {x.split()[1] for x in tool.unfounded(bad, source)} == {"'Petra'", "'Petrovića'", "'180'"}
    replies = iter([json.dumps(bad), json.dumps(good)])
    asked = []
    s, failed = tool.write(lambda system, user, *_: asked.append(user) or next(replies), text, source, "m")
    assert s == good and failed == [] and "nije prošao proveru" in asked[1]
    s, failed = tool.write(lambda *_: json.dumps(bad), text, source, "m")
    assert s is None and failed


def test_the_tool_writes_the_sittings_file_beside_the_days(tmp_path, monkeypatch, capsys):
    if not (REPO / "data" / "15" / "sazetak" / "2026-11-25.json").exists():
        return
    days = ["2026-11-24", "2026-11-25"]
    assert tool.main(["prva", *days, "--izlaz", str(tmp_path), "--bez-modela"]) == 0 and not list(tmp_path.iterdir())
    assert "--- material ---" in capsys.readouterr().out
    _, source = tool.material(REPO / "data" / "15", days)
    monkeypatch.setattr(sudija.config, "MODEL_KEY", "test")
    monkeypatch.setattr(sudija, "ask_claude", lambda *a: json.dumps(
        {"naslov": "Skupština je izabrala članove odbora", "kratko": "Skupština je izabrala članove odbora.", "ukratko": "Izabrani su odbori."}))
    assert tool.main(["prva", *days, "--izlaz", str(tmp_path)]) == 0
    kept = json.loads((tmp_path / "sednica-prva.json").read_text(encoding="utf-8"))
    assert kept["dani"] == days and kept["izvor"] == "dani" and kept["model"] == sudija.config.DAY_MODEL
