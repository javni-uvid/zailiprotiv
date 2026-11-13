# Counter of visitors' votes ("Glasaj i ti") and the clock

A Cloudflare Worker with a D1 table of three numbers per law. It stores no cookies, addresses or times. The site
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
