"""Following a sitting MP by mail: the counter that keeps it sealed (worker/prati.js), the service that sends it
(live/uzivo/prati.py), and the sign-up on the MP's page."""
import base64
import json
import re
import shutil
import subprocess
import sys
import threading
import urllib.error
from datetime import date, datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "live"))

from uzivo import mejl, prati, pretplata  # noqa: E402

KEY = base64.b64encode(bytes(range(32))).decode()
TZ = pretplata.TZ


def node_with_sqlite() -> bool:
    if not shutil.which("node"):
        return False
    return subprocess.run(["node", "--no-warnings", "-e", "require('node:sqlite')"], capture_output=True).returncode == 0


needs_worker = pytest.mark.skipif(not node_with_sqlite(), reason="needs a Node with node:sqlite, as the worker's code is JavaScript over D1")

# The worker's own code over its own schema, in memory. Each test's steps come after this.
WORKER = r"""
import { DatabaseSync } from "node:sqlite";
import { readFileSync } from "node:fs";
import { handle, cleanup, count, confirmMail, pad } from %(module)s;
const db = new DatabaseSync(":memory:");
db.exec(readFileSync(%(schema)s, "utf8"));
const made = (sql, a = []) => ({ sql, a,
  bind: (...b) => made(sql, b),
  first: async () => db.prepare(sql).get(...a) || null,
  all: async () => ({ results: db.prepare(sql).all(...a) }),
  run: async () => ({ meta: { changes: Number(db.prepare(sql).run(...a).changes) } }) });
const DB = { prepare: (sql) => made(sql), batch: async (xs) => { const out = []; for (const x of xs) out.push(await x.run()); return out; } };
const mails = []; let broken = false, listCalls = 0;
globalThis.fetch = async () => { listCalls++; return new Response(JSON.stringify({ "anic-ana": ["Ana Anić", "Ана Анић"], "peric-pera": ["Pera Perić", "Пера Перић"],
  "jovic-jova": ["Jova Jović", "Јова Јовић"], "a-b": ["A B", "А Б"], "c-d": ["C D", "Ц Д"], "e-f": ["E F", "Е Ф"], "g-h": ["G H", "Г Х"] })); };
const env = { DB, SALT: "so", PUSH_TOKEN: "t", MEJL_JAVNI: process.argv[1],
  MEJL: { send: async (m) => { if (broken) throw Object.assign(new Error("x"), { code: "E_X" }); mails.push(m); } } };
const SITE = "https://zailiprotiv.rs", SELF = "https://glasovi.zailiprotiv.rs";
const same = async (a, b) => a === b;
const ask = (path, method = "GET", body, headers = {}) => {
  const req = new Request(SELF + path, { method, body, headers: { "content-type": "application/x-www-form-urlencoded", ...headers } });
  return handle(req, env, new URL(req.url).pathname, headers.origin || "", same);
};
const follow = (sta, adresa = "citalac@primer.rs", more = "&js=1") =>
  ask("/m/prati", "POST", `adresa=${encodeURIComponent(adresa)}&sta=${sta}${more}`, { origin: SITE });
const token = (m) => m.text.match(/potvrdi\?k=([0-9a-f]{32})/)[1];
const confirm = (m) => ask("/m/prati/potvrdi", "POST", "k=" + token(m));
const list = async () => (await (await ask("/m/prati/spisak", "GET", undefined, { authorization: "Bearer t" })).json()).pratioci;
const n = (table) => db.prepare("SELECT COUNT(*) AS n FROM " + table).get().n;
const at = (url) => url.replace(SELF, "");
const later = () => db.prepare("UPDATE pratioci SET dan = '2000-01-01'").run();  // another day
const out = {};
%(steps)s
console.log(JSON.stringify(out));
"""


def worker(steps: str) -> dict:
    script = WORKER % {"module": json.dumps((ROOT / "worker" / "prati.js").as_uri()), "schema": json.dumps(str(ROOT / "worker" / "schema.sql")), "steps": steps}
    ran = subprocess.run(["node", "--no-warnings", "--input-type=module", "-e", script, json.dumps(pretplata.public_jwk(KEY))],
                         capture_output=True, text=True, encoding="utf-8")
    assert ran.returncode == 0, ran.stderr
    return json.loads(ran.stdout)


