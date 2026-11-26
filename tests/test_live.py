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
    assert "<title>Skupština uživo: prenos i ko sada govori · Za ili Protiv</title>" in lat and "Lista za primer" in lat
    assert '<meta name="description" content="Prenos Narodne skupštine uživo: ko je sada za govornicom i koliko dugo, prepis i snimak svakog govora. Deo sajta Za ili Protiv.">' in lat
    assert "<h1>Za ili Protiv: Jutrić, Kafica, Skupštinica</h1>" in lat  # the hook stays on the page itself
    cyr = page(snap, cyr=True, site="https://zailiprotiv.rs/", tz=TZ)
    assert "Петар Петровић" in cyr and "https://zailiprotiv.rs/cir/poslanik/petrovic-petar" in cyr
    assert "<title>Скупштина уживо: пренос и ко сада говори · За или Против</title>" in cyr
    assert "Пренос Народне скупштине уживо: ко је сада за говорницом и колико дуго, препис и снимак сваког говора. Део сајта За или Против." in cyr
    # the Rules of Procedure, always under the day (20 Nov 2026: the new convocation's readers asked to find it)
    assert 'href="https://zailiprotiv.rs/poslovnik-clanovi#pojmovi"' in lat and ">Poslovnik<" in lat
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
    assert "youtube.com/watch?v=abc&amp;t=595s" in html and 'class="time tp"' in html
    # The broadcast over: its YouTube video goes private, so no link into it (18 Nov 2026).
    t.tick(now=day1 + 200)
    assert all(d["snimak"] is None for d in t.snapshot(now=day1 + 200)["danas"])
    # The next day, before the broadcast: the last sitting day's list, with its date.
    day2 = datetime(2026, 11, 19, 9, 0, tzinfo=TZ).timestamp()
    t2 = Tracker(str(path), tz="Europe/Belgrade")
    assert t.snapshot(now=day1 + 86400)["ranije"]  # past midnight, before any frame: no longer "today"
    snap = t2.snapshot(now=day2)
    assert snap["dan"] == "2026-11-18" and [d["ime"] for d in snap["danas"]] == ["Nikolić Nina", "Petrović Petar"]
    assert "Poslednji dan sednice, 18. novembar 2026." in fragment(snap, cyr=False, site="", tz=TZ)
    # The broadcast on and the chair alone has spoken: today, with nobody yet, not the last day (24 Nov 2026).
    t2.observe(None, now=day2)
    snap = t2.snapshot(now=day2)
    assert snap["dan"] == "2026-11-19" and not snap["ranije"] and snap["danas"] == []
    html = fragment(snap, cyr=False, site="", tz=TZ)
    assert "Poslednji dan sednice" not in html and "Danas još niko nije prepoznat u prenosu." in html
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


def test_a_slow_sound_does_not_hold_up_the_frames(monkeypatch, tmp_path):
    """The sound-only track's segments hang: the frames go on, and the sound that comes is kept in order with the
    moment its own frame was read."""
    import threading
    import time
    import urllib.error
    from uzivo import stream
    let_go, kept = threading.Event(), []
    frames: list[tuple[int, float]] = []
    mine = lambda path: Path(path).read_bytes()[:1] == b"s"  # not what an earlier test's reading was still at  # noqa: E731

    def get(self, url, timeout=20):
        if url == "https://v/zvuk":
            time.sleep(0.2)
            return _PLAYLIST.replace(b"https://v/", b"https://z/")
        if url.startswith("https://z/"):
            let_go.wait(20)
            return b"s" * 2000
        if "/sq/" not in url:
            return _PLAYLIST
        # the picture's segments once the sound's playlist is in: the sound of one read before that is not known
        if int(url.split("/sq/")[1].split("/")[0]) > 14 or not self._sound_segments:
            raise urllib.error.HTTPError(url, 404, "not yet", None, None)
        return b"x" * 2000
    monkeypatch.setattr(config, "FRAME_PATH", str(tmp_path / "frame" / "now.jpg"))
    monkeypatch.setattr(stream.HlsPoller, "_get", get)
    monkeypatch.setattr(stream, "_ffmpeg_last_frame", lambda path: frames.append((len(frames), time.time())))
    monkeypatch.setattr(stream.prepis, "on", lambda: True)
    monkeypatch.setattr(stream.slusaj, "on", lambda: True)
    monkeypatch.setattr(stream.prepis, "keep", lambda path, at, dur, program=None: mine(path) and kept.append(at))
    added = []
    monkeypatch.setattr(stream.slusaj.PLAYLIST, "add", lambda path, dur, n, at, video="": mine(path) and added.append(n))
    p = stream.HlsPoller("https://v/playlist", {}, "https://v/zvuk")
    try:
        end = time.time() + 15
        while len(frames) < 4 and time.time() < end:
            time.sleep(0.02)
        assert len(frames) == 4 and not kept  # 11-14 read while no sound has come
        let_go.set()
        end = time.time() + 15
        while len(added) < 4 and time.time() < end:
            time.sleep(0.02)
        assert added == [11, 12, 13, 14] and kept == sorted(kept)
        assert all(0 <= at - f[1] < 2 for at, f in zip(kept, frames))
    finally:
        let_go.set()
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


def test_an_earlier_copy_of_the_services_own_day_does_not_take_its_place(tmp_path):
    """24 Nov 2026: after the sitting the page listed the site's copy of the day taken at 17:56, without the turns since and
    with a name corrected since; the data run that brings a new copy takes hours."""
    from datetime import datetime
    from uzivo.names import Person, person_key
    t = Tracker(str(tmp_path / "stanje.json"), tz="Europe/Belgrade")
    day1 = datetime(2026, 11, 24, 17, 0, tzinfo=TZ).timestamp()
    a = Person(person_key("Petrović Petar"), "Petrović Petar", "petrovic-petar", "PG A")
    b = Person(person_key("Marković Marko"), "Marković Marko", "markovic-marko", "PG B")
    for i in range(3):
        t.observe(a, "PG A", now=day1 + 5 * i)
    for i in range(3):
        t.observe(b, "PG B", now=day1 + 3600 + 5 * i)
    t.tick(now=day1 + 3900)
    turn = {"ime": "Petrović Petar", "adresa": "petrovic-petar", "grupa": "PG A", "uloga": "", "od": int(day1), "do": int(day1 + 10),
            "okvira": 3, "video": "", "snimak": None}
    t.use_recording({"dan": "2026-11-24", "izvor": "uzivo", "govori": [turn]})
    snap = t.snapshot(now=day1 + 3900)
    assert not snap["snimak"] and [d["ime"] for d in snap["danas"]] == ["Marković Marko", "Petrović Petar"]
    # the archive's files the site knows stay: a turn begun inside one has its place in it, the others no link
    part = {"url": "https://arhiva.example/a.mp4", "od": int(day1 + 3000), "trajanje": 1200}
    t.use_recording({"dan": "2026-11-24", "izvor": "uzivo", "govori": [turn], "datoteke": [part]})
    snap = t.snapshot(now=day1 + 3900)
    assert snap["datoteke"] == [part] and not snap["snimak"]
    marko, petar = snap["danas"]
    assert marko["datoteka"] == part["url"] and marko["snimak"] == 600 and not petar.get("datoteka") and petar["snimak"] is None
    from uzivo.page import fragment
    assert 'data-file="https://arhiva.example/a.mp4"' in fragment(snap, cyr=False, site="", tz=TZ)
    t.use_recording({"dan": "2026-11-24", "izvor": "uzivo", "govori": [turn]})
    nxt = datetime(2026, 11, 25, 8, 0, tzinfo=TZ).timestamp()
    assert len(Tracker(str(tmp_path / "stanje.json"), tz="Europe/Belgrade").snapshot(now=nxt)["danas"]) == 2  # the next morning too, kept across a restart
    later = {**turn, "ime": "Marković Marko", "adresa": "markovic-marko", "od": int(day1 + 3600), "do": int(day1 + 3610)}
    t.use_recording({"dan": "2026-11-24", "izvor": "uzivo", "govori": [turn, later]})  # a copy that has the whole day: as before
    assert t.snapshot(now=day1 + 3900)["snimak"]
    t.use_recording({"dan": "2026-11-24", "izvor": "snimak", "govori": [turn]})  # read from the recording: another source
    assert t.snapshot(now=day1 + 3900)["snimak"]


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
    assert 'data-yt="abcdefghijk"' in live and 'data-e="mikrofon.pusti"' in live and "slika.png" not in live and "fx-calm" in live
    assert "<iframe" not in live and "youtube" not in live
    assert "Против" in player({**day, "stanje": SPEAKING}, cyr=True, live="abcdefghijk")
    assert " src=" not in live and "fx-sp" not in live  # our mark alone, whoever speaks
    assert player({**day, "danas": []}, cyr=False) == ""
    frag = fragment(day, cyr=False, site="", tz=TZ)
    assert 'data-file="https://arhiva.videonet.co.rs/a.mp4" data-t="7"' in frag  # each turn opens in the player
    page_ = page(day, cyr=False, site="", tz=TZ, live="")
    assert 'id="screen"' in page_ and "youtube-nocookie.com/embed/" in page_  # the address is only in the script
    assert " data-api=" not in page_
    assert 'data-api="https://glasovi.zailiprotiv.rs"' in page(day, cyr=False, site="", tz=TZ, api="https://glasovi.zailiprotiv.rs")
    assert " data-api=" not in page(day, cyr=False, site="", tz=TZ, api='x" onload="y')


def test_the_broadcast_started_after_the_sound_is_counted_once(tmp_path):
    """25 Nov 2026: the button that offers the picture while the sound plays counts as the first ▶ does, once per page
    opened whichever way the broadcast was started. The player's own script, on a page of three buttons."""
    import json
    import shutil
    import subprocess
    from pathlib import Path
    node = shutil.which("node")
    if not node:
        pytest.skip("no node")
    js = (Path(__file__).parents[1] / "src/zailiprotiv/templates/mikrofon.js").read_text(encoding="utf-8")
    harness = """
const el = (attrs = {}) => ({ attrs, innerHTML: "", textContent: "", hidden: false, classList: { add() {}, toggle() {} },
  getAttribute(k) { return k in attrs ? attrs[k] : null; }, setAttribute(k, v) { attrs[k] = v; }, removeAttribute(k) { delete attrs[k]; },
  hasAttribute(k) { return k in attrs; }, appendChild() {}, insertAdjacentHTML() {}, scrollIntoView() {}, contains() { return false; },
  querySelector() { return el(); }, addEventListener() {}, play() {},
  closest(s) { return s.split(",").some(x => x.trim().slice(1, -1) in attrs) ? this : null; } });
const screen = el(), sent = [];
const facade = el({ "data-yt": "abcdefghijk", "data-t": "0", "data-e": "mikrofon.pusti", "data-text": "▶" });
const swap = el({ "data-uzivo": "/slusaj/z.m3u8" });
let press;
globalThis.document = { getElementById: i => i === "screen" ? screen : null, createElement: () => el(), querySelectorAll: () => [],
  querySelector: s => s === ".listen-live" ? swap : s.includes("facade") ? facade : null, documentElement: { lang: "sr" },
  body: { getAttribute: () => "https://glasovi.example" },
  addEventListener: (k, f) => { if (k === "click" && !press) press = f; } };
globalThis.location = { origin: "https://" + HOST, hostname: HOST, href: "" };
globalThis.fetch = (u, o) => { sent.push(JSON.parse(o.body).e); return Promise.resolve(); };
globalThis.setInterval = () => 0;
const click = b => press({ target: b, preventDefault() {} });
SCRIPT
const out = [];
for (const b of ORDER) { click(b); out.push([...sent]); }
console.log(JSON.stringify(out));
"""
    def ran(order, host="mikrofon.zailiprotiv.rs"):
        f = tmp_path / "p.cjs"
        f.write_text(harness.replace("SCRIPT", js).replace("ORDER", order).replace("HOST", json.dumps(host)), encoding="utf-8")
        r = subprocess.run([node, str(f)], capture_output=True, text=True, encoding="utf-8")
        assert r.returncode == 0, r.stderr
        return json.loads(r.stdout)
    both = ["mikrofon.slusaj", "mikrofon.pusti"]
    assert ran("[swap, swap, swap, swap]") == [both[:1], both, both, both]  # sound, picture, sound, picture
    assert ran("[facade, swap, swap]") == [both[1:], both[::-1], both[::-1]]  # the first ▶, the sound, the picture again
    for host in ("127.0.0.1", "localhost", "", "mikrofon.zailiprotiv.rs.example"):  # a test's page, one from disk, another's
        assert ran("[facade, swap, swap]", host) == [[], [], []]


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
    from zailiprotiv import publish
    assert len(publish.ANALYTICS.findall(html)) == 1 and "62b7969c87164343897a48605c9267c0" in html  # the site's own form
    assert "cloudflareinsights" not in publish.ANALYTICS.sub("", html)
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
    assert html.count("kako-racunamo#posetioci") == 1  # what is counted is on the method page, linked in one place
    assert '<a href="https://s.rs/cir/kako-racunamo#posetioci">Бројач сајта</a> збраја по дану' in foot(
        page(snap, cyr=True, site="https://s.rs/", tz=TZ, api="https://glasovi.zailiprotiv.rs"))
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


def test_the_speaker_has_the_name_and_the_clock_and_no_box_under_them():
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
    # the box under the speaker is off (24 Nov 2026, the maintainer); the name is the way to the MP's page
    assert '<a href="https://zailiprotiv.rs/poslanik/petrovic-petar">' in html
    assert 'class="o"' not in html and "2. put za govornicom" not in html and "sazivi 13–14" not in html
    assert 'id="t1794920610"' in html and 'class="st-c"' not in html  # the strip and the cards are off since 24 Nov 2026
    t.observe(marko, now=now + 840)
    t.observe(marko, now=now + 845)
    html = fragment(t.snapshot(now=now + 846), cyr=True, site="https://zailiprotiv.rs/", tz=TZ)
    assert "/cir/poslanik/jovanovic-marko" in html and "Лекар" not in html


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
    assert "Ana Anić" in html  # the strip of the day, which said "Vlada i gosti", is off since 24 Nov 2026


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
    assert title == "Skupština uživo: ko sada govori" and "Petrović" not in text  # a card is kept: nobody's name on it
    assert og_text({**snap, "stanje": UNKNOWN, "sada": None}, cyr=False, tz=TZ) == (title, text)
    html = page(snap, cyr=False, site="https://zailiprotiv.rs/", tz=TZ, url="https://mikrofon.zailiprotiv.rs/")
    assert 'property="og:image" content="https://mikrofon.zailiprotiv.rs/slika.png?v=' in html and 'class="hl"' not in html  # off since 24 Nov 2026
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
    assert "tiles" not in html and "Danas su govorili" not in html and "Svi govori, redom" in html  # off since 24 Nov 2026
    assert "st-open" not in html and "Najviše vremena" not in html  # the cards and the headline are off since 24 Nov 2026 (the maintainer)
    assert 'class="th">' in html and html.index("<li class=\"th\">") < html.index('id="t')  # the turns under the hour they began in


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
    html = fragment({**t.snapshot(), "stanje": "nepoznato"}, cyr=False, site="https://zailiprotiv.rs/", tz=TZ)
    assert 'class="agenda"' in html and "2 od 4 tačaka gotovo" in html and "Izbor potpredsednika" in html
    assert '<span class="st-h">u toku:</span> 3. Izbor potpredsednika' in html and "u toku · po rečima" in html
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


def test_the_transcript_is_corrected_after_it_is_out(tmp_path, monkeypatch):
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
    assert w.step(now=now + 62) is True
    assert "Poslovnik" in hints[0] and "Petar Petrović" in hints[0]  # the terms and today's speakers, told to Whisper
    assert next(iter(t.said.values())) == "Petrovic je rekao oktober."  # kept as written
    assert t.snapshot(now=now + 63)["sada"]["prepis"] == "Petrović je rekao oktobar."  # shown corrected
    t.observe(None, now=now + 100)
    t.observe(None, now=now + 130)
    while w.step(now=now + 131):
        pass
    page_ = transcript_page(t.transcript(), cyr=False, site="https://zailiprotiv.rs/", tz=TZ)
    assert "Petrović je rekao oktobar." in page_
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
    # agenda, which links its page); with nothing heard, its sentences are the list
    days = html.split('<section class="steps-sec">')[1].split("</section>")[0]
    assert "izabrala potpredsednike" not in days and "Zvanično" not in html
    assert days.split('<ol class="steps">')[1].count("<li") == 2
    assert "Zapis sednice na sajtu Skupštine" not in html and "kvorum, replika" not in html  # off, 25 Nov 2026
    assert '<p class="dl-foot rk-f"><a class="rk-l" href="https://zailiprotiv.rs/poslovnik-clanovi#pojmovi">' in days  # the card stays
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


def _break(tmp, *, pause=True, minutes=60, after=(0, 20), words=12):
    """A day heard: the chair from 10:00 to 10:07, a break said, a silence, and speech `after` seconds past its end."""
    from datetime import datetime as dt_
    start = dt_(2026, 11, 24, 10, 0, tzinfo=TZ).timestamp()
    said = {f"p{int(start + 20 * i)}": "rec " * 20 for i in range(21)}
    said[f"p{int(start + 430)}"] = "Zadok, ne budućić."  # the odd sound in a break: no speech
    end = start + 400 + 20  # the last piece with speech, and its twenty seconds
    back = end + 60 * minutes
    said.update({f"p{int(back + a)}": "rec " * words for a in after})
    events = [{"t": int(start + 415), "vrsta": "Pauza", "tekst": "proglašavam pauzu", "izvor": "model"}] if pause else []
    return said, events, int(end), back


def test_the_live_page_says_less_and_its_folds_are_closed(monkeypatch):
    """24 Nov 2026, the maintainer: these texts off the page, the agenda closed; what loads and when, and what of a
    reader is kept, stays told under "Kako ovo radi" (principle 5)."""
    from uzivo import page as page_, slusaj
    monkeypatch.setattr(config, "LISTEN_PUBLIC", True)
    monkeypatch.setattr(slusaj, "fresh", lambda now: True)
    monkeypatch.setattr(slusaj, "address", lambda: "https://zvuk.example/z.m3u8")
    snap = {**Tracker(None, "Europe/Belgrade").snapshot(), "stanje": "nepoznato"}
    html = page_.page(snap, cyr=False, site="https://zailiprotiv.rs/", tz=TZ, api="https://glasovi.zailiprotiv.rs", push_key="k", live="abc")
    top, how = html.split('<details class="how">', 1)
    for words in ("učitava se tek na klik", "Samo zvuk je naš", "kod nas ostaje samo adresa"):
        assert words not in top and words in how
    assert "🎧 <span>Slušaj<small>radi i sa zaključanim telefonom</small></span>" in top  # 25 Nov 2026, the maintainer
    assert "ne vidi u potpisu" not in html and "listen-live" in top and "Isključi obaveštenja" in top
    snap["provereno"] = 1795515045
    assert 'id="checked"' not in fragment(snap, cyr=False, site="https://zailiprotiv.rs/", tz=TZ)  # nothing above it
    now = {"ime": "Petrović Petar", "adresa": "petrovic-petar", "od": 1795515000, "do": 1795515040, "sekundi": 40, "lista": "PG A"}
    assert 'id="checked"' in fragment({**snap, "stanje": "govori", "sada": now}, cyr=False, site="https://zailiprotiv.rs/", tz=TZ)


def test_the_end_of_a_long_break_is_found_from_speech(tmp_path):
    from uzivo.obavesti import resumed
    said, events, end, back = _break(tmp_path)
    assert resumed(said, [], events, back + 45) == end  # the chair speaks again, whatever the words
    assert resumed(said, [], events, back - 60) == 0  # still silent
    assert resumed(said, [], events, back + 3600) == 0  # long ago: no news
    assert resumed(*(lambda b: (b[0], [], b[1]))(_break(tmp_path, pause=False)), back + 45) == 0  # no break said
    assert resumed(*(lambda b: (b[0], [], b[1]))(_break(tmp_path, after=(0,))), back + 45) == 0  # one piece is not sure yet
    assert resumed(*(lambda b: (b[0], [], b[1]))(_break(tmp_path, words=3)), back + 45) == 0  # a word or two in the hall
    short = _break(tmp_path, minutes=10)
    assert resumed(short[0], [], short[1], short[3] + 45) == 0  # ten minutes: nobody is woken
    quiet = {k: v for k, v in said.items() if int(k[1:]) < back}
    turn = {"start": back + 5, "seen": back + 20, "n": 3, "role": "PG A"}
    assert resumed(quiet, [turn], events, back + 30) == end  # an MP read at the rostrum is enough
    assert resumed(quiet, [{**turn, "role": "", "n": 1}], events, back + 30) == 0  # noise read as a name is not
    long = {"start": end - 60, "seen": end + 3000, "n": 600}  # an MP speaking through: no silence at all
    assert resumed(said, [long], events, back + 45) == 0


def test_the_bell_hears_the_end_of_a_break_from_the_tracker_itself(tmp_path):
    """24 Nov 2026: the tracker had a `heard` already (a voice's turn), and the bell's failed on every look; the test
    with a stand-in for the tracker did not see it."""
    from datetime import datetime as dt_
    from uzivo.obavesti import Bell
    posts = []
    said, events, end, back = _break(tmp_path)
    t = Tracker(str(tmp_path / "stanje.json"), "Europe/Belgrade")
    t.day, t.said, t.events = "2026-11-24", said, events
    bell = Bell(str(tmp_path / "o.json"), token="t", api="https://glasovi.example", post=lambda od, *w: posts.append((od, *w)) or {"sent": 1})
    assert bell.heard(t, dt_.fromtimestamp(back + 45, TZ), wait=True) and posts == [(0, "nastavak", 1)]


