"""The page shown at mikrofon.zailiprotiv.rs while "Ko sada govori" is down (pages_mikrofon, live/edge)."""
import json
import urllib.parse
from pathlib import Path

from zailiprotiv import pages_mikrofon


def _facts(days=21, word=("izdajnici", 145)):
    conv = {"n": "14", "years": "2024–2026"}
    numbers = [{"conv": conv, "with_bill": 395, "urgent": 66, "days": days, "voted": 394, "unopposed": 239}]
    law = {"slug": "rebalans", "law": {"short": "Rebalans"}, "final": {"counts": {"za": 136, "protiv": 51}}}
    totals = {"14": {"years": "2024–2026", "page": "varnice.html", "page_who": "varnice-ko.html", "sittings": 16,
                     "speeches": 7298, "measures": 38, "exchanges": 60, "harsh_word": word}}
    return pages_mikrofon.facts(stats={"all_laws": 2097, "all_mps": 995}, numbers=numbers, items=[law],
                                most_against=lambda items, k: items[:k], totals=totals, active="14")


def test_facts_come_from_the_sites_counts_each_with_its_page():
    facts = _facts()
    assert [f["href"] for f in facts] == ["zakoni.html", "brojke.html", "brojke.html", "brojke.html",
                                          "zakon/rebalans.html", "varnice.html", "varnice-ko.html"]
    text = " ".join(f["text"] for f in facts)
    for said in ("2097 zakona", "66 od 395", "za 21 dan ", "239 od 394", "136 za i 51 protiv", "7298 govora",
                 "„izdajnici“", "145 puta"):
        assert said in text


def test_facts_leave_out_what_is_not_known():
    facts = _facts(days=None, word=(None, 0))
    assert not any("Polovina" in f["text"] or "Teška reč" in f["text"] for f in facts)
    assert "za 22 dana " in _facts(days=22)[2]["text"]


def test_the_last_day_read_from_the_recording():
    day = {"dan": "2026-11-17", "govori": [
        {"ime": "Vučić Aleksandar", "adresa": "vucic-aleksandar", "grupa": "", "uloga": "Lista A", "od": 1794920657,
         "do": 1794926412, "okvira": 1152, "video": "qkm", "snimak": 14527},
        {"ime": "Jović Jova", "adresa": "", "grupa": "", "uloga": "", "od": 1794926500, "do": 1794926505, "okvira": 1,
         "video": "qkm", "snimak": 20370}]}
    out = pages_mikrofon.turns(day)
    assert out == [{"od": 1794920657, "do": 1794926412, "from": "14:04", "to": "15:40", "name": "Aleksandar Vučić", "slug": "vucic-aleksandar",
                    "side": "Lista A", "minutes": 96, "recording": "https://www.youtube.com/watch?v=qkm&t=14527s",
                    "file": "", "t": 14527}]


def _quiz():
    conv = {"n": "14", "years": "2024–2026"}
    numbers = [{"conv": conv, "with_bill": 395, "urgent": 66, "days": 21, "voted": 394, "unopposed": 239}]
    totals = {"14": {"years": "2024–2026", "page": "varnice.html", "page_who": "varnice-ko.html", "sittings": 16,
                     "speeches": 7298, "measures": 38, "exchanges": 60, "harsh": 412, "harsh_word": ("izdajnici", 145),
                     "harsh_top": [("izdajnici", 145), ("lopovi", 90), ("bitange", 12)],
                     "harsh_days": [("2025-03-04", 40), ("2024-11-20", 31), ("2025-06-10", 25)],
                     "harsh_quote": {"text": "Vi ste izdajnici ovog naroda i to svi znaju.", "word": "izdajnici",
                                     "who": "Petrović Petar", "slug": "petrovic-petar", "date": "2025-03-04",
                                     "url": "https://beleske.zailiprotiv.rs/a#g12"}}}
    items = [{"law": {"passed": d}} for d in ("2025-03-04", "2025-03-04", "2025-03-04", "2025-05-01", "2025-05-01")]
    return pages_mikrofon.quiz(numbers=numbers, totals=totals, active="14", items=items)


