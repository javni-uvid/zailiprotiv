CREATE TABLE IF NOT EXISTS votes (law TEXT NOT NULL, vote TEXT NOT NULL, n INTEGER NOT NULL, PRIMARY KEY (law, vote));
CREATE TABLE IF NOT EXISTS ballots (item TEXT NOT NULL, device TEXT NOT NULL, vote TEXT NOT NULL, day TEXT NOT NULL, net TEXT NOT NULL, PRIMARY KEY (item, device));
CREATE INDEX IF NOT EXISTS ballots_day ON ballots (day, item, net);
CREATE TABLE IF NOT EXISTS events (day TEXT NOT NULL, what TEXT NOT NULL, n INTEGER NOT NULL, PRIMARY KEY (day, what));
CREATE TABLE IF NOT EXISTS marks (item TEXT NOT NULL, quote TEXT NOT NULL, device TEXT NOT NULL, day TEXT NOT NULL, PRIMARY KEY (item, quote, device));
-- The sums of `ballots` per law and vote, kept by the triggers below, so that the totals read a few rows per law
-- and not every ballot (the free D1 reads 5 million rows a day; the full count reached 98% of that on 18 Nov 2026).
-- Filled once from `ballots` before the triggers exist; on later runs the INSERT OR IGNORE changes nothing.
CREATE TABLE IF NOT EXISTS tally (item TEXT NOT NULL, vote TEXT NOT NULL, n INTEGER NOT NULL, PRIMARY KEY (item, vote));
INSERT OR IGNORE INTO tally (item, vote, n) SELECT item, vote, COUNT(*) FROM ballots GROUP BY item, vote;
CREATE TRIGGER IF NOT EXISTS ballots_in AFTER INSERT ON ballots BEGIN INSERT INTO tally (item, vote, n) VALUES (new.item, new.vote, 1) ON CONFLICT (item, vote) DO UPDATE SET n = n + 1; END;
CREATE TRIGGER IF NOT EXISTS ballots_up AFTER UPDATE OF vote ON ballots WHEN old.vote <> new.vote BEGIN UPDATE tally SET n = n - 1 WHERE item = old.item AND vote = old.vote; INSERT INTO tally (item, vote, n) VALUES (new.item, new.vote, 1) ON CONFLICT (item, vote) DO UPDATE SET n = n + 1; END;
-- Notifications from the live page (20 Nov 2026): the address a browser's push service gave for one device (nothing
-- else about it), the page's script, the day it was asked for; and the days a notification went out, once each.
CREATE TABLE IF NOT EXISTS push (endpoint TEXT PRIMARY KEY, cir INTEGER NOT NULL, day TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS push_days (day TEXT PRIMARY KEY, sent INTEGER NOT NULL DEFAULT 0, gone INTEGER NOT NULL DEFAULT 0);
-- The maintainer's devices, told when "Ko sada govori" is down while a sitting is on (20 Nov 2026), and the watch's
-- own few values (the outage under way, the Assembly's last answer, what was last sent), as JSON by name.
CREATE TABLE IF NOT EXISTS push_admin (endpoint TEXT PRIMARY KEY, day TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS watch (k TEXT PRIMARY KEY, v TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS ballots_out AFTER DELETE ON ballots BEGIN UPDATE tally SET n = n - 1 WHERE item = old.item AND vote = old.vote; END;
-- The day's summary by mail (23 Nov 2026; worker/mejl.js): the address sealed for the maintainer's key (this worker
-- can't read it), a hash of it with SALT to find it again, the script, when asked and confirmed, the hash of the
-- confirmation's code and the day that mail went. Unconfirmed rows go after 48 hours.
CREATE TABLE IF NOT EXISTS mejl (id TEXT PRIMARY KEY, kljuc TEXT NOT NULL UNIQUE, adresa TEXT NOT NULL, cir INTEGER NOT NULL,
  prijava TEXT NOT NULL, potvrda TEXT, kod TEXT, poslato TEXT);
CREATE INDEX IF NOT EXISTS mejl_kod ON mejl (kod);