def test_the_end_of_each_break_is_told_once_whatever_their_number(tmp_path):
    from datetime import datetime as dt_
    from uzivo.obavesti import Bell
    posts = []
    path = str(tmp_path / "o.json")
    bell = lambda: Bell(path, token="t", api="https://glasovi.example", post=lambda od, *w: posts.append((od, *w)) or {"sent": 1})
    said, events, end, back = _break(tmp_path)

    class Heard:
        def day_heard(self):
            return said, [], events
    at = lambda s: dt_.fromtimestamp(back + s, TZ)
    b = bell()
    assert b.heard(Heard(), at(45), wait=True) and posts == [(0, "nastavak", 1)]
    assert not b.heard(Heard(), at(75), wait=True)  # the same break: once
    assert not bell().heard(Heard(), at(90), wait=True) and len(posts) == 1  # a restart of the service too
    again = back + 4 * 3600
    said.update({f"p{int(back + 60 + 20 * i)}": "rec " * 12 for i in range(5)})
    said.update({f"p{int(again + 20 * i)}": "rec " * 12 for i in range(3)})
    events.append({"t": int(back + 150), "vrsta": "Pauza", "tekst": "", "izvor": "model"})
    assert bell().heard(Heard(), dt_.fromtimestamp(again + 50, TZ), wait=True) and posts[-1] == (0, "nastavak", 2)
    third = again + 2 * 3600
    said.update({f"p{int(third + 20 * i)}": "rec " * 12 for i in range(3)})
    events.append({"t": int(again + 70), "vrsta": "Pauza", "tekst": "", "izvor": "model"})
    assert bell().heard(Heard(), dt_.fromtimestamp(third + 50, TZ), wait=True) and posts[-1] == (0, "nastavak", 3)  # no limit
    off = Bell(str(tmp_path / "x.json"), token="", api="https://glasovi.example", post=lambda *a: posts.append(a) or {})
    assert not off.heard(Heard(), at(45), wait=True)  # no token (a test of the service): never


def test_the_page_offers_the_notification_and_its_worker_writes_it():
    from uzivo.page import service_worker
    snap = {"stanje": "nema_prenosa", "provereno": 0, "sada": None, "danas": [], "dan": "2026-11-20"}
    html = page(snap, cyr=False, site="https://zailiprotiv.rs/", tz=TZ, api="https://glasovi.zailiprotiv.rs/", push_key="BKEY")
    assert 'data-key="BKEY"' in html and "Obavesti me kad sednica počne" in html
    assert 'data-key="' not in page(snap, cyr=False, site="https://zailiprotiv.rs/", tz=TZ, push_key="BKEY")  # no counter: no offer
    sw = service_worker(True, "BKEY", "https://glasovi.zailiprotiv.rs/")
    assert "Седница је настављена" in sw and 'k.vrsta === "nastavak"' in sw
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
    assert on.count('class="add-home"') == 1 and on.index('class="add-home"') < on.index('id="deo"')  # pills under the player


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
    assert len(measures) == 2 and "Opomena" in measures[1] and "Bakiću" in measures[1] and "mk-mera-teska" in measures[0]
    assert '<i aria-hidden="true">3</i>' in html and "Prelazak na 3. tačku dnevnog reda" in html and "Pretres je otvoren" in html
    assert '<details class="chip"><summary>automatski · može da pogreši</summary>' in html and "Claude Haiku" in html
    assert "Aleksandar Čupić" in page_._steps({**snap, "sazetak": None}, cyr=False, tz=TZ)  # no summary: the step tells it
    assert "Одлука" in page_._steps(snap, cyr=True, tz=TZ)


def test_the_notice_of_when_the_assembly_goes_on_is_said_on_top(monkeypatch):
    """22 Nov 2026, the maintainer: say that part as when the Assembly goes on."""
    from datetime import datetime
    from uzivo import page as page_
    monkeypatch.setattr(page_, "_now", lambda: datetime(2026, 11, 23, 12, 0, tzinfo=TZ))  # said only until that hour
    assert page_._resumes("Narodna skupština nastavlja sa radom u utorak, 24. novembra 2026. godine, u 10.00 časova.") == "u utorak, 24. novembra, u 10.00"
    assert page_._resumes("Narodna skupština je izabrala predsednika.") == ""
    snap = {"stanje": "nema_prenosa", "provereno": 1, "sada": None, "sazvano": None, "bez_potpisa": None, "dan": "2026-11-19",
            "ranije": True, "danas": [], "dnevni_red": None, "hronika": [],
            "obavestenja": [{"od": "2026-11-20", "do": "2026-11-24", "tekst": "Narodna skupština nastavlja sa radom u utorak, 24. novembra 2026. godine, u 10.00 časova.",
                             "izvor": "sajt Narodne skupštine", "url": "https://www.parlament.gov.rs/x", "adresa": ""}]}
    html = fragment(snap, cyr=False, site="https://zailiprotiv.rs/", tz=TZ)
    assert "Sednica sutra u 10 h" in html and "Skupština nastavlja sa radom u utorak, 24. novembra, u 10.00." in html
    assert "<span>uto</span><b>24</b><span>nov</span>" in html and 'class="st-bell"' in html and 'class="news"' not in html
    for now, said in ((datetime(2026, 11, 24, 9, 0, tzinfo=TZ), "Sednica danas u 10 h"),
                      (datetime(2026, 11, 20, 9, 0, tzinfo=TZ), "Sednica u utorak u 10 h")):
        monkeypatch.setattr(page_, "_now", lambda now=now: now)
        assert said in fragment(snap, cyr=False, site="https://zailiprotiv.rs/", tz=TZ)
    assert "Седница у уторак у 10 ч" in fragment(snap, cyr=True, site="https://zailiprotiv.rs/", tz=TZ)
    monkeypatch.setattr(page_, "_now", lambda: datetime(2026, 11, 23, 12, 0, tzinfo=TZ))
    assert "Скупштина наставља са радом у уторак, 24. новембра, у 10.00." in fragment(snap, cyr=True, site="", tz=TZ)
    assert 'class="news"' in fragment({**snap, "stanje": "govori", "sada": None}, cyr=False, site="", tz=TZ)  # on the air before that hour: as it is
    monkeypatch.setattr(page_, "_now", lambda: datetime(2026, 11, 24, 11, 0, tzinfo=TZ))  # its hour come: no news, whoever is on
    for stanje in ("govori", "nema_prenosa"):
        assert 'class="news"' not in fragment({**snap, "stanje": stanje, "sada": None}, cyr=False, site="", tz=TZ)

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
    assert '<div class="status st-card st-live"><p class="st-tile"><i aria-hidden="true"></i><span>Uživo</span></p>' in live
    assert '<p class="st-when"><span class="st-h">u toku:</span> 2. Druga</p>' in live
    assert '<details class="agenda" id="dnevni-red">' in live and "hero-cta" not in live
    off = page_({**snap, "stanje": "nema_prenosa", "datoteke": [{"url": "https://x/1.mp4", "od": 1795089600, "trajanje": 60},
                                                                 {"url": "https://x/2.mp4", "od": 1795093200, "trajanje": 60}]},
                cyr=True, site="https://zailiprotiv.rs/", tz=TZ)
    assert "у току" not in off  # 25 Nov 2026: under "Ne zaseda" nothing is said to be under way, nor in the agenda
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
    assert 'main:has(#deo[data-stanje="nema_prenosa"]) > .pills { order: 4; }' in css


def test_the_speaker_stands_beside_the_small_picture_and_the_picture_stays_on_top():
    """22 Nov 2026, the maintainer: the picture kept small on top while the page is read, with a way to put it back and
    the speaker beside it; not over the picture itself since 24 Nov 2026."""
    from uzivo.page import player, SCRIPT, CSS
    snap = {"stanje": "govori", "danas": [], "datoteke": []}
    live = player(snap, cyr=False, live="dQw4w9WgXcQ", tz=TZ)
    assert '<div class="stage"><div class="screen" id="screen">' in live and '<p class="on-air" hidden' in live
    assert 'class="mini-x" hidden aria-label="Vrati snimak na njegovo mesto"' in live
    day = {"stanje": NO_STREAM, "datoteke": [{"url": "https://arhiva.videonet.co.rs/a.mp4", "od": 0, "trajanje": 60}], "danas": []}
    archive = player(day, cyr=False, tz=TZ)
    assert 'class="mini-x"' in archive and "on-air" not in archive  # the archive's speaker is not the part's
    assert ".player:not(.mini) .on-air { display: none; }" in CSS  # nothing over the picture
    # on a phone pinned as wide as the screen, the speaker in one line under it (24 Nov 2026, the maintainer)
    assert 'matchMedia("(max-width: 720px)")' in SCRIPT and ".player.mini .screen { grid-column: 1 / -1; width: 100%" in CSS
    assert '<span class="oa-rk">' in live
    assert "function past()" in SCRIPT and "&& !past())" in SCRIPT  # not over an earlier moment's picture
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


def test_an_election_an_mp_speaks_of_is_no_step_and_the_chairs_is():
    """24 Nov 2026: an MP told what the proposal of the committees held, and the page said there was an election."""
    from uzivo.steps import model_steps
    base = 1795510000
    ev = lambda t, kind, text, **more: {"t": base + t, "vrsta": kind, "tekst": text, "izvor": "model", "vise": more}
    said = "Saopštili da u odboru za spoljne poslove gde su izabrali gospodina Mavrića i Saru Valentika."
    snap = {"provereno": base + 4000, "danas": [{"od": base + 100, "do": base + 700}], "sada": None, "dnevni_red": None,
            "hronika": [ev(300, "Izbor", said, ko="gospodina Mavrića i Saru Valentika")]}
    assert model_steps(snap) == []
    chair = ev(720, "Izbor", "Narodna skupština je izabrala Aleksandra Čupića.", ko="Aleksandar Čupić")
    assert [s["naslov"] for s in model_steps({**snap, "hronika": [chair]})] == ["Izbor"]
    edge = ev(690, "Izbor", "Narodna skupština je izabrala Aleksandra Čupića.", ko="Aleksandar Čupić")
    assert len(model_steps({**snap, "hronika": [edge]})) == 1  # a turn's end is known to some seconds only
    measure = ev(300, "Mera predsedavajućeg", "Izričem vam opomenu.", napomena="opomena")
    assert len(model_steps({**snap, "hronika": [measure]})) == 1  # a measure comes in the middle of a turn
    on = {**snap, "danas": [], "sada": {"od": base + 100}, "hronika": snap["hronika"]}
    assert model_steps(on) == []  # the turn still on


def test_an_outlined_caption_counts_only_with_the_mps_own_list_under_the_name():
    """24 Nov 2026: the caption stood higher, its letters ringed, and was cut in two; a name counts with its list."""
    from uzivo.caption import Caption, sure
    from uzivo.names import Person, Roster
    people = [Person("bakic jovo", "Bakić Jovo", "bakic-jovo", "Studentska lista"),
              Person("aleksandar vucic", "Vučić Aleksandar", "vucic-aleksandar", "Aleksandar Vučić - Srbija pobeđuje")]
    roster = Roster(people)
    roster.current = {"bakic-jovo", "vucic-aleksandar"}
    read_ = lambda name, role: sure(Caption(name, role, False, False), roster, 0.8)
    assert read_("Јово Еакић", "Ступентека писта").slug == "bakic-jovo"  # as read from the broadcast
    assert read_("Александар Вучић.", "Александар Вучић - Србија побеђуј").slug == "vucic-aleksandar"
    assert read_("Јово Бакић", "Александар Вучић - Србија") is None  # another's list: no such caption
    assert read_("Јово Бакић", "") is None and read_("", "Студентска листа") is None
    assert read_("Марић Лазар", "Студентска листа") is None  # not a sitting MP's name with their list
    assert read_("Александар Вучић", 'Студентска листа') is None
    # a list read alone names no one: the list's line of another's caption was read as Vučić, the name cut off
    from uzivo.caption import who
    assert who(Caption("Александар Вучић - Срб", "", False, False), roster, 0.8) is None
    assert who(Caption("Јово Бакић", "", False, False), roster, 0.8).slug == "bakic-jovo"
    assert who(Caption("Александар Вучић", "Александар Вучић - Србија побеђује", True, True), roster, 0.8).slug == "vucic-aleksandar"


def test_a_caption_of_seconds_names_the_speaker_and_the_turn_goes_on():
    """24 Nov 2026: the caption stood ten seconds at a turn's start; the turn must not end with it."""
    now = 1795519000.0
    t = Tracker(None, "Europe/Belgrade")
    t.roster = ROSTER
    marko = next(p for p in ROSTER.people if p.slug == "markovic-marko")
    t.observe(None, now=now)
    t.heard(marko, "prepis", now + 2, now + 2)  # the chair's words
    t.heard(marko, "potpis", now + 10, now + 10)  # his caption
    for s_ in range(15, 120, 5):
        t.observe(None, now=now + s_)
    cur = t.open_turn()
    assert cur["slug"] == "markovic-marko" and cur["izvor"] == "potpis" and len(t.turns_now()) == 1
    assert "by_potpis" not in __import__("uzivo.texts", fromlist=["TEXT"]).TEXT  # no word on how: a caption said it


def test_a_steps_time_leads_to_its_moment():
    """24 Nov 2026, the maintainer: a press on the reprimand's time leads to that part of the broadcast."""
    from uzivo.steps import model_steps
    base = 1795510000
    ev = {"t": base + 5000, "vrsta": "Mera predsedavajućeg", "tekst": "Ja vam izričem opomenu.", "izvor": "model", "vise": {"napomena": "opomena"}}
    snap = {**Tracker(None, "Europe/Belgrade").snapshot(), "stanje": "govori", "provereno": base + 9000, "hronika": [ev],
            "prenos": {"video": "dQw4w9WgXcQ", "od": base}}
    assert model_steps(snap)
    html = fragment(snap, cyr=False, site="https://zailiprotiv.rs/", tz=TZ)
    assert '<a class="time" href="https://www.youtube.com/watch?v=dQw4w9WgXcQ&amp;t=5000s" data-yt="dQw4w9WgXcQ" data-t="5000"' in html
    none = fragment({**snap, "prenos": None}, cyr=False, site="https://zailiprotiv.rs/", tz=TZ)
    assert '<span class="time">' in none and 'class="time" href' not in none  # nothing to lead to
    part = {"url": "https://arhiva.videonet.co.rs/a.mp4", "od": base + 4000, "trajanje": 3000}
    arch = fragment({**snap, "stanje": "nema_prenosa", "prenos": None, "datoteke": [part]}, cyr=False, site="https://zailiprotiv.rs/", tz=TZ)
    assert 'data-file="https://arhiva.videonet.co.rs/a.mp4" data-t="1000"' in arch


def test_a_decisions_time_leads_to_its_moment_as_a_steps_does():
    """25 Nov 2026, the maintainer: "na vremenskoj oznaci stavi link da prebaci na taj deo videa". The day's decisions too,
    to the minute they carry, wherever a step's time leads; the time alone where nothing holds it."""
    from datetime import datetime
    from uzivo.page import _at_clock
    noon = datetime(2026, 11, 25, 11, 58, tzinfo=TZ).timestamp()
    assert _at_clock("2026-11-25", "11:58", TZ) == noon and _at_clock("2026-11-25", "00:30", TZ) == noon + (12 * 60 + 32) * 60
    assert not _at_clock("2026-11-25", "", TZ) and not _at_clock("", "11:58", TZ) and not _at_clock("2026-11-25", "x:y", TZ)
    snap = {**Tracker(None, "Europe/Belgrade").snapshot(), "stanje": "nema_prenosa", "dan": "2026-11-25", "ranije": True, "provereno": noon + 9000,
            "sazetak": {"vrsta": "dan", "odluke": [{"vreme": "11:58", "sta": "Zaključena je sednica."}, {"vreme": "", "sta": "Bez vremena."}]}}
    draw = lambda cyr=False, **kw: fragment({**snap, **kw}, cyr=cyr, site="https://zailiprotiv.rs/", tz=TZ)
    plain = draw()
    assert '<span class="time">11:58</span>' in plain and 'class="time" href' not in plain
    video = {"video": "dQw4w9WgXcQ", "od": noon - 5000, "do": noon + 5000, "pocetak": noon - 5000}
    part = {"url": "https://arhiva.videonet.co.rs/a.mp4", "od": noon - 600, "trajanje": 3000}
    for cyr in (False, True):
        # the broadcast over, its video still public; then the archive's file, which comes first
        assert 'data-yt="dQw4w9WgXcQ" data-t="5000"' in draw(cyr, otvoreno=[video]) and "&amp;t=5000s" in draw(cyr, otvoreno=[video])
        assert 'data-file="https://arhiva.videonet.co.rs/a.mp4" data-t="600"' in draw(cyr, otvoreno=[video], datoteke=[part])
    assert 'class="time" href' not in draw(otvoreno=[{**video, "od": noon + 1000, "pocetak": noon + 1000}])  # read from later on
    live = draw(stanje="govori", ranije=False, prenos={"video": "dQw4w9WgXcQ", "od": noon - 60})
    assert 'data-yt="dQw4w9WgXcQ" data-t="60"' in live


def test_a_turn_found_without_a_caption_has_its_place_in_the_broadcast():
    """24 Nov 2026, the maintainer: in "Svi govori redom" a way back to the moment; found turns had no place."""
    now = 1795519000.0
    t = Tracker(None, "Europe/Belgrade")
    t.roster = ROSTER
    marko = next(p for p in ROSTER.people if p.slug == "markovic-marko")
    at = lambda sq: {"video": "dQw4w9WgXcQ", "sq": sq, "seg": 5.0}
    t.observe(None, now=now, at=at(1000))  # 5000 s into the broadcast
    t.heard(marko, "prepis", now + 10, now + 10)
    t.observe(None, now=now + 60, at=at(1012))
    t.unheard(now + 70)
    snap = t.snapshot(now + 100)
    d = snap["danas"][0]
    assert d["video"] == "dQw4w9WgXcQ" and abs(d["snimak"] - (5010 - 5 * config.RECORDING_LEAD)) <= 1
    html = fragment(snap, cyr=False, site="https://zailiprotiv.rs/", tz=TZ)
    assert 'data-yt="dQw4w9WgXcQ"' in html and "class=\"time tp\"" in html and "▶ " in html
    t.turns[0]["start"] -= 6000  # before this broadcast began: another video, no place
    t._snap = None
    assert t.snapshot(now + 100)["danas"][0]["snimak"] is None


def test_a_speaker_named_again_after_speech_that_went_on_is_the_same_turn():
    """24 Nov 2026, 15:47: the voice of an MP was taken for another's, and 139 s of her speech were nobody's."""
    now = 1795519000.0
    def tracker(words, floor=False):
        t = Tracker(None, "Europe/Belgrade")
        t.roster = ROSTER
        t.observe(None, now=now)
        marko = next(p for p in ROSTER.people if p.slug == "markovic-marko")
        t.heard(marko, "potpis", now + 5, now + 5)
        t.observe(None, now=now + 100)
        t.unheard(now + 100)
        t.said = {f"p{int(now + 105 + 10 * i)}": "rec " * words for i in range(13)}
        t.events = [{"t": now + 150, "vrsta": "Reč ima", "tekst": "Petrović Petar", "izvor": "prepis", "url": "petrovic-petar"}] if floor else []
        t.heard(marko, "potpis", now + 240, now + 240)
        return t
    t = tracker(20)
    assert len(t.turns_now()) == 1 and t.turns_now()[0]["seen"] >= now + 240 and t.open_turn()  # it went on: one turn
    assert len(tracker(4).turns_now()) == 2  # silence, or the chair's few words: not his time
    assert len(tracker(20, floor=True).turns_now()) == 2  # the floor was given to another between
    t = tracker(20)
    for words in ("Da li predsednici poslaničkih grupa žele reč? Aleksandar Vučić, replika.", "Reč ima narodni poslanik.", "Upozoravam vas."):
        from uzivo.state_base import CHAIRS
        assert CHAIRS.search(words)  # the chair's words: never the speaker's time
    assert not CHAIRS.search("Pomenuti izveštaji ovog komiteta ukazuju na stanje ljudskih prava.")


def test_a_voice_not_recognised_does_not_end_a_turn():
    """24 Nov 2026, 14:02: Miroslav Andrić's voice was on the list and not recognised; 80 s of his stood as 0 s."""
    now = 1795519000.0
    t = Tracker(None, "Europe/Belgrade")
    t.roster = ROSTER
    t.observe(None, now=now)
    marko = next(p for p in ROSTER.people if p.slug == "markovic-marko")
    t.heard(marko, "potpis", now + 5, now + 5)
    t.observe(None, now=now + 60)
    t.voice_gone(now + 1, now + 70, {marko.slug})  # his voice is known, nobody's was recognised
    assert t.open_turn() and t.open_turn()["slug"] == "markovic-marko"
    t.heard(marko, "glas", now + 60, now + 90)  # recognised: now its end counts
    t.voice_gone(now + 90, now + 110, {marko.slug})
    assert t.open_turn() and t.turns_now()[0]["seen"] == now + 90  # held: it may be applause
    t.voice_gone(now + 90, now + 121, {marko.slug})
    assert t.open_turn() is None and t.turns_now()[0]["seen"] == now + 90  # the end is where the voice was


