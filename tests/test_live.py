"""live/uzivo: who is speaking now, read from the broadcast's caption. Only the parts with no outside packages
(names, the caption's lines, the turns, the page); OCR and the stream are tried on the broadcast itself."""
import json
import sys
import threading
import time
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "live"))

from uzivo import config  # noqa: E402
config.SHOW_TRANSCRIPT = True  # the tests of the transcript's showing; off on the page by default
config.CHAIR_ONLY = False  # and of the speakers' sound being written down; by default only the chair's is
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



import pytest  # noqa: E402
from uzivo import state as _state  # noqa: E402


@pytest.fixture(autouse=True)
def _short_turns_without_a_second_line(request, monkeypatch):
    """These tests read turns of a few frames with no line under the name, to test other things; the rule that such
    a turn needs more frames (state.counted) has its own test, marked to keep the real number."""
    if "real_frames" not in request.keywords:
        monkeypatch.setattr(_state, "SURE_FRAMES", 2)


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
    t.observe(petar, "Lista za primer", now=now + 5)    # a whole caption (the list under the name): taken at once
    assert t.status == SPEAKING and t.snapshot()["sada"]["ime"] == "Petrović Petar"
    t.observe(None, now=now + 10)                       # a frame without a name: still Petar
    t.observe(petar, now=now + 15)
    t.observe(marko, "Lista za primer", now=now + 20)   # another name: Petar's turn ends
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
    t.observe(marko, "Lista za primer", now=now)
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
    nina = Person(person_key("Nikolić Nina"), "Nikolić Nina", "nikolic-nina", "PG B")
    for i in range(2):
        t.observe(nina, now=day1 + 15 + 5 * i, at={"video": "abc", "sq": 123 + i, "seg": 5.0})
    snap = t.snapshot(now=day1 + 25)
    assert not snap["ranije"]
    assert snap["danas"][0]["snimak"] == 595 and snap["danas"][0]["video"] == "abc"  # (120 - 1) × 5 s
    html = fragment(snap, cyr=False, site="", tz=TZ)
    assert "youtube.com/watch?v=abc&amp;t=595s" in html and "snimak 9:55" in html
    # The broadcast over: its YouTube video goes private, so no link into it (18 Nov 2026).
    t.tick(now=day1 + 200)
    assert all(d["snimak"] is None for d in t.snapshot(now=day1 + 200)["danas"])
    # The next day, before anyone is read: the last sitting day's list, with its date.
    day2 = datetime(2026, 11, 19, 9, 0, tzinfo=TZ).timestamp()
    t2 = Tracker(str(path), tz="Europe/Belgrade")
    assert t.snapshot(now=day1 + 86400)["ranije"]  # past midnight, before any frame: no longer "today"
    t2.observe(None, now=day2)
    snap = t2.snapshot(now=day2)
    assert snap["dan"] == "2026-11-18" and [d["ime"] for d in snap["danas"]] == ["Nikolić Nina", "Petrović Petar"]
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
    assert seen[0] == "https://www.youtube.com/watch?v=new"  # the page's stream of the day first
    assert seen[1:] == ["https://www.youtube.com/watch?v=old", config.CHANNEL_LIVE]  # then the others, none live


def test_a_private_video_on_the_page_falls_back_to_the_live_one(monkeypatch):
    from uzivo import stream
    monkeypatch.setattr(config, "YOUTUBE_URL", "")
    monkeypatch.setattr(config, "SOURCE_PAGE", "https://example.org/page")
    monkeypatch.setattr(stream, "_youtube_url_from_page", lambda page: "https://www.youtube.com/watch?v=private")

    def resolve(url):
        if url.endswith("private"):
            raise RuntimeError("Private video")
        stream.VIDEO.update(id="live1")
        return "https://hls/live1.m3u8", {}
    monkeypatch.setattr(stream, "_resolve_youtube", resolve)
    assert stream.resolve_input()[0] == "https://hls/live1.m3u8"  # the channel's live broadcast
    assert stream._last_live.endswith("live1")  # and kept for the next time


_PLAYLIST = b"#EXTM3U\n#EXT-X-MEDIA-SEQUENCE:10\n#EXTINF:5.0,\nhttps://v/sq/10/a\n#EXTINF:5.0,\nhttps://v/sq/11/a\n"


def _poller(monkeypatch, tmp_path, segment):
    """An HlsPoller on a fake YouTube: the playlist always answers, `segment(n)` answers for segment n."""
    import time
    from uzivo import stream
    calls = {"playlist": 0, "frames": 0}

    def get(self, url, timeout=20):
        if "/sq/" not in url:
            calls["playlist"] += 1
            return _PLAYLIST
        return segment(int(url.split("/sq/")[1].split("/")[0]))

    def frame(path):
        calls["frames"] += 1
    monkeypatch.setattr(config, "FRAME_PATH", str(tmp_path / "frame" / "now.jpg"))
    monkeypatch.setattr(stream.HlsPoller, "_get", get)
    monkeypatch.setattr(stream, "_ffmpeg_last_frame", frame)
    p = stream.HlsPoller("https://v/playlist", {})

    def until(cond, limit=5.0):
        end = time.time() + limit
        while not cond() and time.time() < end:
            time.sleep(0.05)
        return cond()
    return p, calls, until


def test_a_fault_on_the_way_to_a_segment_does_not_stop_the_reading(monkeypatch, tmp_path):
    import urllib.error
    faults = [urllib.error.URLError(OSError(-5, "No address associated with hostname"))]

    def segment(n):
        if n == 11 and faults:
            raise faults.pop()  # 18 Nov 2026: one failed lookup ended the reading
        if n > 11:
            raise urllib.error.HTTPError("https://v", 404, "not yet", None, None)
        return b"x" * 2000
    p, calls, until = _poller(monkeypatch, tmp_path, segment)
    try:
        assert until(lambda: calls["frames"] == 1)  # the segment came when asked again
        assert p.poll() is None  # and the reading goes on
    finally:
        p.kill()


