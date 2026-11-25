# The live page: notifications and the day's mail

Decisions about the live page `mikrofon.zailiprotiv.rs` and its service: the push notifications and the summary by mail (the counter's side is in `worker/README.md`). Moved word for word from
`live/AGENTS.md` on 23 Nov 2026 (it had grown to 77 KB, read whole by every agent working in `live/`); what holds now,
in short, is there. **Keep it current:** a decision is added at the end of this file, in the same commit, and one that
changes an earlier one says so. Dates are the maintainer's decisions unless said otherwise.

**Changed since written:** The mail's link works until noon ("Who gets the day's mail" first said 8).
The mail's look and what it loads are as the last entry says (25 Nov 2026): "no picture" and "Dan u brojevima" no longer hold.

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
  breaks of five and ten minutes tell nobody. As many as there are breaks (the same day's
  decision, in place of twice a day: "nema razloga za limit"), from 7 to 22 h, a break once (`obavesti.json`,
  `nastavak`; the counter keeps "n1:<day>", "n2:<day>" …); a push not delivered in 15 minutes is dropped. A silence with no
  break said is none (the transcript was off). The promise of principle 5, "at most once a day", changed with it, on the
  button, the method page and the privacy page; a device that asked before gets it too, and can be turned off there.
  A caption counts only when it is read for sure (`counted`): in the silent hall of that break the picture's noise was
  read as an MP's name for one frame.
- **The confirming mail says what to press** (24 Nov 2026, the maintainer: two readers answered it rather than press; 22 of 86
  were not confirmed): the subject and the first line say to press the button, and once more on the page it opens, the button is as wide as the mail ("Da, prijavi
  me"), the mail says an answer does not confirm, and the link stands under it for a reader whose button does not work;
  the page it leads to says "Poslednji korak", as it has a button of its own (scanners open links).
- **The mail is the day by the clock, then who spoke by lists, with portraits** (25 Nov 2026, the maintainer, over drafts of
  24 Nov's mail in which he chose among four tops: "napravi da se mail uvek pravi na ovaj način s ovim dizajnom"). After
  a look at what such mails do well (one thing on top, cards and white space, a single column of 600 px, 16 px text,
  buttons a thumb can press, the reading time). A masthead with the date and the minutes of reading; a dark card with
  the day's title and **the day by the clock**: the summary's steps ("tok"), the chair's measures (`mere`, amber, the
  list's names as before, "ime nije izgovoreno" otherwise) and the decisions (white and bold; a vote in large figures
  and a bar), in one line by time, a day past midnight in order. A step that tells of a measure, or stands at a
  decision's minute, is left out: the code's words say it. The call for support follows, then **"Govorili su"**: a
  band per parliamentary group, the groups by their seats in the list and then the alphabet, MPs of no group last
  with the party that proposed them; within a band the longest first; a mark beside who got a measure and when.
  "Odluke", "Opomene i mere" and "Ko je šta rekao" as parts of their own, "najduže" and the bar of time are gone, and
  so is "Dan u brojevima" (`brojevi.py` removed: the maintainer wanted what does not matter out).
  **Portraits change principle 5's exception**: the mail loads the MPs' portraits from `zailiprotiv.rs/foto/`, the
  same address for every reader and nothing of the reader in it, so nobody can tell who opened a mail; the site's
  host sees the request as on any visit. The maintainer chose this over circles with initials (which stay for an MP
  with no portrait); the privacy page said "u mejlu nema slika" and now says what is loaded and why it tells nothing.
  A portrait is cut round from its top by the mail reader; where that is not done (Outlook) it is a small upright
  picture. **Sentences are the maintainer's, never the service's**: "Rečeno u sali" stands only when
  `/data/mejl/recenice-<day>.json` is there (a list of `{"vreme", "ime", "o_cemu", "tekst", "snimak"}`), put by hand
  before the click that sends to all, each sentence chosen and checked against the recording by a person, with a link
  to its place in the archive; the mail says so. The rule that the automatic transcript is never a quote stands: the
  service shows none by itself. A file that cannot be read sends the mail without them. With 39 speakers the HTML is
  58 KB (70 KB with seven sentences), under the 102 KB at which Gmail cuts a mail.
- **The mail's line is shorter, and two helps stand on top of the maintainer's mail** (25 Nov 2026, the maintainer, of a
  list of what could be better: "može", "da", "poboljšaj ako treba"). `mejl.short_steps`: a break and the work going on
  after it are one step in the code's words ("Pauza do 11:23", the hour the next step gives), and of a step in two
  parts ("…; …") the first is kept; 24 Nov's line went from 20 rows to 15. Nothing is added to what a step says.
  **The weaker model in the subject**: "[za tebe, SLABIJI MODEL]" when the stronger one did not write the day (the
  note inside was there; on 24 Nov a wrong line of the weaker one went to all). **Whom the chair named after a measure
  with no name** (`pretplata.hints`): the chair's pieces of the five minutes after it that name a sitting MP and speak
  of a warning, word for word, for the maintainer only. No rule names anybody by it: tried on 24 Nov it shows
  Kuburović at 13:27, rightly, and Vučić at 12:15, wrongly (the chair only gave him the floor), so a rule would
  have named a wrong MP. A name the maintainer confirms is put in the day's line by hand (`vise.kome`).
- **A correction of an earlier mail stands in the next one** (25 Nov 2026, the maintainer, asked whether that evening's mail
  should carry a line of correction after 24 Nov's said something false about an MP to all readers: "1 da"; until then the
  page was mended and the readers told nothing). When a mail that was sent said something false about a person, the next
  mail says so. The conductor puts it by hand in `/data/mejl/ispravke-<day>.json`, `<day>` being the day of the mail that
  carries it, beside `recenice-<day>.json` and read like it, each time a mail is made: a list of `{"dan": "<the day whose
  mail was wrong, YYYY-MM-DD>", "tekst": "..."}`, the same for anybody. The words are the maintainer's, shown as written
  (never a model's; only escaped, and in Cyrillic letters for who reads Cyrillic). A plain white card "Ispravka" with the
  day it is of, above the day's dark card, and "ISPRAVKA" first in the plain text; in the maintainer's copy, the mail to
  all and the sample. With no file or an empty list the mail is byte for byte what it was. What cannot be read of the
  file is left out and the maintainer's copy says so on top (`pretplata.UNREAD`): a correction that silently does not go
  would be taken for sent. A file put after the maintainer's copy went is in the mail to all and not in that copy, so it
  is put before.
- **How many asked to be called back is counted, never who** (25 Nov 2026, the maintainer's yes to counting subscribers by
  sitting day; a site without cookies cannot see who came back, only who asked to be told). `tools/pretplate.py`, run by the
  conductor, only reads: the counter's public overview, and the ids of `/data/mejl/<day>.json` inside the page's container,
  which gives numbers alone (no id comes out, no sealed address is asked for, no key read). New and gone are from one mail
  to the next. The first reading: 119 confirmed of 145 sign-ups sent from the page (82%, roughly: the same address sent
  twice counts twice), nobody gone between the mails of 24 and 25 Nov, 33 devices with notifications; 7.3 sign-ups per
  1,000 pages opened on 24 Nov, 5.3 on the 25th. Not kept, so not counted: the day of a leaving, and the sign-ups never
  confirmed (deleted after 48 hours). Nothing new is kept for it.
- **An address Cloudflare refuses does not keep the day from its end** (25 Nov 2026, the conductor's task; found reading the
  code: one such address, and every click said "Nije završeno" and tried it again). A row refused with
  `E_RECIPIENT_SUPPRESSED` (Cloudflare's list: a bounce, a complaint, an entry by hand) is put in the day's `odbijeni`, by
  the counter's row id, and is not tried again that day; it stays in `greske` too, and the click says some were refused.
  Their documentation marks no code as lasting, and the answer gives neither the reason nor the end (a full mailbox 24
  hours, other bounces 7 days, no such mailbox or a complaint for good). That code alone speaks of the address, so it
  alone counts. The rest are tried again, `E_DELIVERY_FAILED` (a rejection or a failure on the way, not told apart) and
  `E_RECIPIENT_NOT_ALLOWED`, `E_RECIPIENT_PLAN_RESTRICTED` (our account's settings) among them. The same code also comes
  when the sender's own address is refused, then for everybody: so a refusal counts only while more have the day's mail
  than are refused it. **The row is not deleted**: the next day's mail tries it once, as anybody's. Whether a row refused
  for long is to be deleted is the maintainer's to decide.