def test_the_quiz_asks_for_the_sites_own_numbers_with_wrong_answers_by_a_fixed_rule():
    quiz = _quiz()
    assert [q["key"] for q in quiz] == ["quote", "urgent", "harsh", "per_day", "days", "harsh_all", "measures",
                                        "unopposed", "harsh_day", "speeches"]
    for q in quiz:
        assert len(q["options"]) == 3 and len(set(q["options"])) == 3 and 0 <= q["answer"] < 3 and q["href"]
    right = [q["options"][q["answer"]] for q in quiz]
    assert right == ["„izdajnici“", "66", "145", "3", "21", "412", "38", "239", "4. marta 2025", "7298"]
    assert quiz[0]["q"] == "Koja reč nedostaje? „Vi ste _____ ovog naroda i to svi znaju.“"
    assert quiz[0]["options"] == ["„bitange“", "„izdajnici“", "„lopovi“"] and quiz[0]["more"] == "Ceo govor"
    assert quiz[0]["href"].startswith("https://beleske.") and quiz[0]["why"].endswith("Rečeno 4. marta 2025.")
    numeric = [q for q in quiz if q["options"][0].isdigit()]
    assert len({q["answer"] for q in numeric}) == 3  # the right one now smallest, now middle, now largest
    assert all(int(o) <= 395 for o in quiz[1]["options"]) and all(int(o) <= 394 for o in quiz[7]["options"])
    assert quiz[8]["options"] == ["20. novembra 2024", "4. marta 2025", "10. juna 2025"]  # by date


def test_the_quiz_leaves_out_what_is_not_known_and_the_live_page_gets_plain_links():
    conv = {"n": "14", "years": "2024–2026"}
    numbers = [{"conv": conv, "with_bill": 0, "urgent": 0, "days": None, "voted": 10, "unopposed": 4}]
    quiz = pages_mikrofon.quiz(numbers=numbers, totals={}, active="14")
    assert [q["options"][q["answer"]] for q in quiz] == ["4"]
    w = pages_mikrofon.waiting([{"text": "x", "href": "zakon/a.html"}], _quiz())
    assert w["cinjenice"][0]["href"] == "zakon/a" and w["kviz"][1]["href"] == "brojke"
    assert w["kviz"][0]["href"] == "https://beleske.zailiprotiv.rs/a#g12"  # an address elsewhere stays whole
    # Beside the quiz, only the facts it does not ask about.
    assert [f["key"] for f in pages_mikrofon.besides(_facts(), _quiz())] == ["laws", "against"]


def test_a_turn_in_the_archive_links_to_its_second_in_the_file():
    day = {"dan": "2026-11-17", "govori": [{"ime": "Radeta Vjerica", "adresa": "radeta-vjerica", "grupa": "",
            "uloga": "", "od": 1794910712, "do": 1794910792, "okvira": 17, "video": "",
            "datoteka": "https://arhiva.videonet.co.rs/filesnsrs/zasedanja/zas2026111710.mp4", "snimak": 769}]}
    t = pages_mikrofon.turns(day)[0]
    assert t["recording"].endswith("zas2026111710.mp4#t=769") and t["file"].endswith("10.mp4") and t["t"] == 769


