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
