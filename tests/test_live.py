"""live/uzivo: who is speaking now, read from the broadcast's caption. Only the parts with no outside packages
(names, the caption's lines, the turns, the page); OCR and the stream are tried on the broadcast itself."""
import json
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "live"))

from uzivo import config  # noqa: E402
from uzivo.caption import differs, read, tidy, who  # noqa: E402
from uzivo.names import Roster, cyrillic, given_first, latin, normalize  # noqa: E402
from uzivo.page import fragment, page  # noqa: E402
from uzivo.state import NO_STREAM, SPEAKING, UNKNOWN, Tracker  # noqa: E402

ROSTER = Roster.from_json(json.dumps({"mps": [
    {"n": "Petrović Petar", "s": "petrovic-petar", "g": "Lista za primer"},
    {"n": "Petrović Petra", "s": "petrovic-petra", "g": "Druga lista"},
    {"n": "Jovanović Marko", "s": "jovanovic-marko", "g": "Lista za primer"},
    {"n": "Marković Marko", "s": "markovic-marko", "g": "Treća lista"},
    {"n": "Đorđević Ljiljana", "s": "djordjevic-ljiljana", "g": "Treća lista"},
]}))
TZ = ZoneInfo("Europe/Belgrade")


def w(text, conf=95):
    return [(x, conf) for x in text.split()]


def test_scripts():
    assert latin("Љиљана Ђорђевић") == "Ljiljana Đorđević"
    assert cyrillic("Ljiljana Đorđević") == "Љиљана Ђорђевић"
    assert cyrillic("Džajić Nikola") == "Џајић Никола"
    assert normalize("Петровић") == normalize("Petrović") == normalize("PETROVIC") == "petrovic"
    assert given_first("Jovanović Marko") == "Marko Jovanović"


def test_match_tolerates_ocr_and_word_order():
    assert ROSTER.match("Петар Петровнћ", 0.8).slug == "petrovic-petar"    # one letter misread
    assert ROSTER.match("PETROVIĆ Petar", 0.8).slug == "petrovic-petar"    # either order
    assert ROSTER.match("ла Марко Јовановић", 0.8).slug == "jovanovic-marko"  # a bit of noise beside the name
    assert ROSTER.match("Ljiljana Đorđević", 0.8).slug == "djordjevic-ljiljana"


def test_match_refuses_half_names_and_guesses():
    assert ROSTER.match("Петар", 0.8) is None              # a given name alone is nobody
    assert ROSTER.match("Марко Николић", 0.8) is None      # not on the list
    assert ROSTER.match("Петр Петровић", 0.95) is None     # not close enough at a strict threshold


def test_name_line_is_above_the_list_line():
    """A list's name often holds its leader's name: the speaker is on the line above it."""
    cap = read([w("~ ."), w("Марко Јовановић"), w("Петар Петровић - Листа за пример")], 85)
    assert cap.name_line == "Марко Јовановић"
    assert who(cap, ROSTER, 0.8).slug == "jovanovic-marko"
    cap = read([w("Петар Петровић"), w("Петар Петровић - Листа за пример")], 85)
    assert who(cap, ROSTER, 0.8).slug == "petrovic-petar"


def test_name_not_on_the_list():
    """Shown only when read cleanly (a minister, a guest, a new MP), never from a half-read line."""
    cap = read([w("Нина Николић"), w("министар финансија")], 85)
    p = who(cap, ROSTER, 0.8)
    assert p.name == "Nikolić Nina" and p.slug == ""
    assert cap.role_clean
    assert who(read([w("Нина Николић", 60), w("министар финансија")], 85), ROSTER, 0.8) is None
    assert who(read([w("ФУЈ ешандар 7 ВУЛИђ"), w("Листа")], 85), ROSTER, 0.8) is None
    assert who(read([w("| ; ~"), w("1 .")], 85), ROSTER, 0.8) is None


