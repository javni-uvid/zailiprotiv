"""A finished speech by its own link (live/uzivo/deljenje.py, mikrofon.js, the site's page of the day, the edge worker)."""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "live"))

from uzivo import config, deljenje  # noqa: E402
from uzivo.page import fragment, page, speech_title  # noqa: E402

TZ = ZoneInfo("Europe/Belgrade")
SITE, URL = "https://zailiprotiv.rs/", "https://mikrofon.zailiprotiv.rs/"
A, B, C = 1795520640, 1795520700, 1795524000  # 24 Nov 2026: 12:44, 12:45 and 13:40
NODE = shutil.which("node")


def turn(name, od, do, **more):
    return {"ime": name, "adresa": "", "grupa": "", "uloga": "", "lista": "Lista", "od": od, "do": do, "sekundi": do - od,
            "video": "abcdefghijk", "snimak": od - A + 100, **more}


def snapshot(**more):
    return {"stanje": "nepoznato", "provereno": A, "sada": None, "dan": "2026-11-24", "ranije": False, "snimak": False,
            "danas": [turn("Jović Jova", C, C + 900), turn("Perić Pera", B, B + 600), turn("Anić Ana", A, A + 40)],
            "hronika": [], **more}


def test_only_a_second_of_a_day_that_can_have_been_kept_is_an_address():
    assert deljenje.moment(str(A), now=A) == A
    for bad in ("", "abc", "179552064", str(A) + "0", "-795520640", "1794800000", "9999999999", "١٧٩٥٥٢٠٦٤٠", str(A) + "\n", "../x"):
        assert deljenje.moment(bad, now=A) is None, bad


CASES = [(A, A), (A + 10, A), (B, B), (B - 45, A), (B - 20, B), (B + 46, B), (B + 500, B), (C - 45, C), (C - 46, None), (C + 901, None), (C + 800, C)]


def test_a_link_means_the_turn_that_begins_nearest_else_the_one_that_holds_the_second():
    for at, od in CASES:
        d = deljenje.turn_at(snapshot()["danas"], at)
        assert (d["od"] if d else None) == od, at


def test_the_kept_days_links_are_found_in_the_day_read_again():
    """24 Nov 2026 as the service kept it, and as the site made it of that record: every speech of the first is the
    same speaker's in the second."""
    data = ROOT / "data" / "15"
    kept, again = (json.loads((data / d / "2026-11-24.json").read_text(encoding="utf-8")) for d in ("uzivo", "snimak"))
    if again.get("izvor") != "uzivo":
        pytest.skip("the day was read from its notes since")
    rows = [t for t in again["govori"] if t["okvira"] >= 2]
    for t in kept["govori"]:
        if t["okvira"] >= 2:
            found = deljenje.turn_at(rows, t["od"])
            assert found and found["ime"] == t["ime"], t


def test_an_earlier_day_leads_only_to_a_day_the_site_lists():
    w = {"dani": ["2026-11-24"]}
    assert deljenje.elsewhere(A, w, cyr=False, tz=TZ) == config.SITE + f"govornici/2026-11-24#govor-{A}"
    assert deljenje.elsewhere(A, w, cyr=True, tz=TZ) == config.SITE + f"cir/govornici/2026-11-24#govor-{A}"
    for none in ({"dani": ["2026-11-23"]}, {}, None, {"dani": "2026-11-24"}):
        assert deljenje.elsewhere(A, none, cyr=False, tz=TZ) == ""


def test_every_finished_speech_has_the_same_link_and_no_name_in_it():
    for cyr, own, word in ((False, "", "podeli"), (True, "/cir", "подели")):
        html = fragment(snapshot(), cyr=cyr, site=SITE, tz=TZ)
        links = re.findall(r'class="share-turn" data-share="([^"]+)"', html)
        assert links == [f"{own}/govor/{x}" for x in (C, B, A)] and html.count(f"<span>{word}</span></button>") == 3
        assert f'data-od="{A}" data-do="{A + 40}"' in html


def test_what_a_pasted_link_to_a_speech_shows(monkeypatch):
    """The same form for everyone: the name as the record has it, and when; no word of the transcript or the topic; not
    the announcement of the next sitting."""
    snap = snapshot(stanje="nema_prenosa")
    snap["danas"][2]["rezime"] = "O nečemu"
    html = page(snap, cyr=False, site=SITE, tz=TZ, url=URL, speech=A)
    head = html.split("</head>")[0].split("<style>")[0]
    assert 'property="og:title" content="Ana Anić, govor u Skupštini, 24. novembra u 12:44"' in head
    assert f'property="og:url" content="{URL}govor/{A}"' in head and f'content="{URL}govor.png?v=s4"' in head
    assert "O nečemu" not in head and 'name="robots" content="noindex"' in head and 'rel="canonical"' not in head
    assert f'href="/cir/govor/{A}" hreflang="sr-Cyrl"' in html  # the other script: the same speech
    cir = page(snap, cyr=True, site=SITE, tz=TZ, url=URL, speech=A + 5)
    assert 'content="Ана Анић, говор у Скупштини, 24. новембра у 12:44"' in cir and f'content="{URL}cir/govor.png?v=s4"' in cir
    plain = page(snap, cyr=False, site=SITE, tz=TZ, url=URL)
    assert "noindex" not in plain and 'rel="canonical"' in plain and 'href="/cir/" hreflang="sr-Cyrl"' in plain
    monkeypatch.setattr(config, "SHARE_NAME", False)
    assert speech_title(snap, A, cyr=False, tz=TZ) == "Govor u Skupštini, 24. novembra u 12:44"