def test_a_floor_passed_on_by_name_is_not_filled():
    """24 Nov 2026, 15:11: "Reč ima doktor Milica Jovanović … Narodna poslanica, Ana Brnabić": the first had no turn."""
    from uzivo.names import Person
    from uzivo.popuna import fill
    people = [Person("jovanovic milica", "Jovanović Milica", "jovanovic-milica", "A"), Person("brnabic ana", "Brnabić Ana", "brnabic-ana", "B")]
    said = {"p1000": "Reč ima doktorka Milica Jovanović.", "p1005": "Narodna poslanica, Ana Brnavić. Ja se izvinjam.", "p1030": "rec " * 60}
    turns = [{"key": "brnabic ana", "name": "Brnabić Ana", "slug": "brnabic-ana", "group": "", "start": 1080, "seen": 1400, "n": 4, "izvor": "potpis", "role": ""}]
    assert fill(turns, said, people) == (turns, [])


def test_the_days_turns_are_filled_from_the_chairs_words_by_one_rule():
    from uzivo.names import Person
    from uzivo.popuna import fill
    people = [Person("andric miroslav", "Andrić Miroslav", "andric-miroslav", "A"), Person("bakic jovo", "Bakić Jovo", "bakic-jovo", "B"),
              Person("djajic zoran", "Đajić Zoran", "djajic-zoran", "B")]
    turn = lambda key, name, a, b: {"key": key, "name": name, "slug": key.replace(" ", "-"), "group": "", "start": a, "seen": b, "n": 4,
                                     "izvor": "potpis", "role": ""}
    said = {"p1000": "Reč ima narodni poslanik Miroslav Andrić.", "1020": "rec " * 30, "p1100": "Reč ima narodni poslanik Jovo Bakić.",
            "1120": "rec " * 30, "p1200": "Reč ima narodni poslanik Zoran Đajić.", "1220": "rec " * 30, "p1800": "Reč ima Jovo Bakić."}
    turns = [turn("andric miroslav", "Andrić Miroslav", 1020, 1020), turn("bakic jovo", "Bakić Jovo", 1120, 1190), turn("bakic jovo", "Bakić Jovo", 1820, 2000)]
    out, done = fill(turns, said, people)
    by = {t["name"]: round(t["seen"] - t["start"]) for t in out if t["name"] != "Bakić Jovo"}
    assert by == {"Andrić Miroslav": 80, "Đajić Zoran": 580}  # the one of 0 s lengthened, the one missing written
    assert [round(t["seen"] - t["start"]) for t in out if t["name"] == "Bakić Jovo"] == [70, 180]  # a whole one left as it was
    assert len(done) == 2 and fill(out, said, people)[1] == []  # a second run does nothing
    cut_two = [turn("bakic jovo", "Bakić Jovo", 5000, 5100), turn("bakic jovo", "Bakić Jovo", 5240, 5400)]
    spoke = {str(5100 + 10 * i): "rec " * 20 for i in range(14)}
    assert [round(t["seen"] - t["start"]) for t in fill(cut_two, spoke, people)[0]] == [400]  # one turn, speech between
    assert len(fill(cut_two, {}, people)[0]) == 2
    mixed = [turn("bakic jovo", "Bakić Jovo", 5000, 5100), turn("andric miroslav", "Andrić Miroslav", 5060, 5200)]
    cut, said_ = fill(mixed, {}, people)
    assert [round(t["seen"]) for t in cut] == [5060, 5200] and len(said_) == 1  # none runs into the next


def test_the_name_before_the_word_and_a_measure_only_spoken_of():
    from uzivo import hronika
    from uzivo.names import Person
    from uzivo.mere import given
    people = [Person("a", "Kokanović Zlatko", "kokanovic-zlatko", ""), Person("b", "Vučić Aleksandar", "vucic-aleksandar", "")]
    got = lambda text: [p.slug for p in hronika.floor(text, people)]
    assert got("Prijavila se još, verovatno, replika. Zlatko Kokanović, reč. Izvolite.") == ["kokanovic-zlatko"]
    people += [Person("c", "Radović Vera", "radovic-vera", ""), Person("d", "Mirković Aleksandar", "mirkovic-aleksandar", "")]
    assert got("Imamo povredu poslovnika, Vera Radović, je li po povredi?") == ["radovic-vera"]
    assert got("Povredu poslovnika je počinio Vera Radović.") == []  # the name not right after it
    assert got("Da li želite prvo dajem Aleksandru Mirkoviću?") == ["mirkovic-aleksandar"]
    # the speaker announced with no "reč ima" (24 Nov 2026: Ahmedin Škrijelj's speech of five minutes stood as nobody's)
    people += [Person("e", "Škrijelj Ahmedin", "skrijelj-ahmedin", ""), Person("f", "Lesjak Marija", "lesjak-marija", "")]
    assert got("Imamo još jednog govornika za danas, to je gospodin narodni posljednik Ahmedin Škrijelj.") == ["skrijelj-ahmedin"]
    assert got("Idemo dalje, sljedeći govornik, odnosno govornica je profesor doktor Marija Lesjak.") == ["lesjak-marija"]
    assert got("Prethodni govornik je rekao da Ahmedin Škrijelj nije u pravu.") == []  # said of a speaker, not an announcement
    assert got("Zlatko Kokanović, reč o kojoj govorim nije ta.") == [] and got("Zlatko Kokanović je rekao reč.") == []
    assert given("Ja vam izričem opomenu, imali ste...") and given("Izričajam opomenu.")
    assert not given("Zato ste mu dali opomenu, izrekli ste je.") and not given("vi ste njega opomenuli pa ste ga opomenuli i drugi put")
    assert not given("ja sam dao opomene poslanici Anji Brnabić")


def test_a_measure_has_its_reason_by_the_rules_list_and_never_the_transcripts_words():
    """24 Nov 2026, the maintainer: the day's steps fuller with no sentence of the transcript: why a warning was given,
    one of the Rules' reasons (art. 109) in our words, where the chair's sentence says exactly one."""
    from uzivo import page as page_
    from uzivo.mere import reason
    from uzivo.steps import steps_shown
    assert reason("Dakle, izričem vam opomenu zato što uporno govorite bez date reči.") == "zbog govora bez date reči"
    assert reason("Druga opomena, druga opomena, i dalje niste u temi.") == "zbog govora van teme"
    assert reason("Izričano mi sad opomenu i vama, prišli ste bez poziva.") == "zbog prilaska govornici bez dozvole"
    assert reason("Ja vam izričem opomenu, imali ste...") == "" and reason("Izričem vam opomenu zbog ovoga.") == ""
    assert reason("Izričem vam opomenu, niste u temi i dobacujete.") == ""  # two heard: none
    assert reason("Zato ste mu dali opomenu, govorio je bez date reči.") == ""  # spoken of, not given
    now = 1795518700.0
    ev = lambda dt, text: {"t": now - dt, "vrsta": "Mera predsedavajućeg", "tekst": text, "izvor": "model", "url": "",
                           "vise": {"napomena": "opomena"}}
    said = "Dakle, izričem vam opomenu zato što uporno govorite bez date reči."
    snap = {"provereno": now, "sada": None, "danas": [], "dnevni_red": None,
            "hronika": [ev(6000, "Izričem vam opomenu, niste u temi."), ev(100, "poslednji put vas upozorio. Izričem opomenu."), ev(80, said)]}
    rows = [r for r in steps_shown(snap) if r["naslov"] == "Mera predsedavajućeg"]
    # said again with its reason within a minute: one step, with the reason; another reason earlier: another step
    assert sorted((r["t"], r.get("razlog")) for r in rows) == [(now - 6000, "zbog govora van teme"), (now - 100, "zbog govora bez date reči")]
    html = page_._steps(snap, cyr=False, tz=TZ)
    assert "zbog govora bez date reči" in html and "uporno govorite" not in html
    assert "због говора без дате речи" in page_._steps(snap, cyr=True, tz=TZ)


def test_the_broadcasts_clock_says_when_a_turn_began():
    """24 Nov 2026: the caption has a clock beside it ("0:15"), how long the turn has gone on; the floor given at 11:59:54
    was a speech begun at 12:00:24."""
    now = 1795519000.0
    t = Tracker(None, "Europe/Belgrade")
    t.roster = ROSTER
    marko = next(p for p in ROSTER.people if p.slug == "markovic-marko")
    petar = next(p for p in ROSTER.people if p.slug == "petrovic-petar")
    t.observe(None, now=now)
    t.heard(petar, "prepis", now - 100, now - 100)
    t.observe(None, now=now)
    t.heard(marko, "prepis", now + 10, now + 10)  # the chair's words, a moment early
    t.heard(marko, "potpis", now + 45, now + 45)
    t.clocked(marko, now + 45, 15)  # began at now + 30
    assert t.turns_now()[-1]["start"] == now + 10  # one reading is not yet sure
    t.clocked(marko, now + 50, 20)
    assert abs(t.turns_now()[-1]["start"] - (now + 30)) <= 1
    t.clocked(marko, now + 55, 900)  # a reading that does not agree
    t.clocked(marko, now + 60, 30)
    assert abs(t.turns_now()[-1]["start"] - (now + 30)) <= 1
    t.heard(petar, "potpis", now + 200, now + 200)
    t.clocked(petar, now + 200, 5)
    t.clocked(petar, now + 205, 10)  # a later turn begins at now + 195; the one before ends there at the latest
    turns = t.turns_now()
    assert abs(turns[-1]["start"] - (now + 195)) <= 1 and turns[-2]["seen"] <= now + 196
    assert t.clocked(marko, now + 1000, 5) is None  # no turn of theirs open: nothing


def test_a_break_ended_is_a_step_where_the_model_did_not_say_so():
    """24 Nov 2026: after the break to 15:10 the chair said "pošto imamo kvorum, nastavljamo pretres po petoj tački", and
    no step told it; the break before it was told by the move to an item at once."""
    from uzivo.steps import model_steps
    base = 1795510000
    ev = lambda t, kind, text, src="prepis", **more: {"t": base + t, "vrsta": kind, "tekst": text, "izvor": src, **({"vise": more} if more else {})}
    snap = {"provereno": base + 9000, "sada": None, "danas": [{"od": base + 100, "do": base + 500}, {"od": base + 4000, "do": base + 4400}],
            "dnevni_red": {"tacke": [{"n": 5, "tekst": "Izbor"}]},
            "hronika": [ev(600, "Pauza", "Proglašavam pauzu do 15 sati i 10 minuta.", "model", do="15 sati i 10 minuta"),
                        ev(3900, "Tačka dnevnog reda", "nastavljamo pretres po petoj tački")]}
    titles = [(s["t"] - base, s["naslov"]) for s in model_steps(snap)]
    assert titles == [(3900, "Rad je nastavljen"), (600, "Pauza")]
    told = {**snap, "hronika": snap["hronika"] + [ev(3910, "Tačka dnevnog reda", "Prelazimo na petu tačku.", "model", tacka="5")]}
    assert [s["naslov"] for s in model_steps(told)] == ["Prelazak na 5. tačku dnevnog reda", "Pauza"]  # said already, once
    still = {**snap, "danas": snap["danas"][:1], "hronika": snap["hronika"][:1]}
    assert [s["naslov"] for s in model_steps(still)] == ["Pauza"]  # the break goes on


def test_sound_a_run_before_left_is_written_down_unless_too_old(tmp_path, monkeypatch):
    """24 Nov 2026: a restart lost the chair's words of a break; what is left on the volume is taken up, the old thrown away."""
    from uzivo import prepis
    monkeypatch.setattr(config, "SOUND_PATH", str(tmp_path))
    now = 1795520000.0
    fresh, old = tmp_path / f"{int((now - 30) * 1000)}-4000.pcm", tmp_path / f"{int((now - 1000) * 1000)}-4000.pcm"
    for f in (fresh, old, tmp_path / f"{int(now * 1000)}-4000.tmp"):
        f.write_bytes(b"x" * 4000)
    assert prepis.left(now) == 2 and [f for _, _, f in prepis.waiting()] == [fresh]
    assert prepis.left(now) == 0
    compose = (Path(__file__).resolve().parents[1] / "live" / "docker-compose.yml").read_text(encoding="utf-8")
    assert "SOUND_PATH: /data/zvuk" in compose


def test_a_turn_of_the_chairs_words_and_two_seconds_is_none():
    """24 Nov 2026, 15:11: "Reč ima doktor Milica Jovanović … Narodna poslanica, Ana Brnabić": the floor passed on at once."""
    from uzivo.state_base import counted
    turn = lambda sec, how: {"n": 4, "start": 100, "seen": 100 + sec, "izvor": how, "role": ""}
    assert not counted(turn(2, "prepis")) and not counted(turn(8, "prepis")) and counted(turn(20, "prepis"))
    assert counted(turn(2, "potpis")) and counted(turn(2, "glas"))  # seen or heard: it stays


def test_an_exchange_is_a_reply_the_chair_gave_and_what_it_takes_up():
    """24 Nov 2026, the maintainer's choice of three: the words said, as a conversation. Chosen by what happened (a reply
    the chair gave) and by the words both share, never by tone; only pieces wholly inside a turn, as the seams are the
    next speaker's (a sentence of one had stood as the other's in the day's try)."""
    from uzivo.razmene import find
    turn = lambda name, a, b, lista: {"ime": name, "adresa": "", "lista": lista, "od": a, "do": b, "sekundi": b - a}
    turns = [turn("Petrović Petar", 1000, 1200, "A"), turn("Marković Marko", 1230, 1300, "B")]
    said = {"p1205": "Reč ima narodni poslanik Marko Marković. Replika.",
            "1040": "Tržište je rastureno i korenite sistemske promene nisu napravljene.",
            "1245": "On govori o korenitim sistemskim promenama u celoj zemlji."}
    said |= {str(1060 + 30 * i): f"Nešto drugo se govori u sali redom {i}." for i in range(4)}
    assert find(said, turns) == [] or find(said, turns)[0]["odgovor"]["ime"] == "Marković Marko"
    many = [turn(f"Poslanik {i}", 2000 + 300 * i, 2200 + 300 * i, "C") for i in range(14)]
    far = {str(2020 + 300 * i): f"Reč o temi {i}, a onda sve dalje po redu danas ovde." for i in range(14)}
    got = find({**said, **far}, turns + many)
    assert got and got[0]["prvi"]["ime"] == "Petrović Petar" and "korenite sistemske" in got[0]["prvi"]["tekst"]
    assert got[0]["odgovor"]["tekst"].startswith("On govori")
    no_reply = {**said, "p1205": "Reč ima narodni poslanik Marko Marković."}
    assert find({**no_reply, **far}, turns + many) == []  # the chair gave no reply: no exchange
    edge = {**said, "1190": "Korenite sistemske promene su sve što je rečeno na kraju govora."}
    assert "kraju govora" not in str(find({**edge, **far}, turns + many))  # a piece over the turn's end is the next speaker's


def test_the_measures_sentence_and_the_list_by_hour_are_on_the_page(monkeypatch):
    """24 Nov 2026: the chair's sentence of a measure under its step, the turns under the hour they began in. The
    sentences only where they are turned on (RECI_PRIKAZ=1): off since the same day, the transcript erring too often."""
    base = 1795510000
    ev = {"t": base + 5000, "vrsta": "Mera predsedavajućeg", "tekst": "Ja vam izričem opomenu.", "izvor": "model", "vise": {"napomena": "opomena"}}
    turn = {"ime": "Petrović Petar", "adresa": "petrovic-petar", "uloga": "", "grupa": "PG A", "lista": "PG A", "od": base + 100, "do": base + 400,
            "sekundi": 300, "video": "", "snimak": None, "foto": "12.jpg", "rezime": "O budžetu."}
    snap = {**Tracker(None, "Europe/Belgrade").snapshot(), "stanje": "nepoznato", "provereno": base + 9000, "hronika": [ev], "danas": [turn],
            "razmene": [{"t": base + 6000, "prvi": {"ime": "Petrović Petar", "adresa": "", "lista": "PG A", "tekst": "Prva rečenica.", "t": base + 5990},
                         "odgovor": {"ime": "Marković Marko", "adresa": "", "lista": "PG B", "tekst": "Druga rečenica.", "t": base + 6010}}]}
    assert not config.SHOW_QUOTES
    html = fragment(snap, cyr=False, site="https://zailiprotiv.rs/", tz=TZ)
    assert "Ja vam izričem opomenu." not in html and "Prva rečenica." not in html and "Druga rečenica." not in html
    monkeypatch.setattr(config, "SHOW_QUOTES", True)
    html = fragment(snap, cyr=False, site="https://zailiprotiv.rs/", tz=TZ)
    assert "Ja vam izričem opomenu." in html and "automatski prepis" in html and "<b>Predsedavajući</b>" in html
    assert "Prva rečenica." in html and "<b>Petar Petrović</b>" in html and "Replika" in html
    assert '<img class="tf" src="https://zailiprotiv.rs/foto/12.jpg"' in html and "O budžetu." in html and '<li class="th">' in html
    assert "Poslovnik" in html and "st-title" in html
    monkey = fragment({**snap, "hronika": [], "razmene": []}, cyr=False, site="https://zailiprotiv.rs/", tz=TZ)
    assert "class=\"q" not in monkey


def test_the_mails_card_can_be_put_away():
    """24 Nov 2026, the maintainer: for who does not want to see it, or has signed up; kept in that browser alone."""
    from uzivo.page import SCRIPT
    assert 'localStorage.setItem("mejl-sklonjen", "1")' in SCRIPT and 'localStorage.removeItem("mejl-sklonjen")' in SCRIPT
    assert "mejl-prijavljen" in SCRIPT  # signing up puts it away too
    assert "mejl-skloni\"" not in SCRIPT  # and nothing of it is sent, as a sum either (25 Nov 2026)


def test_a_turn_by_a_voice_merely_alike_goes_back_to_whose_speech_it_was():
    """24 Nov 2026, 17:26:23: Nikola Selaković's last 24 s stood as Miroslav Petrašinović's, found by voice alone."""
    from uzivo.popuna import fill

    def day(words: dict, izvor="glas", long=24):
        a = {"key": "a", "name": "Selaković Nikola", "slug": "a", "group": "", "role": "", "start": 1000, "seen": 1117,
             "n": 4, "izvor": "potpis", "natpis": 1002}
        b = {"key": "b", "name": "Petrašinović Miroslav", "slug": "b", "group": "", "role": "", "start": 1117,
             "seen": 1117 + long, "n": 4, "izvor": izvor, "po_glasu": True}
        return fill([a, b], words, [])
    words = {"1065": "Pored Zgrade Narodne Biblioteke doneli su vaši prethodnici.", "1095": "Godinama, deceniju i po. I za kraj.",
             "1125": "Od jedne decenije nego smo ga otvorili."}
    out, done = day(words)
    assert [(t["name"], t["seen"]) for t in out] == [("Selaković Nikola", 1141)] and len(done) == 1
    assert len(day({**words, "p1110": "Hvala, vreme je isteklo."})[0]) == 2  # the chair spoke at the seam: a real change
    assert len(day({**words, "1040": "Da čujemo, Miroslav Petrašinović."})[0]) == 2  # named shortly before
    assert len(day(words, long=90)[0]) == 2 and len(day(words, izvor="potpis")[0]) == 2  # long, or a caption: as it was
    assert len(day({})[0]) == 2  # no words kept: nothing is known of the seam


def test_a_break_the_chair_declares_ends_a_turn_found_without_a_caption():
    """24 Nov 2026, 18:08: the break's noise stood as Vjerica Radeta's speech for minutes, with the hall's words in it."""
    from uzivo.popuna import fill
    from uzivo.state_base import BREAK
    for said_ in ("Ja ću sada da pozovem pauzu. Pauza deset minuta.", "Proglašavam pauzu do 15 sati i 10 minuta.",
                  "za raspravu, proglašam pauzu od jednog sata,", "Pauza u trajanju od jednog sata."):
        assert BREAK.search(said_), said_
    for other in ("posle toga ćemo proglasiti pauzu.", "I odredili pauzu od sat vremena", "kada je pauza proglašena",
                  "Vi ste tu pauzu napravili", "morali ste da proglasite pauzu", "i posle toliko dana pauze"):
        assert not BREAK.search(other), other

    def day(text: str) -> Tracker:
        t = Tracker(None, "Europe/Belgrade")
        t.roster = ROSTER
        now = 1795519000.0
        t.observe(None, now=now)
        t.heard(next(p for p in ROSTER.people if p.slug == "markovic-marko"), "prepis", now + 10, now + 10)
        for i in range(0, 120, 5):
            t.observe(None, now=now + 10 + i)
        t.say(now + 40, text)
        return t
    ended = day("Molim vas. Pauza deset minuta.")
    assert not ended.open_turn() and ended.turns_now()[-1]["seen"] == 1795519040 and ended.snapshot(now=1795519130)["sada"] is None
    assert day("Vi ste tu pauzu napravili.").open_turn()  # spoken of by a speaker: the turn goes on
    # the fill gives nobody the break: not by the floor given before it, and a turn that ran into it is cut there
    from uzivo.names import Person
    people = [Person("a", "Radeta Vjerica", "radeta-vjerica", ""), Person("b", "Nikolić Nina", "nikolic-nina", "")]
    said = {"1000": "Reč ima Vjerica Radeta, narodna poslanica.", "p1060": "Pauza deset minuta.", "1100": "Koga treba da bijemo?",
            "p1700": "Reč ima Nina Nikolić, narodna poslanica."}
    turn = {"key": "a", "name": "Radeta Vjerica", "slug": "radeta-vjerica", "group": "", "role": "", "start": 1030, "seen": 1250, "n": 4, "izvor": "prepis"}
    other = {**turn, "key": "b", "name": "Nikolić Nina", "slug": "nikolic-nina", "start": 1720, "seen": 1900, "izvor": "potpis"}
    out, done = fill([turn, other], said, people)
    assert [round(t["seen"]) for t in out] == [1060, 1900] and any("pauza" in d for d in done)