def test_turns(tmp_path):
    t = Tracker(str(tmp_path / "s.json"), "Europe/Belgrade")
    petar = ROSTER.match("Петар Петровић", 0.8)
    marko = ROSTER.match("Марко Јовановић", 0.8)
    now = 1794920000.0
    assert t.status == NO_STREAM
    t.observe(None, now=now)
    assert t.status == UNKNOWN
    t.observe(petar, now=now + 5)
    assert t.status == SPEAKING and t.snapshot()["sada"]["ime"] == "Petrović Petar"
    t.observe(None, now=now + 10)                       # a frame without a name: still Petar
    t.observe(petar, now=now + 15)
    t.observe(marko, now=now + 20)                      # another name: Petar's turn ends
    snap = t.snapshot()
    assert snap["sada"]["ime"] == "Jovanović Marko"
    assert [d["ime"] for d in snap["danas"]] == ["Petrović Petar"] and snap["danas"][0]["sekundi"] == 10
    t.observe(None, now=now + 20 + config.HOLD_SECONDS + 1)  # nothing read for a while: nobody known
    assert t.status == UNKNOWN and t.snapshot()["sada"] is None
    assert [d["ime"] for d in t.snapshot()["danas"]] == ["Petrović Petar"]  # Marko read once: not listed
    t.tick(now=now + 200)
    assert t.status == NO_STREAM
    kept = json.loads((tmp_path / "dani" / f"{t.day}.json").read_text(encoding="utf-8"))["turns"]  # across restarts
    assert [x["name"] for x in kept] == ["Petrović Petar", "Jovanović Marko"]
    again = Tracker(str(tmp_path / "s.json"), "Europe/Belgrade")
    again._load(t.day)
    assert [x["name"] for x in again.turns] == ["Petrović Petar", "Jovanović Marko"]


def test_a_days_record_says_where_each_turn_is_and_where_the_gaps_are(tmp_path):
    t = Tracker(str(tmp_path / "s.json"), "Europe/Belgrade")
    petar = ROSTER.match("Петар Петровић", 0.8)
    now = 1794920000.0
    for i in range(3):
        t.observe(petar, now=now + 5 * i, at={"video": "abc", "sq": 100 + i, "seg": 5.0})
    t.observe(None, now=now + 300, at={"video": "abc", "sq": 160, "seg": 5.0})  # after a gap: no frames for 285 s
    rec = t.record(t.day)
    assert rec["pokriveno"] == [{"od": int(now), "do": int(now + 10)}, {"od": int(now + 300), "do": int(now + 300)}]
    g = rec["govori"][0]
    assert (g["ime"], g["video"], g["sq_od"], g["sq_do"], g["segment"], g["okvira"]) == ("Petrović Petar", "abc", 100, 102, 5.0, 3)
    assert t.days_kept() == [t.day] and t.record("2001-01-01") is None


def test_a_name_not_on_the_list_needs_two_frames():
    t = Tracker(None, "Europe/Belgrade")
    nina = who(read([w("Нина Николић"), w("министар финансија")], 85), ROSTER, 0.8)
    now = 1794920000.0
    t.observe(nina, now=now)
    assert t.status == UNKNOWN                          # once could be noise
    t.observe(nina, now=now + 5)
    assert t.status == SPEAKING and t.snapshot()["sada"]["ime"] == "Nikolić Nina"


def test_same_speaker_after_a_short_break_is_one_turn():
    t = Tracker(None, "Europe/Belgrade")
    petar = ROSTER.match("Петар Петровић", 0.8)
    now = 1794920000.0
    t.observe(petar, now=now)
    t.observe(petar, now=now + 5)
    t.observe(None, now=now + 5 + config.HOLD_SECONDS + 1)
    t.observe(petar, now=now + 60)
    assert len(t.turns) == 1 and t.snapshot()["sada"]["sekundi"] == 60


def test_page_both_scripts():
    t = Tracker(None, "Europe/Belgrade")
    petar = ROSTER.match("Петар Петровић", 0.8)
    t.observe(petar, "Lista za primer", now=1794920000.0)
    snap = t.snapshot()
    lat = page(snap, cyr=False, site="https://zailiprotiv.rs/", tz=TZ, url="https://mikrofon.zailiprotiv.rs/")
    assert "Petar Petrović" in lat and 'href="https://zailiprotiv.rs/poslanik/petrovic-petar"' in lat
    assert "Ko sada govori u Skupštini" in lat and "Lista za primer" in lat
    cyr = page(snap, cyr=True, site="https://zailiprotiv.rs/", tz=TZ)
    assert "Петар Петровић" in cyr and "https://zailiprotiv.rs/cir/poslanik/petrovic-petar" in cyr
    assert "Ко сада говори у Скупштини" in cyr
    for html in (lat, cyr):  # nothing from elsewhere but links
        assert "<script src" not in html and "googleapis" not in html
    guest = Tracker(None, "Europe/Belgrade")
    odd = who(read([w("Нина <b>Николић")], 85), ROSTER, 0.8) or petar
    guest.observe(odd, now=1794920000.0)
    guest.observe(odd, now=1794920005.0)
    assert "<b>" not in fragment(guest.snapshot(), cyr=False, site="", tz=TZ)


