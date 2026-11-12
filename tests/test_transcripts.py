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
    assert not any(s["part"] == "general" for s in d["speeches"] if s["day"] == 3)
    on_2 = [a for a in d["amendments"] if a["item"] == 2]
    assert on_2[0] == {"day": 3, "item": 2, "article": 3, "by": "народни посланици групе „Ми – Снага народа“"}


def test_days_from_the_sitting_page():
    html = ('<a href="/upload/archive/files/cir/doc/stenografske_beleske/Sednica%2017.docx">СТЕНОГРАФСКЕ БЕЛЕШКЕ - '
            'Седмо ванредно заседање</a><a href="/upload/archive/files/cir/doc/stenografske_beleske/Sednica 2.docx">'
            'СТЕНОГРАФСКЕ БЕЛЕШКЕ - Седмо ванредно заседање - 2. дан (18. јун 2026.)</a><a href="/x.pdf">x</a>')
    found = t.days(html, "https://www.parlament.gov.rs/sednica.53524.43.html")
    assert [d["day"] for d in found] == [1, 2] and found[1]["url"].endswith("Sednica 2.docx")