def test_the_floor_given_at_a_seam_and_a_surname_misheard():
    """24 Nov 2026: "Ima narodni poslanik Zoran Đajić" at a piece's beginning, and "Sanja Fritz" for Sanja Fric."""
    from uzivo import hronika
    from uzivo.names import Person
    people = [Person("a", "Đajić Zoran", "djajic-zoran", ""), Person("b", "Fric Sanja", "fric-sanja", ""),
              Person("c", "Belić Sanja", "belic-sanja", ""), Person("d", "Petrović Ana", "petrovic-ana", "")]
    got = lambda text: [p.slug for p in hronika.floor(text, people)]
    assert got("Ima narodni poslanik Zoran Đajić, molim da se prijavi.") == ["djajic-zoran"]
    assert got("Kaže da ima narodni poslanik Zoran Đajić u sali.") == []  # inside a sentence: said of him
    assert got("Reč ima narodna poslanica Sanja Fritz, po komu osnu?") == ["fric-sanja"]
    assert got("Reč ima narodna poslanica Sanja Belić.") == ["belic-sanja"]
    assert got("Reč ima narodna poslanica Sanja Marković.") == [] and got("Reč ima Ana Nikolić.") == []


def test_a_caption_of_seconds_teaches_the_voice(tmp_path):
    """24 Nov 2026: the caption was not read, so no voice was learnt all day; its seconds are."""
    np = pytest.importorskip("numpy")
    import threading as th
    from uzivo import glas
    t = Tracker(None, "Europe/Belgrade")
    t.roster = ROSTER
    now = 1795100000.0
    t.observe(None, now=now)
    marko = next(p for p in ROSTER.people if p.slug == "markovic-marko")
    t.heard(marko, "prepis", now, now)
    t.heard(marko, "potpis", now + 10, now + 10)
    t.observe(None, now=now + 120)
    a = np.zeros(512, np.float32)
    a[0] = 1
    L = glas.Listener(t, th.Event(), embed=lambda x: a, path=tmp_path / "v.npz")
    L.t, L.f = [now + 1.5 * i for i in range(70)], [a] * 70
    L.learn(t.turns_now())
    n = L.voices.n["markovic-marko"]
    assert 15 <= n <= 30  # from the caption to LEARN_ON, not the whole turn
    L.learn(t.turns_now())
    assert L.voices.n["markovic-marko"] == n  # the same seconds once


def test_a_voice_known_from_a_few_seconds_neither_names_nor_ends_a_turn(tmp_path):
    """24 Nov 2026, 16:57: Milena Đorđijević's voice was known from two windows of the same speech, matched those seconds
    and then no more, and a speech of ten minutes ended at 56 s."""
    np = pytest.importorskip("numpy")
    import threading as th
    from uzivo import glas
    a, b = np.zeros(512, np.float32), np.zeros(512, np.float32)
    a[0] = 1
    b[0], b[1] = 0.5, 0.866  # the same speaker further on: below VOICE_MIN, above CHANGE

    def turn(count: int) -> tuple:
        t = Tracker(None, "Europe/Belgrade")
        t.roster = ROSTER
        now = 1795100000.0
        t.observe(None, now=now)
        marko = next(p for p in ROSTER.people if p.slug == "markovic-marko")
        t.heard(marko, "potpis", now, now)
        f = tmp_path / f"v{count}.npz"
        np.savez_compressed(f, slugs=np.array(["markovic-marko"]), vecs=np.stack([a]), counts=np.array([count]))
        L = glas.Listener(t, th.Event(), embed=lambda x: a, path=f)
        for n in (20, 40):
            L.t, L.f = [now + 1.5 * i for i in range(n)], [a] * min(n, 20) + [b] * max(0, n - 20)
            t.observe(None, now=now + 1.5 * n)
            L.judge()
            L.changed()
        return t.open_turn(), L
    still, L = turn(glas.LEAST - 1)
    assert still and not still.get("po_glasu") and L.voices.refs() == {}
    L.voices.add("markovic-marko", np.stack([a]))
    assert list(L.voices.refs()) == ["markovic-marko"]  # known well enough from here on
    assert turn(glas.LEAST)[0] is None  # a voice known well that is gone ends the turn, as before


def test_a_voice_merely_alike_another_does_not_take_the_floor(tmp_path):
    """24 Nov 2026, 17:26: Nikola Selaković's voice, not yet known, was some 0.58 like Miroslav Petrašinović's all along and a
    little over the line for 24 s, which stood as Petrašinović's speech."""
    np = pytest.importorskip("numpy")
    import threading as th
    from uzivo import glas

    def like(x: float):  # a voice so like the known one
        v = np.zeros(512, np.float32)
        v[0], v[1] = x, (1 - x * x) ** 0.5
        return v

    def run(before: float, after: float, between: float) -> dict | None:
        t = Tracker(None, "Europe/Belgrade")
        t.roster = ROSTER
        now = 1795100000.0
        t.observe(None, now=now)
        t.heard(next(p for p in ROSTER.people if p.slug == "petrovic-petar"), "potpis", now, now)
        f = tmp_path / "v.npz"
        np.savez_compressed(f, slugs=np.array(["markovic-marko"]), vecs=np.stack([like(1.0)]), counts=np.array([300]))
        L = glas.Listener(t, th.Event(), embed=lambda x: like(1.0), path=f)
        L.t = [now + 1.5 * i for i in range(60)]
        L.f = [like(before)] * 33 + [like(between)] * 7 + [like(after)] * 20  # a pause over GAP between: a stretch of its own
        t.observe(None, now=now + 92)
        L.judge()
        return t.open_turn()
    assert run(0.64, 0.69, 0.5)["slug"] == "petrovic-petar"  # alike all along: the same speaker
    assert run(0.3, 0.8, 0.3)["slug"] == "markovic-marko"  # the voice is new in the turn: the floor passed on


def test_a_voice_that_ends_before_the_floor_passed_on_does_not_end_the_turn():
    """24 Nov 2026, 12:18:54: the chair gave Jovo Bakić the floor, the last seconds of the speaker before came after,
    and the reply of 50 s stood as that speaker's."""
    now = 1795519000.0
    t = Tracker(None, "Europe/Belgrade")
    t.roster = ROSTER
    petar = next(p for p in ROSTER.people if p.slug == "petrovic-petar")
    marko = next(p for p in ROSTER.people if p.slug == "markovic-marko")
    t.observe(None, now=now)
    t.heard(petar, "glas", now, now + 60)
    t.heard(marko, "prepis", now + 80, now + 80)
    t.heard(petar, "glas", now + 40, now + 78, tracked={petar.slug})  # the voice windows lag
    t.observe(None, now=now + 100)
    cur = t.open_turn()
    assert cur["slug"] == "markovic-marko" and len(t.turns_now()) == 2 and t.turns_now()[0]["seen"] == now + 78
    t.heard(petar, "glas", now + 130, now + 140)  # a voice that goes on past it is the next turn
    assert t.open_turn()["slug"] == "petrovic-petar" and t.turns_now()[1]["seen"] >= now + 100


def test_a_replys_and_a_point_of_orders_two_minutes_stand_by_the_clock():
    """24 Nov 2026, the maintainer: how long the turn may last, where the transcript tells what it is."""
    from uzivo.rok import limit
    start = 1795515909.0
    chair = lambda text, at=-20: {f"p{int(start + at)}": text}
    own = lambda text, at=5: {str(int(start + at)): text}
    assert limit(chair("Reč ima poslanica Ana Brnabić. Povreda poslovnika člana 108."), start, 30) == {"vrsta": "povreda", "sek": 120}
    assert limit(chair("Aleksandar Vučić, Replika. To će dva minuta da traje."), start, 30)["vrsta"] == "replika"
    assert limit(own("Reklamiram povredu poslanika, predsedavajući"), start, 30)["vrsta"] == "povreda"
    assert limit({**chair("Replika."), **own("povreda Poslovnika, član 27")}, start, 30) == {"vrsta": "", "sek": 120}
    assert limit(own("Vi ste povredili Poslovnik, ali to je nešto na šta smo naučili."), start, 30) is None  # a speech
    assert limit(chair("Reč ima narodni poslanik Petar Petrović."), start, 30) is None
    assert limit(chair("Replika.", -600), start, 30) is None  # another turn's
    assert limit(chair("Replika."), start, 200) is None  # long past two minutes: no such turn, or let on
    snap = {"stanje": "govori", "provereno": start, "danas": [], "dan": "2026-11-24", "dnevni_red": None, "hronika": [],
            "sada": {"ime": "Petrović Petar", "adresa": "petrovic-petar", "od": int(start), "do": int(start + 30), "sekundi": 30,
                     "lista": "PG A", "rok": {"vrsta": "replika", "sek": 120}}}
    html = fragment(snap, cyr=False, site="https://zailiprotiv.rs/", tz=TZ)
    assert '<span class="rk"><span>/ 2 min</span> <span>· replika</span></span>' in html


def test_the_groups_time_left_stands_small_under_the_speaker(monkeypatch):
    """24 Nov 2026, the maintainer: smaller, under the speaker, no other words; the method under "Kako ovo radi"."""
    g = {"tacka": 5, "pojedinosti": False, "zakljucen": False,
         "grupe": [{"lista": "PG A", "mesta": 100, "ima": 7200, "potroseno": 600, "govora": 1}]}
    snap = {**Tracker(None, "Europe/Belgrade").snapshot(), "stanje": "nepoznato", "vreme_grupa": g}
    draw = lambda **more: fragment({**snap, **more}, cyr=False, site="https://zailiprotiv.rs/", tz=TZ)
    html = draw()
    assert html.index('class="sp"') < html.index('class="gt-sec"') < html.index('class="said-sec"')
    assert "PG A</span><b>1 h 50 min</b>" in html and "procena" in html and "potrošeno" not in html
    assert "gt-sec" not in draw(vreme_grupa={**g, "zakljucen": True})  # the debate closed: no time left to tell
    assert "gt-said" not in html  # no figure of the chair's: nothing under the bar
    told = {**g, "grupe": [{**g["grupe"][0], "receno": {"t": __import__("datetime").datetime(2026, 11, 24, 18, 43, 40, tzinfo=TZ).timestamp(), "sek": 1401, "nase": 180}}]}
    assert '<small class="gt-said">predsedavajući u 18:43: još 23 min 21 s</small>' in draw(vreme_grupa=told)
    how = page(snap, cyr=False, site="https://zailiprotiv.rs/", tz=TZ).split('<details class="how">', 1)[1]
    assert "član 97" in how and "poslovnik-clanovi#pojam-vreme-rasprave" in how
    monkeypatch.setattr(config, "SHOW_GROUP_TIME", False)
    assert "gt-sec" not in draw()


def test_a_reply_longer_than_two_minutes_is_not_the_groups_time():
    from uzivo.rok import short
    from uzivo.vreme import groups_time
    start = 1795089600
    said = {str(start + 1005): "Javio sam se za repliku, hvala."}
    turn = lambda at, sec: {"od": start + at, "do": start + at + sec, "sekundi": sec, "lista": "A"}
    assert short(said, turn(1000, 142), 180) and not short(said, turn(1000, 300), 180) and not short(said, turn(5000, 142), 180)
    rows = [{**turn(100, 600)}, {**turn(1000, 142), "kratko": True}]
    g = groups_time(item=4, start=start, seats={"A": 10}, turns=rows, events=[], now=start + 4000)
    assert g["grupe"][0]["potroseno"] == 600
    # the chair's "po kom osnovu?" tells it too, for the groups' time only: the clock by the speaker wants the kind heard
    from uzivo.rok import limit
    asked = {"p" + str(start + 1980): "Reč ima narodni poslanik Petar Petrović, po kom osnovu?"}
    assert short(asked, turn(2000, 145), 180) and not short(asked, turn(2000, 272), 180)
    assert limit(asked, start + 2000, 30) is None


def test_the_time_the_chair_says_is_where_the_groups_count_goes_on_from():
    """24 Nov 2026, 18:43: "po pretresu, sad ću vam reći vreme, 23 minuta 21 sekunda" while our count stood at 3 minutes
    left, and at "preko za 16 min" a quarter of an hour on."""
    from uzivo.vreme import groups_time, told
    start = 1795515829
    people = [p for p in ROSTER.people if p.slug in ("petrovic-petar", "markovic-marko")]
    a, b = people[0].group, people[1].group
    said = {"p" + str(start + 5000): f"Dajem reč narodnom poslaniku {given_first(people[0].name)}. Samo se prijavite, po pretresu, "
                                     "sad ću vam reći vreme, 23 minuta 21 sekunda.",
            "p" + str(start + 5100): f"Reč ima {given_first(people[1].name)}, replika, dva minuta.",   # a reply's time: none
            str(start + 5200): "Imali smo 23 minuta 21 sekunda i ništa nismo rekli.",                      # nobody given the floor
            "p" + str(start + 5300): f"Reč ima {given_first(people[1].name)}, preostalo vam je 900 minuta."}  # more than it can have
    got = told(said, people)
    assert [(t, g, left) for t, g, left in got if g == a] == [(start + 5000, a, 23 * 60 + 21)]
    turn = lambda at, sec, g: {"od": start + at, "do": start + at + sec, "sekundi": sec, "lista": g}
    # the turn given the floor began before the word (joined with the speaker's turn before it): its part after counts
    turns = [turn(100, 4000, a), turn(4900, 710, a), turn(5700, 100, a), turn(5900, 300, b)]
    g = groups_time(item=5, start=start, seats={a: 102, b: 140}, turns=turns, events=[], now=start + 7000, told=got)
    mine = next(r for r in g["grupe"] if r["lista"] == a)
    assert mine["ima"] - mine["potroseno"] == 23 * 60 + 21 - 610
    # our own count at that moment is kept beside the chair's figure: 4000 s and the 100 s of the turn begun before it
    assert mine["receno"] == {"t": start + 5000, "sek": 1401, "nase": mine["ima"] - 4100}
    other = next(r for r in g["grupe"] if r["lista"] == b)
    assert other["potroseno"] == 300 and "receno" not in other


def test_the_proposers_word_is_none_of_the_groups_time():
    """24 Nov 2026, from the notes of 19 Nov: the chair's "Osamnaest minuta imate još" fits the group's speeches without
    the proposer's (100-116 min by their words against 108), not with them (130-150)."""
    from uzivo.rok import proposer
    from uzivo.vreme import groups_time
    start = 1795089600
    said = {"p" + str(start + 990): "Zahvaljujem. Reč ima predlagač, narodni poslanik Petar Petrović.",
            "p" + str(start + 2990): "Reč ima narodni poslanik Petar Petrović.",
            str(start + 4005): "Kao što je predlagač rekao, ovo je dobar predlog."}  # an MP speaking of the proposer
    turn = lambda at, sec: {"od": start + at, "do": start + at + sec, "sekundi": sec, "lista": "A"}
    assert proposer(said, turn(1000, 900)) and not proposer(said, turn(3000, 900)) and not proposer(said, turn(4000, 900))
    assert proposer({"p" + str(start + 5990): "Reč ima gospodin Petar Petrović, predstavnik predlagača. Izvolite."}, turn(6000, 300))
    rows = [{**turn(1000, 900), "predlagac": True}, turn(3000, 600)]
    g = groups_time(item=4, start=start, seats={"A": 10}, turns=rows, events=[], now=start + 5000)
    assert g["grupe"][0]["potroseno"] == 600 and g["grupe"][0]["govora"] == 1


def test_the_groups_time_runs_from_the_debates_opening():
    """24 Nov 2026: a point of order of 136 s between the move to the item and the debate's opening had been counted;
    and a decision's one debate ("jedinstveni pretres", art. 192) has no debate in detail after it."""
    from uzivo.vreme import phase
    ev = lambda t, kind, text="": {"t": t, "vrsta": kind, "tekst": text}
    assert phase([], 100) == (100, False, False)
    assert phase([ev(600, "Pretres otvoren"), ev(605, "Pretres otvoren")], 100) == (600, False, False)
    one = [ev(600, "Pretres otvoren", "otvaram jedinstveni pretres"), ev(900, "Pretres zaključen")]
    assert phase(one, 100) == (600, False, True)
    assert phase(one + [ev(950, "Pretres otvoren", "otvaram jedinstveni pretres")], 100) == (950, False, False)


def test_the_groups_time_in_the_debate_is_an_estimate_by_one_rule():
    """22 Nov 2026, readers asked how much time each party has left: five hours for the groups by their MPs (art. 97),
    replies and points of order (two minutes at most) left out, the debate in detail counted afresh (art. 158)."""
    from uzivo import page as page_
    from uzivo.vreme import CHAIR_MORE, REPRESENTATIVE, TOTAL, groups_time
    start = 1795089600
    turn = lambda at, sec, g: {"od": start + at, "do": start + at + sec, "sekundi": sec, "lista": g}
    seats = {"Studentska lista": 140, "Aleksandar Vučić - Srbija pobeđuje": 102}
    turns = [turn(100, 600, "Studentska lista"), turn(800, 120, "Studentska lista"),      # a reply: not counted
             turn(1000, 900, "Aleksandar Vučić - Srbija pobeđuje"), turn(2000, 1200, ""),  # the Government: not a group
             turn(3500, 300, "*")]
    g = groups_time(item=4, start=start, seats=seats, turns=turns, events=[], now=start + 4000)
    sl, av = g["grupe"]
    assert sl["lista"] == "Studentska lista" and sl["ima"] == round(TOTAL * 140 / 242) + REPRESENTATIVE and sl["potroseno"] == 600
    assert sl["govora"] == 1 and av["potroseno"] == 900 and not g["pojedinosti"]
    # a debate closed and another opened: the debate in detail, counted from its opening, the chairs' 15 minutes more
    events = [{"t": start + 1950, "vrsta": "Pretres zaključen"}, {"t": start + 3000, "vrsta": "Pretres otvoren"}]
    d = groups_time(item=4, start=start, seats=seats, turns=turns + [turn(3100, 400, "Studentska lista")], events=events,
                    now=start + 4000)
    assert d["pojedinosti"] and d["grupe"][0]["potroseno"] == 400 and d["grupe"][0]["ima"] == sl["ima"] - REPRESENTATIVE + CHAIR_MORE
    assert groups_time(item=4, start=start, seats=seats, turns=[turn(100, 90, "Studentska lista")], events=[], now=start + 200) is None
    html = page_._group_time({"vreme_grupa": g}, cyr=False)
    assert "Preostalo vreme poslaničkih grupa" in html and "procena" in html
    assert "Преостало време посланичких група" in page_._group_time({"vreme_grupa": g}, cyr=True)
    assert page_._group_time({}, cyr=False) == ""


def test_a_days_recording_on_the_card_makes_words_of_tokens():
    """22 Nov 2026: zvuk_dana on the graphics card; whisper.cpp gives tokens, a token with no space before it is the
    same word's, the server's marks are left out, the seconds count from the piece's place in the file."""
    from uzivo import zvuk_dana
    tokens = [{"word": "[_BEG_]", "start": 0, "end": 0}, {"word": " Ti", "start": 0.04, "end": 0.16},
              {"word": " ć", "start": 0.16, "end": 0.24}, {"word": "e", "start": 0.24, "end": 0.28},
              {"word": " morati", "start": 0.3, "end": 0.6}, {"word": ".", "start": 0.6, "end": 0.62}]
    assert zvuk_dana.words(tokens, 600) == [[600.04, 600.16, "Ti"], [600.16, 600.28, "će"], [600.3, 600.62, "morati."]]
    # the segment stood at 10.0-11.16 s in the whole sound, its tokens at 0.04-0.62 in the shortened one
    assert zvuk_dana.words(tokens, 600, (10.0, 11.16)) == [[610.0, 610.24, "Ti"], [610.24, 610.48, "će"], [610.52, 611.16, "morati."]]