def test_the_page_says_that_a_shared_speech_starts_by_itself():
    how = page(snapshot(), cyr=False, site=SITE, tz=TZ, live="abcdefghijk").split('<details class="how">', 1)[1]
    assert "Link ka podeljenom govoru jedini pušta sam" in how and "učitava se tek na klik" in how
    cir = page(snapshot(), cyr=True, site=SITE, tz=TZ, live="abcdefghijk").split('<details class="how">', 1)[1]
    assert "Линк ка подељеном говору једини пушта сам" in cir
    for f in ("about.html", "method.html"):
        assert "podeljenom govoru" in (ROOT / "src/zailiprotiv/templates" / f).read_text(encoding="utf-8") or f == "method.html"
    assert "kreće sam, od tog govora" in (ROOT / "src/zailiprotiv/templates/method.html").read_text(encoding="utf-8")


HARNESS = r"""
const rows = ROWS.map(([od, end, yt, t]) => {
  const at = { "data-od": String(od), "data-do": String(end) }, cls = new Set();
  const place = yt ? { getAttribute: k => ({ "data-yt": yt, "data-t": String(t) })[k] ?? null } : null;
  return { od, cls, getAttribute: k => at[k] ?? null, closest: () => null,
    classList: { add: c => cls.add(c), remove: c => cls.delete(c) },
    querySelector: s => s === ".ko" ? { textContent: " Ana <b>Anić</b> " } : place };
});
const made = [], clicks = [];
const node = tag => ({ tag, attrs: {}, kids: [], setAttribute(k, v) { this.attrs[k] = v; }, getAttribute(k) { return this.attrs[k] ?? null; },
  appendChild(x) { this.kids.push(x); }, remove() { this.gone = true; }, click() { clicks.push(this); } });
let inside = null;
const screen = { querySelector: s => s === ".play.govor" ? inside : null, set textContent(v) { inside = null; },
  appendChild(x) { inside = x; made.push(x); }, scrollIntoView() {} };
const notes = [];
const words = { querySelector: s => { const k = /data-w="(\w)"/.exec(s)[1]; return k === "l" ? null : { textContent: ({ p: "Pusti govor", d: "24. novembra u", n: "Nema." })[k] }; },
  parentNode: { insertBefore: x => notes.push(x) } };
const on = {};
globalThis.document = { hidden: false, getElementById: i => i === "deljen" ? words : i === "screen" ? screen : null, createElement: node,
  querySelectorAll: s => s.startsWith("li[data-od]") ? rows : rows.filter(r => r.cls.has("govor-on")), contains: x => x === inside,
  querySelector: () => null, addEventListener: (k, f) => { (on[k] = on[k] || []).push(f); } };
globalThis.window = { addEventListener() {} };
globalThis.location = { pathname: PATH, hash: HASH, href: "https://x/" };
globalThis.Audio = function () { this.play = () => MAY ? Promise.resolve() : Promise.reject(new Error("NotAllowedError")); this.pause = () => {}; };
SCRIPT
setTimeout(() => console.log(JSON.stringify({ on: rows.filter(r => r.cls.has("govor-on")).map(r => r.od), made: made.map(b => b.attrs),
  text: made.map(b => b.kids[0].kids[0].textContent), clicks: clicks.length, notes: notes.map(x => x.textContent) })), 20);
"""