def test_a_reading_that_ends_stops_asking_for_the_playlist(monkeypatch, tmp_path):
    import time
    import urllib.error

    def segment(n):
        raise urllib.error.HTTPError("https://v", 403, "expired", None, None)  # the address no longer valid
    p, calls, _ = _poller(monkeypatch, tmp_path, segment)
    p.join(5)
    assert p.poll() == 1 and b"403" in p.stderr.read()
    time.sleep(1.3)  # the playlist's thread asks once a second while it runs
    asked = calls["playlist"]
    time.sleep(1.3)
    assert calls["playlist"] == asked  # it ended with the reading


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
         "do": int(day1 + 600), "okvira": 130, "video": "", "datoteka": "https://arhiva.example/zas.mp4",
         "snimak": 3500}]}
    t.use_recording(rec)
    # The same day, the broadcast over: the day read from the recording (its links lead into the archive).
    assert t.snapshot(now=day1 + 200)["snimak"]
    next_day = datetime(2026, 11, 18, 9, 0, tzinfo=TZ).timestamp()
    snap = Tracker(str(path), tz="Europe/Belgrade").snapshot(now=next_day)  # kept across restarts
    if snap["dan"] == "2026-11-17":  # a tracker started after the test day (as in any run after 17 Nov 2026)
        assert snap["snimak"] and [d["ime"] for d in snap["danas"]] == ["Petrović Petar", "Nikolić Nina"]
        html = fragment(snap, cyr=False, site="", tz=TZ)
        assert "Poslednji dan sednice, 17. novembar 2026." in html and "sa celog snimka" in html
        assert "youtube.com" not in html and 'href="https://arhiva.example/zas.mp4#t=3500"' in html
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
    assert "Skupština sada ne zaseda" in lat  # the quiz's words don't take the state's place
    assert '<a href="https://zailiprotiv.rs/brojke">Kako je izračunato</a>' in lat and "Da li ste znali" in lat
    cyr = waiting_part(w, cyr=True, site="https://zailiprotiv.rs/")
    assert "Док чекате" in cyr and 'href="https://zailiprotiv.rs/cir/zakoni"' in cyr
    snap["stanje"] = SPEAKING
    assert "Dok čekate" not in page(snap, cyr=False, site="", tz=TZ, waiting=w)  # not while someone speaks
    assert waiting_part({}, cyr=False, site="") == ""


def test_the_player_is_a_button_until_clicked():
    from uzivo.page import player
    day = {"stanje": NO_STREAM, "provereno": 0, "sada": None, "dan": "2026-11-17", "ranije": True, "snimak": True,
           "danas": [{"ime": "B", "adresa": "", "grupa": "", "uloga": "", "od": 2, "do": 3, "sekundi": 1, "video": "",
                      "datoteka": "https://arhiva.videonet.co.rs/b.mp4", "snimak": 40},
                     {"ime": "A", "adresa": "", "grupa": "", "uloga": "", "od": 0, "do": 1, "sekundi": 1, "video": "",
                      "datoteka": "https://arhiva.videonet.co.rs/a.mp4", "snimak": 7}]}
    html = player(day, cyr=False, live="abcdefghijk")  # between sittings: the day's recording, from its first turn
    assert 'data-file="https://arhiva.videonet.co.rs/a.mp4" data-t="7"' in html and "Pusti snimak dana" in html
    assert "<iframe" not in html and "<video" not in html and " src=" not in html  # nothing loads before a click
    live = player({**day, "stanje": SPEAKING}, cyr=False, live="abcdefghijk")
    # while a sitting is on, the broadcast is on the page (the maintainer's decision), in YouTube's no-cookie mode
    assert '<iframe src="https://www.youtube-nocookie.com/embed/abcdefghijk"' in live and "autoplay=1" not in live
    assert player({**day, "danas": []}, cyr=False) == ""
    frag = fragment(day, cyr=False, site="", tz=TZ)
    assert 'data-file="https://arhiva.videonet.co.rs/a.mp4" data-t="7"' in frag  # each turn opens in the player
    page_ = page(day, cyr=False, site="", tz=TZ, live="")
    assert 'id="screen"' in page_ and "youtube-nocookie.com/embed/" in page_  # the address is only in the script


def test_a_day_in_several_files_plays_from_the_first_with_each_part_listed():
    from uzivo.page import player
    day = {"stanje": NO_STREAM, "danas": [], "datoteke": [
        {"url": "https://arhiva.videonet.co.rs/1.mp4", "od": 1794909938, "trajanje": 1102},
        {"url": "https://arhiva.videonet.co.rs/2.mp4", "od": 1794920192, "trajanje": 6938}]}
    html = player(day, cyr=False, tz=TZ)
    assert 'class="play" data-file="https://arhiva.videonet.co.rs/1.mp4" data-t="0"' in html
    assert "Deo 1 · 11:05–11:24" in html and "Deo 2 · 13:56–15:52" in html and '<p class="meta"></p>' not in html


def test_the_shared_state_is_cacheable_and_open_to_other_pages():
    import pytest
    pytest.importorskip("fastapi")  # the live service's own packages (live/requirements.txt), not the site's
    from fastapi.testclient import TestClient
    from uzivo import main
    r = TestClient(main.app).get("/stanje.js")
    assert r.status_code == 200 and r.headers["access-control-allow-origin"] == "*"
    assert "s-maxage=2" in r.headers["cache-control"] and "stanje" in r.json()


def test_the_page_is_counted_as_the_site_is():
    from uzivo import config
    snap = {"stanje": NO_STREAM, "provereno": 0, "sada": None, "dan": "2026-11-17", "ranije": False, "danas": []}
    html = page(snap, cyr=False, site="", tz=TZ, analytics="62b7969c87164343897a48605c9267c0")
    assert 'src="https://static.cloudflareinsights.com/beacon.min.js"' in html and "62b7969c87164343897a48605c9267c0" in html
    assert "posete se samo broje" in html
    plain = page(snap, cyr=False, site="", tz=TZ)
    assert "cloudflareinsights" not in plain and "broje" not in plain
    assert "cloudflareinsights" not in page(snap, cyr=False, site="", tz=TZ, analytics='x" onload="y')
    assert config.ANALYTICS_TOKEN.isalnum()  # read from data/settings.json, as the image has it
    ignore = (Path(__file__).parents[1] / "live" / "Dockerfile.dockerignore").read_text()
    assert "!data/settings.json" in ignore  # the image's build is sent the file it copies


def test_specks_around_an_unknown_name_are_left_out():
    from uzivo.caption import Caption, tidy, who
    from uzivo.names import Roster
    got = who(Caption(name_line="KE Mo Jugoslav Gašić 2", name_clean=True), Roster(), 0.8)
    assert got.name == "Gašić Jugoslav"
    assert who(Caption(name_line="Milica Vasiljević-Blagojević", name_clean=True), Roster(), 0.8).name == \
        "Vasiljević-Blagojević Milica"
    assert tidy("c Studentska lista") == "Studentska lista"


