"""What following an area of laws would have sent on a morning, without sending anything and with nobody's address.

    uv run python tools/prati_primer.py 2025-12-04 [<folder>] [--cir] [--zakoni]

The site's events (oblasti.py over data/) as they stood that morning, told by the live service's own rules (prati.py:
area_news, build) to a reader who follows one area, a mail per area with something new, written as HTML files to the
folder (default: prati-primer/ here). The counter is not asked and no mail goes. Each event is taken as known the day
it happened, as the proposal counted (27 Nov 2026). With --zakoni, instead a mail to a follower of each law with
something new (one bill or one law, 28 Nov 2026): `<day>-z-<key>.html`.
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "live"))

from uzivo import prati  # noqa: E402
from zailiprotiv import oblasti  # noqa: E402
from zailiprotiv.cyrillic import cyr  # noqa: E402
from zailiprotiv.site import slug  # noqa: E402
from zailiprotiv.translit import latin  # noqa: E402


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 2
    day = date.fromisoformat(args[0])
    out = Path(args[1]) if len(args) > 1 else Path("prati-primer")
    out.mkdir(parents=True, exist_ok=True)
    evs = [{k: v for k, v in e.items() if k != "poznato"} for e in oblasti.events(ROOT / "data", "14", "15")
           if e["dan"] < day.isoformat()]
    shown = oblasti.published(evs, today=day, laws={}, bills={}, latin=latin, cyr=cyr)
    for i, e in enumerate(shown["dogadjaji"], 1):
        e["seq"] = i
    if "--zakoni" in argv:
        return laws(shown, day, out, "--cir" in argv)
    points = {v[0]: int(k) for k, v in shown["oblasti"].items()}
    wrote = 0
    for name, point in sorted(points.items(), key=lambda kv: kv[1]):
        area = prati.Followed(slug(name)[:80], name, day - timedelta(days=prati.KEEP_DAYS), ("#",), "o")
        reader = prati.Follower("", "", "--cir" in argv, "", "#", "#", (area,))
        told = prati.area_news(reader, shown["dogadjaji"], points, 0, day)
        if told:
            mail = prati.build(reader, prati.Told([], told), day)
            (out / f"{day.isoformat()}-{point:02d}.html").write_text(mail.html, encoding="utf-8")
            print(f"{point:2d} {name}: {sum(len(x) for _, x in told)} · {mail.subject}")
            wrote += 1
    print(f"{wrote} mails, in {out}" if wrote else "nothing that morning")
    return 0


def laws(shown: dict, day: date, out: Path, cir: bool) -> int:
    names = {}
    for e in shown["dogadjaji"]:
        for k, n in zip(e.get("zakoni") or [], oblasti.named(e["naslov"])):
            names.setdefault(k, n)
    wrote = 0
    for key, name in sorted(names.items()):
        law = prati.Followed(key, name, day - timedelta(days=prati.KEEP_DAYS), ("#",), "z")
        reader = prati.Follower("", "", cir, "", "#", "#", (law,))
        told = prati.law_news(reader, shown["dogadjaji"], shown["predlozi"], 0, day)
        if told:
            mail = prati.build(reader, prati.Told([], [], 0, told), day)
            (out / f"{day.isoformat()}-z-{key}.html").write_text(mail.html, encoding="utf-8")
            print(f"{name}: {sum(len(x) for _, x in told)} · {mail.subject}")
            wrote += 1
    print(f"{wrote} mails, in {out}" if wrote else "nothing that morning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
