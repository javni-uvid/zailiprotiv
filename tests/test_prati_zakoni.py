"""Following one bill or one law by mail, the live service's sender (live/uzivo/prati.py), 28 Nov 2026."""
import collections
import json
import threading
from datetime import date, timedelta

from test_prati import NEXT, prati, row, sealed, service  # noqa: F401 — the fixture

ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
BILL, LAW = "zakon-o-izmenama-zakona-o-radu", "zakon-o-radu"


def follows(kind, key, name, rid, od="2026-11-20"):
    return {**sealed(key, name, rid, od), "sta": f"{kind}|{key}|{name}   "}


def event(i, kind, day, title, bill="", laws=(LAW,), **more):
    return {"id": f"{kind}:{i}", "vrsta": kind, "dan": day, "oblasti": [], "naslov": title, "naslov_cir": title,
            "strana": f"predlog/{bill or i}", "predlog": bill, "zakoni": list(laws), **more}


def bills(passed=""):
    return {BILL: {"zakoni": [[LAW, "Zakon o radu", "Закон о раду"]], "usvojen": passed}}


def test_a_day_with_nothing_new_sends_nothing_and_asks_no_one(service, monkeypatch):
    """No event of the bill or the law in three days: no mail, and the counter is not asked."""
    service.days.kept = {}
    service.people = [row("r", "c@primer.rs", follows("z", LAW, "Zakon o radu", "z1"))]
    asked = []
    real = prati.pretplata._call
    monkeypatch.setattr(prati.pretplata, "_call", lambda path, body=None: asked.append(path) or real(path, body))
    monkeypatch.setattr(prati.config, "FOLLOW_ALONE", True)
    service.events = {"oblasti": {}, "predlozi": bills(), "dogadjaji": [
        event(1, "procedura", "2026-11-10", "Predlog zakona o izmenama Zakona o radu", BILL, predlagac="Vlada")]}
    assert not service.follow.step(NEXT) and service.sent == [] and asked == []


def test_a_bill_is_told_its_steps_and_then_goes_on_as_its_law(service, monkeypatch):
    monkeypatch.setattr(prati.config, "FOLLOW_ALONE", True)
    service.days.kept = {}
    service.people = [row("r", "c@primer.rs", follows("b", BILL, "Predlog zakona o izmenama Zakona o radu", "b1"))]
    title = "Predlog zakona o izmenama Zakona o radu"
    service.events = {"oblasti": {}, "predlozi": bills(), "dogadjaji": [
        event(1, "dnevni_red", "2026-11-26", title, BILL, sednica="Druga sednica", pocinje="2026-11-26T10:00"),
        event(2, "procedura", "2026-11-24", "Predlog zakona o izmeni Zakona o radu", "drugi", predlagac="Poslanička grupa X")]}
    assert service.follow.step(NEXT)
    t = service.sent[0]["text"]
    assert "NA DNEVNOM REDU\n  sednica počinje: četvrtak, 26. novembar u 10 · Druga sednica" in t
    assert "izmeni Zakona o radu" not in t  # another bill of the law: not until this one passed
    assert f"Predlog: {title} · Prestani da pratiš: https://glasovi.zailiprotiv.rs/m/prati/kraj?i=b1&k=kb1" in t
    assert "Iz spiska zakona u proceduri, dnevnog reda, poimeničnih glasanja i spiska donetih zakona" in t
    kept = json.dumps(service.state())
    assert "@" not in kept and "radu" not in kept  # by row and number only
    # Passed: told with the note, under the law's short name.
    day = NEXT + timedelta(days=1)
    service.events["predlozi"] = bills("2026-11-25")
    service.events["dogadjaji"].append(event(3, "usvojen", "2026-11-25", "Rad: novi odmori", BILL, za=140, protiv=3, uzdrzan=1,
                                             strana="zakon/rad"))
    assert service.follow.step(day)
    t = service.sent[-1]["text"]
    assert t.count("Rad: novi odmori") == 1 and "USVOJEN\n  sreda, 25. novembar · za 140 · protiv 3 · uzdržan 1" in t
    assert "Dalje pratiš zakon: javljamo kad bude predložena njegova izmena." in t and "Druga sednica" not in t
    # In the Gazette days later, and a bill changing the law after it passed: under the law's name.
    day += timedelta(days=6)
    service.events["dogadjaji"] += [event(4, "objavljen", "2026-11-25", "Rad: novi odmori", BILL, glasnik="101/26", strana="zakon/rad"),
                                    event(5, "procedura", "2026-12-01", "Predlog zakona o dopuni Zakona o radu", "treci",
                                          predlagac="Vlada", poznato="2026-12-01")]
    assert service.follow.step(day)
    t = service.sent[-1]["text"]
    assert "OBJAVLJEN\n  u „Službenom glasniku RS“ br. 101/26" in t
    assert "PREDLOŽENA IZMENA\n  Predlog zakona o dopuni Zakona o radu · podneo: Vlada · utorak, 1. decembar" in t
    assert "Dalje pratiš zakon" not in t


