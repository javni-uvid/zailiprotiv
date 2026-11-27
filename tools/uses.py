"""What readers started on "Ko sada govori" (mikrofon.zailiprotiv.rs), hour by hour, from our own counter's sums.

The counter (`worker/`) adds one per page opened to a sum: the broadcast started (`pusti`), the live sound started
(`slusaj`), the page in view after 1 and after 5 minutes. Its public overview gives the sums of the last two weeks, per
hour without those under three: nothing about any one reader is kept there at all. Beside tools/watching.py, which
tells how many had the page in view in the same hours.

Run by the `visits` workflow; needs no token.
"""
import json
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

OVERVIEW = "https://glasovi.zailiprotiv.rs/pregled"
AGENT = "zailiprotiv/0.1 (+https://github.com/javni-uvid/zailiprotiv)"
USES = ("pusti", "slusaj", "1min", "5min")


def table(by_hour: dict, since: str) -> list[str]:
    """A line per hour from `since` ("2026-11-25T09") on, the earliest first; "-" where the counter gives no sum."""
    lines = []
    for hour in sorted(h for h in by_hour if h >= since):
        sums = by_hour[hour]
        lines.append(f"  {hour[5:].replace('T', ' ')}:00" + "".join(f"{sums.get('mikrofon.' + u, '-'):>9}" for u in USES))
    return lines


def main(hours: int):
    req = urllib.request.Request(OVERVIEW, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(req, timeout=60) as r:
        by_hour = json.load(r).get("uses_by_hour") or {}
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime("%Y-%m-%dT%H")
    print(f"Started on the live page by hour, from {since}:00 UTC (each use once per page opened; under three: -)")
    lines = table(by_hour, since)
    print("  hour, UTC  " + "".join(f"{u:>9}" for u in USES) if lines else "  nothing counted")
    print("\n".join(lines))


MENU = ("zakoni", "poslanici", "uzivo", "glasaj", "jos", "jos-izbor")


def menu(by_day: dict) -> list[str]:
    """The phone's bar (27 Nov 2026): a line per day of its ways taken, each once per page opened."""
    lines = [f"  {day}" + "".join(f"{by_day[day].get('meni.' + m, 0):>10}" for m in MENU)
             for day in sorted(by_day) if any(by_day[day].get("meni." + m) for m in MENU)]
    return ["  day       " + "".join(f"{m:>10}" for m in MENU)] + lines if lines else ["  nothing counted"]


def print_menu():
    req = urllib.request.Request(OVERVIEW, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(req, timeout=60) as r:
        by_day = json.load(r).get("uses") or {}
    print("\nThe phone's bar, by day (UTC; each way once per page opened)")
    print("\n".join(menu(by_day)))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 24)
    print_menu()
