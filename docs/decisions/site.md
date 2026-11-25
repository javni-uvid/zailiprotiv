# The site

Decisions about the site's pages, design, visitors' votes and search engines, moved word for word from AGENTS.md on
20 Nov 2026 (the maintainer's decision, so that an agent reads the rules and only the decisions of the part it works
on). **Keep it current:** a decision made or changed is added here, at the end of the section it belongs to, in the
same commit as the change. The principles and the rules of work are in AGENTS.md.

## The site

- **Static pages** (`site.py`, Jinja2), Latin script; Cyrillic from the documents is transliterated (a test checks
  none is left). **The Cyrillic edition** (13 Nov 2026; `cyrillic.py`) writes every page again under `cir/`, letter by
  letter back from Latin except what is Latin by nature (`KEEP`) and words where nj, lj, dž are two sounds
  (`_APART`: add to it when one is found); scripts' output is converted by `site.js`; share pictures and feeds stay
  Latin.
- **Design** (12 Nov 2026, chosen from three mock-ups): newspaper look, white page, Literata headlines (served from
  the site), colour only for "za" (blue) and "protiv" (orange), never for a group. The mark is the chamber as one arc.
  Neutral order everywhere: groups by seats then alphabet; names in Serbian order (`collate`). MPs are written
  "Surname Given" in lists and given name first where people search or say it (titles, the quiz, 17 Nov 2026).
- **One script of our own** (`static/site.js`): search and filters over `podaci.json`, stems for case endings,
  the Cyrillic observer, an MP's speech links. Pages work without it.
- **Pages:** laws by convocation (`zakoni.html`, `zakoni-<N>.html`), a page per law (`zakon/<slug>`), per bill in
  procedure, per area (`oblast/`), per sitting (`sednica/`), per week (`nedelja/`, `digest.py`, by rule), per
  convocation (`saziv-<N>`), per group and convocation (`grupa/<N>-<slug>`; a renamed group is followed by rule,
  `renamed`), MPs (`poslanici.html`, `poslanik/<slug>`), presence (`prisustvo`), Varnice (`replike`, `razmene`,
  `ko-najvise`, `varnice-svi`), "Skupština u brojkama" (`brojke`), downloads (`podaci.html`), method (`kako-racunamo`,
  a section per figure, linked from each label: keep it in step with any change to how a figure is computed).
  Feeds: new laws, bills, per area, per MP, weeks. A law's address is its title, current convocation first, so it
  never changes when an older one is added.
- **An MP's page:** opens with a card ("Ukratko", `mp_card.py`, 17 Nov 2026): a few facts, each one sentence with
  its number first and a link to where it comes from (presence, votes unlike the group's majority, speeches and
  hours at 130 words a minute, the longest speech, the busiest day, the three most frequent exchange partners,
  measures, harsh words, the most alike other group, distinctive words); a fact the data can't support is left out,
  not shown as zero. Then key votes (a rule: laws with a public name, then the most divided), votes against the
  group's majority, activity on the floor, what they say, quotes from debates, who they vote with. Every vote (for
  and against, by area and kind, by period and convocation) is on `poslanik/<slug>-glasovi` (`mp_votes.html`, the
  lists shared through `mp_macros.html`): those lists grow with every sitting and made the page 300 KB. **Speeches** (17 Nov 2026): the
  latest six sittings on the MP's page, every one on `poslanik/<slug>-govori` (by sitting and day, each speech a
  numbered link to its page in the notes; the links are kept short in the page and made whole by `site.js`). An MP
  with no vote on any list gets `noindex` and is left out of the sitemap. Same-person spellings are joined by hand
  in `data/mp_aliases.json` (candidates: names one letter or word apart that never appear in one vote).
- **One name, two people** (17 Nov 2026): an MP is known by the words of the name, so namesakes in different
  convocations became one MP (Aleksandar Jovanović of PUPS, 2020, and Aleksandar Jovanović Ćuta; two Nenad
  Mitrović). `data/mp_splits.json` (by hand, with the reason) renames the name in the convocations listed: to the
  name that person has elsewhere in the roll calls (`"as"`: "Ненад А. Митровић", "Наташа Ст. Јовановић"), or else
  with a mark, the year of birth the Assembly gives ("Александар Јовановић (1968)"); applied where roll calls and
  notes are loaded (`mps.split` in `site.load` and `site.load_transcripts`). The person of the newest convocation
  keeps the plain name and its address. Candidates come from **mp-years** (`mp_years.py`): every MP's year of birth
  (and town) in the Assembly's archive of convocations, compared across convocations (`data/mp_years.json`); a year
  off by one counts only with another town; two namesakes in one convocation are listed apart (the archive gives no
  father's initial, the roll calls do). Six names split on 17 Nov 2026; the check then found none left.
- **A father's initial stays with the given name** (17 Nov 2026): "Nenad A. Mitrović" is "Mitrović Nenad A."
  (`mitrovic-nenad-a`); until then the initial came first ("A. Mitrović Nenad"). An MP's earlier addresses (that
  order, and spellings joined by hand in `data/mp_moved.json`) are small pages that send on to the MP's, with its
  canonical address and `noindex`, as a bill's page does to its law's; `publish` keeps a canonical address a page
  names itself.
