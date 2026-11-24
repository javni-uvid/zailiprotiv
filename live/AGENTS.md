# AGENTS.md for `live/`: "Ko sada govori"

What holds now for the live page `mikrofon.zailiprotiv.rs` and the service behind it, in short, and where each
decision is. It continues the repository's `AGENTS.md` (how to work, the principles), which is read first; `README.md`
here says how the service works. The decisions themselves, with their reasons, are in `docs/decisions/live-*.md` (23
Nov 2026: this file had grown to 77 KB). **Before changing a part, read its file**; a decision is added at the end of
that file in the same commit, and here only when a line below no longer holds.

| Part | File in `docs/decisions/` |
|---|---|
| How the service runs: the test and the live image, restarts, the edge, alerts, secrets, the code's parts | `live-service.md` |
| Who is speaking: the caption, the chair's words, the voice, who presides | `live-speaker.md` |
| The automatic transcript: Whisper, corrections, the line under the picture | `live-transcript.md` |
| What happened: the day's steps, the agenda, the model's steps and summary, the groups' time | `live-day.md` |
| How the page looks: order, the speaker's box, the cards, colours, words | `live-page.md` |
| Notifications and the day's mail | `live-mail.md` (the counter: `worker/README.md`) |
| Listening: the recording's sound, the live sound | `live-sound.md` |
| What the site makes of the service's records, and the recordings read afterwards | `recordings.md` |

## What must not change without the maintainer

- **Every speaker by one rule** (principle 1): nobody followed, singled out or ranked by preference.
- **Nothing from elsewhere on the page** but what principle 5 names: the counter of visits, the player only on a click,
  notifications and the mail only to who asks.
- **The automatic transcript is never a quote** and is off the page, but for the line under the picture, which says
  it may err. A correction mends spellings only. No step shows the transcript's wording (the sentences of a measure and
  of an exchange in "Šta se desilo", tried on 24 Nov 2026, are off since that day: `RECI_PRIKAZ`).
- **Nobody is ever named from a face on the live page;** a voice or the chair's words name a speaker only while no
  caption does, by the rule checked against the notes, and the page says which it was. The presiding officers are
  never named as speakers by voice.
- **The model** (`sudija.py`) tells only what was said, by a set list of steps each resting on a sentence found word
  for word; a vote that does not add up goes without its figures. Its words are labelled as a model's. The day's summary is a
  stronger model's (`DAY_MODEL`), from the whole transcript, after the sitting; what its lines rest on goes to the
  maintainer only.
- **A name in the mail or the measures is the list's, never guessed.**
- **The readers' addresses** are opened only here, only to send, and never written down: what went is kept by the
  counter's row id. To all only on the maintainer's click, until noon the next day.

## How to work here

- **Test, look, then live, by the agent itself:** `mikrofon.ps1 test` from the worktree, look at the page (a phone's
  width, both scripts); after the merge build the test from the main clone on a clean `origin/main`, check that
  nothing else lies between the live image's commit and `main` (`mikrofon.ps1 stanje`, `git log <commit>..origin/main
  -- live/`), then `mikrofon.ps1 uzivo`, and check the public page.
- **Without a sitting:** a container by hand on a round-the-clock broadcast (`SOURCE_PAGE=`, `CHANNEL_LIVE=`,
  `YOUTUBE_URL=<its address>`, port 8095), never with `--env-file`.
- **Secrets** are in `live/.env` only; a test has none but the page's key, and a new one is emptied in
  `docker-compose.test.yml` (a test asks for it).
- **The sound never holds up the frames**, and neither does anything else: what is slow has a thread of its own.
- **A file the service keeps is written whole** (`state_base._write`).
- **The voices' rule and the recordings' are the same** (`glas.stretches`, the site's `ko.stretches`): change both. The
  name of a worktree's test is computed in `mikrofon.ps1` and `tools/pocisti-projekat.sh`: change both.
- **What the page says about principle 5** (what loads, what is kept, what is counted) is on the page or the method
  page: a change there changes the words too, in both scripts.
- The tests are `tests/test_live.py`, `test_pretplata.py` and `test_mejl.py`; OCR and the stream are tried against a
  broadcast.

**What Google shows of the live page (23 Nov 2026, from the maintainer's picture of the search).** The result's
description was the player's note ("Snimak iz arhive … učitava se tek na klik"): that note is `data-nosnippet`, so
the page's own description stands. Its name was the address: the home says it as schema.org WebSite ("Mikrofon Za
ili Protiv", which people search for; Latin home only, as on the site).

**The live page's heading has the name** (23 Nov 2026, the maintainer: "moramo i mikrofon istaći isto"): "Za ili
Protiv: Jutrić, Kafica, Skupštinica", the maintainer's words, as the h1 and first in the tab's title, which keeps
"Skupština uživo" after it (what people search for: the decision of 22 Nov on the title). Google titles a page by its
h1 as well as its title. The link's preview and the description say what they said.
