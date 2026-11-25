"""govor.py: the notes' speeches found in the recording's words."""
from zailiprotiv import govor

F = "https://arhiva.example/zas1.mp4"


def heard(text: str, start: float = 0.0, url: str = F, step: float = 0.5):
    return [(w, url, start + i * step) for i, w in enumerate(govor.fold(text))]


def test_fold_latin_lower_no_diacritics():
    assert govor.fold("Реч има народни посланик Ђорђе Милићевић.") == ["rec", "ima", "narodni", "poslanik", "djordje",
                                                                       "milicevic"]
    assert govor.fold("Gjordjević") == ["djordjevic"]


def test_anchors_keep_one_order():
    said = "a b c d e f g h i j".split()
    got = "x a b c d e y f g h i j".split()
    runs = govor.anchors(said, got, n=4)
    assert runs and all(p2 > p1 for (_, p1), (_, p2) in zip(runs, runs[1:]))
    assert runs[0] == (0, 1)


def test_place_and_day():
    chair = "Hvala vam. Reč ima narodni poslanik Petar Petrović, izvolite kolega."
    mp = ("Poštovani predsedavajući, dame i gospodo, govorim danas o budžetu za školstvo i o tome kako se novac deli "
          "opštinama na jugu zemlje gde škole nemaju grejanje već treću godinu zaredom.")
    speeches = [{"key": "1", "chair": True, "speaker": "ПРЕДСЕДАВАЈУЋИ", "text": chair},
                {"key": "2", "chair": False, "speaker": "ПЕТАР ПЕТРОВИЋ", "text": mp},
                {"key": "3", "chair": True, "speaker": "ПРЕДСЕДАВАЈУЋИ", "text": "Zahvaljujem."}]
    # the recording: a few words before, the chair, the speech with one word misheard, the end
    words = heard("buka u sali " + chair, 100) + heard(mp.replace("grejanje", "grijanje"), 120) + heard("hvala", 160)
    placed = govor.place(speeches, words)
    assert placed[1]["datoteka"] == F and 119 <= placed[1]["od"] <= 121 and placed[1]["do"] > 130
    assert "datoteka" not in placed[2]  # one word is no run of four: no place
    turns = govor.day(placed, [{"url": F, "od": 1_000_000}], lambda s: {"ime": "Petrović Petar", "adresa": "petrovic-petar",
                                                                       "grupa": "", "uloga": ""})
    assert [t["ime"] for t in turns] == ["Petrović Petar"]  # the chair is not listed
    t = turns[0]
    assert t["od"] == 1_000_000 + int(placed[1]["od"]) and t["snimak"] == int(placed[1]["od"] - govor.LEAD)
    assert t["okvira"] >= govor.MIN_ANCHORS and t["beleske"] == ["2"]


def test_a_very_short_speech_between_two_placed_ones_gets_a_place():
    """21 Nov 2026: "Ne želim." (two words) answering the chair has no run of four, and so no place by runs; it stands
    just after the speech before it. A longer speech with no runs, or a short one at the edge, still has none."""
    def sp(key, text, **kw):
        return {"key": key, "speaker": "P" if key != "2" else "A", "chair": key != "2", "text": text, "sidra": 0, **kw}
    chair1 = sp("1", "Да ли желите да се Скупштина изјасни о овоме што сте рекли?", datoteka=F, od=10.0, do=15.0, sidra=2)
    mp = sp("2", "Не желим.")
    chair2 = sp("3", "Нећете. Имамо још једну пријаву повреде Пословника.", datoteka=F, od=14.0, do=26.0, sidra=2)
    out = govor.between([dict(chair1), dict(mp), dict(chair2)])
    assert out[1]["datoteka"] == F and out[1]["od"] == 15.0 and 15.0 < out[1]["do"] < 17.0 and out[1]["sidra"] == 0
    long_ = sp("2", "Ovo je govor koji ima mnogo više reči nego što staje u kratak odgovor i nema nijedan niz.")
    assert "datoteka" not in govor.between([dict(chair1), dict(long_), dict(chair2)])[1]
    assert "datoteka" not in govor.between([dict(chair1), dict(mp)])[1]  # nothing after it
    other = dict(chair2, datoteka=F + "b")
    assert "datoteka" not in govor.between([dict(chair1), dict(mp), other])[1]  # the neighbours in two files
    turns = govor.day(govor.between([dict(chair1, speaker="A", chair=False), dict(mp), dict(chair2)]),
                      [{"url": F, "od": 0}], lambda s: {"ime": s, "adresa": "", "grupa": "", "uloga": ""})
    assert len(turns) == 1 and turns[0]["okvira"] == 2  # joined to the speech before it as one turn, no sample of its own


