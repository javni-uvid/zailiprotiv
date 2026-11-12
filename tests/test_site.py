import json
import re

from zailiprotiv import site

BASE = "https://www.parlament.gov.rs/upload/rezultati_glasanja/2026/"


def data(tmp_path):
    d = tmp_path / "data"
    (d / "votes").mkdir(parents=True)
    rows = [[1, "АБРАМОВИЋ НЕНАД", "za", "ПГ А"], [2, "ИЛИЋ-СТОШИЋ БИЉАНА", "protiv", "ПГ Б"],
            [3, "ЧОЛАКОВИЋ ЈОВАН", "nije_prisutan", "ПГ Б"]]
    (d / "votes" / "1.json").write_text(json.dumps({"sitting": "s1", "title": "Седмо ванредно заседање", "pdfs": {},
        "votes": {BASE + "1.pdf#0": {"when": "2026-07-10T15:55:01", "item": "1. Предлог закона о оружју",
                                     "kind": "Гласање о предлогу акта у целини", "session": "",
                                     "counts": {"za": 1, "protiv": 1, "uzdrzan": 0, "nije_glasao": 0,
                                                "nije_prisutan": 1}, "problems": [], "rows": rows}}}))
    (d / "laws.json").write_text(json.dumps({"fetched": "2026-11-12T02:00:00+00:00", "laws": {"L": {
        "title": "Zakon o oružju", "passed": "2026-07-10", "gazette": "63/26", "treaty": False, "pdf": "z.pdf",
        "bill_pdf": "p.pdf", "kind": "law", "areas": [4], "votes": [BASE + "1.pdf#0"],
        "final_vote": BASE + "1.pdf#0"}}}))
    (d / "summaries").mkdir()
    (d / "summaries" / "b.json").write_text(json.dumps({"model": "claude-sonnet-5-5", "summary": {
        "ukratko": "Закон уређује набавку оружја, према предлагачу.", "razlozi": ["усклађивање са ЕУ"],
        "promene": ["нова дозвола"], "sredstva": "Нису потребна средства."}}))
    laws = json.loads((d / "laws.json").read_text())
    laws["laws"]["L"]["bill_file"] = "b.json"
    (d / "laws.json").write_text(json.dumps(laws))
    return d


def test_site_builds_every_page(tmp_path):
    out = tmp_path / "_site"
    stats = site.build(data(tmp_path), out, "zailiprotiv.rs")
    assert stats["laws"] == 1 and stats["mps"] == 3 and stats["linked"] == 1
    law = (out / "zakon" / "zakon-o-oruzju.html").read_text()
    assert "Odbrana i bezbednost" in law and "Ilić-Stošić Biljana" in law
    assert "Zakon uređuje nabavku oružja, prema predlagaču." in law and "AI model (claude-sonnet-5-5)" in law
    assert "Zakon uređuje nabavku oružja" in (out / "zakoni.html").read_text()
    assert (out / "CNAME").read_text().strip() == "zailiprotiv.rs"
    assert "Allow: /" in (out / "robots.txt").read_text()
    assert "https://zailiprotiv.rs/zakon/zakon-o-oruzju.html" in (out / "sitemap.xml").read_text()
    assert not (out / "najvise-protiv.html").exists()
    assert "1. mesto u sazivu" in law and "50.0%" in law
    assert "Hitan postupak" in law
    names = re.findall(r'poslanik/[^"]+">([^<]+)<', (out / "poslanici.html").read_text())
    assert names == ["Abramović Nenad", "Čolaković Jovan", "Ilić-Stošić Biljana"]  # Č after C, before I
    for page in out.rglob("*.html"):
        text = page.read_text()
        assert "<script" not in text and "http://" not in text  # nothing from other servers, no plain http
        assert not re.search(r"[Ѐ-ӿ]", text), page  # Latin pages: no Cyrillic left


def test_serbian_order():
    words = ["Čolaković", "Cvetković", "Ćirić", "Džajić", "Đurić", "Dinić", "Ljubić", "Lazić", "Šarac", "Žarić"]
    assert sorted(words, key=site.collate) == ["Cvetković", "Čolaković", "Ćirić", "Dinić", "Džajić", "Đurić",
                                               "Lazić", "Ljubić", "Šarac", "Žarić"]


def test_most_against_first():
    def it(za, protiv, passed="2026-01-01"):
        c = {"za": za, "protiv": protiv, "uzdrzan": 0, "nije_glasao": 0, "nije_prisutan": 0}
        return {"final": {"counts": c, "rows": []}, "law": {"passed": passed, "title": f"{za}:{protiv}"}}
    items = [it(140, 0), it(130, 40), it(126, 60), it(150, 60), it(130, 40, "2026-02-01"), {"final": None, "law": {}}]
    ranked = [x["law"]["title"] for x in site.most_against(items, 3)]
    assert ranked == ["126:60", "150:60", "130:40"]
    assert site.most_against(items, 3)[2]["law"]["passed"] == "2026-02-01"  # a tie goes to the newer law