@pytest.mark.skipif(not NODE, reason="no node")
def test_the_script_opens_the_speech_of_the_address_and_starts_it_only_where_the_browser_lets_it(tmp_path):
    js = (ROOT / "src/zailiprotiv/templates/mikrofon.js").read_text(encoding="utf-8")
    own = js[js.index("// A finished speech by its own link"):]

    def ran(path="/", hash_="", may=True, yt="abcdefghijk"):
        rows = [[C, C + 900, yt, 900], [B, B + 600, yt, 160], [A, A + 40, yt, 100]]
        f = tmp_path / "d.cjs"
        f.write_text(HARNESS.replace("ROWS", json.dumps(rows)).replace("PATH", json.dumps(path)).replace("HASH", json.dumps(hash_))
                     .replace("MAY", json.dumps(may)).replace("SCRIPT", own), encoding="utf-8")
        r = subprocess.run([NODE, str(f)], capture_output=True, text=True, encoding="utf-8")
        assert r.returncode == 0, r.stderr
        return json.loads(r.stdout)

    for at, od in CASES:  # the same turns as deljenje.turn_at, by both addresses
        for got in (ran(f"/govor/{at}"), ran("/govornici/2026-11-24", f"#govor-{at}"), ran(f"/cir/govor/{at}")):
            assert got["on"] == ([od] if od else []) and len(got["made"]) == got["clicks"] == (1 if od else 0), at
    b = ran(f"/govor/{B + 500}")["made"][0]  # held, not near: from that second on
    assert b["data-yt"] == "abcdefghijk" and b["data-t"] == "660" and b["aria-label"].endswith("24. novembra u 12:45")
    refused = ran(f"/govor/{A}", may=False)
    assert len(refused["made"]) == 1 and refused["clicks"] == 0  # the large button stays, nothing is loaded
    assert refused["text"] == ["Ana <b>Anić</b>"]  # as text
    none = ran(f"/govor/{A}", yt="")  # no place yet: said, and no button
    assert none["made"] == [] and none["notes"] == ["Ana <b>Anić</b>, 24. novembra u 12:44. Nema."]
    for bad in (("/", ""), ("/govor/abc", ""), ("/govor/1", ""), ("/", "#govor-1x"), ("/", "#govor-<img>")):
        got = ran(*bad)
        assert got["on"] == got["made"] == [] and not got["clicks"]
    assert ran("/govornici/2026-11-24", f"#g{A}")["on"] == [A]  # a turn's old place in a day since read again


@pytest.mark.skipif(not NODE, reason="no node")
def test_the_edge_keeps_a_speech_as_the_page_and_shows_the_sites_page_when_the_service_is_off():
    script = """
const kept = new Map();
globalThis.caches = { default: { match: async k => kept.get(k.url)?.clone(), put: async (k, r) => { kept.set(k.url, r); } } };
globalThis.HTMLRewriter = class { on() { return this; } transform(r) { return r; } };
let asked = [], up = true;
globalThis.fetch = async r => { const u = r.url || r; asked.push(u); return u.startsWith("https://zailiprotiv.rs/") ? new Response("site") : new Response("page", { status: up ? 200 : 503 }); };
const edge = (await import(WORKER)).default, jobs = [], ctx = { waitUntil: p => jobs.push(p) };
const get = async p => { const r = await edge.fetch(new Request("https://mikrofon.zailiprotiv.rs" + p), {}, ctx); await Promise.all(jobs); return r; };
const out = {};
await get("/govor/1795520640"); await get("/govor/1795520640?fbclid=1"); out.once = asked.length;
up = false; asked = []; kept.clear();
out.off = (await get("/govor/1795520640")).status; out.where = asked.filter(u => u.includes("zailiprotiv.rs/") && !u.includes("mikrofon.zaili"));
asked = []; await get("/cir/govor/1795520640"); out.cir = asked.filter(u => u.startsWith("https://zailiprotiv.rs/"));
const other = await get("/govor/../x"); out.other = other.status + " " + other.headers.get("location");
console.log(JSON.stringify(out));
""".replace("WORKER", json.dumps((ROOT / "live" / "edge" / "worker.js").as_uri()))
    r = subprocess.run([NODE, "--input-type=module", "-e", script], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["once"] == 1 and out["off"] == 503
    assert out["where"] == ["https://zailiprotiv.rs/mikrofon"] and out["cir"] == ["https://zailiprotiv.rs/cir/mikrofon"]
    assert out["other"] == "302 https://zailiprotiv.rs/"


def test_the_service_answers_a_speechs_address(monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from uzivo import main
    monkeypatch.setattr(main.tracker, "snapshot", lambda now=None: snapshot())
    monkeypatch.setattr(main.tracker, "waiting", {"dani": ["2026-11-23", "//evil.example"]})
    monkeypatch.setattr(deljenje.time, "time", lambda: C + 1000)
    c = TestClient(main.app, follow_redirects=False)
    r = c.get(f"/govor/{A}")
    assert r.status_code == 200 and "noindex" in r.text
    to = lambda p: (lambda x: (x.status_code, x.headers.get("location")))(c.get(p))
    assert to("/govor/1795430000") == (302, config.SITE + "govornici/2026-11-23#govor-1795430000")
    assert to("/cir/govor/1795430000") == (302, config.SITE + "cir/govornici/2026-11-23#govor-1795430000")
    for gone in ("1795300000", "abc", "0", "99999999999", "%2F%2Fevil.example"):
        assert to("/govor/" + gone)[1] in ("/", None) and to("/govor/" + gone)[0] in (302, 404)
    assert c.get("/govor.png").headers["content-type"] == "image/png"