def test_the_next_sitting_is_one_convened_for_today_or_later_with_its_agenda(tmp_path):
    from datetime import datetime as dt_
    (tmp_path / "15").mkdir()
    (tmp_path / "15" / "index.json").write_text(json.dumps({"sittings": {
        "https://a/druga": {"title": "Друга седница", "starts": "2026-11-24T10:00", "agenda": ["Избор судија"], "votes": []},
        "https://a/prva": {"title": "Прва седница", "starts": "", "agenda": ["Избор председника"], "votes": []},
        "https://a/vest": {"title": "Вест", "starts": "", "agenda": [], "votes": []}}}), encoding="utf-8")
    coming = [{"title": "Стара седница", "url": "https://a/stara", "starts": "2026-11-02", "agenda": ["x"]}]
    every = pages_mikrofon.upcoming(tmp_path, coming, "15")
    assert [c["url"] for c in every] == ["https://a/stara", "https://a/druga", "https://a/prva"]
    w = pages_mikrofon.waiting([], [], every, now=dt_(2026, 11, 20, 1, 0, tzinfo=pages_mikrofon.TZ))
    assert w["sazvano"] == {"naslov": "Druga sednica", "url": "https://a/druga", "pocinje": "2026-11-24T10:00",
                            "tacke": ["Izbor sudija"]}
    assert "sazvano" not in pages_mikrofon.waiting([], [], coming, now=dt_(2026, 11, 20, tzinfo=pages_mikrofon.TZ))


def test_a_sitting_begun_is_announced_when_its_page_says_it_goes_on(tmp_path):
    """25 Nov 2026: the first sitting had a roll call, so it was taken as over, and the live page said only "Ne zaseda"."""
    from datetime import datetime as dt_
    (tmp_path / "15").mkdir()
    put = lambda **more: (tmp_path / "15" / "index.json").write_text(json.dumps({"sittings": {
        "https://a/prva": {"title": "Прва седница", "starts": "", "agenda": ["Избор председника"], "votes": [["x", "y"]],
                           "continues": "2026-11-25T10:00"}, **more}}), encoding="utf-8")
    at = lambda *t: pages_mikrofon.waiting([], [], pages_mikrofon.upcoming(tmp_path, [], "15"),
                                           now=dt_(*t, tzinfo=pages_mikrofon.TZ)).get("sazvano")
    put()
    first = {"naslov": "Prva sednica", "url": "https://a/prva", "pocinje": "2026-11-25T10:00", "tacke": [], "nastavak": True}
    assert at(2026, 11, 24, 22) == first and at(2026, 11, 25, 9, 59) == first
    assert at(2026, 11, 25, 12) == first  # its hour come and no other known: the live page knows whether it has begun
    assert at(2026, 11, 26, 0, 1) is None
    put(**{"https://a/druga": {"title": "Друга седница", "starts": "2026-11-26T10:00", "agenda": ["Буџет"], "votes": []}})
    assert at(2026, 11, 25, 9) == first and at(2026, 11, 25, 12)["naslov"] == "Druga sednica"  # the nearest to come
    assert "nastavak" not in at(2026, 11, 25, 12)


