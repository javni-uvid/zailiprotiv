from pathlib import Path

from zailiprotiv import transcripts as t

HERE = Path(__file__).parent / "fixtures" / "transcripts"


def day(part: str) -> list[str]:
    return t.paragraphs(next(p for p in HERE.glob("*.docx") if part in p.name).read_bytes())


def test_speeches_and_heading():
    paras = day("04.11.2025")
    assert t.heading(paras) == {"date": "04 новембар 2025", "provisional": True}
    s = t.speeches(paras)
    assert s[0]["speaker"] == "ПРЕДСЕДНИК" and s[0]["chair"]
    assert any(x["speaker"] == "МИЛЕНКО ЈОВАНОВ" and not x["chair"] for x in s)
    assert t.joint(s) and t.joint(s)[0] == (1, 8)


def test_chair_typo():
    assert t.is_chair("ПРЕДСЕДСАВАЈУЋА") and t.is_chair("ПРЕДСЕДАВАЈУЋ") and not t.is_chair("МИЛЕНКО ЈОВАНОВ")


def test_debate_parts_carry_over_days():
    d = t.debate([day("04.11.2025"), day("drugi_dan"), day("cetvrti_dan")])
    assert list(d["agenda"]) == list(range(1, 9))
    assert d["agenda"][2].startswith("Предлог закона о посебним поступцима ради реализације пројекта ревитализације")
    parts = {(s["day"], s["part"], tuple(s["items"])) for s in d["speeches"] if not s["chair"]}
    assert (1, "general", tuple(range(1, 9))) in parts and (2, "general", tuple(range(1, 9))) in parts
    assert (3, "detail", (2,)) in parts and (3, "detail", (5,)) in parts
    # On the last day only the amendments of the bills debated together were discussed (and a list of candidates).
    assert not any(s["part"] == "general" and set(s["items"]) & set(range(1, 9)) for s in d["speeches"] if s["day"] == 3)
    on_2 = [a for a in d["amendments"] if a["item"] == 2]
    assert on_2[0] == {"day": 3, "item": 2, "article": 3, "by": "народни посланици групе „Ми – Снага народа“"}


def test_days_from_the_sitting_page():
    html = ('<a href="/upload/archive/files/cir/doc/stenografske_beleske/Sednica%2017.docx">СТЕНОГРАФСКЕ БЕЛЕШКЕ - '
            'Седмо ванредно заседање</a><a href="/upload/archive/files/cir/doc/stenografske_beleske/Sednica 2.docx">'
            'СТЕНОГРАФСКЕ БЕЛЕШКЕ - Седмо ванредно заседање - 2. дан (18. јун 2026.)</a><a href="/x.pdf">x</a>')
    found = t.days(html, "https://www.parlament.gov.rs/sednica.53524.43.html")
    assert [d["day"] for d in found] == [1, 2] and found[1]["url"].endswith("Sednica 2.docx")


def test_chair_phrasings():
    agenda = {1: "Предлог закона о буџету", 2: "Предлог закона о судијама", 3: "Предлог закона о Високом савету тужилаштва",
              4: "Предлог закона о оружју"}
    state = {"part": "detail", "items": [2], "joint": [1, 2, 3, 4]}
    debated = {1, 2, 3, 4}
    move = lambda line: t._move(line, agenda, state, debated, {1, 2})
    assert move("Прелазимо на трећу тачку дневног реда – ПРЕДЛОГ ЗАКОНА О ВИСОКОМ САВЕТУ ТУЖИЛАШТВА.") == \
        {"part": "detail", "items": [3]}
    assert move("Претрес у појединостима о 4. тачки дневног реда – ПРЕДЛОГУ ЗАКОНА О ОРУЖЈУ") == {"part": "detail", "items": [4]}
    assert move("Отварам претрес Предлога закона, у појединостима.") == {"part": "detail", "items": [2]}
    assert move("Прелазимо на одлучивање о повредама Пословника.") == {"part": "other", "items": []}
    assert move("Прелазимо на листу.") is None
    assert t.ordinal("Пету") == 5 and t.ordinal("Првој") == 1 and t.ordinal("петнаесту") is None
    m = t.AMENDMENT.search("На члан 1. амандмане, у истоветном тексту, поднели су посланици групе Слога.")
    assert m and m.group(1) == "1" and m.group(2) == "посланици групе Слога"


