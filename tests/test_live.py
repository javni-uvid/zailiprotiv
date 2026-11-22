"""live/uzivo: who is speaking now, read from the broadcast's caption. Only the parts with no outside packages
(names, the caption's lines, the turns, the page); OCR and the stream are tried on the broadcast itself."""
import json
import re
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
from uzivo import state_base as _state  # noqa: E402  (state.counted's rule lives there)


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
    assert "<title>Skupština uživo: ko sada govori" in lat and "Lista za primer" in lat
    cyr = page(snap, cyr=True, site="https://zailiprotiv.rs/", tz=TZ)
    assert "Петар Петровић" in cyr and "https://zailiprotiv.rs/cir/poslanik/petrovic-petar" in cyr
    assert "<title>Скупштина уживо: ко сада говори" in cyr
    # the Rules of Procedure, always under the day (20 Nov 2026: the new convocation's readers asked to find it)
    assert 'href="https://zailiprotiv.rs/poslovnik-clanovi#pojmovi"' in lat and "Sednica po Poslovniku" in lat
    assert 'href="https://zailiprotiv.rs/cir/poslovnik-clanovi#pojmovi"' in cyr
    for html in (lat, cyr):  # nothing from elsewhere but links
        assert "<script src" not in html and "googleapis" not in html
    guest = Tracker(None, "Europe/Belgrade")
    odd = who(read([w("Нина <b>Николић")], 85), ROSTER, 0.8) or petar
    guest.observe(odd, now=1794920000.0)
    guest.observe(odd, now=1794920005.0)
    assert "<b>" not in fragment(guest.snapshot(), cyr=False, site="", tz=TZ)


def test_cyrillic_page_mixes_no_scripts_in_a_word():
    """20 Nov 2026: the live page's own converter wrote "Цлоудфларе Wеб Аналyтицс" and "иПхонеу". It now uses the
    site's (names.cyrillic → zailiprotiv.cyrillic.cyr): what is Latin by nature stays Latin, whole, and no word is
    left half in one script and half in the other."""
    from uzivo.page import TEXT
    mixed = re.compile(r"\b(?=\w*[а-шђјљњћџ])(?=\w*[a-zčćžšđ])\w+\b", re.I)
    for key, text in TEXT.items():
        assert not mixed.search(cyrillic(text)), (key, cyrillic(text))
    t = Tracker(None, "Europe/Belgrade")
    t.observe(ROSTER.match("Петар Петровић", 0.8), "Lista za primer", now=1794920000.0)
    html = page(t.snapshot(), cyr=True, site="https://zailiprotiv.rs/", tz=TZ)
    shown = re.sub(r"<(script|style)\b.*?</\1>|<[^>]+>", " ", html, flags=re.S)
    assert not mixed.findall(shown)
    assert "Cloudflare Web Analytics" in cyrillic(TEXT["counted"])
    assert cyrillic("mikrofon.zailiprotiv.rs ne odgovara") == "mikrofon.zailiprotiv.rs не одговара"


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


def test_between_sittings_the_page_has_the_sites_facts_and_no_quiz(tmp_path):
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
    # 22 Nov 2026, the maintainer: the quiz off the foot; the facts stay
    assert snap["stanje"] == NO_STREAM and "Da li ste znali" in lat and 'data-a="1"' not in lat and 'id="mq"' not in lat
    assert '<span class="pill off">Ne zaseda</span>' in lat
    cyr = waiting_part(w, cyr=True, site="https://zailiprotiv.rs/")
    assert "Да ли сте знали" in cyr and 'href="https://zailiprotiv.rs/cir/zakoni"' in cyr
    snap["stanje"] = SPEAKING
    assert "Da li ste znali" not in page(snap, cyr=False, site="", tz=TZ, waiting=w)  # not while someone speaks
    assert "parlament.gov.rs/prenosi" not in lat  # no link to the Assembly's own broadcast (22 Nov 2026)
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
    # while a sitting is on, a facade: our picture of the moment and ▶; YouTube loads only on the press, counted
    assert 'data-yt="abcdefghijk"' in live and 'data-e="mikrofon.pusti"' in live and 'src="/slika.png"' in live
    assert "<iframe" not in live and "youtube" not in live
    assert 'src="/cir/slika.png"' in player({**day, "stanje": SPEAKING}, cyr=True, live="abcdefghijk")
    assert player({**day, "danas": []}, cyr=False) == ""
    frag = fragment(day, cyr=False, site="", tz=TZ)
    assert 'data-file="https://arhiva.videonet.co.rs/a.mp4" data-t="7"' in frag  # each turn opens in the player
    page_ = page(day, cyr=False, site="", tz=TZ, live="")
    assert 'id="screen"' in page_ and "youtube-nocookie.com/embed/" in page_  # the address is only in the script
    assert " data-api=" not in page_
    assert 'data-api="https://glasovi.zailiprotiv.rs"' in page(day, cyr=False, site="", tz=TZ, api="https://glasovi.zailiprotiv.rs")
    assert " data-api=" not in page(day, cyr=False, site="", tz=TZ, api='x" onload="y')


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


def test_an_unchanged_part_is_not_sent_again():
    import pytest
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from uzivo import main
    c = TestClient(main.app)
    first = c.get("/deo")
    tag = first.headers["etag"]
    assert first.status_code == 200 and first.headers["cache-control"] == "no-cache" and 'data-stanje="' in first.text
    assert c.get("/deo", headers={"if-none-match": "W/" + tag}).status_code == 304  # weakened by Cloudflare
    assert c.get("/deo", headers={"if-none-match": '"other"'}).status_code == 200


def test_the_hidden_transcript_is_not_in_the_state(monkeypatch):
    """20 Nov 2026: with the transcript off the page, /stanje.json still carried the speaker's last words and the
    chair's; the snapshot leaves them out while config.SHOW_TRANSCRIPT is off."""
    t = Tracker(None, "Europe/Belgrade")
    now = 1794920000.0
    petar = ROSTER.match("Петар Петровић", 0.8)
    t.observe(petar, "Lista za primer", now=now)
    t.observe(petar, "Lista za primer", now=now + 30)
    t.say(now + 5, "poštovani predsedavajući, kolege")
    monkeypatch.setattr(config, "SHOW_TRANSCRIPT", True)
    assert "kolege" in json.dumps(t.snapshot(now=now + 31), ensure_ascii=False)
    monkeypatch.setattr(config, "SHOW_TRANSCRIPT", False)
    snap = t.snapshot(now=now + 31)
    assert "kolege" not in json.dumps(snap, ensure_ascii=False) and snap["bez_potpisa"] is None
    assert "reci" not in snap["sada"] and "prepis" not in snap["sada"]