def test_the_speaker_by_the_chairs_words_and_by_the_voice(tmp_path, monkeypatch):
    """22 Nov 2026, the maintainer: with no caption, whom the chair gives the floor to is the speaker, and so is a
    voice clearly an MP's for 20 s; the time counts, labelled; a caption rules; the chair's voice ends such a turn."""
    import threading as th
    from uzivo import config
    monkeypatch.setattr(config, "SOUND_PATH", str(tmp_path / "zvuk"))
    (tmp_path / "zvuk").mkdir()
    now = 1795100000.0
    t = Tracker(None, "Europe/Belgrade")
    t.roster = ROSTER
    t.observe(None, now=now)  # a broadcast, nobody's caption
    petar = next(p for p in ROSTER.people if p.slug == "petrovic-petar")
    marko = next(p for p in ROSTER.people if p.slug == "markovic-marko")
    t.heard(petar, "prepis", now + 10, now + 10)  # "Reč ima Petar Petrović"
    t.observe(None, now=now + 40)  # frames go on, no caption: the turn goes on
    snap = t.snapshot(now + 40)
    assert snap["stanje"] == "govori" and snap["sada"]["ime"] == "Petrović Petar" and snap["sada"]["izvor"] == "prepis"
    assert snap["sada"]["sekundi"] == 30
    from uzivo.page import fragment
    html = fragment(snap, cyr=False, site="", tz=TZ)
    assert '<p class="meta how-found">prepoznavanje govornika može da pogreši</p>' in html and "jer prenos ne prikazuje ime" not in html
    # voices (numpy, which the live image has and the site's tests may not): Marko's sample known; his voice for 24 s
    # ends Petar's turn and begins his
    np = pytest.importorskip("numpy")
    from uzivo import glas
    a, b = np.zeros(512, np.float32), np.zeros(512, np.float32)
    a[0], b[1] = 1, 1
    voices = tmp_path / "glasovi.npz"
    np.savez_compressed(voices, slugs=np.array(["markovic-marko", "jovanovic-marko"]), vecs=np.stack([a, b]), counts=np.array([30, 30]))
    L = glas.Listener(t, th.Event(), embed=lambda s: a if s[0] > 0 else b, path=voices)
    for i in range(2):  # the hall quiet first: what the loudness is measured against
        (tmp_path / "zvuk" / f"{int((now + 36 + 4 * i) * 1000)}-4000.pcm").write_bytes(np.zeros(4 * 16000, np.int16).tobytes())
    for i in range(6):  # six segments of 4 s with Marko's voice (positive samples)
        (tmp_path / "zvuk" / f"{int((now + 44 + 4 * i) * 1000)}-4000.pcm").write_bytes((np.ones(4 * 16000) * 3000).astype(np.int16).tobytes())
    L.step()
    snap = t.snapshot(now + 70)
    assert snap["sada"]["ime"] == "Marković Marko" and snap["sada"]["izvor"] == "glas"
    done = [d for d in snap["danas"] if d["ime"] == "Petrović Petar"][0]
    assert done["izvor"] == "prepis" and done["do"] <= now + 41
    # a caption comes up for Marko: the caption rules, the turn is his by caption now
    t.observe(marko, "Treća lista", now=now + 72)
    assert "izvor" not in t.snapshot(now + 72)["sada"] and not t.turns_now()[-1].get("izvor")
    # learning: a caption turn's windows go into the speaker's voice
    L.learn([{"slug": "petrovic-petar", "start": now + 40, "seen": now + 70}])
    assert "petrovic-petar" in L.voices.sums
    # the presiding officers are never named by voice
    assert {"cupic-aleksandar", "radenovic-stojan", "macura-nada"} <= config.VOICE_SKIP  # by address, as the voices are kept
    # the voices' rule is in one place, the site's recordings and the live service alike
    from zailiprotiv import ko
    from uzivo import komadi
    assert glas.stretches is komadi.stretches and ko.stretches is komadi.stretches and glas.WIN == komadi.WIN == ko.WIN


def _words_turn(tmp_path, monkeypatch, slug="petrovic-petar", windows=50, first=None, samples=(), n=50):
    """A turn the chair's words gave `slug`, `windows` windows on (first: one voice for all of them), with samples known."""
    import threading as th
    np = pytest.importorskip("numpy")
    from uzivo import config, glas
    monkeypatch.setattr(config, "SOUND_PATH", str(tmp_path))
    now = 1795100000.0
    t = Tracker(None, "Europe/Belgrade")
    t.roster = ROSTER
    t.observe(None, now=now)
    person = next(p for p in ROSTER.people if p.slug == slug)
    t.heard(person, "prepis", now, now)
    for i in range(0, 200, 5):
        t.observe(None, now=now + i)
    path = tmp_path / "g.npz"
    path.unlink(missing_ok=True)
    if samples:
        np.savez_compressed(path, slugs=np.array([s for s, _ in samples]), vecs=np.stack([v for _, v in samples]),
                            counts=np.array([n] * len(samples)))
    L = glas.Listener(t, th.Event(), embed=lambda x: first, path=path)
    L.t = [now + 1.5 * i for i in range(windows)]
    L.f = [first] * windows
    return t, L, now


def test_a_name_the_voice_is_against_is_taken_back(tmp_path, monkeypatch):
    """25 Nov 2026: Balać's speech stood under Vučić's name, Drašković's under Bakić's (17-19 Nov): the voice of the turn's
    first minute is surely another's, or unlike the named MP's known one, and the turn is no turn."""
    np = pytest.importorskip("numpy")
    a, b = np.eye(512, dtype=np.float32)[:2]
    c = ((a + b) / np.linalg.norm(a + b)).astype(np.float32)
    for said, known in ((b, [("petrovic-petar", a)]), (b, [("markovic-marko", b)])):  # unlike his; surely another's
        t, L, now = _words_turn(tmp_path, monkeypatch, first=said, samples=known)
        L.changed()
        assert t.turns == [] and not t.open and t.status == "nepoznato"
    for said, known in ((a, [("petrovic-petar", a)]), (c, [("petrovic-petar", a)]), (b, [])):  # his; alike enough (0.71); not known
        t, L, now = _words_turn(tmp_path, monkeypatch, first=said, samples=known)
        L.changed()
        assert t.open and len(t.turns) == 1
    t, L, now = _words_turn(tmp_path, monkeypatch, first=b, samples=[("petrovic-petar", a)], windows=15)  # 22 s: too soon to say
    L.changed()
    assert t.open
    # a caption that stays is not judged by the voice
    t, L, now = _words_turn(tmp_path, monkeypatch, first=b, samples=[("petrovic-petar", a)])
    t.turns[-1].pop("izvor")
    L.changed()
    assert t.open and len(t.turns) == 1


def test_the_days_own_voice_is_learnt_from_the_chairs_words(tmp_path, monkeypatch):
    """25 Nov 2026, 17 Nov's speeches: an MP the chair named and who spoke a minute is known by voice for the rest of the
    day, but the turn it was learnt from is not judged by it."""
    np = pytest.importorskip("numpy")
    a, b = np.eye(512, dtype=np.float32)[:2]
    t, L, now = _words_turn(tmp_path, monkeypatch, first=a, samples=[("markovic-marko", b)], windows=70)
    L.changed()
    assert set(L.today) == {"petrovic-petar"}
    assert set(L.refs()) == {"markovic-marko"}  # not of the turn that is on
    t.unheard(now + 120)
    assert set(L.refs()) == {"markovic-marko", "petrovic-petar"} and float(L.refs()["petrovic-petar"] @ a) > 0.99
    assert "petrovic-petar" not in L.voices.sums  # only for the day, in memory
    t.day = "2026-11-26"
    t2, L2, now = _words_turn(tmp_path, monkeypatch, first=a, samples=[("petrovic-petar", a)], windows=70)
    L2.changed()
    assert L2.today == {}  # known already
    # and never of a presiding officer
    from uzivo import config
    t3, L3, now = _words_turn(tmp_path, monkeypatch, first=a, windows=70)
    monkeypatch.setattr(config, "VOICE_SKIP", {"petrovic-petar"})
    L3.changed()
    assert L3.today == {}


def test_a_name_with_a_surname_unread_is_the_sitting_mps_not_a_former_ones():
    """18 Nov 2026: "Biljana Pantić" was Biljana Pantić Pilja; a former MP of those two words took the turn."""
    from uzivo.names import Person, Roster, person_key
    people = [Person(person_key(n), n, s, "Lista") for n, s in (
        ("Pantić Pilja Biljana", "pantic-pilja-biljana"), ("Pantić Biljana", "pantic-biljana"), ("Pantić Marić Biljana", "pantic-maric-biljana"))]
    r = Roster(people)
    r.current = frozenset({"pantic-pilja-biljana"})
    assert r.match("Biljana Pantić", 0.8).slug == "pantic-pilja-biljana"
    assert r.match("Biljana Pantić Pilja", 0.8).slug == "pantic-pilja-biljana"
    r.current = frozenset({"pantic-pilja-biljana", "pantic-maric-biljana"})  # two sitting MPs: not either's
    assert r.match("Biljana Pantić", 0.8).slug == "pantic-biljana"
    r.current = frozenset({"pantic-biljana", "pantic-pilja-biljana"})  # sitting herself: whole words win
    assert r.match("Biljana Pantić", 0.8).slug == "pantic-biljana"


def test_listening_live_a_playlist_of_the_broadcasts_own_sound(tmp_path, monkeypatch):
    """22 Nov 2026, the maintainer's trial: each fetched segment's sound into a live HLS playlist of our own, copied
    as it is with its timestamps, the last WINDOW kept, a gap marked; a player reads it as one stream."""
    import shutil
    import subprocess
    import pytest
    from uzivo import config, slusaj
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("ffmpeg")
    src = tmp_path / "src"
    src.mkdir()
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=20",
                    "-f", "lavfi", "-i", "color=c=black:s=64x36:d=20", "-shortest", "-c:a", "aac", "-c:v", "libx264",
                    "-f", "segment", "-segment_time", "5", "-segment_format", "mpegts", str(src / "s%d.ts")], check=True)
    pl = slusaj.Playlist(tmp_path / "out")
    for n in range(4):
        assert pl.add(str(src / f"s{n}.ts"), 5.0, 100 + n, 1000.0 + n)
    text = pl.text()
    assert "#EXT-X-MEDIA-SEQUENCE:100" in text and text.count("#EXTINF:") == 4 and "DISCONTINUITY" not in text
    assert "#EXT-X-ENDLIST" not in text  # live
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type",
                            "-of", "csv=p=0", str(tmp_path / "out" / "z.m3u8")], capture_output=True, text=True)
    assert "audio" in probe.stdout and "video" not in probe.stdout
    assert abs(float([x for x in probe.stdout.split() if x.replace(".", "").isdigit()][-1]) - 20) < 1.5
    # a stall: the next number skipped, marked; the window keeps the newest
    assert pl.add(str(src / "s0.ts"), 5.0, 110, 2000.0)
    assert "#EXT-X-DISCONTINUITY\n#EXTINF:5.000,\nz110.ts" in pl.text()
    for n in range(111, 111 + slusaj.WINDOW):
        pl.add(str(src / "s1.ts"), 5.0, n, 3000.0)
    assert pl.text().count("#EXTINF:") == slusaj.WINDOW and "z110.ts" not in pl.text()
    assert pl.segment("z111.ts") and pl.segment("../stanje.json") is None
    monkeypatch.setattr(config, "TRANSCRIPT_KEY", "")
    assert not slusaj.on()


def test_the_live_sound_goes_to_the_bucket_signed_as_s3_wants(monkeypatch):
    """22 Nov 2026, the maintainer's choice: the live sound from Cloudflare R2. The PUT's signature (AWS Signature
    Version 4) is the one botocore gives for the same request and moment (checked then, kept here); the playlist in
    the bucket names its segments under the broadcast's id; the page offers the bucket's address once it is set."""
    import datetime as dt
    from uzivo import r2, slusaj
    when = dt.datetime(2026, 11, 22, 23, 37, 52, tzinfo=dt.timezone.utc)
    req = r2.request("uzivo/vid_1/z100870.ts", b"\x47" * 1880, "video/mp2t", "public, max-age=86400, immutable", now=when,
                     endpoint="https://abc123.r2.cloudflarestorage.com", bucket="zailiprotiv-zvuk", key_id="KEYID",
                     secret="SECRETVALUE", region="auto")
    assert req.full_url == "https://abc123.r2.cloudflarestorage.com/zailiprotiv-zvuk/uzivo/vid_1/z100870.ts"
    assert dict(req.header_items())["Authorization"].endswith(
        "Signature=4ada9e739d5b8ee4ac7441d8da127ea0562c7ddd617cfff324f3b6be555ee3d8")
    pl = slusaj.Playlist("/nonexistent")
    pl.items, pl.video = [(5, 2.0, False), (6, 2.0, False)], "vid_1"
    assert "vid_1/z5.ts" in pl.text(folder="vid_1") and "\nz5.ts" in pl.text()
    monkeypatch.setattr(r2, "PUBLIC", "")
    assert slusaj.address() == "/slusaj/z.m3u8"
    for k, v in (("ENDPOINT", "https://abc.r2.cloudflarestorage.com"), ("BUCKET", "b"), ("KEY_ID", "k"), ("SECRET", "s"),
                 ("PUBLIC", "https://zvuk.zailiprotiv.rs/")):
        monkeypatch.setattr(r2, k, v)
    assert slusaj.address() == "https://zvuk.zailiprotiv.rs/uzivo/z.m3u8"


def test_the_floor_given_now_and_the_chair_by_voice(tmp_path, monkeypatch):
    """22 Nov 2026, replaying 19 Nov: "Reč ima X, a posle njega ima reč Y" gives the floor to X now; a turn found by
    the chair's words ends when its voice changes; a presiding officer's voice is the chair, said on top."""
    from uzivo import hronika, config
    from uzivo.names import Person
    people = [Person("a", "Bakić Jovo", "bakic-jovo", ""), Person("b", "Jovanov Milenko", "jovanov-milenko", "")]
    text = "Reč ima Jovo Bakić, a posle njega ima reč Milenko Jovanov."
    assert [p.slug for p in hronika.floor(text, people)] == ["bakic-jovo", "jovanov-milenko"]
    assert [p.slug for p in hronika.floor(text, people, now_only=True)] == ["bakic-jovo"]
    np = pytest.importorskip("numpy")
    import threading as th
    from uzivo import glas
    monkeypatch.setattr(config, "SOUND_PATH", str(tmp_path))
    now = 1795100000.0
    t = Tracker(None, "Europe/Belgrade")
    t.roster = ROSTER
    t.observe(None, now=now)
    petar = next(p for p in ROSTER.people if p.slug == "petrovic-petar")
    t.heard(petar, "prepis", now + 1, now + 1)
    a, b = np.zeros(512, np.float32), np.zeros(512, np.float32)
    a[0], b[1] = 1, 1
    L = glas.Listener(t, th.Event(), embed=lambda x: a, path=tmp_path / "none.npz")
    L.t = [now + 1 + 1.5 * i for i in range(50)]  # 75 s: his voice (a) for 30 s, then another (b): both sides of a cut need 20 s
    L.f = [a if i < 20 else b for i in range(50)]
    L.changed()
    snap = t.snapshot(now + 77)
    assert snap["stanje"] != "govori" and t.turns_now()[-1]["seen"] <= now + 1 + 1.5 * 22
    # the chair's voice: a presiding officer's, said on top
    monkeypatch.setattr(config, "VOICE_SKIP", {"markovic-marko"})
    np.savez_compressed(tmp_path / "v.npz", slugs=np.array(["markovic-marko"]), vecs=np.stack([b]), counts=np.array([30]))
    L = glas.Listener(t, th.Event(), embed=lambda x: b, path=tmp_path / "v.npz")
    L.t, L.f = [now + 50 + 1.5 * i for i in range(16)], [b] * 16
    t.observe(None, now=now + 75)
    L.judge()
    snap = t.snapshot(now + 75)
    assert snap["predsedava"] == {"ime": "Marković Marko", "adresa": "markovic-marko"} and snap["sada"] is None
    from uzivo.page import fragment
    html = fragment(snap, cyr=False, site="", tz=TZ)
    assert "Predsedava: Marko Marković</span>" in html and "po glasu" not in html  # how is under "Kako ovo radi"


def test_a_test_container_has_none_of_the_live_services_secrets():
    """Every secret the service reads from its .env is emptied in the test's compose file (23 Nov 2026: a test had the
    keys of the live sound's bucket). The page's own key stays: it opens the pages one looks at."""
    import re
    live = Path(__file__).parents[1] / "live"
    read = set()
    for f in (live / "uzivo").glob("*.py"):
        read |= set(re.findall(r'environ(?:\.get\(|\[)"([A-Z0-9_]+)"', f.read_text(encoding="utf-8")))
    secret = {n for n in read if re.search(r"KEY|TOKEN|KLJUC|TAJNA|SECRET|LOZINKA|R2_(ENDPOINT|BUCKET)|MEJL", n)} - {"PREPIS_KLJUC"}
    assert {"MEJL_KLJUC", "ZVUK_R2_TAJNA", "PUSH_TOKEN", "ANTHROPIC_API_KEY"} <= secret
    compose = (live / "docker-compose.test.yml").read_text(encoding="utf-8")
    empty = set(re.findall(r'^ {6}([A-Z0-9_]+): "(?:\$\{TEST_[A-Z_]+:-\})?"', compose, re.M))
    assert secret <= empty, secret - empty


def test_the_service_keeps_every_file_by_the_one_writer(tmp_path):
    """Written beside and moved into place, so that a crash leaves the old file or the new one, never half of one; no
    other part writes a kept file itself (the sound's pieces and the day's reading in zvuk_dana are work files)."""
    from uzivo.state_base import _write, write_text
    write_text(tmp_path / "a" / "x.json", "ž")
    _write(tmp_path / "a" / "x.json", {"ž": 1})
    assert (tmp_path / "a" / "x.json").read_text(encoding="utf-8") == '{"ž": 1}' and len(list((tmp_path / "a").iterdir())) == 1
    own = {"state_base.py", "slusaj.py", "zvuk_dana.py"}
    live = Path(__file__).parents[1] / "live" / "uzivo"
    assert not [f.name for f in live.glob("*.py") if f.name not in own and ".write_text(" in f.read_text(encoding="utf-8")]


def test_the_counter_is_asked_with_the_token_and_the_site_without(monkeypatch):
    import io
    from uzivo import mreza
    asked = []

    def opened(req, timeout=0):
        asked.append((req.get_method(), req.full_url, dict(req.header_items()), req.data, timeout))
        return io.BytesIO('{"ok": "ž"}'.encode())
    monkeypatch.setattr(mreza.urllib.request, "urlopen", opened)
    assert mreza.site("https://zailiprotiv.rs/podaci.json") == '{"ok": "ž"}'
    assert mreza.counter("https://b.rs/m/spisak", "t") == {"ok": "ž"}
    assert mreza.counter("https://b.rs/p/salji", "t", {"od": 0}, timeout=15) == {"ok": "ž"}
    assert [a[0] for a in asked] == ["GET", "GET", "POST"] and asked[2][3] == b'{"od": 0}' and asked[2][4] == 15
    assert "Authorization" not in asked[0][2] and asked[1][2]["Authorization"] == asked[2][2]["Authorization"] == "Bearer t"


def test_before_a_sitting_a_pasted_link_announces_it_and_past_the_hour_it_does_not(monkeypatch):
    """23 Nov 2026, the maintainer: the link's picture before a sitting is the announcement, not who spoke how long."""
    from datetime import datetime
    from uzivo import page, picture
    snap = Tracker(None, "Europe/Belgrade").snapshot()
    snap = {**snap, "stanje": "nema_prenosa", "dan": "2026-11-19", "ranije": True,
            "obavestenja": [{"od": "2026-11-20", "do": "2026-11-24", "url": "https://www.parlament.gov.rs/x.html",
                             "tekst": "Narodna skupština nastavlja sa radom u utorak, 24. novembra 2026. godine, u 10.00 časova."}],
            "dnevni_red": {"tacke": [{"n": 5, "tekst": "Izbor članova radnih tela Narodne skupštine", "stanje": "na_redu"}]}}
    monkeypatch.setattr(page, "_now", lambda: datetime(2026, 11, 24, 9, 59, tzinfo=TZ))
    title, line = page.og_text(snap, cyr=False, tz=TZ)
    assert title == "Skupština nastavlja sa radom u utorak, 24. novembra, u 10.00"
    assert line == ("Na redu: Izbor članova radnih tela Narodne skupštine. "
                    "Uživo: ko govori, opomene, glasanja i snimak svakog govora.")
    assert "Скупштина наставља са радом у уторак" in page.og_text(snap, cyr=True, tz=TZ)[0]
    before = page._og(snap, cyr=False, url="https://mikrofon.zailiprotiv.rs/", tz=TZ)
    assert "slika.png?v=najava3-2026-11-20" in before and "Najviše vremena" not in before
    a = picture.render(snap, cyr=False, tz=TZ, host="mikrofon.zailiprotiv.rs")
    assert a[:8] == b"\x89PNG\r\n\x1a\n" and picture.render(snap, cyr=True, tz=TZ) != a
    monkeypatch.setattr(page, "_now", lambda: datetime(2026, 11, 24, 10, 0, tzinfo=TZ))
    assert page.announced(snap) == ("", {}) and "najava" not in page._og(snap, cyr=False, url="https://mikrofon.zailiprotiv.rs/", tz=TZ)
    assert "goes-on" not in page._status(snap, cyr=False)  # the evening of the sitting doesn't say it goes on that morning
    # a notice of December speaking of January; somebody on the air: no announcement
    jan = {**snap, "obavestenja": [{"od": "2026-12-28", "tekst": "Narodna skupština nastavlja sa radom u utorak, 12. januara 2027. godine, u 10.00 časova."}]}
    monkeypatch.setattr(page, "_now", lambda: datetime(2026, 12, 30, 9, 0, tzinfo=TZ))
    assert page.announced(jan)[0] and not page.announced({**jan, "stanje": "govori"})[0]


