# Counter of visitors' votes ("Glasaj i ti") and the clock

A Cloudflare Worker with a D1 database (`schema.sql`). It stores no cookies or addresses. The site
shows the totals only when `data/settings.json` names the worker's address.

It is also the project's clock: GitHub's own schedule didn't start the workflows (13 Nov 2026), so the worker starts
the **votes** workflow every hour of the working day and **summaries** every six hours (`[triggers]` in
`wrangler.toml`), through GitHub's API with the secret `DISPATCH_TOKEN`.

## Publishing

The **worker** workflow publishes it whenever `worker/` changes. Repository secrets it needs:

- `CLOUDFLARE_API_TOKEN`: a Cloudflare API token from the template "Edit Cloudflare Workers", plus Account → D1 → Edit;
- `CLOUDFLARE_ACCOUNT_ID`;
- `DISPATCH_TOKEN`: a fine-grained GitHub token for javni-uvid/zailiprotiv only, with Actions: Read and write.

To reset the count: in Cloudflare, D1 → `zailiprotiv-glasovi` → Console: `DELETE FROM votes`.

The totals read `tally` (sums per law and vote that triggers on `ballots` keep), not `ballots` itself: the free D1
reads 5 million rows a day, and counting every ballot on every quiz page and every vote sent reached 98% of that on
18 Nov 2026. `GET /` is cached at Cloudflare's edge for a minute, and each copy of the worker keeps the totals a minute,
reading again only the laws just voted on. Should `tally` ever disagree with `ballots`, rebuild it:

    wrangler d1 execute zailiprotiv-glasovi --remote --command "DELETE FROM tally; INSERT INTO tally (item, vote, n) SELECT item, vote, COUNT(*) FROM ballots GROUP BY item, vote"

## Votes on a law's page

`POST /z {d, item, v}` is one device's vote on one law (a later one replaces it); `POST /c {d, item, q, on}` marks
or unmarks a quote as convincing; `GET /z/<law>` gives the law's totals and the marks on its quotes. `d` is a random
mark the browser makes up and keeps; the counter stores only its hash with the secret `SALT`, the day, and a hash of
the network (the address's /24 or /64, the day and `SALT`), which changes daily and holds no address. What may be
voted on is read from the site's `glasanje.json`. The quiz's old sums stay in `votes` and are added to the totals.

## Uses of the quiz and the ballot

`POST /e {e}` adds one to a sum per day for one of a fixed list of uses: `kviz.kraj` (the quiz's result reached), and
for the quiz's picture (`kviz.`) and the ballot's (`listic.`): `otvori` (the ballot's picture opened), `podeli` (the
share button), `podeljeno` (the share sheet finished), `kopiraj`, `sacuvaj`; and `mikrofon.pusti` (the live
page's ▶ on the broadcast pressed; the one use taken from `https://mikrofon.zailiprotiv.rs`, which may send only
`mikrofon.` uses). Nothing else is stored with it, not even
the device's mark. `GET /pregled` lists them under `uses`, by day, for the last two weeks. Each page sends each use at
most once.

## Inflated counts

There is no robot check. The `watch` workflow reads `GET /pregled` four times a day and opens an issue when one
network sends most of a law's votes of the day. To look closer, and to remove (the maintainer's decision; say so on
the method page when it is done):

    wrangler d1 execute zailiprotiv-glasovi --remote --command "SELECT net, vote, COUNT(*) FROM ballots WHERE item='<law>' AND day='<day>' GROUP BY net, vote ORDER BY 3 DESC LIMIT 20"
    wrangler d1 execute zailiprotiv-glasovi --remote --command "DELETE FROM ballots WHERE item='<law>' AND day='<day>' AND net='<net>'"

If this happens often, the next step is Cloudflare Turnstile on `POST /z` (free; adds a script from Cloudflare).
