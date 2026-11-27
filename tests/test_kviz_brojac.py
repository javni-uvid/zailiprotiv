"""How far the quizzes are taken (26 Nov 2026, the maintainer: "Ubaci tracker na kvizu"): the counter's sums, with
nothing of the reader, and the visits workflow's report of them."""
import json
import shutil
import sqlite3
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

STEPS = r"""
import worker from %s;
globalThis.fetch = async (url) => new Response(JSON.stringify({ laws: {}, kviz: ["podelili-salu", "zivotna-sredina"] }));
const done = [], said = [];
const st = (sql, a = []) => ({ sql, a, bind: (...b) => st(sql, b), run: async () => ({}) });
const DB = { prepare: (sql) => st(sql), batch: async (all) => { done.push(...all.map((x) => [x.sql, x.a])); return []; } };
const site = "https://zailiprotiv.rs";
for (const body of [{ e: "kviz.pocetak", k: "podelili-salu" }, { e: "kviz.pola", k: "podelili-salu" },
                    { e: "kviz.sve", k: "neki-drugi" }, { e: "kviz.kraj", k: "zivotna-sredina" }, { e: "kviz.kraj" },
                    { e: "kviz.pocetak", k: 7 }, { e: "kviz.nesto", k: "podelili-salu" }])
  said.push((await worker.fetch(new Request("https://glasovi.zailiprotiv.rs/e", { method: "POST", headers: { origin: site },
    body: JSON.stringify(body) }), { DB }, { waitUntil() {} })).status);
console.log(JSON.stringify({ said, done }));
"""


@pytest.mark.skipif(not shutil.which("node"), reason="needs Node, as the worker's code is JavaScript")
def test_a_quizs_steps_are_sums_by_day_and_by_a_quiz_the_site_lists():
    ran = subprocess.run(["node", "--input-type=module", "-e", STEPS % json.dumps((ROOT / "worker" / "worker.js").as_uri())],
                         capture_output=True, text=True, encoding="utf-8")
    assert ran.returncode == 0, ran.stderr
    out = json.loads(ran.stdout)
    assert out["said"] == [204] * 6 + [400]  # a name the counter doesn't know is refused
    db = sqlite3.connect(":memory:")
    db.executescript((ROOT / "worker" / "schema.sql").read_text(encoding="utf-8"))
    for sql, values in out["done"]:
        db.execute(sql, values)
    sums = dict(db.execute("SELECT what, SUM(n) FROM events GROUP BY what"))
    assert sums == {"kviz.pocetak": 2, "kviz.pola": 1, "kviz.sve": 1, "kviz.kraj": 2,
                    "kviz.pocetak:podelili-salu": 1, "kviz.pola:podelili-salu": 1, "kviz.kraj:zivotna-sredina": 1}
    assert [c[1] for c in db.execute("PRAGMA table_info(events)")] == ["day", "what", "n"]  # nothing else is kept


def test_the_quiz_sends_its_steps_once_per_page_and_only_its_name():
    js = (ROOT / "src/zailiprotiv/static/glasaj.js").read_text(encoding="utf-8")
    site_js = (ROOT / "src/zailiprotiv/static/site.js").read_text(encoding="utf-8")
    assert 'used("kviz.pocetak")' in js and 'used("kviz.pola")' in js and 'used("kviz.sve")' in js
    assert "window.zipCount(what, QUIZ)" in js and "slug((location.pathname.match(" in js
    assert "zipCounted[what] = 1" in site_js and "{ e: what, k: quiz }" in site_js  # once per page opened; no mark of who


def test_the_visits_workflow_prints_how_many_finish_a_quiz():
    import importlib.util
    spec = importlib.util.spec_from_file_location("uses", ROOT / "tools" / "uses.py")
    uses = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(uses)
    lines = uses.quizzes({"2026-11-25": {"kviz.kraj": 12}, "2026-11-26": {
        "kviz.pocetak": 40, "kviz.pola": 25, "kviz.sve": 18, "kviz.kraj": 20,
        "kviz.pocetak:podelili-salu": 30, "kviz.kraj:podelili-salu": 16, "kviz.pocetak:zivotna-sredina": 10,
        "kviz.kraj:zivotna-sredina": 4, "mikrofon.pusti": 9}})
    assert lines[1].split() == ["2026-11-25", "0", "0", "0", "12", "-"]  # no starts counted yet: no rate
    assert lines[2].split() == ["2026-11-26", "40", "25", "18", "20", "50%"]
    assert lines[-2].split() == ["podelili-salu", "30", "0", "0", "16", "53%"] and lines[-1].split()[-1] == "40%"
    assert uses.quizzes({}) == ["  nothing counted"]