def test_someone_else_unreadably_ends_the_turn():
    """Two frames naming someone else, even unreadably, end the current speaker's turn; a misread of the speaker's
    own name does not."""
    t = Tracker(None, "Europe/Belgrade")
    marko = ROSTER.match("Марко Јовановић", 0.8)
    now = 1794920000.0
    t.observe(marko, now=now)
    own = read([w("Марко Јоввновић", 60), w("Листа")], 85)          # his name, badly read: not someone else
    assert who(own, ROSTER, 0.95) is None and not differs(own, t.current(), 0.8)
    odd = read([w("Мина Николић", 60), w("министар финансија")], 85)  # someone not clearly read
    assert who(odd, ROSTER, 0.8) is None and differs(odd, t.current(), 0.8)
    t.observe(None, now=now + 5, other=True)
    assert t.status == SPEAKING                          # once is not enough
    t.observe(None, now=now + 10, other=True)
    assert t.status == UNKNOWN and t.snapshot()["sada"] is None


def test_tidy_keeps_the_dash_and_drops_specks():
    assert tidy('·" Петар Петровић - Листа за пример |') == "Petar Petrović - Lista za primer"
    assert tidy("~ Листа за пример.") == "Lista za primer"


def test_turns_link_to_the_recording_and_stay_until_the_next_sitting(tmp_path):
    from datetime import datetime
    from uzivo.names import Person, person_key
    path = tmp_path / "stanje.json"
    t = Tracker(str(path), tz="Europe/Belgrade")
    day1 = datetime(2026, 11, 18, 10, 0, tzinfo=TZ).timestamp()
    p = Person(person_key("Petrović Petar"), "Petrović Petar", "petrovic-petar", "PG A")
    for i in range(3):
        t.observe(p, now=day1 + 5 * i, at={"video": "abc", "sq": 120 + i, "seg": 5.0})
    t.tick(now=day1 + 200)
    snap = t.snapshot(now=day1 + 200)
    assert not snap["ranije"]
    assert snap["danas"][0]["snimak"] == 595 and snap["danas"][0]["video"] == "abc"  # (120 - 1) × 5 s
    html = fragment(snap, cyr=False, site="", tz=TZ)
    assert "youtube.com/watch?v=abc&amp;t=595s" in html and "snimak 9:55" in html
    # The next day, before anyone is read: the last sitting day's list, with its date.
    day2 = datetime(2026, 11, 19, 9, 0, tzinfo=TZ).timestamp()
    t2 = Tracker(str(path), tz="Europe/Belgrade")
    assert t.snapshot(now=day1 + 86400)["ranije"]  # past midnight, before any frame: no longer "today"
    t2.observe(None, now=day2)
    snap = t2.snapshot(now=day2)
    assert snap["dan"] == "2026-11-18" and [d["ime"] for d in snap["danas"]] == ["Petrović Petar"]
    assert "Poslednji dan sednice, 18. novembar 2026." in fragment(snap, cyr=False, site="", tz=TZ)
    # Someone read at the new sitting: today's list only.
    for i in range(2):
        t2.observe(Person(person_key("Nikolić Nina"), "Nikolić Nina", "nikolic-nina", "PG B"), now=day2 + 5 + 5 * i)
    assert [d["ime"] for d in t2.snapshot(now=day2 + 20)["danas"]] in ([], ["Nikolić Nina"])
    assert t2.snapshot(now=day2 + 20)["dan"] == "2026-11-19" and not t2.snapshot(now=day2 + 20)["ranije"]


def test_between_sittings_the_page_is_read_afresh(monkeypatch):
    from uzivo import stream
    seen = []
    monkeypatch.setattr(config, "YOUTUBE_URL", "https://www.youtube.com/watch?v=old")
    monkeypatch.setattr(config, "SOURCE_PAGE", "https://example.org/page")
    monkeypatch.setattr(stream, "_youtube_url_from_page", lambda page: "https://www.youtube.com/watch?v=new")

    def resolve(url):
        seen.append(url)
        raise stream.NotLive(url)
    monkeypatch.setattr(stream, "_resolve_youtube", resolve)
    try:
        stream.resolve_input()
    except stream.NotLive:
        pass
    assert seen == ["https://www.youtube.com/watch?v=new"]  # the page's stream of the day, not the one in .env


def test_a_day_kept_only_in_the_old_state_file_gets_its_own(tmp_path):
    from datetime import datetime
    day = datetime(2026, 11, 17, 17, 38, tzinfo=TZ).timestamp()
    turn = {"key": "a", "name": "Petrović Petar", "slug": "petrovic-petar", "group": "PG A", "role": "",
            "start": day, "seen": day + 600, "n": 120}
    (tmp_path / "stanje.json").write_text(json.dumps({"turns": [turn]}), encoding="utf-8")
    t = Tracker(str(tmp_path / "stanje.json"), tz="Europe/Belgrade")
    assert (tmp_path / "dani" / "2026-11-17.json").exists()
    snap = t.snapshot(now=datetime(2026, 11, 18, 9, 0, tzinfo=TZ).timestamp())
    if t.day > "2026-11-17":  # the clock of the test run decides which day the tracker starts on
        assert snap["dan"] == "2026-11-17" and snap["ranije"] and [d["ime"] for d in snap["danas"]] == ["Petrović Petar"]