@needs_worker
def test_nothing_the_counter_keeps_says_who_follows_whom():
    out = worker("""
await follow("anic-ana"); await follow("peric-pera", "duza.adresa.jednog.citaoca@negde.primer.rs");
await confirm(mails[0]); await confirm(mails[1]);
out.rows = JSON.stringify([db.prepare("SELECT * FROM pratioci").all(), db.prepare("SELECT * FROM prati").all()].flat().map((r) => Object.values(r)));
out.lengths = [db.prepare("SELECT DISTINCT length(sta) AS n FROM prati").all().length, db.prepare("SELECT DISTINCT length(adresa) AS n FROM pratioci").all().length];
out.columns = db.prepare("SELECT name FROM pragma_table_info('prati')").all().map((r) => r.name).concat(db.prepare("SELECT name FROM pragma_table_info('pratioci')").all().map((r) => r.name));
out.list = await list(); out.count = await count(env); out.subjects = mails.map((m) => m.subject); out.mail = mails[0];
out.long = pad("x".repeat(500), 416);
""")
    for said in ("anic", "peric", "Ana", "Pera", "citalac", "primer"):
        assert said not in out["rows"]
    assert out["lengths"] == [1, 1]  # padded: neither the name's nor the address's length shows
    assert set(out["columns"]) == {"id", "citalac", "sta", "prijava", "potvrda", "kod", "kljuc", "adresa", "cir", "dan", "n"}
    assert out["count"] == {"citalaca": 2, "ceka": 0}  # in all, never by MP
    assert pretplata.unseal(KEY, out["list"][0]["prati"][0]["sta"]).rstrip().split("|")[0] == "p"
    opened = {pretplata.unseal(KEY, r["adresa"]).rstrip(): pretplata.unseal(KEY, r["prati"][0]["sta"]).rstrip() for r in out["list"]}
    assert opened["citalac@primer.rs"] == "p|anic-ana|Ana Anić"
    assert out["subjects"] == ["Potvrdi praćenje: klikni na dugme u ovom mejlu"] * 2  # no name in a subject
    assert "Ana Anić" in out["mail"]["html"] and "Koga pratiš može da govori o tvom političkom mišljenju." in out["mail"]["html"]
    assert "Prekidaš kad hoćeš, dugmetom u svakom mejlu: tada se odmah briše." in out["mail"]["text"]
    assert "<img" not in out["mail"]["html"] and out["long"] is None


@needs_worker
def test_each_following_is_confirmed_by_a_press_in_a_mail_that_names_it():
    out = worker("""
out.first = (await follow("anic-ana")).status;
const opened = await (await ask("/m/prati/potvrdi?k=" + token(mails[0]))).text();   // a scanner opens the link
out.button = opened.includes('<form method="post" action="/m/prati/potvrdi">') && opened.includes("Poslednji korak");
out.opened = (await list()).length;
out.second_unconfirmed = [(await follow("peric-pera")).status, mails.length];        // once a day to an address not confirmed
out.done = (await (await confirm(mails[0])).text()).includes("Praćenje važi");
out.again = (await (await confirm(mails[0])).text()).includes("Link je istekao");     // a link confirms once
out.second = [(await follow("peric-pera")).status, mails.length];
out.before = (await list())[0].prati.length;
await confirm(mails[1]);
const all = await list();
out.after = [all.length, all[0].prati.length, all[0].prati.every((p) => /^\\d{4}-\\d\\d-\\d\\d$/.test(p.od))];
for (const s of ["jovic-jova", "a-b", "c-d", "e-f", "g-h"]) await follow(s);
out.day = mails.length;                                                             // a confirmed one: 5 a day in all
out.unknown = (await follow("niko-nikic")).status;                                   // not a sitting MP
out.path = (await follow("../x")).status;
out.bad = (await follow("anic-ana", "nije adresa")).status;
out.kept = db.prepare("SELECT prijava FROM prati WHERE potvrda IS NOT NULL").all().every((r) => r.prijava.length === 10);
""")
    assert out["first"] == 200 and out["button"] and out["opened"] == 0
    assert out["second_unconfirmed"] == [200, 1]  # the same answer, and no mail
    assert out["done"] and out["again"] and out["second"] == [200, 2] and out["before"] == 1 and out["after"] == [1, 2, True]
    assert out["day"] == 5 and out["unknown"] == out["path"] == out["bad"] == 400
    assert out["kept"]  # once confirmed, the day alone


@needs_worker
def test_one_is_ended_or_all_or_everything_and_the_row_goes_at_once():
    out = worker("""
db.prepare("INSERT INTO mejl (id, kljuc, adresa, cir, prijava, potvrda) SELECT 'm1', 'x', 'y', 0, 'z', '2026-11-25'").run();
await follow("anic-ana"); await confirm(mails[0]);
await follow("peric-pera"); await confirm(mails[1]);
await follow("anic-ana"); await confirm(mails[2]);                                    // the same MP once more
let [r] = await list();
const page = await (await ask(at(r.prati[0].kraj))).text();
out.scanned = [n("prati"), page.includes("Prestani da pratiš") && page.includes('method="post"')];
out.forged = (await ask(at(r.prati[0].kraj).replace(/k=./, "k=" + (r.prati[0].kraj.includes("k=0") ? "1" : "0")), "POST", "strana=1"), n("prati"));
const two = r.prati[0].kraj + "&" + r.prati[2].kraj.split("?")[1];
const gone = await (await ask(at(two), "POST", "strana=1")).text();
out.one = [n("prati"), gone.includes("Praćenje je obrisano"), n("pratioci")];
r = (await list())[0];
out.cross = (await ask(at(r.sve).replace("/sve", "/svega"), "POST", "strana=1"), n("pratioci"));   // one link's code is not another's
out.oneclick = [(await ask(at(r.sve), "POST", "List-Unsubscribe=One-Click")).status, n("prati"), n("pratioci"), n("mejl")];
later(); await follow("anic-ana"); await confirm(mails.at(-1));
db.prepare("UPDATE mejl SET kljuc = (SELECT kljuc FROM pratioci)").run();
r = (await list())[0];
out.joined = r.mejl;
out.everything = [(await (await ask(at(r.svega), "POST", "strana=1")).text()).includes("Tvoja adresa je obrisana"), n("prati"), n("pratioci"), n("mejl")];
""")
    assert out["scanned"] == [3, True] and out["forged"] == 3
    assert out["one"] == [1, True, 1]  # both rows of the MP asked for twice
    assert out["cross"] == 1
    assert out["oneclick"] == [204, 0, 0, 1]  # the mail reader's own button ends what is followed, and leaves the summary
    assert out["joined"] == "m1" and out["everything"] == [True, 0, 0, 0]


