"""Following an area of laws by mail, the live service's sender (live/uzivo/prati.py), 27 Nov 2026."""
import datetime as dt
import json
from datetime import date, datetime, timedelta

from test_prati import NEXT, TZ, prati, row, sealed, service  # noqa: F401 — the fixture

ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
SAOBRACAJ, RAD = "Saobraćaj", "Rad, zapošljavanje i socijalno osiguranje"
POINTS = {"13": [SAOBRACAJ, "Саобраћај"], "8": [RAD, "Рад, запошљавање и социјално осигурање"]}


def area(slug, name, rid, od="2026-11-20"):
    return {**sealed(slug, name, rid, od), "sta": f"o|{slug}|{name}   "}


def event(i, kind, day, areas, title, **more):
    return {"id": f"{kind}:{i}", "vrsta": kind, "dan": day, "oblasti": areas, "naslov": title,
            "naslov_cir": title, "strana": f"predlog/{i}", **more}


def test_a_day_with_nothing_new_sends_nothing_and_asks_no_one(service, monkeypatch):
    """The maintainer: "Šta ako ništa nema update?" (27 Nov 2026): no speech and no event, no mail, the counter not asked."""
    service.days.kept = {}
    service.people = [row("r", "c@primer.rs", area("saobracaj", SAOBRACAJ, "o1"))]
    asked = []
    real = prati.pretplata._call
    monkeypatch.setattr(prati.pretplata, "_call", lambda path, body=None: asked.append(path) or real(path, body))
    monkeypatch.setattr(prati.config, "FOLLOW_ALONE", True)
    service.events = {"oblasti": POINTS, "dogadjaji": [event(1, "procedura", "2026-11-10", [13], "Predlog zakona o putevima")]}
    assert not service.follow.step(NEXT) and service.sent == [] and asked == []  # only an event older than three days


def test_an_area_is_told_once_in_the_same_mail_as_an_mp_and_ended_in_it(service, monkeypatch):
    monkeypatch.setattr(prati.config, "FOLLOW_ALONE", True)
    service.people = [row("r", "c@primer.rs", sealed("anic-ana", "Ana Anić", "p1"), area("saobracaj", SAOBRACAJ, "o1"),
                          area("rad-zaposljavanje-i-socijalno-osiguranje", RAD, "o2"))]
    service.events = {"oblasti": POINTS, "dogadjaji": [
        event(1, "usvojen", "2026-11-24", [8, 13], "Putevi: naplata", za=140, protiv=3, uzdrzan=1, strana="zakon/putevi"),
        event(2, "procedura", "2026-11-24", [13], "Predlog zakona o železnici", predlagac="Vlada Republike Srbije", poznato="2026-11-25"),
        event(3, "dnevni_red", "2026-11-26", [8], "Predlog zakona o radu", sednica="Druga sednica", pocinje="2026-11-26T10:00"),
        event(4, "procedura", "2026-11-24", [5], "Predlog zakona o strancima")]}  # an area not followed
    assert service.follow.step(NEXT)
    [m] = service.sent
    h, t = m["html"], m["text"]
    assert m["subject"] == "Ono što pratiš: utorak, 24. novembar"  # no name in a subject
    assert h.index(">Ana Anić<") < h.index(f">{RAD}<") < h.index(f">{SAOBRACAJ}<")  # MPs, then areas by their point
    assert t.count("Putevi: naplata") == 1 and "i u oblasti: Saobraćaj" in t  # once, under the first area by point
    assert "za 140 · protiv 3 · uzdržan 1" in t and "https://zailiprotiv.rs/zakon/putevi" in t
    assert "podneo: Vlada Republike Srbije · utorak, 24. novembar" in t and "sednica počinje: četvrtak, 26. novembar u 10 · Druga sednica" in t
    assert "strancima" not in t and "Oblast je tačka člana 97. Ustava na koju se predlagač poziva." in t
    assert f"Oblast: {SAOBRACAJ} · Prestani da pratiš: https://glasovi.zailiprotiv.rs/m/prati/kraj?i=o1&k=ko1" in t
    kept = json.dumps(service.state())
    assert "@" not in kept and "saobracaj" not in kept and "putevi" not in kept  # by row and number only
    assert not service.follow.step(NEXT)  # one a day
    later = NEXT + timedelta(days=1)
    service.days.kept = {}
    assert not service.follow.step(later) and len(service.sent) == 1  # told once: nothing new the next day
    service.events["dogadjaji"].append(event(5, "procedura", "2026-11-25", [13], "Predlog zakona o lukama", poznato="2026-11-25"))
    assert service.follow.step(later)
    assert "lukama" in service.sent[-1]["text"] and "železnici" not in service.sent[-1]["text"]


