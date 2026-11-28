"""Following one bill or one law by mail, the site's part (oblasti.py), 28 Nov 2026: the laws a title changes, the
events of every bill, the lists the counter takes."""
import collections
import datetime as dt
import json
from pathlib import Path

from zailiprotiv import oblasti
from zailiprotiv.cyrillic import cyr
from zailiprotiv.translit import latin

DATA = Path(__file__).parents[1] / "data"


def test_the_law_a_title_changes():
    assert oblasti.named("Predlog zakona o izmenama i dopunama Zakona o porezu na dohodak građana") == [
        "Zakon o porezu na dohodak građana"]
    assert oblasti.named("Zakon o izmeni Krivičnog zakonika") == ["Krivični zakonik"]
    assert oblasti.named("Zakon o izmenama i dopuni Carinskog zakona") == ["Carinski zakon"]
    assert oblasti.named("Zakon o izmenama i dopunama Zakonika o krivičnom postupku") == ["Zakonik o krivičnom postupku"]
    # The law beneath a repeal of an amendment; a name with a comma or "sa" in it stays whole.
    assert oblasti.named("Predlog zakona o prestanku važenja Zakona o izmenama Zakona o Visokom savetu tužilaštva") == [
        "Zakon o Visokom savetu tužilaštva"]
    assert oblasti.named("Zakon o izmenama i dopunama Zakona o istraživanju nesreća u vazdušnom, železničkom i vodnom "
                         "saobraćaju") == ["Zakon o istraživanju nesreća u vazdušnom, železničkom i vodnom saobraćaju"]
    assert oblasti.named("Zakon o prestanku važenja Zakona o sistemu plata zaposlenih u javnom sektoru, Zakona o platama "
                         "službenika i Zakona o zaposlenima u javnim službama") == [
        "Zakon o sistemu plata zaposlenih u javnom sektoru", "Zakon o platama službenika",
        "Zakon o zaposlenima u javnim službama"]
    assert oblasti.named("Predlog zakona o gasu") == ["Zakon o gasu"]  # a new law: itself
    assert oblasti.named("Предлог закона о изменама Закона о раду") == ["Zakon o radu"]
    assert oblasti.named("Predlog odluke o izboru članova Saveta") == []
    # A law's page follows the law it changes.
    assert oblasti.law_key("Zakon o izmenama Zakona o radu") == oblasti.law_key("Zakon o radu") == "zakon-o-radu"


def test_every_law_of_the_site_has_one_key_the_counter_takes():
    titles = [law["title"] for f in sorted(DATA.glob("*/laws.json"))
              for law in json.loads(f.read_text(encoding="utf-8"))["laws"].values()]
    laws = oblasti.laws_followable(titles, latin=latin, cyr=cyr)
    assert all(len(k) <= oblasti.KEY and k.replace("-", "").isalnum() for k in laws)
    assert all(oblasti.law_key(t) in laws for t in titles)  # every law's page has its key in the list
    # Spellings of one name are one key: a dash, a capital.
    assert oblasti.law_key("Zakon o Registru administrativnih postupaka") == oblasti.law_key(
        "Zakon o registru administrativnih postupaka")
    assert laws["zakon-o-radu"] == ["Zakon o radu", "Закон о раду"]
    # The longest titles (loans) get a key of their first words and a digest, the same at every build.
    long = max(titles, key=len)
    assert len(oblasti.law_key(long)) == oblasti.KEY and oblasti.law_key(long) == oblasti.law_key(long)


def test_a_year_of_the_fourteenth_for_who_follows_a_law_or_a_bill():
    """The real data, 28 Nov 2025 to 27 Nov 2026 (the proposal counted 85 bills and 64 laws by a narrower rule, which
    left out repeals and a law named after another): of 173 bills in procedure, 94 change a law the title names, 67
    laws in all, at most 4 bills a law. Who followed the most changed laws would have had a mail on 11 days, and who
    followed a bill had one to three events after it was listed."""
    evs = [e for e in oblasti.events(DATA, "14", "15") if "2025-11-28" <= e["dan"] <= "2026-11-27"]
    listed = [e for e in evs if e["vrsta"] == "procedura"]
    own = lambda e: oblasti.follow_key(latin(e["naslov"]).replace("Predlog zakona", "Zakon", 1))  # noqa: E731
    changing = [e for e in listed if e["zakoni"] and e["zakoni"] != [own(e)]]
    per_law = collections.Counter(k for e in changing for k in e["zakoni"])
    assert (len(listed), len(changing), len(per_law), max(per_law.values())) == (173, 94, 67, 4)
    days = {k: len({e["dan"] for e in evs if k in e["zakoni"]}) for k in per_law}
    assert max(days.values()) == 11 and days["zakon-o-porezu-na-dohodak-gradjana"] == 5
    after = collections.Counter(collections.Counter(e["predlog"] for e in evs if e["vrsta"] != "procedura").values())
    assert set(after) == {1, 2, 3}
    assert len({e["id"] for e in evs}) == len(evs)