def test_the_snapshot_is_computed_by_one_thread_at_a_time():
    t = Tracker(None, "Europe/Belgrade")
    t.observe(ROSTER.match("Петар Петровић", 0.8), "Lista za primer")
    calls, real = [], t._snapshot

    def slow(now):
        calls.append(1)
        time.sleep(0.2)
        return real(now)
    t._snapshot = slow
    first = t.snapshot()  # the first is computed; then, with one being computed, the others take the last one
    t._snap = (0.0, first)
    threads = [threading.Thread(target=t.snapshot) for _ in range(8)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert len(calls) == 2


def test_the_pages_script_is_valid_javascript(tmp_path):
    import shutil
    import subprocess
    import pytest
    from uzivo import page as page_
    node = shutil.which("node")
    if not node:
        pytest.skip("no node")
    f = tmp_path / "page.js"
    f.write_text(page_.SCRIPT, encoding="utf-8")
    assert subprocess.run([node, "--check", str(f)], capture_output=True).returncode == 0


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


def test_the_pages_uses_go_to_the_projects_own_counter_and_say_so():
    from uzivo import config
    snap = {"stanje": NO_STREAM, "provereno": 0, "sada": None, "dan": "2026-11-17", "ranije": False, "danas": []}
    html = page(snap, cyr=False, site="", tz=TZ, api="https://glasovi.zailiprotiv.rs")
    foot = lambda h: h.split("<footer>")[1].split("</footer>")[0]
    assert 'data-api="https://glasovi.zailiprotiv.rs"' in html and "zbraja po danu" in foot(html)
    plain = page(snap, cyr=False, site="", tz=TZ)
    assert "zbraja" not in foot(plain) and 'data-api="' not in plain
    assert "zbraja" not in foot(page(snap, cyr=False, site="", tz=TZ, api='x" onload="y'))
    assert config.VOTES_API == "https://glasovi.zailiprotiv.rs"  # data/settings.json's votes_api, no ending slash
    # every use the page sends is one the counter takes, and the counter takes the live page's for /e only
    worker = (Path(__file__).parents[1] / "worker" / "worker.js").read_text(encoding="utf-8")
    sent = set(re.findall(r'use\("([a-z0-9]+)"\)', html)) | set(re.findall(r'\[\d+, "([a-z0-9]+)"\]', html))
    assert sent >= {"otvori", "1min", "5min", "15min", "30min", "snimak", "sajt"}
    for what in sent:
        assert f'"mikrofon.{what}"' in worker
    assert 'path === "/e" && from === LIVE' in worker


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
    # 22 Nov 2026, the maintainer: the box of the day's sentence and its shares is gone; the link preview keeps it
    assert paused["stanje"] != "govori" and "Dosad danas" not in html and "share-day" not in html and 'class="pz' not in html
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
    again._load(t.day)  # on the test's day: a restart reads the real day's, which is another after midnight
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
    assert 'class="agenda"' in html and "2 od 4 tačaka gotovo" in html and "u toku: 3. Izbor potpredsednika" in html
    assert "Mandati su potvrđeni." in html and "po rečima predsedavajućeg" in html  # heard: said so; the Assembly's: the default
    assert "Tačka je gotova kad to napiše Skupština" in html  # by whose word, in the label under the list


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
    # what the Assembly wrote is not told a second time on the day's list (its sentence per item is in the
    # agenda): its page is linked; with nothing heard, its sentences are the list
    days = html.split('<section class="steps-sec">')[1].split("</section>")[0]
    assert "izabrala potpredsednike" not in days and "Zvanično" not in html
    assert days.split('<ol class="steps">')[1].count("<li") == 2
    assert 'href="https://www.parlament.gov.rs/x">Zapis sednice na sajtu Skupštine ↗</a>' in days
    only = fragment({**snap, "hronika": snap["hronika"][:1]}, cyr=False, site="https://zailiprotiv.rs/", tz=TZ)
    assert '<p class="st-said">Narodna skupština je izabrala potpredsednike.</p>' in only and "<time" not in only
    assert "Skupština piše posle događaja" in only  # where from: in the label beside the heading


def test_only_the_chairs_sound_is_written_down_and_a_step_is_shown_when_something_bears_it_out(tmp_path):
    from uzivo import page as page_, prepis
    f = lambda at: (at, 5.0, tmp_path / f"{at}.pcm")
    turn = {"od": 100, "do": 160, "sekundi": 60}
    piece, drop, chair = prepis.choose([f(110), f(120), f(200), f(205), f(210), f(215)], [turn], None, now=300, chair_only=True)
    assert chair and [x[0] for x in piece] == [200, 205, 210, 215] and len(drop) == 2  # the speaker's sound is let go
    piece, drop, chair = prepis.choose([f(110), f(120), f(200), f(205), f(210), f(215)], [turn], None, now=300)
    assert chair and [x[0] for x in piece] == [200, 205, 210, 215] and not drop  # the chair's first, the speaker's kept
    piece, drop, chair = prepis.choose([f(110), f(120)], [turn], None, now=300)
    assert not chair and [x[0] for x in piece] == [110, 120] and not drop  # then the speaker's
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
    # 20 Nov 2026: the other ways the chair gives the floor, as Whisper wrote them on 19 Nov
    assert got("Zahvaljujem. Rečima narodna poslanica Nataša Jovanović.") == ["jovanovic-natasa"]  # "reč ima" as one word
    assert got("Složio bih se sa tim rečima kolege Bakića.") == []  # "rečima", the word: "kolege" is no title of a speaker
    assert got("Rečima koje je izgovorio Jovo Bakić nema mesta ovde.") == []  # "rečima", the word, no title after it
    assert got("Povreda Poslovnika, narodni poslanik Milenko Jovanov.") == ["jovanov-milenko"]
    assert got("Pravo na repliku ima Jovo Bakić.") == ["bakic-jovo"] and got("Dajem reč Milenku Jovanovu.") == ["jovanov-milenko"]
    assert got("Replika, narodni poslanik Jovo Bakić.") == ["bakic-jovo"]
    assert got("Replika gospodinu Bakiću.") == []  # whom it answers, not who speaks
    assert got("Izvolite, kolega Jovanov.") == ["jovanov-milenko"]
    now = 1795089600.0
    ev = lambda at, name, slug: {"t": now + at, "vrsta": "Reč ima", "tekst": name, "izvor": "prepis", "url": slug}
    snap = {"provereno": now + 3000, "sada": None, "dnevni_red": None, "danas": [{"od": now + 1000, "do": now + 1400}],
            "hronika": [ev(100, "Bakić Jovo", "bakic-jovo"), ev(400, "Bakić Jovo", "bakic-jovo"), ev(1050, "Jovanov Milenko", "jovanov-milenko"),
                        ev(2000, "Jovanović Nataša", "jovanovic-natasa")]}
    assert [r["naslov"] for r in page_.steps_shown(snap)] == ["Reč ima: Nataša Jovanović", "Reč ima: Jovo Bakić"]  # once in a quarter of an hour; not where the picture named the speaker
    html = page_._steps(snap, cyr=True, tz=TZ, site="https://zailiprotiv.rs/")
    assert 'Реч има: <b><a href="https://zailiprotiv.rs/cir/poslanik/jovanovic-natasa">Наташа Јовановић</a></b>' in html


def test_the_transcript_behind_a_key_while_it_is_off_the_page(monkeypatch):
    monkeypatch.setattr(config, "SHOW_TRANSCRIPT", False)
    monkeypatch.setattr(config, "TRANSCRIPT_KEY", "")
    assert not config.transcript_open("")  # no key set: nobody
    monkeypatch.setattr(config, "TRANSCRIPT_KEY", "kratak")
    assert not config.transcript_open("kratak")  # too short to be a key
    monkeypatch.setattr(config, "TRANSCRIPT_KEY", "dug-kljuc-za-prepis")
    assert not config.transcript_open("pogresan") and not config.transcript_open("") and config.transcript_open("dug-kljuc-za-prepis")
    monkeypatch.setattr(config, "SHOW_TRANSCRIPT", True)
    assert config.transcript_open("")  # on the page: open to all


def test_the_next_sitting_is_counted_down_between_sittings():
    from datetime import datetime as dt_
    from uzivo.page import _units, countdown, left
    u = _units(False)
    assert left(0, u) == "Počinje uskoro" and left(59, u) == "1 min" and left(3 * 3600 + 120, u) == "3 h 2 min"
    assert left(86400 + 5 * 3600, u) == "1 dan 5 h" and left(21 * 86400, u) == "21 dan" and left(2 * 86400, u) == "2 dana"
    assert _units(True)["h"] == "ч"  # never "х", letter by letter
    at = dt_(2026, 11, 24, 10, 0, tzinfo=TZ).timestamp()
    snap = {"stanje": "nema_prenosa", "sazvano": {"naslov": "Druga sednica", "url": "https://www.parlament.gov.rs/x",
            "pocinje": "2026-11-24T10:00", "tacke": ["Predlog zakona o budžetu", "Izbor sudija"]}}
    html = countdown(snap, cyr=False, tz=TZ, now=at - 2 * 86400 - 3600)
    assert "Utorak, 24. novembar 2026. u 10:00" in html and ">2 dana 1 h<" in html and f'data-at="{int(at)}"' in html
    assert "Dnevni red (2)" in html and "<li>Izbor sudija</li>" in html and 'href="https://www.parlament.gov.rs/x"' in html
    assert "Уторак" in countdown(snap, cyr=True, tz=TZ, now=at - 60) and "Počinje uskoro" in countdown(snap, cyr=False, tz=TZ, now=at + 60)
    assert countdown(snap, cyr=False, tz=TZ, now=at + 13 * 3600) == ""  # long begun: not counted down to
    day_only = {"sazvano": {**snap["sazvano"], "pocinje": "2026-11-24"}}
    assert ">Sutra<" in countdown(day_only, cyr=False, tz=TZ, now=at - 86400)
    assert "za</span> <b>3 dana" in countdown(day_only, cyr=False, tz=TZ, now=at - 3 * 86400)
    assert countdown({"sazvano": None}, cyr=False, tz=TZ) == ""


def test_the_page_can_go_on_a_phones_home_screen():
    from uzivo.page import manifest
    m, c = manifest(False), manifest(True)
    assert m["start_url"] == "/" and c["start_url"] == "/cir/" and m["display"] == "standalone"
    assert c["short_name"] == "Микрофон" and {i["purpose"] for i in m["icons"]} == {"any", "maskable"}
    assert any(i["sizes"] == "512x512" for i in m["icons"]) and any(i["sizes"] == "192x192" for i in m["icons"])


def test_the_notification_goes_out_once_a_day_when_a_broadcast_begins(tmp_path):
    from datetime import datetime as dt_
    from uzivo.obavesti import Bell
    asked = []
    pages = {0: {"sent": 30, "gone": 1, "next": 31}, 31: {"sent": 4, "gone": 0, "next": None}}
    bell = Bell(str(tmp_path / "o.json"), token="t", api="https://glasovi.example/", post=lambda od: asked.append(od) or pages[od])
    morning = dt_(2026, 11, 24, 10, 0, tzinfo=TZ)
    assert not bell.frame(morning, wait=True) and not bell.frame(morning, wait=True)  # two frames: not yet
    assert bell.frame(morning, wait=True) and asked == [0, 31]  # the third: sent, every batch
    bell.restart()
    assert not any(bell.frame(morning, wait=True) for _ in range(5)) and asked == [0, 31]  # once a day, restarts too
    night = Bell(str(tmp_path / "n.json"), token="t", api="https://glasovi.example", post=lambda od: asked.append(od) or {})
    assert not any(night.frame(dt_(2026, 11, 24, 23, 0, tzinfo=TZ), wait=True) for _ in range(5))  # out of hours
    off = Bell(str(tmp_path / "x.json"), token="", api="https://glasovi.example", post=lambda od: asked.append(od) or {})
    assert not any(off.frame(morning, wait=True) for _ in range(5)) and asked == [0, 31]  # no token (the test): never


def test_the_page_offers_the_notification_and_its_worker_writes_it():
    from uzivo.page import service_worker
    snap = {"stanje": "nema_prenosa", "provereno": 0, "sada": None, "danas": [], "dan": "2026-11-20"}
    html = page(snap, cyr=False, site="https://zailiprotiv.rs/", tz=TZ, api="https://glasovi.zailiprotiv.rs/", push_key="BKEY")
    assert 'data-key="BKEY"' in html and "Obavesti me kad sednica počne" in html
    assert 'data-key="' not in page(snap, cyr=False, site="https://zailiprotiv.rs/", tz=TZ, push_key="BKEY")  # no counter: no offer
    sw = service_worker(True, "BKEY", "https://glasovi.zailiprotiv.rs/")
    assert "Седница је почела" in sw and '"url": "/cir/"' in sw and '"api": "https://glasovi.zailiprotiv.rs"' in sw
    assert "addEventListener(\"fetch\"" not in sw  # it handles no requests


def test_a_restart_takes_up_the_speaker_still_on(tmp_path, monkeypatch):
    from uzivo.names import Person, person_key
    path = tmp_path / "stanje.json"
    t0 = time.time() - 20  # frames until 20 s ago, then the image was put live again
    t = Tracker(str(path), tz="Europe/Belgrade")
    p = Person(person_key("Petrović Petar"), "Petrović Petar", "petrovic-petar", "PG A")
    for i in range(3):
        t.observe(p, role="PG A", now=t0 + 5 * i - 10)
    again = Tracker(str(path), tz="Europe/Belgrade")  # the new container, at once
    assert again.status == SPEAKING and again.current() == "Petrović Petar"
    now = time.time()
    again.tick(now=now + 50)  # 70 s after the last frame, but 50 s after the restart: the broadcast is still taken as on
    assert again.status == SPEAKING
    again.observe(p, role="PG A", now=now + 30)  # the stream found again: the same turn goes on
    assert len(again.turns) == 1 and again.turns[0]["n"] == 4
    again.tick(now=now + 30 + 61)
    assert again.status == NO_STREAM  # and once frames stop for good, it ends as ever
    assert Tracker(str(path), tz="Europe/Belgrade").status == NO_STREAM  # a restart after it: nothing taken up
    third = Tracker(str(path), tz="Europe/Belgrade")
    third.observe(p, role="PG A", now=time.time() - 30)
    assert Tracker(str(path), tz="Europe/Belgrade").status == SPEAKING
    monkeypatch.setattr(config, "RESUME_SECONDS", 5)  # a restart long after the last frame: nothing taken up
    assert Tracker(str(path), tz="Europe/Belgrade").status == NO_STREAM


def test_the_page_names_the_commit_it_was_built_from():
    snap = {"stanje": "nema_prenosa", "provereno": 0, "sada": None, "danas": [], "dan": "2026-11-20"}
    assert 'Verzija 31ce3a4</span></footer>' in page(snap, cyr=False, site="https://zailiprotiv.rs/", tz=TZ, version="31ce3a4")
    assert 'class="ver"' not in page(snap, cyr=False, site="https://zailiprotiv.rs/", tz=TZ)


def test_the_maintainer_alone_turns_on_the_outage_alerts(monkeypatch, tmp_path):
    from uzivo.obavesti import Bell
    from uzivo.page import admin_page, service_worker
    monkeypatch.setattr(config, "TRANSCRIPT_KEY", "dug-kljuc-za-prepis")
    monkeypatch.setattr(config, "SHOW_TRANSCRIPT", True)
    assert config.admin_open("dug-kljuc-za-prepis") and not config.admin_open("") and not config.admin_open("pogresan")
    monkeypatch.setattr(config, "TRANSCRIPT_KEY", "kratak")
    assert not config.admin_open("kratak")  # too short to be a key, transcript on the page or not
    html = admin_page("dug-kljuc-za-prepis", "BKEY")
    assert 'content="noindex"' in html and '"BKEY"' in html and "/upozorenja?k=" in html
    sw = service_worker(False, "BKEY", "https://glasovi.zailiprotiv.rs")
    assert "Mikrofon ne radi" in sw and "/p/vrsta" in sw and "Mikrofon ponovo radi" in sw
    assert not Bell(str(tmp_path / "o.json"), token="", api="https://glasovi.example").admin("https://fcm.googleapis.com/x")


def test_the_last_sitting_days_steps_between_sittings():
    """20 Nov 2026: after midnight the day's steps were gone; between sittings the last sitting day's are shown, dated."""
    from uzivo import page as page_
    now = 1795089600.0
    step = {"t": now, "vrsta": "Sajt Skupštine", "tekst": "Skupština je izabrala potpredsednike.", "izvor": "sajt", "url": "https://www.parlament.gov.rs/x"}
    snap = {"provereno": now, "sada": None, "dnevni_red": None, "danas": [], "hronika": [step], "ranije": True, "dan": "2026-11-19"}
    html = page_._steps(snap, cyr=False, tz=TZ)
    assert "Šta se desilo 19. novembra" in html and "potpredsednike" in html
    assert "Шта се десило 19. новембра" in page_._steps(snap, cyr=True, tz=TZ)
    assert "Šta se desilo danas" in page_._steps({**snap, "ranije": False}, cyr=False, tz=TZ)


def test_a_date_does_not_end_a_sentence_of_the_assemblys_page():
    from uzivo import hronika
    parts = hronika._SENTENCE.split("Trećeg dana rada, 19. novembra 2026. godine, Skupština je nastavila rad. Narodna skupština nastavlja sa radom u utorak, 24. novembra 2026. godine, u 10.00 časova. Hvala.")
    assert parts == ["Trećeg dana rada, 19. novembra 2026. godine, Skupština je nastavila rad.",
                     "Narodna skupština nastavlja sa radom u utorak, 24. novembra 2026. godine, u 10.00 časova.", "Hvala."]

def test_letter_sizes_are_the_scale():
    """The live page's letters are the site's scale (the --t- variables in page.CSS and in the shared mikrofon.css);
    a share of the parent's size is the one exception."""
    import re
    from pathlib import Path
    from uzivo import page
    shared = (Path(__file__).parent.parent / "src" / "zailiprotiv" / "templates" / "mikrofon.css").read_text(encoding="utf-8")
    for css in (page.CSS, shared):
        sizes = {v.strip() for v in re.findall(r"font-size:\s*([^;}]+)", css)}
        assert {v for v in sizes if not re.fullmatch(r"var\(--t-(\d|h1|d1|d2)\)", v)} <= {"40%", "inherit"}
        assert not re.search(r"font:\s*\d+\s+[\d.]+rem", css)


def test_earlier_turns_are_folded():
    """A long day's list of turns shows the latest and folds the earlier ones, each still on the page with its id."""
    from zoneinfo import ZoneInfo
    from uzivo import page
    turns = [{"ime": f"Petrović Petar{i}", "adresa": "", "uloga": "", "grupa": "", "lista": "", "od": 1000 + 100 * i,
              "do": 1060 + 100 * i, "sekundi": 60} for i in reversed(range(20))]  # as the snapshot lists them: newest first
    snap = {"provereno": 0, "stanje": "nema_prenosa", "sada": None, "danas": turns, "dan": "2026-11-19"}
    html = page.fragment(snap, cyr=False, site="https://zailiprotiv.rs/", tz=ZoneInfo("Europe/Belgrade"))
    fold = html[html.index('id="raniji-govori"'):html.index("</details>", html.index('id="raniji-govori"'))]
    assert fold.count("<li id=") == 20 - page.TURNS_SHOWN and "Raniji govori (12)" in fold
    assert html.count('<li id="t') == 20 and 'id="t2900"' not in fold and 'id="t1000"' in fold  # the newest stands open
    few = page.fragment({**snap, "danas": turns[:10]}, cyr=False, site="https://zailiprotiv.rs/", tz=ZoneInfo("Europe/Belgrade"))
    assert "raniji-govori" not in few


def test_between_sittings_the_notification_offer_stands_above_the_day_and_the_speakers_link_the_site():
    """20 Nov 2026: one device had asked for the sitting's notification, its button half a phone's screens down under
    the last day's summary. Between sittings it stands above the day; while a broadcast is on, under the speaker's
    box as before. The day's three with the most time lead to their pages on the site, as the totals do."""
    from zoneinfo import ZoneInfo
    from uzivo import page
    tz = ZoneInfo("Europe/Belgrade")
    turns = [{"ime": n, "adresa": a, "uloga": "", "grupa": "", "lista": "", "od": od, "do": od + s, "sekundi": s}
             for n, a, od, s in (("Petrović Petar", "petrovic-petar", 1000, 900), ("Jovanović Jovan", "", 2000, 300),
                                 ("Marković Marko", "markovic-marko", 3000, 120))]
    snap = {"provereno": 0, "stanje": "nema_prenosa", "sada": None, "danas": turns, "dan": "2026-11-19"}
    site = "https://zailiprotiv.rs/"
    html = page.page(snap, cyr=False, site=site, tz=tz)
    assert html.count('class="add-home"') == 1 and html.index('class="add-home"') < html.index('id="deo"')
    tot = html[html.index('class="tot"'):]
    assert '<a href="https://zailiprotiv.rs/poslanik/petrovic-petar">Petar Petrović</a>' in tot
    assert "Jovan Jovanović" in tot and 'poslanik/"' not in tot  # no page known: the name alone
    assert 'href="https://zailiprotiv.rs/cir/poslanik/petrovic-petar"' in page.page(snap, cyr=True, site=site, tz=tz)
    on = page.page({**snap, "stanje": "govori"}, cyr=False, site=site, tz=tz)
    assert on.count('class="add-home"') == 1 and on.index('class="add-home"') > on.index('id="deo"')


def test_the_days_steps_follow_the_order_of_the_assemblys_work():
    """20 Nov 2026, the maintainer: a vote cannot be closed before it was put, a debate opened after it was closed…"""
    from uzivo import page as page_
    now = 1795089600.0
    ev = lambda at, kind, text: {"t": now + at, "vrsta": kind, "tekst": text, "izvor": "prepis", "url": ""}
    agenda = {"tacke": [{"n": 1, "tekst": "Prva", "stanje": ""}, {"n": 2, "tekst": "Druga", "stanje": ""}]}
    steps = [ev(0, "Tačka dnevnog reda", "Prelazimo na prvu tačku dnevnog reda."),
             ev(60, "Glasanje zaključeno", "Zaključujem glasanje."),                 # nothing was put to the vote: out
             ev(120, "Pretres otvoren", "Otvaram pretres."),
             ev(500, "Pretres otvoren", "Otvaram pretres."),                         # opened already: out
             ev(900, "Glasanje", "Stavljam na glasanje predlog."),
             ev(900, "Pretres zaključen", "Zaključujem pretres."),                   # the same second: the debate first
             ev(960, "Glasanje", "Pristupamo glasanju prozivkom."),                  # the same vote, still open: out
             ev(2000, "Glasanje", "Za je glasalo 136 narodnih poslanika."),          # a result, kept under the old name
             ev(2100, "Pretres otvoren", "Otvaram pretres."),                        # closed already: out
             ev(2200, "Tačka dnevnog reda", "Prelazimo na drugu tačku dnevnog reda."),
             ev(2260, "Pretres otvoren", "Otvaram pretres.")]
    snap = {"provereno": now + 9000, "sada": None, "dnevni_red": agenda, "danas": [], "hronika": steps}
    got = [(int(r["t"] - now), r["naslov"]) for r in page_.steps_shown(snap)[::-1]]
    assert got == [(0, "Prelazak na 1. tačku dnevnog reda"), (120, "Pretres je otvoren"), (900, "Pretres je zaključen"),
                   (900, "Glasanje"), (2000, "Glasanje je zaključeno"), (2200, "Prelazak na 2. tačku dnevnog reda"),
                   (2260, "Pretres je otvoren")]


def test_the_models_steps_take_the_rules_place():
    """20 Nov 2026, the maintainer: the model (sudija.py) is the source of the day's steps, the rules the fallback.
    Its steps show; the rules' lose their place but for "Reč ima"; what it read besides shows only where the sentence
    bears it out (a number or name not in the sentence is left out)."""
    from uzivo import page as page_
    from uzivo.steps import steps_shown
    now = 1795089600.0
    agenda = {"tacke": [{"n": 2, "tekst": "Izbor predsednika"}, {"n": 3, "tekst": "Izbor potpredsednika"}]}
    ev = lambda dt, kind, text, src, **more: {"t": now - dt, "vrsta": kind, "tekst": text, "izvor": src, "url": "",
                                              **({"vise": more} if more else {})}
    hronika = [
        ev(3000, "Tačka dnevnog reda", "Ovo nema veze sa tačkom dnevnog reda.", "prepis"),  # a rule's false step
        ev(2900, "Tačka dnevnog reda", "Treća tačka dnevnog reda, izbor potpredsednika.", "model", tacka=3),
        ev(2800, "Rezultat glasanja", "Za je glasalo 136, protiv nula.", "model", napomena="za 136"),
        ev(2790, "Rezultat glasanja", "Zaključujem glasanje i saopštavam.", "model", napomena="za 140"),  # 140 not said
        ev(2700, "Izbor", "Narodna skupština je izabrala Aleksandra Čupića.", "model", ko="Aleksandar Čupić"),
        ev(2600, "Pauza", "Proglašavam pauzu od deset minuta.", "model", do="deset minuta"),
    ]
    snap = {"provereno": now, "sada": None, "danas": [], "dnevni_red": agenda, "hronika": hronika}
    rows = steps_shown(snap)
    titles = [(r["naslov"], r["opis"]) for r in rows[::-1]]
    assert titles == [("Prelazak na 3. tačku dnevnog reda", "Izbor potpredsednika"),
                      ("Rezultat glasanja", "za 136"), ("Rezultat glasanja", ""),
                      ("Izbor", "Aleksandar Čupić"), ("Pauza", "deset minuta")]
    assert all(r["model"] for r in rows)
    assert "prepoznao model (Claude Haiku)" in page_._steps(snap, cyr=False, tz=TZ)
    # a break still waits for nobody at the rostrum after it
    late = {**snap, "danas": [{"od": now - 2500, "do": now - 100}]}
    assert ("Pauza", "deset minuta") not in [(r["naslov"], r["opis"]) for r in steps_shown(late)]
    # no model step today: the rules as before
    assert all(not r.get("model") for r in steps_shown({**snap, "hronika": hronika[:1]}))


def test_the_judge_reads_the_transcript_and_sums_the_day_up(tmp_path, monkeypatch):
    """The model's calls (sudija.Judge): the steps it finds kept when their sentence is in the transcript, a stretch
    summed up at a break once nobody is on, the day when the broadcast has been off a while; a summary naming someone
    who did not speak, or a number not said, is asked again and then left out."""
    from uzivo import sudija
    monkeypatch.setattr(config, "STATE_PATH", str(tmp_path / "stanje.json"))
    t = Tracker(str(tmp_path / "stanje.json"), "Europe/Belgrade")
    base = 1795082400  # 19 Nov 2026, 11:00 in Belgrade
    t.day = t._day(base)
    t.say(base + 10, "Govorio sam o penzijama i o budžetu za sledeću godinu.")
    t.say(base + 250, "Proglašavam pauzu od deset minuta, nastavljamo u jedanaest.", chair=True)
    turns = [{"ime": "Petrović Petar", "lista": "Lista za primer", "od": base + 5, "do": base + 200}]
    state = {"stanje": "govori"}
    monkeypatch.setattr(t, "snapshot", lambda now=None: {"dan": t.day, "ranije": False, "stanje": state["stanje"],
                                                         "danas": turns, "sada": None, "provereno": base + 400})
    asked = []

    def ask(system, user, *rest):
        asked.append(system)
        if system is sudija.EVENTS:
            assert "[11:04:10] bez potpisa" in user and "[11:00:10] Petrović Petar (Lista za primer)" in user
            return json.dumps({"dogadjaji": [
                {"vrsta": "Pauza", "vreme": "11:04:10", "recenica": "Proglašavam pauzu od deset minuta", "do": "deset minuta"},
                {"vrsta": "Izbor", "vreme": "11:00:10", "recenica": "Skupština je izabrala nekoga ko nije pomenut", "ko": "X"}]})
        if system is sudija.SUMMARY:
            bad = sum(1 for s in asked if s is sudija.SUMMARY) == 1
            return "Evo: " + json.dumps({"od": "10:00", "do": "10:05", "ukratko": "Petrović je govorio o penzijama."
                                         + (" Glasalo je 99." if bad else ""),
                                         "tok": [], "govornici": [{"ime": "Petrović Petar", "o_cemu": "penzije"}]})
        return json.dumps({"kratko": "Dan o penzijama.", "ukratko": "Petrović je govorio o penzijama.", "odluke": [],
                           "tok": [], "govornici": [{"ime": "Petrović Petar", "o_cemu": "penzije"}]})

    j = sudija.Judge(t, threading.Event(), ask=ask)
    j.step(now=base + 300)  # the pieces read, the steps kept; the break not yet quiet long enough: no summary
    kept = [e for e in t.events if e["izvor"] == "model"]
    assert [(e["vrsta"], e["vise"]) for e in kept] == [("Pauza", {"do": "deset minuta"})]  # the invented one dropped
    assert asked == [sudija.EVENTS]
    j.step(now=base + 250 + sudija.BREAK_QUIET)  # nobody at the rostrum since the break
    assert asked.count(sudija.SUMMARY) == 2  # 99 was not said: asked again, then fine
    part = j.kept["delovi"][0]
    assert part["ukratko"] == "Petrović je govorio o penzijama." and part["t_do"] == base + 251
    state["stanje"] = "nema_prenosa"
    j.step(now=base + 400 + sudija.END_QUIET)
    assert j.kept["dan"]["kratko"] == "Dan o penzijama."
    on_disk = json.loads((tmp_path / "sazetak" / f"{t.day}.json").read_text(encoding="utf-8"))
    assert on_disk["dan"]["kratko"] == "Dan o penzijama." and on_disk["vidjeno"]
    monkeypatch.setattr(config, "SHOW_SUMMARY", True)
    assert t._summary_shown(t.day)["vrsta"] == "dan"
    monkeypatch.setattr(config, "SHOW_SUMMARY", False)
    assert t._summary_shown(t.day) is None


def test_the_subscribers_are_told_when_the_days_summary_is_out(tmp_path, monkeypatch):
    """Once a day, in the hours a notification may wake someone, and only while the summary is on the page and
    under half a day old; the counter is asked with the kind "sazetak"."""
    from uzivo import sudija
    from uzivo.obavesti import Bell
    posts = []
    bell = Bell(str(tmp_path / "o.json"), token="t", api="https://glasovi.example", post=lambda od, *w: posts.append(w) or {"sent": 1})
    monkeypatch.setattr(config, "STATE_PATH", str(tmp_path / "stanje.json"))
    t = Tracker(str(tmp_path / "stanje.json"), "Europe/Belgrade")
    j = sudija.Judge(t, threading.Event(), ask=lambda *a: "{}", bell=bell)
    night = 1795134600  # 20 Nov 2026, 01:30 in Belgrade
    j.day, j.kept = "2026-11-19", {"vidjeno": [], "delovi": [], "dan": {"ukratko": "U.", "t": night - 1800}}
    monkeypatch.setattr(config, "SHOW_SUMMARY", True)
    j._tell(night)
    assert posts == []  # at night: nobody woken
    morning = night + 6 * 3600  # 07:30
    j._tell(morning)
    import time as _t
    for _ in range(50):
        if posts:
            break
        _t.sleep(0.02)
    assert posts == [("sazetak",)] and j.kept["javljeno"] == morning
    j._tell(morning + 60)
    assert len(posts) == 1  # once
    assert not bell.summary("2026-11-19")  # the bell keeps the day too
    j.kept = {"dan": {"ukratko": "U.", "t": morning - 13 * 3600}}
    j._tell(morning)
    assert len(posts) == 1  # half a day old: no more news


def test_a_votes_figures_add_up_or_are_not_shown():
    """21 Nov 2026, the maintainer: for + against + abstained must equal those who voted. A vote that does not add up
    is asked for again; if it still doesn't it goes without its figures (and the line is dropped when its words carry
    them); one that adds up is told in one form."""
    from uzivo import sudija
    good = {"za": 136, "protiv": 0, "uzdrzano": 0, "glasalo": 136, "nije_glasalo": 98, "prisutno": 234}
    assert sudija.vote_errors(good) == []
    assert sudija.vote_text(good) == "za 136, protiv 0, uzdržano 0, glasalo 136, nije glasalo 98, prisutno 234"
    assert sudija.vote_errors({"za": 235, "protiv": 1, "uzdrzano": 0, "nevazece": 3, "glasalo": 239}) == []
    assert sudija.vote_errors({"za": 100, "protiv": 30, "uzdrzano": 5, "glasalo": 140})  # 135, not 140
    assert sudija.vote_errors({"za": 150, "glasalo": 140})  # a part over the whole
    assert sudija.vote_errors({"glasalo": 140, "nije_glasalo": 98, "prisutno": 234})  # 238, not 234
    assert sudija.vote_errors({"za": 97}) == []  # only what was said is checked
    assert sudija.vote_of({"za": "97", "protiv": -1, "x": 4, "uzdrzano": True}) is None  # nothing usable
    s = {"odluke": [{"vreme": "13:27", "sta": "Izabran predsednik.", "glasanje": {"za": 140, "protiv": 97, "glasalo": 237}},
                    {"vreme": "22:20", "sta": "Šest potpredsednika.", "glasanje": {"za": 136, "protiv": 5, "glasalo": 200}},
                    {"vreme": "22:22", "sta": "Način izbora.", "glasanje": {"za": 133, "protiv": 1, "uzdrzano": 0, "glasalo": 150}},
                    {"vreme": "22:30", "sta": "Odluka sa 120 glasova.", "glasanje": {"za": 120, "protiv": 10, "uzdrzano": 0, "glasalo": 140}},
                    {"vreme": "23:00", "sta": "Pauza."}]}
    assert len(sudija.check_votes(s)) == 3  # 22:20 lacks "uzdrzano" so cannot be added up; 22:22 does not add up;
    sudija.settle_votes(s)                  # 22:30 does not, and says 120 in its words too
    assert [o["vreme"] for o in s["odluke"]] == ["13:27", "22:20", "22:22", "23:00"]  # 22:30: better none than wrong
    assert s["odluke"][0]["glasovi"] == "za 140, protiv 97, glasalo 237"
    assert "glasanje" not in s["odluke"][2] and "glasovi" not in s["odluke"][2]  # no figures, the line stays
    assert sudija.check_votes(s) == []


def test_the_day_is_one_line_of_time_with_a_mark_for_each_kind():
    """22 Nov 2026, the maintainer: everything in the steps, the line of time with its marks, a symbol for each kind
    (a warning a red square). The day summary's decisions with a vote's figures (the steps telling an election or
    a result then left out); every step heard, each measure its own line titled by its kind; the model's paragraph
    not shown; where it is from in one label beside the heading."""
    from datetime import datetime
    from uzivo import page as page_
    now = datetime(2026, 11, 19, tzinfo=TZ).timestamp()  # 00:00 in Belgrade
    agenda = {"tacke": [{"n": 2, "tekst": "Izbor predsednika"}, {"n": 3, "tekst": "Izbor potpredsednika"}]}
    ev = lambda h, kind, text, **more: {"t": now + h * 3600, "vrsta": kind, "tekst": text, "izvor": "model", "url": "",
                                        **({"vise": more} if more else {})}
    hronika = [ev(13, "Tačka dnevnog reda", "Prelazimo na treću tačku dnevnog reda.", tacka=3),
               ev(13.1, "Pretres otvoren", "Otvaram pretres."),
               ev(13.2, "Izbor", "Izabran je Aleksandar Čupić.", ko="Aleksandar Čupić"),
               ev(14, "Mera predsedavajućeg", "Izričem opomenu Bakiću.", napomena="opomena", kome="Bakiću"),
               ev(16, "Mera predsedavajućeg", "Oduzimam reč.", napomena="oduzimanje reči")]
    s = {"vrsta": "dan", "kratko": "K.", "ukratko": "Ovo je dugačak pasus modela.", "odluke": [
        {"vreme": "13:27", "sta": "Izabran predsednik Skupštine.", "glasovi": "za 140, protiv 97, glasalo 237"},
        {"vreme": "00:10", "sta": "Imenovan generalni sekretar."}]}
    snap = {"provereno": now + 20 * 3600, "sada": None, "danas": [], "dnevni_red": agenda, "hronika": hronika, "sazetak": s}
    html = page_._steps(snap, cyr=False, tz=TZ, site="https://zailiprotiv.rs/")
    rows = html.split('<ol class="steps">')[1].split("</ol>")[0].split("<li ")[1:]
    assert "Imenovan generalni sekretar" in rows[0] and 'class="mk-odluka"' in rows[0]  # 00:10 is the night after: the newest
    assert "Ovo je dugačak pasus" not in html and "Izabran je Aleksandar Čupić" not in html  # the summary told the election
    assert '<b class="v-za">za 140</b>, <b class="v-protiv">protiv 97</b>, glasalo 237' in html
    measures = [r for r in rows if "mk-mera" in r]
    assert len(measures) == 2 and ">Opomena<" in measures[1] and "Bakiću" in measures[1] and "mk-mera-teska" in measures[0]
    assert '<i aria-hidden="true">3</i>' in html and "Prelazak na 3. tačku dnevnog reda" in html and "Pretres je otvoren" in html
    assert '<details class="chip"><summary>automatski · može da pogreši</summary>' in html and "Claude Haiku" in html
    assert "Aleksandar Čupić" in page_._steps({**snap, "sazetak": None}, cyr=False, tz=TZ)  # no summary: the step tells it
    assert "Одлука" in page_._steps(snap, cyr=True, tz=TZ)


def test_the_notice_of_when_the_assembly_goes_on_is_said_on_top():
    """22 Nov 2026, the maintainer: say that part as when the Assembly goes on."""
    from uzivo import page as page_
    assert page_._resumes("Narodna skupština nastavlja sa radom u utorak, 24. novembra 2026. godine, u 10.00 časova.") == "u utorak, 24. novembra, u 10.00"
    assert page_._resumes("Narodna skupština je izabrala predsednika.") == ""
    snap = {"stanje": "nema_prenosa", "provereno": 1, "sada": None, "sazvano": None, "bez_potpisa": None, "dan": "2026-11-19",
            "ranije": True, "danas": [], "dnevni_red": None, "hronika": [],
            "obavestenja": [{"od": "2026-11-20", "do": "2026-11-24", "tekst": "Narodna skupština nastavlja sa radom u utorak, 24. novembra 2026. godine, u 10.00 časova.",
                             "izvor": "sajt Narodne skupštine", "url": "https://www.parlament.gov.rs/x", "adresa": ""}]}
    html = fragment(snap, cyr=False, site="https://zailiprotiv.rs/", tz=TZ)
    assert '<p class="goes-on">Skupština nastavlja sa radom u utorak, 24. novembra, u 10.00.' in html and 'class="news"' not in html
    assert "Скупштина наставља са радом у уторак, 24. новембра, у 10.00." in fragment(snap, cyr=True, site="", tz=TZ)
    assert 'class="news"' in fragment({**snap, "stanje": "govori", "sada": None}, cyr=False, site="", tz=TZ)  # a sitting on: as it is

def test_a_steps_line_leads_to_what_the_rules_say_of_it():
    """20 Nov 2026, the maintainer's choice: the sitting's steps by the Rules of Procedure. A step's line leads to its
    term on the site's page of the Rules (steps.STEP_TERM); every term named there is one the site explains."""
    import json
    from pathlib import Path
    from uzivo import page as page_
    from uzivo.steps import STEP_TERM, STEP_TITLES
    kept = {t["id"] for t in json.loads((Path(__file__).parent.parent / "data" / "poslovnik" / "pojmovi.json").read_text(encoding="utf-8"))}
    assert set(STEP_TERM.values()) <= kept and set(STEP_TITLES) <= set(STEP_TERM)
    now = 1795089600.0
    agenda = {"tacke": [{"n": 1, "tekst": "Prva", "stanje": ""}]}
    steps = [{"t": now, "vrsta": "Tačka dnevnog reda", "tekst": "Prelazimo na prvu tačku dnevnog reda.", "izvor": "prepis", "url": ""},
             {"t": now + 60, "vrsta": "Pretres otvoren", "tekst": "Otvaram pretres.", "izvor": "prepis", "url": ""}]
    snap = {"provereno": now + 9000, "sada": None, "dnevni_red": agenda, "danas": [], "hronika": steps}
    html = page_._steps(snap, cyr=False, tz=TZ, site="https://zailiprotiv.rs/")
    assert 'href="https://zailiprotiv.rs/poslovnik-clanovi#pojam-tok-pretresa"' in html
    assert 'href="https://zailiprotiv.rs/poslovnik-clanovi#pojam-dnevni-red"' in html
    assert "cir/poslovnik-clanovi#pojam-tok-pretresa" in page_._steps(snap, cyr=True, tz=TZ, site="https://zailiprotiv.rs/")
    assert "poslovnik-clanovi" not in page_._steps(snap, cyr=False, tz=TZ)  # no site known: no link


def test_the_days_cards_tell_what_happened_before_who_spoke():
    """The cards from the sources the day has: the model's sentence (said to be the model's), the agenda's items the
    sitting's page has finished that day, the chair's measures counted by kind without names, what comes next; then
    the rostrum's cards. A card with more to read stays longer."""
    from uzivo.page import fragment
    now = 1795100000
    turn = lambda name, a, sec: {"ime": name, "adresa": "", "grupa": "", "uloga": "", "lista": "A", "od": now + a,
                                 "do": now + a + sec, "sekundi": sec, "video": ""}
    snap = {"stanje": "nema_prenosa", "provereno": now + 9000, "sada": None, "sazvano": None, "bez_potpisa": None,
            "dan": "2026-11-19", "ranije": True, "snimak": False, "verzija": "x",
            "danas": [turn("Petrović Petar", 0, 600), turn("Jović Jovan", 700, 300), turn("Petrović Petar", 1100, 200)],
            "obavestenja": [{"od": "2026-11-20", "do": "2026-11-24", "tekst": "Narodna skupština nastavlja sa radom u utorak.",
                             "izvor": "sajt Narodne skupštine", "url": "", "adresa": ""}],
            "sazetak": {"vrsta": "dan", "kratko": "Skupština je izabrala predsednika.", "ukratko": "Duže.", "odluke": []},
            "dnevni_red": {"naslov": "Prva sednica", "url": "", "tacke": [
                {"n": 1, "tekst": "Potvrđivanje mandata", "stanje": "gotova", "izvor": "sajt", "kada": "2026-11-17", "sta": "Ranije."},
                {"n": 2, "tekst": "Izbor predsednika", "stanje": "gotova", "izvor": "sajt", "kada": "2026-11-19", "sta": "Izabran je predsednik: 140 glasova."},
                {"n": 3, "tekst": "Izbor potpredsednika", "stanje": "gotova", "izvor": "prepis", "kada": "", "sta": ""},
                {"n": 4, "tekst": "Izbor radnih tela", "stanje": "na_redu", "izvor": "", "kada": "", "sta": ""}]},
            "hronika": [
                {"t": now + 500, "vrsta": "Mera predsedavajućeg", "tekst": "Izričem opomenu Petru Petroviću.", "izvor": "model", "url": "",
                 "vise": {"napomena": "opomenu", "kome": "Petru Petroviću"}},
                {"t": now + 2500, "vrsta": "Mera predsedavajućeg", "tekst": "Izričem opomenu.", "izvor": "model", "url": "", "vise": {"napomena": "opomenu"}}]}
    assert "st-data" not in fragment(snap, cyr=False, site="https://zailiprotiv.rs/", tz=TZ)  # no way to them between sittings (22 Nov 2026)
    from uzivo.page import _cards, _shades
    html = _cards({**snap, "stanje": "govori", "sada": snap["danas"][-1]}, snap["danas"], _shades(snap["danas"]), cyr=False,
                  site="https://zailiprotiv.rs/", tz=TZ)
    cards = html.split('<div class="st-data"')[1].split('<section class="st-c"')[1:]
    cards[-1] = cards[-1].split("</section>")[0]
    kickers = [c.split('<p class="st-k">')[1].split("</p>")[0] for c in cards]
    assert kickers[1:5] == ["Dan ukratko", "Završena 2. tačka dnevnog reda", "Mere predsedavajućeg", "Najviše vremena za govornicom"]
    assert kickers[-2:] == ["Šta sledi", "Ko su ljudi koji govore i kako glasaju?"]
    brief, item, measures = cards[1:4]
    assert "Skupština je izabrala predsednika." in brief and "Napisao model" in brief and 'data-t="7"' in brief
    assert "Izbor predsednika" in item and "140 glasova" in item and "na sajtu Skupštine" in item
    assert "Potvrđivanje mandata" not in "".join(cards)  # finished on another day
    assert '<p class="st-big">2</p>' in measures and "<b>2</b> opomenu" in measures and "Petroviću" not in measures  # kinds, no names
    assert "nastavlja sa radom u utorak" in cards[-2] and "4. Izbor radnih tela" in cards[-2]
    assert 'href="https://zailiprotiv.rs/govornici/2026-11-19"' in cards[-1]
    plain = {**snap, "sazetak": None, "dnevni_red": None, "hronika": [], "obavestenja": [], "stanje": "govori",
             "sada": snap["danas"][-1]}
    bare = _cards(plain, snap["danas"], _shades(snap["danas"]), cyr=False, site="https://zailiprotiv.rs/", tz=TZ)
    assert "Dan ukratko" not in bare and "Šta sledi" not in bare and bare.count('<section class="st-c"') == 5  # as before


def test_a_day_asked_for_is_found_among_the_kept_files_and_nowhere_else(tmp_path):
    from uzivo.state import _kept
    days = tmp_path / "dani"
    days.mkdir()
    (days / "2026-11-17.json").write_text("{}", encoding="utf-8")
    (tmp_path / "state.json").write_text("{}", encoding="utf-8")
    assert _kept(days, "2026-11-17") == days / "2026-11-17.json"
    assert _kept(days, "../state") is None and _kept(days, "2026-11-18") is None and _kept(None, "2026-11-17") is None


def test_the_first_line_says_what_is_now_and_the_agenda_stands_open():
    """22 Nov 2026, the maintainer's choice: the first screen says what is now, in place of the bar to the site; the
    agenda is open; the recording's parts and every row that opens are one kind of row."""
    from uzivo.page import page as page_
    agenda = {"naslov": "S", "url": "", "tacke": [{"n": 1, "tekst": "Prva", "stanje": "gotova", "izvor": "sajt", "kada": "", "sta": ""},
                                                {"n": 2, "tekst": "Druga", "stanje": "u_toku", "izvor": "prepis", "kada": "", "sta": ""}]}
    snap = {"stanje": "nepoznato", "provereno": 1, "sada": None, "sazvano": None, "bez_potpisa": None, "dan": "2026-11-19",
            "ranije": False, "danas": [], "dnevni_red": agenda, "hronika": []}
    live = page_(snap, cyr=False, site="https://zailiprotiv.rs/", tz=TZ)
    assert '<div class="status"><p><span class="pill"><i aria-hidden="true"></i>Uživo</span><span class="status-on">u toku: 2. Druga</span></p></div>' in live
    assert '<details class="agenda" id="dnevni-red" open>' in live and "hero-cta" not in live
    off = page_({**snap, "stanje": "nema_prenosa", "datoteke": [{"url": "https://x/1.mp4", "od": 1795089600, "trajanje": 60},
                                                                 {"url": "https://x/2.mp4", "od": 1795093200, "trajanje": 60}]},
                cyr=True, site="https://zailiprotiv.rs/", tz=TZ)
    assert '<span class="pill off">Не заседа</span>' in off and "Скупштина сада не заседа" not in off
    assert '<details class="parts-more"><summary>Делови дана (2)</summary>' in off


def test_colour_where_it_means_something():
    """22 Nov 2026, the maintainer's choice: the speaker in their list's colour (the day's bars' shade), a vote's bar
    and figures in "za" and "protiv"; nothing else in those two colours."""
    from uzivo import page as page_
    v = {"za": 136, "protiv": 0, "uzdrzano": 0, "glasalo": 136, "nije_glasalo": 98, "prisutno": 234}
    told = page_._votes("za 136, protiv 0, uzdržano 0, glasalo 136, nije glasalo 98, prisutno 234", v, False)
    assert '<i class="z" style="width:58.1%"></i>' in told and '<b class="v-za">za 136</b>' in told
    assert "dl-bar" not in page_._votes("za 5", None, False) and '<b class="v-za">за 5</b>' in page_._votes("za 5", None, True)
    now = 1795100000
    turn = {"ime": "Bakić Jovo", "adresa": "", "grupa": "", "uloga": "", "lista": "Studentska lista", "od": now - 60, "do": now,
            "sekundi": 60, "video": ""}
    snap = {"stanje": "govori", "provereno": now, "sada": turn, "sazvano": None, "bez_potpisa": None, "dan": "2026-11-19",
            "ranije": False, "danas": [], "hronika": [], "dnevni_red": None}
    assert '<div id="deo" class="lc-c-sl"' in fragment(snap, cyr=False, site="https://zailiprotiv.rs/", tz=TZ)
    assert '<div id="deo" data-checked' in fragment({**snap, "stanje": "nema_prenosa"}, cyr=False, site="", tz=TZ)
    css = (Path(__file__).parent.parent / "live" / "uzivo" / "static" / "live.css").read_text(encoding="utf-8")
    assert "ag-gotova i { color: var(--za)" not in css and ".dot { flex: none; width: .8rem; height: .8rem; border-radius: 50%; background: var(--protiv)" not in css


def test_the_days_speakers_five_stand_the_rest_open_and_no_bar_of_lists():
    """22 Nov 2026, the maintainer: "Ko je koliko govorio" the first five, the rest on a tap; the day's time by list
    off the page (the cards keep it); "Sednica po Poslovniku" higher."""
    from uzivo import page as page_
    turns = [{"ime": f"Prezime{i} Ime{i}", "adresa": "", "uloga": "", "grupa": "", "lista": "L" + str(i % 2),
              "od": 1000 * i, "do": 1000 * i + 60 * (10 - i), "sekundi": 60 * (10 - i)} for i in range(1, 9)]
    snap = {"provereno": 0, "stanje": "nema_prenosa", "sada": None, "danas": turns, "dan": "2026-11-19", "ranije": True}
    html = page_.fragment(snap, cyr=False, site="", tz=TZ)
    shown = html[html.index('class="tot"'):html.index('class="tot-more"')]
    assert shown.count('class="tr"') == 5 and "Ime1 Prezime1" in shown and "Ime6" not in shown
    more = html[html.index('class="tot-more"'):]
    assert "Ostali govornici (3)" in more and more.count('class="tr"') == 3
    assert '<h3 class="sub">Vreme za govornicom po listama' not in html  # in the cards only
    css = page_.CSS
    assert 'main:has(#deo[data-stanje="nema_prenosa"]) > .rules-cta { order: 16; }' in css


def test_the_speaker_stands_on_the_picture_and_the_picture_stays_on_top():
    """22 Nov 2026, the maintainer: the name, list and clock on the broadcast's picture; the picture kept small on
    top while the page is read, with a way to put it back."""
    from uzivo.page import player, SCRIPT, CSS
    snap = {"stanje": "govori", "danas": [], "datoteke": []}
    live = player(snap, cyr=False, live="dQw4w9WgXcQ", tz=TZ)
    assert '<div class="stage"><div class="screen" id="screen">' in live and '<p class="on-air" hidden' in live
    assert 'class="mini-x" hidden aria-label="Vrati snimak na njegovo mesto"' in live
    day = {"stanje": NO_STREAM, "datoteke": [{"url": "https://arhiva.videonet.co.rs/a.mp4", "od": 0, "trajanje": 60}], "danas": []}
    archive = player(day, cyr=False, tz=TZ)
    assert 'class="mini-x"' in archive and "on-air" not in archive  # the archive's speaker is not the part's
    assert "function onAir()" in SCRIPT and "function mini(on)" in SCRIPT and ".player.mini .stage { position: fixed" in CSS


def test_whisper_on_the_graphics_card_and_the_cpu_while_it_does_not_answer(monkeypatch):
    """22 Nov 2026: whisper.cpp's server on the Radeon writes the sound; the CPU while it does not answer, asked again
    after RETRY; a word's loop is cut either way."""
    import http.server
    import threading as th
    from uzivo import prepis, config
    assert prepis.calm("da da da da da da ne ne") == "da da da ne ne"
    assert prepis.calm("Znaju, znaju znaju znaju. Znaju dobro") == "Znaju, znaju znaju. dobro"
    got = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            got["body"] = body
            self.send_response(200)
            self.end_headers()
            self.wfile.write('{"text": " Poštovani predsedniče,\\n hvala hvala hvala hvala hvala."}'.encode())

        def log_message(self, *a):
            pass
    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    th.Thread(target=srv.serve_forever, daemon=True).start()
    raw = b"\0\0" * prepis.RATE
    assert prepis.over_http(f"http://127.0.0.1:{srv.server_port}", raw, "Govore: Petrović Petar.") == \
        "Poštovani predsedniče, hvala hvala hvala hvala hvala."
    assert b'name="language"\r\n\r\nsr' in got["body"] and b"Govore: Petrovi" in got["body"] and b"RIFF" in got["body"]
    w = prepis.Writer(None, th.Event())
    cpu_calls = []
    monkeypatch.setattr(prepis.Writer, "_cpu", lambda self: (lambda raw: cpu_calls.append(1) or "sa procesora"))
    monkeypatch.setattr(config, "WHISPER_URL", f"http://127.0.0.1:{srv.server_port}")
    write = w._model()
    assert write(raw) == "Poštovani predsedniče, hvala hvala hvala." and not cpu_calls  # the card; the loop cut
    srv.shutdown()
    srv.server_close()
    monkeypatch.setattr(config, "WHISPER_URL", "http://127.0.0.1:9")  # nothing answers there
    write = w._model()
    assert write(raw) == "sa procesora" and write(raw) == "sa procesora" and len(cpu_calls) == 2
    monkeypatch.setattr(config, "WHISPER_URL", "")
    assert w._model()(raw) == "sa procesora"


def test_the_line_under_the_picture(tmp_path, monkeypatch):
    """22 Nov 2026, the maintainer: the automatic transcript under the broadcast's picture, at once. The newest sound,
    some eight seconds at a time, written by the card's Whisper for the page only; the page holds it for the script."""
    import threading as th
    from uzivo import prepis, config, page as page_
    monkeypatch.setattr(config, "SOUND_PATH", str(tmp_path))
    now = 1795100000.0
    for i in range(3):  # three segments of 4 s, the last ended a second ago; by the broadcast's clock 20 s earlier
        (tmp_path / f"{int((now - 9 + 4 * i) * 1000)}-4000-{int((now - 33 + 4 * i) * 1000)}.pcm").write_bytes(b"\0\0" * prepis.RATE * 4)
    t = Tracker(None, "Europe/Belgrade")
    t.status, t.last_frame = SPEAKING, now
    heard = []
    c = prepis.Captions(t, th.Event(), write=lambda raw, hint: heard.append((len(raw), hint)) or
                        [(0.5, 2.0, "Добар дан."), (2.5, 7.0, "Хвала хвала хвала хвала, колеге.")])
    assert c.step(now) and heard[0][0] == 2 * prepis.RATE * 4 and "Narodna skupština" in heard[0][1]
    assert t.captions[-1]["tekst"] == "Hvala hvala hvala kolege."
    assert t.captions[0]["pt"] == round(now - 33 + 0.5, 2) and t.captions[-1]["od"] == round(now - 13 + 2.5, 1)
    assert len(list(tmp_path.glob("*.pcm"))) == 3  # nothing taken from the transcript
    snap = t.snapshot(now)
    assert [c["tekst"] for c in snap["titl"]] == ["Dobar dan.", "Hvala hvala hvala kolege."]
    monkeypatch.setattr(config, "SHOW_CAPTIONS", False)
    assert t.snapshot(now + 1)["titl"] == []
    monkeypatch.setattr(config, "SHOW_CAPTIONS", True)
    t.status = NO_STREAM
    assert t.snapshot(now + 2)["titl"] == []  # between sittings, none
    html = page_.fragment({**snap, "stanje": "govori"}, cyr=True, site="", tz=TZ)
    assert '<ol class="cc-src" hidden><li data-od=' in html and "Хвала хвала хвала колеге." in html and 'data-pt="' in html
    assert prepis.program(tmp_path / "1-2-3000.pcm") == 3.0 and prepis.program(tmp_path / "1-2.pcm") is None
    assert len(prepis.waiting()) == 3  # a name with the broadcast's clock is still read
    live = page_.player({"stanje": "govori", "danas": [], "datoteke": []}, cyr=False, live="dQw4w9WgXcQ", tz=TZ)
    assert '<div class="cc" hidden aria-hidden="true" data-delay="0">' in live and "nije citat" in live
    assert "function captions()" in page_.SCRIPT and 'func: "seekTo"' in page_.SCRIPT  # set back when a phrase comes late


def test_the_groups_time_in_the_debate_is_an_estimate_by_one_rule():
    """22 Nov 2026, readers asked how much time each party has left: five hours for the groups by their MPs (art. 97),
    replies and points of order (two minutes at most) left out, the debate in detail counted afresh (art. 158)."""
    from uzivo import page as page_
    from uzivo.vreme import CHAIR_MORE, TOTAL, groups_time
    start = 1795089600
    turn = lambda at, sec, g: {"od": start + at, "do": start + at + sec, "sekundi": sec, "lista": g}
    seats = {"Studentska lista": 140, "Aleksandar Vučić - Srbija pobeđuje": 102}
    turns = [turn(100, 600, "Studentska lista"), turn(800, 120, "Studentska lista"),      # a reply: not counted
             turn(1000, 900, "Aleksandar Vučić - Srbija pobeđuje"), turn(2000, 1200, ""),  # the Government: not a group
             turn(3500, 300, "*")]
    g = groups_time(item=4, start=start, seats=seats, turns=turns, events=[], now=start + 4000)
    sl, av = g["grupe"]
    assert sl["lista"] == "Studentska lista" and sl["ima"] == round(TOTAL * 140 / 242) and sl["potroseno"] == 600
    assert sl["govora"] == 1 and av["potroseno"] == 900 and not g["pojedinosti"]
    # a debate closed and another opened: the debate in detail, counted from its opening, the chairs' 15 minutes more
    events = [{"t": start + 1950, "vrsta": "Pretres zaključen"}, {"t": start + 3000, "vrsta": "Pretres otvoren"}]
    d = groups_time(item=4, start=start, seats=seats, turns=turns + [turn(3100, 400, "Studentska lista")], events=events,
                    now=start + 4000)
    assert d["pojedinosti"] and d["grupe"][0]["potroseno"] == 400 and d["grupe"][0]["ima"] == sl["ima"] + CHAIR_MORE
    assert groups_time(item=4, start=start, seats=seats, turns=[turn(100, 90, "Studentska lista")], events=[], now=start + 200) is None
    html = page_._group_time({"vreme_grupa": g}, cyr=False, site="https://zailiprotiv.rs/")
    assert "Vreme poslaničkih grupa za 4. tačku" in html and "procena" in html and "ostalo oko" in html
    assert 'href="https://zailiprotiv.rs/poslovnik-clanovi#pojam-vreme-rasprave"' in html and "član 97" in html
    assert "Време посланичких група" in page_._group_time({"vreme_grupa": g}, cyr=True, site="https://zailiprotiv.rs/")
    assert page_._group_time({}, cyr=False) == ""
