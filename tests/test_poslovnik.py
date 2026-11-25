"""poslovnik.py: the Rules of Procedure read article by article, every version kept."""
import json

from zailiprotiv import poslovnik

MENU = ("<li><a href='/народна-скупштина/важна-документа/пословник-(пречишћени-текст)/уводнa-одредбa.1309.html'>Уводнa одредбa</a>"
        "<li><a href='/народна-скупштина/важна-документа/пословник-(пречишћени-текст)/поступци.1317.html'>Поступци за доношење аката</a>")
PAGE = MENU + """<div class="col"><a name="1"></a>
<div class="block"><h3>I. УВОДНА ОДРЕДБА</h3><div><p align="center"><b>Члан 1.</b></p>
<p align="justify">Овим пословником уређују се организација и рад Народне скупштине.</p></div></div>
<div class="block"><h3>IХ. ПОСТУПЦИ ЗА ДОНОШЕЊЕ АКАТА</h3><p class="preamble">1. Хитни поступак</p><div>
<p align="center"><b>Члан 167.</b></p><p align="justify">Закон се може донети по хитном поступку.</p>
<p align="justify">Предлагач је дужан да наведе разлоге.</p>
<p><b>&nbsp;&nbsp;Члан 168.<br/></b><br/>Први став у реду.<br/><br/>Други став.</p></div></div></div>"""


def test_articles_chapters_and_their_pages():
    d = poslovnik.parse(PAGE)
    assert [(c["broj"], c["naslov"]) for c in d["glave"]] == [("I", "УВОДНА ОДРЕДБА"), ("IX", "ПОСТУПЦИ ЗА ДОНОШЕЊЕ АКАТА")]
    assert d["glave"][0]["url"].endswith("уводнa-одредбa.1309.html")  # a Latin "a" in the menu's title: still found
    assert d["glave"][1]["url"].endswith("поступци.1317.html")
    a = {x["n"]: x for x in d["clanovi"]}
    assert sorted(a) == [1, 167, 168]
    assert a[167]["glava"] == "IX" and a[167]["odeljak"] == "1. Хитни поступак" and len(a[167]["stavovi"]) == 2
    assert a[168]["stavovi"] == ["Први став у реду.", "Други став."]  # one <p> of lines broken by <br/>


def test_the_last_article_ends_with_its_chapter():
    """25 Nov 2026: the end of the Assembly's page as it was that day. The margin's calendar and news and the foot of the
    page stood as paragraphs of article 298, and two "versions" were kept in which nothing else had changed."""
    from pathlib import Path
    end = (Path(__file__).parent / "fixtures" / "pages" / "poslovnik-kraj.1422.html").read_text(encoding="utf-8")
    assert "Цео календар догађаја" in end and "Прикажи мобилну верзију" in end  # the page does go on after the Rules
    d = poslovnik.parse(end)
    assert [a["n"] for a in d["clanovi"]] == [295, 296, 297, 298]
    last = d["clanovi"][-1]["stavovi"]
    assert len(last) == 1 and last[0].startswith("Овај пословник ступа на снагу") and last[0].endswith("у новом сазиву.")
    # whatever the margin says, in whatever words, the text and its fingerprint are the same
    other = end.replace("наставак Прве седнице", "нешто друго").replace("Уторак, 24. новембар 2026.", "Петак, 4. децембар 2026.")
    assert other != end and poslovnik.fingerprint(poslovnik.parse(other)) == poslovnik.fingerprint(d)
    kept = poslovnik.load(Path(__file__).resolve().parents[1] / "data" / "poslovnik", "2026-11-20")
    assert kept["clanovi"][-1]["stavovi"] == last and kept["otisak"] == poslovnik.fingerprint(kept)


def test_a_version_is_kept_only_when_the_text_changes(tmp_path):
    d = poslovnik.parse(PAGE)
    assert poslovnik.store(tmp_path, d, "2026-11-20") == "2026-11-20.json"
    assert poslovnik.store(tmp_path, d, "2026-11-21") is None  # the same text: no new version
    d2 = json.loads(json.dumps(d))
    d2["clanovi"][1]["stavovi"][0] = "Закон се може донети по хитном поступку, изузетно."
    assert poslovnik.store(tmp_path, d2, "2026-12-01") == "2026-12-01.json"
    index = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    assert [v["od"] for v in index["verzije"]] == ["2026-11-20", "2026-12-01"]
    assert "изузетно" not in poslovnik.load(tmp_path, "2026-11-25")["clanovi"][1]["stavovi"][0]  # in force then
    assert "изузетно" in poslovnik.load(tmp_path)["clanovi"][1]["stavovi"][0]
    assert poslovnik.load(tmp_path, "2020-01-01")["prvi_put_vidjeno"] == "2026-11-20"  # before any: the earliest