def test_a_role_read_with_a_word_missing_is_the_list_the_site_names():
    from uzivo.caption import role
    roster = Roster.from_json(json.dumps({"mps": [
        {"n": "Mirković Aleksandar", "s": "mirkovic-aleksandar", "g": "Aleksandar Vučić - Srbija pobeđuje"},
        {"n": "Gašić Jugoslav", "s": "gasic-jugoslav", "g": "Studentska lista"},
        {"n": "Stari Poslanik", "s": "stari-poslanik", "g": "A. VUČIĆ - Srbija ne sme da stane"}]}))
    mirkovic = roster.match("Aleksandar Mirković", 0.8)
    assert role("RA Aleksandar Vučić Srbija", mirkovic, roster, 0.8) == "Aleksandar Vučić - Srbija pobeđuje"
    assert role("c Studentska lista", None, roster, 0.8) == "Studentska lista"
    assert role("ministar finansija", None, roster, 0.8) == "ministar finansija"


def test_one_frame_of_another_name_inside_a_speech_is_not_a_turn():
    t = Tracker(None, "Europe/Belgrade")
    petar, marko = ROSTER.match("Петар Петровић", 0.8), ROSTER.match("Марко Јовановић", 0.8)
    now = 1794920000.0
    for s in (0, 5, 10):
        t.observe(petar, now=now + s)
    t.observe(marko, now=now + 15)
    for s in (20, 25):
        t.observe(petar, now=now + s)
    assert [x["name"] for x in t.turns] == ["Petrović Petar"] and t.turns[0]["n"] == 5
    t.observe(marko, now=now + 30)
    t.observe(marko, now=now + 35)
    assert [x["name"] for x in t.turns] == ["Petrović Petar", "Jovanović Marko"]


def test_the_speaker_shows_the_day_so_far_lines_about_the_mp_and_the_way_to_the_page():
    t = Tracker(None, "Europe/Belgrade")
    t.roster = ROSTER
    t.use_facts({
        "petrovic-petar": {"lista": "Lista za primer", "foto": "12.jpg", "sv": {"sek": 3600, "n": 4, "do": "2026-11-16", "saziv": "15"},
                           "c": [{"t": "300 za · 12 protiv · 1 uzdržan na konačnim glasanjima o zakonima.", "iz": "sazivi 13–14"},
                                 {"t": "87% prisustva na konačnim glasanjima.", "iz": "sazivi 13–14"}]},
        "jovanovic-marko": {"novi": 1, "lista": "Lista za primer", "c": [{"t": "Lekar · Niš · godište 1980.", "iz": "sajt Skupštine"}]}})
    petar, marko = ROSTER.match("Петар Петровић", 0.8), ROSTER.match("Марко Јовановић", 0.8)
    now = 1794920000.0
    for s in range(0, 601, 5):
        t.observe(petar, now=now + s)
    for s in range(610, 700, 5):
        t.observe(marko, now=now + s)
    for s in range(710, 831, 5):
        t.observe(petar, now=now + s)
    snap = t.snapshot(now=now + 831)
    cur = snap["sada"]
    assert cur["danas"] == {"n": 2, "sek": 720, "mesto": 1, "od": 2} and cur["lista"] == "Lista za primer"
    assert cur["saziv"] == {"broj": "15", "sek": 3600 + 720, "n": 6}  # the site's days and today
    html = fragment(snap, cyr=False, site="https://zailiprotiv.rs/", tz=TZ)
    assert 'src="https://zailiprotiv.rs/foto/12.jpg"' in html and 'data-sek="120"' in html
    assert "2. put za govornicom · ukupno 12 min · 1. po vremenu od 2 govornika" in html
    assert "15. saziv" in html and "1 h 12 min u 6 govora" in html
    assert '<span class="src">sazivi 13–14</span>300 za · 12 protiv' in html and "87% prisustva" in html
    assert 'class="cta" href="https://zailiprotiv.rs/poslanik/petrovic-petar"' in html and 'class="share-now"' in html
    assert "Vreme za govornicom po listama" in html and 'href="#t1794920610"' in html and 'id="t1794920610"' in html
    assert 'class="l1 on"' in html  # the turn now on, marked in the day's strip
    t.observe(marko, now=now + 840)
    t.observe(marko, now=now + 845)
    html = fragment(t.snapshot(now=now + 846), cyr=True, site="https://zailiprotiv.rs/", tz=TZ)
    assert "Лекар · Ниш · годиште 1980." in html and "/cir/poslanik/jovanovic-marko" in html and "Подели овај тренутак" in html


def test_a_speaker_on_no_list_is_counted_apart_in_the_days_time_by_list():
    t = Tracker(None, "Europe/Belgrade")
    t.roster = ROSTER
    guest = who(read([w("Ana Anić")], 85), Roster(), 0.8)
    petar = ROSTER.match("Петар Петровић", 0.8)
    now = 1794920000.0
    for s in (0, 5, 10):
        t.observe(petar, now=now + s)
    for s in (20, 25, 30):
        t.observe(guest, "ministar finansija", now=now + s)
    for s in (40, 45):
        t.observe(petar, now=now + s)
    snap = t.snapshot(now=now + 46)
    assert [d["lista"] for d in snap["danas"]] == ["", "Lista za primer"]
    html = fragment(snap, cyr=False, site="", tz=TZ)
    assert "Vlada i gosti" in html and 'class="lx"' in html


def test_a_half_read_name_is_the_sitting_mp_it_is_nearest_to():
    roster = Roster.from_json(json.dumps({"mps": [
        {"n": "Vasiljević Blagojević Milica", "s": "vasiljevic-blagojevic-milica", "g": "Studentska lista"},
        {"n": "Šoškić Dejan", "s": "soskic-dejan", "g": "Studentska lista"},
        {"n": "Stošić Dejan", "s": "stosic-dejan", "g": "AV-ZND"},
        {"n": "Hubač Željko", "s": "hubac-zeljko", "g": "Studentska lista"},
        {"n": "Vasić Milan", "s": "vasic-milan", "g": "SNS"}]}))
    roster.current = frozenset({"vasiljevic-blagojevic-milica", "soskic-dejan", "hubac-zeljko"})
    assert roster.match("Blagoj Milica Vasiljević", 0.8).slug == "vasiljevic-blagojevic-milica"
    assert roster.match("Dejan Šoškić", 0.8).slug == "soskic-dejan"
    assert roster.match("Hubač KU Željko", 0.8).slug == "hubac-zeljko"
    assert roster.match("Petar Petrović", 0.8) is None  # nobody near: nobody


def test_turns_read_before_the_list_knew_the_mp_are_named_and_joined_on_the_page():
    t = Tracker(None, "Europe/Belgrade")
    odd = lambda name: who(read([w(name)], 85), Roster(), 0.8)
    now = 1794920000.0
    for s, name in ((0, "Петар Петровић"), (5, "Петар Петровић"), (60, "Петар Петровић"), (65, "Петар Петровић")):
        person = odd(name)
        t.observe(person, "c Lista za primer", now=now + s)
        if s == 5:
            t.observe(None, now=now + 40)  # the turn closes, the same name comes back within the merge time
    t.observe(ROSTER.match("Марко Јовановић", 0.8), now=now + 120)
    t.observe(ROSTER.match("Марко Јовановић", 0.8), now=now + 125)
    t.roster = ROSTER
    shown = t.snapshot()["danas"]
    assert [d["ime"] for d in shown] == ["Petrović Petar"] and shown[0]["adresa"] == "petrovic-petar"
    assert shown[0]["uloga"] == "Lista za primer"