@needs_worker
def test_floods_failed_mails_and_other_pages():
    out = worker("""
broken = true;
out.failed = [(await follow("anic-ana")).status, n("prati"), n("pratioci")];
broken = false;
out.then = [(await follow("anic-ana")).status, mails.length];
out.origin = (await ask("/m/prati", "POST", "adresa=a%40b.rs&sta=anic-ana", { origin: "https://drugde.rs" })).status;
out.token = (await ask("/m/prati/spisak", "GET", undefined, { authorization: "Bearer x" })).status;
env.LIMIT = { limit: async () => ({ success: false }) };
out.limited = (await follow("anic-ana", "c@d.rs")).status;
delete env.LIMIT;
db.prepare("UPDATE prati_dani SET n = 300").run();
out.day = [(await follow("anic-ana", "e@f.rs")).status, mails.length, n("pratioci")];
db.prepare("DELETE FROM prati_dani").run();
await confirm(mails[0]);
for (let i = 0; i < 25; i++) { later(); await follow("anic-ana"); }
out.together = n("prati");
out.noscript = await (await follow("anic-ana", "g@h.rs", "&pismo=cir")).text();
out.cir = mails.at(-1);
db.prepare("UPDATE prati SET prijava = '2026-01-01T00:00:00Z' WHERE potvrda IS NULL").run();
out.expired = (await (await ask("/m/prati/potvrdi?k=" + token(out.cir))).text());
await cleanup(env);
out.cleaned = [n("prati"), n("pratioci")];
""")
    assert out["failed"] == [502, 0, 0] and out["then"] == [200, 1]  # a mail that did not go leaves nothing, and may be asked again
    assert out["origin"] == 403 and out["token"] == 403 and out["limited"] == 429
    assert out["day"] == [429, 1, 1] and out["together"] == 20
    assert "Провери сандуче" in out["noscript"] and 'href="https://zailiprotiv.rs/cir/"' in out["noscript"]
    assert out["cir"]["subject"] == "Потврди праћење: кликни на дугме у овом мејлу" and "Ана Анић" in out["cir"]["html"]
    assert "Линк је истекао" in out["expired"] and out["cleaned"] == [1, 1]


def test_the_workers_words_are_written_in_one_script_each():
    js = (ROOT / "worker" / "prati.js").read_text(encoding="utf-8")
    said = js[js.index("const SAID"):js.index("// A page of the worker's own")]
    lat, cir = said.split("  cir: {")
    assert not re.search(r"[Ѐ-ӿ]", lat) and not mejl.mixed_words(cir)
    main = (ROOT / "worker" / "worker.js").read_text(encoding="utf-8")
    assert "prati.cleanup(env)" in main and "prati: await prati.count(env)" in main
    assert main.index('path === "/m/prati"') < main.index('if (path === "/m" ||')


# The service.

DAY, NEXT = date(2026, 11, 24), datetime(2026, 11, 25, 9, 5, tzinfo=TZ)
FACTS = {"anic-ana": {"ime": "Anić Ana"}, "peric-pera": {"ime": "Perić Pera"}, "cukic-caca": {"ime": "Čukić Caca"}}


def at(h: int, m: int = 0, day: date = DAY) -> int:
    return int(datetime(day.year, day.month, day.day, h, m, tzinfo=TZ).timestamp())


def turn(slug, od, do, izvor=None, okvira=9):
    return {"ime": slug, "adresa": slug, "od": od, "do": do, "okvira": okvira, **({"izvor": izvor} if izvor else {})}


def sealed(slug, name, rid="1", od="2026-11-20"):
    return {"id": rid, "sta": f"p|{slug}|{name}   ", "od": od, "kraj": f"https://glasovi.zailiprotiv.rs/m/prati/kraj?i={rid}&k=k{rid}"}


def row(rid, to, *follows, cir=False, summary=""):
    return {"id": rid, "adresa": to + "  ", "cir": cir, "mejl": summary, "sve": f"https://x/sve?i={rid}&k=1", "svega": f"https://x/svega?i={rid}&k=1",
            "prati": list(follows)}


