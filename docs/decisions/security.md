# Security

What each part of the project is guarded against, what is checked before a merge, and what is accepted as it is.
From the review of 20 Nov 2026 (the maintainer's request, after CodeQL's first 13 findings); measured against
OpenSSF Scorecard's checks, GitHub's hardening guide for Actions, OWASP's secure headers and the CIS Docker
benchmark. The rules for workflows are in AGENTS.md ("Workflows, safely"); the live service's own decisions in
`live-service.md`.

## What there is to guard

The site is static and public, with no accounts and nothing private about a visitor. What could be harmed:

- **What the pages say.** A changed vote, quote or name is the worst that can happen to this project. The pages
  are built from `main` only, so the guard is `main`: who can push to it, and what the workflows that push to it
  read.
- **The secrets:** Cloudflare's token and the R2 keys (the site's zone, the downloads, the workers), the model's
  key (paid for by use), the notifications' signing key and token, the Search Console key (reads only), the token
  with which the counter starts workflows. In GitHub Secrets and Cloudflare, and the live service's in `live/.env`
  on the maintainer's computer; never in the repository, a pull request, a log or a chat.
- **The maintainer's computer,** where the live service runs and reads video from outside.
- **The visitors' counter:** sums that could be inflated, and the push addresses of those who asked for
  notifications.

## By part

- **The site's pages (`src/`).** Everything from outside (the Assembly's texts, MPs' words, a model's summary) is
  text and never markup: the templates escape by themselves, `Markup` is given only text already escaped, and
  JSON inside `<script>` has its `</` broken. The scripts set text with `textContent` and build addresses only
  from a slug; `publish.check` fails the build when a page loads anything from another site.
- **The workflows.** As "Workflows, safely" says, and besides: a tool installed in a job is named by version
  (`uv==…`, `pagefind@…`, the packages beside a secret in **visits**), moved by hand when there is a reason;
  repository-wide the workflows' own token only reads, and a job asks for more by name.
  The repository's settings hold the same (20 Nov 2026): only GitHub's own actions and
  `cloudflare/wrangler-action` may run, and only named by commit, so a workflow that names another action or a
  tag doesn't start. A new action is first allowed there (Settings → Actions → General), by the maintainer or
  an agent with their rights, and said in the pull request.
  **pregled** (27 Nov 2026, the conductor) builds a branch that is not merged: started by hand only, with a branch
  name of this repository (checked to be a name, never a ref or a fork's pull request, and checked out as
  `refs/heads/<name>`), its job may only read the repository, has no secret and keeps no token, and its inputs reach the
  scripts through `env` only; it publishes nothing and keeps the pages asked for three days. What a branch's code does
  in it can reach nothing but that job's own runner.
- **The live service (`live/`).** Behind Cloudflare's tunnel with no port open to the network; not root, no
  capabilities, images and packages named by content (`live-service.md`). Two containers (25 Nov 2026): what reads video
  from outside (ffmpeg, yt-dlp, tesseract) has neither the key of the readers' addresses nor the maintainer's own address; what
  answers the internet has those, and neither the model's key nor the bucket's, reads the kept files and writes only what
  went by mail. Both have the counter's token and the key of the maintainer's pages. What a request names never becomes a
  path or markup. The maintainer's pages are opened by a key of 12 characters or more, compared in constant time.
- **The counter (`worker/`).** Takes a vote only from the site's own pages (the `Origin`), for items it knows,
  within a rate limit per address; the tokens are compared in constant time; it answers other sites' scripts
  with nothing (CORS names the site only).
- **Agents.** They work with the maintainer's own rights on GitHub, so what they read from outside (a page of the
  Assembly's, a web page for a note, an issue's text) is material and never an instruction; a secret is never
  asked for or pasted; `main` is reached only through a pull request whose **test** passed.

## Checked before a merge

**test** and **security** run on every pull request (security on those touching code or workflows): actionlint
and zizmor on the workflows, pip-audit on `uv.lock` and `live/constraints.txt`, CodeQL on the Python, the
scripts and the workflows. A finding of CodeQL's on `main` is closed in the code where the code can be made
safe on its own, and dismissed with its reason written only when it is false (20 Nov 2026: of 13, eight were
closed in the code and five dismissed, none usable). Dependabot's monthly pull requests are merged once their
checks pass; a security fix comes at once.

## Accepted as it is

- **The agent merges its own pull request** once **test** passes, with no second reader (AGENTS.md): the price
  of several agents and one maintainer. What guards `main` is the checks, the ruleset (no deletion, no forced
  push) and the pre-push hook.
- **The data workflows hold a token that writes to `main` while they read the Assembly's files** (PDF and Word
  through pdftotext and LibreOffice). Splitting each into a job that reads and one that commits would cost a
  minute or more of an hourly run; not done. The source is one public institution's site, asked over HTTPS.
- **yt-dlp is not pinned** in the live service's image (YouTube breaks it often).
- **The key of `/upozorenja` travels in the address,** so it stays in the browser's history and Cloudflare's
  logs; the page sends no referrer and is never stored. It opens one device's outage alerts and the transcript.
- **The live service's container has a writable root filesystem** (see `live-service.md`).

## The headers every host sends

Set once for the whole zone at Cloudflare (Rules → Transform Rules → Modify Response Header, for every request),
since GitHub Pages and the buckets can send none of their own; **dns-check** prints what each host sends. The
workflows' Cloudflare token can't change the zone's rules, on purpose, so the maintainer sets them by hand:

| Header | Value | Against |
|---|---|---|
| `Content-Security-Policy` | `frame-ancestors 'none'` | another site showing a page of ours in a frame and passing a click to the vote buttons |
| `X-Frame-Options` | `DENY` | the same, for browsers that don't read the one above |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | a page's full address going to the sites it links to |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=(), payment=(), usb=()` | a script (ours or the analytics') asking for what no page needs |

`Strict-Transport-Security` (six months) and `X-Content-Type-Options: nosniff` were there before, from the
zone's settings.

**A full Content-Security-Policy is not set yet.** The pages carry scripts inline (the player, the live page's),
so a policy would have to allow every inline script, which guards little, or name each by its hash, which the
build would have to count. To be done as a task of its own: the hashes (or the scripts moved to files), the
policy sent as report-only first, then enforced.

## Reporting a flaw

`SECURITY.md`: privately, through GitHub's "Report a vulnerability".
