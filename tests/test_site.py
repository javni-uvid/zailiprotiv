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
    (d / "notes").mkdir()
    (d / "notes" / "b.json").write_text(json.dumps({"checked": "2026-11-12", "independent": [
        {"source": "Фискални савет", "date": "2026-07-01", "title": "Оцена", "url": "https://www.fiskalnisavet.rs/x",
         "note": "Фискални савет оцењује да закон нема фискалне ефекте."}], "media": []}))
    (d / "transcripts").mkdir()
    (d / "transcripts" / "1.json").write_text(json.dumps({"sitting": "s1", "agenda": {"1": "Предлог закона о оружју"},
        "days": [{"day": 1, "url": "https://www.parlament.gov.rs/upload/archive/files/cir/doc/stenografske_beleske/x.docx",
                  "title": "", "date": "10 јул 2026", "provisional": True}],
        "amendments": [{"day": 1, "item": 1, "article": 3, "by": "народни посланик Ненад Абрамовић"}],
        "speeches": {"0": {"day": 1, "speaker": "ПРЕДСЕДНИК", "chair": True, "part": "general", "items": [1], "text": "x"},
                     "1": {"day": 1, "speaker": "НЕНАД АБРАМОВИЋ", "chair": False, "part": "general", "items": [1],
                           "text": "један два три"},
                     "2": {"day": 1, "speaker": "МИНИСТАР НЕКИ", "chair": False, "part": "detail", "items": [1],
                           "text": "један"}}}))
    (d / "short_titles.json").write_text(json.dumps({"L": "Oružje i municija"}))
    (d / "debates").mkdir()
    (d / "debates" / "b.json").write_text(json.dumps({"model": "claude-opus-5-5", "debate": {
        "predlagac": ["Предлагач наводи да закон усклађује прописе са ЕУ."], "podrska": [],
        "zamerke": ["Посланици групе ПГ Б оцењују да закон отежава лов."],
        "citati": [{"govornik": "НЕНАД АБРАМОВИЋ", "grupa": "ПГ А", "dan": 1,
                    "tekst": "Овај закон не ваља јер укида дозволе за ловце."}]}}))
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
    assert "Oružje i municija" in (out / "zakoni.html").read_text()  # the short name in lists
    assert "<h1>Oružje i municija</h1>" in law and '<p class="official">Zakon o oružju</p>' in law
    index = json.loads((out / "podaci.json").read_text())
    assert index["laws"][0]["t"] == "Oružje i municija" and index["laws"][0]["s"] == "zakon-o-oruzju"
    assert len(index["mps"]) == 3 and (out / "site.js").exists() and (out / "fonts").is_dir()
    home = (out / "index.html").read_text()
    assert '<span class="w-za">Za</span> ili <span class="w-protiv">Protiv</span>' in home
    mp = (out / "poslanik" / "abramovic-nenad.html").read_text()
    assert "Glasovi protiv" in mp and "Glasovi za" in mp and "Po vrsti zakona" in mp
    assert "Sa kim glasa isto" not in mp  # fewer than ten votes in common with any group
    assert (out / "kako-racunamo.html").exists() and "kako-racunamo.html#" in (out / "zakon" / "zakon-o-oruzju.html").read_text(encoding="utf-8")
    import xml.dom.minidom as dom
    assert dom.parse(str(out / "zakoni.xml")).getElementsByTagName("entry")
    assert list((out / "poslanik").glob("*.xml")) and all(dom.parse(str(f)) for f in (out / "poslanik").glob("*.xml"))
    assert (out / "oblasti.html").exists()
    assert "Iz rasprava" in mp and "„Ovaj zakon ne valja jer ukida dozvole za lovce.“" in mp
    assert (out / "CNAME").read_text().strip() == "zailiprotiv.rs"
    assert "Allow: /" in (out / "robots.txt").read_text()
    assert "https://zailiprotiv.rs/zakon/zakon-o-oruzju.html" in (out / "sitemap.xml").read_text()
    assert not (out / "najvise-protiv.html").exists()
    assert "50% glasova protiv" in law
    assert law.index("50% glasova protiv") < law.index("Šta zakon menja") < law.index("Rasprava u Skupštini") \
        < law.index("Detaljnije")  # the outcome first, the long text last
    assert "Hitan postupak" in law
    assert "Rasprava u Skupštini" in law and "o 1 amandmanu na ovaj zakon" in law and "Protiv zakona</h3>" in law
    assert "„Ovaj zakon ne valja jer ukida dozvole za lovce.“" in law and "Nenad Abramović, PG A" in law
    assert "glas: za" in law  # the quote's speaker voted for the law
    assert "Fiskalni savet" in law and "Nezavisna i međunarodna tela" in law and "Mediji i civilno" not in law
    names = re.findall(r'class="row-title" href="poslanik/[^"]+">([^<]+)<', (out / "poslanici.html").read_text())
    assert names == ["Abramović Nenad", "Čolaković Jovan", "Ilić-Stošić Biljana"]  # Č after C, before I
    for page in out.rglob("*.html"):
        text = page.read_text()
        # The site's own script only, nothing from other servers, no plain http.
        if page.name == "pretraga.html":  # and the search's two scripts, both from the site itself
            assert re.findall(r'<script src="(?!site\.js)([^"?]+)', text) == ["pagefind/pagefind-ui.js", "pretraga.js"]
            text = re.sub(r'<script src="(?:pagefind/pagefind-ui|pretraga)\.js[^>]*>', "", text)
        if page.name == "glasaj.html":  # and its own data and script, both from the site itself
            assert re.findall(r"<script[^>]*>", text)[1:] == ['<script type="application/json" id="quiz-data">',
                '<script src="glasaj.js?v=' + re.search(r'data-v="(\w+)"', text).group(1) + '" defer>']
            text = text.replace('<script type="application/json" id="quiz-data">', "").replace(
                '<script src="glasaj.js?v=' + re.search(r'data-v="(\w+)"', text).group(1) + '" defer>', "")
        assert re.findall(r"<script[^>]*>", text) == [f'<script src="{"../" if page.parent != out else ""}site.js?v='
                                                      + re.search(r'data-v="(\w+)"', text).group(1) + '" defer>']
        assert "http://" not in text and not re.search(r'(?:src|href)="https?://(?!www\.parlament\.gov\.rs|github\.com)'
                                                       r'[^"]*\.(?:js|css|woff2?)', text)
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