def test_only_a_speech_read_from_the_caption_is_told():
    said = prati.spoken({"govori": [
        turn("anic-ana", at(10), at(10, 6)), turn("anic-ana", at(10, 7), at(10, 9)),      # a pause in one speech
        turn("peric-pera", at(11), at(11, 4), "glas"), turn("peric-pera", at(12), at(12, 4), "prepis"),
        turn("cukic-caca", at(13), at(13, 2), "potpis"), turn("cukic-caca", at(14), at(14, 1), okvira=1),
        turn("", at(15), at(15, 5)), turn("anic-ana", at(16), at(16, 1))]})
    assert set(said) == {"anic-ana", "cukic-caca"}
    assert said["anic-ana"] == [(at(10), at(10, 9)), (at(16), at(16, 1))] and len(said["cukic-caca"]) == 1
    assert prati.spoken(None) == {}


def test_two_speeches_are_two_when_somebody_spoke_between_them():
    said = prati.spoken({"govori": [turn("anic-ana", at(10), at(10, 1)), turn("peric-pera", at(10, 1), at(10, 2), "glas"), turn("anic-ana", at(10, 2), at(10, 3))]})
    assert len(said["anic-ana"]) == 2


@pytest.fixture
def service(tmp_path, monkeypatch):
    """The sender with a day of two speakers; what the counter was asked to send, and how it answers."""
    monkeypatch.setattr(pretplata.config, "MAIL_KEY", KEY)
    monkeypatch.setattr(pretplata.config, "MAIL_EDITOR", "urednik@primer.rs")
    monkeypatch.setattr(pretplata.config, "PUSH_TOKEN", "t")
    monkeypatch.setattr(pretplata.config, "PUBLIC_URL", "https://mikrofon.zailiprotiv.rs/")
    monkeypatch.setattr(prati.config, "FOLLOW_ALONE", False)
    monkeypatch.setattr(pretplata, "unseal", lambda key, s: s)
    monkeypatch.setattr(pretplata, "deadline", lambda d: datetime(2026, 11, 25, 12, 0, tzinfo=TZ) if d == DAY else datetime(2000, 1, 1, tzinfo=TZ))

    class Clock(datetime):
        now_ = NEXT

        @classmethod
        def now(cls, tz=None):
            return cls.now_
    monkeypatch.setattr(prati, "datetime", Clock)

    class Days:
        facts = FACTS
        kept = {"2026-11-24": {"govori": [turn("anic-ana", at(10, 42), at(10, 48)), turn("peric-pera", at(11, 20), at(11, 25)),
                                          turn("anic-ana", at(13, 5), at(13, 7))]}}

        def days_kept(self):
            return sorted(self.kept)

        def record(self, day):
            return self.kept.get(day)

    class Box:
        people: list = []
        sent: list = []
        answer = None
        clock = Clock

    box = Box()
    box.sent, box.people = [], []

    def call(path, body=None):
        if path == "/m/prati/spisak":
            return {"pratioci": box.people}
        if path == "/m/spisak":
            return {"primaoci": [{"id": p["mejl"], "adresa": p["adresa"].strip(), "odjava": "https://x/odjava"} for p in box.people if p["mejl"]]
                    + [{"id": "sam", "adresa": "samo.sazetak@primer.rs", "odjava": "https://x/odjava"}]}
        wrong = box.answer(body["poruke"]) if box.answer else {}
        box.sent += [m for i, m in enumerate(body["poruke"]) if i not in wrong]
        return {"poslato": len(body["poruke"]) - len(wrong), "greske": [{"i": i, "code": c} for i, c in wrong.items()]}
    monkeypatch.setattr(pretplata, "_call", call)
    box.days = Days()
    built = []

    def build(day, cyr, out, following=None):
        built.append(following)
        return mejl.Mail("Skupština", "dan " + out, "<html><body>dan" + (following[0] if following else "") + "</body></html>")
    box.built = built
    box.mailer = pretplata.Mailer(tmp_path, build)
    box.follow = prati.Following(box.days, box.mailer, threading.Event())
    box.state = lambda: json.loads((tmp_path / "prati" / "stanje.json").read_text(encoding="utf-8"))
    box.click = lambda now=NEXT: box.follow.to_all(now.date(), prati.code(now.date()), now)
    return box


def readers(box, n=1, slug="anic-ana", name="Ana Anić"):
    box.people = [row(f"r{i}", f"c{i}@primer.rs", sealed(slug, name, f"p{i}")) for i in range(n)]