def test_the_articles_a_speech_invokes():
    got = lambda t, p=True: [n for n, _, _ in poslovnik.cited(t, p)]
    assert got("Повреда Пословника, члан 103. став 1. Дакле, позивање на члан 106. став 1.") == [103, 106]
    assert got("Рекламирам члан 107.") == [107]
    assert got("Говорим о томе. " + "x" * 450 + " члан 104.") == []                     # far from the head: not taken
    assert got("Како каже члан 107. Пословника, достојанство", p=False) == [107]       # the Rules named: anywhere
    assert got("Повреда Пословника, члан 98. Устава каже", ) == []                       # of the Constitution
    assert got("члан 5. закона о буџету", p=False) == [] and got("члан 900.") == []
    text = "Повреда Пословника, члан 103."
    (n, a, b), = poslovnik.cited(text, True)
    assert text[a:b] == "члан 103."


def test_the_invoked_articles_listed_most_first():
    from collections import Counter
    from zailiprotiv import pages_floor
    rules = poslovnik.parse(PAGE)
    by_conv = [{"name": "Petnaesti", "invoked": Counter({167: 2})}, {"name": "Četrnaesti", "invoked": Counter({1: 3, 167: 1})}]
    got = pages_floor.invoked_articles(Counter({1: 3, 167: 3, 999: 5}), by_conv, rules)
    assert [(a["n"], a["count"]) for a in got] == [(1, 3), (167, 3)]  # ties by number; an article the Rules lack: out
    a = got[1]
    assert a["convs"] == [{"name": "Petnaesti", "count": 2}, {"name": "Četrnaesti", "count": 1}]
    assert a["section"] == "1. Hitni postupak" and a["text"][0].startswith("Zakon se može") and a["url"].endswith(".1317.html")
    assert pages_floor.invoked_articles(Counter({1: 1}), by_conv, None) == []


def test_a_term_keeps_its_sentence_only_while_its_articles_read_the_same(tmp_path):
    from zailiprotiv import pages_floor
    d = poslovnik.parse(PAGE)
    poslovnik.store(tmp_path, d, "2026-11-20")
    (tmp_path / poslovnik.TERMS).write_text(json.dumps([
        {"id": "hitni-postupak", "pojam": "Hitni postupak", "clanovi": [167, 168], "verzija": "2026-11-20",
         "objasnjenje": "Naše prepričavanje.", "kako": "brojke", "na_sajtu": "Kako sajt broji."},
        {"id": "uvod", "pojam": "Uvod", "clanovi": [1], "verzija": "2026-11-20", "objasnjenje": "Uvod."}]), encoding="utf-8")
    t = {x["id"]: x for x in poslovnik.terms(tmp_path)}
    assert not t["hitni-postupak"]["changed"] and [a["n"] for a in t["hitni-postupak"]["articles"]] == [167, 168]
    d2 = json.loads(json.dumps(d))
    d2["clanovi"][1]["stavovi"][0] = "Закон се изузетно може донети по хитном поступку."
    poslovnik.store(tmp_path, d2, "2026-12-01")
    t = {x["id"]: x for x in poslovnik.terms(tmp_path)}
    assert t["hitni-postupak"]["changed"] and not t["uvod"]["changed"]  # only the term whose article changed
    shown = {x["id"]: x for x in pages_floor.rule_terms(list(t.values()), [{"n": 1}], d2)}
    assert shown["hitni-postupak"]["explained"] is None  # the article alone, until written again
    assert shown["hitni-postupak"]["articles"][0]["text"][0].startswith("Zakon se izuzetno")  # as the Rules now read
    assert shown["hitni-postupak"]["method"] == "brojke" and shown["uvod"]["explained"] == "Uvod."
    assert shown["uvod"]["articles"][0]["listed"] and not shown["hitni-postupak"]["articles"][0]["listed"]
    assert poslovnik.terms(tmp_path / "none") == []


