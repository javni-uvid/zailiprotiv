"""Following an area of laws by mail: the events of each area (oblasti.py), 27 Nov 2026."""
import datetime as dt
import json
from pathlib import Path

from zailiprotiv import oblasti

DATA = Path(__file__).parents[1] / "data"
BASE = "https://www.parlament.gov.rs/upload/rezultati_glasanja/x"


def test_a_year_of_the_fourteenth_gives_the_mails_the_proposal_counted():
    """The real data, 28 Nov 2025 to 27 Nov 2026: per area, the days with a mail at one mail a day, as in the
    proposal's table (PREDLOG.md), now from the built code. The adopted laws are 101 where the table had 98: it merged
    laws of one title passed the same day, which are separate laws."""
    evs = oblasti.events(DATA, "14", "15")
    mails = {a: oblasti.mail_days(evs, a, "2025-11-28", "2026-11-27")["mejlova"] for a in range(1, 18)}
    assert mails == {1: 4, 2: 13, 3: 1, 4: 3, 5: 1, 6: 15, 7: 1, 8: 14, 9: 6, 10: 16, 11: 6, 12: 4, 13: 9, 14: 0,
                     15: 14, 16: 16, 17: 16}
    every = oblasti.mail_days(evs, None, "2025-11-28", "2026-11-27")
    assert every["mejlova"] == 49 and every["najvise_u_nedelji"] == 5
    assert (every["usvojen"], every["procedura"]) == (101, 89) and 50 <= every["dnevni_red"] <= 56
    assert len({e["id"] for e in evs}) == len(evs)  # an event once


def _store(root, conv, **files):
    (root / conv / "votes").mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (root / conv / name.replace("__", "/")).write_text(json.dumps(data), encoding="utf-8")


def _vote(item, za, when="2026-12-10T12:00:00"):
    return {"item": item, "kind": oblasti.WHOLE, "when": when,
            "counts": {"za": za, "protiv": 3, "uzdrzan": 1, "nije_glasao": 0, "nije_prisutan": 0}, "rows": []}


def _bills(**areas):
    return {"fetched": "2026-12-01", "bills": {f"{k}.pdf": {
        "title": f"Predlog zakona o {k}", "submitted": "2026-11-30", "proposer": "Vlada", "first_seen": "2026-12-01",
        "last_seen": "2026-12-01", "areas": a} for k, a in areas.items()}}


def test_adopted_by_its_roll_call_the_next_morning_and_once(tmp_path):
    _store(tmp_path, "15", **{"laws.json": {"laws": {}}, "procedure.json": _bills(gasu=[6], putevima=[13], ugovoru=[]),
                              "votes__1.json": {"title": "Prva sednica", "votes": {
                                  BASE + "#0": _vote("1. Предлог закона о гасу у целини", 140),
                                  BASE + "#1": _vote("2. Предлог закона о путевима у целини", 120),
                                  BASE + "#2": _vote("3. Предлог закона о уговору у целини", 150)}}})
    evs = oblasti.events(tmp_path, "15", "15")
    adopted = [e for e in evs if e["vrsta"] == "usvojen"]
    # 140 for: passed whatever majority it needed. 120: it waits for the page of adopted laws. No area: no one.
    assert [(e["naslov"], e["dan"], e["za"]) for e in adopted] == [("Predlog zakona o gasu", "2026-12-10", 140)]
    assert {e["vrsta"] for e in evs if e["predlog"] == "ugovoru.pdf"} == set()
    # Listed later among the adopted laws: the same event, not a second one.
    _store(tmp_path, "15", **{"laws.json": {"laws": {"z.pdf": {
        "title": "Zakon o gasu", "bill_title": "Predlog zakona o gasu", "bill_pdf": "gasu.pdf", "passed": "2026-12-10",
        "areas": [6], "final_vote": BASE + "#0"}}}})
    again = [e for e in oblasti.events(tmp_path, "15", "15") if e["vrsta"] == "usvojen"]
    assert [e["id"] for e in again] == [adopted[0]["id"]]


def test_two_roll_calls_of_one_name_the_same_day_tell_nothing(tmp_path):
    _store(tmp_path, "15", **{"laws.json": {"laws": {}}, "procedure.json": _bills(gasu=[6]),
                              "votes__1.json": {"title": "Prva sednica", "votes": {
                                  BASE + "#0": _vote("1. Предлог закона о гасу у целини", 140),
                                  BASE + "#1": _vote("2. Предлог закона о гасу у целини", 140)}}})
    assert [e for e in oblasti.events(tmp_path, "15", "15") if e["vrsta"] == "usvojen"] == []


