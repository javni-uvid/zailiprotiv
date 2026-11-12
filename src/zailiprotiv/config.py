"""Where the Assembly publishes, and how the project introduces itself when it asks."""

BASE = "https://www.parlament.gov.rs"
# The Assembly publishes each roll-call vote as a PDF under this path (by year, sometimes by sitting).
VOTES_PATH = "/upload/rezultati_glasanja/"
USER_AGENT = "zailiprotiv/0.1 (+https://github.com/javni-uvid/zailiprotiv)"
# Seconds between requests to the Assembly's site.
DELAY = 1.0