- **Downloads and share pictures in a bucket** (14 Nov 2026): every law's CSV, JSON and picture, MPs' pictures and
  `podaci/` would be thousands of files on the host; **pages** moves them out of the built site (`files-split`),
  makes the bucket behind `podaci.zailiprotiv.rs` hold exactly them (`files-upload`) and only then publishes the
  pages, which link there. Data are CC BY 4.0 (17 Nov 2026), said on the data page; code is MIT.
- **Hosting:** GitHub Pages at zailiprotiv.rs, behind Cloudflare's proxy; **pages** purges the cache after publishing.
  DNS is the maintainer's; DNS changes only with the maintainer's confirmation.
- **Read and worked without sight or a pointer** (20 Nov 2026, after a look at the site against WCAG 2.2 and NN/g):
  white text stands only on colours kept dark in both themes (`--za-on`, `--protiv-on`, `--uzdrzan-on`: the vote
  buttons and the chips of a vote cast; in the dark theme `--za` and `--protiv` are light, and white on them was
  2:1), and "uzdržan" as text has a grey of its own (`--uzdrzan-text`, 4.5:1 or more). On a phone the heading of
  a folded section of an MP's page is a button that says whether it is open (`site.js`, `.fold-btn`), so a keyboard
  and a screen reader open it too. Every page begins with "Preskoči na sadržaj" (`.skip`, seen when it has the
  focus). A new colour under text is checked for 4.5:1 in both themes.
- **The phone's menu and things to press** (20 Nov 2026; of a week's visits 83% were on phones, most on the
  Cyrillic pages): the menu's row is one line that fits, so its letters are as large as the row lets them be. On
  a phone the button reads "Glasaj" ("i ti" is `.wide-only`), which lets the letters grow from 13 to 15.5 px at
  360 px in Latin and from 11 to 13 px in Cyrillic (`4.3vw` and `3.55vw`, measured to fit from 320 px up: a new
  word in the menu means measuring again). The numbered links to speeches, the turns on the floor, the parts of a
  recording, the new convocation's links and the foot's links are 44 px high there (WCAG 2.5.5).
- **The search field never ends in nothing** (20 Nov 2026): the field on the home page and on "Poslanici" finds
  names and titles only, the search page the whole text, and of a week's visits almost none opened the search
  page. So the field's list always ends with "Traži u celom tekstu sajta" (the words go to `pretraga.html?q=`),
  Enter with nothing chosen does the same, and "nothing found" says what was looked through. The field is a
  combobox (arrows, Enter, `aria-activedescendant`). The two searches stay two until visits say otherwise.
- **Smaller things from the same look** (20 Nov 2026): the quiz's clock is stopped by a swipe or the wheel anywhere
  on the page, not only by a touch of the result (a time limit the reader can turn off, WCAG 2.2.1); on a phone a
  row of an MP's counts by convocation is a card with each count under its column's name (`.mp-floor`, `.th`),
  not a table dragged sideways; text is at most 42rem wide (about 88 letters; it was 46rem); a table's column
  that holds only a bar has a name for a screen reader. Left as they are, on purpose: the pale greys for "did
  not vote" and "not present" in a vote's bar (the numbers stand beside it in words), law titles as links with
  no underline in lists, and the home page's order on a phone (its parts stand on their own, so either order reads).