def test_a_law_is_told_every_bill_that_names_it_each_once(service, monkeypatch):
    monkeypatch.setattr(prati.config, "FOLLOW_ALONE", True)
    service.days.kept = {}
    service.people = [row("r", "c@primer.rs", follows("z", LAW, "Zakon o radu", "z1"), follows("b", BILL, "Predlog", "b1"),
                          cir=False)]
    service.events = {"oblasti": {}, "predlozi": bills(), "dogadjaji": [
        event(1, "procedura", "2026-11-24", "Predlog zakona o izmenama Zakona o radu", BILL, predlagac="Vlada", poznato="2026-11-24"),
        event(2, "procedura", "2026-11-24", "Predlog zakona o izmeni Zakona o radu", "drugi", predlagac="Grupa X", poznato="2026-11-24"),
        event(3, "nije_na_spisku", "2026-11-23", "Predlog zakona o dopuni Zakona o radu", "treci", poznato="2026-11-25"),
        event(4, "procedura", "2026-11-24", "Predlog zakona o gasu", "gas", laws=("zakon-o-gasu",))]}
    assert service.follow.step(NEXT)
    t = service.sent[0]["text"]
    # The followed bill's own listing came before its following (20 Nov): it goes under the law, and once.
    assert "PREDLOŽENE IZMENE 2" in t and t.count("Predlog zakona o izmenama Zakona o radu ·") == 1
    assert ("VIŠE NIJE NA SPISKU\n  Predlog zakona o dopuni Zakona o radu · povučen je, ili mu je postupak prestao; "
            "Skupština ne navodi razlog · poslednji put na spisku: ponedeljak, 23. novembar") in t
    assert "gasu" not in t and "Zakon: Zakon o radu · Prestani da pratiš" in t


def test_in_cyrillic():
    reader = prati.Follower("r", "x", True, "", "#", "#", (prati.Followed(LAW, "Zakon o radu", date(2026, 11, 1), ("#",), "z"),))
    told = prati.law_news(reader, [{**event(1, "procedura", "2026-11-24", "Predlog zakona o izmeni Zakona o radu", "x",
                                            predlagac="Vlada"), "seq": 1}], {}, 0, date(2026, 11, 25))
    t = prati.build(reader, prati.Told([], [], 1, told), date(2026, 11, 25)).text
    assert "ПРЕДЛОЖЕНА ИЗМЕНА" in t and "Закон: Закон о раду" in t and "Предлог закона о измени Закона о раду" in t


