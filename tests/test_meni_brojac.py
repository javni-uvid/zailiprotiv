"""The phone's bar counted (27 Nov 2026, the maintainer: "Stavi svakako tracker"): sums per day, names the counter takes."""
import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAMES = {"meni.zakoni", "meni.poslanici", "meni.uzivo", "meni.glasaj", "meni.jos", "meni.jos-izbor"}


def test_the_bar_sends_only_names_the_counter_takes():
    js = (ROOT / "src/zailiprotiv/static/site.js").read_text(encoding="utf-8")
    worker = (ROOT / "worker/worker.js").read_text(encoding="utf-8")
    events = worker[worker.index("const EVENTS"):worker.index("]);", worker.index("const EVENTS"))]
    assert set(re.findall(r'"(meni\.[a-z-]+)"', js)) == NAMES
    assert all(f'"{n}"' in events for n in NAMES)
    assert "zipCounted[what] = 1" in js  # once per page opened, through the one sender
    base = (ROOT / "src/zailiprotiv/templates/base.html").read_text(encoding="utf-8")
    assert all(f'data-at="{a}"' in base for a in ("zakon", "poslani", "glasaj"))  # the ways the script names


def test_the_visits_workflow_prints_the_bar_by_day():
    spec = importlib.util.spec_from_file_location("uses", ROOT / "tools" / "uses.py")
    uses = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(uses)
    lines = uses.menu({"2026-11-27": {"meni.zakoni": 9, "meni.jos": 2, "mikrofon.pusti": 4}, "2026-11-26": {"kviz.kraj": 3}})
    assert len(lines) == 2 and lines[1].split() == ["2026-11-27", "9", "0", "0", "0", "2", "0"]
    assert uses.menu({}) == ["  nothing counted"]