def test_day_joins_one_speaker_across_the_chair():
    a = {"key": "1", "speaker": "A", "datoteka": F, "od": 10.0, "do": 50.0, "sidra": 3}
    c = {"key": "2", "speaker": "P", "chair": True}
    b = {"key": "3", "speaker": "A", "datoteka": F, "od": 60.0, "do": 90.0, "sidra": 2}
    other = {"key": "4", "speaker": "B", "datoteka": F, "od": 100.0, "do": 120.0, "sidra": 2}
    turns = govor.day([a, c, b, other], [{"url": F, "od": 0}], lambda s: {"ime": s, "adresa": "", "grupa": "", "uloga": ""})
    assert [(t["ime"], t["od"], t["do"], t["okvira"]) for t in turns] == [("A", 10, 90, 5), ("B", 100, 120, 2)]


def test_a_days_part_the_archive_holds_before_its_page_lists_it():
    from zailiprotiv import videos
    base = "https://arhiva.videonet.co.rs/filesnsrs/zasedanja/zas2026111910"
    parts = [{"part": i + 1, "title": "Sednica", "url": f"{base}{s}.mp4"} for i, s in enumerate(["", "a", "b", "c", "d"])]
    there = {f"{base}e.mp4"}
    got = videos.unlisted(parts, lambda u: u in there)
    assert got == [{"part": 6, "title": "Sednica", "url": f"{base}e.mp4", "nenavedeno": True}]
    assert videos.unlisted(parts[:1], lambda u: u in there) == []  # "a" is not there: nothing further is tried
    assert videos.unlisted([], lambda u: True) == []


def test_files_placed_on_the_clock_by_captions_read_in_passing():
    a, b, c = "u/a.mp4", "u/b.mp4", "u/c.mp4"
    files = [{"url": a, "trajanje": 1000}, {"url": b, "trajanje": 2000}, {"url": c, "trajanje": 500}]
    stretches = {b: [("pastor", 100.0, 400.0, 0.8)], c: [("pastor", 50.0, 150.0, 0.8)]}
    # one caption of Pastor read in passing in each: b alone could start anywhere in 300 s, but b's end and c's start
    # must meet (no break between them), and c has one reading too
    record = [{"adresa": "pastor", "od": 10_200}, {"adresa": "pastor", "od": 12_100 + 100}]
    got = govor.clock(files, stretches, record, {a: 5000})
    assert got[a] == (5000, "poznato")
    assert set(got) == {a, b, c} and abs(got[b][0] + 2000 - got[c][0]) <= govor.AGREE
    assert govor.clock(files, {b: stretches[b]}, record[:1], {a: 5000}).keys() == {a}  # one reading, no neighbour to confirm it


def test_voice_day_joins_and_places():
    f = "u/b.mp4"
    st = {f: [("x", 100.0, 200.0, "glas"), ("x", 250.0, 300.0, "glas"), ("y", 400.0, 500.0, "glas")]}
    turns = govor.voice_day([{"url": f, "trajanje": 1000}], st, {f: (1000.0, "")},
                            lambda w: {"ime": w, "adresa": w, "grupa": "", "uloga": ""})
    assert [(t["adresa"], t["od"], t["do"], t["snimak"], t["po"]) for t in turns] == [
        ("x", 1100, 1300, 95, "glas"), ("y", 1400, 1500, 395, "glas")]


def test_a_part_starts_after_the_one_before_it():
    a, b = "u/a.mp4", "u/b.mp4"
    files = [{"url": a, "trajanje": 1000}, {"url": b, "trajanje": 1000}]
    st = {b: [("x", 100.0, 200.0, 0.8)]}
    # x was read in the morning, inside a's time, and again later: only the later readings can place b
    record = [{"adresa": "x", "od": 5150}, {"adresa": "x", "od": 5160}, {"adresa": "x", "od": 9150}, {"adresa": "x", "od": 9160}]
    got = govor.clock(files, st, record, {a: 5000})
    assert 8950 <= got[b][0] <= 9060


def test_a_speech_across_two_files_has_a_place_in_each():
    """24 Nov 2026: an hour's speech of 19 Nov ended in the next file of the archive and had no place."""
    g = "https://arhiva.example/zas2.mp4"
    first = "govorim danas o budžetu za školstvo i o tome kako se novac deli opštinama na jugu zemlje"
    rest = "gde škole nemaju grejanje već treću godinu zaredom i gde nastavnici sami kupuju drva za zimu"
    speeches = [{"key": "1", "chair": False, "speaker": "ПЕТАР ПЕТРОВИЋ", "text": first + " " + rest}]
    placed = govor.place(speeches, heard(first, 3000) + heard(rest, 0, url=g))
    assert placed[0]["datoteka"] == F and placed[0]["od"] == 3000 and placed[0]["dalje"]["datoteka"] == g
    turns = govor.day(placed, [{"url": F, "od": 1_000_000}, {"url": g, "od": 1_010_000}],
                      lambda s: {"ime": "Petrović Petar", "adresa": "petrovic-petar", "grupa": "", "uloga": ""})
    assert [(t["datoteka"], t["od"]) for t in turns] == [(F, 1_003_000), (g, 1_010_000)]