def test_a_year_of_real_events_for_who_follows_a_law_or_a_bill(tmp_path):
    """The site's events of a year of the Fourteenth (oblasti.py over data/), each known the day after it happened, told
    by the sender's own rules each morning to a follower of every law a bill changed and of every bill listed in the
    year (from the day it was listed): a mail on each day with an event of theirs, the same as counted from the events
    alone, at most one a day, and an event never twice."""
    from zailiprotiv import oblasti
    from zailiprotiv.cyrillic import cyr
    from zailiprotiv.translit import latin
    evs = [{k: v for k, v in e.items() if k != "poznato"} for e in oblasti.events(ROOT / "data", "14", "15")]
    year = [e for e in evs if "2025-11-28" <= e["dan"] <= "2026-11-27"]
    pages = {pdf: f"predlog/b{i}" for i, pdf in enumerate(sorted({e["predlog"] for e in evs}))}
    key = {pdf: oblasti.follow_key(p.removeprefix("predlog/")) for pdf, p in pages.items()}
    laws = sorted({k for e in year if e["vrsta"] == "procedura" for k in e["zakoni"]})
    listed = {e["predlog"]: date.fromisoformat(e["dan"]) for e in year if e["vrsta"] == "procedura"}
    follow = prati.Following(None, prati.pretplata.Mailer(tmp_path, lambda *a, **k: None), threading.Event())
    start = date(2025, 11, 28)
    readers = [prati.Follower(f"z{k}", "x", False, "", "#", "#", (prati.Followed(k, k, start, ("#",), "z"),)) for k in laws] + \
              [prati.Follower(f"b{key[p]}", "x", False, "", "#", "#", (prati.Followed(key[p], p, d, ("#",), "b"),))
               for p, d in listed.items()]
    mails, told = collections.Counter(), collections.Counter()
    day = start + timedelta(days=1)
    while day <= date(2026, 11, 28):
        known = [e for e in evs if e["dan"] < day.isoformat()]
        follow.fetch = lambda: oblasti.published(known, today=day, laws={}, bills=pages, latin=latin, cyr=cyr)
        events = follow.events(day)
        state = follow._state()
        ready = [(p, t) for p in readers if (t := follow.told(p, {}, events, state, day))]
        if ready:
            follow.begin(ready)
            for p, t in ready:
                mails[p.id] += 1
                for _, xs in t.laws:
                    told.update(f"{p.id}|{x['id']}" for x in xs)
        day += timedelta(days=1)
    assert max(told.values()) == 1  # an event never twice
    # Counted from the events alone: a law's, the days with an event of a bill naming it; a bill's, the days with an
    # event of its own after it was listed, and once passed, of a bill naming its laws.
    passed = {e["predlog"]: e["dan"] for e in evs if e["vrsta"] == "usvojen"}
    expected = {f"z{k}": len({e["dan"] for e in year if k in e["zakoni"] and e["dan"] >= "2025-11-28"}) for k in laws}
    for p, d in listed.items():
        mine = set(oblasti.follow_key(n) for n in oblasti.named(next(e["naslov"] for e in evs if e["predlog"] == p)))
        days = {e["dan"] for e in year if e["dan"] >= d.isoformat() and (
            (e["predlog"] == p and e["vrsta"] != "procedura") or
            (p in passed and e["predlog"] != p and mine & set(e["zakoni"]) and e["dan"] >= passed[p]))}
        expected[f"b{key[p]}"] = len(days)
    assert {k: v for k, v in mails.items()} == {k: v for k, v in expected.items() if v}
    assert max(mails[f"z{k}"] for k in laws) == 11 and len(laws) == 144  # 67 changed, the rest new laws


def test_the_maintainers_preview_with_only_a_bills_event(service):
    """No speech and no event of an area: the morning's preview shows a bill's mail, and the rest go on his click."""
    service.days.kept = {}
    service.people = [row("r", "c@primer.rs", follows("b", BILL, "Predlog zakona o izmenama Zakona o radu", "b1"))]
    service.events = {"oblasti": {}, "predlozi": bills(), "dogadjaji": [
        event(1, "dnevni_red", "2026-11-26", "Predlog zakona o izmenama Zakona o radu", BILL, sednica="Druga sednica",
              pocinje="2026-11-26T10:00")]}
    assert service.follow.step(NEXT)
    [m] = service.sent
    assert m["to"] == "urednik@primer.rs" and "Spremno: 1" in m["html"] and "kod predloga i zakona: 1" in m["html"]
    assert "Druga sednica" in m["html"] and "c@primer.rs" not in m["html"] + m["text"]
    assert service.click() == ("ok", 1) and service.sent[-1]["to"] == "c@primer.rs"
