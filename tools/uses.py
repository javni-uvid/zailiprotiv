"""What readers started on "Ko sada govori" (mikrofon.zailiprotiv.rs), hour by hour, from our own counter's sums.

The counter (`worker/`) adds one per page opened to a sum: the broadcast started (`pusti`), the live sound started
(`slusaj`), the page in view after 1 and after 5 minutes. Its public overview gives the sums of the last two weeks, per
hour without those under three: nothing about any one reader is kept there at all. Beside tools/watching.py, which
tells how many had the page in view in the same hours.

And how far the quizzes were taken (26 Nov 2026), by day and by quiz: started (an answer given), half the laws
answered, every law, the result reached, each once per page opened, and the share of the started that reached the
result. The result can be opened after three answers, so "finished" is the result reached, not every law answered.

Run by the `visits` workflow; needs no token.
"""
import json
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

OVERVIEW = "https://glasovi.zailiprotiv.rs/pregled"
AGENT = "zailiprotiv/0.1 (+https://github.com/javni-uvid/zailiprotiv)"
USES = ("pusti", "slusaj", "1min", "5min")
STEPS = ("pocetak", "pola", "sve", "kraj")


def rate(sums: dict) -> str:
    """The result reached per quiz started, or "-" before any start was counted (the starts are counted since 26 Nov)."""
    start = sums.get("pocetak", 0)
    return f"{100 * sums.get('kraj', 0) / start:.0f}%" if start else "-"


def quizzes(by_day: dict) -> list[str]:
    """The quiz's steps a line per day, the newest last, then a line per quiz for the whole span."""
    lines, per = [], {}
    for day in sorted(by_day):
        steps = {s: by_day[day].get("kviz." + s, 0) for s in STEPS}
        if any(steps.values()):
            lines.append(f"  {day}" + "".join(f"{steps[s]:>9}" for s in STEPS) + f"{rate(steps):>9}")
        for what, n in by_day[day].items():
            if what.startswith("kviz.") and ":" in what:
                step, quiz = what[5:].split(":", 1)
                if step in STEPS:
                    per.setdefault(quiz, {})[step] = per.get(quiz, {}).get(step, 0) + n
    if not lines:
        return ["  nothing counted"]
    head = ["  day       " + "".join(f"{s:>9}" for s in STEPS) + f"{'result %':>9}"]
    out = head + lines
    if per:
        out += ["", "  by quiz, the whole span"] + [
            f"  {quiz[:28]:<28}" + "".join(f"{sums.get(s, 0):>9}" for s in STEPS) + f"{rate(sums):>9}"
            for quiz, sums in sorted(per.items(), key=lambda kv: -kv[1].get("pocetak", 0))]
    return out


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
        over = json.load(r)
    by_hour = over.get("uses_by_hour") or {}
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime("%Y-%m-%dT%H")
    print(f"Started on the live page by hour, from {since}:00 UTC (each use once per page opened; under three: -)")
    lines = table(by_hour, since)
    print("  hour, UTC  " + "".join(f"{u:>9}" for u in USES) if lines else "  nothing counted")
    print("\n".join(lines))
    print("\nThe quizzes, by day (UTC; each step once per page opened; the result reached per quiz started)")
    print("\n".join(quizzes(over.get("uses") or {})))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 24)