def test_site_builds_every_convocation(tmp_path):
    import shutil
    one = data(tmp_path)
    root = tmp_path / "root"
    shutil.copytree(one, root / "14")
    shutil.copytree(one, root / "13")
    older = root / "13" / "votes" / "1.json"
    store = json.loads(older.read_text())
    store["votes"] = {BASE.replace("2026", "2023") + "1.pdf#0": {**v, "when": "2023-07-10T15:55:01"}
                      for v in store["votes"].values()}
    older.write_text(json.dumps(store))
    laws = json.loads((root / "13" / "laws.json").read_text())
    laws["laws"]["L"].update(passed="2023-07-10", votes=list(store["votes"]), final_vote=next(iter(store["votes"])))
    (root / "13" / "laws.json").write_text(json.dumps(laws))
    out = tmp_path / "_site"
    stats = site.build(root, out, None)
    assert stats["laws"] == 1 and stats["all_laws"] == 2
    assert (out / "zakon" / "zakon-o-oruzju.html").exists()  # the current convocation keeps the plain address
    assert "Trinaesti saziv" in (out / "zakon" / "zakon-o-oruzju-2.html").read_text()
    assert (out / "zakoni-13.html").exists() and "zakoni-13.html" in (out / "zakoni.html").read_text()
    mp = (out / "poslanik" / "abramovic-nenad.html").read_text()
    assert "zakon-o-oruzju.html" in mp and "zakon-o-oruzju-2.html" in mp
    assert "abramovic-nenad.html" in (out / "poslanici.html").read_text()  # one page of MPs per convocation
    assert "abramovic-nenad.html" in (out / "poslanici-13.html").read_text()
    assert 'href="poslanici-13.html"' in (out / "poslanici.html").read_text()


def test_a_built_site_loads_nothing_from_other_sites(tmp_path):
    out = tmp_path / "_site"
    site.build(data(tmp_path), out, "zailiprotiv.rs")
    assert site.check(out) == []
    (out / "x.html").write_text('<script src="https://cdn.example.com/a.js"></script>')
    (out / "y.css").write_text("@import url('https://fonts.googleapis.com/css2?family=X');")
    (out / "z.html").write_text('<a href="https://www.parlament.gov.rs/">izvor</a>' + "x" * (site.PAGE_LIMIT + 1))
    assert [b.split(":")[0] for b in site.check(out)] == ["x.html", "y.css", "z.html"]


