import json
import re
import shutil

import pytest

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


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    """One site built from data(), for the tests that only read it: (the site's folder, the build's stats)."""
    tmp = tmp_path_factory.mktemp("built")
    out = tmp / "_site"
    return out, site.build(data(tmp), out, "zailiprotiv.rs")


def test_site_builds_every_page(built):
    out, stats = built
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
    # The page opens with the card; the lists of every vote are on a page of their own, linked from it.
    votes = (out / "poslanik" / "abramovic-nenad-glasovi.html").read_text()
    assert 'id="ukratko"' in mp and 'href="abramovic-nenad-glasovi.html"' in mp and "Po vrsti zakona" not in mp
    assert "Glasovi protiv" in votes and "Glasovi za" in votes and "Po vrsti zakona" in votes and 'href="abramovic-nenad.html"' in votes
    assert "Sa kim glasa isto" not in mp  # fewer than ten votes in common with any group
    # What a search result shows: the MP's own counts first, the same sentence for everyone; who they are as data.
    assert re.search(r'<meta name="description" content="Nenad Abramović, poslanik: od \d+ konačn\w+ glasanja o zakonima \d+ za, \d+ protiv', mp)
    assert '"@type": "Person"' in mp and '"url": "https://zailiprotiv.rs/poslanik/abramovic-nenad"' in mp
    assert (out / "kako-racunamo.html").exists() and "kako-racunamo.html#" in (out / "zakon" / "zakon-o-oruzju.html").read_text(encoding="utf-8")
    import xml.dom.minidom as dom
    assert dom.parse(str(out / "zakoni.xml")).getElementsByTagName("entry")
    assert list((out / "poslanik").glob("*.xml")) and all(dom.parse(str(f)) for f in (out / "poslanik").glob("*.xml"))
    assert (out / "oblasti.html").exists()
    assert "Iz rasprava" in mp and "„Ovaj zakon ne valja jer ukida dozvole za lovce.“" in mp
    assert (out / "CNAME").read_text().strip() == "zailiprotiv.rs"
    assert "Allow: /" in (out / "robots.txt").read_text()
    sitemap = (out / "sitemap.xml").read_text()
    assert "https://zailiprotiv.rs/zakon/zakon-o-oruzju.html" in sitemap
    # The MP's page is the one to find: the page of every vote is linked from it, kept out of search engines.
    assert "poslanik/abramovic-nenad.html" in sitemap and "-glasovi.html" not in sitemap
    assert '<meta name="robots" content="noindex">' in votes and "nedelja/" not in sitemap
    assert not (out / "najvise-protiv.html").exists()
    assert "<dt>Glasovi protiv</dt><dd>50%" in law
    assert law.index("<dt>Glasovi protiv</dt><dd>50%") < law.index("Šta zakon menja") < law.index("Rasprava u Skupštini") \
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
        v = re.search(r'data-v="(\w+)"', text).group(1)
        if page.name == "podelili-salu.html":  # the quiz: and its own data and script, both from the site itself
            assert re.findall(r"<script\b[^>]*>", text, re.I)[1:] == ["<script>", '<script type="application/json" id="quiz-data">',
                                                              f'<script src="../glasaj.js?v={v}" defer>']
            assert 'classList.add("q-wait")' in text
            text = text.replace('<script type="application/json" id="quiz-data">', "").replace(f'<script src="../glasaj.js?v={v}" defer>', "").replace("<script>", "", 1)
        if page.name == "glasaj.html":  # the visitor's ballot: its own script
            assert re.findall(r"<script\b[^>]*>", text, re.I)[1:] == ["<script>", f'<script src="listic.js?v={v}" defer>']
            assert text.count("<script>") == 1 and 'getElementById("lb-mine").hidden = false' in text  # opens the ballot before the first paint
            text = text.replace(f'<script src="listic.js?v={v}" defer>', "").replace("<script>", "", 1)
        if page.parent.name == "govornici" and "<script>" in text:  # a day's turns: the player and the share, inline
            assert text.count("<script>") == 1
            text = text.replace("<script>", "", 1)
        if page.name == "mikrofon.html" and "<script>" in text:  # the player and the quiz: one script of its own, inline
            assert text.count("<script>") == 1 and "youtube-nocookie.com/embed/" in text
            text = text.replace("<script>", "", 1)
        text = re.sub(r'<script type="application/ld\+json">.*?</script\s*>', "", text, flags=re.S | re.I)  # data for search engines, not code
        here = "/" if page.name == "404.html" else "../" if page.parent != out else ""  # the 404 page is served at any depth
        assert re.findall(r"<script\b[^>]*>", text, re.I) == [f'<script src="{here}site.js?v='
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
    mp = (out / "poslanik" / "abramovic-nenad-glasovi.html").read_text()
    assert "zakon-o-oruzju.html" in mp and "zakon-o-oruzju-2.html" in mp
    assert "abramovic-nenad.html" in (out / "poslanici.html").read_text()  # one page of MPs per convocation
    assert "abramovic-nenad.html" in (out / "poslanici-13.html").read_text()
    assert 'href="poslanici-13.html"' in (out / "poslanici.html").read_text()


def test_a_built_site_loads_nothing_from_other_sites(built, tmp_path):
    out = tmp_path / "_site"
    shutil.copytree(built[0], out)  # pages are added to it below
    assert site.check(out) == []
    (out / "x.html").write_text('<script src="https://cdn.example.com/a.js"></script>')
    (out / "y.css").write_text("@import url('https://fonts.googleapis.com/css2?family=X');")
    (out / "z.html").write_text('<a href="https://www.parlament.gov.rs/">izvor</a>' + "x" * (site.PAGE_LIMIT + 1))
    assert [b.split(":")[0] for b in site.check(out)] == ["x.html", "y.css", "z.html"]


def test_groups_numbers_quiz_and_share_picture(built):
    out = built[0]
    law = (out / "zakon" / "zakon-o-oruzju.html").read_text()
    assert 'og:image" content="https://zailiprotiv.rs/zakon/zakon-o-oruzju.png"' in law
    assert (out / "zakon" / "zakon-o-oruzju.png").read_bytes()[:4] == b"\x89PNG"
    assert "Skupština u brojkama" in (out / "brojke.html").read_text()
    assert (out / "grupe.html").exists() and (out / "glasaj.js").exists()
    quiz = json.loads(re.search(r'id="quiz-data">(.*?)</script>', (out / "kviz" / "podelili-salu.html").read_text(), re.S).group(1))
    assert quiz["laws"] == [{"s": "zakon-o-oruzju"}] and "groups" in quiz and "mps" not in quiz  # groups only (17 Nov 2026)
    area = next((out / "oblast").glob("*.xml")).read_text()
    assert "<feed" in area and "zakon-o-oruzju.html" in area


def test_visitors_votes_are_sent_only_when_an_address_is_set(tmp_path):
    out = tmp_path / "_site"
    root = data(tmp_path)
    site.build(root, out, "zailiprotiv.rs")
    page = (out / "kviz" / "podelili-salu.html").read_text()
    assert "ulaze u zbir" not in page and 'data-api=""' in page and "nikuda se ne šalju" in page
    assert json.loads((out / "glasaj.json").read_text()) == {"laws": ["zakon-o-oruzju"]}
    (root / "settings.json").write_text(json.dumps({"votes_api": "https://glasovi.example/"}))
    site.build(root, out, "zailiprotiv.rs")
    page = (out / "kviz" / "podelili-salu.html").read_text()
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


def test_the_week_in_the_assembly_and_its_feed(built):
    out = built[0]
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
    # As the chair of the Thirteenth said it: the name right after the measure, the first name deciding.
    said = lambda text: {"kind": "opomena", "chair": {"text": text}}
    two = {"СТЕФАН ЈОВАНОВИЋ": "јовановић", "ЖЕЉКО ВЕСЕЛИНОВИЋ": "веселиновић"}
    assert pages_floor.to_whom(said("Због нарушавања реда изричем опомену Стефану Јовановићу."), two) == "СТЕФАН ЈОВАНОВИЋ"
    assert pages_floor.to_whom(said("Изричем опомену Добрици Веселиновићу."), two) is None  # another Veselinović
    assert pages_floor.to_whom(said("Изричем опомену Стефану Јовановићу, Жељку Веселиновићу."), two) is None  # several
    # The case decides: the floor goes to the nominative, the measure to the dative (23 Dec 2022).
    floor_then = said("По Пословнику, народни посланик Миленко Јованов, а народном посланику Новаковићу изричем опомену због недоличног понашања.")
    assert pages_floor.to_whom(floor_then, {"МИЛЕНКО ЈОВАНОВ": "јованов", "БОРИСЛАВ НОВАКОВИЋ": "новаковић"}) == "БОРИСЛАВ НОВАКОВИЋ"
    assert pages_floor.to_whom(floor_then, {"МИЛЕНКО ЈОВАНОВ": "јованов"}) is None  # Novaković said no word that day
    assert pages_floor.to_whom(said("Народни посланик Александар Јовановић, изричем вам опомену."),
                               {"АЛЕКСАНДАР ЈОВАНОВИЋ": "јовановић"}) == "АЛЕКСАНДАР ЈОВАНОВИЋ"  # the nominative alone
    assert pages_floor.measures([say("ПРЕДСЕДНИК", "Нећу да вам изричем сад никакву опомену.", True)]) == []
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
    from zailiprotiv import members, mps, photos
    html = ('<a href="https://www.parlament.gov.rs/NENAD_ABRAMOVI%C4%86.1435.891.html"><a name="x"></a></a>'
            '<img src="/upload/thumbs/images/archive/photo/poslanici/14_saziv/288-Nenad_Abramovic_150x0.jpg">'
            '<a href="/NENAD_ABRAMOVIĆ.1435.891.html">ABRAMOVIĆ NENAD</a><img src="/images/logo.png">')
    found = photos.parse(html)
    assert list(found) == ["1435"] and found["1435"]["src"].endswith("288-Nenad_Abramovic_150x0.jpg")
    assert photos.key(found["1435"]["name"]) == mps.key("АБРАМОВИЋ НЕНАД")
    assert photos.key("DRAGANA ŽIVKOVIĆ - OBRADOVIĆ") == members.key("ЖИВКОВИЋ-ОБРАДОВИЋ ДРАГАНА", "15")  # one surname of two


def test_a_measure_without_a_name_is_placed_by_context_only_when_the_notes_show_whom():
    from zailiprotiv import pages_floor as f
    said = {"speaker": "ПЕТАР ПЕТРОВИЋ", "text": "Ово је срамота.", "day": 1}
    heckle = {"chair": True, "speaker": "ПРЕДСЕДНИК", "day": 1,
              "text": "Молим за мир.\n(Радомир Лазовић: Јавите се за реч!)\nЈел можете да не вичете?\nДакле, изричем вам опомену."}
    m = f.measures([said, heckle])[0]
    assert f.by_context(m)[0] == "Радомир Лазовић"  # the one who interjects, not the speaker before
    at_once = {"chair": True, "speaker": "ПРЕДСЕДНИК", "day": 1, "text": "Хвала. Изричем вам опомену. Настављамо даље."}
    assert f.by_context(f.measures([said, at_once])[0])[0] == "ПЕТАР ПЕТРОВИЋ"
    later = {"chair": True, "speaker": "ПРЕДСЕДНИК", "day": 1,
             "text": "Хвала. Реч има министар. Не, чекајте. Молим за мир у сали. Изричем вам опомену."}
    assert f.by_context(f.measures([said, later])[0]) is None  # too far from the speech to say


def test_a_measure_to_another_one_too_in_the_same_address_is_its_own():
    """19 Nov 2026, the notes: "Изричем вам опомену због овога. … Изричем вам и сад опомену и вама, пришли сте без позива."
    The second was taken for the first told again."""
    from zailiprotiv import measures as f
    mp = {"speaker": "АЛЕКСАНДАР ВУЧИЋ", "text": "Нисте ни испосник као што су вас представљали, али…", "chair": False, "day": 3}
    chair = lambda text: {"speaker": "ПРЕДСЕДНИК", "text": text, "chair": True, "day": 3}
    both = chair("Изричем вам опомену због овога. (Народни посланици добацују с места.) Молим посланицу Ану Брнабић да се врати "
                 "на место. (Ана Брнабић: И кад су ме гађали нисам дала ниједну опомену.) Изричем вам и сад опомену и вама, "
                 "пришли сте без позива. (Ана Брнабић: Још једну ми дај.) Проглашавам паузу од 15 минута.")
    found = f.measures([mp, both])
    assert [m["sentence"][:22] for m in found] == ["Изричем вам опомену зб", "Изричем вам и сад опом"]
    people = f.present([mp, both, {"speaker": "АНА БРНАБИЋ", "text": "Говор.", "chair": False, "day": 3}])
    assert f.by_context(found[1], people)[0].upper() == "АНА БРНАБИЋ" and f.by_context(found[0], people)[0].upper() == "АЛЕКСАНДАР ВУЧИЋ"
    # the chair's own account soon after names both it went to; without it, by context as above
    heckler = {"speaker": "МИЛЕНКО ЈОВАНОВ", "text": "Говор.", "chair": False, "day": 3}
    account = chair("Настављамо седницу. Ја сам дао опомене посланици Ани Брнабић и посланику Миленку Јованову.")
    people = f.present([mp, both, heckler, {"speaker": "АНА БРНАБИЋ", "text": "Говор.", "chair": False, "day": 3}])
    told = f.measures([mp, both, heckler, account])
    assert [f.to_whom(m, people) for m in told[1:]] == ["АНА БРНАБИЋ", "МИЛЕНКО ЈОВАНОВ"] and len(told) == 3
    assert len(f.measures([mp, both, heckler, {**account, "day": 4}])) == 2  # an account of another day is not of this measure
    again = chair("Изричем вам опомену због овога. Молим вас. Изричем вам опомену, рекао сам.")
    assert len(f.measures([mp, again])) == 1  # told again with nobody else in it: one


def test_the_measures_as_the_chairs_said_them_in_every_convocation():
    """23 Nov 2026: every measure in the notes read with its context; the sentences are the notes' own."""
    from zailiprotiv import measures as f
    mp = lambda who, text="Говор.": {"speaker": who, "text": text, "chair": False, "day": 1}
    chair = lambda text: {"speaker": "ПРЕДСЕДНИК", "text": text, "chair": True, "day": 1}

    def found(*speeches, everyone=None):
        people = f.present(list(speeches))
        out = []
        for m in f.measures(list(speeches)):
            to = f.to_whom(m, people, everyone)
            ctx = None if to else f.by_context(m, people)
            out.append((m["kind"], to.upper() if to else None, ctx[0].upper() if ctx else None))
        return out
    op = lambda name: ("opomena", name, None)
    likely = lambda name: ("opomena", None, name)
    # several in one address; a list of names; the same one told again is not another
    assert found(mp("БОШКО ОБРАДОВИЋ"), mp("ИВАН КОСТИЋ"), chair(
        "Дакле, изричем опомену Бошку Обрадовићу, ви сте хтели, Ивану Костићу изричем опомену.")) == [op("БОШКО ОБРАДОВИЋ"), op("ИВАН КОСТИЋ")]
    assert found(mp("АЛЕКСАНДАР ЈОВАНОВИЋ"), mp("БОРИСЛАВ НОВАКОВИЋ"), mp("СРЂАН МИЛИВОЈЕВИЋ"), mp("РАДОМИР ЛАЗОВИЋ"), mp("ЂОРЂО ЂОРЂИЋ"), chair(
        "Изричем опомену Александру Јовановићу, Бориславу Новаковићу, Срђану Миливојевићу. Изричем другу опомену Радомиру Лазовићу.")) == [
        op("АЛЕКСАНДАР ЈОВАНОВИЋ"), op("БОРИСЛАВ НОВАКОВИЋ"), op("СРЂАН МИЛИВОЈЕВИЋ"), op("РАДОМИР ЛАЗОВИЋ")]
    assert found(mp("ГОРДАНА ЧОМИЋ"), chair(
        "Госпођо Чомић, нажалост, изричем вам опомену. Изричем вам опомену, из простог разлога што не поштујете председавајућег.")) == [op("ГОРДАНА ЧОМИЋ")]
    assert found(mp("СЛОБОДАН НИКОЛИЋ"), mp("ДРАГАН НИКОЛИЋ"), mp("СЛОБОДАН НИКОЛИЋ"), chair(
        "Хвала. Изричем вам, господине Николићу, опомену зато што је некоректно. Дакле, тако да имате једну опомену.")) == [op("СЛОБОДАН НИКОЛИЋ")]
    assert found(mp("ГОРАН ЈЕШИЋ"), chair("Изричем вам опомену, колега Јешићу. (Горан Јешић: Ви не знате ништа.) Изричем вам другу опомену.")) == [
        op("ГОРАН ЈЕШИЋ"), likely("ГОРАН ЈЕШИЋ")]
    # other words for it
    assert found(mp("НЕНАД БОЖИЋ"), chair("Колега Божићу, изричем вам опомену. (Ненад Божић: Зашто?) Колега Божићу, друга опомена. (Ненад Божић: Срам те било!) "
                                          "Колега Божићу, трећа опомена.")) == [op("НЕНАД БОЖИЋ")] * 3
    assert found(mp("НЕБОЈША БАКАРЕЦ"), chair("Посланиче Бакарец, морам да вам изрекнем опомену због овог.")) == [op("НЕБОЈША БАКАРЕЦ")]
    # not a measure: a condition, talk, a rule, an earlier one
    for text in ("Добаците још једном и добијате опомену.", "Ако наставите овако, имате опомену.", "Боље да вас упозорим, него да вам сада изричем опомену.",
                 "Без везе је да вас опомињем па да вам на крају одузимам реч.", "Нећу да вам изричем сад никакву опомену.",
                 "Господине Трнавчевићу, ако наставите да довикујете с места, дужна сам да вам изрекнем опомену.",
                 "Пошто сам за меру удаљења са седнице која је изречена Александру Јовановићу на претходној седници рекао да ће да се примењује.",
                 "Председник Народне скупштине изриче меру удаљења са седнице."):
        assert found(mp("ПЕТАР ПЕТРОВИЋ"), chair(text)) == [], text
    assert found(mp("АЛЕКСАНДАР ЈОВАНОВИЋ", "Имам опомену, у реду је. Баш ме брига."), chair("Све је у реду, имате опомену.")) == []
    # someone named is never replaced by whoever spoke before
    assert found(mp("НИКОЛА СЕЛАКОВИЋ", "Идемо даље. (Добрица Веселиновић: Чудо, ви министар културе.) Идемо даље."),
                 chair("Изричем опомену Добрици Веселиновићу. Хвала вам."), mp("НИКОЛА СЕЛАКОВИЋ")) == [op("ДОБРИЦА ВЕСЕЛИНОВИЋ")]
    assert found(mp("АЛЕКСАНДАР ЈОВАНОВИЋ"), mp("АЛЕКСАНДР ЈОВАНОВИЋ"), mp("МИЛОШ ВУЧЕВИЋ"), chair(
        "Хвала вам, председниче Владе. Народном посланику Александру Јовановићу изричем опомену поново.")) == [op("АЛЕКСАНДАР ЈОВАНОВИЋ")]  # misspelt once
    assert found(mp("МИЛОШ ВУЧЕВИЋ"), chair("Хвала вам. Народном посланику Петру Петровићу изричем опомену.")) == [("opomena", None, None)]
    assert found(mp("РАДОМИР ЛАЗОВИЋ"), mp("МИЛЕНКО ЈОВАНОВ"), chair(
        "Господине Лазовићу, да ли можете да прекинете да добацујете? Не можете да прекинете. Ја вама изричем опомену."), mp("МИЛЕНКО ЈОВАНОВ")) == [likely("РАДОМИР ЛАЗОВИЋ")]
    assert found(mp("БОШКО ОБРАДОВИЋ"), mp("НЕБОЈША СТЕФАНОВИЋ"), chair(
        "Молим посланика Бошка Обрадовића да физички не угњетава посланика. Посланиче, имате опомену зато што сте покушали краватом да задавите посланика.")) == [likely("БОШКО ОБРАДОВИЋ")]
    # a warning without a name, and another by name to the one who heckled right before it: the first is someone else's
    assert found(mp("МАРЈАНА МАРАШ"), chair(
        "Јован Палалић. (Бошко Обрадовић: Повреда Пословника.) Изричем вам опомену за ово понашање. Не можете да приђете председавајућем ако вам то није дозволио. "
        "Реч има народни посланик Јован Палалић. (Иван Костић: Повреда Пословника.) (Бошко Обрадовић: Повреда Пословника.) Бошку Обрадовићу изричем опомену.")) == [
        ("opomena", None, None), op("БОШКО ОБРАДОВИЋ")]
    # the notes cut one address in two at a heckle; someone not at the sitting, named in full
    assert found(mp("МАРКО ЂУРИШИЋ"), chair("Изричем вам опомену. (Марко Ђуришић: А ви, господине Бабићу, тапшете овде.)"),
                 chair("Господине Ђуришићу, изричем вам опомену.")) == [op("МАРКО ЂУРИШИЋ")]
    assert found(mp("МИЛОШ ПАРАНДИЛОВИЋ"), chair(
        "Мени не преостаје ништа друго осим да изрекнем меру удаљења са седнице народним посланицима Милошу Парандиловићу и Драгану Нинковићу."),
        everyone={"ДРАГАН НИНКОВИЋ": "нинковић"}) == [("udaljenje", "МИЛОШ ПАРАНДИЛОВИЋ", None), ("udaljenje", "ДРАГАН НИНКОВИЋ", None)]


def test_every_speech_of_the_notes_has_a_place_and_long_days_are_split(monkeypatch):
    from zailiprotiv import notes_site
    monkeypatch.setattr(notes_site, "PART", 30)
    notes = {"sitting": "https://www.parlament.gov.rs/Седница.53893.43.html",
             "speeches": {"00000": {"day": 1, "text": "а" * 10}, "00001": {"day": 1, "text": "б" * 10},
                          "00002": {"day": 1, "text": "в" * 10}, "00003": {"day": 2, "text": "г"}}}
    where = notes_site.layout("14", notes)
    assert where["00000"] == ("14/53893/dan-1.html", "g00000") and where["00001"][0] == "14/53893/dan-1-2.html"
    assert where["00003"][0] == "14/53893/dan-2.html"


def test_only_changed_notes_pages_are_sent(tmp_path):
    from zailiprotiv import notes_site
    (tmp_path / "a.html").write_text("a")
    (tmp_path / "b.html").write_text("b")
    now, send, gone = notes_site.changed(tmp_path, {})
    assert send == ["a.html", "b.html"] and not gone
    (tmp_path / "b.html").write_text("b2")
    (tmp_path / "a.html").unlink()
    assert notes_site.changed(tmp_path, now)[1:] == (["b.html"], ["a.html"])


def test_a_speech_is_linked_among_the_notes_only_when_its_page_is_in_the_bucket():
    import inspect
    from zailiprotiv import pages_floor
    src = inspect.getsource(pages_floor.count)
    assert "notes_pages" in inspect.signature(pages_floor.count).parameters and "v[0] in notes_pages" in src


def test_links_to_the_notes_bucket_keep_their_ending(tmp_path):
    from zailiprotiv import publish
    (tmp_path / "a.html").write_text('<head></head><a href="https://beleske.zailiprotiv.rs/14/1/dan-1.html#g1">x</a>'
                                     '<a href="https://zailiprotiv.rs/b.html">y</a>')
    publish.clean_urls(tmp_path)
    text = (tmp_path / "a.html").read_text()
    assert "beleske.zailiprotiv.rs/14/1/dan-1.html#g1" in text and 'href="https://zailiprotiv.rs/b"' in text


def test_downloads_and_share_pictures_move_out_and_pages_point_at_the_bucket(tmp_path):
    from zailiprotiv import files_site
    site, out = tmp_path / "s", tmp_path / "o"
    for d in ("zakon", "cir/zakon", "podaci", "poslanik"):
        (site / d).mkdir(parents=True)
    for f in ("zakon/a.csv", "zakon/a.json", "zakon/a.png", "podaci/zakoni.csv", "poslanik/m.png", "podaci.json", "za-ili-protiv.png"):
        (site / f).write_text("x")
    (site / "zakon/a.html").write_text('<meta property="og:image" content="https://zailiprotiv.rs/zakon/a.png">'
                                       '<a href="a.csv">c</a><a href="a.html">p</a><a href="https://x.rs/a.csv">o</a>')
    (site / "cir/zakon/a.html").write_text('<a href="../../zakon/a.json">j</a>')
    (site / "podaci.html").write_text('<a href="podaci/zakoni.csv">z</a>')
    n = files_site.split(site, out, "https://podaci.zailiprotiv.rs", "zailiprotiv.rs")
    assert n == {"moved": 5, "pages": 3} and (out / "zakon/a.csv").exists() and not (site / "zakon/a.csv").exists()
    assert (site / "podaci.json").exists() and (site / "za-ili-protiv.png").exists()  # the search's data and the site's own picture stay
    law = (site / "zakon/a.html").read_text()
    assert 'content="https://podaci.zailiprotiv.rs/zakon/a.png"' in law and 'href="https://podaci.zailiprotiv.rs/zakon/a.csv"' in law
    assert 'href="a.html"' in law and 'href="https://x.rs/a.csv"' in law
    assert "https://podaci.zailiprotiv.rs/zakon/a.json" in (site / "cir/zakon/a.html").read_text()
    assert "https://podaci.zailiprotiv.rs/podaci/zakoni.csv" in (site / "podaci.html").read_text()
    assert files_site.plan({"a": "1", "b": "2"}, {"b": "x", "c": "3"}) == (["a", "b"], ["c"])


def test_the_cache_is_not_asked_without_a_zone_or_for_nothing(monkeypatch):
    from zailiprotiv import files_site
    monkeypatch.delenv("CLOUDFLARE_ZONE_ID", raising=False)
    assert files_site.purge("https://podaci.zailiprotiv.rs/", []) == "nothing to purge"
    assert "not purged" in files_site.purge("https://podaci.zailiprotiv.rs/", ["podaci/zakoni.csv"])


def test_talk_about_measures_is_not_a_measure_and_what_was_said_before_one_is_shown():
    from zailiprotiv import pages_floor as f
    chair = lambda t: {"chair": True, "speaker": "ПРЕДСЕДНИК", "day": 1, "text": t}
    for talk in ("Ја нећу да изричем опомене, нисмо деца.", "Шта очекујете од мене - да изричем опомене?",
                 "Ја сам толерантна и не изричем вам опомену, него тражим да поштујете Пословник."):
        assert f.measures([chair(talk)]) == []
    said = {"chair": False, "speaker": "БОШКО ОБРАДОВИЋ", "day": 1, "text": "Први став. СПС 25 година пљачка ову државу. Искључите ме поново."}
    c = chair("Опет говорите да неко пљачка државу. (Бошко Обрадовић: Не директно.) Изричем вам опомену, господине "
              "Обрадовићу, због таквог говора. Зато што сам вас најпре упозорио. Идемо даље.")
    m = f.measures([said, c])[0]
    a = f.around(m, "БОШКО ОБРАДОВИЋ")
    assert a["lead"] == "Опет говорите да неко пљачка државу." and a["after"] == "Зато што сам вас најпре упозорио."
    assert a["asides"] == [("Бошко Обрадовић", "Не директно.")]
    assert "".join(t for t, _ in a["last"]).endswith("Искључите ме поново.") and a["last_who"] == "БОШКО ОБРАДОВИЋ"
    assert f.around(m, "НЕКО ДРУГИ")["last"] == []  # the speech before was not that person's


def test_a_quote_is_found_among_our_notes_pages(tmp_path):
    import json
    from zailiprotiv import notes_site
    d = tmp_path / "14" / "transcripts"; d.mkdir(parents=True)
    notes = {"sitting": "https://www.parlament.gov.rs/x.123.43.html", "days": [{"day": 1, "url": "https://p/a.docx"}],
             "speeches": {"00001": {"day": 1, "speaker": "ПРЕДСЕДНИК", "chair": True, "text": "Реч има Ђорђе Станковић."},
                          "00002": {"day": 1, "speaker": "ЂОРЂЕ СТАНКОВИЋ", "text": "Хвала. Како министар очекује да преживе мале фирме? Питам."}}}
    (d / "s.json").write_text(json.dumps(notes))
    spot = notes_site.Finder(tmp_path, "https://beleske.zailiprotiv.rs")
    assert spot("https://p/a.docx", "Станковић Ђорђе", "Како министар очекује да преживе мале фирме") == "https://beleske.zailiprotiv.rs/14/123/dan-1.html#g00002"
    assert spot("https://p/a.docx", "Неко Други", "речи којих нема") == "https://beleske.zailiprotiv.rs/14/123/dan-1.html"
    assert spot("https://p/other.docx", "Станковић Ђорђе", "Како") == "" and spot.day("https://p/a.docx", "Ђорђе Станковић").endswith("#g00002")
    assert notes_site.Finder(tmp_path, "https://beleske.zailiprotiv.rs", set())("https://p/a.docx", "Станковић Ђорђе", "Како министар") == ""


def test_notes_are_packed_the_same_way_every_time(tmp_path):
    import gzip
    from zailiprotiv import files_site
    f = tmp_path / "a.json"; f.write_text('{"sitting": "x"}')
    assert files_site._packed(f) == files_site._packed(f) and gzip.decompress(files_site._packed(f)) == f.read_bytes()


def test_a_surname_alone_is_the_one_such_speaker_of_the_sitting():
    from zailiprotiv import debates
    sp = lambda name, chair=False: {"speaker": name, "chair": chair}
    assert debates.whole_names([sp("БОШКО ОБРАДОВИЋ"), sp("ОБРАДОВИЋ"), sp("ПРЕДСЕДНИК", True)]) == {"ОБРАДОВИЋ": "БОШКО ОБРАДОВИЋ"}
    assert debates.whole_names([sp("БОШКО ОБРАДОВИЋ"), sp("ЈАСМИНА ОБРАДОВИЋ"), sp("ОБРАДОВИЋ")]) == {}
    assert debates.whole_names([sp("БОШКОВИЋ")]) == {}
    assert debates.whole_names([sp("МАРИНИКА ТЕПИЋ"), sp("МАРИНИКАТЕПИЋ")]) == {"МАРИНИКАТЕПИЋ": "МАРИНИКА ТЕПИЋ"}


def test_a_quotes_name_depends_on_its_words_alone():
    from zailiprotiv.site import qid
    assert qid("Ovaj zakon je dobar.") == qid("Ovaj zakon je dobar.") != qid("Ovaj zakon je loš.")
    assert len(qid("a")) == 10 and qid("a").isalnum()


def test_the_ballots_files_hold_each_law_with_a_letter_per_mp(built):
    out = built[0]
    where = json.loads((out / "listic" / "zakoni.json").read_text())
    conv = where["zakon-o-oruzju"]
    held = json.loads((out / "listic" / f"{conv}.json").read_text())
    law = held["laws"]["zakon-o-oruzju"]
    assert len(law["v"]) == len(held["mps"]) == 3 and set(law["v"]) <= set("zpu-") and len(law["k"]) == 3
    assert law["k"][0] == law["v"].count("z") and len(law["r"]) == 3 and all(0 <= x <= 1 for x in law["r"])
    assert (out / "kviz" / "podelili-salu.html").exists() and "Moj listić" in (out / "glasaj.html").read_text()


def test_place_among_values():
    from zailiprotiv.pages_ballot import below
    assert below([0, 0, 5, 10]) == {0: 0.0, 5: 0.67, 10: 1.0}


def test_the_live_bar_links_the_live_page_while_a_sitting_lasts(tmp_path):
    from zailiprotiv.config import NEWEST
    out, root = tmp_path / "_site", data(tmp_path)
    (root / NEWEST).mkdir()
    (root / NEWEST / "index.json").write_text(json.dumps({"sittings": {"s": {
        "title": "Прва седница Народне скупштине (у току)"}}}))
    site.build(root, out, "zailiprotiv.rs", cyrillic=True)
    assert "Skupština sada zaseda" in (out / "index.html").read_text() and "Ko sada govori" not in (out / "index.html").read_text()
    (root / "settings.json").write_text(json.dumps({"live_page": "https://mikrofon.example/"}))
    site.build(root, out, "zailiprotiv.rs", cyrillic=True)
    home, twin = (out / "index.html").read_text(), (out / "cir" / "index.html").read_text()
    # on the home page the live page's strip stands in the bar's place; the list of sittings keeps the bar
    assert '<a class="mic on" data-pagefind-ignore href="https://mikrofon.example/"' in home
    assert "Uživo · sednica je u toku" in home and "Skupština sada zaseda" not in home
    assert 'href="https://mikrofon.example/cir/"' in twin and "Ко сада говори" in twin
    bar = (out / "sednice.html").read_text()
    assert 'data-cir-href="https://mikrofon.example/cir/" data-mik="traka">Ko sada govori</a>' in bar
    assert '<a class="nav-live on" href="https://mikrofon.example/"' in bar
    assert '<a class="dno-live on" href="https://mikrofon.example/"' in bar  # the phone's bar, red
    assert site.check(out) == []


def test_the_next_sitting_from_the_assemblys_listing_or_a_notice(tmp_path):
    from datetime import datetime
    from zailiprotiv.pages_mikrofon import TZ, next_start
    now = datetime(2026, 11, 22, 3, 0, tzinfo=TZ)
    assert next_start(tmp_path, "15", now) is None
    (tmp_path / "obavestenja.json").write_text(json.dumps([
        {"tekst": "Nastavlja u utorak.", "url": "https://x/", "pocinje": "2026-11-24T10:00"},
        {"tekst": "Bilo je.", "url": "https://x/", "pocinje": "2026-11-19T10:00"}]), encoding="utf-8")
    n = next_start(tmp_path, "15", now)
    assert (n["pocinje"], n["dan"], n["sat"]) == ("2026-11-24T10:00", "utorak, 24. novembar", "10 h")
    at = datetime(2026, 11, 24, 10, 0, tzinfo=TZ).timestamp()
    assert n["u"] == at and n["dan_od"] == at - 10 * 3600 and n["od"] == at - 34 * 3600
    (tmp_path / "15").mkdir()
    (tmp_path / "15" / "index.json").write_text(json.dumps({"sittings": {
        "a": {"title": "Druga sednica", "agenda": ["x"], "starts": "2026-11-23T11:30"},
        "b": {"title": "Ranija", "agenda": ["x"], "starts": "2026-11-23T09:00", "votes": [["x", "y"]]}}}))
    assert next_start(tmp_path, "15", now)["pocinje"] == "2026-11-23T11:30"
    assert next_start(tmp_path, "15", now)["sat"] == "11.30 h"


def test_the_live_page_on_every_page_before_a_sitting(tmp_path):
    out, root = tmp_path / "_site", data(tmp_path)
    (root / "settings.json").write_text(json.dumps({"live_page": "https://mikrofon.example/"}))
    (root / "obavestenja.json").write_text(json.dumps([{"od": "2026-01-01", "do": "2099-12-31", "tekst": "Nastavlja.",
        "url": "https://x/", "pocinje": "2099-11-24T10:00"}]), encoding="utf-8")
    site.build(root, out, "zailiprotiv.rs", cyrillic=True)
    home, laws = (out / "index.html").read_text(), (out / "zakoni.html").read_text()
    assert '<a class="mic" data-pagefind-ignore href="https://mikrofon.example/"' in home
    assert "u 10 h: sednica Skupštine" in home and 'class="live soon"' not in home
    assert '<a class="nav-live" href="https://mikrofon.example/"' in laws and 'data-mik="meni"' in laws
    assert 'data-src="https://mikrofon.example/stanje.js" data-od="' in laws  # asked from its start on
    assert '<a class="dno-live" href="https://mikrofon.example/"' in laws and "<summary>" in laws.split('class="dno"')[1].split("</nav>")[0]
    assert '<p class="live soon" data-pagefind-ignore data-show="' in laws and 'data-mik="najava"' in laws
    assert "Sutra</span>" in laws and "Danas</span>" in laws
    assert "Уживо" in (out / "cir" / "zakoni.html").read_text()
    assert site.check(out) == []


def test_a_speech_in_the_notes_links_to_its_minute_in_the_recording(tmp_path):
    from zailiprotiv import notes_site
    root, out = data(tmp_path), tmp_path / "_beleske"
    t = json.loads((root / "transcripts" / "1.json").read_text())
    t["days"][0]["listed_date"] = "2026-07-10"
    (root / "transcripts" / "1.json").write_text(json.dumps(t))
    notes_site.build(root, out)
    page = next(out.glob("*/*/dan-1.html")).read_text()
    assert "▶ snimak" not in page                       # no record of the day: no link, no guess
    (root / "uzivo").mkdir()
    (root / "uzivo" / "2026-07-10.json").write_text(json.dumps({"dan": "2026-07-10", "pokriveno": [], "govori": [
        {"ime": "Abramović Nenad", "od": 1783670000, "do": 1783670300, "okvira": 9, "video": "vid", "sq_od": 241,
         "sq_do": 300, "segment": 5.0}]}))
    notes_site.build(root, out)
    assert "▶ snimak" not in next(out.glob("*/*/dan-1.html")).read_text()  # not until the links are switched on
    (root / "settings.json").write_text(json.dumps({"recording_links": True}))
    notes_site.build(root, out)
    page = next(out.glob("*/*/dan-1.html")).read_text()
    assert 'href="https://www.youtube.com/watch?v=vid&amp;t=1200s"' in page and "▶ snimak, " in page
    assert page.count("▶ snimak") == 1                  # Abramović's speech only; the minister's is not in the record
    assert "▶ снимак" in next(out.glob("cir/*/*/dan-1.html")).read_text()


def test_the_last_day_read_from_the_recording_is_on_the_mikrofon_page_and_published_for_the_service(tmp_path):
    out, root = tmp_path / "_site", data(tmp_path)
    day = {"dan": "2026-11-17", "izvor": "snimak", "govori": [
        {"ime": "Petrović Petar", "adresa": "", "grupa": "", "uloga": "Lista A", "od": 1794920657, "do": 1794926412,
         "okvira": 1152, "video": "qkm", "snimak": 14527}]}
    (root / "15" / "snimak").mkdir(parents=True)
    (root / "15" / "snimak" / "2026-11-17.json").write_text(json.dumps(day))
    site.build(root, out, "zailiprotiv.rs", cyrillic=True)
    page = (out / "mikrofon.html").read_text()
    assert "Poslednji dan sednice, 17. novembar 2026." in page and "Petar Petrović" in page and "· 96 min" in page
    assert "youtube.com/watch?v=qkm&amp;t=14527s" in page and "Петар Петровић" in (out / "cir" / "mikrofon.html").read_text()
    assert json.loads((out / "mikrofon-dan.json").read_text())["dan"] == "2026-11-17"
    assert set(json.loads((out / "mikrofon-cekanje.json").read_text())) == {"kviz", "cinjenice"}
    day["govori"][0].update(video="", datoteka="https://arhiva.videonet.co.rs/f/zas.mp4", snimak=60)
    (root / "15" / "snimak" / "2026-11-17.json").write_text(json.dumps(day))
    site.build(root, out, "zailiprotiv.rs", cyrillic=True)
    page = (out / "mikrofon.html").read_text()
    assert 'data-file="https://arhiva.videonet.co.rs/f/zas.mp4" data-t="60"' in page and "Pusti snimak dana" in page
    day["datoteke"] = [{"url": "https://arhiva.videonet.co.rs/f/1.mp4", "od": 1794909938, "trajanje": 1102},
                       {"url": "https://arhiva.videonet.co.rs/f/2.mp4", "od": 1794920192, "trajanje": 6938}]
    (root / "15" / "snimak" / "2026-11-17.json").write_text(json.dumps(day))
    site.build(root, out, "zailiprotiv.rs", cyrillic=True)
    page = (out / "mikrofon.html").read_text()
    assert 'class="play" data-file="https://arhiva.videonet.co.rs/f/1.mp4" data-t="0"' in page
    assert "Deo 2 · 13:56–15:52" in page
    assert site.check(out) == []


def test_who_spoke_how_long_a_page_per_day_and_the_convocations_sum(tmp_path):
    out, root = tmp_path / "_site", data(tmp_path)
    start = 1794920000
    day = {"dan": "2026-11-17", "izvor": "snimak", "govori": [
        {"ime": "Petrović Petar", "adresa": "petrovic-petar", "uloga": "Lista A", "od": start, "do": start + 600, "okvira": 120,
         "video": "", "datoteka": "https://arhiva.videonet.co.rs/f/zas.mp4", "snimak": 55},
        {"ime": "Nikolić Nina", "adresa": "", "uloga": "Lista B", "od": start + 700, "do": start + 1000, "okvira": 60,
         "video": "", "snimak": None},
        {"ime": "Jović Jova", "adresa": "", "uloga": "", "od": start + 1100, "do": start + 1100, "okvira": 1}]}
    (root / "15" / "snimak").mkdir(parents=True)
    (root / "15" / "snimak" / "2026-11-17.json").write_text(json.dumps(day))
    site.build(root, out, "zailiprotiv.rs", cyrillic=True)
    page = (out / "govornici" / "2026-11-17.html").read_text()
    assert "Ko je koliko govorio u Skupštini, 17. novembar 2026." in page and "Petar Petrović" in page
    assert "Jova" not in page  # read in one frame: not counted
    assert page.index("Petar Petrović") < page.index("Nina Nikolić") and "66,7 %" in page and "Lista B" in page
    assert f'id="g{start}"' in page and 'data-share="#g' in page and (out / "govornici" / "2026-11-17.png").exists()
    (root / "15" / "prepis").mkdir()
    (root / "15" / "prepis" / "2026-11-17.json").write_text(json.dumps({"model": "medium", "govori": {
        str(start): {"ime": "Petrović Petar", "od": start, "do": start + 600, "tekst": "Поштовани председниче, даме и господо"}}}))
    site.build(root, out, "zailiprotiv.rs", cyrillic=True)
    page = (out / "govornici" / "2026-11-17.html").read_text()
    assert "Automatski prepis" in page and "Poštovani predsedniče" in page and "nije citat" in page
    total = (out / "govornici.html").read_text()
    assert "Ko koliko govori u 15. sazivu" in total and "govornici/2026-11-17.html" in total
    assert "Po danima" in total and "<th>Prosečno</th>" in total
    mp_page = (out / "poslanik" / "petrovic-petar.html").read_text() if (out / "poslanik" / "petrovic-petar.html").exists() else ""
    if mp_page:  # the MP's turns from the recording on the MP's own page, and the way on
        assert "Za govornicom u 15. sazivu" in mp_page and "govornici/2026-11-17.html#g" in mp_page
    assert "Петар Петровић" in (out / "cir" / "govornici" / "2026-11-17.html").read_text()
    assert site.check(out) == []


def test_static_patch_moves_every_page_to_the_new_version(tmp_path, monkeypatch):
    # The pages workflow's fast path: static/ into a site built before, as a full build would have it.
    out = tmp_path / "_site"
    site.build(data(tmp_path), out, "zailiprotiv.rs", cyrillic=True)
    old = site.asset_version()
    (out / "site.js").write_text("stale", encoding="utf-8")
    monkeypatch.setattr(site, "asset_version", lambda: "0123456789")
    got = site.patch_static(out)
    assert got["was"] == old and got["pages"] > 10
    law = (out / "zakon" / "zakon-o-oruzju.html").read_text()
    assert "style.css?v=0123456789" in law and 'data-v="0123456789"' in law and old not in law
    assert (out / "cir" / "zakon" / "zakon-o-oruzju.html").read_text().count("?v=0123456789") >= 2
    assert (out / "site.js").read_text() != "stale" and ' + ".html"' not in (out / "site.js").read_text()


def test_the_bar_shows_while_the_live_page_reads_a_sitting(tmp_path):
    root = data(tmp_path)
    (root / "live.json").write_text('{"live": true}', encoding="utf-8")
    out = tmp_path / "_site"
    site.build(root, out, "zailiprotiv.rs")
    assert "Skupština sada zaseda" in (out / "index.html").read_text()


def test_no_bar_overnight_while_a_sitting_of_several_days_is_still_marked_on(tmp_path):
    from zailiprotiv.config import NEWEST
    out, root = tmp_path / "_site", data(tmp_path)
    (root / NEWEST).mkdir()
    (root / NEWEST / "index.json").write_text(json.dumps({"sittings": {"s": {
        "title": "Прва седница Народне скупштине (у току)"}}}))
    (root / "live.json").write_text('{"live": false}', encoding="utf-8")
    site.build(root, out, "zailiprotiv.rs")
    assert "Skupština sada zaseda" not in (out / "index.html").read_text()


def test_a_new_convocations_members_before_its_first_roll_call(tmp_path):
    from zailiprotiv import members, pages_members
    out, root = tmp_path / "_site", data(tmp_path)
    page = "<table>" + "".join(f"<tr><td>{n}</td><td>{p}</td><td>{pl}</td><td>{y}.</td></tr>" for n, p, pl, y in [
        ("ПЕТРОВИЋ ПЕТАР", "СНС", "Ниш", 1970),
        ("ПАСТОР проф. др БАЛИНТ (PÁSZTOR Prof. Dr BÁLINT)", "-", "Суботица", 1979),
        ("ЖИВКОВИЋ - ОБРАДОВИЋ ДРАГАНА", "-", "Бор", 1964)]) + "</table>"
    found = members.read(page)
    assert [m["name"] for m in found] == ["ПЕТРОВИЋ ПЕТАР", "ПАСТОР проф. др БАЛИНТ", "ЖИВКОВИЋ-ОБРАДОВИЋ ДРАГАНА"]
    assert members.read("<table><tr><td>НОВИ НИКОЛА</td><td>-</td><td>Бор</td><td>2003.</td></tr></table>")[0]["year"] == 2003
    (root / "15").mkdir(exist_ok=True)
    (root / "15" / "members.json").write_text(members.dumps("2026-11-18T10:00:00+00:00", found))
    site.build(root, out, "zailiprotiv.rs", cyrillic=True)
    listing = (out / "poslanici-15.html").read_text()
    assert listing.count('class="row"') == 3 and "konstituisan je 17. novembra 2026." in listing
    assert "Pastor Balint" in listing and "prvi put" in listing and "Suboti" in listing
    new = (out / "poslanik" / "pastor-balint.html").read_text()
    assert 'content="noindex"' in new and "1979.</b><span>godište</span>" in new and "nije navedena" in new
    assert (out / "cir" / "poslanici-15.html").exists() and "poslanici-15.html" in (out / "poslanici.html").read_text()
    # the newest convocation has its tab on the MPs' pages, the menu leads to it, and the groups' page lists its groups
    assert '<a href="poslanici-15.html">2026–<span>Petnaesti saziv</span></a>' in (out / "poslanici.html").read_text()
    assert 'aria-current="page">2026–<span>Petnaesti saziv</span>' in listing and '<a href="poslanici-15.html">Poslanici</a>' in listing
    groups_page = (out / "grupe.html").read_text()
    assert 'id="saziv-15"' in groups_page and "Poslaničke grupe u petnaestom sazivu" in groups_page
    assert 'id="saziv-15"' in (out / "sednice.html").read_text()
    assert any(m["s"] == "pastor-balint" for m in json.loads((out / "podaci.json").read_text())["mps"])
    assert site.check(out) == []
    # A namesake of an earlier MP whose year of birth the archive gives otherwise is another person.
    assert not members.same_person("петар петровић", 1970, {"петар петровић": {1951}})
    assert members.same_person("петар петровић", 1970, {"петар петровић": {1971}})  # a year off: a typo
    assert pages_members.party("-") == "" and pages_members.party(" СНС ") == "СНС"


def test_the_new_convocations_members_by_parliamentary_group(tmp_path):
    from zailiprotiv import members
    out, root = tmp_path / "_site", data(tmp_path)
    form = ('<select name="group"><option value="0">Изаберите посланичку групу</option>'
            '<option value="174">Посланичка група „Студентска листа“</option>'
            '<option value="173">Народни посланици који нису чланови посланичких група</option></select>')
    assert members.groups(form) == [("174", "Посланичка група „Студентска листа“"),
                                    ("173", "Народни посланици који нису чланови посланичких група")]
    assert members.group_url("174").endswith("?submitted=true&group=174")
    found = [{"name": "ПЕТРОВИЋ ПЕТАР", "party": "-", "place": "Ниш", "year": 1970},
             {"name": "ЈОВИЋ ЈОВА", "party": "-", "place": "Бор", "year": 1980},
             {"name": "НИКОЛИЋ НИНА", "party": "СНС", "place": "Бор", "year": 1990},
             {"name": "ЛАЗИЋ ЛАЗА", "party": "-", "place": "Бор", "year": 1985}]
    by = {"Посланичка група „Студентска листа“": [{"name": "ПЕТРОВИЋ ПЕТАР"}, {"name": "ЈОВИЋ ЈОВА"}],
          "Народни посланици који нису чланови посланичких група": [{"name": "НИКОЛИЋ НИНА (NIKOLIĆ NINA)"}]}
    found = members.with_groups(found, by)
    assert [m.get("group") for m in found] == ["Студентска листа", "Студентска листа", "", None]
    (root / "15").mkdir(exist_ok=True)
    (root / "15" / "members.json").write_text(members.dumps("2026-11-18T10:00:00+00:00", found))
    site.build(root, out, "zailiprotiv.rs", cyrillic=True)
    listing = (out / "poslanici-15.html").read_text()
    order = [listing.index(n) for n in ("Jović Jova", "Petrović Petar", "Nikolić Nina", "Lazić Laza")]
    assert order == sorted(order)  # the group first, then those in none, then those no group's page lists
    assert '<option value="Studentska lista">Studentska lista (2)</option>' in listing and "Van poslaničkih grupa" in listing
    assert "Poslanička grupa: <b>Studentska lista</b>" in (out / "poslanik" / "jovic-jova.html").read_text()
    assert "nije član nijedne" in (out / "poslanik" / "nikolic-nina.html").read_text()
    index = {m["s"]: m["g"] for m in json.loads((out / "podaci.json").read_text())["mps"]}
    assert index["jovic-jova"] == "Studentska lista" and index["nikolic-nina"] == ""
    assert site.check(out) == []


def test_a_transcript_is_written_turn_by_turn_and_goes_on_where_it_stopped(tmp_path, monkeypatch):
    from zailiprotiv import prepis
    (tmp_path / "15" / "snimak").mkdir(parents=True)
    day = {"dan": "2026-11-19", "govori": [
        {"ime": "A", "od": 100, "do": 400, "okvira": 60, "datoteka": "https://a/f.mp4", "snimak": 95},
        {"ime": "B", "od": 500, "do": 510, "okvira": 3, "datoteka": "https://a/f.mp4", "snimak": 495},  # too short
        {"ime": "C", "od": 600, "do": 900, "okvira": 60, "datoteka": "https://a/f.mp4", "snimak": 595}]}
    (tmp_path / "15" / "snimak" / "2026-11-19.json").write_text(json.dumps(day))
    cut = []
    monkeypatch.setattr(prepis, "sound", lambda url, start, secs, path: cut.append((start, secs)) or path.write_bytes(b"x" * 2000) or True)
    assert prepis.run(tmp_path, "15", "2026-11-19", transcribe=lambda p: "tekst", minutes=0) == 0  # out of time at once
    assert prepis.run(tmp_path, "15", "2026-11-19", transcribe=lambda p: "tekst") == 2
    kept = json.loads((tmp_path / "15" / "prepis" / "2026-11-19.json").read_text())
    assert set(kept["govori"]) == {"100", "600"} and cut[0] == (95, 300 + prepis.LEAD + prepis.TAIL)
    assert prepis.run(tmp_path, "15", "2026-11-19", transcribe=lambda p: "tekst") == 0


def test_the_time_between_turns_and_quick_exchanges_by_rule():
    from zailiprotiv import pages_govornici as g
    t = lambda name, a, b: {"ime": name, "od": a, "do": b}
    day = [t("A", 0, 100), t("B", 130, 200), t("A", 220, 260), t("B", 300, 320), t("C", 1000, 1500), t("A", 1520, 1600)]
    assert g.between(day) == 30 + 20 + 40 + 20  # the 680 s stretch before C is a break
    quick = g.exchanges(day)
    assert [(x["a"], x["b"], x["n"]) for x in quick] == [("A", "B", 4)]


def test_a_new_convocations_notes_are_counted_before_it_has_a_law(tmp_path, monkeypatch):
    from zailiprotiv import members, pages_floor
    counts = []
    count = pages_floor.count
    monkeypatch.setattr(pages_floor, "count", lambda **kw: counts.append(count(**kw)) or counts[-1])
    out, root = tmp_path / "_site", data(tmp_path)
    page = "<table>" + "".join(f"<tr><td>{n}</td><td>{p}</td><td>{pl}</td><td>{y}.</td></tr>" for n, p, pl, y in [
        ("ПЕТРОВИЋ ПЕТАР", "СНС", "Ниш", 1970), ("НОВАК НОВА", "-", "Бор", 1985)]) + "</table>"
    (root / "15").mkdir(exist_ok=True)
    (root / "15" / "members.json").write_text(members.dumps("2026-11-18T10:00:00+00:00", members.read(page)))
    (root / "15" / "transcripts").mkdir()
    (root / "15" / "transcripts" / "54098.json").write_text(json.dumps({
        "sitting": "https://www.parlament.gov.rs/Прва_седница.54098.43.html", "agenda": {}, "amendments": [],
        "days": [{"day": 1, "url": "https://www.parlament.gov.rs/upload/archive/files/cir/doc/stenografske_beleske/p.docx",
                  "title": "СТЕНОГРАФСКЕ БЕЛЕШКЕ - Прва седница Народне скупштине Републике Србије у Петнаестом сазиву",
                  "date": "17 новембар 2026", "listed_date": "2026-11-17"}],
        "speeches": {"0": {"day": 1, "speaker": "ПРЕДСЕДАВАЈУЋИ", "chair": True, "part": "other", "items": [], "text": "Реч има Нова Новак."},
                     "1": {"day": 1, "speaker": "НОВА НОВАК", "chair": False, "part": "other", "items": [],
                           "text": "Поштовани народни посланици, ово је мој први говор у овом дому."},
                     "2": {"day": 1, "speaker": "ПЕТАР ПЕТРОВИЋ", "chair": False, "part": "other", "items": [],
                           "text": "Реплика. Не слажем се са претходним говорником."}}}))
    site.build(root, out, "zailiprotiv.rs", cyrillic=True)
    counted = counts[0].per_mp  # the new MP's speech is counted and leads to the MP's own page
    assert counted["novak-nova"][0]["conv"] == "15" and counted["novak-nova"][0]["speeches"] == 1
    new = (out / "poslanik" / "novak-nova.html").read_text()
    assert "<b>1</b><span>govor u stenogramima</span>" in new and "15. saziv" in new
    assert site.check(out) == []


def test_letter_sizes_are_the_scale():
    """Every letter size in the stylesheet is a step of the one scale (the --t- variables), so a page does not grow
    twenty sizes again; the menu's and the tabs' letters, sized to fit a phone's row, and an SVG's are the exceptions."""
    from pathlib import Path
    css = (Path(site.__file__).parent / "static" / "style.css").read_text(encoding="utf-8")
    fit = {"clamp(.72rem, 4.3vw, 1rem)", "clamp(.68rem, 3.55vw, .95rem)", "clamp(.68rem, 3.65vw, 1rem)", "clamp(.64rem, 3.05vw, .95rem)", "clamp(.8rem, 3.7vw, .95rem)", "inherit", ".8em", "25px", "28px"}
    sizes = {v.strip() for v in re.findall(r"font-size:\s*([^;}]+)", css)}
    assert {v for v in sizes if not re.fullmatch(r"var\(--t-(\d|h1|d1|d2)\)", v)} <= fit
    assert not re.search(r"font:\s*\d+\s+[\d.]+rem", css)


def test_the_search_page_counts_its_use_and_never_its_words():
    """20 Nov 2026, before a search by meaning is decided: a search run, one with no result, a result opened, each a
    name the counter knows; what is sent is one of those names, never the field's words."""
    import re
    from pathlib import Path
    root = Path(__file__).parents[1]
    js = (root / "src/zailiprotiv/static/pretraga.js").read_text(encoding="utf-8")
    worker = (root / "worker/worker.js").read_text(encoding="utf-8")
    sent = re.findall(r"zipCount\(([^)]*)\)", js)
    assert sent and all(re.fullmatch(r'"pretraga\.[a-z]+"', s) for s in sent)
    events = worker[worker.index("const EVENTS"):worker.index("]);", worker.index("const EVENTS"))]
    for name in {s.strip('"') for s in sent}:
        assert f'"{name}"' in events


def test_every_use_a_page_sends_is_one_the_counter_takes():
    """The site's scripts, the day page's recordings and the live page send only names on the worker's list; a name
    missing there would be refused (400) and never counted."""
    import re
    from pathlib import Path
    root = Path(__file__).parents[1]
    worker = (root / "worker/worker.js").read_text(encoding="utf-8")
    events = set(re.findall(r'"([a-z]+\.[a-z-]+)"', worker[worker.index("const EVENTS"):worker.index("]);", worker.index("const EVENTS"))]))
    sent = set()
    for f in ("src/zailiprotiv/static/site.js", "src/zailiprotiv/static/pretraga.js"):
        sent |= set(re.findall(r'"((?:pretraga|sajt|kviz|listic)\.[a-z-]+)"', (root / f).read_text(encoding="utf-8")))
    sent |= set(re.findall(r'data-e="([^"{]+)"', (root / "src/zailiprotiv/templates/govornici_dan.html").read_text(encoding="utf-8")))
    live = (root / "live/uzivo/static/live.js").read_text(encoding="utf-8")
    sent |= {"mikrofon." + w for w in re.findall(r'use\("([a-z-]+)"\)', live)}
    player = (root / "src/zailiprotiv/templates/mikrofon.js").read_text(encoding="utf-8")
    sent |= set(re.findall(r'count\("([a-z0-9.-]+)"\)', player))
    assert {"pretraga.polje-ceo", "sajt.snimak", "mikrofon.slusaj", "sajt.mikrofon", "mikrofon.obavesti-odbijeno"} <= sent
    assert sent <= events, sent - events


def test_the_chairs_measures_are_paged_and_linked_where_they_stand(tmp_path, monkeypatch):
    """More measures than a page holds: the rest on numbered pages, an MP's page linking each where it stands, the
    table by sitting on the first only (23 Nov 2026: one page of them passed the 1 MB limit and stopped publishing)."""
    from zailiprotiv import pages_floor
    monkeypatch.setattr(pages_floor, "PER_PAGE", 1)
    d = data(tmp_path)
    notes = d / "transcripts" / "1.json"
    store = json.loads(notes.read_text())
    mp = {"day": 1, "speaker": "НЕНАД АБРАМОВИЋ", "chair": False, "part": "general", "items": [1], "text": "један два три"}
    warn = {"day": 1, "speaker": "ПРЕДСЕДНИК", "chair": True, "part": "general", "items": [1],
            "text": "Изричем опомену Ненаду Абрамовићу."}
    store["speeches"] = {"0": mp, "1": warn, "2": mp, "3": {**warn, "text": "Изричем другу опомену Ненаду Абрамовићу."}}
    notes.write_text(json.dumps(store))
    d.rename(tmp_path / "one")
    (tmp_path / "root").mkdir()
    (tmp_path / "one").rename(tmp_path / "root" / "14")
    out = tmp_path / "site"
    site.build(tmp_path / "root", out)
    first, second = ((out / n).read_text(encoding="utf-8") for n in ("replike.html", "replike-s2.html"))
    assert 'id="sednice"' in first and 'id="sednice"' not in second
    for page in (first, second):
        assert 'href="replike.html#deo"' in page and 'href="replike-s2.html#deo"' in page and page.count('class="measure-main"') == 1
    links = re.findall(r'href="\.\./(replike(?:-s2)?\.html)#([^"]+)"', (out / "poslanik" / "abramovic-nenad.html").read_text(encoding="utf-8"))
    assert {p for p, _ in links} == {"replike.html", "replike-s2.html"}
    assert all(f'id="{i}"' in (out / p).read_text(encoding="utf-8") for p, i in links)


def test_a_lighter_page_is_the_same_page():
    """Indentation and the end tags of cells and rows go; a script, a style and what is inside a cell stay as they are."""
    from html.parser import HTMLParser

    from zailiprotiv import publish
    page = """<table class="roll" id="roll">
      <thead><tr><th>Poslanik</th><th>Glas</th></tr></thead>
      <tbody>
        <tr><td><a href="x">A  b</a></td><td class="num"></td></tr>

        <tr><td>c <details><summary>d</summary><ul class="plain"><li>e</li> <li>f</li></ul></details></td> <td>g</td></tr>
      </tbody>
    </table>
    <script>
      var a = "</td> <td>";
    </script>
    <p>h
       i</p>"""
    out = publish.lighter(page)
    assert "</td> <td>\";\n    </script>" in out and "<li>e</li> <li>f</li>" in out
    assert "</tr>" not in out and out.count("</td>") == 1  # only the one inside the script

    class Cells(HTMLParser):
        """The rows as the HTML standard reads them: a cell ends where the next begins."""
        def __init__(self):
            super().__init__()
            self.rows, self.raw = [], False

        def handle_starttag(self, tag, attrs):
            if tag == "tr":
                self.rows.append([])
            elif tag in ("td", "th"):
                self.rows[-1].append([dict(attrs), ""])
            self.raw = tag == "script"

        def handle_endtag(self, tag):
            self.raw = False

        def handle_data(self, data):
            if self.rows and self.rows[-1] and not self.raw and "h\n" not in data:
                self.rows[-1][-1][1] += data

    def cells(text):
        p = Cells()
        p.feed(text.split("</table>")[0])
        return [[(a, " ".join(t.split())) for a, t in r] for r in p.rows]
    assert cells(out) == cells(page) and len(cells(out)) == 3
    assert publish.lighter(out) == out  # the fast path of "pages" lightens nothing twice


def test_the_chamber_is_a_group_a_vote_with_every_seat_in_its_place():
    from zailiprotiv import site
    counts = {"za": 144, "protiv": 38}
    got = site.chamber_groups(counts)
    assert [(k, len(run)) for k, run in got] == [("za", 144), ("ostali", 68), ("protiv", 38)]
    assert [(float(x), float(y), k) for k, run in got for x, y in run] == site.hemicycle(counts)
    assert [k for k, _ in site.chamber_groups({"za": 250})] == ["za"]


def test_a_change_of_markup_alone_tells_the_search_engines_nothing(tmp_path, monkeypatch):
    import json
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
    import indexnow
    site_, store, listing = tmp_path / "s", tmp_path / "c.json", tmp_path / "l.txt"
    site_.mkdir()
    urls = ["https://zailiprotiv.rs/a", "https://zailiprotiv.rs/b"]
    sitemap = '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join(f"<url><loc>{u}</loc></url>" for u in urls) + "</urlset>"

    def run(a, b):
        (site_ / "sitemap.xml").write_text(sitemap, encoding="utf-8")
        (site_ / "a.html").write_text(f"<main>{a}</main>", encoding="utf-8")
        (site_ / "b.html").write_text(f"<main>{b}</main>", encoding="utf-8")
        monkeypatch.setattr(sys, "argv", ["indexnow", "list", str(site_), str(store), str(listing)])
        indexnow.main()
        return listing.read_text(encoding="utf-8").split()
    store.write_text(json.dumps({u: ["hash of the markup", "2026-11-01"] for u in urls}), encoding="utf-8")
    assert run("<p>x</p>", "y") == []  # another way of making the hash: the days stay
    assert (site_ / "sitemap.xml").read_text(encoding="utf-8").count("<lastmod>2026-11-01</lastmod>") == 2
    assert run("<p>\n  x", "y") == []
    assert run("x", "z") == [urls[1]]
    assert run('<a href="q">x</a>', "z") == [urls[0]]


def test_the_support_pages_uses_are_known_to_the_counter_and_say_nothing_of_who():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    js = (root / "src/zailiprotiv/static/site.js").read_text(encoding="utf-8")
    worker = (root / "worker/worker.js").read_text(encoding="utf-8")
    sent = set(re.findall(r'"(podrzi\.[a-z-]+)"', js))
    assert sent and sent == set(re.findall(r'"(podrzi\.[a-z-]+)"', worker))  # a name the counter doesn't know is refused
    for f, where in (("base.html", ("meni", "podnozje")), ("index.html", ("pocetna",))):
        html = (root / "src/zailiprotiv/templates" / f).read_text(encoding="utf-8")
        assert all(f'data-don="{w}"' in html for w in where)
    mail = (root / "live/uzivo/mejl.py").read_text(encoding="utf-8")
    assert 'SUPPORT = "podrzi"' in mail  # the same address for every reader: the privacy page says no link is tracked