def test_questions_hour_pauses_the_debate():
    day1 = ["ПРЕДСЕДНИК: Д н е в н и р е д:", "Предлог закона о буџету,", "Предлог закона о судијама,",
            "Отварам заједнички начелни и јединствени претрес о предлозима аката из тачака 1. до 2. дневног реда.",
            "ПЕТАР ПЕТРОВИЋ: Говорим о буџету."]
    day2 = ["ПРЕДСЕДНИК: Да ли неко жели да затражи обавештење у складу са чланом 287. Пословника?",
            "МАРКО МАРКОВИЋ: Питање за министра.", "ПРЕДСЕДНИК: Настављамо са листом.", "ЈОВАН ЈОВИЋ: О судијама."]
    d = t.debate([day1, day2])
    parts = [(s["speaker"], s["part"], s["items"]) for s in d["speeches"] if not s["chair"]]
    assert parts == [("ПЕТАР ПЕТРОВИЋ", "general", [1, 2]), ("МАРКО МАРКОВИЋ", "other", []),
                     ("ЈОВАН ЈОВИЋ", "general", [1, 2])]


def test_iso_date():
    assert t.iso_date("Druga sednica Drugog redovnog zasedanja NSRS 04.11.2025..docx") == "2025-11-04"
    assert t.iso_date("NSRS, odrzana  7. novembra 2025. godine, cetvrti dan rada.docx") == "2025-11-07"
    assert t.iso_date("СТЕНОГРАФСКЕ БЕЛЕШКЕ - … - 2. дан (18. јун 2026.)") == "2026-06-18"
    assert t.iso_date("Sednica Sedmog vanrednog zasedanja") == ""


def test_tools_installed_at_first_need(monkeypatch):
    """A program the older notes need is installed only when asked for and missing, and only where the environment
    says how."""
    ran, have = [], set()
    monkeypatch.setattr(t.shutil, "which", lambda name: name if name in have else None)
    monkeypatch.setattr(t.subprocess, "run", lambda cmd, **kw: ran.append((cmd, kw)))
    monkeypatch.delenv("NOTES_TOOLS_INSTALL", raising=False)
    assert t.tool("soffice") == "soffice" and not ran  # nowhere said how: left to fail as a missing program does
    monkeypatch.setenv("NOTES_TOOLS_INSTALL", "install-them")
    assert t.tool("soffice") == "soffice" and ran == [("install-them", {"shell": True, "check": True})]
    have.add("soffice")
    assert t.tool("soffice") == "soffice" and len(ran) == 1  # there already: not installed again