def test_a_second_sitting_convened_goes_by_itself_from_the_listing_to_the_live_page(tmp_path, monkeypatch):
    """25 Nov 2026, a trial: a listing and a page made up in the shape of the Assembly's, read as votes reads them, made
    the live service's file as the build makes it, and shown as the service shows it."""
    import sys
    from datetime import datetime as dt_
    from zailiprotiv import skupstina
    from zailiprotiv.config import BASE, CONVOCATIONS
    sys.path.insert(0, str(Path(__file__).parent.parent / "live"))
    from uzivo import page
    from uzivo.state import Tracker
    first_url, second_url = f"{BASE}/Прва_седница.54098.43.html", f"{BASE}/Друга_седница.54120.43.html"
    old = (Path(__file__).parent / "fixtures" / "pages" / "sednica.54098.43.html").read_text(encoding="utf-8")
    new = ('<p class="posted">Среда, 25. новембар 2026.</p><h2>Друга седница</h2><p class="preamble">Председник Народне скупштине '
           'Републике Србије Александар Чупић сазвао је Другу седницу Народне скупштине Републике Србије у Петнаестом сазиву, за '
           'уторак, 1. децембар 2026. године, са почетком у 10.00 часова.</p>')
    forms = {"списак": "<div>За ову седницу утврђен је следећи дневни ред:</div><ol><li>Предлог закона о буџету;</li><li>Избор судија.</li></ol>",
             "редови": "<div>За ову седницу утврђен је следећи дневни ред:</div><div>1.Предлог закона о буџету;</div><div>2. Избор судија.</div>",
             "реченица": "<div>Дневни ред са једном тачком и то: Избор Владе.</div>", "без реда": ""}
    monkeypatch.setattr(page, "_now", lambda: dt_(2026, 11, 30, 20, 0, tzinfo=pages_mikrofon.TZ))
    (tmp_path / "15").mkdir()
    for name, body in forms.items():
        links_ = f'<a href="{second_url}">Друга седница Народне скупштине Републике Србије у Петнаестом сазиву</a>' \
                 f'<a href="{first_url}">Прва седница Народне скупштине Републике Србије у Петнаестом сазиву</a>'
        site_ = {**{u: "" for u in CONVOCATIONS["15"]["listings"]}, CONVOCATIONS["15"]["listings"][0]: links_,
                 first_url: old, second_url: new + body}
        found, _ = skupstina.index(lambda u: site_[urllib.parse.unquote(u)].encode(), "15")
        (tmp_path / "15" / "index.json").write_text(json.dumps({"sittings": {s.url: {
            "title": s.title, "votes": [[v.item, v.pdf] for v in s.votes], "agenda": s.agenda, "starts": s.starts,
            **({"continues": s.continues} if s.continues else {})} for s in found}}), encoding="utf-8")
        built = dt_(2026, 11, 25, 13, 0, tzinfo=pages_mikrofon.TZ)
        rows = pages_mikrofon.sittings(tmp_path, "15")
        w = pages_mikrofon.waiting([], [], pages_mikrofon.upcoming(tmp_path, [], "15"), None, pages_mikrofon.read_live(rows, built),
                                   pages_mikrofon.agenda(tmp_path, "15", rows), now=built)
        items = {"списак": ["Predlog zakona o budžetu", "Izbor sudija"], "реченица": ["Izbor Vlade"], "без реда": []}.get(
            name, ["Predlog zakona o budžetu", "Izbor sudija"])
        assert urllib.parse.unquote(w["sazvano"]["url"]) == second_url and w["sazvano"]["pocinje"] == "2026-12-01T10:00", name
        assert w["sazvano"]["tacke"] == items and "nastavak" not in w["sazvano"], name
        assert pages_mikrofon.next_start(tmp_path, "15", built)["pocinje"] == "2026-12-01T10:00"
        assert pages_mikrofon.label(pages_mikrofon.current_sitting(rows, built)["title"]) == "Druga sednica"
        t = Tracker(None, "Europe/Belgrade")
        t.use_waiting(json.loads(json.dumps(w)))
        t.item = {"n": 6, "t": int(dt_(2026, 11, 25, 11, 30, tzinfo=pages_mikrofon.TZ).timestamp())}  # the First's last item
        snap = t.snapshot(now=dt_(2026, 11, 30, 20, 0, tzinfo=pages_mikrofon.TZ).timestamp())
        html = page.fragment(snap, cyr=False, site="", tz=pages_mikrofon.TZ)
        assert "Sednica sutra u 10" in html and "nastavlja" not in html, name
        assert [x["stanje"] for x in (snap["dnevni_red"] or {"tacke": []})["tacke"]] == ["na_redu", ""][:len(items)], name
        assert [x["tekst"] for x in (snap["dnevni_red"] or {"tacke": []})["tacke"]] == items, name


def test_the_waiting_file_lists_the_days_made_from_the_notes():
    from zailiprotiv import pages_mikrofon
    w = pages_mikrofon.waiting([], [], days_=["2026-11-25", "2026-11-24"], notes_=["2026-11-25"])
    assert w["dani"] == ["2026-11-24", "2026-11-25"] and w["iz_beleski"] == ["2026-11-25"]
    assert "iz_beleski" not in pages_mikrofon.waiting([], [], days_=["2026-11-25"])