def test_groups_numbers_quiz_and_share_picture(tmp_path):
    out = tmp_path / "_site"
    site.build(data(tmp_path), out, "zailiprotiv.rs")
    law = (out / "zakon" / "zakon-o-oruzju.html").read_text()
    assert 'og:image" content="https://zailiprotiv.rs/zakon/zakon-o-oruzju.png"' in law
    assert (out / "zakon" / "zakon-o-oruzju.png").read_bytes()[:4] == b"\x89PNG"
    assert "Skupština u brojkama" in (out / "brojke.html").read_text()
    assert (out / "grupe.html").exists() and (out / "glasaj.js").exists()
    quiz = json.loads(re.search(r'id="quiz-data">(.*?)</script>', (out / "glasaj.html").read_text(), re.S).group(1))
    assert quiz["laws"] == [{"s": "zakon-o-oruzju"}] and {m["v"] for m in quiz["mps"]} == {"z", "p", "-"}
    area = next((out / "oblast").glob("*.xml")).read_text()
    assert "<feed" in area and "zakon-o-oruzju.html" in area


def test_visitors_votes_are_sent_only_when_an_address_is_set(tmp_path):
    out = tmp_path / "_site"
    root = data(tmp_path)
    site.build(root, out, "zailiprotiv.rs")
    page = (out / "glasaj.html").read_text()
    assert "ulaze u zbir" not in page and 'data-api=""' in page and "nikuda se ne šalju" in page
    assert json.loads((out / "glasaj.json").read_text()) == {"laws": ["zakon-o-oruzju"]}
    (root / "settings.json").write_text(json.dumps({"votes_api": "https://glasovi.example/"}))
    site.build(root, out, "zailiprotiv.rs")
    page = (out / "glasaj.html").read_text()
    assert "ulaze u zbir" in page and 'data-api="https://glasovi.example/"' in page and "nije istraživanje" in page


def test_links_without_html_when_published(tmp_path):
    out = tmp_path / "_site"
    site.build(data(tmp_path), out, "zailiprotiv.rs", clean=True)
    law = (out / "zakon" / "zakon-o-oruzju.html").read_text()  # the file keeps its name; GitHub Pages serves it without
    assert 'href="../poslanik/abramovic-nenad"' in law and 'href="../kako-racunamo#' in law and 'href="../"' in law
    assert 'content="https://zailiprotiv.rs/zakon/zakon-o-oruzju"' in law and "zakon-o-oruzju.png" in law
    assert "www.parlament.gov.rs" in law and not re.search(r'href="(?!https?:)(?!\.\./podaci\.html)[^"]*\.html', law)
    home = (out / "index.html").read_text()
    assert 'href="zakoni"' in home and 'href="./"' in home and 'href="zakon/zakon-o-oruzju"' in home
    assert "zakon/zakon-o-oruzju</loc>" in (out / "sitemap.xml").read_text() and (out / "sitemap.xml").read_text().count(".html") == 1
    assert "/zakon/zakon-o-oruzju\"" in (out / "zakoni.xml").read_text()
    assert 'href="podaci.html"' in home  # beside the folder podaci/, so it keeps its ending
    assert '+ ".html"' not in (out / "site.js").read_text() and '+ ".html"' not in (out / "glasaj.js").read_text()


def test_the_week_in_the_assembly_and_its_feed(tmp_path):
    out = tmp_path / "_site"
    site.build(data(tmp_path), out, "zailiprotiv.rs")
    week = (out / "nedelja" / "2026-28.html").read_text()  # the law in the test data was passed on 10 July 2026
    assert "6–12. jul 2026." in week and "zakon-o-oruzju.html" in week
    feed = (out / "nedelje.xml").read_text()
    assert '<content type="html">' in feed and "https://zailiprotiv.rs/zakon/zakon-o-oruzju.html" in feed
    assert "nedelja/2026-28.html" in (out / "nedelje.html").read_text()


def test_the_cyrillic_edition(tmp_path):
    from zailiprotiv import cyrillic
    assert cyrillic.cyr("Injekcija, konjunktura, Tanjug; njega, Ljubljana, džak") == "Инјекција, конјунктура, Танјуг; њега, Љубљана, џак"
    assert cyrillic.cyr("PDF na zailiprotiv.rs/glasaj, model claude-sonnet-5-5, XIV saziv") == \
        "PDF на zailiprotiv.rs/glasaj, модел claude-sonnet-5-5, XIV сазив"
    out = tmp_path / "_site"
    site.build(data(tmp_path), out, "zailiprotiv.rs", clean=True, cyrillic=True)
    law, twin = (out / "zakon" / "zakon-o-oruzju.html").read_text(), (out / "cir" / "zakon" / "zakon-o-oruzju.html").read_text()
    assert 'href="../cir/zakon/zakon-o-oruzju"' in law and 'href="../../zakon/zakon-o-oruzju"' in twin
    assert 'lang="sr-Cyrl"' in twin and "Абрамовић Ненад" in twin and 'href="../poslanik/abramovic-nenad"' in twin
    assert 'href="../../style.css' in twin and 'src="../../site.js' in twin and 'href="../../zakon/zakon-o-oruzju.csv"' in twin
    assert '<link rel="canonical" href="https://zailiprotiv.rs/cir/zakon/zakon-o-oruzju">' in twin
    text = re.sub(r"<script.*?</script>|<style.*?</style>|<[^>]+>", " ", twin, flags=re.S)
    assert "Закон о оружју" in text and "гласа" in text and not re.search(r"\b(Zakon|glasao|protiv|poslanik)\b", text)
    assert "cir/zakon/zakon-o-oruzju</loc>" in (out / "sitemap.xml").read_text()
    assert site.check(out) == []