def test_an_event_before_the_following_or_beyond_three_days_is_not_told(service, monkeypatch):
    monkeypatch.setattr(prati.config, "FOLLOW_ALONE", True)
    service.days.kept = {}
    service.people = [row("r", "c@primer.rs", area("saobracaj", SAOBRACAJ, "o1", od="2026-11-24"))]
    service.events = {"oblasti": POINTS, "dogadjaji": [event(1, "procedura", "2026-11-23", [13], "Predlog zakona o starom"),
                                                       event(2, "procedura", "2026-11-24", [13], "Predlog zakona o novom")]}
    assert service.follow.step(NEXT)
    assert "novom" in service.sent[0]["text"] and "starom" not in service.sent[0]["text"]


def test_more_than_ten_of_a_kind_send_the_rest_to_the_areas_page(service, monkeypatch):
    monkeypatch.setattr(prati.config, "FOLLOW_ALONE", True)
    service.days.kept = {}
    service.people = [row("r", "c@primer.rs", area("saobracaj", SAOBRACAJ, "o1"), cir=True)]
    service.events = {"oblasti": POINTS, "dogadjaji": [event(i, "usvojen", "2026-11-24", [13], f"Zakon {i:02d}", za=130, protiv=0, uzdrzan=0)
                                                       for i in range(16)]}
    assert service.follow.step(NEXT)
    t = service.sent[0]["text"]
    assert "УСВОЈЕНО 16" in t and t.count("Закон ") == 10 and "још 6 на страни области: https://zailiprotiv.rs/cir/oblast/saobracaj" in t


def test_a_year_of_real_events_gives_the_proposals_mails(tmp_path, monkeypatch):
    """The site's events of a year of the Fourteenth (oblasti.py over data/), each first seen the day it happened, told
    by the sender's own rules each morning to a follower of every area: the mails per area the proposal counted."""
    import threading
    from zailiprotiv import oblasti
    from zailiprotiv.translit import latin
    from zailiprotiv.cyrillic import cyr
    # Each known on its own day, as the proposal counted: the store of bills in procedure began on 13 Nov 2026, and the
    # day it first listed the Fourteenth's 91 bills is no day they entered.
    evs = [{k: v for k, v in e.items() if k != "poznato"} for e in oblasti.events(ROOT / "data", "14", "15")]
    names = {n: latin(v) for n, v in oblasti.kinds.AREAS.items()}
    follow = prati.Following(None, prati.pretplata.Mailer(tmp_path, lambda *a, **k: None), threading.Event())
    readers = [prati.Follower(f"r{n}", "x", False, "", "#", "#", (prati.Followed(f"o{n}", names[n], date(2025, 1, 1), ("#",), "o"),))
               for n in names]
    mails = {n: 0 for n in names}
    day = date(2025, 11, 29)
    while day <= date(2026, 11, 28):
        known = [e for e in evs if e["dan"] < day.isoformat()]  # by the morning after
        follow.fetch = lambda: oblasti.published(known, today=day, laws={}, bills={}, latin=latin, cyr=cyr)
        events = follow.events(day)
        state = follow._state()
        ready = [(p, follow.told(p, {}, events, state, day)) for p in readers]
        ready = [(p, t) for p, t in ready if t]
        if ready:
            follow.begin(ready)
            for p, _ in ready:
                mails[int(p.id[1:])] += 1
        day += timedelta(days=1)
    assert mails == {1: 4, 2: 13, 3: 1, 4: 3, 5: 1, 6: 15, 7: 1, 8: 14, 9: 6, 10: 16, 11: 6, 12: 4, 13: 9, 14: 0,
                     15: 14, 16: 16, 17: 16}