def test_the_maintainer_first_and_the_rest_on_his_click_that_morning(service):
    readers(service, 2)
    assert not service.follow.step(datetime(2026, 11, 25, 8, 59, tzinfo=TZ))
    assert service.follow.step(NEXT) and not service.follow.step(NEXT)  # once
    [m] = service.sent
    assert m["to"] == "urednik@primer.rs" and "Spremno: 2" in m["html"] and "Ana Anić (2)" in m["html"] and "Pera Perić (1)" in m["html"]
    assert "c0@primer.rs" not in m["html"] + m["text"]
    assert service.follow.to_all(DAY, prati.code(DAY), NEXT)[0] == "kasno"
    assert service.follow.to_all(NEXT.date(), "x" * 32, NEXT)[0] == "kod"
    assert service.follow.to_all(NEXT.date(), pretplata.link_key(NEXT.date()), NEXT)[0] == "kod"  # not the summary's code
    assert service.click(NEXT.replace(hour=13))[0] == "kasno"
    assert service.click() == ("ok", 2) and service.click() == ("ok", 0)
    assert [m["to"] for m in service.sent[1:]] == ["c0@primer.rs", "c1@primer.rs"]
    assert service.sent[1]["odjava"] == "https://x/sve?i=r0&k=1"
    assert "@" not in json.dumps(service.state()) and "anic" not in json.dumps(service.state())  # nothing of who or whom


def test_by_itself_only_when_it_is_set_to(service, monkeypatch):
    readers(service, 1)
    monkeypatch.setattr(prati.config, "FOLLOW_ALONE", True)
    assert service.follow.step(NEXT) and [m["to"] for m in service.sent] == ["c0@primer.rs"]
    assert not service.follow.step(NEXT) and len(service.sent) == 1


def test_the_mail_is_the_plain_list_with_no_name_in_its_subject_and_nothing_loaded(service):
    service.people = [row("r", "c@primer.rs", sealed("peric-pera", "Pera Perić", "p1"), sealed("anic-ana", "Ana Anić", "p2"), sealed("cukic-caca", "Caca Čukić", "p3"),
                          sealed("anic-ana", "Ana Anić", "p4"))]
    service.click()
    [m] = service.sent
    assert m["subject"] == "Ono što pratiš: utorak, 24. novembar"
    h = m["html"]
    assert h.index(">Ana Anić<") < h.index(">Pera Perić<") and "govori u sali</span>" not in h and "govori u sali, 2" in h
    assert f"https://mikrofon.zailiprotiv.rs/iz-mejla/govor/{at(10, 42)}" in h and "10.42 · oko 6 min" in h
    assert "Po natpisu na prenosu. Prepoznavanje može da pogreši; merodavne su stenografske beleške." in h
    assert "<img" not in h and "src=" not in h and "foto/" not in h and "podrzi" not in h and "model" not in h
    assert not re.search(r"https://(?!zailiprotiv\.rs/|mikrofon\.zailiprotiv\.rs/|glasovi\.zailiprotiv\.rs/|x/)", h)
    assert h.count(">Prestani da pratiš<") == 3 and "Caca Čukić" in h  # everything followed, also who did not speak
    assert "kraj?i=p2&amp;k=kp2&amp;i=p4&amp;k=kp4" in h  # an MP asked for twice ends at once
    assert "Prestani sve da pratiš" in h and "Odjavi me sa svega" in h and "c@primer.rs" not in h
    assert m["text"].count("Prestani da pratiš: ") == 3
    service.people[0]["cir"], service.people[0]["id"] = True, "r2"
    service.click()
    c = service.sent[-1]
    assert c["subject"] == "Оно што пратиш: уторак, 24. новембар" and "Ана Анић" in c["html"] and "/cir/iz-mejla/govor/" in c["html"]
    assert not mejl.mixed_words(re.sub(r"<[^>]+>|https?://\S+", " ", c["html"] + c["text"]).replace("kontakt@zailiprotiv.rs", ""))


def test_the_links_are_the_same_for_every_reader(service):
    readers(service, 2)
    service.click()
    links = [set(re.findall(r'href="(https://(?:mikrofon\.)?zailiprotiv\.rs/[^"]+)"', m["html"])) for m in service.sent]
    assert links[0] == links[1] and len(links[0]) >= 5


def test_nobody_is_told_twice_and_nothing_old(service):
    readers(service, 1)
    assert service.click() == ("ok", 1)
    service.clock.now_ = later = NEXT.replace(day=26)
    assert not service.follow.step(later)  # nothing new: no mail to anybody
    service.days.kept["2026-11-25"] = {"govori": [turn("anic-ana", at(9, day=date(2026, 11, 25)), at(9, 3, date(2026, 11, 25)))]}
    assert service.click(later) == ("ok", 1)
    assert "Ono što pratiš: sreda, 25. novembar" == service.sent[-1]["subject"] and "10.42" not in service.sent[-1]["html"]
    service.people = [row("nov", "n@primer.rs", sealed("anic-ana", "Ana Anić", "p9", od="2026-11-26"))]
    service.clock.now_ = NEXT.replace(day=27)
    assert service.click(NEXT.replace(day=27)) == ("ok", 0)  # asked for after she spoke
    service.people = [row("kasni", "k@primer.rs", sealed("peric-pera", "Pera Perić", "p8"))]
    service.clock.now_ = NEXT.replace(day=28)
    assert service.click(NEXT.replace(day=28)) == ("ok", 0)  # four days after


