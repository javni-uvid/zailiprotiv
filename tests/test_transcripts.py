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