def test_a_list_with_a_colour_of_its_own_wears_it_in_the_days_bars_and_the_rest_stay_grey():
    from uzivo.page import _shades
    turns = [{"lista": "Studentska lista", "sekundi": 60}, {"lista": "Aleksandar Vučić - Srbija pobeđuje", "sekundi": 90},
             {"lista": "Lista za primer", "sekundi": 30}, {"lista": "*", "sekundi": 20}, {"lista": "", "sekundi": 10}]
    assert _shades(turns) == {"Studentska lista": "c-sl", "Aleksandar Vučić - Srbija pobeđuje": "c-av",
                              "Lista za primer": "l1", "*": "c-mn", "": "lx"}


def test_the_day_in_one_sentence_the_summary_while_nobody_is_on_and_the_link_preview():
    from uzivo import picture
    from uzivo.page import headline, og_text, page
    t = Tracker(None, "Europe/Belgrade")
    t.roster = ROSTER
    t.use_facts({"petrovic-petar": {"lista": "Lista za primer"}, "jovanovic-marko": {"lista": "Druga lista"}})
    petar, marko = ROSTER.match("Петар Петровић", 0.8), ROSTER.match("Марко Јовановић", 0.8)
    now = 1794920000.0
    for s_ in range(0, 601, 5):
        t.observe(petar, now=now + s_)
    for s_ in range(610, 700, 5):
        t.observe(marko, now=now + s_)
    for s_ in range(710, 731, 5):
        t.observe(petar, now=now + s_)
    snap = t.snapshot(now=now + 731)
    every = snap["danas"] + [snap["sada"]]
    line = headline(every, cyr=False)
    assert line.startswith("Najviše vremena za govornicom danas: Petar Petrović, 10 min")
    assert "Највише времена за говорницом данас: Петар Петровић, 10 мин" in headline(every, cyr=True)
    title, text = og_text(snap, cyr=False, tz=TZ)
    assert title.startswith("Sada govori: Petar Petrović") and "za govornicom od" in text and "Najviše vremena" in text
    html = page(snap, cyr=False, site="https://zailiprotiv.rs/", tz=TZ, url="https://mikrofon.zailiprotiv.rs/")
    assert 'property="og:image" content="https://mikrofon.zailiprotiv.rs/slika.png?v=' in html and '<p class="hl">' in html
    assert 'name="twitter:card" content="summary_large_image"' in html
    t.observe(None, now=now + 800)
    t.observe(None, now=now + 860)
    paused = t.snapshot(now=now + 861)
    html = fragment(paused, cyr=False, site="https://zailiprotiv.rs/", tz=TZ)
    assert paused["stanje"] != "govori" and "Dosad danas" in html and 'class="share-now share-day" data-src="/slika.png"' in html
    assert "<b>Petar Petrović</b>" in html
    for s_ in (snap, paused, Tracker(None, "Europe/Belgrade").snapshot(now=now)):
        png = picture.render(s_, cyr=True, tz=TZ, host="mikrofon.zailiprotiv.rs")
        assert png[:8] == b"\x89PNG\r\n\x1a\n" and len(png) > 2000