def test_a_call_that_may_have_sent_is_not_sent_again_and_one_that_did_not_is(service):
    readers(service, 25)

    def timeout(messages):
        raise TimeoutError("timed out")
    service.answer = timeout
    assert service.click()[0] == "deo"
    service.answer = None
    assert service.click() == ("ok", 5) and len(service.sent) == 5  # the first twenty may have it

    readers(service, 3)
    for i, p in enumerate(service.people):
        p["id"] = f"n{i}"

    def refused(messages):
        raise urllib.error.HTTPError("u", 429, "limit", None, None)
    service.answer = refused
    assert service.click() == ("deo", 0)
    service.answer = lambda messages: {1: "E_RECIPIENT_SUPPRESSED"}
    assert service.click() == ("deo", 2)
    service.answer = None
    assert service.click() == ("ok", 0)  # the refused one is not tried again that day
    service.clock.now_ = NEXT.replace(day=26)
    assert service.click(NEXT.replace(day=26)) == ("ok", 1)  # nor is it taken for told


def test_who_has_the_summary_too_gets_one_mail_and_waits_for_it_until_noon(service):
    service.people = [row("r1", "oba@primer.rs", sealed("anic-ana", "Ana Anić"), summary="s1"), row("r2", "samo@primer.rs", sealed("anic-ana", "Ana Anić", "2"))]
    service.follow.step(NEXT)
    assert "Spremno: 1; čekaju sažetak dana: 1" in service.sent[0]["html"]
    assert service.click() == ("ok", 1) and service.sent[-1]["to"] == "samo@primer.rs"


def test_the_summary_carries_what_its_reader_follows_and_then_no_mail_of_its_own_goes(service, monkeypatch):
    monkeypatch.setattr(pretplata, "deadline", lambda d: datetime(2999, 1, 1, tzinfo=TZ))
    service.people = [row("r1", "oba@primer.rs", sealed("anic-ana", "Ana Anić"), summary="s1")]
    assert service.mailer.to_all(DAY, pretplata.link_key(DAY)) == ("ok", 2)
    by = {m["to"]: m["html"] for m in service.sent}
    assert "Ono što pratiš" in by["oba@primer.rs"] and "Prestani da pratiš" in by["oba@primer.rs"] and "Ono što" not in by["samo.sazetak@primer.rs"]
    assert service.built.count(None) == 2  # the first for the check, and the reader who follows nobody: called as before
    assert service.click() == ("ok", 0)


def test_at_noon_the_one_who_waited_gets_it_without_another_click(service):
    service.people = [row("r1", "oba@primer.rs", sealed("anic-ana", "Ana Anić"), summary="s1")]
    assert service.click() == ("ok", 0)
    assert not service.follow.step(NEXT.replace(hour=11))
    assert service.follow.step(NEXT.replace(hour=12, minute=1)) and service.sent[-1]["to"] == "oba@primer.rs"
    assert service.sent[-1]["subject"].startswith("Ono što pratiš")


def test_the_summary_goes_when_the_counter_has_no_list_of_followers(service, monkeypatch):
    monkeypatch.setattr(pretplata, "deadline", lambda d: datetime(2999, 1, 1, tzinfo=TZ))

    def broken():
        raise urllib.error.HTTPError("u", 405, "method", None, None)
    monkeypatch.setattr(service.follow, "followers", broken)
    assert service.mailer.to_all(DAY, pretplata.link_key(DAY)) == ("ok", 1) and service.built == [None, None]


def test_a_summary_that_surely_did_not_go_leaves_the_reader_to_be_told(service, monkeypatch):
    monkeypatch.setattr(pretplata, "deadline", lambda d: datetime(2999, 1, 1, tzinfo=TZ))
    service.people = [row("r1", "oba@primer.rs", sealed("anic-ana", "Ana Anić"), summary="s1")]
    service.answer = lambda messages: {i: "E_DELIVERY_FAILED" for i, m in enumerate(messages) if m["to"] == "oba@primer.rs"}
    assert service.mailer.to_all(DAY, pretplata.link_key(DAY)) == ("deo", 1)
    service.answer = None
    assert service.mailer.to_all(DAY, pretplata.link_key(DAY)) == ("ok", 2)
    assert "Ono što pratiš" in service.sent[-1]["html"]


SUMMARY = {"naslov": "Jedna odluka", "kratko": "Kratko.", "odluke": [{"vreme": "10:50", "sta": "Usvojeno."}],
           "tok": [{"vreme": "10:00", "sta": "Počelo"}], "govornici": [{"ime": "Ana Anić", "lista": "Lista", "o_cemu": "O zakonu."}]}


@pytest.mark.parametrize("cyr", [False, True])
def test_the_days_mail_is_byte_for_byte_the_same_for_who_follows_nobody(cyr):
    """Against what the mail was before following was added: the same arguments, with the new one left out, None, and its
    place in the mail taken out of one that has it."""
    plain = mejl.build(DAY, SUMMARY, cyr=cyr, unsubscribe="https://x/odjava", other_script="https://x/")
    assert mejl.build(DAY, SUMMARY, cyr=cyr, unsubscribe="https://x/odjava", other_script="https://x/", following=None) == plain
    card = ("<tr><td>KARTICA</td></tr>", ["KARTICA", ""])
    has = mejl.build(DAY, SUMMARY, cyr=cyr, unsubscribe="https://x/odjava", other_script="https://x/", following=card)
    assert has.subject == plain.subject and has.html.replace(card[0], "") == plain.html and has.text.replace("KARTICA\n\n", "") == plain.text
    assert has.html.count("KARTICA") == 1


