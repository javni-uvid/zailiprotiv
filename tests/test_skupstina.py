from zailiprotiv import skupstina
from zailiprotiv.translit import latin

PAGE = """<html><body>
<a href="/lat/aktivnosti/sednice.html">Седнице</a>
<a href="https://www.parlament.gov.rs/upload/rezultati_glasanja/2026/20.pdf">Резултати гласања</a>
<a href="/upload/rezultati_glasanja/2026/osma_sednica/1.pdf#page=1">1</a>
<a href="/upload/archive/files/lat/doc/beleske.docx">белешке</a>
<a href="https://example.com/other">elsewhere</a>
<a href="mailto:info@example.com">mail</a>
<a href="/o-skupstini.html">О Скупштини</a>
</body></html>"""


def test_links_are_absolute_without_fragments():
    found = skupstina.links(PAGE, "https://www.parlament.gov.rs/lat/")
    urls = [u for u, _ in found]
    assert "https://www.parlament.gov.rs/upload/rezultati_glasanja/2026/osma_sednica/1.pdf" in urls
    assert not any(u.startswith("mailto:") for u in urls)
    assert ("https://www.parlament.gov.rs/lat/aktivnosti/sednice.html", "Седнице") in found


def test_vote_pdfs():
    assert skupstina.is_vote_pdf("https://www.parlament.gov.rs/upload/rezultati_glasanja/2026/20.pdf")
    assert skupstina.is_vote_pdf("https://www.parlament.gov.rs/upload/rezultati_glasanja/2026/osma_sednica/3.PDF")
    assert not skupstina.is_vote_pdf("https://www.parlament.gov.rs/upload/archive/files/lat/doc/x.docx")
    assert not skupstina.is_vote_pdf("https://www.parlament.gov.rs/upload/rezultati_glasanja/")


def test_crawl_follows_leads_and_stays_on_site():
    site = {
        "https://www.parlament.gov.rs/": PAGE,
        "https://www.parlament.gov.rs/lat/aktivnosti/sednice.html":
            '<a href="/upload/rezultati_glasanja/2025/7.pdf">7</a>',
        "https://www.parlament.gov.rs/o-skupstini.html": "<p>nothing</p>",
    }
    asked = []

    def get(url):
        asked.append(url)
        if url not in site:
            raise skupstina.FetchError(url)
        return site[url].encode()

    result = skupstina.crawl("https://www.parlament.gov.rs/", max_pages=10, delay=0, get=get)
    assert set(result.pdfs) == {
        "https://www.parlament.gov.rs/upload/rezultati_glasanja/2026/20.pdf",
        "https://www.parlament.gov.rs/upload/rezultati_glasanja/2026/osma_sednica/1.pdf",
        "https://www.parlament.gov.rs/upload/rezultati_glasanja/2025/7.pdf",
    }
    # the page about sittings is read before the one about the Assembly; nothing off the site, no documents
    assert asked.index("https://www.parlament.gov.rs/lat/aktivnosti/sednice.html") < \
        asked.index("https://www.parlament.gov.rs/o-skupstini.html")
    assert not any("example.com" in u or u.endswith(".docx") for u in asked)


def test_archive_comes_last():
    current = skupstina._score("https://www.parlament.gov.rs/активности/народна-скупштина/заседања/ванредна.35.html", "")
    archive = skupstina._score(
        "https://www.parlament.gov.rs/активности/народна-скупштина/архива-активности/сазив-од-3-августа-2020/заседања.html",
        "Седнице")
    assert current > archive


def test_cyrillic_paths_are_encoded_once():
    url = "https://www.parlament.gov.rs/народна-скупштина/седнице.html?x=1"
    assert skupstina.ascii_url(url) == \
        "https://www.parlament.gov.rs/%D0%BD%D0%B0%D1%80%D0%BE%D0%B4%D0%BD%D0%B0-" \
        "%D1%81%D0%BA%D1%83%D0%BF%D1%88%D1%82%D0%B8%D0%BD%D0%B0/%D1%81%D0%B5%D0%B4%D0%BD%D0%B8%D1%86%D0%B5.html?x=1"
    assert skupstina.ascii_url(skupstina.ascii_url(url)) == skupstina.ascii_url(url)
    assert skupstina.ascii_url("https://www.parlament.gov.rs/upload/a%20b.pdf") == \
        "https://www.parlament.gov.rs/upload/a%20b.pdf"


def test_translit():
    assert latin("Гласали за") == "Glasali za"