def test_a_sitting_read_before_is_read_again_when_a_day_is_added(tmp_path, monkeypatch):
    """24 Nov 2026: the notes of 19 Nov were linked after the sitting had been read, and never read."""
    import argparse
    import json
    from zailiprotiv import skupstina, transcripts
    from zailiprotiv.cli import assembly
    url = "https://www.parlament.gov.rs/a.5.43.html"
    (tmp_path / "laws.json").write_text('{"laws": {}}', encoding="utf-8")
    (tmp_path / "index.json").write_text(json.dumps({"sittings": {url: {}}}), encoding="utf-8")
    (tmp_path / "votes").mkdir()
    listed = [{"url": "https://x/1.docx", "day": 1}]
    fetched = []
    monkeypatch.setattr(skupstina, "fetch", lambda u: fetched.append(u) or b"x")
    monkeypatch.setattr(transcripts, "days", lambda page, u: [dict(d) for d in listed])
    monkeypatch.setattr(transcripts, "paragraphs", lambda body: ["a"])
    monkeypatch.setattr(transcripts, "heading", lambda paras: {"date": "", "provisional": True})
    monkeypatch.setattr(transcripts, "debate", lambda days: {"agenda": {}, "amendments": [], "speeches": [{"t": len(days)}]})
    monkeypatch.setattr(assembly, "all_votes", lambda p: {})
    args = argparse.Namespace(laws=str(tmp_path / "laws.json"), votes=str(tmp_path / "votes"), index=str(tmp_path / "index.json"),
                              out=str(tmp_path / "out"), top=5, law=[], again=False, all=True, more=True, minutes=0)
    assembly.notes_of_debate(args)
    assert len(fetched) == 2  # the page and its one day's notes
    fetched.clear()
    assembly.notes_of_debate(args)
    assert len(fetched) == 1  # nothing new: the page only
    listed.append({"url": "https://x/2.docx", "day": 2})
    fetched.clear()
    assembly.notes_of_debate(args)
    path = next((tmp_path / "out").glob("*.json"))
    assert len(json.loads(path.read_text(encoding="utf-8"))["days"]) == 2 and len(fetched) == 3
    fetched.clear()
    args.more = False
    assembly.notes_of_debate(args)
    assert fetched == []  # as before without --more


def test_a_heading_inside_a_line_and_a_roll_call_glued_on_are_split_off_with_every_word_kept():
    """25 Nov 2026: the notes of 24 Nov hold "…повреда Пословника.АНА БРНАБИЋ: …" in the chair's speech, and those of
    19 Nov the rest of a roll call glued onto Ana Brnabić's answer, which the notes give no heading: nobody's. A heading of one word that is no role, or one after
    no sentence's end, splits nothing; no other key moves; run again, nothing changes."""
    from zailiprotiv import transcripts
    roll = "\n".join(f"Презиме{c} Име – Марија Бјелобрк, Сара Валентик;" for c in "абвгдђежзијклљмнњопрс")
    sp = {
        "00001": {"day": 1, "speaker": "СРЂАН СМИЉАНИЋ", "chair": False, "part": "other", "items": [], "text": roll},
        "00002": {"day": 1, "speaker": "АНА БРНАБИЋ", "chair": False, "part": "other", "items": [],
                  "text": "Нећу да учествујем у овој фарси. Хвала вам.\n63/1МВ/МЈ22.35 – 22.45\n" + roll},
        "00003": {"day": 1, "speaker": "ПРЕДСЕДНИК", "chair": True, "part": "other", "items": [],
                  "text": "Молим вас, само објасните која је повреда Пословника.АНА БРНАБИЋ: Члан 107 – поштовање. Да.\n"
                          "Дакле, понављајте за мном. ЗАКОН: није говорник. Рекао је ПРЕДСЕДНИК СКУПШТИНЕ: ништа"},
    }
    got = transcripts.mended(sp)
    assert list(got) == ["00001", "00002", "00002a", "00003", "00003a"]
    assert got["00002"]["text"] == "Нећу да учествујем у овој фарси. Хвала вам.\n63/1МВ/МЈ22.35 – 22.45"
    assert got["00002a"]["speaker"] == "" and got["00002a"]["no_heading"] == transcripts.NO_HEADING  # nobody's
    assert got["00002a"]["text"] == roll and transcripts.tally(list(got.values()))[""] == 0
    assert got["00003"]["text"] == "Молим вас, само објасните која је повреда Пословника."
    assert got["00003a"]["speaker"] == "АНА БРНАБИЋ" and not got["00003a"]["chair"]
    assert got["00003a"]["text"].startswith("Члан 107") and got["00003a"]["text"].endswith("СКУПШТИНЕ: ништа")
    assert transcripts.mended(got) == got
    # a list in a speech with no roll call read before it that day stays the speaker's
    alone = {k: v for k, v in sp.items() if k != "00001"}
    assert transcripts.mended(alone)["00002"] == sp["00002"]
