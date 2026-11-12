"""Where the Assembly publishes, and how the project introduces itself when it asks."""

BASE = "https://www.parlament.gov.rs"
# The Assembly publishes each roll-call vote as a PDF under one of these paths: the first since autumn 2025 (by
# year, sometimes by sitting), the second before ("листинзи", by year).
VOTES_PATHS = ("/upload/rezultati_glasanja/", "/upload/archive/files/cir/doc/Listinzi/")
USER_AGENT = "zailiprotiv/0.1 (+https://github.com/javni-uvid/zailiprotiv)"
# Seconds between requests to the Assembly's site.
DELAY = 1.0
