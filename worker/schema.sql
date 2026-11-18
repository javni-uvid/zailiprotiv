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
CREATE TRIGGER IF NOT EXISTS ballots_out AFTER DELETE ON ballots BEGIN UPDATE tally SET n = n - 1 WHERE item = old.item AND vote = old.vote; END;