def _store(root, conv, **files):
    (root / conv / "votes").mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (root / conv / name.replace("__", "/")).write_text(json.dumps(data), encoding="utf-8")


def _bill(name, last, fetched):
    return {"fetched": fetched, "bills": {f"{name}.pdf": {
        "title": f"Predlog zakona o izmenama Zakona o {name}", "submitted": "2026-11-30", "proposer": "Vlada",
        "first_seen": "2026-12-01", "last_seen": last, "areas": []}}}


def test_no_longer_listed_once_missing_a_whole_day(tmp_path):
    gone = lambda: [e for e in oblasti.events(tmp_path, "15", "15") if e["vrsta"] == "nije_na_spisku"]  # noqa: E731
    _store(tmp_path, "15", **{"laws.json": {"laws": {}}, "procedure.json": _bill("radu", "2026-12-04", "2026-12-05")})
    assert gone() == []  # gone since this morning: it may have passed, its roll calls not read yet
    _store(tmp_path, "15", **{"procedure.json": _bill("radu", "2026-12-04", "2026-12-06")})
    e, = gone()
    assert (e["dan"], e["poznato"], e["zakoni"], e["oblasti"]) == ("2026-12-04", "2026-12-06", ["zakon-o-radu"], [])
    # Voted on as a whole under its name: not told as gone, whatever the count.
    _store(tmp_path, "15", **{"votes__1.json": {"title": "S", "votes": {"u#0": {
        "item": "1. Предлог закона о изменама Закона о раду у целини", "kind": oblasti.WHOLE, "when": "2026-12-04T12:00",
        "counts": {"za": 100, "protiv": 3, "uzdrzan": 1}, "rows": []}}}})
    assert gone() == []


def test_published_in_the_gazette_and_the_keys_of_a_bill(tmp_path):
    _store(tmp_path, "15", **{"procedure.json": _bill("radu", "2026-12-10", "2026-12-10"), "laws.json": {"laws": {
        "z.pdf": {"title": "Zakon o izmenama Zakona o radu", "bill_title": "Predlog zakona o izmenama Zakona o radu",
                  "bill_pdf": "radu.pdf", "passed": "2026-12-10", "gazette": "101/26", "areas": []}}}})
    evs = oblasti.events(tmp_path, "15", "15")
    assert [e["vrsta"] for e in evs if e["predlog"] == "radu.pdf"] == ["procedura", "usvojen", "objavljen"]
    out = oblasti.published(evs, today=dt.date(2026, 12, 12), laws={"radu.pdf": ("zakon/zakon-o-izmenama-zakona-o-radu", "Rad")},
                            bills={"radu.pdf": "predlog/zakon-o-izmenama-zakona-o-radu"}, latin=latin, cyr=cyr)
    pub, = [e for e in out["dogadjaji"] if e["vrsta"] == "objavljen"]
    assert (pub["glasnik"], pub["naslov"], pub["predlog"], pub["zakoni"]) == (
        "101/26", "Rad", "zakon-o-izmenama-zakona-o-radu", ["zakon-o-radu"])
    assert out["predlozi"]["zakon-o-izmenama-zakona-o-radu"] == {
        "zakoni": [["zakon-o-radu", "Zakon o radu", "Закон о раду"]], "usvojen": "2026-12-10"}
    # An area's follower is told none of the new kinds: in the file they have no area.
    assert all(e["oblasti"] == [] for e in out["dogadjaji"] if e["vrsta"] not in oblasti.AREA_KINDS)
    assert oblasti.mail_days(evs, None, "2026-12-01", "2026-12-31")["mejlova"] == 0


def test_the_bills_that_wait_by_their_key():
    rows = [{"slug": "zakon-o-izmenama-zakona-o-radu", "title": "Predlog zakona o izmenama Zakona o radu"}]
    assert oblasti.bills_followable(rows, latin=latin, cyr=cyr) == {
        "zakon-o-izmenama-zakona-o-radu": ["Predlog zakona o izmenama Zakona o radu", "Предлог закона о изменама Закона о раду"]}