def test_a_followed_mps_address_is_theirs_even_once_it_has_changed():
    f = prati.Followed("anic-ana", "Ana Anić", DAY, ("k",))
    assert prati.whose(f, FACTS) == "anic-ana"
    assert prati.whose(f, {"anic-ana-1970": {"ime": "Anić Ana"}}) == "anic-ana-1970"
    assert prati.whose(f, {"anic-ana-1970": {"ime": "Anić Ana"}, "anic-ana-1980": {"ime": "Anić Ana"}}) == "anic-ana"  # two of the name: nobody


def test_what_cannot_be_opened_is_left_out(monkeypatch):
    monkeypatch.setattr(pretplata, "unseal", lambda key, s: s if s != "tudje" else 1 / 0)
    good = row("a", "a@b.rs", sealed("anic-ana", "Ana Anić"))
    assert [p.id for p in prati.opened([good, {**good, "id": "b", "adresa": "tudje"}, {"id": "c"}, {**good, "id": "d", "prati": []},
                                        {**good, "id": "e", "prati": [{**sealed("x", "X"), "sta": "g|grupa|Grupa"}]}])] == ["a"]


def test_the_service_never_logs_or_keeps_what_it_opened():
    src = (ROOT / "live" / "uzivo" / "prati.py").read_text(encoding="utf-8")
    for line in re.findall(r"log\.\w+\([^\n]+", src):
        assert not re.search(r"(?<!type\()exc\)", line) and "p." not in line and ".to" not in line and "slug" not in line, line
    assert "log.exception" not in src  # a traceback shows values


def test_a_speech_from_a_mail_leads_to_the_speech_and_an_earlier_days_to_the_mps_page(monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from uzivo import deljenje, main
    c = TestClient(main.app, follow_redirects=False)
    to = lambda p: (lambda x: (x.status_code, x.headers.get("location")))(c.get(p))  # noqa: E731
    monkeypatch.setattr(deljenje.time, "time", lambda: at(20))
    assert to(f"/iz-mejla/govor/{at(10, 42)}") == (302, f"/govor/{at(10, 42)}#iz-mejla")
    assert to(f"/cir/iz-mejla/govor/{at(10, 42)}") == (302, f"/cir/govor/{at(10, 42)}#iz-mejla")
    for bad in ("abc", "1", "%2F%2Fevil.example"):
        assert to("/iz-mejla/govor/" + bad)[1] in ("/", None)
    monkeypatch.setattr(main.tracker, "snapshot", lambda now=None: {"danas": []})
    monkeypatch.setattr(main.tracker, "waiting", {"dani": []})
    monkeypatch.setattr(main.tracker, "record", lambda day: {"govori": [turn("anic-ana", at(10, 42), at(10, 48)), turn("../x", at(12), at(13))]} if day == "2026-11-24" else None)
    assert to(f"/govor/{at(10, 42)}") == (302, main.config.SITE + "poslanik/anic-ana")
    assert to(f"/cir/govor/{at(10, 42)}") == (302, main.config.SITE + "cir/poslanik/anic-ana")
    assert to(f"/govor/{at(12, 1)}") == (302, "/") and to(f"/govor/{at(17)}") == (302, "/")


@pytest.mark.skipif(not shutil.which("node"), reason="no node")
def test_the_edge_leads_a_speech_from_a_mail_on_while_the_service_is_off():
    script = """
globalThis.caches = { default: { match: async () => undefined, put: async () => {} } };
globalThis.fetch = async () => new Response("x", { status: 503 });
const edge = (await import(%s)).default;
const get = async (p) => (await edge.fetch(new Request("https://mikrofon.zailiprotiv.rs" + p), {}, { waitUntil() {} })).headers.get("location");
console.log(JSON.stringify([await get("/iz-mejla/govor/1795520640"), await get("/cir/iz-mejla/govor/1795520640"), await get("/iz-mejla/govor/abc")]));
""" % json.dumps((ROOT / "live" / "edge" / "worker.js").as_uri())
    ran = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, encoding="utf-8")
    assert ran.returncode == 0, ran.stderr
    assert json.loads(ran.stdout) == ["https://mikrofon.zailiprotiv.rs/govor/1795520640#iz-mejla",
                                      "https://mikrofon.zailiprotiv.rs/cir/govor/1795520640#iz-mejla", "https://zailiprotiv.rs/"]
    toml = (ROOT / "live" / "edge" / "wrangler.toml").read_text(encoding="utf-8")
    assert "mikrofon.zailiprotiv.rs/iz-mejla/*" in toml and "mikrofon.zailiprotiv.rs/cir/iz-mejla/*" in toml


# The site.