def test_a_vote_read_out_is_no_speech_and_a_misspelt_name_is_the_one_near():
    roll = "; ".join(f"Презиме{i} Име – за" for i in range(20)) + ";"
    assert govor.roll_call(roll) and not govor.roll_call("Поштовани, говорим о закону – и то дуго; хвала.")
    keys = {"бакић јово": 1, "митов петар": 1, "јовановић петар": 1, "вучић александар": 1}
    assert govor.nearest("бакић јова", keys) == "бакић јово" and govor.nearest("митев петар", keys) == "митов петар"
    assert govor.nearest("смиљанић срђан", keys) is None  # nobody near
    anas = {"ана брнабић": 1, "ана белоица": 1, "вујичић јован": 1}
    assert govor.nearest("ана брбанић", anas) == "ана брнабић"  # two letters exchanged (25 Nov 2026)
    assert govor.nearest("ана бранчић", anas) is None  # more than two letters out of place
    assert govor.nearest("бакић јова", {"бакић јово": 1, "бакић јоца": 1}) is None  # two as near


def test_a_speaker_seen_first_on_a_day_without_groups_has_the_lists_group(tmp_path, monkeypatch):
    """24 Nov 2026: Vjerica Radeta, whose turn of the 17th names no list, would have stood under none."""
    import json
    from types import SimpleNamespace
    from zailiprotiv.cli import common, recordings
    c = tmp_path / "15"
    for d in ("snimak", "uzivo", "transcripts", "reci"):
        (c / d).mkdir(parents=True)

    def write(path, data):
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    url = "https://x/a.mp4"
    text = "један два три четири пет шест седам осам девет десет"
    write(c / "videos.json", {"days": {"2026-11-24": [{"part": 1, "url": url}]}})
    write(c / "arhiva.json", {url: {"od": 1000, "trajanje": 100}})
    write(c / "members.json", {"members": [{"name": "РАДЕТА ВЈЕРИЦА", "group": "Листа А"}, {"name": "БАКИЋ ЈОВО", "group": "Листа Б"}]})
    write(c / "snimak" / "2026-11-17.json", {"govori": [
        {"ime": "Radeta Vjerica", "adresa": "radeta-vjerica", "grupa": "", "uloga": "", "od": 1, "do": 2},
        {"ime": "Bakić Jovo", "adresa": "bakic-jovo", "grupa": "", "uloga": "Lista s potpisa", "od": 3, "do": 4}]})
    write(c / "transcripts" / "1.json", {"days": [{"day": 4, "listed_date": "2026-11-24"}], "speeches": {
        "1": {"day": 4, "speaker": "ВЈЕРИЦА РАДЕТА", "chair": False, "text": text},
        "2": {"day": 4, "speaker": "ЈОВО БАКИЋ", "chair": False, "text": "а" + text.replace(" ", " а")}}})
    words = text.split() + ("а" + text.replace(" ", " а")).split()
    (c / "reci" / "a.jsonl").write_text(json.dumps({"reci": [[i, i + 1, w] for i, w in enumerate(words)]}), encoding="utf-8")
    monkeypatch.setattr(common, "ROOT", tmp_path)
    monkeypatch.setattr(common, "CONVOCATION", "15")
    recordings.govor_cmd(SimpleNamespace(day="2026-11-24", heard=str(c / "reci"), note="", dry_run=False))
    turns = json.loads((c / "snimak" / "2026-11-24.json").read_text(encoding="utf-8"))["govori"]
    assert [(t["ime"], t["grupa"], t["uloga"]) for t in turns] == [("Radeta Vjerica", "Lista A", ""),
                                                                  ("Bakić Jovo", "", "Lista s potpisa")]


def test_a_file_the_archive_cut_inside_has_a_clock_for_each_stretch():
    """24 Nov 2026: 12 minutes of the first file were published 70 minutes late, the break being cut out of it."""
    f = {"url": "u", "od": 5000, "delovi": [{"sek": 0, "od": 1000}, {"sek": 100, "od": 5000}]}
    assert [govor.start_at(f, s) for s in (0, 99.9, 100, 500)] == [1000, 1000, 5000, 5000]
    assert govor.start_at({"url": "u", "od": 7}, 3) == 7
    speech = lambda key, who, a, b: {"key": key, "speaker": who, "text": "x", "chair": False, "datoteka": "u",
                                     "od": a, "do": b, "sidra": 3}
    turns = govor.day([speech("1", "А", 10, 60), speech("2", "А", 110, 150), speech("3", "А", 200, 220)], [f],
                      lambda s: {"ime": s, "adresa": "", "grupa": "", "uloga": ""})
    # one speaker on both sides of the cut is two turns; each opens at its own second of the file
    assert [(t["od"], t["do"], t["snimak"]) for t in turns] == [(1010, 1060, 5), (5110, 5220, 105)]
    assert govor.stretches(f, 900) == [{"url": "u", "od": 1000, "trajanje": 100},
                                       {"url": "u", "od": 5000, "trajanje": 900, "preskoceno": 100}]
    assert govor.stretches({"url": "u", "od": 7}, 900) == [{"url": "u", "od": 7, "trajanje": 900}]
