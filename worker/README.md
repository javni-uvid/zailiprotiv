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
- `DISPATCH_TOKEN`: a fine-grained GitHub token for javni-uvid/zailiprotiv only, with Actions: Read and write;
- `VAPID_JWK` and `PUSH_TOKEN`: the live page's notifications (below).

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

`POST /e {e, k?}` adds one to a sum per day for one of a fixed list of uses: `kviz.kraj` (the quiz's result reached),
`kviz.pocetak`, `kviz.pola`, `kviz.sve` (an answer given, half the quiz's laws answered, every one; each once per page
opened; 26 Nov 2026), each of the quiz's uses also under the quiz's name (`kviz.kraj:podelili-salu`) when `k` is a quiz
the site lists in `glasanje.json` (`kviz`), and
for the quiz's picture (`kviz.`) and the ballot's (`listic.`): `otvori` (the ballot's picture opened), `podeli` (the
share button), `podeljeno` (the share sheet finished), `kopiraj`, `sacuvaj`; and `mikrofon.pusti` (the live
page's ▶ on the broadcast pressed; the one use taken from `https://mikrofon.zailiprotiv.rs`, which may send only
`mikrofon.` uses); `mikrofon.slusaj` ("Slušaj", the live sound only, pressed; 25 Nov 2026); the site's search: `pretraga.trazi` (a search run), `pretraga.prazno` (one that ended with no
result), `pretraga.klik` (a result opened), and the field on the home page and "Poslanici": `pretraga.polje` (typed in),
`polje-nema` (no name or title), `polje-izbor` (one taken), `polje-ceo` (the whole text's search taken), never the
words searched for; `sajt.snimak` (a recording played on a day page), `sajt.mikrofon` (a link to the live page
taken; `sajt.mikrofon-meni`, `-pocetna`, `-najava`, `-traka`, `-poslanik` by where: the menu, the home page's
strip, the announcement before a sitting, the bar of a sitting, an MP at the rostrum); from the live page `mikrofon.obavesti-moze`, `-klik`, `-odbijeno`, `-greska` (the notification's offer
shown, pressed, refused at the browser's question, failed). The page "Podrži" (23 Nov 2026):
`podrzi.klik-meni`, `-podnozje`, `-pocetna` (the way to it from the site), `podrzi.otvori`, `podrzi.od-mikrofona`
(opened from the live page), `podrzi.kod` (the codes in view), `podrzi.slika` (a code's picture saved),
`podrzi.kopiraj` (the account's details copied), `podrzi.paypal`; the phone's bar (27 Nov 2026): `meni.zakoni`,
`meni.poslanici`, `meni.uzivo`, `meni.glasaj` (taken), `meni.jos` ("Još" opened), `meni.jos-izbor` (a row of it taken). Nothing else is stored with it, not even
the device's mark. `GET /pregled` lists them under `uses`, by day, for the last two weeks. Each page sends each use at
most once.

Four of them are also summed per hour (25 Nov 2026; UTC, the table `events_hours`: the hour, the use, how many, nothing
else): `mikrofon.pusti`, `mikrofon.slusaj`, `mikrofon.1min`, `mikrofon.5min`. `GET /pregled` gives them under
`uses_by_hour`, for the same two weeks, without an hour's sum under three (the overview is public, and a sum of one
can be a person); the **visits** workflow prints them (`tools/uses.py`).

## Notifications from the live page

`POST /p {endpoint, cir}` (from `https://mikrofon.zailiprotiv.rs` only) keeps a browser's push address in `push`;
`POST /p/odjava {endpoint}` forgets it. Only addresses of the known push services are taken (Google, Mozilla, Apple,
Microsoft). `POST /p/salji {od, vrsta, broj}`, with `authorization: Bearer <PUSH_TOKEN>`, is the live service's: the first call of
a day (`od` 0) records the day in `push_days` (a second one that day sends nothing), and each call sends a push with
no content to 30 addresses after row `od`, signed with `VAPID_JWK`, forgets those the service answers 404 or 410
for, and answers `{sent, gone, next}`. Secrets: `VAPID_JWK` (a P-256 private key as a JWK; its public half is
`push_key` in `data/settings.json`) and `PUSH_TOKEN` (also in `live/.env`).

## The watch over "Ko sada govori"

A cron every five minutes, weekdays 6-19 UTC (`watch`): `https://mikrofon.zailiprotiv.rs/stanje.json` answered by
the service itself is up; otherwise the Assembly's listings are read (at most once in 30 minutes, kept in `watch`)
for a sitting marked "(у току)". Down in two checks in a row while one is on, the devices in `push_admin` get a
push, and another when it is up again. `POST /p/admin` and `/p/admin/odjava` (with `PUSH_TOKEN`, from the live
service's `/upozorenja`) keep and forget those devices; `POST /p/vrsta {endpoint}` (from the live page's service
worker) says which notification a push was.

## Inflated counts

There is no robot check. The `watch` workflow reads `GET /pregled` four times a day and opens an issue when one
network sends most of a law's votes of the day. To look closer, and to remove (the maintainer's decision; say so on
the method page when it is done):

    wrangler d1 execute zailiprotiv-glasovi --remote --command "SELECT net, vote, COUNT(*) FROM ballots WHERE item='<law>' AND day='<day>' GROUP BY net, vote ORDER BY 3 DESC LIMIT 20"
    wrangler d1 execute zailiprotiv-glasovi --remote --command "DELETE FROM ballots WHERE item='<law>' AND day='<day>' AND net='<net>'"

If this happens often, the next step is Cloudflare Turnstile on `POST /z` (free; adds a script from Cloudflare).

## Mail

`POST /m/salji {"poruke": [{to, subject, html, text, odjava}]}`, with the push's token, is the live service's: up to
20 messages a call, each sent as it is through Cloudflare Email Service (the binding `MEJL`, Workers Paid) from
`sazetak@mikrofon.zailiprotiv.rs`, answers to `kontakt@zailiprotiv.rs`; `odjava` also as `List-Unsubscribe` (left out
when Cloudflare does not allow the header). Answers `{poslato, greske: [{i, code}]}`.

Who asked for it (`mejl.js`, the table `mejl`): `POST /m {adresa, pismo}` from the live page only, rate-limited, sends
a mail asking to confirm (once a day to one address; the answer is the same whether or not the address is there);
`/m/potvrdi` confirms by a button on its page (mail scanners open links); `/m/odjava?i=&k=`, the link in every mail,
has a button too, and its POST (the button, and List-Unsubscribe-Post) deletes the row at once. A confirming mail
that did not go lets the address ask again. The address is sealed with `MEJL_JAVNI` (the public half of the
maintainer's key; ECDH P-256, HKDF-SHA-256, AES-GCM): this worker writes it and can't read it. `GET /m/spisak`, with
the push's token, gives the live service the confirmed rows, sealed, each with its unsubscribe link. Unconfirmed
rows go after 48 hours (the hourly run); `/pregled` gives the counts only.

## Following an MP by mail

`prati.js`, the tables `pratioci` (a reader: the address sealed, its hash, the script, the day confirmed, how many asked for that day), `prati` (what is
followed: sealed, the day asked and confirmed) and `prati_dani` (confirming mails a day, from all). Both are sealed with `MEJL_JAVNI`, padded first to
one length; there is no hash or column from which an MP can be told, and nothing counts by MP. `POST /m/prati {adresa, sta, pismo}` from the site only,
for a sitting MP of the site's `prati-poslanici.json`, rate-limited: a mail that names the MP and asks for consent, at most one a day to an address not
confirmed, five to one that is, twenty followed at once, 300 such mails a day in all. `/m/prati/potvrdi` confirms that one by a button on its page;
`/m/prati/kraj`, `/sve` and `/svega` end one, all, or all and the day's summary, each by a button, and the mail reader's own button (`/sve`) at once; the row is deleted, the
reader's with the last. `GET /m/prati/spisak`, with the push's token, gives the live service the confirmed, sealed, with their links and the row of the
day's summary of the same address. Not confirmed in 48 hours: deleted. `/pregled` gives how many readers and how many wait, in all.