def sign_up(api="https://glasovi.zailiprotiv.rs/") -> str:
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader(str(ROOT / "src/zailiprotiv/templates")), autoescape=True)
    for f in re.findall(r"\|\s*([a-z_]+)", (ROOT / "src/zailiprotiv/templates/macros.html").read_text(encoding="utf-8")):
        env.filters.setdefault(f, lambda x, *a: x)  # the site's own filters: none is used by this part
    return env.from_string('{% from "macros.html" import follow_part with context %}{{ follow_part("anic-ana") }}').render(root="../", css="1", votes_api=api)


def test_the_sign_up_works_with_no_script_in_either_edition():
    from zailiprotiv.cyrillic import page
    html = sign_up()
    assert '<form class="prati-box" method="post" action="https://glasovi.zailiprotiv.rs/m/prati">' in html
    assert re.search(r'name="sta" value="anic-ana"', html) and re.search(r'name="pismo" value="lat"', html)
    assert "<details" in html and "<h2" not in html and "<section" not in html  # a section's heading would be folded on a phone
    assert re.search(r'<label class="sr" for="prati-adresa">', html) and 'type="email"' in html
    cir = page(f"<html lang=\"sr-Latn\"><body>{html}</body></html>", "poslanik/anic-ana.html")
    assert re.search(r'name="pismo" value="cir"', cir) and 'name="sta" value="anic-ana"' in cir
    assert "Прати мејлом" in cir and "Кога пратиш чувамо шифровано." in cir and 'placeholder="Е-адреса"' in cir
    assert sign_up(api="").strip() == ""


def test_every_sitting_mp_can_be_followed_by_one_rule():
    from zailiprotiv import pages_mikrofon
    from zailiprotiv.cyrillic import cyr
    from zailiprotiv.site import given_first
    got = pages_mikrofon.followable([{"slug": "anic-ana", "name": "Anić Ana"}, {"slug": "peric-pera-1980", "name": "Perić Pera (1980)"}],
                                    latin=lambda s: s, given_first=given_first, cyr=cyr)
    assert got == {"anic-ana": ["Ana Anić", "Ана Анић"], "peric-pera-1980": ["Pera Perić", "Пера Перић"]}
    js = (ROOT / "worker" / "prati.js").read_text(encoding="utf-8")
    assert pages_mikrofon.FOLLOW_FILE in js


def test_the_sign_up_is_on_every_sitting_mps_page_and_on_nobody_elses(tmp_path):
    sys.path.insert(0, str(ROOT / "tests"))
    from test_site import data
    from zailiprotiv import members, site
    out, root = tmp_path / "_site", data(tmp_path)
    (root / "settings.json").write_text(json.dumps({"votes_api": "https://glasovi.example/"}))
    listed = "<table>" + "".join(f"<tr><td>{n}</td><td>-</td><td>Бор</td><td>{y}.</td></tr>" for n, y in [("АБРАМОВИЋ НЕНАД", 1970), ("НОВИ НИКОЛА", 1980)]) + "</table>"
    (root / "15").mkdir(exist_ok=True)
    (root / "15" / "members.json").write_text(members.dumps("2026-11-18T10:00:00+00:00", members.read(listed)))
    site.build(root, out, "zailiprotiv.rs", cyrillic=True)
    named = json.loads((out / "prati-poslanici.json").read_text(encoding="utf-8"))
    assert named == {"abramovic-nenad": ["Nenad Abramović", "Ненад Абрамовић"], "novi-nikola": ["Nikola Novi", "Никола Нови"]}
    for f in (out / "poslanik").glob("*.html"):
        if not f.stem.endswith(("-glasovi", "-govori")):
            page = f.read_text(encoding="utf-8")
            assert ('class="prati-box"' in page) == (f.stem in named), f.stem
            assert f.stem not in named or (f'name="sta" value="{f.stem}"' in page and 'src="../prati.js' in page)
    cir = (out / "cir" / "poslanik" / "novi-nikola.html").read_text(encoding="utf-8")
    assert 'name="pismo" value="cir"' in cir and "Прати мејлом" in cir and (out / "prati.js").exists()
    privacy = (out / "privatnost.html").read_text(encoding="utf-8")
    assert 'id="pracenje"' in privacy and "koji prate klikove" not in privacy
    assert 'id="pracenje"' in (out / "kako-racunamo.html").read_text(encoding="utf-8")
    assert site.check(out) == []
    css = (ROOT / "src/zailiprotiv/static/style.css").read_text(encoding="utf-8")
    assert ".prati-box [hidden] { display: none; }" in css  # the row is a flex one: hidden alone would leave it on the page


def test_the_use_a_mail_counts_is_one_sum():
    live = (ROOT / "live/uzivo/static/live.js").read_text(encoding="utf-8")
    assert 'use("iz-mejla")' in live
    main = (ROOT / "worker/worker.js").read_text(encoding="utf-8")
    assert '"mikrofon.iz-mejla"' in main and "iz-mejla" not in main[main.index("const HOURLY"):main.index("const LEAST")]
