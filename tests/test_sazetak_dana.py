"""A day's summary written after the fact (tools/sazetak_dana.py, sudija.whole_day): from the notes for a day the service
never heard (17 and 18 Nov 2026), or again from the kept transcript; the same call and checks as the service's."""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "live"), str(REPO / "tools")]

from uzivo import sudija  # noqa: E402

DATA = REPO / "data"


def test_the_notes_prompt_is_the_whole_days_rules_said_of_the_notes():
    assert sudija.NOTES != sudija.WHOLE and "STENOGRAFSKIH BELEŠKI" in sudija.NOTES and "AUTOMATSKOG" not in sudija.NOTES
    assert [line for line in sudija.NOTES.lower().splitlines() if "prepis" in line and "prepisane" not in line] == []
    for rule in ('"oslonac"', "SLOVO PO SLOVO", "Isto pravilo za svakog", "Bez navodnika", "NISU odluke"):
        assert rule in sudija.NOTES and rule in sudija.WHOLE, rule
    assert 'NISU odluke' in sudija.DAY


def test_a_chairs_measure_put_among_the_decisions_is_moved_to_the_steps_when_written():
    s = sudija.settle_votes({"odluke": [{"vreme": "10:31", "sta": "Predsedavajući je izrekao opomenu poslaniku Mirkoviću."},
                                        {"vreme": "11:43", "sta": "Usvojena je odluka.", "glasanje": {"za": 136, "protiv": 0}}],
                             "tok": [{"vreme": "10:03", "sta": "Nastavljena je sednica."}, {"vreme": "11:00", "sta": "Pauza."}]})
    assert [o["sta"] for o in s["odluke"]] == ["Usvojena je odluka."] and s["odluke"][0]["glasovi"]
    assert [t["vreme"] for t in s["tok"]] == ["10:03", "10:31", "11:00"]


def _reply(need, said, words=8):
    return json.dumps({"naslov": "Skupština je potvrdila mandate", "kratko": "Potvrđeni su mandati.",
                       "ukratko": "Skupština je potvrdila mandate poslanika.", "odluke": [], "tok": [],
                       "govornici": [{"ime": n, "lista": "", "o_cemu": "Govorio je.", "oslonac": [" ".join(said[n].split()[:words])]}
                                     for n in need]}, ensure_ascii=False)


def test_a_day_from_the_notes_is_the_record_s_speakers_in_latin_letters_each_with_text_of_their_own():
    import sazetak_dana as tool
    f = DATA / "15" / "snimak" / "2026-11-17.json"
    if not f.exists():
        return
    conv = tool.convocation("2026-11-17")
    text, need, lists, said = tool.notes_material("2026-11-17", conv, json.loads(f.read_text(encoding="utf-8")))
    assert need and all(said.get(n) for n in need) and all(n in lists for n in need)
    assert not any("Ѐ" <= ch <= "ӿ" for ch in text)  # the notes are in Cyrillic; the summary is in Latin
    assert text.startswith("[") and sudija.CHAIR in text and "Vučić Aleksandar (Aleksandar Vučić - Srbija pobeđuje):" in text
    clocks = [line[1:9] for line in text.splitlines()]
    assert clocks == sorted(clocks)  # in the notes' order, at the recording's seconds
    calls = []

    def ask(system, user, *_):
        calls.append(system)
        return _reply(need, said)
    done = sudija.whole_day(ask, text, need, lists, said, "", sudija.NOTES, "claude-opus-5-5", "Stenografske beleške dana")
    assert calls == [sudija.NOTES] and done["provera"] == [] and done["bez_oslonca"] == []
    assert all("oslonac" not in g for g in done["dan"]["govornici"]) and set(done["oslonac"]) == set(need)


def test_the_tool_writes_the_days_file_marked_by_its_source_and_puts_nothing_in_place(tmp_path, monkeypatch, capsys):
    import sazetak_dana as tool
    if not (DATA / "15" / "snimak" / "2026-11-17.json").exists():
        return
    assert tool.main(["beleske", "2026-11-17", "--izlaz", str(tmp_path), "--bez-modela"]) == 0 and not list(tmp_path.iterdir())
    conv = tool.convocation("2026-11-17")
    _, need, _, said = tool.notes_material("2026-11-17", conv, json.loads((conv / "snimak" / "2026-11-17.json").read_text(encoding="utf-8")))
    monkeypatch.setattr(sudija.config, "MODEL_KEY", "test")
    monkeypatch.setattr(sudija, "ask_claude", lambda *a: _reply(need, said))
    kept_in_repo = DATA / "15" / "sazetak" / "2026-11-17.json"
    before = kept_in_repo.read_bytes() if kept_in_repo.exists() else None
    assert tool.main(["beleske", "2026-11-17", "--izlaz", str(tmp_path)]) == 0
    kept = json.loads((tmp_path / "sazetak" / "2026-11-17.json").read_text(encoding="utf-8"))
    assert kept["izvor"] == kept["dan"]["izvor"] == "beleske" and kept["dan"]["model"] == sudija.config.DAY_MODEL
    basis = json.loads((tmp_path / "osnova" / "2026-11-17.json").read_text(encoding="utf-8"))
    assert set(basis["oslonac"]) == set(need) and basis["bez_oslonca"] == []
    assert "nađeno" in capsys.readouterr().out
    assert (kept_in_repo.read_bytes() if kept_in_repo.exists() else None) == before  # the repo's copy is not touched


