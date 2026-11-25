"""A break known from the chair's words and the broadcast's graphic (state.Tracker.screen, grafika.py; 25 Nov 2026)."""
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "live"))

from PIL import Image  # noqa: E402

from uzivo import dnevnik, grafika, page, state_base, steps  # noqa: E402
from uzivo.names import Person  # noqa: E402
from uzivo.state import UNKNOWN, Tracker  # noqa: E402

TZ = ZoneInfo("Europe/Belgrade")
UP, DOWN = 0.36, 0.02
MP = Person("a", "Petrović Petar", "petrovic-petar", "Lista")


def at(clock, day=24):
    h, m, s = (int(x) for x in clock.split(":"))
    return int(datetime(2026, 11, day, h, m, s, tzinfo=TZ).timestamp())


def sitting(day, began):
    """A tracker in a broadcast of that day, with a speech ten seconds long at its beginning."""
    t = Tracker(None, "Europe/Belgrade")
    for k in range(3):
        t.observe(MP, "Lista", now=at(began, day) + 5 * k)
    t._close()
    t.status = UNKNOWN
    return t


def run(t, day, first, last, up):
    """Frames each five seconds from `first` to `last`, the graphic up in the stretches `up`; when a break was put."""
    for now in range(at(first, day), at(last, day), 5):
        t.screen(UP if any(at(a, day) <= now < at(b, day) for a, b in up) else DOWN, now)
        if any(e["izvor"] == "slika" for e in t.events):
            return datetime.fromtimestamp(now, TZ).strftime("%H:%M:%S")
    return ""


def test_the_graphic_is_told_by_its_blue():
    fx = ROOT / "tests" / "fixtures"
    # the frame in which an MP was read from "noise" on 24 Nov 2026, 11:10: the graphic, so not read for a caption
    assert grafika.blue(Image.open(fx / "prenos-grafika-2026-11-24-1110.jpg")) > state_base.GRAPHIC + 0.08
    assert grafika.blue(Image.open(fx / "prenos-sala-2026-11-24-1007.jpg")) < 0.05
    assert grafika.blue(Image.new("RGB", (854, 480), (20, 30, 160))) == 1 and grafika.blue(Image.new("RGB", (1280, 720), "white")) == 0


# the four breaks of 24 and 25 Nov: the chair's words (the piece's second, and when written down, some 40 s later), the graphic
BREAKS = [
    (24, "10:07:29", "S obzirom da još uvek nisu spremni materijali, proglašam pauzu od jednog sata", [("10:12:34", "11:22:42")], "10:12:45"),
    (24, "14:10:57", "Proglašavam pauzu do 15 sati i 10 minuta.", [("14:10:46", "15:11:05")], "14:11:40"),
    (24, "18:08:30", "Isključiću vas, molim vas. Ja ću sada da pozovem pauzu. Pauza deset minuta.", [("18:08:59", "18:23:39")], "18:09:15"),
    (25, "10:30:55", "Proglašavam pauzu od pet minuta.", [("10:38:54", "10:41:04")], "10:39:08"),
]


@pytest.mark.parametrize("day,words,text,up,known", BREAKS)
def test_the_breaks_of_24_and_25_november_are_known_with_the_graphic(day, words, text, up, known):
    t = sitting(day, "10:00:40" if day == 24 else "10:04:00")
    began, written = at(words, day), at(words, day) + 40
    clock = lambda x: datetime.fromtimestamp(x, TZ).strftime("%H:%M:%S")
    assert run(t, day, clock(began - 60), clock(written), up) == ""  # until the words are written down the graphic says nothing
    t.say(began, text, chair=True)
    got = run(t, day, clock(written), clock(at(up[0][0], day) + 60 if at(up[0][0], day) > written else written + 60), up)
    assert got and abs(at(got, day) - at(known, day)) <= 15, got
    e = next(e for e in t.events if e["izvor"] == "slika")
    assert e["vrsta"] == "Pauza" and e["t"] == began
    for _ in range(40):
        t.screen(UP, at(got, day) + 5)
    assert sum(e["izvor"] == "slika" for e in t.events) == 1  # once


def test_the_graphic_by_itself_is_no_break():
    for day, began, up in ((24, "10:00:40", ("19:28:47", "19:30:30")), (25, "10:04:00", ("11:59:42", "12:01:22"))):
        t = sitting(day, began)  # the day's end: no break declared in the quarter of an hour before
        t.say(at("10:30:55", day), "Proglašavam pauzu od pet minuta.", chair=True)
        assert run(t, day, up[0][:6] + "00", up[1], [up]) == ""
    for day, up in ((24, ("09:55:35", "10:00:24")), (25, ("09:51:12", "10:03:20"))):  # before a sitting
        assert run(Tracker(None, "Europe/Belgrade"), day, up[0], up[1], [up]) == ""


def test_a_break_with_no_graphic_stays_as_it_was():
    """19 Nov 2026, 16:32, 18:06 and 23:30: the hall was shown throughout."""
    for words, text in (("16:32:01", "Pauza pet minuta."), ("18:06:34", "Proglašavam pauzu od deset minuta."), ("23:30:32", "deset minuta pauza")):
        t = sitting(19, "10:05:00")
        t.say(at(words, 19), text, chair=True)
        assert run(t, 19, words, words[:2] + ":59:00", []) == ""


