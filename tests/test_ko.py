"""ko.py and live/uzivo/komadi.py: a day's sound cut where the voice changes, each piece named by its best sign."""
import pytest

np = pytest.importorskip("numpy")

from zailiprotiv import ko  # noqa: E402
from uzivo import komadi  # noqa: E402

RNG = np.random.default_rng(7)
A, B, C, D = np.eye(512, dtype=np.float64)[:4]
URL = "https://arhiva.example/zas1.mp4"


def sound(*parts, start=0.0):
    """Windows every 1.5 s of one voice after another: (voice, seconds), a voice None being silence."""
    t, f, at = [], [], start
    for v, seconds in parts:
        for x in np.arange(at, at + seconds, 1.5):
            if v is not None:
                w = v + RNG.normal(0, 0.01, 512)  # 0.01 * sqrt(512) = 0.23 of noise
                t.append(x)
                f.append(w / np.linalg.norm(w))
        at += seconds
    return np.array(t), np.array(f, np.float32)


def file(*parts, od=1000):
    t, f = sound(*parts)
    return {"url": URL, "od": od, "t": t, "f": f}


NOBODY = lambda url, a, b: ""


def test_the_sound_is_cut_where_the_voice_changes_and_at_a_long_silence():
    t, f = sound((A, 120), (B, 90), (None, 60), (B, 90))
    cuts = komadi.pieces(t, f)
    assert len(cuts) == 3
    assert abs(cuts[0][1] - 120) <= 6 and cuts[0][1] == cuts[1][0]
    assert abs(cuts[1][1] - 210) <= 3 and abs(cuts[2][0] - 270) <= 2  # the pause is in neither
    assert komadi.pieces(t[:0], f[:0]) == []


def test_a_voice_names_only_when_surely_one():
    refs = {"a": A, "b": B}
    assert komadi.whose({"a": 0.9, "b": 0.3}) == "a"
    assert komadi.whose({"a": 0.79, "b": 0.3}) == ""  # not alike enough
    assert komadi.whose({"a": 0.9, "b": 0.85}) == ""  # two voices as alike
    assert komadi.whose({}) == ""
    assert komadi.alike(A, refs) == {"a": 1.0, "b": 0.0}


def test_a_sign_is_not_taken_against_the_voice():
    sure = {"a": 0.95, "b": 0.2}
    assert komadi.against("b", sure, 20)  # surely another's, however short
    assert not komadi.against("a", sure, 200)
    assert komadi.against("b", {"b": 0.4}, 40) and not komadi.against("b", {"b": 0.4}, 20)  # too short to tell
    assert not komadi.against("c", {"a": 0.5}, 200)  # a voice not known says nothing


def test_the_best_sign_names_the_piece_and_the_voice_may_refuse_it():
    f = file((A, 120), (B, 120), (C, 120), (D, 120))
    refs = {"a": A, "b": B}
    # a caption over the first (of who it is), one over the second misread as "x", whose voice is not known but b's is
    caps = [("a", 1010, 1030), ("x", 1140, 1170)]
    floor = lambda url, a, b: "c" if a <= 240 + 5 <= b else "a" if a <= 360 + 5 <= b else ""  # the fourth: misheard
    got = ko.named([f], refs, caps, floor)
    assert [(g["adresa"], g["po"]) for g in got] == [("a", "potpis"), ("b", "glas"), ("c", "prepis")]
    assert abs(got[2]["od"] - 240) <= 6  # and the fourth is nobody's: the chair's word said "a", the voice did not


def test_a_piece_the_chair_named_is_a_sample_for_the_rest_of_the_day():
    f = file((C, 120), (D, 120), (C, 90))
    floor = lambda url, a, b: "c" if a <= 5 <= b else ""
    got = ko.named([f], {}, [], floor)
    assert [(g["adresa"], g["po"]) for g in got] == [("c", "prepis"), ("c", "glas")]


def test_the_presiding_officers_are_never_named_by_voice():
    f = file((A, 90), (B, 90))
    assert [g["adresa"] for g in ko.named([f], {"a": A, "b": B}, [], NOBODY, skip={"b"})] == ["a"]


def test_a_captions_clock_set_beside_the_files_by_the_sound():
    lengths, turns, at = (60, 95, 50, 120, 70, 85, 60), [], 1000
    f = file(*zip((A, B, C, D, A, B, C), lengths))
    for i, n in enumerate(lengths):
        turns.append((str(i), at, at + n))
        at += n
    late = [(w, a - 30, b - 30) for w, a, b in turns]  # the captions' clock 30 s behind
    assert abs(ko.clock_shift(late, [f]) - 30) <= 4
    assert ko.clock_shift(turns, [f]) == 0
    assert ko.clock_shift(late[:3], [f]) == 0  # too few to say


def test_the_days_samples_leave_out_the_ends_of_a_turn(tmp_path):
    t, f = sound((A, 10), (B, 60), (A, 10))
    np.savez(tmp_path / "zas1.glas.npz", t=t.astype(np.float32), feat=f)
    day = {"govori": [{"adresa": "b", "datoteka": URL, "snimak": 5, "od": 10, "do": 70, "okvira": 9},
                      {"adresa": "c", "datoteka": URL, "snimak": 5, "od": 10, "do": 70, "okvira": 1}]}
    spans = ko.known_spans(day)
    assert spans == [("b", URL, 10, 70)]
    got = ko.voices(spans, lambda url: tmp_path)
    assert set(got) == {"b"} and float(got["b"] @ B) > 0.97