def test_a_reply_whose_sentence_is_not_the_speakers_own_is_asked_again_and_said():
    need, said = ["Petrović Petar"], {"Petrović Petar": "Ovo je ono što je poslanik zaista rekao u sali tog dana i ništa drugo."}
    replies = [json.dumps({"ukratko": "Sednica.", "govornici": [{"ime": "Petrović Petar", "o_cemu": "Govorio je.", "oslonac": ["nešto sasvim drugo što nije rekao nikad"]}]}),
               _reply(need, said)]
    seen = []

    def ask(system, user, *_):
        seen.append(user)
        return replies[len(seen) - 1]
    done = sudija.whole_day(ask, "[10:00:00] Petrović Petar (A): " + said["Petrović Petar"], need, {"Petrović Petar": "A"}, said, "", sudija.NOTES, "m")
    assert len(seen) == 2 and "nije doslovno u njegovim redovima" in seen[1] and done["provera"] == []


def test_a_day_from_the_notes_is_labelled_so_on_the_day_page_and_the_live_page():
    from zoneinfo import ZoneInfo
    from uzivo import page
    day = (REPO / "src" / "zailiprotiv" / "templates" / "govornici_dan.html").read_text(encoding="utf-8")
    assert '{% if summary.izvor == "beleske" %}Napisao AI model' in day and "iz privremenih stenografskih beleški Skupštine" in day
    snap = {"dan": "2026-11-17", "ranije": True, "hronika": [], "danas": [], "sazetak": {
        "vrsta": "dan", "kratko": "Potvrđeni su mandati.", "izvor": "beleske", "model": "claude-opus-5-5",
        "odluke": [{"vreme": "11:20", "sta": "Potvrđeni su mandati poslanika."}]}}
    html = page._steps(snap, cyr=False, tz=ZoneInfo("Europe/Belgrade"))
    assert "iz privremenih stenografskih beleški Skupštine" in html and "iz automatskog prepisa zvuka, ne iz stenograma" not in html
    snap["sazetak"]["izvor"] = "prepis"
    assert "iz automatskog prepisa zvuka, ne iz stenograma" in page._steps(snap, cyr=False, tz=ZoneInfo("Europe/Belgrade"))


def test_a_day_again_from_the_kept_transcript_keeps_the_days_stretches(tmp_path, monkeypatch):
    import sazetak_dana as tool
    f = DATA / "15" / "snimak" / "2026-11-19.json"
    if not f.exists():
        return
    rec = json.loads(f.read_text(encoding="utf-8"))
    turns = tool.turns_of(rec)
    said = {str(t["od"] + 3): f"Ovo je govor broj {i} u kome poslanik govori o dnevnom redu sednice i izboru." for i, t in enumerate(turns)}
    (tmp_path / "in" / "prepis").mkdir(parents=True)
    (tmp_path / "in" / "prepis" / "2026-11-19.json").write_text(json.dumps(said), encoding="utf-8")
    (tmp_path / "in" / "sazetak").mkdir()
    (tmp_path / "in" / "sazetak" / "2026-11-19.json").write_text(json.dumps({"delovi": [{"ukratko": "deo"}], "dan": {"ukratko": "stari"}}), encoding="utf-8")
    text, need, lists, heard = tool.transcript_material("2026-11-19", tmp_path / "in", rec, tool.roster(DATA / "15"))
    assert need and all(heard.get(n) for n in need) and "Ovo je govor broj 0" in text
    monkeypatch.setattr(sudija.config, "MODEL_KEY", "test")
    monkeypatch.setattr(sudija, "ask_claude", lambda *a: _reply(need, heard))
    assert tool.main(["prepis", "2026-11-19", "--podaci", str(tmp_path / "in"), "--izlaz", str(tmp_path / "out")]) == 0
    kept = json.loads((tmp_path / "out" / "sazetak" / "2026-11-19.json").read_text(encoding="utf-8"))
    assert kept["delovi"] == [{"ukratko": "deo"}] and kept["dan"]["ukratko"] != "stari" and "izvor" not in kept["dan"]
