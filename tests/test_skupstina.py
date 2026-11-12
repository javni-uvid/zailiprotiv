from zailiprotiv import skupstina
from zailiprotiv.translit import latin

BASE = "https://www.parlament.gov.rs"

# The shapes of the Assembly's pages, cut down: a listing of sittings with news in its margin, and a sitting whose
# agenda items link to their roll calls (one item with a sub-vote, one link to the same PDF twice).
LISTING = """<html><body>
<a href="/Седмо_ванредно_заседање_Народне.53524.43.html">Седмо ванредно заседање Народне скупштине</a>
<a href="/Трећа_седница_Првог_редовног.53241.43.html">Трећа седница Првог редовног заседања</a>
<a href="/Брнабић_на_самиту.54089.43.html">Брнабић на самиту Европске политичке заједнице</a>
<a href="/Sedmo_vanredno.53525.941.html">Sedmo vanredno zasedanje</a>
</body></html>"""

SITTING = """<html><body><ul>
<li><a href="https://www.parlament.gov.rs/upload/rezultati_glasanja/2026/1.pdf">Предлог закона о јавном
  тужилаштву, који је поднела Влада;</a></li>
<li><a href="/upload/rezultati_glasanja/2026/29.11.pdf">Предлог да се за члана Већа изабере</a></li>
<li><a href="/upload/rezultati_glasanja/2026/1.pdf">Предлог закона о јавном тужилаштву</a></li>
<li><a href="/upload/archive/files/lat/doc/stenografske_beleske/beleske.docx">Стенографске белешке</a></li>
</ul></body></html>"""


def test_sittings_from_listings_without_news():
    pages = {BASE + "/list": LISTING}
    found = skupstina.sittings(get=lambda u: pages[u].encode(), listings=[BASE + "/list", BASE + "/list"])
    assert [s.url for s in found] == [
        BASE + "/Седмо_ванредно_заседање_Народне.53524.43.html",
        BASE + "/Трећа_седница_Првог_редовног.53241.43.html",
    ]
    assert found[0].title == "Седмо ванредно заседање Народне скупштине"


def test_votes_on_a_sitting():
    found = skupstina.votes(SITTING, BASE + "/Седмо.53524.43.html")
    assert [(v.item, v.pdf) for v in found] == [
        ("Предлог закона о јавном тужилаштву, који је поднела Влада",
         BASE + "/upload/rezultati_glasanja/2026/1.pdf"),
        ("Предлог да се за члана Већа изабере", BASE + "/upload/rezultati_glasanja/2026/29.11.pdf"),
    ]


def test_index_reads_each_sitting():
    pages = {skupstina.LISTINGS[0]: LISTING, skupstina.LISTINGS[1]: "<p></p>",
             BASE + "/Седмо_ванредно_заседање_Народне.53524.43.html": SITTING,
             BASE + "/Трећа_седница_Првог_редовног.53241.43.html": "<p>no votes yet</p>"}
    found = skupstina.index(get=lambda u: pages[u].encode(), delay=0)
    assert [len(s.votes) for s in found] == [2, 0]


def test_vote_pdfs():
    assert skupstina.is_vote_pdf(BASE + "/upload/rezultati_glasanja/2026/20.pdf")
    assert skupstina.is_vote_pdf(BASE + "/upload/rezultati_glasanja/2026/osma_sednica/3.PDF")
    assert not skupstina.is_vote_pdf(BASE + "/upload/archive/files/lat/doc/x.docx")


def test_cyrillic_paths_are_encoded_once():
    url = BASE + "/народна-скупштина/седнице.html?x=1"
    assert skupstina.ascii_url(url) == \
        BASE + "/%D0%BD%D0%B0%D1%80%D0%BE%D0%B4%D0%BD%D0%B0-" \
        "%D1%81%D0%BA%D1%83%D0%BF%D1%88%D1%82%D0%B8%D0%BD%D0%B0/%D1%81%D0%B5%D0%B4%D0%BD%D0%B8%D1%86%D0%B5.html?x=1"
    assert skupstina.ascii_url(skupstina.ascii_url(url)) == skupstina.ascii_url(url)
    assert skupstina.ascii_url(BASE + "/upload/a%20b.pdf") == BASE + "/upload/a%20b.pdf"


def test_translit():
    assert latin("Гласали за") == "Glasali za"