def test_not_when_somebody_speaks_or_the_sitting_has_gone_on():
    words = "14:10:57"
    for how in ("speaking", "spoke", "went on", "old", "two frames", "gap"):
        t = sitting(24, "14:00:00")
        t.say(at(words), "Proglašavam pauzu do 15 sati i 10 minuta.", chair=True)
        up, last = [("14:12:00", "14:20:00")], "14:14:00"
        if how in ("speaking", "spoke"):
            for k in range(8):
                t.observe(MP, "Lista", now=at("14:11:35") + 5 * k)
            if how == "spoke":
                t._close()
                t.status = UNKNOWN
        if how == "went on":
            t.note(at("14:12:30"), "Tačka dnevnog reda", "Prelazimo na tačku 6.", "prepis")
            up = [("14:13:00", "14:20:00")]
        if how == "old":
            up, last = [("14:26:30", "14:40:00")], "14:30:00"
        if how == "two frames":
            up = [("14:12:00", "14:12:10")]
        if how == "gap":  # a frame each minute is not a row
            for k in range(6):
                t.screen(UP, at("14:12:00") + 60 * k)
            assert not any(e["izvor"] == "slika" for e in t.events)
            continue
        assert run(t, 24, "14:11:40", last, up) == "", how


def snapshot(events, now, **more):
    return {"stanje": "nepoznato", "provereno": now, "sada": None, "sazvano": None, "bez_potpisa": None, "ranije": False, "dan": "2026-11-24",
            "danas": [], "dnevni_red": None, "sazetak": None, "hronika": events, **more}


def test_it_is_a_step_at_once_and_gives_way_to_the_same_break_heard():
    b = at("14:10:57")
    seen = {"t": b, "vrsta": "Pauza", "tekst": "Proglašavam pauzu do 15 sati i 10 minuta.", "izvor": "slika", "url": ""}
    heard = {"t": b, "vrsta": "Pauza", "tekst": seen["tekst"], "izvor": "model", "url": "", "vise": {"do": "15 sati i 10 minuta"}}
    other = {"t": b - 3000, "vrsta": "Izbor", "tekst": "Petrović je izabran.", "izvor": "model", "url": "", "vise": {"ko": "Petrović"}}
    shown = lambda ev, after: [(e["naslov"], e["opis"]) for e in steps.steps_shown(snapshot(ev, b + after)) if e["naslov"] == "Pauza"]
    for before in ([], [other]):  # the rules' steps, and the model's
        assert shown([*before, seen], 60) == [("Pauza", "")]
    assert shown([heard], 60) == []  # heard alone waits four minutes
    assert shown([heard, seen], 60) == [("Pauza", "")]
    assert shown([seen, heard], 900) == shown([heard, seen], 900) == [("Pauza", "15 sati i 10 minuta")]
    again = {**seen, "t": b + 700, "tekst": "Proglašavam pauzu od deset minuta."}  # another break
    assert len(shown([heard, seen, again], 1700)) == 2
    assert shown([heard, seen, {**heard, "t": b + 700, "vise": {"do": "15 sati i 10 minuta"}}, again], 1700) == [("Pauza", ""), ("Pauza", "15 sati i 10 minuta")]


def test_the_tile_says_pauza_while_a_break_is_known(monkeypatch):
    b = at("14:10:57")
    monkeypatch.setattr(page, "_now", lambda: datetime.fromtimestamp(b + 60, TZ))
    seen = {"t": b, "vrsta": "Pauza", "tekst": "Proglašavam pauzu do 15 sati i 10 minuta.", "izvor": "slika", "url": ""}
    agenda = {"naslov": "S", "url": "", "tacke": [{"n": 2, "tekst": "Druga", "stanje": "u_toku", "izvor": "prepis", "kada": "", "sta": ""}]}
    for cyr, word, live in ((False, "Pauza", "Uživo"), (True, "Пауза", "Уживо")):
        for a in (None, agenda):
            top = lambda s: page._status({**s, "dnevni_red": a}, cyr=cyr)  # noqa: B023
            assert word in top(snapshot([seen], b + 60)) and live not in top(snapshot([seen], b + 60))
            turn = {"ime": "Petrović Petar", "od": b + 600, "do": b + 700, "sekundi": 100, "grupa": "", "adresa": "", "uloga": "", "lista": ""}
            for s in (snapshot([], b + 60), snapshot([seen], b + 800, danas=[turn]), snapshot([seen], b + 800, stanje="govori", sada=turn)):
                assert live in top(s) and word not in top(s)
            assert word not in top(snapshot([seen], b + 60, stanje="nema_prenosa"))
    html = page.fragment(snapshot([seen], b + 60), cyr=False, site="https://zailiprotiv.rs/", tz=TZ)
    assert 'data-gore="pauza"' in html and 'data-nastavak="1"' in html  # the mail's row and the bell come with it


def test_what_was_seen_is_kept_for_going_through_the_day_again(tmp_path):
    t = sitting(24, "14:00:00")
    dnevnik.attach(t, tmp_path, clock=lambda: at("14:12:00"))
    t.screen(0.36, at("14:12:00"))
    row = dnevnik.lines(next(tmp_path.glob("*.jsonl")))[-1]
    assert row["m"] == "screen" and row["a"][0] == 0.36