def test_the_assemblys_listing_announces_a_sitting_by_one_rule_begun_or_convened(monkeypatch):
    """25 Nov 2026: what had a hand in it (the notice) comes from the Assembly's listing ("sazvano"); the card on top, the
    link's line and picture, for a sitting that goes on and for one convened."""
    from datetime import datetime
    from uzivo import page, picture
    url = "https://www.parlament.gov.rs/x.html"
    agenda = {"url": url, "tacke": [{"n": 5, "tekst": "Izbor članova radnih tela", "stanje": "gotova", "izvor": "sajt"},
                                    {"n": 6, "tekst": "Izbor delegacija", "stanje": "na_redu"}]}
    snap = {**Tracker(None, "Europe/Belgrade").snapshot(), "stanje": "nema_prenosa", "dnevni_red": agenda,
            "sazvano": {"naslov": "Prva sednica", "url": url, "pocinje": "2026-11-25T10:00", "tacke": [], "nastavak": True}}
    monkeypatch.setattr(page, "_now", lambda: datetime(2026, 11, 24, 21, 0, tzinfo=TZ))
    html = fragment(snap, cyr=False, site="", tz=TZ)
    assert "Sednica sutra u 10 h" in html and "<li>6. Izbor delegacija</li>" in html and "5. Izbor" not in html.split("st-bell")[0]
    assert "Skupština nastavlja sa radom u sredu, 25. novembra, u 10.00." in html and f'href="{url}"' in html
    assert 'class="nx"' not in html  # the card says it once
    assert page.og_text(snap, cyr=False, tz=TZ)[0] == "Skupština nastavlja sa radom u sredu, 25. novembra, u 10.00"
    assert "najava3-2026-11-25T1000" in page._og(snap, cyr=False, url="https://m/", tz=TZ)
    assert picture.render(snap, cyr=True, tz=TZ) != picture.render({**snap, "sazvano": None}, cyr=True, tz=TZ)
    other = fragment({**snap, "dnevni_red": {**agenda, "url": "https://www.parlament.gov.rs/y.html"}}, cyr=False, site="", tz=TZ)
    assert "<li>6. Izbor" not in other.split("st-bell")[0]  # another sitting's agenda is not this one's
    # one convened: its own items, and it goes on with nothing; the countdown stays, with its agenda
    new = {**snap, "sazvano": {"naslov": "Druga sednica", "url": url, "pocinje": "2026-11-25T10:00", "tacke": ["Budžet"]}}
    html = fragment(new, cyr=False, site="", tz=TZ)
    assert "Sednica sutra u 10 h" in html and "<li>1. Budžet</li>" in html and 'class="nx"' in html and "nastavlja" not in html
    assert page.og_text(new, cyr=False, tz=TZ) == ("Skupština u sredu, 25. novembra, u 10.00",
        "Na redu: Budžet. Uživo: ko govori, opomene, glasanja i snimak svakog govora.")
    # the notice by hand in the words of that morning; with a nearer sitting in the listing that one is said
    note = {"od": "2026-11-25", "do": "2026-11-26", "url": url,
            "tekst": "Narodna skupština nastavlja rad u četvrtak, 26. novembra 2026. godine, sa početkom u 10.00 časova."}
    assert page._resumes(note["tekst"]) == "u četvrtak, 26. novembra, u 10.00"
    assert page.announcement({**snap, "obavestenja": [note]})[2].day == 25
    assert page.announcement({**snap, "sazvano": None, "obavestenja": [note]})[2].day == 26
    # its hour come and no broadcast yet: the countdown, by its own name; a day with no hour too
    monkeypatch.setattr(page, "_now", lambda: datetime(2026, 11, 25, 10, 5, tzinfo=TZ))
    late = page.countdown(snap, cyr=False, tz=TZ, now=datetime(2026, 11, 25, 10, 5, tzinfo=TZ).timestamp())
    assert page.announced(snap) == ("", {}) and "Nastavak sednice" in late and "Počinje uskoro" in late
    assert page.announcement({**snap, "sazvano": {**snap["sazvano"], "pocinje": "2026-11-26"}})[2] is None


def test_each_sitting_has_its_own_agenda_and_the_item_heard_at_it(tmp_path):
    """25 Nov 2026: the last item heard is kept across days, so the Second sitting's first items would have stood as done
    by the chair's word, and the First's last day would have had the Second's items in its steps."""
    from datetime import datetime
    at = lambda d, h, m=0: datetime(2026, 11 if d > 20 else 12, d, h, m, tzinfo=TZ).timestamp()
    t = Tracker(str(tmp_path / "state.json"), "Europe/Belgrade")
    row = lambda name, day, n: {"naslov": name, "url": f"https://x/{name}", "pocinje": day,
                                "tacke": [{"n": i, "tekst": f"{name} {i}", "gotova": False} for i in range(1, n + 1)]}
    t.use_waiting({"kviz": [], "cinjenice": [], "dnevni_red": [row("Druga", "2026-12-01T10:00", 8), row("Prva", "", 6)],
                   "sazvano": {"naslov": "Druga", "url": "https://x/Druga", "pocinje": "2026-12-01T10:00", "tacke": []}})
    t._load("2026-11-25")
    t.item = {"n": 6, "t": int(at(25, 11))}
    states = lambda a: [x["stanje"] for x in a["tacke"]]
    snap = t.snapshot(now=at(25, 13))  # closed at noon, the Second convened
    assert snap["dnevni_red"]["naslov"] == "Druga" and states(snap["dnevni_red"]) == ["na_redu"] + [""] * 7
    assert snap["dnevni_red_dana"]["naslov"] == "Prva" and states(snap["dnevni_red_dana"])[-1] == "u_toku"
    from uzivo.steps import model_steps
    snap = {**snap, "hronika": [{"t": int(at(25, 11)), "vrsta": "Tačka dnevnog reda", "izvor": "model", "url": "",
                                 "tekst": "Prelazimo na šestu tačku dnevnog reda.", "vise": {"tacka": 6}}]}
    assert "Prva 6" in str(model_steps(snap)) and "Druga 6" not in str(model_steps(snap))
    t._load("2026-12-01")
    t.observe(None, now=at(1, 10, 1))
    snap = t.snapshot(now=at(1, 10, 2))
    assert states(snap["dnevni_red"]) == ["na_redu"] + [""] * 7 and "dnevni_red_dana" not in snap
    t.note(at(1, 10, 30), "Tačka dnevnog reda", "Prelazimo na drugu tačku dnevnog reda.", "prepis")
    assert t.item["n"] == 2  # lower than the First's sixth: another sitting's count
    t._snap = None
    assert states(t.snapshot(now=at(1, 10, 31))["dnevni_red"])[:3] == ["gotova", "u_toku", ""]
    t.note(at(1, 11), "Tačka dnevnog reda", "Prelazimo na prvu tačku dnevnog reda.", "prepis")
    assert t.item["n"] == 2  # within a sitting it only goes on


def test_a_sitting_that_has_begun_is_no_longer_the_next_one():
    """25 Nov 2026: in its break and on its evening the page would have said that it begins soon."""
    from datetime import datetime
    t = Tracker(None, "Europe/Belgrade")
    at = lambda h, m=0: datetime(2026, 11, 25, h, m, tzinfo=TZ).timestamp()
    t.use_waiting({"kviz": [], "cinjenice": [], "sazvano": {"naslov": "Prva", "url": "https://www.parlament.gov.rs/x",
                   "pocinje": "2026-11-25T10:00", "tacke": [], "nastavak": True}})
    t._load("2026-11-25")
    assert t.snapshot(now=at(9))["sazvano"]
    t.observe(None, now=at(9, 55))  # the broadcast is on before its hour
    assert t.snapshot(now=at(9, 56))["sazvano"]
    t.observe(None, now=at(10, 1))
    assert t.snapshot(now=at(10, 2))["sazvano"] is None and t.snapshot(now=at(19))["sazvano"] is None


def test_the_app_and_the_notification_say_what_they_give_with_a_mark_each():
    """23 Nov 2026, the maintainer: say that the page becomes an app, and mark both buttons."""
    from uzivo import page
    snap = Tracker(None, "Europe/Belgrade").snapshot()
    html = page.page(snap, cyr=False, site="https://zailiprotiv.rs/", tz=TZ, api="https://glasovi.zailiprotiv.rs", push_key="k")
    for words in ("Dodaj kao aplikaciju", "Obavesti me", 'aria-label="Obavesti me kad sednica počne"'):  # pills, 24 Nov 2026
        assert words in html
    assert html.count('class="pill-b') >= 2 and 'class="ic-share"' in html
    for cls in ("nt-on", "add-go", "nt-off", "add-ios"):  # what the page's script looks for
        assert f" {cls}" in html or f'"{cls}' in html
    assert "Додај као апликацију" in page.page(snap, cyr=True, site="https://zailiprotiv.rs/", tz=TZ)


def test_what_a_search_engine_takes_of_the_page():
    """23 Nov 2026: Google showed the player's note as the page's description, and the address as its name."""
    from uzivo.page import page, player
    day = {"stanje": NO_STREAM, "provereno": 0, "sada": None, "dan": "2026-11-19", "ranije": True, "danas": [],
           "datoteke": [{"url": "https://arhiva.videonet.co.rs/a.mp4", "od": 0, "trajanje": 60}]}
    assert '<p class="meta" data-nosnippet>' in player(day, cyr=False, tz=TZ)
    html = page(day, cyr=False, site="https://zailiprotiv.rs/", tz=TZ, url="https://mikrofon.zailiprotiv.rs/")
    assert '"@type": "WebSite", "name": "Mikrofon Za ili Protiv"' in html
    assert "application/ld+json" not in page(day, cyr=True, site="https://zailiprotiv.rs/", tz=TZ, url="https://mikrofon.zailiprotiv.rs/")


def test_a_break_shows_what_happened_until_it():
    """24 Nov 2026, the maintainer: while a break lasts, the model's paragraph of the stretch, the measures counted by
    the code and the hour the chair said; never the speakers' lines; gone once the sitting goes on."""
    from datetime import datetime
    from uzivo import page as page_
    at = lambda h, m: int(datetime(2026, 11, 24, h, m, tzinfo=TZ).timestamp())
    ev = lambda t, kind, text, **more: {"t": t, "vrsta": kind, "tekst": text, "izvor": "model", "url": "", "vise": more}
    b = at(14, 10)
    snap = {"stanje": "nepoznato", "provereno": b + 900, "sada": None, "ranije": False, "dan": "2026-11-24",
            "danas": [{"ime": "Petrović Petar", "od": at(14, 0), "do": at(14, 8), "sekundi": 480, "grupa": "", "adresa": ""}], "dnevni_red": None,
            "hronika": [ev(b, "Pauza", "Proglašavam pauzu do 15 sati i 10 minuta."),
                        ev(at(12, 10), "Mera predsedavajućeg", "Izričem vam opomenu.", napomena="opomena"),
                        ev(at(9, 10), "Mera predsedavajućeg", "Izričem vam opomenu.", napomena="opomena")],
            "sazetak": {"vrsta": "deo", "ukratko": "Raspravljalo se o odborima.", "t_od": at(11, 0), "t_do": b + 1,
                        "tok": [{"vreme": "13:00", "sta": "Glasano o predlogu.", "glasovi": "za 136, protiv 2"}],
                        "govornici": [{"ime": "Petrović Petar", "o_cemu": "o tajnoj temi"}]}}
    html = page_._break(snap, cyr=False, tz=TZ)
    assert "Raspravljalo se o odborima." in html and "u 15:10" in html and "Claude Haiku" in html
    assert "1 × opomena (12:10)" in html and "09:10" not in html  # the stretch's measures only
    assert '<b class="v-za">za 136</b>' in html and "tajnoj" not in html
    assert html in page_.fragment({**snap, "danas": []}, cyr=False, site="https://zailiprotiv.rs/", tz=TZ)
    assert "Распр" in page_._break(snap, cyr=True, tz=TZ)
    later = {"ime": "Jović Jova", "od": b + 600, "do": b + 700, "sekundi": 100}
    for gone in ({"danas": [later, *snap["danas"]]}, {"stanje": "govori"}, {"sada": later}, {"ranije": True},
                 {"sazetak": {**snap["sazetak"], "vrsta": "dan"}}, {"sazetak": None}):
        assert page_._break({**snap, **gone}, cyr=False, tz=TZ) == ""
    for said, hour in (("Pauza do 15.30", "15:30"), ("nastavljamo u 16 časova", "16:00"), ("pauzu od jednog sata", ""),
                       ("pauza do 12 sati", ""), ("pauza do 5 minuta", "")):
        assert page_._resumes_at(said, b, TZ) == hour


def test_the_day_is_summed_up_by_the_stronger_model_from_the_whole_transcript(tmp_path, monkeypatch):
    """24 Nov 2026, the maintainer: Haiku during the sitting, Opus for the day's summary; each speaker's line rests on
    a sentence of their own, kept for the maintainer only; when it does not work, the stretches tell the day."""
    from uzivo import sudija
    monkeypatch.setattr(config, "STATE_PATH", str(tmp_path / "stanje.json"))
    monkeypatch.setattr(config, "DAY_MODEL", "claude-opus-5-5")
    t = Tracker(str(tmp_path / "stanje.json"), "Europe/Belgrade")
    base = 1795082400
    t.day = t._day(base)
    t.say(base + 10, "Nisam učestvovala u kontroli tog projekta i to vam kažem.")
    t.say(base + 250, "Proglašavam pauzu od deset minuta.", chair=True)
    turns = [{"ime": "Jović Jova", "lista": "Lista za primer", "od": base + 5, "do": base + 200},
             {"ime": "Kratki Kosta", "lista": "Lista", "od": base + 205, "do": base + 225}]
    rows, j = sudija.pieces(dict(t._said_of(t.day))), None
    seen = []

    def day(basis):
        return json.dumps({"kratko": "K.", "ukratko": "U.", "odluke": [], "tok": [], "govornici": [
            {"ime": "Jović Jova", "lista": "nešto", "o_cemu": "Poricala učešće.", "oslonac": [basis]}]})

    def ask_bad_then_good(system, user, *rest):
        seen.append((system, user, rest))
        return day("Ovo nikad nije rekla niko ovde" if len(seen) == 1 else "Nisam učestvovala u kontroli tog projekta")

    j = sudija.Judge(t, threading.Event(), ask=ask_bad_then_good)
    j._load(t.day)
    s = j._whole(rows, turns)
    assert len(seen) == 2 and seen[0][0] is sudija.WHOLE and seen[0][2][-1] == "claude-opus-5-5"
    assert "Kratki" not in seen[0][1].split("Prepis dana")[0] and "oslonac za 'Jović Jova'" in seen[1][1]
    assert "oslonac" not in json.dumps(s) and s["govornici"][0]["lista"] == "Lista za primer"
    kept = json.loads((tmp_path / "osnova" / f"{t.day}.json").read_text(encoding="utf-8"))
    assert kept["bez_oslonca"] == [] and kept["oslonac"]["Jović Jova"][0].startswith("Nisam")
    j.ask = lambda system, user, *rest: day("Ovo nikad nije rekla niko ovde")  # never found: kept, and said to the maintainer
    assert j._whole(rows, turns)["govornici"]
    assert json.loads((tmp_path / "osnova" / f"{t.day}.json").read_text(encoding="utf-8"))["bez_oslonca"] == ["Jović Jova"]

    def boom(*a):
        raise RuntimeError("no")
    j.ask = boom
    assert j._whole(rows, turns) is None  # the stretches tell the day
    from uzivo import page as page_
    assert page_._model({"model": "claude-opus-5-5"}) == "Claude Opus" and page_._model({}) == "Claude Haiku"


def test_a_speech_that_has_ended_gets_its_topic_checked_twice(tmp_path, monkeypatch):
    """24 Nov 2026, the maintainer: a line by Haiku under each speech when it ends, the topic only; what it rests on
    must be in the speech, a second call judges it, and one that fails twice is left out."""
    from uzivo import rezimei, sudija
    from uzivo import page as page_
    monkeypatch.setattr(config, "STATE_PATH", str(tmp_path / "stanje.json"))
    t = Tracker(str(tmp_path / "stanje.json"), "Europe/Belgrade")
    base = 1795082400
    t.day = t._day(base)
    words = "Govorim o sastavu odbora i o tome ko u njima sedi, jer to je važno za kontrolu vlasti u ovoj zemlji, i zato pitam ko je o tome odlučio danas."
    t.say(base + 10, words)
    speech = {"ime": "Jović Jova", "od": base + 5, "do": base + 200, "sekundi": 195, "lista": "Lista", "grupa": "Lista", "uloga": "", "adresa": ""}
    short = {**speech, "ime": "Kratki Kosta", "od": base + 205, "do": base + 225, "sekundi": 20}
    snap = {"dan": t.day, "ranije": False, "snimak": False, "danas": [short, speech]}
    monkeypatch.setattr(t, "snapshot", lambda now=None: snap)
    monkeypatch.setattr(rezimei.prepis, "waiting", lambda: [])
    answers, asked = [], []

    def ask(system, user):
        asked.append(system)
        if system is rezimei.CHECK:
            return json.dumps({"tacno": answers.pop(0), "razlog": "pretpostavlja"})
        return json.dumps({"rezime": "O sastavu odbora.", "oslonac": "Govorim o sastavu odbora i o tome ko u njima sedi"})

    w = rezimei.Writer(t, threading.Event(), ask=ask)
    assert w.due(snap, base + 210, []) == []  # ended ten seconds ago: not yet
    assert w.due(snap, base + 260, [(base + 100, 5, None)]) == []  # its sound still waits to be written down
    answers[:] = [False, True]
    w.step(now=base + 300)
    assert [k["rezime"] for k in w.kept] == ["O sastavu odbora."] and asked.count(rezimei.LINE) == 2
    assert rezimei.shown(w.kept, speech) == "O sastavu odbora." and rezimei.shown(w.kept, short) == ""
    asked.clear()
    w.step(now=base + 400)  # kept: not asked again; the short speech never
    assert asked == []
    stored = (tmp_path / "rezimei" / f"{t.day}.json").read_text(encoding="utf-8")
    assert "Govorim o sastavu" not in stored  # the transcript's sentence is never kept

    for bad in ("Govori o odborima.", "O odboru 5.", "O „odboru“.", "O " + "reč " * 25):
        w2 = rezimei.Writer(t, threading.Event(), ask=lambda s, u, bad=bad: json.dumps({"rezime": bad, "oslonac": words[:60], "tacno": True}))
        assert w2.line(words) == ("", True), bad
    w3 = rezimei.Writer(t, threading.Event(), ask=lambda s, u: json.dumps({"rezime": "O odborima.", "oslonac": "ovo nikad nije rečeno ovde", "tacno": True}))
    assert w3.line(words) == ("", True)

    html = page_.fragment({"stanje": "nepoznato", "provereno": base + 900, "sada": None, "ranije": False, "dan": t.day, "dnevni_red": None,
                           "hronika": [], "sazetak": None, "danas": [{**speech, "rezime": "O sastavu odbora."}]},
                          cyr=False, site="https://zailiprotiv.rs/", tz=TZ)
    assert '<p class="rz">O sastavu odbora.</p>' in html and "Claude Haiku" in html
    assert html.index("Svi govori, redom") < html.index("sub\">Ko je koliko") if "Ko je koliko" in html else True


def test_the_shared_links_picture_says_nothing_that_goes_stale():
    """24 Nov 2026, the maintainer: a service keeps the picture by its address, so it is the same whoever speaks and
    whatever is on; only before a sitting it is the announcement, which names its day."""
    pytest.importorskip("PIL")
    import io
    from PIL import Image
    from uzivo import picture
    from uzivo import page as page_
    base = {"dan": "2026-11-24", "ranije": False, "danas": [], "dnevni_red": None, "hronika": [], "obavestenja": [], "sazetak": None, "provereno": 5}
    cur = {"ime": "Jović Jova", "od": 1, "sekundi": 60, "lista": "Lista", "o": {"foto": "12.jpg"}}
    pause = {"t": 1795525857, "vrsta": "Pauza", "izvor": "model", "tekst": "Proglašavam pauzu do 15 sati i 10 minuta.", "url": ""}
    states = [{**base, "stanje": SPEAKING, "sada": cur}, {**base, "stanje": "nepoznato", "sada": None},
              {**base, "stanje": "nepoznato", "sada": None, "hronika": [pause]}, {**base, "stanje": NO_STREAM, "sada": None, "ranije": True}]
    drawn = {picture.render(s_, cyr=False, tz=TZ) for s_ in states}
    assert len(drawn) == 1 and Image.open(io.BytesIO(drawn.pop())).size == (1200, 630)
    assert picture.render(states[0], cyr=True, tz=TZ) != picture.render(states[0], cyr=False, tz=TZ)
    assert all("slika.png?v=s4" in page_._og(s_, cyr=False, url="https://mikrofon.zailiprotiv.rs/", tz=TZ) for s_ in states)


def test_the_broadcasts_clock_joins_a_speech_cut_in_two():
    """24 Nov 2026, the maintainer, of Milena Đorđijević: the floor given at 16:56:50, the turn ended at 16:57:46, the caption
    back at 17:08:32 with 11:26 on the clock: one speech. Never another's turn, nor one begun after."""
    now = 1795519000.0
    marko = next(p for p in ROSTER.people if p.slug == "markovic-marko")
    petar = next(p for p in ROSTER.people if p.slug == "petrovic-petar")

    def cut(other=None):
        t = Tracker(None, "Europe/Belgrade")
        t.roster = ROSTER
        t.observe(None, now=now)
        t.heard(petar, "prepis", now, now)
        t.heard(marko, "prepis", now + 10, now + 10)
        t.turns[-1]["seen"] = now + 66
        t._close()
        if other:
            t.heard(other, "prepis", now + 300, now + 320)
            t._close()
        t.heard(marko, "potpis", now + 712, now + 712)
        return t
    t = cut()
    assert len(t.turns) == 3
    t.clocked(marko, now + 712, 686)  # one reading is not yet sure
    assert len(t.turns) == 3
    t.clocked(marko, now + 717, 691)  # began at now + 26, in the turn before
    last = t.turns_now()[-1]
    assert len(t.turns) == 2 and last["key"] == marko.key and t.open
    assert abs(last["start"] - (now + 26)) <= 1 and last["seen"] >= now + 712 and last["izvor"] == "potpis"
    t = cut(petar)  # another spoke between: not joined
    t.clocked(marko, now + 712, 686)
    t.clocked(marko, now + 717, 691)
    assert len(t.turns) == 4 and t.turns_now()[-1]["start"] == now + 712
    t = cut()  # the clock says a speech of its own, begun after: not joined
    t.clocked(marko, now + 712, 5)
    t.clocked(marko, now + 717, 10)
    assert len(t.turns) == 3 and abs(t.turns_now()[-1]["start"] - (now + 707)) <= 1