def test_a_retelling_is_shown_in_the_files_own_words():
    """The page gives a retelling a paragraph a sentence, its numbers in bold: form only, not a letter changed. Every
    term belongs to a part of the page, and each part's terms follow one another in the file."""
    from itertools import groupby
    from pathlib import Path
    from zailiprotiv import pages_floor
    folder = Path(__file__).resolve().parents[1] / "data" / "poslovnik"
    kept = json.loads((folder / poslovnik.TERMS).read_text(encoding="utf-8"))
    for t in kept:
        pieces = pages_floor.retold(t["objasnjenje"])
        assert " ".join("".join(x for x, _ in s) for s in pieces) == t["objasnjenje"]
    bold = [x for t in kept for s in pages_floor.retold(t["objasnjenje"]) for x, b in s if b]
    assert {"84 poslanika", "dva minuta", "10%", "10 do 18 časova", "24 časa"} <= set(bold)
    assert "109" not in bold  # an article's number is no limit
    assert [k for k, _ in groupby(t["deo"] for t in kept)] == [id_ for id_, _ in pages_floor.RULE_PARTS]
    parts = pages_floor.rule_parts([{"id": "a", "part": "tok-sednice"}, {"id": "b", "part": ""}])
    assert [(p["id"], [t["id"] for t in p["terms"]]) for p in parts] == [("tok-sednice", ["a"]), ("", ["b"])]


def test_the_page_of_the_rules_keeps_the_addresses_other_pages_link_to():
    """The live page, the notes and the site lead to #pojmovi, #pojam-<id>, #clanovi and #clan-<n>; the finder on the
    page looks through every list of it."""
    import re
    from pathlib import Path
    from zailiprotiv import pages_floor
    text = (Path(pages_floor.__file__).parent / "templates" / "rules_cited.html").read_text(encoding="utf-8")
    for id_ in ("pojmovi", "clanovi", "pojam-{{ t.id }}", "clan-{{ a.n }}"):
        assert text.count(f'id="{id_}"') == 1
    assert 'id="rc-rows"' in text and re.search(r'data-filter="[^"]*rt-\{\{ loop\.index \}\}[^"]*rc-rows"', text)
    assert not {id_ for id_, _ in pages_floor.RULE_PARTS} & {"pojmovi", "clanovi", "sadrzaj"}


def test_the_sites_terms_rest_on_articles_the_rules_have():
    from pathlib import Path
    folder = Path(__file__).resolve().parents[1] / "data" / "poslovnik"
    kept = json.loads((folder / poslovnik.TERMS).read_text(encoding="utf-8"))
    ids = [t["id"] for t in kept]
    assert len(ids) == len(set(ids))
    terms = poslovnik.terms(folder)
    assert all(len(t["articles"]) == len(t["clanovi"]) for t in terms)


def test_the_rules_share_picture_is_drawn_from_the_rules_in_both_scripts(tmp_path):
    """25 Nov 2026: an open book at the article on the reply, in each script; the general picture when the retelling no
    longer stands on the article as it reads."""
    from pathlib import Path

    from PIL import Image

    from zailiprotiv import cyrillic, poslovnik, rules_card
    root = Path(__file__).parents[1]
    terms, rules = poslovnik.terms(root / "data/poslovnik"), poslovnik.load(root / "data/poslovnik")
    shown = rules_card.parts(terms, rules)
    assert [a for a, _ in shown[1]] == ["Član 103", "Član 104"] and shown[0] == next(t for t in terms if t["id"] == "replika")["objasnjenje"]
    lat, cir = tmp_path / "a.png", tmp_path / "b.png"
    rules_card.both(shown, lat, cir)
    for f in (lat, cir):
        assert Image.open(f).size == (1200, 630) and f.stat().st_size < 300_000
    assert lat.read_bytes() != cir.read_bytes()
    changed = [{**t, "changed": True} if t["id"] == rules_card.TERM else t for t in terms]
    assert rules_card.parts(changed, rules) is None and rules_card.parts([], rules) is None and rules_card.parts(terms, None) is None
    assert rules_card.parts(terms, {"clanovi": [a for a in rules["clanovi"] if a["n"] != 103]}) is None
    page = '<meta property="og:image" content="https://x.rs/poslovnik.png" data-cir-content="https://x.rs/poslovnik-cir.png"><p>a</p>'
    assert 'content="https://x.rs/poslovnik-cir.png"><' in cyrillic.page(page, "a.html") and "data-cir" not in cyrillic.page(page, "a.html")
