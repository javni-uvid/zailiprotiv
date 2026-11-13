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
    "11": {"from": "2016-06-03", "to": "2020-08-03", "ordinal": "jedanaest",
           "archive": BASE + "/aktivnosti/narodna-skupstina/arhiva-aktivnosti/saziv-od-3-juna-2016/zasedanja.4184.html",
           "laws": BASE + "/akti/doneti-zakoni/u-sazivu-od-3-juna-2016.4242.html"},
    # The address of this page of laws has a Cyrillic "а" in "аprila": as the Assembly links it.
    "10": {"from": "2014-04-16", "to": "2016-06-03", "ordinal": "deset",
           "archive": BASE + "/aktivnosti/narodna-skupstina/arhiva-aktivnosti/saziv-od-16-aprila-2014/zasedanja.3458.html",
           "laws": BASE + "/akti/doneti-zakoni/u-sazivu-od-16-аprila-2014.3411.html"},
    "9": {"from": "2012-05-31", "to": "2014-04-16", "ordinal": "devet",
          "archive": BASE + "/aktivnosti/narodna-skupstina/arhiva-aktivnosti/saziv-od-31-maja-2012/zasedanja.2269.html",
          "laws": BASE + "/akti/doneti-zakoni/u-sazivu-od-31-maja-2012.2194.html"},
}
CURRENT = "14"
ORDINALS = ("devet", "deset", "jedanaest", "dvanaest", "trinaest", "četrnaest", "petnaest", "šesnaest")
