# Counter of visitors' votes ("Glasaj i ti")

A Cloudflare Worker with a D1 table of three numbers per law. It stores no cookies, addresses or times. The site
shows the totals only when `data/settings.json` names the worker's address; until then the page works as before.

## Set-up (once, by the maintainer; a free Cloudflare account is enough)

1. `npm install -g wrangler` and `wrangler login`
2. `cd worker && wrangler d1 create zailiprotiv-glasovi` — paste the `database_id` it prints into `wrangler.toml`
3. `wrangler d1 execute zailiprotiv-glasovi --remote --file schema.sql`
4. `wrangler deploy` — it prints the address, e.g. `https://zailiprotiv-glasovi.<account>.workers.dev`
5. Put that address in `data/settings.json`: `{"votes_api": "https://…workers.dev"}` and push.

To reset the count: `wrangler d1 execute zailiprotiv-glasovi --remote --command "DELETE FROM votes"`.