# The page while the live service is down is the live page itself (27 Nov 2026).

DATA = Path(__file__).resolve().parents[1] / "data"


def _real_days() -> list[Path]:
    days = sorted(DATA.glob("*/snimak/*.json"), key=lambda f: f.stem)
    return [days[0], days[-1]] if days else []


def test_the_page_while_the_service_is_down_is_the_live_page_drawn_from_real_days():
    import re
    from zailiprotiv import pages_govornici
    live_page, _ = pages_mikrofon._uzivo()
    told = {"kviz": [], "cinjenice": [{"text": "Na sajtu je 2097 zakona.", "href": "zakoni", "key": "laws"}]}
    for f in _real_days():  # the oldest day read from a recording and the newest, as the data has them
        day = pages_govornici.with_points(DATA, json.loads(f.read_text(encoding="utf-8")))
        snap = pages_mikrofon.live_snapshot(day, facts={}, waiting_=told,
                                            summary=pages_govornici.day_summary(DATA, f.parent.parent.name, day["dan"]))
        assert snap["dan"] == day["dan"] and snap["stanje"] == "nema_prenosa" and snap["snimak"]
        assert len(snap["danas"]) == sum(1 for t in day["govori"] if t.get("okvira", 0) >= 2) > 0
        for cyr in (False, True):
            html = pages_mikrofon.offline_page(snap, cyr=cyr, waiting_=told, live="https://mikrofon.zailiprotiv.rs/")
            # one source: the live page's own styles and script, its own part, its own day's list
            assert live_page.CSS in html and live_page.SCRIPT in html and '<div id="deo"' in html
            assert html.count('<li id="t') == len(snap["danas"]) and 'class="turns"' in html
            assert ("Тренутно не пратимо пренос" if cyr else "Trenutno ne pratimo prenos") in html
            assert '<meta name="robots" content="noindex">' in html and "Ne zaseda" not in html and "Не заседа" not in html
            assert not re.search(r'(?:href|src|data-share)="/(?!/)', html)  # the edge's <base> would send them to the site
            assert not re.search(r'<(?:img|script|link)\b[^>]*\b(?:src|href)="https?://', html)  # nothing loaded from elsewhere
            assert len(html.encode()) < 1_000_000
            # the part is asked for only under the edge, on the service's host; not on the site's (a 404 every 30 s)
            assert '<body data-base="' in html and 'data-uzivo-host="mikrofon.zailiprotiv.rs"' in html
        assert 'own && location.hostname !== own)) return;' in live_page.SCRIPT and 'getAttribute("data-uzivo-host")' in live_page.SCRIPT
        from zoneinfo import ZoneInfo
        assert 'data-uzivo-host="' not in live_page.page(snap, cyr=False, site="https://zailiprotiv.rs/", tz=ZoneInfo("Europe/Belgrade"))


def test_a_day_the_service_cannot_read_fails_the_build_rather_than_draw_an_empty_page():
    import pytest
    told = {"kviz": [], "cinjenice": []}
    turn = {"ime": "Petrović Petar", "adresa": "", "grupa": "", "uloga": "Lista A", "od": 1794920657, "do": 1794926412,
            "okvira": 9}
    assert len(pages_mikrofon.live_snapshot({"dan": "2026-11-17", "govori": [turn]}, facts={}, waiting_=told)["danas"]) == 1
    with pytest.raises(KeyError):  # a turn without its end
        pages_mikrofon.live_snapshot({"dan": "2026-11-17", "govori": [{k: v for k, v in turn.items() if k != "do"}]},
                                     facts={}, waiting_=told)
    with pytest.raises(ValueError):  # a day the service would not list (here: not a day)
        pages_mikrofon.live_snapshot({"dan": "2026-11-17", "govori": "nije spisak"}, facts={}, waiting_=told)