def test_the_sound_is_written_down_turn_by_turn_and_shown_as_an_automatic_transcript(tmp_path, monkeypatch):
    from uzivo import config, prepis
    from uzivo.page import transcript_page
    monkeypatch.setattr(config, "SOUND_PATH", str(tmp_path / "zvuk"))
    monkeypatch.setattr(config, "WHISPER_MODEL", "test")
    (tmp_path / "zvuk").mkdir()
    t = Tracker(str(tmp_path / "stanje.json"), "Europe/Belgrade")
    t.roster = ROSTER
    petar, marko = ROSTER.match("Петар Петровић", 0.8), ROSTER.match("Марко Јовановић", 0.8)
    now = float(int(time.time()) // 86400 * 86400 + 12 * 3600)  # noon today, so the day is the tracker's own
    t._load(t._day(now))

    def sound(at: float, seconds: float = 5.0) -> None:  # a segment's sound, read at `at`
        (tmp_path / "zvuk" / f"{int(at * 1000)}-{int(seconds * 1000)}.pcm").write_bytes(b"\0" * 100)

    for s_ in range(0, 121, 5):
        t.observe(petar, now=now + s_)
        sound(now + s_)
    heard = []
    w = prepis.Writer(t, threading.Event(), write=lambda raw: heard.append(len(raw)) or "Поштовани председниче, хвала.")
    assert w.step(now=now + 121) is True  # a piece of the speaker now on, once enough has gathered
    assert heard and t.said and "Poštovani predsedniče" in next(iter(t.said.values()))  # kept in Latin
    snap = t.snapshot(now=now + 121)
    assert snap["sada"]["prepis"].startswith("Poštovani") and snap["sada"]["reci"] == 3
    html = fragment(snap, cyr=False, site="https://zailiprotiv.rs/", tz=TZ)
    assert "automatski prepis" in html and "Poštovani predsedniče, hvala." in html and 'href="/prepis#t' in html
    assert w.step(now=now + 122) is False  # nothing new yet
    sound(now + 200)  # sound in no turn (the chair): thrown away once old
    for s_ in range(300, 311, 5):  # a turn too short to write down
        t.observe(marko, now=now + s_)
        sound(now + s_)
    t.observe(None, now=now + 400)
    t.observe(None, now=now + 460)
    assert w.step(now=now + 461) is True  # the rest of the finished turn
    assert w.step(now=now + 462) is False and not list((tmp_path / "zvuk").glob("*.pcm"))
    assert len(heard) == 2  # the short turn and the chair's sound were never read
    page_ = transcript_page(t.transcript(), cyr=True, site="https://zailiprotiv.rs/", tz=TZ)
    assert "Поштовани председниче, хвала." in page_ and "Петар Петровић" in page_ and "није" in page_
    again = Tracker(str(tmp_path / "stanje.json"), "Europe/Belgrade")  # kept across a restart
    assert again.said == t.said


def test_the_day_in_numbers_and_in_cards():
    t = Tracker(None, "Europe/Belgrade")
    t.roster = ROSTER
    petar, marko = ROSTER.match("Петар Петровић", 0.8), ROSTER.match("Марко Јовановић", 0.8)
    now = 1794920000.0
    for a, b, who_ in ((0, 300, petar), (310, 400, marko), (410, 500, petar), (510, 560, marko), (570, 700, petar)):
        for s_ in range(a, b + 1, 5):
            t.observe(who_, now=now + s_)
    html = fragment(t.snapshot(now=now + 701), cyr=False, site="https://zailiprotiv.rs/", tz=TZ)
    assert '<dl class="tiles">' in html and "<dd>5</dd><dt>govora</dt>" in html and "<dd>2</dd><dt>govornika</dt>" in html
    assert 'class="share-now st-open"' in html and html.count('<section class="st-c">') >= 5
    assert "Najduži govor bez prekida" in html and "Najviše puta za govornicom" in html and "3 <small>puta</small>" in html


def test_the_sound_is_found_in_a_format_of_its_own_when_the_picture_has_none():
    from uzivo.stream import sound_format
    formats = [{"format_id": "231", "protocol": "m3u8_native", "vcodec": "avc1", "acodec": "none", "url": "v"},
               {"format_id": "234", "protocol": "m3u8_native", "vcodec": "none", "acodec": "mp4a", "abr": 128, "url": "a-high"},
               {"format_id": "233", "protocol": "m3u8_native", "vcodec": "none", "acodec": "mp4a", "abr": 48, "url": "a-low"},
               {"format_id": "140", "protocol": "https", "vcodec": "none", "acodec": "mp4a", "abr": 128, "url": "not-hls"}]
    assert sound_format(formats) == "a-low" and sound_format(formats[:1]) == ""
    unsaid = [formats[0], {"format_id": "233-0", "protocol": "m3u8_native", "vcodec": "none", "url": "a"}]
    assert sound_format(unsaid) == "a"  # the sound track's codec left unsaid, as yt-dlp does for a playlist's tracks


@pytest.mark.real_frames
def test_a_name_read_in_two_frames_with_no_line_under_it_is_not_a_turn():
    t = Tracker(None, "Europe/Belgrade")
    t.roster = ROSTER
    petar, marko = ROSTER.match("Петар Петровић", 0.8), ROSTER.match("Марко Јовановић", 0.8)
    now = 1794920000.0
    for s_ in (0, 5, 10):
        t.observe(petar, "Lista za primer", now=now + s_)  # a real caption: the list under the name
    for s_ in (60, 75):
        t.observe(marko, now=now + s_)  # something read as a name, twice, nothing under it
    for s_ in (120, 180, 240):
        t.observe(None, now=now + s_)  # nothing read: the reading ends
    for s_ in (500, 505, 510, 515):
        t.observe(marko, now=now + s_)  # no second line either, but long enough
    t.observe(None, now=now + 600)
    t.observe(None, now=now + 660)
    snap = t.snapshot(now=now + 661)
    assert [(d["ime"], d["od"]) for d in snap["danas"]] == [("Jovanović Marko", int(now + 500)), ("Petrović Petar", int(now))]


def test_a_notice_from_the_site_stands_on_top_from_its_day_until_its_last():
    t = Tracker(None, "Europe/Belgrade")
    day = t._day(time.time())
    t.use_waiting({"kviz": [], "cinjenice": [], "obavestenja": [
        {"od": day, "do": day, "tekst": "Petar Petrović izabran je za predsednika Narodne skupštine.", "izvor": "sajt Narodne skupštine",
         "url": "https://www.parlament.gov.rs/x", "adresa": "petrovic-petar"},
        {"od": "2000-01-01", "do": "2000-01-02", "tekst": "Staro.", "izvor": "", "url": "https://www.parlament.gov.rs/y", "adresa": ""}]})
    snap = t.snapshot()
    assert [n["tekst"] for n in snap["obavestenja"]] == ["Petar Petrović izabran je za predsednika Narodne skupštine."]
    html = fragment(snap, cyr=True, site="https://zailiprotiv.rs/", tz=TZ)
    assert 'class="news"' in html and "Петар Петровић изабран је за председника" in html and "Старо" not in html
    assert 'href="https://www.parlament.gov.rs/x"' in html and "/cir/poslanik/petrovic-petar" in html


def test_the_days_steps_from_the_chairs_words_and_the_assemblys_page(tmp_path, monkeypatch):
    from uzivo import config, hronika, prepis
    assert hronika.find("Хвала. Прелазимо на другу тачку дневног реда. Реч има народни посланик.") == [
        ("Tačka dnevnog reda", "Prelazimo na drugu tačku dnevnog reda.")]
    assert [w for w, _ in hronika.find("Zaključujem pretres. Stavljam na glasanje predlog. Određujem pauzu do 15 časova.")] == [
        "Pretres zaključen", "Glasanje", "Pauza"]
    assert hronika.find("Poštovani narodni poslanici, hvala vam.") == []
    monkeypatch.setattr(config, "SOUND_PATH", str(tmp_path / "zvuk"))
    monkeypatch.setattr(config, "WHISPER_MODEL", "test")
    (tmp_path / "zvuk").mkdir()
    t = Tracker(str(tmp_path / "stanje.json"), "Europe/Belgrade")
    t.roster = ROSTER
    petar = ROSTER.match("Петар Петровић", 0.8)
    now = float(int(time.time()) // 86400 * 86400 + 12 * 3600)
    t._load(t._day(now))
    for s_ in range(0, 31, 5):
        t.observe(petar, now=now + s_)
    t.observe(None, now=now + 60)
    t.observe(None, now=now + 90)
    for s_ in range(100, 141, 5):  # nobody's caption: the chair speaks
        (tmp_path / "zvuk" / f"{int((now + s_) * 1000)}-5000.pcm").write_bytes(b"\0" * 100)
    w = prepis.Writer(t, threading.Event(), write=lambda raw: "Прелазимо на другу тачку дневног реда.")
    assert w.step(now=now + 118) is False  # too new: it may yet be a turn's beginning
    assert w.step(now=now + 260) is True
    assert list(t.said) == [f"p{int(now + 95)}"]  # the chair's words are kept apart, no one's speech by name
    snap = t.snapshot(now=now + 261)
    assert snap["bez_potpisa"]["tekst"] == "Prelazimo na drugu tačku dnevnog reda."
    shown_ = fragment(snap, cyr=False, site="https://zailiprotiv.rs/", tz=TZ)
    assert "Bez potpisa: predsedavajući ili sala" in shown_ and "Prelazimo na drugu tačku dnevnog reda." in shown_
    assert [(e["vrsta"], e["izvor"]) for e in snap["hronika"]] == [("Tačka dnevnog reda", "prepis")]
    page_ = "<html><body>Претрага сајта <h1>Прва седница</h1><p>Седница је почела у 10 часова у Дому Народне скупштине.</p>{more}<h3>Фото галерија</h3></body></html>"
    t.use_waiting({"kviz": [], "cinjenice": [], "sednice": ["https://www.parlament.gov.rs/Прва_седница.1.43.html"]})
    pages = [page_.format(more=""), page_.format(more="<p>Народни посланици изабрали су председника Народне скупштине јавним гласањем.</p>")]
    watcher = hronika.Watcher(t, threading.Event(), fetch=lambda url: pages.pop(0))
    assert watcher.look(now=now + 300) == 0 and watcher.look(now=now + 900) == 1  # the first reading is the start, the second brings what is new
    html = fragment(t.snapshot(now=now + 901), cyr=False, site="https://zailiprotiv.rs/", tz=TZ)
    assert "Šta se desilo danas" in html and "Narodni poslanici izabrali su predsednika" in html and "sajt Skupštine" in html
    assert "Prelazak na 2. tačku" not in html  # no agenda to bear the step out: not shown
    t.use_waiting({"kviz": [], "cinjenice": [], "dnevni_red": [{"naslov": "Prva sednica", "url": "", "tacke": [
        {"n": 1, "tekst": "Izbor predsednika"}, {"n": 2, "tekst": "Izbor potpredsednika"}]}]})
    html = fragment(t.snapshot(now=now + 902), cyr=False, site="https://zailiprotiv.rs/", tz=TZ)
    assert "Prelazak na 2. tačku dnevnog reda" in html and "prepoznato automatski" in html


def test_the_agenda_under_the_broadcast_says_which_items_are_done_and_by_whose_word():
    from uzivo import hronika
    assert hronika.item_no("Прелазимо на трећу тачку дневног реда.") == 3 and hronika.item_no("Prelazimo na tačku 4.") == 4
    assert hronika.item_no("Hvala, reč ima narodni poslanik.") == 0
    t = Tracker(None, "Europe/Belgrade")
    t.use_waiting({"kviz": [], "cinjenice": [], "dnevni_red": [{"naslov": "Prva sednica", "url": "https://www.parlament.gov.rs/x", "tacke": [
        {"n": 1, "tekst": "Potvrđivanje mandata", "gotova": True, "kada": "2026-11-17", "sta": "Mandati su potvrđeni."},
        {"n": 2, "tekst": "Izbor predsednika", "gotova": False, "kada": "", "sta": ""},
        {"n": 3, "tekst": "Izbor potpredsednika", "gotova": False, "kada": "", "sta": ""},
        {"n": 4, "tekst": "Imenovanje generalnog sekretara", "gotova": False, "kada": "", "sta": ""}]}]})
    states = lambda: [(x["stanje"], x["izvor"]) for x in t.snapshot()["dnevni_red"]["tacke"]]
    assert states() == [("gotova", "sajt"), ("na_redu", ""), ("", ""), ("", "")]
    t.note(time.time(), "Tačka dnevnog reda", "Prelazimo na treću tačku dnevnog reda.", "prepis")
    assert states() == [("gotova", "sajt"), ("gotova", "prepis"), ("u_toku", "prepis"), ("", "")]
    html = fragment(t.snapshot(), cyr=False, site="https://zailiprotiv.rs/", tz=TZ)
    assert 'class="agenda"' in html and "2 od 4 tačaka gotovo" in html and "u toku: Izbor potpredsednika" in html
    assert "po sajtu Skupštine" in html and "Mandati su potvrđeni." in html and "po rečima predsedavajućeg" in html


def test_one_word_read_cannot_stand_for_two_words_of_a_name():
    roster = Roster.from_json(json.dumps({"mps": [{"n": "El Sarag Sarah", "s": "el-sarag-sarah", "g": "L"},
                                                  {"n": "Valentik Sara", "s": "valentik-sara", "g": "L"}]}))
    roster.current = frozenset({"el-sarag-sarah", "valentik-sara"})
    assert roster.match("Сара", 0.8) is None and roster.match("Сара Павловић", 0.8) is None
    assert roster.match("Сара Валентик", 0.8).slug == "valentik-sara"
    assert roster.match("Сара Валентнк", 0.8).slug == "valentik-sara"  # a letter misread: still her, not the other Sara
    assert roster.match("Sarah El Sarag", 0.8).slug == "el-sarag-sarah" and roster.match("Сарах Ел Сараг", 0.8).slug == "el-sarag-sarah"


def test_a_name_with_nothing_under_it_is_taken_on_its_second_frame():
    t = Tracker(None, "Europe/Belgrade")
    petar, marko = ROSTER.match("Петар Петровић", 0.8), ROSTER.match("Марко Јовановић", 0.8)
    now = 1794920000.0
    t.observe(None, now=now)
    t.observe(marko, now=now + 5)  # a break: something read as a name once, nothing under it
    assert t.status == UNKNOWN and t.snapshot(now=now + 6)["sada"] is None and not t.turns
    t.observe(None, now=now + 10)
    t.observe(marko, now=now + 300)  # the same chance reading minutes later is not a second frame
    assert t.snapshot(now=now + 301)["sada"] is None and not t.turns
    t.observe(petar, now=now + 400)
    t.observe(petar, now=now + 405)  # twice in a row: a speaker, from the first of the two frames
    cur = t.snapshot(now=now + 406)["sada"]
    assert cur["ime"] == "Petrović Petar" and cur["od"] == int(now + 400) and t.turns[-1]["n"] == 2


def test_the_transcript_is_corrected_after_it_is_out_and_a_finished_turn_is_read_again(tmp_path, monkeypatch):
    from uzivo import config, ispravke, prepis
    from uzivo.page import transcript_page
    forms = ispravke.name_forms(["Petrović Petar", "Jovanović Marko"])
    assert ispravke.apply("Rec ima Petrovic, pa Jovanovicu. U oktoberu.", {"oktober": "oktobar", "oktoberu": "oktobru"}, forms) == \
        "Rec ima Petrović, pa Jovanoviću. U oktobru."
    assert ispravke.apply("petrovic malim slovom i Petrovićka ostaju", {}, forms) == "petrovic malim slovom i Petrovićka ostaju"
    monkeypatch.setattr(config, "SOUND_PATH", str(tmp_path / "zvuk"))
    monkeypatch.setattr(config, "WHISPER_MODEL", "test")
    (tmp_path / "zvuk").mkdir()
    t = Tracker(str(tmp_path / "stanje.json"), "Europe/Belgrade")
    t.roster = ROSTER
    t.use_waiting({"kviz": [], "cinjenice": [], "ispravke": {"oktober": "oktobar"}})
    petar = ROSTER.match("Петар Петровић", 0.8)
    now = float(int(time.time()) // 86400 * 86400 + 12 * 3600)
    t._load(t._day(now))
    for s_ in range(0, 61, 5):
        t.observe(petar, "Lista za primer", now=now + s_)
        (tmp_path / "zvuk" / f"{int((now + s_) * 1000)}-5000.pcm").write_bytes(b"\0" * 100)
    hints = []
    w = prepis.Writer(t, threading.Event(), write=lambda raw: hints.append(w.hint) or "Petrovic je rekao oktober.")
    w.write_whole = lambda raw: "Petrović je rekao: oktobar, tačno."
    assert w.step(now=now + 62) is True
    assert "Poslovnik" in hints[0] and "Petar Petrović" in hints[0]  # the terms and today's speakers, told to Whisper
    assert next(iter(t.said.values())) == "Petrovic je rekao oktober."  # kept as written
    assert t.snapshot(now=now + 63)["sada"]["prepis"] == "Petrović je rekao oktobar."  # shown corrected
    t.observe(None, now=now + 100)
    t.observe(None, now=now + 130)
    while w.step(now=now + 131):
        pass
    page_ = transcript_page(t.transcript(), cyr=False, site="https://zailiprotiv.rs/", tz=TZ)
    assert "Petrović je rekao: oktobar, tačno." in page_ and "drugo, tačnije čitanje" in page_  # the second reading took its place
    assert "mailto:kontakt@zailiprotiv.rs?subject=Ispravka%20prepisa" in page_ and "Prijavi grešku u prepisu" in page_


def test_trying_another_model_listens_to_the_kept_sound(tmp_path, monkeypatch):
    from uzivo import config, proba
    monkeypatch.setattr(config, "SOUND_PATH", str(tmp_path))
    (tmp_path / "2000-1000.pcm").write_bytes(b"\1\0" * 16000)
    (tmp_path / "1000-1000.pcm").write_bytes(b"\2\0" * 16000)
    raw, length = proba.collect(0)
    assert length == 2 and raw[:2] == b"\2\0" and raw[-2:] == b"\1\0"  # in the order of time, whole


def test_the_days_steps_wear_the_corrections_too(tmp_path):
    t = Tracker(None, "Europe/Belgrade")
    t.waiting = {"ispravke": {"prenego": "pre nego", "pošto vene": "poštovane"}}
    now = 1795089600.0
    t.observe(None, now=now)
    t.events.append({"t": now, "vrsta": "Nastavak rada", "tekst": "Dobar dan, pošto vene, prenego što nastavim.", "izvor": "prepis"})
    t.events.append({"t": now, "vrsta": "", "tekst": "prenego", "izvor": "sajt"})
    rows = t.snapshot(now=now + 1)["hronika"]
    assert rows[1]["tekst"] == "Dobar dan, poštovane, pre nego što nastavim." and rows[0]["tekst"] == "prenego"  # the Assembly's own words are left as they are
    assert t.events[0]["tekst"].startswith("Dobar dan, pošto vene")  # kept as written


def test_the_transcript_is_written_but_not_shown_and_the_steps_are_our_own_lines(monkeypatch):
    from uzivo import page as page_
    now = 1795089600.0
    snap = {"provereno": 0, "stanje": "nepoznato", "sada": None, "danas": [], "dan": "2026-11-19", "ranije": False,
            "bez_potpisa": {"od": now, "tekst": "pošto vene postanici"},
            "dnevni_red": {"naslov": "Prva sednica", "url": "", "tacke": [
                {"n": 1, "tekst": "Izbor predsednika", "stanje": "gotova", "izvor": "sajt", "kada": "", "sta": ""},
                {"n": 2, "tekst": "Izbor potpredsednika", "stanje": "u_toku", "izvor": "prepis", "kada": "", "sta": ""}]},
            "hronika": [
                {"t": now + 900, "vrsta": "Sajt Skupštine", "tekst": "Narodna skupština je izabrala potpredsednike.", "izvor": "sajt", "url": "https://www.parlament.gov.rs/x"},
                {"t": now + 400, "vrsta": "Predsedavajući konstatuje", "tekst": "Konstatujem da je krada.", "izvor": "prepis", "url": ""},
                {"t": now + 300, "vrsta": "Tačka dnevnog reda", "tekst": "Prelazimo na drugu tačku dnevnog reda.", "izvor": "prepis", "url": ""},
                {"t": now + 200, "vrsta": "Tačka dnevnog reda", "tekst": "po tački dnevnog reda", "izvor": "prepis", "url": ""},
                {"t": now + 60, "vrsta": "Nastavak rada", "tekst": "nastavljamo sa radom", "izvor": "prepis", "url": ""},
                {"t": now, "vrsta": "Nastavak rada", "tekst": "pošto vene postanici, nastavljamo sednicu prenego", "izvor": "prepis", "url": ""}]}
    rows = page_.steps_shown(snap)
    assert [(r["naslov"], r["opis"]) for r in rows] == [
        ("", "Narodna skupština je izabrala potpredsednike."), ("Prelazak na 2. tačku dnevnog reda", "Izbor potpredsednika"),
        ("Rad je nastavljen", "")]  # the Assembly's sentence whole; ours by rule; the repeated and the unsure left out
    monkeypatch.setattr(config, "SHOW_TRANSCRIPT", False)
    html = fragment(snap, cyr=False, site="https://zailiprotiv.rs/", tz=TZ)
    assert "pošto vene" not in html and "/prepis" not in html and "Bez potpisa" not in html
    assert "Rad je nastavljen" in html and "Izbor potpredsednika" in html and "krada" not in html
    cir = fragment(snap, cyr=True, site="https://zailiprotiv.rs/", tz=TZ)
    assert "Рад је настављен" in cir and "Прелазак на 2. тачку дневног реда" in cir


def test_only_the_chairs_sound_is_written_down_and_a_step_is_shown_when_something_bears_it_out(tmp_path):
    from uzivo import page as page_, prepis
    f = lambda at: (at, 5.0, tmp_path / f"{at}.pcm")
    turn = {"od": 100, "do": 160, "sekundi": 60}
    piece, drop, chair = prepis.choose([f(110), f(120), f(200), f(205), f(210), f(215)], [turn], None, now=300, chair_only=True)
    assert chair and [x[0] for x in piece] == [200, 205, 210, 215] and len(drop) == 2  # the speaker's sound is let go
    now = 1795089600.0
    said = {"Sednica otvorena": "Otvaram sednicu.", "Pauza": "Određujem pauzu.", "Nastavak rada": "Nastavljamo sa radom.",
            "Glasanje": "Stavljam na glasanje.", "Mera predsedavajućeg": "Izričem opomenu.", "Kraj rada": "Zaključujem današnji rad."}
    ev = lambda at, kind, text="": {"t": now + at, "vrsta": kind, "tekst": text or said[kind], "izvor": "prepis", "url": ""}
    snap = {"provereno": now + 5000, "sada": None, "dnevni_red": None,
            "danas": [{"od": now + 100, "do": now + 900}, {"od": now + 1000, "do": now + 1500}, {"od": now + 2400, "do": now + 2600}],
            "hronika": [ev(0, "Sednica otvorena"), ev(950, "Pauza"), ev(1510, "Pauza"), ev(1600, "Nastavak rada"), ev(2390, "Nastavak rada"),
                        ev(2500, "Glasanje"), ev(2550, "Mera predsedavajućeg"), ev(2560, "Tačka dnevnog reda", "Prelazimo na drugu tačku dnevnog reda."),
                        ev(4900, "Kraj rada")]}
    assert [(int(r["t"] - now), r["naslov"]) for r in page_.steps_shown(snap)][::-1] == [
        (0, "Sednica je otvorena"), (1510, "Pauza"), (1600, "Rad je nastavljen")]
    # the break at 950 had a speaker right after it; the vote and the item have no agenda behind them; the measure
    # waits for the Assembly; the second "resumed" had no break before it; the day's end is too fresh to be sure of
    snap["dnevni_red"] = {"tacke": [{"n": 1, "tekst": "Prva", "stanje": "gotova"}, {"n": 2, "tekst": "Druga", "stanje": "u_toku"}]}
    snap["provereno"] = now + 4900 + 300
    assert [r["naslov"] for r in page_.steps_shown(snap)] == [
        "Kraj rada za danas", "Prelazak na 2. tačku dnevnog reda", "Glasanje", "Rad je nastavljen", "Pauza", "Sednica je otvorena"]


def test_the_afternoon_of_19_november_as_the_service_kept_it():
    """What stood in the day's record when the steps vanished from the page: work resumed after a three-hour break
    nobody had announced in our hearing, the third item named without "prelazimo na", and a rule's false find."""
    from uzivo import hronika, page as page_
    assert hronika.item_no("Treća tačka dnevnog reda, izbor potpredsednika narodne skupštine.") == 3
    assert not hronika.find("Prema članu poslovnika do otvaranja pretresa prijave za reč podnose se u pisanom obliku.")
    assert hronika.find("Otvaram jedinstveni pretres.")[0][0] == "Pretres otvoren"
    day = 1795046400.0  # 19 Nov 2026, 00:00 in Belgrade
    at = lambda h, m: day + h * 3600 + m * 60
    ev = lambda h, m, kind, text: {"t": at(h, m), "vrsta": kind, "tekst": text, "izvor": "prepis", "url": ""}
    snap = {"provereno": at(17, 0), "sada": None, "danas": [{"od": at(10, 7), "do": at(11, 0)}, {"od": at(11, 37), "do": at(12, 38)}],
            "dnevni_red": {"tacke": [{"n": n, "tekst": f"Tačka {n}", "stanje": "gotova" if n < 3 else ""} for n in range(1, 7)]},
            "hronika": [ev(15, 41, "Nastavak rada", "Dobar dan, nastavljamo sednicu pre nego što nastavim."),
                        ev(15, 41, "Tačka dnevnog reda", "Treća tačka dnevnog reda, izbor potpredsednika narodne skupštine."),
                        ev(16, 24, "Predsedavajući konstatuje", "samo konstatujem da je pretres otpočeo"),
                        ev(16, 41, "Nastavak rada", "Nastavljamo, nastavljamo sa radom."),
                        ev(16, 43, "Pretres otvoren", "poslovnika do otvaranja pretresa prijave za reč")]}
    assert [r["naslov"] for r in page_.steps_shown(snap)] == ["Prelazak na 3. tačku dnevnog reda", "Rad je nastavljen"]


def test_the_floor_given_by_the_chairs_word_when_the_picture_names_nobody():
    from uzivo import hronika, page as page_
    from uzivo.names import Person, person_key
    mk = lambda n, sl: Person(person_key(n), n, sl, "Lista")
    people = [mk("Bakić Jovo", "bakic-jovo"), mk("Jovanov Milenko", "jovanov-milenko"), mk("Jovanović Nataša", "jovanovic-natasa"),
              mk("Petrović Ana", "petrovic-ana"), mk("Petrović Ana Marija", "petrovic-ana-marija")]
    got = lambda text: [p.slug for p in hronika.floor(text, people)]
    assert got("Hvala. Reč ima narodni poslanik Jovo Bakić. Izvolite.") == ["bakic-jovo"]
    assert got("Реч има народна посланица Наташа Јовановић.") == ["jovanovic-natasa"]
    assert got("Reč ima Jovo Bakic, a posle njega ima reč Milenko Jovanov.") == ["bakic-jovo", "jovanov-milenko"]  # diacritics lost: still whole
    assert got("Reč ima narodni poslanik Jova Bakič.") == ["bakic-jovo"]  # a letter off after "reč ima": the nearest, clearly
    assert got("Reč ima Milenko Jovanof.") == ["jovanov-milenko"] and got("Reč ima Nataša Jovano Vić.") == ["jovanovic-natasa"]
    assert got("Reč ima kolega Bakić.") == ["bakic-jovo"] and got("Reč ima ministar Marko Bakić.") == []  # a surname alone after a title, not after a name we do not know
    assert got("Reč ima koleginica Petrović.") == [] and got("Reč ima Zoran Lutovac.") == []  # two of that surname; nobody near
    assert got("Reč ima Ana Petrović.") == ["petrovic-ana"] and got("Reč ima Ana Marija Petrović.") == []  # two fit: nobody
    assert got("Jovo Bakić je to rekao. Reč ima predstavnik predlagača.") == []  # named elsewhere, not after the phrase
    now = 1795089600.0
    ev = lambda at, name, slug: {"t": now + at, "vrsta": "Reč ima", "tekst": name, "izvor": "prepis", "url": slug}
    snap = {"provereno": now + 3000, "sada": None, "dnevni_red": None, "danas": [{"od": now + 1000, "do": now + 1400}],
            "hronika": [ev(100, "Bakić Jovo", "bakic-jovo"), ev(400, "Bakić Jovo", "bakic-jovo"), ev(1050, "Jovanov Milenko", "jovanov-milenko"),
                        ev(2000, "Jovanović Nataša", "jovanovic-natasa")]}
    assert [r["naslov"] for r in page_.steps_shown(snap)] == ["Reč ima: Nataša Jovanović", "Reč ima: Jovo Bakić"]  # once in a quarter of an hour; not where the picture named the speaker
    html = page_._steps(snap, cyr=True, tz=TZ, site="https://zailiprotiv.rs/")
    assert 'Реч има: <b><a href="https://zailiprotiv.rs/cir/poslanik/jovanovic-natasa">Наташа Јовановић</a></b>' in html
