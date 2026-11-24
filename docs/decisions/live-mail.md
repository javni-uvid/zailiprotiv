# The live page: notifications and the day's mail

Decisions about the live page `mikrofon.zailiprotiv.rs` and its service: the push notifications and the summary by mail (the counter's side is in `worker/README.md`). Moved word for word from
`live/AGENTS.md` on 23 Nov 2026 (it had grown to 77 KB, read whole by every agent working in `live/`); what holds now,
in short, is there. **Keep it current:** a decision is added at the end of this file, in the same commit, and one that
changes an earlier one says so. Dates are the maintainer's decisions unless said otherwise.

**Changed since written:** The mail's link works until noon ("Who gets the day's mail" first said 8).

- **A notification when a sitting begins** (20 Nov 2026, the maintainer's choice: only the broadcast's beginning,
  the addresses kept by the counter). "Obavesti me kad sednica počne" under the speaker's box asks the browser,
  registers the page's service worker (`/sw.js`, `page.service_worker`: it shows the notification and opens the
  page, and handles no requests) and sends the browser's push address to the counter (`POST /p`, from
  `mikrofon.` only, the table `push`; "Isključi" sends `/p/odjava`). The live service (`obavesti.Bell`), after three
  frames of a live broadcast in a row between 7 and 22 h, asks the counter once a day to send (`POST /p/salji` with
  the token `PUSH_TOKEN`, in `live/.env` and GitHub Secrets; the test's is empty); the counter keeps the day
  (`push_days`), sends a push with no content signed with the VAPID key (secret `VAPID_JWK`, its public half
  `push_key` in `data/settings.json`) to 30 addresses a call, its free plan's limit, forgets addresses the push
  service says are gone, and the service asks for the next 30 until none is left. On an iPhone it works once the
  page is on the home screen, which the page says. `GET /pregled` gives the number of addresses and what each day
  sent; `mikrofon.obavesti` and `odjavi` are counted as uses.
- **The day's summary by mail** (22–23 Nov 2026, the maintainer's decisions: principle 5's exception as for the
  notifications, a mail every sitting day, the addresses kept by the maintainer, encrypted; the look chosen over
  three drafts). `mejl.build` makes the subject, text and HTML of a day (Latin or Cyrillic) from the day's summary,
  the chair's measures and the speakers' measured time: the decisions, the warnings and to whom, and what each
  speaker spoke about, on a line of time with the live page's marks; a speaker's list in its colour, a bar of the
  time, "opomena" by who got one and "najduže" by the three longest; no paragraph (the maintainer: "veliki blokovi
  teksta su loši"). The subject and the counts are the code's, and how the summary is made is on the method page
  linked at the foot, not in the mail. Tables and inline styles only: no picture, font or anything loaded, nothing
  tracked. `mejl.mixed_words` finds a word in two scripts (19 Nov: "iznео"). The counter sends what the service
  made (`POST /m/salji`, the push's token; Cloudflare Email Service from `sazetak@mikrofon.zailiprotiv.rs`, the
  only sending domain: the site's own keeps its mail at Loopia, whose MX records Email Routing would replace;
  answers go to `kontakt@zailiprotiv.rs`).
- **Who is who: the list's names and lists, never the model's** (23 Nov 2026, the maintainer: "Anji Brnabić",
  "Bakić" and MPs of the ruling group shown "bez liste" in the first draft). `mere.Roll` finds an MP in a sentence by
  the surname in any case ("Bakiću", "Milinku Jovanovu" → Milenko Jovanov), the given name or who had the floor
  deciding between MPs of one surname, nobody when still two; an MP's list is the group, else the party that
  proposed them (`data/<N>/members.json`), else "van poslaničkih grupa". `mere.measures` keeps only the chair's own
  words giving a measure (a sentence that speaks of one given before is none: of 19 Nov's 13, 8 were measures) and
  finds to whom, said so: a name in the chair's sentence; the stretch's summary naming who got one at that minute;
  the chair saying later whom he warned; for a word taken away over time, the MP with the floor. Never guessed
  otherwise. Written on 19 Nov alone: to be checked on the next days before the live page and the day's page use it.
- **Who gets the day's mail, and when** (23 Nov 2026, the maintainer's decisions: B, the maintainer first and all on
  his click; the addresses kept by him, encrypted, his name on the privacy page). "Sažetak dana na mejl" on the page
  (beside the notification's offer; a form to the counter that works without the script) asks the counter, which
  seals the address for the maintainer's key and mails a confirmation (`worker/mejl.js`). When the day's summary is
  on the page (`sudija.Judge._tell`), `pretplata.Mailer.ready` mails the day to `MEJL_UREDNIK` with a link
  (`/mejl/posalji?dan=&k=`, the day signed with `MEJL_KLJUC`) to a page with one button; the button sends the day to
  every confirmed address (`/m/spisak`, opened here with `MEJL_KLJUC`, each with its own unsubscribe link), once,
  until noon the next day (23 Nov 2026; first until 8). A word in two scripts stops it: the maintainer is told, nobody else gets the day. Both
  keys are in `live/.env` only; without them nothing is sent. What went is kept in `/data/mejl/<day>.json`.
- **The day's mail loses nobody and goes to nobody twice** (23 Nov 2026, found by trying the sender with the counter
  replaced: two clicks sent everything twice; a break after the first batch left the rest without the mail, the next
  click saying "already sent"; a mail to the maintainer that failed was kept as sent; a word in two scripts blocked
  the day after it was mended too). `pretplata.Mailer` sends under a lock and keeps per reader (the counter's row
  id, never the address) who has it, written before and after every batch of 20: a click after a break goes on where
  it stopped. A batch whose call timed out or ended in a 5xx is "nesigurni" and is not sent again: better one batch
  without the mail than twice. The mail to the maintainer is tried every five minutes (`sudija.MAIL_EVERY`) until it
  goes, and again when a word in two scripts was mended (edit `/data/sazetak/<day>.json` and restart the service,
  which keeps the summary in memory). The link works until noon (the maintainer; a day ended late reaches them at 7).
  Without `MEJL_KLJUC` no code opens anything (an empty key signed codes anyone could compute).
- **Leaving the day's mail takes the reader's own press** (23 Nov 2026, found in a look at the code): the link in
  every mail deleted the address when merely opened, and mail scanners open links. It is now a page with one button,
  as the confirmation is; the mail reader's own button (List-Unsubscribe-Post) still leaves at once. The texts no
  longer say "jednim klikom". A confirming mail that failed to go lets the address ask again (it had been told all day to
  look in its box). `tests/test_pretplata.py` runs the worker's own code in Node against a table in memory.
- **The card that offers the mail stands out, and shows what it offers** (23 Nov 2026, the maintainer: "ulepšaj i izrazi
  karticu … želeo bih da bude deo objave"). A dark card in either theme with colours of its own, the one thing on the
  page that asks something of the reader: "Dan u Skupštini, u jednom mejlu" (a sitting has many days), the maintainer's three lines with the mail's
  own marks (a decision, a warning, a speaker), the address and one button; `#mejl` leads straight to it. "Pogledaj
  primer" (`/mejl/primer`, `/cir/mejl/primer`) is the last day's mail by the same code, public once its summary is,
  with a line on top that it is a sample and that a model writes the summary; with a word in two scripts there is none.
  An hour or more at the rostrum is said in hours ("3 h 26 min").
- **The call for support is a card in the middle of the mail** (23 Nov 2026, the maintainer: "ulepšaj i izrazi podrži u
  mejlu i stavi ga više negde na sredini"; until then one line at the end). Dark as the live page's card that offers the
  mail, between the decisions and measures and "Ko je šta rekao" (after it, on a day with neither): a heart as a letter,
  who makes it, and the page's amounts (`settings.json`, `support.amounts`: 200, 500, 1000), each a link to its code
  (`podrzi#din-500`), plus "ili koliko želiš". Still nothing loaded, nothing that tells who pressed, nothing locked.
- **The mail's top, and the day in figures** (23 Nov 2026, the maintainer: "sredi izgled mejla, pogotovo kako predstavljamo
  summary i taj početak"; how many decisions and speakers "mi je nebitno, možda neke druge random zabavne statistike").
  A dark top with the day as a leaf of a calendar (as the live page's card) and the day in one line: "naslov", asked of
  the model (60 letters, one decision as a short sentence, nothing listed, no figures (the maintainer, the same day, on
  "…, potpredsednika je šest"), no speaker's claims; over 100 it is not used and
  "kratko" stands there as before). With decisions their list is the summary, so "kratko" stays only for the preview and
  the plain text. A vote is a bar of the hall and its figures. "Dan u brojevima" (`brojevi.py`): the code's, not the
  model's; how long and how many words, and two of six others turned by the date alone. The words are the same every
  day and nobody's (courtesy, the Rules); no figure is of a person or a list; counted only when the transcript covers the
  day (a silence of 20 minutes nobody called a break means it was off). The subject no longer counts decisions: it says
  what is in the mail, the code's words still. 19 Nov, read from the recording, has its figures in
  `/data/brojevi/2026-11-19.json`.
- **A notification when the sitting goes on after a long break** (24 Nov 2026, the maintainer's decision, in the hour's break
  of the second sitting week: to everybody who asked for notifications, not behind a choice of its own, and from when they
  begin to speak). `obavesti.resumed`: the chair said a break, nobody was heard for 20 minutes after it, and now an MP is
  read at the rostrum or two pieces of the transcript in 90 s have 8 words or more. Not from the words "nastavljamo sa
  radom": on 19 Nov they were said twice with no break before them. The rule on 19 Nov's steps: 15:42 and 18:24; the
  breaks of five and ten minutes tell nobody. At most twice a day, from 7 to 22 h, a break once (`obavesti.json`,
  `nastavak`; the counter keeps "n1:<day>", "n2:<day>"); a push not delivered in 15 minutes is dropped. A silence with no
  break said is none (the transcript was off). The promise of principle 5, "at most once a day", changed with it, on the
  button, the method page and the privacy page; a device that asked before gets it too, and can be turned off there.