def test_the_words_kept_as_the_chairs_inside_a_mended_turn_are_the_speakers():
    """24 Nov 2026, Milena Đorđijević: ten minutes written down under the chair's key while her turn was cut; read as
    hers once the turn holds them, but for what only the chair says and for what is at its edges."""
    from uzivo import rezimei, sudija
    from uzivo.state_base import speakers_own
    d = {"ime": "Đorđijević Milena", "lista": "Lista", "od": 1000, "do": 1900}
    said = {"1004": "Poštovani,", "p1100": "Biblioteka Srbije je spomenik kulture.", "p1500": "Reč ima poslanik Petrović.",
            "p1890": "Odbor nije odgovorio ni na jedno pitanje.", "1895": "Hvala.", "p2000": "Nastavljamo dalje."}
    assert rezimei.spoken(said, d) == "Poštovani, Biblioteka Srbije je spomenik kulture. Hvala."  # not the chair's, nor the last seconds
    assert speakers_own(1100, "Biblioteka je spomenik.", 1000, 1900) and not speakers_own(1003, "x", 1000, 1900)
    out = [l for _, l in sudija.lines(sudija.pieces(said), [d], TZ)]
    assert "Đorđijević Milena (Lista)" in out[0] and not any("bez potpisa" in l and "Biblioteka" in l for l in out)
    assert any("Reč ima poslanik Petrović" in l and "bez potpisa" in l for l in out)


def test_a_speech_cut_by_a_silent_voice_is_joined_when_its_words_are_written():
    """24 Nov 2026, Vjerica Radeta: 14 s of her speech nobody's, joined by the rule of words once they are there; not over the
    chair's words, nor when another has the floor between."""
    import time as _time
    now = 1795532500.0
    marko = next(p for p in ROSTER.people if p.slug == "markovic-marko")
    petar = next(p for p in ROSTER.people if p.slug == "petrovic-petar")

    def cut():
        t = Tracker(None, "Europe/Belgrade")
        t.roster = ROSTER
        t.day = t._day(now)
        t.observe(None, now=now)
        t.heard(marko, "glas", now, now + 100)
        t._close()
        t.heard(marko, "glas", now + 114, now + 150)
        return t
    words = " ".join(["reč"] * 40)
    t = cut()
    assert len(t.turns) == 2  # no words between yet
    t.say(now + 100, words)
    assert len(t.turns) == 1 and t.turns[0]["start"] == now and t.turns[0]["seen"] >= now + 150 and t.open
    t = cut()
    t.say(now + 100, "Reč ima poslanik. " + words, chair=True)  # the chair's words: a new turn
    assert len(t.turns) == 2
    t = cut()
    t.say(now + 60, words)  # words, but long before the gap
    assert len(t.turns) == 2
    t = cut()
    t.turns.insert(1, {**t.turns[0], "key": petar.key, "start": now + 102, "seen": now + 108})
    t.say(now + 100, words)
    assert len(t.turns) == 3


def test_applause_does_not_end_a_speech_and_the_chairs_words_do(tmp_path):
    """24 Nov 2026, the maintainer: "ako bude pauza u govoru zbog tapšanja, ti prekineš govor". A turn known by voice is held
    for HOLD_VOICE; the same voice after it goes on as one turn, in seconds; the chair's words end it at once."""
    now = 1795532500.0
    marko = next(p for p in ROSTER.people if p.slug == "markovic-marko")

    def tracker():
        t = Tracker(None, "Europe/Belgrade")
        t.roster = ROSTER
        t.day = t._day(now)
        t.observe(None, now=now)
        t.heard(marko, "glas", now, now + 100)
        return t
    t = tracker()
    t.voice_gone(now + 100, now + 112, {marko.slug})
    assert t.open and t.turns[-1]["zadrzan"] == now + 100 and t.turns[-1]["seen"] == now + 100
    t.heard(marko, "glas", now + 120, now + 130)  # he goes on after it
    assert len(t.turns) == 1 and t.turns[0]["seen"] == now + 130 and "zadrzan" not in t.turns[0]
    t = tracker()
    t.voice_gone(now + 100, now + 112, {marko.slug})
    t.say(now + 103, "Zahvaljujem. Reč ima narodni poslanik.", chair=True)
    assert not t.open and t.turns[0]["seen"] == now + 100 and t.status == UNKNOWN
    t = tracker()
    t.voice_gone(now + 100, now + 112, {marko.slug})
    t.say(now + 60, "Reč ima narodni poslanik.", chair=True)  # words long before the silence say nothing of it
    assert t.open



def test_a_held_speaker_is_known_again_in_a_few_windows(tmp_path):
    """24 Nov 2026: only the held turn's own voice, and clearly; anyone else needs the whole rule."""
    np = pytest.importorskip("numpy")
    from uzivo import glas
    now = 1795532500.0
    marko = next(p for p in ROSTER.people if p.slug == "markovic-marko")

    def tracker():
        t = Tracker(None, "Europe/Belgrade")
        t.roster = ROSTER
        t.day = t._day(now)
        t.observe(None, now=now)
        t.heard(marko, "glas", now, now + 100)
        return t
    v = np.array([1.0, 0, 0], dtype=np.float32)
    other = np.array([0, 1.0, 0], dtype=np.float32)
    lis = glas.Listener.__new__(glas.Listener)
    lis.tracker = tracker()
    lis.t = [now + 105 + 1.5 * i for i in range(6)]
    lis.f = [other, other, v, v, v, v]
    refs = {marko.slug: v, "petrovic-petar": other}
    assert lis.again(refs) == (marko, now + 108)
    lis.f = [v, v, v, v, other, v]
    assert lis.again(refs) is None
    lis.f = [v * 0.3] * 6
    assert lis.again(refs) is None


def test_the_day_ends_after_a_restart_that_read_no_frame(tmp_path, monkeypatch):
    """24 Nov 2026: restarted at 19:31, two minutes after the broadcast ended, the service knew no frame and the day's
    summary, and its mail, would never have come. Not sooner than END_QUIET after the run began: a restart in a break."""
    from uzivo import sudija
    monkeypatch.setattr(config, "STATE_PATH", str(tmp_path / "stanje.json"))
    monkeypatch.setattr(config, "DAY_MODEL", "")
    t = Tracker(str(tmp_path / "stanje.json"), "Europe/Belgrade")
    base = 1795082400
    t.day = t._day(base)
    t.say(base + 10, "Govorio sam o penzijama i o budžetu za sledeću godinu.")
    turns = [{"ime": "Petrović Petar", "lista": "Lista", "od": base + 5, "do": base + 200}]
    monkeypatch.setattr(t, "snapshot", lambda now=None: {"dan": t.day, "ranije": False, "stanje": NO_STREAM, "danas": turns,
                                                         "sada": None, "provereno": 0})
    day = json.dumps({"kratko": "Dan.", "ukratko": "Govorilo se.", "odluke": [], "tok": [], "govornici": []})
    j = sudija.Judge(t, threading.Event(), ask=lambda system, user, *rest: day if system is not sudija.EVENTS else json.dumps({"dogadjaji": []}))
    j.began = base + 3600  # an hour after the last word
    j.step(now=base + 3600 + sudija.END_QUIET - 5)
    assert j.kept["dan"] is None  # a restart in a break does not end the day
    j.step(now=base + 3600 + sudija.END_QUIET + 5)
    assert j.kept["dan"]["kratko"] == "Dan."


def test_the_day_ends_sooner_when_the_chair_closed_it_and_a_restart_does_not_begin_the_wait_anew(tmp_path, monkeypatch):
    """24 Nov 2026, the maintainer: the day's mail sooner."""
    from uzivo import sudija
    monkeypatch.setattr(config, "STATE_PATH", str(tmp_path / "stanje.json"))
    monkeypatch.setattr(config, "DAY_MODEL", "")
    base = 1795082400
    day = json.dumps({"kratko": "Dan.", "ukratko": "Govorilo se.", "odluke": [], "tok": [], "govornici": []})

    def judge(closed, frame_before=0.0, provereno=0, words_after=0):
        where = str(tmp_path / f"s{closed}{frame_before}{provereno}{words_after}" / "stanje.json")
        monkeypatch.setattr(config, "STATE_PATH", where)  # each its own day's files
        t = Tracker(where, "Europe/Belgrade")
        t.day = t._day(base)
        t.say(base + 10, "Govorio sam o penzijama i o budžetu za sledeću godinu.")
        if words_after:
            t.say(base + 400, "reč " * words_after)
        if closed:
            t.note(base + 250, "Kraj rada", "Zaključujem rad za danas.", "model")
        t.frame_before = frame_before
        turns = [{"ime": "Petrović Petar", "lista": "Lista", "od": base + 5, "do": base + 200}]
        monkeypatch.setattr(t, "snapshot", lambda now=None: {"dan": t.day, "ranije": False, "stanje": NO_STREAM, "danas": turns,
                                                             "sada": None, "provereno": provereno})
        j = sudija.Judge(t, threading.Event(), ask=lambda system, user, *rest: day if system is not sudija.EVENTS else json.dumps({"dogadjaji": []}))
        j.began = base + 5000
        return j
    j = judge(True, provereno=base + 300)
    j.step(now=base + 300 + sudija.CLOSED_QUIET - 5)
    assert j.kept["dan"] is None
    j.step(now=base + 300 + sudija.CLOSED_QUIET + 5)
    assert j.kept["dan"]["kratko"] == "Dan."  # closed by the chair: three minutes
    j = judge(False, provereno=base + 300)
    j.step(now=base + 300 + sudija.CLOSED_QUIET + 5)
    assert j.kept["dan"] is None  # not closed: it may be a break
    j = judge(True, provereno=base + 300, words_after=60)
    j.step(now=base + 300 + sudija.CLOSED_QUIET + 5)
    assert j.kept["dan"] is None  # the work went on after the words
    j = judge(False, frame_before=base + 300)  # a restart long after: the wait is from the last frame, not from now
    j.step(now=base + 5010)
    assert j.kept["dan"]["kratko"] == "Dan."


def test_a_days_summary_already_in_the_file_is_not_written_again(tmp_path, monkeypatch):
    """24 Nov 2026: made by hand while the service ran, it is taken at the day's end, and the model is not asked."""
    from uzivo import sudija
    monkeypatch.setattr(config, "STATE_PATH", str(tmp_path / "stanje.json"))
    monkeypatch.setattr(config, "DAY_MODEL", "")
    t = Tracker(str(tmp_path / "stanje.json"), "Europe/Belgrade")
    base = 1795082400
    t.day = t._day(base)
    t.say(base + 10, "Govorio sam o penzijama i o budžetu za sledeću godinu.")
    turns = [{"ime": "Petrović Petar", "lista": "Lista", "od": base + 5, "do": base + 200}]
    monkeypatch.setattr(t, "snapshot", lambda now=None: {"dan": t.day, "ranije": False, "stanje": NO_STREAM, "danas": turns,
                                                         "sada": None, "provereno": base + 300})
    asked = []

    def ask(system, user, *rest):
        asked.append(system)
        return json.dumps({"dogadjaji": []}) if system is sudija.EVENTS else json.dumps({"ukratko": "Deo.", "tok": []})
    j = sudija.Judge(t, threading.Event(), ask=ask)
    j.step(now=base + 400)  # the day loaded, the pieces read; not yet ended
    f = tmp_path / "sazetak" / f"{t.day}.json"
    kept = json.loads(f.read_text(encoding="utf-8"))
    kept["dan"] = {"kratko": "Rukom.", "ukratko": "Napisano rukom.", "odluke": [], "t": base + 500}
    f.write_text(json.dumps(kept), encoding="utf-8")
    j.step(now=base + 300 + sudija.END_QUIET + 5)
    assert j.kept["dan"]["kratko"] == "Rukom." and sudija.DAY not in asked and sudija.SUMMARY not in asked
    assert json.loads(f.read_text(encoding="utf-8"))["dan"]["kratko"] == "Rukom."


def test_the_mails_row_says_what_comes_next_and_stands_higher_at_three_moments(monkeypatch):
    """25 Nov 2026, the maintainer's words: in a break, when the day is over, at a shared speech; nothing promised that
    is not sure (the mail goes on his click, and who signs up after it went does not get that day)."""
    from datetime import datetime
    from uzivo import page as page_
    at = lambda h, m: int(datetime(2026, 11, 24, h, m, tzinfo=TZ).timestamp())
    clock = lambda h, m: monkeypatch.setattr(page_, "_now", lambda: datetime(2026, 11, 24, h, m, tzinfo=TZ))
    clock(14, 20)
    b = at(14, 10)
    brk = {"t": b, "vrsta": "Pauza", "tekst": "Proglašavam pauzu do 15 sati i 10 minuta.", "izvor": "model", "url": "", "vise": {}}
    turn = {"ime": "Petrović Petar", "od": at(14, 0), "do": at(14, 8), "sekundi": 480, "grupa": "", "adresa": "", "uloga": "", "lista": "", "video": ""}
    snap = {"stanje": "nepoznato", "provereno": b + 900, "sada": None, "sazvano": None, "bez_potpisa": None, "ranije": False,
            "dan": "2026-11-24", "danas": [turn], "dnevni_red": None, "sazetak": None, "hronika": [brk]}
    tag = lambda s, **kw: page_.fragment(s, cyr=False, site="https://zailiprotiv.rs/", tz=TZ, **kw).split(">", 1)[0]
    on = tag(snap)
    assert 'data-ml="danas"' in on and 'data-gore="pauza"' in on and 'data-nastavak="1"' in on
    clock(14, 50)  # exactly twenty minutes left: the bell promises nothing
    assert "data-nastavak" not in tag(snap) and 'data-gore="pauza"' in tag(snap)
    clock(14, 20)
    assert "data-nastavak" not in tag({**snap, "hronika": [{**brk, "tekst": "Određujem pauzu od jednog sata."}]})  # no hour named
    later = {**turn, "od": b + 600, "do": b + 700}
    for s in ({**snap, "stanje": "govori", "sada": {**turn, "od": b + 600, "do": b + 700}}, {**snap, "danas": [later, turn]},
              {**snap, "hronika": []}, {**snap, "provereno": b + 60}):  # speaking; spoke since; no break; not yet known as one
        assert "data-gore" not in tag(s) and 'data-ml="svake"' in tag(s) and 'data-ml-govor="danas"' in tag(s)
    off = {**snap, "stanje": "nema_prenosa"}
    assert 'data-ml="gotov"' in tag(off) and 'data-gore="kraj"' in tag(off) and "data-nastavak" not in tag(off)
    assert 'data-ml="sledeci"' in tag(off, sent=True) and 'data-ml="sledeci"' in tag(snap, sent=True)
    old = tag({**off, "ranije": True})
    assert 'data-ml="svake"' in old and 'data-ml-govor="sledeci"' in old and "data-gore" not in old
    kw = dict(site="https://zailiprotiv.rs/", tz=TZ, api="https://glasovi.zailiprotiv.rs", push_key="K")
    seen = lambda html: re.findall(r'data-k="(\w+)">([^<]+)<', html)  # the one not hidden, without the script
    assert seen(page_.page(snap, cyr=False, **kw)) == [("danas", "stiže kad se današnja sednica završi")]
    assert seen(page_.page(off, cyr=True, **kw)) == [("gotov", "данашњи стиже кад буде готов")]
    assert seen(page_.page(off, cyr=False, sent=True, **kw)) == [("sledeci", "stiže posle sledećeg dana sednice")]
    assert seen(page_.page({**off, "ranije": True}, cyr=True, **kw)) == [("svake", "после сваке седнице")]
    assert seen(page_.page({**off, "ranije": True}, cyr=True, speech=turn["od"], **kw)) == [("sledeci", "стиже после следећег дана седнице")]
    assert re.search(r"<title>[^<]+ · Скупштина уживо</title>", page_.page(off, cyr=True, speech=turn["od"], **kw))  # a speech keeps its tail
    cyr = page_.page(snap, cyr=True, **kw)
    assert 'data-nastavak="Јави кад се настави">Обавести ме<' in cyr
    assert '<p class="in-app meta" hidden>Да ти јавимо кад се настави, отвори страну у прегледачу (мени ⋯).</p>' in cyr
    assert "večeras" not in page_.page(snap, cyr=False, **kw)


def test_whether_the_days_mail_went_to_all_is_only_read(tmp_path):
    from datetime import date
    from uzivo import pretplata
    m, day = pretplata.Mailer(tmp_path, lambda *a: None), date(2026, 11, 24)
    assert m.went(day) is False and list(tmp_path.iterdir()) == []
    (tmp_path / "2026-11-24.json").write_text('{"uredniku": "x"}', encoding="utf-8")
    assert m.went(day) is False
    (tmp_path / "2026-11-24.json").write_text('{"uredniku": "x", "svima": "y"}', encoding="utf-8")
    assert m.went(day) is True
    (tmp_path / "2026-11-24.json").write_text("{", encoding="utf-8")
    assert m.went(day) is False


def test_the_sitting_goes_on_tomorrow_is_the_days_end_and_a_break_stays_a_break():
    """24 Nov 2026, 19:29: "Nastavak sednice sutra u 10." was taken for a break."""
    from uzivo import hronika, state_base, steps
    kind = lambda text: [k for k, _ in hronika.find(text)]
    for end in ("Nastavak sednice sutra u 10.", "Nastavljamo sutra u 10 sati.", "Nastavljamo sa radom sutra.", "Nastavak sednice je zakazan za sutra."):
        assert kind(end) == ["Kraj rada"], end
    for other in ("Nastavak sednice u 15 časova.", "Nastavljamo u 16 sati.", "Određujem pauzu."):
        assert kind(other) == ["Pauza"], other
    assert kind("Nastavljamo sa radom.") == ["Nastavak rada"]
    # the four breaks of 24 and 25 Nov: the model's steps, shown as breaks; the chair's words end a turn by state_base.BREAK
    now = 1795500000
    for said in ("proglašam pauzu od jednog sata", "Proglašavam pauzu do 15 sati i 10 minuta.",
                 "Ja ću sada da pozovem pauzu. Pauza deset minuta.", "Proglašavam pauzu od pet minuta."):
        assert state_base.BREAK.search(said) and "Kraj rada" not in kind(said)
        snap = {"provereno": now + 900, "sada": None, "dnevni_red": None, "danas": [], "hronika": [
            {"t": now, "vrsta": "Pauza", "tekst": said, "izvor": "model", "url": "", "vise": {}}]}
        assert [e["naslov"] for e in steps.steps_shown(snap)] == ["Pauza"]
    # a day kept before the mend: read again by today's rules, the page's own words for the day's end
    old = {"provereno": now + 900, "sada": None, "dnevni_red": None, "danas": [], "hronika": [
        {"t": now, "vrsta": "Pauza", "tekst": "Nastavak sednice sutra u 10.", "izvor": "prepis", "url": ""}]}
    assert [e["naslov"] for e in steps.steps_shown(old)] == ["Kraj rada za danas"]


def test_the_sittings_notification_waits_for_the_graphic_to_go_down(tmp_path):
    """25 Nov 2026, the maintainer: the broadcast's graphic stood before the sittings of 24 Nov (09:55:35 to 10:00:24) and 25 Nov
    (09:51:12 to 10:03:20), and "Sednica je počela" went at the third frame of it."""
    from datetime import datetime as dt_
    from uzivo.obavesti import SLATE, Bell
    at = lambda d, clock: dt_(2026, 11, d, *(int(x) for x in clock.split(":")), tzinfo=TZ)  # noqa: E731
    for day, began, down in ((24, "09:55:35", "10:00:24"), (25, "09:51:12", "10:03:20")):
        posts = []
        bell = Bell(str(tmp_path / f"{day}.json"), token="t", api="https://glasovi.example", post=lambda od: posts.append(od) or {})
        t, end, told = at(day, began).timestamp(), at(day, down).timestamp(), []
        while t < end + 60 and not told:
            if bell.frame(dt_.fromtimestamp(t, TZ), wait=True, covered=t < end):
                told.append(t)
            t += 5
        assert told and end <= told[0] < end + 5 and posts == [0], day
    # it never goes down: told after SLATE, once
    bell = Bell(str(tmp_path / "s.json"), token="t", api="https://glasovi.example", post=lambda od: {})
    t0 = at(26, "10:00:00").timestamp()
    told = [k for k in range(0, 3600, 5) if bell.frame(dt_.fromtimestamp(t0 + k, TZ), wait=True, covered=True)]
    assert told == [SLATE] and SLATE == 1800
    # not read: as before, at the third frame
    bell = Bell(str(tmp_path / "n.json"), token="t", api="https://glasovi.example", post=lambda od: {})
    assert [bell.frame(at(27, "10:00:00"), wait=True, covered=None) for _ in range(4)] == [False, False, True, False]
    # out of the hours at its beginning: nothing that run, also once the graphic is down
    bell = Bell(str(tmp_path / "h.json"), token="t", api="https://glasovi.example", post=lambda od: {})
    assert not any(bell.frame(at(27, "06:59:00"), wait=True, covered=k < 3) for k in range(8))
    # a run begun out of them tells nothing when the hours come, as before (once looked at, a run is done)
    bell = Bell(str(tmp_path / "r.json"), token="t", api="https://glasovi.example", post=lambda od: {})
    t0 = at(28, "06:59:30").timestamp()
    assert not any(bell.frame(dt_.fromtimestamp(t0 + 5 * k, TZ), wait=True, covered=False) for k in range(40))


