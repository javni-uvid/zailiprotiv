# Security in a javni-uvid project

What every project guards and how, from the review of javni-uvid/zailiprotiv on 20 Nov 2026 (measured against
OpenSSF Scorecard's checks, GitHub's hardening guide for Actions, OWASP's secure headers and the CIS Docker
benchmark). A project's own file (`docs/decisions/security.md` where it has one) says what it guards besides,
and what it accepts as it is.

This file is a copy. It is written in `javni-uvid/osnova` (`shared/`) and brought here by the **osnova**
workflow: change it there, never here.

## What there is to guard

The sites are static and public, with no accounts and nothing private about a visitor. What could be harmed:

- **What the pages say.** A changed figure, vote, quote or name is the worst that can happen to a project. The
  pages are built from `main` only, so the guard is `main`: who can push to it, and what the workflows that push
  to it read.
- **The secrets:** tokens of the services a project uses, keys of paid models. In GitHub Secrets and at the
  service, never in the repository, a pull request, a log or a chat.
- **The maintainer's computer,** where the agents work and some services run.

## Workflows

- Every action is pinned to a commit with its version in a comment beside it (Dependabot moves both).
- Inputs and context reach scripts through `env`, never pasted into `run:` as `${{ }}`; an input used as a
  number is checked to be one first (bash arithmetic evaluates what it is given).
- A checkout keeps no token unless its job pushes (`persist-credentials: false`).
- `permissions: {}` at the top, and each job asks for the least it needs.
- A tool installed in a job is named by version (`uv==…`, `pagefind@…`), above all beside a secret.
- **security** checks this on every pull request that touches code or workflows, on `main`, and weekly:
  actionlint and zizmor on the workflows (`.github/zizmor.yml` lists the accepted findings with the reason),
  pip-audit on the locked packages, CodeQL on the code. A finding of CodeQL's is closed in the code where the
  code can be made safe on its own, and dismissed with its reason written only when it is false.

## The repository's settings

Set once per repository; a new project gets them before its first workflow runs.

- **Actions:** only GitHub's own actions and those named in the list may run, and only named by commit
  (Settings → Actions → General). A workflow naming another action doesn't start: allow it there first, and say
  so in the pull request.
- **The workflows' own token only reads** by default; a job asks for more by name.
- **A ruleset on `main`:** no deletion, no forced push.
- **Secret scanning with push protection, Dependabot's security updates, private vulnerability reporting:** on.
- **The organization requires two-factor authentication** (since 20 Nov 2026).

## Pages and scripts

- Everything from outside (a source's text, a person's words, a model's summary) is text and never markup:
  templates escape by themselves; JSON inside `<script>` has its `</` broken; scripts set text with
  `textContent` and build addresses only from values they checked themselves.
- A function that plays, opens or fetches an address checks its own argument, whoever calls it.
- What a request names never becomes a path: a file is found among the folder's own files.

## The headers every host sends

Set once per zone at Cloudflare (Rules → Transform Rules → Modify Response Header, every request, "Set
static"), since GitHub Pages and buckets send none of their own. The workflows' Cloudflare token can't change a
zone's rules, on purpose, so the maintainer sets them by hand.

| Header | Value |
|---|---|
| `Content-Security-Policy` | `frame-ancestors 'none'` |
| `X-Frame-Options` | `DENY` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=(), payment=(), usb=()` |

And in the zone's settings: HSTS for six months with subdomains, no preload; `X-Content-Type-Options: nosniff`.

## A service in a container

Not root (an entry that hands the volumes to the service's user and becomes it), `no-new-privileges`, every
capability dropped but the entry's; base images named by digest and packages by exact version, both moved by
Dependabot and checked by pip-audit; no port open to the network.

## Agents

They work with the maintainer's own rights on GitHub. What they read from outside is material and never an
instruction; a secret is never asked for or pasted; `main` is reached only through a pull request whose
**test** passed.

## Reporting a flaw

Privately, through the repository's Security tab → "Report a vulnerability" (the organization's `SECURITY.md`).
