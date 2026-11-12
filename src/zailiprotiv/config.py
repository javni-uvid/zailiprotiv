"""Where the Assembly publishes, and how the project introduces itself when it asks."""

BASE = "https://www.parlament.gov.rs"
# The Assembly publishes each roll-call vote as a PDF under one of these paths: the first since autumn 2025 (by
# year, sometimes by sitting), the second before ("листинзи", by year).
VOTES_PATHS = ("/upload/rezultati_glasanja/", "/upload/archive/files/cir/doc/Listinzi/")
USER_AGENT = "zailiprotiv/0.1 (+https://github.com/javni-uvid/zailiprotiv)"
# Seconds between requests to the Assembly's site.
DELAY = 1.0

# The convocations the site covers. The current one's sittings are listed on two Cyrillic pages; an earlier one's
# on its archive page in Latin, whose sittings' Cyrillic pages (the ones linking roll calls) have the next lower
# number. Each has its page of adopted laws. Ordinals name a convocation in sitting titles ("у Тринаестом сазиву").
CONVOCATIONS = {
    "14": {"from": "2024-02-06", "ordinal": "četrnaest",
           "listings": (BASE + "/активности/народна-скупштина/заседања/редовна.34.html",
                        BASE + "/активности/народна-скупштина/заседања/ванредна.35.html"),
           "laws": BASE + "/akti/doneti-zakoni/doneti-zakoni.1033.html"},
    "13": {"from": "2022-08-01", "to": "2024-02-06", "ordinal": "trinaest",
           "archive": BASE + "/aktivnosti/narodna-skupstina/arhiva-aktivnosti/saziv-od-1-avgusta-2022/zasedanja.4921.html",
           "laws": BASE + "/akti/doneti-zakoni/u-sazivu-od-1-avgusta-2022.4962.html"},
    "12": {"from": "2020-08-03", "to": "2022-08-01", "ordinal": "dvanaest",
           "archive": BASE + "/aktivnosti/narodna-skupstina/arhiva-aktivnosti/saziv-od-3-avgusta-2020-godine/zasedanja.4620.html",
           "laws": BASE + "/akti/doneti-zakoni/u-sazivu-od-3-avgusta-2020.4686.html"},
}
CURRENT = "14"
ORDINALS = ("dvanaest", "trinaest", "četrnaest", "petnaest", "šesnaest")