def test_on_a_sittings_agenda_by_the_bills_exact_name(tmp_path):
    _store(tmp_path, "15", **{"laws.json": {"laws": {}}, "procedure.json": _bills(gasu=[6]),
                              "index.json": {"sittings": {"u": {"title": "Druga sednica", "starts": "2026-12-08T10:00",
                                  "agenda": ["Предлог закона о гасу, који је поднела Влада", "Предлог закона о гасу и нафти"]}}}})
    agenda = [e for e in oblasti.events(tmp_path, "15", "15") if e["vrsta"] == "dnevni_red"]
    assert [(e["naslov"], e["dan"], e["sednica"]) for e in agenda] == [("Predlog zakona o gasu", "2026-12-08", "Druga sednica")]


def test_the_published_file_has_both_scripts_and_the_sites_pages(tmp_path):
    _store(tmp_path, "15", **{"laws.json": {"laws": {}}, "procedure.json": _bills(gasu=[6])})
    from zailiprotiv.cyrillic import cyr
    from zailiprotiv.translit import latin
    out = oblasti.published(oblasti.events(tmp_path, "15", "15"), today=dt.date(2026, 12, 2), laws={},
                            bills={"gasu.pdf": "predlog/zakon-o-gasu"}, latin=latin, cyr=cyr)
    e, = out["dogadjaji"]
    assert e["vrsta"] == "procedura" and e["strana"] == "predlog/zakon-o-gasu" and e["naslov_cir"] == "Предлог закона о гасу"
    assert e["predlagac"] == "Vlada" and len(out["oblasti"]) == 17
    assert oblasti.published(oblasti.events(tmp_path, "15", "15"), today=dt.date(2027, 2, 1), laws={}, bills={},
                             latin=latin, cyr=cyr)["dogadjaji"] == []  # past KEEP_DAYS


def test_every_area_can_be_followed():
    from zailiprotiv.cyrillic import cyr
    from zailiprotiv.site import slug
    from zailiprotiv.translit import latin
    areas = oblasti.followable(latin=latin, cyr=cyr, area_slug=lambda a: slug(latin(a))[:80])
    assert len(areas) == 17 and areas["saobracaj"] == ["Saobraćaj", "Саобраћај"]


def test_every_area_page_has_the_sign_up_and_a_law_links_to_it(tmp_path):
    import re
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from test_site import data
    from zailiprotiv import site
    out, root = tmp_path / "_site", data(tmp_path)
    (root / "settings.json").write_text(json.dumps({"votes_api": "https://glasovi.example/"}))
    site.build(root, out, "zailiprotiv.rs", cyrillic=True)
    assert len(json.loads((out / oblasti.FOLLOW_FILE).read_text(encoding="utf-8"))) == 17
    assert "dogadjaji" in json.loads((out / oblasti.EVENTS_FILE).read_text(encoding="utf-8"))
    pages = sorted((out / "oblast").glob("*.html"))
    assert len(pages) == 17
    for f in pages:
        page = f.read_text(encoding="utf-8")
        assert f'name="sta" value="{f.stem}"' in page and 'name="vrsta" value="o"' in page, f.stem
        assert "Kad zakon iz ove oblasti uđe u proceduru, dođe na dnevni red ili bude usvojen" in page
    empty = (out / "oblast" / "praznici-i-odlikovanja.html").read_text(encoding="utf-8")
    assert "Iz ove oblasti još nema usvojenog zakona ni predloga u proceduri." in empty
    cir = (out / "cir" / "oblast" / "praznici-i-odlikovanja.html").read_text(encoding="utf-8")
    assert 'name="pismo" value="cir"' in cir and "Шта пратиш чувамо шифровано." in cir
    law = (out / "zakon" / "zakon-o-oruzju.html").read_text(encoding="utf-8")
    assert re.search(r'href="\.\./oblast/odbrana-i-bezbednost-vanredne-mere(\.html)?#prati">prati oblast mejlom</a>', law)
    mp = (out / "poslanik" / "abramovic-nenad.html").read_text(encoding="utf-8")
    assert 'name="vrsta"' not in mp  # an MP's sign-up as it was