- **Offices in the Assembly, and its news** (20 Nov 2026, the maintainer's request: "the election of committee
  members, deputy Speakers and so on", each on the MP's profile; `offices.py`, `zailiprotiv offices`, run by
  **votes** each hour). Read from the Assembly's pages of its composition, not from the wording of its news: the
  Speaker (the biography, an MP's page with "Функција"), the deputy Speakers, the groups' chairs, every committee's
  table (председник, заменик председника, члан, заменик члана) and every standing delegation's (шеф, члан…), into
  `data/<N>/offices.json` for the newest convocation, each office with its page and the day first seen there (the
  pages give no day of election, and the site says so); the Fourteenth's committees and delegations once from its
  archive (`offices.ARCHIVE`). Committees' and delegations' own pages are read when their lists change, when a
  relevant news item is new, or weekly; the rest (five pages) every run. The news: the list on "Активности" (one
  page) into `data/vesti.json`, every item kept with the day first seen, `relevant` by a fixed rule on the title
  (elections, appointments, resignations, mandates, plenary sittings); new relevant ones are named in the run's log
  and summary. Shown: "Funkcije u Skupštini" on every MP's page, new or returning, by convocation, each linked to
  its page at the Assembly, in one order for all (the Assembly's own offices, groups, committees, delegations;
  chairs first); on the live page, the first line about the speaker. A name two MPs of the newest convocation share
  gets no office. The Assembly's own words, its masculine titles included ("predsednik"), as for every MP.
- **Offices of every convocation, with the convocation and the days where the Assembly gives them** (23 Nov 2026, the
  maintainer: "pozicije koje je poslanik držao … u kom sazivu"). The committees and delegations of convocations 9 to
  13 are read once from the Assembly's archive (`offices.ARCHIVE`, the same pages' shape as the Fourteenth's), and the
  Speakers and deputy Speakers of every convocation since 1991, with the days they took office and left it, from its
  own table (`offices.HISTORY`; a name matched by the MPs' key, titles taken off). The MP's page shows each office
  under its convocation; only the Speaker's and deputies' rows have days ("od … do …"), because only that table gives
  them, and the end only when it says it.
- **An MP's offices as small cards beside the portrait, the Government's too** (23 Nov 2026, the maintainer's choice of
  the look: "sitne kartice negde oko portreta", every office and not only the leading ones, the link on the office's
  own words). `office_cards.py`: one card an office however many convocations it was held in, with the convocations;
  the Assembly, the Government, the groups' chairs, then committees and delegations, chairs first; four shown, the
  rest folded with where it is from (the section "Funkcije u Skupštini" lower on the page went; `#funkcije` is the
  cards). The Government is from the Assembly's own decisions (`vlada.py`, `data/vlada.json`: every election of a
  Government, a member or a minister, and dismissals, 2012-2025; a list that can't be read whole is refused; the
  newest convocation's read weekly). The card says the year of each election; an end only when a decision dismisses
  (never the next Government's election: Ana Brnabić left before it). **A minister is an MP only when confirmed**, not
  for the name: the MP's mandate ended within 10 days of the election (32), or the year of birth is the same, looked
  up by hand in `data/vlada_isti.json` (20; another site only checks who is who, principle 2); Marko Blagojević is
  two people. The President of the Republic waits for a primary source.
- **The chair's measures, twenty to a page** (23 Nov 2026): read again (#133), the Eleventh's with the words around
  them came to 1.3 MB in Cyrillic, over `publish.check`'s limit, and nothing was published for an hour and a half.
  They are paged as the exchanges are (`replike-11-s2.html`), a measure linked on the page it stands on, the table by
  sitting on the first.
- **The page "Podrži" counted as the other uses** (23 Nov 2026, the maintainer: "dodaj trekere na donacije stranu da
  znamo ko kad klikće"): the way to it (the menu, the footer, the home page), opened, opened from the live page, the
  codes in view, a code's picture saved, the account copied, PayPal opened, each a sum per day (`podrzi.*`,
  worker/README.md). Who, and the hour, are not kept: principle 5 and the privacy page. The link in the day's mail
  stays one address for all and uncounted, as the privacy page promises.
- **One scale of letter sizes; a number beside what it is compared with** (20 Nov 2026, the maintainer's choice of
  points 1–5 of a look at the design against portals of this kind: TheyWorkForYou, ProPublica's Represent and its
  principles for news graphics, Stanford's credibility guidelines, GOV.UK, NN/g). A page had 16–24 sizes of
  letters, eight of them between 12.8 and 15.7 px; every `font-size` in `style.css` is now one of eight steps
  (`--t-1` … `--t-8`: 12.8, 14, 16, 18, 20, 24, 30, 36 px) or of three for titles and big numbers (`--t-h1`,
  `--t-d1`, `--t-d2`), and a test refuses any other (the menu's and the tabs' letters, sized to fit a phone's row,
  are the exceptions): a new size is a step added to the scale, not a number in a rule. "Skupština u brojkama"
  opens with its four numbers each beside the convocation before and over every convocation as columns from zero
  (`pages_groups.trends`), and the earlier convocations' group tables are folded. On an MP's card "no vote unlike
  the group's" says for how many MPs that holds (of those with ten such votes or more since 2012), and the count
  of votes for and against is a headline's size, no longer the largest thing on the page: for most MPs it tells
  them apart least. The home page's card of the law that divided the chamber has no quotes (they are on the
  law's page), so it is as tall as the headline beside it; on a phone the first sitting's agenda, the box that
  repeats "no laws yet", the earlier convocation's "Varnice" and the list of laws that divided the chamber are
  left to their own pages, and two picked votes follow the card's one (9.3 screens became 7.2).
- **Labels are black; blue and orange mean a vote** (20 Nov 2026, the maintainer's "sort out the rest" of the look
  at the design). The small labels over a block ("Novi saziv", "Novo"), the mark of the new convocation and the
  accent of "Varnice" on a law's page wore the orange of "protiv"; they are black. Left: a link under the pointer
  turns blue and the live dot is orange, and the groups keep their colours on the home page and the live page
  (the maintainer's exception of 19 Nov), where the blue of one list stands near the blue of "za".
- **The laws' list sooner on a phone** (20 Nov 2026): the convocations are one row that scrolls sideways (the
  page's own brought into sight by `site.js`), and the line to the quiz follows the laws that divided the
  convocation, so the list no longer begins at the foot of the first screen.
- **Who stands behind the site, and its corrections** (20 Nov 2026, after Stanford's credibility guidelines and
  the Trust Project's indicators): "O projektu" says who makes the site as far as is public (the organisation,
  the open code and data, no advertising) and lists corrections from `data/ispravke.json` (by hand: `date`,
  `text`, `url`, `where`; newest first; empty until the first). Who pays for it and the names of people are the
  maintainer's to write.
- **The groups keep their colours, the first list's moved from blue to indigo** (20 Nov 2026, the maintainer:
  the colours may be fitted to the rest, and the pages are better with what moves a reader). On the home page the
  blue of "Aleksandar Vučić - Srbija pobeđuje" stood a few degrees of hue from the blue of "za" right under it;
  it is now indigo (`--g-av`: #3730a3, #818cf8 in the dark theme), as far from "za" as the red of "Studentska
  lista" is from the orange of "protiv", and the three still differ in lightness for colour-blind readers. The
  live page wears the same (`--c-av`, `page.HEX`). "O projektu" says the project is independent (the
  maintainer's words); the names of the people behind it waited until 23 Nov.
- **The new pages looked at against the rules** (20 Nov 2026: `poslovnik-clanovi`, `u-proceduri`, a day of
  "Ko koliko govori", `varnice-svi`, the quiz; 320, 390 and 1280 px, both scripts and both themes). None is wider
  than its screen, each has six to eight letter sizes of the scale, no text is under 4.5:1. One page was changed,
  `poslovnik-clanovi`: each row's summary was underlined whole (three lines of underlined text a row on a phone)
  and the list opened on how the count is made. It now opens on its main fact (how many articles, which one
  most; rule 3), each count has a grey bar from zero against the most invoked (rules 4 and 5; grey, as a count
  is no vote), only the article's name is underlined, and an opened row doesn't say its first sentence twice.
  Left as found: on a phone the menu's links are 37-41 px high, the quiz's strip of numbers 34 px and a turn's
  "podeli" 16 px, under rule 7's 44 px.
- **The search page's use is counted, never its words** (20 Nov 2026, the maintainer's decision, before deciding
  on a search by meaning over the laws: Pagefind runs in the browser and nobody knew whether the search is used).
  `pretraga.js` adds to the counter's sums per day, each once per page: `pretraga.trazi` (a search run),
  `pretraga.prazno` (still no result two seconds after the last letter) and `pretraga.klik` (a result opened).
  The words searched for never leave the browser; the method page says so. Read in `GET /pregled` (`uses`).
- **More uses counted, each to answer one question** (20 Nov 2026, the maintainer's choice of four): the field on the
  home page and "Poslanici" (`pretraga.polje`, `-nema`, `-izbor`, `-ceo`: is the name-and-title search enough, or
  do people leave it for the whole text), a recording played on a day page (`sajt.snimak`: is "who spoke when" with
  the recording worth going on with), and a link from the site to the live page (`sajt.mikrofon`). Sums per day,
  once per page, never the words; the method page lists them.
- **The live page has its way on the site** (22 Nov 2026, the maintainer's decision; links from the site to it were
  taken 2 or 3 times a day, the other way 26 to 177). "Uživo" in the menu of every page, its dot red while a sitting
  is on (the same reading as the live bar, at the build). On the home page a strip in the live bar's place, under the
  search on a phone: while a sitting is on, who speaks now (read from the live page's state, as the bar); before
  one, its day and hour; after, the last day with its recording. On every other page, from the day before a
  sitting until it starts, the live bar with its dot grey: "Sutra (Danas) u 10 h: sednica Skupštine". The next
  sitting's start is the Assembly's listing of a sitting convened, or, for the next day of one going on, the
  notice's `pocinje` in `data/obavestenja.json`, written by hand from the Assembly's site
  (`pages_mikrofon.next_start`); the pages carry the hours and the script shows each part only in them
  (`data-show`). Each way counted by where it was taken (`sajt.mikrofon-meni`, `-pocetna`, `-najava`, `-traka`,
  `-poslanik`), to see after the 24 Nov sitting what brings people.
- **The phone's menu is a bar at the bottom, and "Uživo" is its middle** (23 Nov 2026, the maintainer's choice of three:
  "Uživo" was the fifth of six words in a row, 11 px high in Cyrillic at 360 px). Zakoni, Poslanici, the microphone
  (red, `--live`, while a sitting is on: as at the build, and, as that is hourly, the live page asked once a page from
  ten minutes before an announced start to 16 hours after it), Glasaj, and "Još" with the
  rest (a `details`, so it works without the script). It goes away whole while the page is read down and comes back at
  the first move up (tried on a page on the phone, against keeping the microphone and against standing always); 52 px,
  where the old row held 46 px at all times. The head is one row that scrolls away, so a page's own menu (`.page-menu`)
  sticks to the top. In the quiz there is no
  bar until it is answered: its answers stand there. Counted as before (`data-mik="meni"`). On a wide screen
  the menu stays on top, with "Uživo" as a button. The notes' pages keep their own head.
- **The family's look and links** (20 Nov 2026, the maintainer's decision: every site of Javni uvid has the same
  font and base colours, and links the others). The font, the page's base colours in both themes and the scale
  of letter sizes are no longer declared here: they come from `osnova/design/osnova.css` (the copy of
  javni-uvid/osnova's), and `style.css` only gives them this site's names (`--bg: var(--ju-bg)` and the like).
  They were this site's own values before, which the family took as its base, so no page looks different.
  The build serves the two as one `style.css`, the family's first (`family.stylesheet`), so a page still asks
  for one stylesheet; the version in `?v=` counts both. Every page begins with the family's bar (Javni uvid,
  then its sites, this one marked) and its footer has the family's block (the promise, a line on each site),
  written by `family.py` from `osnova/design/sites.json`; the notes' pages have the bar. On a Cyrillic page the
  links lead to the other sites' Cyrillic editions (`data-cir-href`, as for the live page). The live page
  (`live/`) is not changed here. A new site of the family shows after the next copy of `osnova/` and build.

## Design rules

What the pages keep to, from the looks at the site against WCAG 2.2, NN/g, GOV.UK, Stanford's credibility
guidelines, the Trust Project, ProPublica's principles for news graphics and TheyWorkForYou (20 Nov 2026, the
maintainer's request that they be written down "for now": they are working rules, changed as visits and readers
show otherwise, unlike the six principles above). A change to a page is checked against them.

1. **One scale of letter sizes.** A size is a step of the scale (`--t-*`); body text is 16 px; grey is for what is
   secondary. A test refuses a size outside the scale, on the site and on the live page.
2. **Colour means a vote.** Blue is "za", orange "protiv", and nothing else wears them (the exceptions are
   listed above). White text only on colours dark in both themes; any text 4.5:1 or more.
3. **The most important first.** A page says what it is and gives its main fact in the first screen; then the
   reasons, then the details and documents. The home page shows what the site holds by a few examples and
   leaves the lists to their own pages ("do less").
4. **A number never stands alone.** It has what it is counted of, something to compare it with (the convocation
   before, the half of MPs, how many others the same holds for), and a link to how it is computed. The largest
   thing on a page is what tells its subject apart, not what is the same for most.
5. **A trend is drawn, a table is kept.** Where the point is how something changed, columns or bars from zero
   come first, in black and grey, and the table follows (folded when long). No chart without its numbers.
6. **Asked after it is shown.** The visitor votes after what the law changes; a question never precedes what is
   needed to answer it.
7. **The phone first.** Four visits in five are on phones, most on the Cyrillic pages: every change is looked at
   at 320 and 390 px in both scripts, no page is wider than its screen, things to press are 44 px high, and a
   list shows its first rows and a way to the rest.
8. **Everything can be checked.** Each figure links its source and its rule; what a model wrote says so; what was
   corrected is listed. No rating of an MP and no ranking by preference (principle 1).
9. **For every reader.** Keyboard and screen reader reach everything; nothing moves by the clock that the reader
   cannot stop; the visitor is not addressed as a man or a woman.
10. **Measured, then changed.** Visits and the pages' speed are read before a change to how a page is laid out,
    and after it.
11. **What moves a reader stays** (20 Nov 2026, the maintainer: the pages are better with what draws a reader in).
    Faces, names, a speaker's clock, a sentence said in the hall and the groups' colours are kept where they
    lead into the page, and a tidier look is no reason to take them out. The groups' colours are an exception to
    rule 2 on the home page and the live page only: each hue stands apart from blue and orange (the first list's
    is indigo for that reason), the same hues on both pages, a key always names them, and they differ in
    lightness for colour-blind readers. They follow the same rules as everything else: the same for every group
    (principle 1), no judgement in the words beside them, and never the only way a fact is told.

## Visitors' votes ("Glasaj i ti")

- **The counter** (`worker/`, a Cloudflare Worker with D1; README there): a vote is one device's vote on one law or
  bill (`POST /z`), replacing its last; quotes can be marked convincing (`POST /c`); the quiz sends its laws at once.
  Kept: the vote, a hash of a random mark the browser made (with the secret `SALT`), the day, a daily hash of the
  network. No cookies, no addresses. Only items the site lists (`glasanje.json`). No robot check: **watch** opens an
  issue when one network sends most of a law's votes; removing is the maintainer's decision, written on the method
  page. **Uses** (17 Nov 2026, `POST /e`): a sum per day of the quiz's result reached and the share pictures opened,
  shared, copied, saved; nothing beside it. `GET /pregled` shows both. **The live page's uses** (19 Nov 2026,
  the maintainer's request, to see how long people stay and what keeps them): the same sums from
  `mikrofon.zailiprotiv.rs` beside the broadcast's ▶ (`mikrofon.pusti`, `live-page.md`): opened; in view 1, 5, 15, 30 min,
  time out of sight not counted; a recording of the archive played (`mikrofon.snimak`); the agenda, the speaker's
  lines, a share, the day in cards, a way to the site; each at most once per page opened. Same counter and switch
  as `mikrofon.pusti` (`config.VOTES_API`); the page's footer and the method page say so.
- **The page** (`glasaj.html`, `pages_ballot.py`, `listic.js`): the visitor's ballot ("Moj listić", kept in the
  browser only) beside the Assembly's results, the MPs and groups that voted alike, one law picked by a stated rule;
  the newest bill in procedure to vote on, and the next. **The quiz** (`kviz/podelili-salu`, `pages_quiz.py`,
  `glasaj.js`): the laws in `data/quiz.json` (chosen by the maintainer, 13 Nov 2026, each with a plain description;
  the page says so), or by rule without it. **Quizzes by theme** (17 Nov 2026, `kviz/<theme>`): per area of the
  current convocation with five or more laws with votes against, the most divided ten, by the same rule; areas get
  short names (`pages_quiz.THEMES`); Article 97's "other matters" gets none.
- **The quiz keeps a screen's height** (20 Nov 2026): the first reading of the pages' speed (`tools/vitals.py`)
  had the quiz as the one page under the line, its layout shift good in half of the loads. The cause: when one law
  gives way to the next by the clock (not on a tap, so the browser counts it), the note under the quiz jumped up,
  0.31 a time on a phone (0.1 is good). The list now holds the screen's height from the first paint and the strip
  of numbers is in its place before the script, so nothing under the quiz is in sight to jump (0.001 after).
- **The visitor is not addressed as a man** (20 Nov 2026; the MP's card lost its gender on 19 Nov). The question is
  "Kako ti glasaš?" (it was "Kako bi ti glasao?"), a vote cast is "Tvoj glas: za" ("Glasao si za"), and the
  counts speak in the present ("Kao većina u sali glasaš na 4 od 10 zakona") or of the vote ("tvoj glas", in the
  shared text "moj glas"). "Uzdržan" stays: it is the vote's name in the roll calls. New text for the visitor
  keeps to this: the present tense or "tvoj glas", no past participle.
- **The vote is asked after what the law changes** (20 Nov 2026, the maintainer's choice): on a law's page the box
  stood right under the result and asked the visitor to read first what was below it. It now follows "Šta zakon
  menja" and the voices from the debate. The result still stands above it: the page is the record of the vote
  first, and the visitors' sum is no poll, as the box says.
- **Listening counted, and four uses by the hour** (25 Nov 2026, the maintainer: "3 dobro", to the offer "the counter: add
  `mikrofon.slusaj` and hourly sums for `pusti`/`1min`/`5min`"). The live page sent `mikrofon.slusaj` from the button's
  first day (#120), but the counter's list had no such name and refused it (400, silent for the reader), so the sound
  of 24 Nov, its first open day, was not counted; a test now checks the names in `mikrofon.js` too. It is counted as
  `mikrofon.pusti` is, once per page opened. It and `pusti`, `1min`, `5min` are also summed per hour (UTC; the table
  `events_hours`: hour, use, how many, nothing of a reader), to be read beside `tools/watching.py`. **visits** prints
  them (`tools/uses.py`, from `/pregled`, `uses_by_hour`, two weeks); an hour's sum under three is left out by the
  counter itself, as both the overview and the run's log are public. The method page says it all (the maintainer, the
  same day, on the words: "Ništa ne stavljaj na dno stranice. Sve neka ide na metod pa linkuj na jednom mestu"): the
  live page's footer keeps its words, of which "Brojač sajta" is the one link to it; the privacy page no longer says
  "only per day" and points there.

## Search engines

- **Allowed, AI training not** (16–17 Nov 2026): Cloudflare's AI Crawl Control blocks training crawlers and its
  managed robots.txt says so; Googlebot and Bingbot are let through by hand there (Cloudflare
  counts Googlebot as an AI crawler; blocked, Google could read nothing). Our `robots.txt` keeps `/pagefind/` out.
  `tools/blocked.py` (**visits**, `blocked`) shows what Cloudflare stopped and by which rule.
- **Each page:** a title of its own (a long one drops the site's name), a description of its own cut between words
  at 160 characters (`publish.fit_head`), a canonical address, its twin in the other script (`hreflang`, Latin the
  default), large image previews allowed, the place in the site as BreadcrumbList made from its crumbs; the home page
  names the site and its publisher (WebSite, Organization), the data page its downloads (Dataset). A 404 page of its
  own (`noindex`). Favicon also as PNG (Google shows no SVG).
- **An MP's result says what the page holds** (22 Nov 2026): searches for MPs' names showed the site 7th to 12th
  and were hardly ever clicked (in the week to 22 Nov "danijela nikolic" was shown 101 times, not clicked once),
  under a description that was one sentence for all. Now it is the MP's own counts, in the same words and order for
  everyone: the final votes on laws and how they went (za, protiv, then uzdržan, nije prisutan, nije glasao when
  any), the speeches in the hall, the latest group and convocation; what is past 160 characters is cut. The page
  also says who the MP is as schema.org `Person` (name, address, portrait; a sitting MP's office and the Assembly),
  only what the page shows. Read the clicks on MPs' names with **visits** `search` in December.
- **The sitemap** lists every indexed page in both scripts with the day its main text last changed and its pictures;
  **IndexNow** tells Bing and others which pages changed after each publishing (`tools/indexnow.py`; the hashes in
  the build's cache; `indexnow_all` sends all). Search Console and Bing Webmaster Tools are the maintainer's;
  `tools/search.py` (**visits**, `search`) reads Search Console with a service account key in `GSC_KEY`.
- **Which pages Google takes in, by kind** (20 Nov 2026): Search Console's first report counted 3,252 pages
  "crawled, currently not indexed" and names them only on its own pages. `search.py --inspect N` (**visits**,
  `inspect`) asks the URL Inspection API about N addresses of each kind of page (a law, an MP, an MP's votes, …) in
  each script, spread evenly over the sitemap, and sums what Google says of each kind, with the canonical address
  it chose where that is another page. 8 a kind is some 200 of the property's 2,000 a day. Each of **visits**'
  readings now runs when another failed (that day a key not set right stopped the rest).
- **The pages to find, the rest linked from them** (22 Nov 2026): the first `inspect` (8 a kind) found the home
  pages, MPs, laws, bills and sittings mostly indexed, and an MP's every vote (`-glasovi`) and every speech
  (`-govori`) and the weeks mostly "discovered, not crawled": 3,756 of the sitemap's 10,954 pages, a third of what
  Google was asked to read, for a domain ten days old that it reads slowly. The three get `noindex` and so leave
  the sitemap: the MP's page, which links them, is what a name is searched for; a week's laws and sittings have
  pages of their own. They stay linked and open; links on them are followed. Read the effect with `inspect` in
  December: whether the MPs' and laws' pages leave "discovered" sooner.

- **The site searched for by its name** (23 Nov 2026, the maintainer saw it for "zailiprotiv" and not for "za ili
  protiv"). Search Console to 20 Nov: "za ili protiv" 211 times shown, 163 clicks, position 2.2, the same place as
  "zailiprotiv" (140, 112, 2.2), 184 of the 211 in Serbia; 21-23 Nov had too few of either to tell. `search.py`
  (**visits**, `search`) now also gives the searches for the name day by day to the newest day, which page and from
  where. The home page's structured data names the other forms (`publish.NAMES`: Google takes a list, the preferred
  first) beside the domain. The rest is outside the pages: a phrase in common use, a domain two weeks old; links and
  mentions under the name (profiles in `sameAs`) are what tells Google it is a name.
  The maintainer's two pictures of 23 Nov said it the other way round: "za ili protiv" gave the Cyrillic home page
  first of the plain results, while "zailiprotiv" was corrected by Google to "za ili protiv" and then showed the
  live page 8th. The project's Instagram (its only profile) is in `sameAs` and in both footers (`rel="me"`, a plain link). All four home pages are in the index, read that morning (`search.py` `home_pages`). Google titles
  the home page by its h1, which has no name in it; the h1 is the maintainer's choice and waits for them.

## Support

- **"Podrži": readers' support by bank transfer** (22 Nov 2026, the maintainer's decision, after readers asked for
  donations; ads ruled out by principle 5). `podrzi.html` (`pages_support.py`, `support.html`) from `settings.json`
  `support` (account, payee and place, payment code 289, purpose, amounts, an optional PayPal link): three NBS IPS
  QR codes (200, 500 and 1000 din since 23 Nov 2026, 300 before; the payer can change the amount; the amount is mandatory in the NBS's form),
  drawn as SVG in the page (nothing from elsewhere) and kept as PNG to load from a phone's gallery, and the payment
  order's fields. The codes' text checked with the NBS's validator (text and image) on 22 Nov 2026. The page says
  the account is the maintainer's own, that support buys nothing (principle 1) and that who paid is not published.
  Linked from the home page (a box before the laws), the footer's "Projekat" column, the page at mikrofon while the
  service is down, and the live page (`support_cta`). The Cyrillic edition leaves a payment code's SVG as drawn
  (`cyrillic.page`). Options weighed that day: Stripe does not serve Serbia; Ko-fi, Liberapay pay out through
  PayPal only.
- **"Podrži" on top, and a card worth a look** (22 Nov 2026, the maintainer): the header's tools have "Podrži" (a heart,
  its word on a wide screen) beside the search; the home page's card has the site's mark, the promise (free, no ads,
  nothing from others), a button and the amounts, with no colour but the mark's (design rule 2).
- **"O projektu" names who makes the site** (23 Nov 2026, the maintainer: "ubaci o projektu i moje ime"): Marko
  Pomorišac, as "Podrži" and "Politika o privatnosti" already did; until then it named the organisation only.
- **Časlav in a heart beside "Podrži"** (23 Nov 2026, the maintainer: "stavi obavezno Časlava umesto crnog srca"): the
  live page's picture (`caslav-srce.webp`, 6 KB) in the head of every page, in place of the black heart. On a phone the
  script's switch is "Ћир" / "Lat", as on the live page: at 360 px in Cyrillic the heart stood over the site's name.
  The word "Podrži" beside it on a phone too where it fits (Latin from 360 px, Cyrillic from 400).
- **"Podrži": who makes the site, and what it costs** (23 Nov 2026, the maintainer's request and photos): the page
  names the maintainer with his photo and the cat Časlav's (part of every gift buys his food), and lists what the money
  pays for, with a figure only where it is known (Cloudflare's 5 $ a month). The photos are cut so that no screen's
  text shows (another person's name was on one) and saved anew, without their metadata (place, phone). Every mail of
  the day's summary ends with one line asking for support; nothing is locked behind it (the maintainer's decision).