def test_between_sittings_the_day_read_from_the_recording_takes_the_place_of_the_services_own(tmp_path):
    from datetime import datetime
    from uzivo.names import Person, person_key
    path = tmp_path / "stanje.json"
    t = Tracker(str(path), tz="Europe/Belgrade")
    day1 = datetime(2026, 11, 17, 17, 38, tzinfo=TZ).timestamp()
    p = Person(person_key("Petrović Petar"), "Petrović Petar", "petrovic-petar", "PG A")
    for i in range(3):
        t.observe(p, now=day1 + 5 * i)
    t.tick(now=day1 + 200)
    rec = {"dan": "2026-11-17", "izvor": "snimak", "govori": [
        {"ime": "Nikolić Nina", "adresa": "", "grupa": "", "uloga": "Lista B", "od": int(day1 - 3600),
         "do": int(day1 - 3000), "okvira": 120, "video": "xyz", "snimak": 95},
        {"ime": "Jović Jova", "adresa": "", "grupa": "", "uloga": "", "od": int(day1 - 2000), "do": int(day1 - 1995),
         "okvira": 1, "video": "xyz", "snimak": 600},
        {"ime": "Petrović Petar", "adresa": "petrovic-petar", "grupa": "", "uloga": "", "od": int(day1 - 60),
         "do": int(day1 + 600), "okvira": 130, "video": "xyz", "snimak": 3500}]}
    t.use_recording(rec)
    assert not t.snapshot(now=day1 + 200)["snimak"]  # the same day, while it lasts: what the service read
    next_day = datetime(2026, 11, 18, 9, 0, tzinfo=TZ).timestamp()
    snap = Tracker(str(path), tz="Europe/Belgrade").snapshot(now=next_day)  # kept across restarts
    if snap["dan"] == "2026-11-17":  # a tracker started after the test day (as in any run after 17 Nov 2026)
        assert snap["snimak"] and [d["ime"] for d in snap["danas"]] == ["Petrović Petar", "Nikolić Nina"]
        html = fragment(snap, cyr=False, site="", tz=TZ)
        assert "Poslednji dan sednice, 17. novembar 2026." in html and "sa celog snimka" in html
        assert "youtube.com/watch?v=xyz&amp;t=95s" in html
    # An older day from the recording does not replace a later day the service read itself.
    t.use_recording({**rec, "dan": "2026-11-16"})
    snap = Tracker(str(path), tz="Europe/Belgrade").snapshot(now=next_day)
    assert not snap["snimak"]
    t.use_recording({"dan": 5})  # not shaped like a day: ignored
    assert t.recording["dan"] == "2026-11-16"


def test_between_sittings_the_page_has_the_sites_quiz_and_facts(tmp_path):
    from uzivo.page import waiting_part
    path = tmp_path / "stanje.json"
    t = Tracker(str(path), tz="Europe/Belgrade")
    w = {"kviz": [{"q": "Koliko?", "options": ["10", "21", "34"], "answer": 1, "why": "21 dan.", "href": "brojke"}],
         "cinjenice": [{"text": "Na sajtu je 2097 zakona.", "href": "zakoni"}]}
    t.use_waiting(w)
    t.use_waiting({"kviz": "x"})  # not shaped like it: ignored
    assert Tracker(str(path), tz="Europe/Belgrade").waiting == w  # kept across restarts
    snap = t.snapshot()
    lat = page(snap, cyr=False, site="https://zailiprotiv.rs/", tz=TZ, waiting=w)
    assert snap["stanje"] == NO_STREAM and "Dok čekate" in lat and 'data-a="1"' in lat
    assert '<a href="https://zailiprotiv.rs/brojke">Kako je izračunato</a>' in lat and "Da li ste znali" in lat
    cyr = waiting_part(w, cyr=True, site="https://zailiprotiv.rs/")
    assert "Док чекате" in cyr and 'href="https://zailiprotiv.rs/cir/zakoni"' in cyr
    snap["stanje"] = SPEAKING
    assert "Dok čekate" not in page(snap, cyr=False, site="", tz=TZ, waiting=w)  # not while someone speaks
    assert waiting_part({}, cyr=False, site="") == ""