def test_the_live_record_says_what_it_is_and_where_the_notes_corrected_it():
    from uzivo import config
    from uzivo.names import Person
    t = Tracker(None, "Europe/Belgrade")
    t.observe(Person("a", "Štimac Aleksandra", "stimac-aleksandra", "Studentska lista"), "Studentska lista", now=1795598171)
    day = t.day
    rec = t.record(day)
    assert rec["zapis"] == "uzivo" and "ispravljeno" not in rec and rec["govori"][0]["ime"] == "Štimac Aleksandra"
    t.use_waiting({"kviz": [], "cinjenice": [], "dani": [day], "iz_beleski": [day]})
    rec = t.record(day)
    assert rec["ispravljeno"] == {"izvor": "beleske", "dan": f"{config.SITE}govornici/{day}"}
    assert rec["govori"][0]["ime"] == "Štimac Aleksandra"  # nothing taken out: the record as read
    t.use_waiting({"kviz": [], "cinjenice": [], "dani": [day], "iz_beleski": ["2026-11-24"]})
    assert "ispravljeno" not in t.record(day)


# "O govorniku" (26 Nov 2026, the maintainer's choice C with D) -----------------------------------------------------
_FN = [{"v": "vice", "t": "", "u": "Potpredsednik Narodne skupštine"},
       {"v": "committee", "t": "Odbor za prava deteta", "u": "član"},
       {"v": "committee", "t": "Odbor za finansije, republički budžet i kontrolu trošenja javnih sredstava", "u": "zamenik člana"},
       {"v": "delegation", "t": "Delegacija u Parlamentarnoj skupštini Saveta Evrope", "u": "šef"}]


def _speaking(fn, *, foto="12.jpg", item=None, ime="Petrović Petar"):
    o = {"lista": "Lista za primer", **({"foto": foto} if foto else {})}
    if fn is not None:
        o.update(fn=fn, fn_dan="2026-11-26")
    turn = {"ime": ime, "adresa": "petrovic-petar", "od": 1794919000, "do": 1794920000, "sekundi": 1000,
            "lista": "Lista za primer", "o": o}
    turn["duze"] = 70  # a snapshot of a service not yet rebuilt still carries it
    return {"stanje": "govori", "provereno": 1794920000, "danas": [], "dan": "2026-11-26", "hronika": [], "sada": turn,
            "dnevni_red": {"tacke": [item]} if item else {}}


def test_the_portrait_opens_the_speakers_offices_and_the_block_gets_nothing_more():
    snap = _speaking(_FN)
    html = page(snap, cyr=False, site="https://zailiprotiv.rs/", tz=TZ)
    start = html.index('<div class="sp-head">')
    head = html[start:html.index("</section>", start)]
    # the portrait is the press; without the script it leads to the MP's offices on the site
    assert re.search(r'<a class="ph-a" href="https://zailiprotiv\.rs/poslanik/petrovic-petar#funkcije" data-og '
                     r'aria-haspopup="dialog" aria-controls="og" aria-label="O govorniku: Petar Petrović"><img class="ph"', head)
    sheet = head[head.index("<template"):]
    # the one order for all: the Assembly's, committees, delegations, each heading only when held
    assert re.findall(r'<h3 class="og-g">([^<]+)', sheet) == ["U Skupštini", "Odbori", "Delegacije"]
    assert (sheet.index("Potpredsednik Narodne skupštine") < sheet.index("Odbor za prava deteta")
            < sheet.index("Odbor za finansije, republički") < sheet.index("Saveta Evrope"))
    assert "<span>· zamenik člana</span>" in sheet and "<span>· šef</span>" in sheet
    assert "Sajt Skupštine, pročitano 26. novembra 2026." in sheet
    assert 'href="https://zailiprotiv.rs/poslanik/petrovic-petar">Stranica poslanika →' in sheet
    assert "govor danas" not in html  # C's line of today's speeches is left out (the maintainer: a light card)
    assert "današnjih govora" not in html  # "duže od N%" off (26 Nov 2026, the maintainer)
    assert "govori od" not in head and '<b class="clk" data-od="1794919000" data-sek="1000">16:40</b></p>' in head  # and "govori od"
    # one dialog for the page, outside the part that is replaced every five seconds
    assert html.count('<dialog class="og" id="og"') == 1 and html.index("<dialog") > html.index("</main>")
    assert 'id="og"' not in fragment(snap, cyr=False, site="https://zailiprotiv.rs/", tz=TZ)
    assert "sp-item" not in head  # D: no line, no room kept for one
    cyr = fragment(snap, cyr=True, site="https://zailiprotiv.rs/", tz=TZ)
    assert "О говорнику" in cyr and "Одбор за права детета" in cyr and "Делегације" in cyr
    assert "/cir/poslanik/petrovic-petar#funkcije" in cyr


def test_an_mp_with_no_office_gets_the_sheet_saying_so_and_an_unknown_one_none():
    html = fragment(_speaking([]), cyr=False, site="https://zailiprotiv.rs/", tz=TZ)
    assert "Bez funkcije, odbora i delegacije na sajtu Skupštine." in html and 'class="og-g"' not in html and "data-og" in html
    # offices not said (a name two MPs share, a file of before): no sheet, and the portrait as it was
    html = fragment(_speaking(None), cyr=False, site="https://zailiprotiv.rs/", tz=TZ)
    assert "data-og" not in html and "<template" not in html
    assert '<img class="ph" src="https://zailiprotiv.rs/foto/12.jpg"' in html
    # no portrait: a small "i" after the name opens it
    html = fragment(_speaking(_FN, foto=""), cyr=False, site="https://zailiprotiv.rs/", tz=TZ)
    assert '<a class="og-i" href="https://zailiprotiv.rs/poslanik/petrovic-petar#funkcije" data-og' in html and "ph-a" not in html


def test_d_names_a_committee_only_when_the_item_under_way_names_it_word_for_word():
    from uzivo.page import named
    cur = _speaking(_FN)["sada"]

    def item(text, state="u_toku"):
        return {"n": 3, "tekst": text, "stanje": state, "izvor": "sajt"}
    # the head word in any case, the rest as written, either script
    assert named(cur, item("Predlog odluke o izboru članova Odbora za prava deteta")) == [_FN[1]]
    assert named(cur, item("Извештај о раду Одбора за финансије, републички буџет и контролу трошења јавних средстава")) == [_FN[2]]
    assert named(cur, item("Izveštaj Delegacije u Parlamentarnoj skupštini Saveta Evrope")) == [_FN[3]]
    # never by a guess: a finance bill names no committee, a name cut short is not the name
    assert named(cur, item("Predlog zakona o budžetu Republike Srbije za 2027. godinu")) == []
    assert named(cur, item("Predlog odluke o članovima Odbora za finansije")) == []
    assert named(cur, item("Predlog zakona o pravima deteta")) == []
    assert named(cur, None) == [] and named(_speaking(None)["sada"], item("Odbor za prava deteta")) == []
    whole = "Predlog odluke o izboru članova Odbora za finansije, republički budžet i kontrolu trošenja javnih sredstava"
    html = fragment(_speaking(_FN, item=item(whole)), cyr=False, site="https://zailiprotiv.rs/", tz=TZ)
    assert '<p class="sp-item">Odbor za finansije (tačka 3) · zamenik člana</p>' in html
    html = fragment(_speaking(_FN, item=item("Izveštaj Delegacije u Parlamentarnoj skupštini Saveta Evrope")), cyr=True,
                    site="https://zailiprotiv.rs/", tz=TZ)
    assert '<p class="sp-item">Делегација у Парламентарној скупштини Савета Европе (тачка 3) · шеф</p>' in html
    # only the item under way
    done = item("Izveštaj Delegacije u Parlamentarnoj skupštini Saveta Evrope", "gotova")
    assert "sp-item" not in fragment(_speaking(_FN, item=done), cyr=False, site="https://zailiprotiv.rs/", tz=TZ)


def test_a_long_name_is_a_step_smaller_on_a_phone_by_its_longest_word():
    from uzivo.page import CSS

    def cls(ime, cyr=False):
        html = fragment(_speaking(_FN, ime=ime), cyr=cyr, site="https://zailiprotiv.rs/", tz=TZ)
        return re.search(r'class="(who[^"]*)"', html).group(1)
    assert cls("Bakić Ana") == "who"
    assert cls("Milosavljević Ivan") == "who who-13" and cls("Milosavljević Ivan", True) == "who who-12"  # Љ is one letter
    assert cls("Živković-Obradović Dragana") == "who who-9"  # a hyphen is a place to break
    for n in range(6, 14):
        assert re.search(rf"\.sp-head \.who-{n}\b", CSS)  # every count the rule gives has its size, in Cyrillic at least


def test_the_site_gives_each_sitting_mp_their_offices_for_the_sheet():
    from zailiprotiv import pages_mikrofon
    from zailiprotiv.translit import latin as lat

    def row(slug, offices, known=True):
        return {"slug": slug, "new": True, "name": "Petrović Petar", "group": "", "party": "-", "offices": offices,
                "offices_known": known}
    vice = {"kind": "vice", "role": "потпредседник", "body": "Народна скупштина", "text": "Potpredsednik Narodne skupštine"}
    deleg = {"kind": "delegation", "role": "шеф Делегације", "body": "Делегација у Парламентарној скупштини ОЕБС", "text": "x"}
    comm = {"kind": "committee", "role": "заменик члана", "body": "Одбор за спољне послове", "text": "x"}
    out = pages_mikrofon.speakers([row("a", [vice, comm, deleg]), row("b", []), row("c", [comm], known=False)], {}, conv="15",
                                  spoken_={}, plain=str, latin=lat, day=str, offices_read="2026-11-25T23:30:00+00:00")
    assert out["a"]["fn"] == [{"v": "vice", "t": "", "u": "Potpredsednik Narodne skupštine"},
                              {"v": "committee", "t": "Odbor za spoljne poslove", "u": "zamenik člana"},
                              {"v": "delegation", "t": "Delegacija u Parlamentarnoj skupštini OEBS", "u": "šef"}]
    assert out["a"]["fn_dan"] == "2026-11-26"  # the day in Belgrade
    assert out["b"]["fn"] == [] and "fn" not in out["c"]  # none held is said; a name two MPs share says nothing
    assert "fn" not in pages_mikrofon.speakers([row("a", [vice])], {}, conv="15", spoken_={}, plain=str, latin=lat, day=str)["a"]


# A point of order live, with the articles the speaker named (26 Nov 2026) ----------------------------------------------
def test_the_articles_of_a_point_of_order_are_the_speakers_own_after_the_chair_gives_the_floor():
    from uzivo import povreda
    # the caption comes late: the speaker's first words are among the pieces with no caption, after the chair's
    said = {"p1000": "Ne može član 15. Reč ima narodni poslanik Petar Petrović. Izvolite.",
            "p1020": "Povreda Poslovnika, član 27. i član 107. Poslovnika.", "1031": "Hvala."}
    assert povreda.split(said, 1030)[0].endswith("Izvolite")
    assert povreda.articles(said, 1030) == [27, 107]
    # a number the chair just said is not the speaker's; a number said in words is read
    said = {"p1000": "Pitate po članu 15? Reč ima poslanik. Izvolite.", "p1020": "Član 15. i član sto sedam."}
    assert povreda.articles(said, 1030) == [107]
    assert povreda.digits("član dvadeset i sedam, član sto osmi, član trideset tri") == "član 27, član 108, član 33"
    assert povreda.digits("član sedam sto") == "član sedam sto"  # not a number in order: left as said
    # only the Rules' articles, never another act's
    assert povreda.articles({"p1020": "Član 107. Ustava i član 300."}, 1030) == []
    # the site's second sign: an article named at once
    assert povreda.opens_with_article({"p1000": "Izvolite.", "p1010": "Član 107, predsedniče."}, 1015)
    assert not povreda.opens_with_article({"p1000": "Izvolite.", "p1010": "Hvala, poštovani predsedniče."}, 1015)


def test_the_live_rules_agree_with_the_sites_over_the_notes():
    """povreda.py is notes_site's and poslovnik's rule in Latin: the same answers over the notes' speeches, turned to
    Latin (the newest convocation's, where the repository has them)."""
    from uzivo import povreda
    from zailiprotiv import notes_site, pages_govornici, poslovnik
    from zailiprotiv.translit import latin as lat
    texts = pages_govornici._notes_texts(Path(__file__).parent.parent / "data", "15")
    if not texts:
        pytest.skip("no notes here")
    for t, _ in texts.values():
        assert [x[0] for x in povreda.cited(lat(t), True)] == [x[0] for x in poslovnik.cited(t, True)]
        assert bool(povreda.NOT.search(lat(t))) == bool(notes_site._POINT_NOT.search(t))
    assert povreda.LAST == 298 and povreda.CITE_HEAD == poslovnik.CITE_HEAD


def test_the_clock_line_names_a_point_of_order_and_its_articles_only_where_asked():
    from uzivo.rok import limit
    chair = {"p1000": "Reč ima narodni poslanik Petar Petrović. Izvolite."}
    said = {**chair, "p1020": "Povreda Poslovnika, član 107. Poslovnika."}
    assert limit(said, 1030, 10, label=True) == {"vrsta": "povreda", "sek": 120, "clanovi": [107]}
    assert limit(said, 1030, 10, label=True, articles=False) == {"vrsta": "povreda", "sek": 120}  # POVREDA_CLAN=0
    assert limit(said, 1030, 10) == {"vrsta": "povreda", "sek": 120}  # the groups' time and razmene: as before
    # denied, or in passing: none on the clock's line (the site's negations)
    denied = {**chair, "p1020": "Ovo nije povreda Poslovnika, ali hoću da kažem."}
    assert limit(denied, 1030, 10, label=True) is None and limit(denied, 1030, 10) is not None
    # an article named at once is a point of order (the site's second sign); not when a reply is heard
    assert limit({**chair, "p1020": "Član 107. Gospodine predsedniče."}, 1030, 10, label=True)["vrsta"] == "povreda"
    assert limit({**chair, "p1020": "Replika. Član 107."}, 1030, 10, label=True)["vrsta"] == "replika"
    assert limit({**chair, "p1020": "Član 107."}, 1030, 200, label=True) is None  # past the two minutes and a half


def test_the_block_says_povreda_poslovnika_with_each_article_linked():
    snap = _speaking(_FN)
    snap["sada"]["rok"] = {"vrsta": "povreda", "sek": 120}
    html = fragment(snap, cyr=False, site="https://zailiprotiv.rs/", tz=TZ)
    assert '<span class="rk"><span>/ 2 min</span> <span>· Povreda Poslovnika</span></span>' in html
    snap["sada"]["rok"]["clanovi"] = [107]
    html = fragment(snap, cyr=False, site="https://zailiprotiv.rs/", tz=TZ)
    assert ('<span>· čl. <a href="https://zailiprotiv.rs/poslovnik-clanovi#clan-107">107</a></span>') in html
    snap["sada"]["rok"]["clanovi"] = [27, 107]
    cyr = fragment(snap, cyr=True, site="https://zailiprotiv.rs/", tz=TZ)
    assert ('<span>· Повреда Пословника</span> <span>· чл. <a href="https://zailiprotiv.rs/cir/poslovnik-clanovi#clan-27">27</a> и '
            '<a href="https://zailiprotiv.rs/cir/poslovnik-clanovi#clan-107">107</a></span>') in cyr
    snap["sada"]["rok"] = {"vrsta": "replika", "sek": 120, "clanovi": [107]}  # a reply has no articles
    assert "clan-107" not in fragment(snap, cyr=False, site="https://zailiprotiv.rs/", tz=TZ)


def test_a_turns_first_piece_is_written_from_20_s_and_the_rest_from_30_s(tmp_path):
    """26 Nov 2026, the maintainer: the first piece of the speaker now on at 20 s of sound, the rest at 30 s as before."""
    from uzivo import prepis
    from uzivo.state_base import SAID_LEAD
    f = lambda at: (at, 5.0, tmp_path / f"{at}.pcm")  # noqa: E731
    begin = 100 - SAID_LEAD  # the turn's sound begins before its first frame
    cur = lambda secs: {"od": 100, "sekundi": secs}  # noqa: E731
    first = [f(begin + 5 * i) for i in range(4)]  # 20 s
    piece, drop, chair = prepis.choose(first, [], cur(20), now=100 + 20)
    assert not chair and [x[0] for x in piece] == [x[0] for x in first] and not drop
    assert prepis.choose(first[:3], [], cur(20), now=120)[0] == []  # 15 s: not yet
    # once the first piece is written, the next waits for 30 s, as before
    later = [f(begin + 20 + 5 * i) for i in range(5)]  # 25 s
    assert prepis.choose(later, [], cur(45), now=145)[0] == []
    piece = prepis.choose(later + [f(begin + 45)], [], cur(50), now=150)[0]
    assert [x[0] for x in piece] == [begin + 20 + 5 * i for i in range(6)]
    # a turn shorter than 20 s is still not written while it is on
    assert prepis.choose(first, [], cur(15), now=115)[0] == []


# The speaker's card while a recording plays (26 Nov 2026, the maintainer) ------------------------------------------
def test_the_card_of_a_recording_has_its_place_outside_the_part_and_its_words():
    snap = _speaking(_FN)
    html = page(snap, cyr=False, site="https://zailiprotiv.rs/", tz=TZ)
    assert html.count('<section class="rc" id="rc" hidden') == 1 and 'data-o="/o/"' in html
    assert 'data-clan="https://zailiprotiv.rs/poslovnik-clanovi#clan-"' in html
    assert '<span data-w="na">Na snimku</span>' in html and '<span data-w="izmedju">Između govora</span>' in html
    part = fragment(snap, cyr=False, site="https://zailiprotiv.rs/", tz=TZ)
    assert 'id="rc"' not in part and 'data-dan-ime="26. novembra"' in part  # the part is replaced; the card is not
    cyr = page(snap, cyr=True, site="https://zailiprotiv.rs/", tz=TZ)
    assert 'data-o="/cir/o/"' in cyr and "На снимку" in cyr and "Између говора" in cyr and "cir/poslovnik-clanovi#clan-" in cyr


def test_each_finished_turn_carries_what_its_card_needs():
    t = Tracker(None, "Europe/Belgrade")
    t.roster = ROSTER
    t.use_facts({"petrovic-petar": {"lista": "Lista za primer", "foto": "12.jpg", "ime": "Petrović Petar"}})
    petar, marko = ROSTER.match("Петар Петровић", 0.8), ROSTER.match("Марко Јовановић", 0.8)
    now = 1794920000.0
    for s_ in range(0, 101, 5):
        t.observe(petar, now=now + s_)
    t.say(int(now - 20), "Reč ima narodni poslanik Petar Petrović. Izvolite.", chair=True)
    t.say(int(now + 1), "Povreda Poslovnika, član 107. Poslovnika, predsedniče.")
    for s_ in range(110, 200, 5):
        t.observe(marko, now=now + s_)
    snap = t.snapshot(now=now + 200)
    first = next(d for d in snap["danas"] if d["adresa"] == "petrovic-petar")
    assert first["povreda"] == [107]  # the live rule on a finished turn, kept on the turn only
    html = fragment(snap, cyr=False, site="https://zailiprotiv.rs/", tz=TZ)
    row = html[html.index(f'id="t{int(first["od"])}"'):]
    row = row[:row.index(">")]
    assert 'data-adresa="petrovic-petar"' in row and 'data-povreda="107"' in row and 'data-lc="' in row
    assert "povreda" not in (snap["sada"] or {})  # the turn on now has the label beside its clock instead


def test_a_day_from_the_notes_brings_the_notes_label(tmp_path):
    from uzivo.state_view import View
    turn = {"ime": "Petrović Petar", "adresa": "petrovic-petar", "od": 100, "do": 200, "povreda": [27, 107]}
    assert View._recorded(turn)["povreda"] == [27, 107]
    assert "povreda" not in View._recorded({**turn, "povreda": None})


def test_the_site_gives_the_live_service_the_notes_labels(tmp_path):
    import json as _json
    from zailiprotiv import pages_govornici
    conv = tmp_path / "15"
    (conv / "snimak").mkdir(parents=True)
    (conv / "transcripts").mkdir()
    (conv / "transcripts" / "1.json").write_text(_json.dumps({"speeches": {
        "001": {"chair": True, "text": "Реч има народни посланик Петар Петровић."},
        "002": {"text": "Повреда Пословника, члан 107. Хвала."},
        "003": {"text": "Поштовани грађани, данас говоримо о закону."}}}), encoding="utf-8")
    day = {"dan": "2026-11-24", "izvor": "govor", "govori": [{"od": 1, "do": 2, "beleske": ["1/002"]},
                                                           {"od": 3, "do": 4, "beleske": ["1/003"]}]}
    (conv / "snimak" / "2026-11-24.json").write_text(_json.dumps(day), encoding="utf-8")
    pages_govornici._TEXTS.clear()
    got = pages_govornici.with_points(tmp_path, day)
    assert got["govori"][0]["povreda"] == [107] and "povreda" not in got["govori"][1]
    assert pages_govornici.with_points(tmp_path, {**day, "izvor": "uzivo"}) == {**day, "izvor": "uzivo"}
    pages_govornici._TEXTS.clear()


def test_a_speakers_sheet_is_given_by_address():
    from uzivo.page import sheet
    facts = {"petrovic-petar": {"ime": "Petrović Petar", "lista": "Lista za primer", "fn": _FN, "fn_dan": "2026-11-26"},
             "bez-funkcija": {"ime": "Jovanović Jovan", "lista": "Lista"}}
    got = sheet(facts, "petrovic-petar", cyr=False, site="https://zailiprotiv.rs/")
    assert got.startswith('<p class="og-k">O govorniku</p>') and "<template" not in got and "Odbor za prava deteta" in got
    assert "Одбор за права детета" in sheet(facts, "petrovic-petar", cyr=True, site="https://zailiprotiv.rs/")
    for unknown in ("nepoznat", "../x", "bez-funkcija", ""):  # unknown, not an address, offices not said
        assert sheet(facts, unknown, cyr=False, site="https://zailiprotiv.rs/") == ""