def test_replies_and_the_chairs_measures_are_found_by_rule():
    from zailiprotiv import pages_floor
    say = lambda who, text, chair=False: {"speaker": who, "text": text, "chair": chair, "day": 1}
    speeches = [say("А", "Први."), say("ПРЕДСЕДНИК", "Реч има Б.", True), say("Б", "Одговор."), say("А", "Реплика."),
                say("Б", "Опет."), say("ПРЕДСЕДНИК", "Господине Б, изричем вам опомену.\n39/2AL/JG", True),
                say("В", "Нешто треће."), say("ПРЕДСЕДНИК", "Могао бих да вам изрекнем опомену, али нећу.", True)]
    runs = pages_floor.exchanges(speeches)
    assert [[s["speaker"] for s in r] for r in runs] == [["А", "ПРЕДСЕДНИК", "Б", "А", "Б"]]  # with the chair's words between
    found = pages_floor.measures(speeches)
    assert [(m["kind"], m["before"]["speaker"]) for m in found] == [("opomena", "Б")]
    assert pages_floor.to_whom(found[0], {"А": "а", "Б": "б"}) is None  # "Господине Б": no surname of a speaker
    call = {"kind": "opomena", "chair": {"text": "Извините, господине Ђуришићу. Господине Живковићу, зато што сте то рекли, изричем вам опомену."}}
    assert pages_floor.to_whom(call, {"ЗОРАН ЖИВКОВИЋ": "живковић", "МАРКО ЂУРИШИЋ": "ђуришић"}) == "ЗОРАН ЖИВКОВИЋ"
    about = {"kind": "opomena", "chair": {"text": "Господине Живковићу, зато што сте колеги Србиславу Филиповићу рекли то, изричем вам опомену."}}
    assert pages_floor.to_whom(about, {"ЗОРАН ЖИВКОВИЋ": "живковић", "СРБИСЛАВ ФИЛИПОВИЋ": "филиповић"}) == "ЗОРАН ЖИВКОВИЋ"
    victim = {"kind": "opomena", "chair": {"text": "Изричем вам опомену јер сте увредили Мартиновића."}}
    assert pages_floor.to_whom(victim, {"АЛЕКСАНДАР МАРТИНОВИЋ": "мартиновић"}) is None
    assert pages_floor.spoken(speeches[5]["text"]) == "Господине Б, изричем вам опомену."


def test_the_visit_counter_is_the_only_script_from_elsewhere(tmp_path):
    from zailiprotiv import publish
    (tmp_path / "a.html").write_text(publish.ANALYTICS + " data-cf-beacon='{}'></script>")
    (tmp_path / "b.html").write_text('<script src="https://example.com/x.js"></script>')
    assert [b.split(":")[0] for b in publish.check(tmp_path)] == ["b.html"]


def test_harsh_words_are_counted_in_their_sentence_and_everyday_words_are_not():
    from zailiprotiv import pages_floor
    text = "Град је затрпан ђубретом, тргују стоком, то је лоповлук. Ви сте олош и лопови! Говорим о свињарству, а не о идиотским примедбама."
    found = pages_floor.harsh(text)
    assert [w for w, _ in found] == ["олош", "лопови", "идиотским"]
    assert found[0][1] == "Ви сте олош и лопови!"


def test_portraits_are_read_from_the_list_of_mps():
    from zailiprotiv import mps, photos
    html = ('<a href="https://www.parlament.gov.rs/NENAD_ABRAMOVI%C4%86.1435.891.html"><a name="x"></a></a>'
            '<img src="/upload/thumbs/images/archive/photo/poslanici/14_saziv/288-Nenad_Abramovic_150x0.jpg">'
            '<a href="/NENAD_ABRAMOVIĆ.1435.891.html">ABRAMOVIĆ NENAD</a><img src="/images/logo.png">')
    found = photos.parse(html)
    assert list(found) == ["1435"] and found["1435"]["src"].endswith("288-Nenad_Abramovic_150x0.jpg")
    assert photos.key(found["1435"]["name"]) == mps.key("АБРАМОВИЋ НЕНАД")
