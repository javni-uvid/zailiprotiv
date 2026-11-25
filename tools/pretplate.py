"""How many asked to be called back (the day's mail, the notifications), by sitting day: sums only, for the maintainer.

    uv run python tools/pretplate.py

Read, never written, from two places:
- the counter's public overview (`/pregled`): confirmed and waiting now, devices with notifications now, how many a day's
  notification reached, and the uses of the live page by day (the form sent, the bell turned on and off; UTC, two weeks);
- what the live service keeps of each mail (`/data/mejl/<day>.json`: the counter's row ids it went to, never an address).
  This same file runs in the page's container (`docker exec -i … python - --zbir`), counts there and prints numbers
  alone: no id leaves the container, the sealed addresses are not asked for and no key is read.

From the ids of one mail and the next: new since the one before, and gone since (who left; an address sealed for another
key, or one in two rows, is not mailed, so it would count as gone too). Not known, as nobody keeps it: the day of a leaving,
and how many sign-ups were ever begun (a row not confirmed is deleted after 48 hours).
"""
from __future__ import annotations

import json
import subprocess
import sys
import urllib.request
from pathlib import Path

OVERVIEW = "https://glasovi.zailiprotiv.rs/pregled"
AGENT = "zailiprotiv/0.1 (+https://github.com/javni-uvid/zailiprotiv)"
CONTAINER, FOLDER = "mikrofon-uzivo-1", "/data/mejl"
SINCE = "2026-11-23"  # the first day of the form on the page


def mails(folder: Path) -> list[dict]:
    """A day's mail to all, oldest first, as numbers: to how many it went, how many of them new, how many gone since
    the mail before, and the calls that failed or whose end is not known."""
    out, before, ever = [], None, set()
    for f in sorted(folder.glob("20??-??-??.json")):
        kept = json.loads(f.read_text(encoding="utf-8"))
        if not kept.get("svima"):  # never sent to all
            continue
        sent, unsure = set(kept.get("poslati") or []), set(kept.get("nesigurni") or [])
        failed = {g["id"] for g in kept.get("greske") or []} - sent
        there = sent | unsure | failed
        out.append({"dan": f.stem, "poslato": len(sent), "novi": len(there - ever),
                    "otisli": None if before is None else len(before - there), "greske": len(failed), "nesigurno": len(unsure)})
        before, ever = there, ever | there
    return out


def row(*cells) -> str:
    return "  " + str(cells[0]).ljust(12) + "".join(str("-" if c is None else c).rjust(11) for c in cells[1:])


def report(over: dict, sent: list[dict] | None) -> list[str]:
    uses, now, push = over.get("uses") or {}, over["mejl"], over["push"]
    lines = ["Sada:", f"  mejl: {now['potvrdjeno']} potvrdjenih, {now['ceka']} ceka potvrdu (nepotvrdjeni se brisu posle 48 sati)",
             f"  obavestenja: {push['devices']} uredjaja"]
    if sent:
        last = sent[-1]
        lines.append(f"  od poslednjeg mejla svima ({last['dan']}): {now['potvrdjeno'] - last['poslato']:+d} potvrdjenih "
                     "(novi manje odjavljeni)")
    lines += ["", "Na uzivo strani, po danu (UTC; jednom po otvorenoj strani):",
              row("dan", "otvorena", "prijava", "na 1000", "zvono", "ugaseno")]
    for day in sorted(d for d in uses if d >= SINCE):
        n = lambda what, u=uses[day]: u.get("mikrofon." + what, 0)  # noqa: E731
        per = f"{1000 * n('mejl') / n('otvori'):.1f}" if n("otvori") else None
        lines.append(row(day, n("otvori"), n("mejl"), per, n("obavesti"), n("odjavi")))
    if sent is None:
        return lines + ["", f"Mejlovi: {CONTAINER} ne odgovara, pa se ne broje."]
    lines += ["", "Mejl svima, po danu sednice (novi i otisli od mejla pre njega):",
              row("dan", "poslato", "novi", "otisli", "greske", "nesigurno")]
    lines += [row(*(m[k] for k in ("dan", "poslato", "novi", "otisli", "greske", "nesigurno"))) for m in sent]
    begun = sum(u.get("mikrofon.mejl", 0) for u in uses.values())
    if begun and min(uses) <= SINCE:  # only while the overview still has every day since the first sign-up
        # who ever confirmed, at least: in a mail, or confirmed since the last one
        ever = sum(m["novi"] for m in sent) + max(0, now["potvrdjeno"] - sent[-1]["poslato"]) if sent else now["potvrdjeno"]
        lines.append(f"  udeo potvrdjenih, grubo: {ever} od {begun} poslatih prijava ({100 * ever / begun:.0f}%; ista adresa "
                     "poslata dvaput broji se dvaput)")
    lines += ["", "Obavestenja po slanju (s: sazetak, n: nastavak posle pauze):", row("", "stiglo", "ugaslih")]
    lines += [row(p["day"], p["sent"], p["gone"]) for p in sorted(push["sent"], key=lambda p: p["day"][-10:])]
    return lines


def main() -> None:
    req = urllib.request.Request(OVERVIEW, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(req, timeout=60) as r:
        over = json.load(r)
    try:
        got = subprocess.run(["docker", "exec", "-i", CONTAINER, "python", "-", "--zbir"], input=Path(__file__).read_bytes(),
                             capture_output=True, timeout=60)
        sent = json.loads(got.stdout) if got.returncode == 0 else None
    except (OSError, ValueError, subprocess.TimeoutExpired):
        sent = None
    print("\n".join(report(over, sent)))


if __name__ == "__main__":
    if "--zbir" in sys.argv:
        print(json.dumps(mails(Path(FOLDER))))
    else:
        main()
