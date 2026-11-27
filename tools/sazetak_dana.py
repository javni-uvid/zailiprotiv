"""A day's summary written by the day's model (DAY_MODEL) after the fact (27 Nov 2026): for a day the service never heard,
from the Assembly's stenographic notes (17 and 18 Nov 2026; the maintainer: "17 i 18 iz stenograma"), or again from
the automatic transcript the service kept (19 and 24 Nov 2026, written then by the weaker model). The service's own
call (`sudija.whole_day`) and checks, run from the repository on a computer, with no container.

    PYTHONUTF8=1 uv run python tools/sazetak_dana.py beleske <day> --izlaz <folder> [--bez-modela]
    PYTHONUTF8=1 uv run python tools/sazetak_dana.py prepis <day> --podaci <folder> --izlaz <folder> [--bez-modela]

Who spoke when is the site's record of the day (data/<N>/snimak/<day>.json, the notes found in the recording's sound),
for both: the speakers with two minutes or more (sudija.SPOKE) are the ones the summary must name.
`beleske`: the day's speeches from the notes (data/<N>/transcripts), in Latin letters, each at its recording's second
where it was found and otherwise at the end of the speech before it.
`prepis`: the service's transcript of the day, copied out of the measuring container into <folder> as it lies in /data
(`prepis/<day>.json`; `sazetak/<day>.json`, whose "delovi" are kept; `cekanje.json` for the transcript's corrections).
`--bez-modela`: only what would be sent, and its size.

Nothing is put in place: <folder>/sazetak/<day>.json is the day's file as the service keeps it, and
<folder>/osnova/<day>.json what each line rests on (for the maintainer, never a page). Printed: each speaker's line,
its sentences and whether they were found word for word, and what the reply still fails. Needs ANTHROPIC_API_KEY."""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "src"), str(REPO / "live")]
from zailiprotiv import translit  # noqa: E402
from uzivo import config, ispravke, sudija  # noqa: E402
from uzivo.names import Person, Roster, person_key  # noqa: E402

TZ = ZoneInfo("Europe/Belgrade")


def convocation(day: str) -> Path:
    found = sorted(REPO.glob(f"data/*/snimak/{day}.json"))
    if not found:
        sys.exit(f"no record of {day} in data/*/snimak")
    return found[0].parent.parent


def turns_of(rec: dict) -> list[dict]:
    """The day's turns as the service's whole-day call takes them (state_view._recorded, _lists)."""
    return [{"ime": t["ime"], "lista": t.get("uloga") or t.get("grupa") or "", "od": int(t["od"]), "do": int(t["do"])}
            for t in rec["govori"] if t.get("okvira", 0) >= 2]


def roster(conv: Path) -> Roster:
    """The convocation's MPs as the service names them (tools/uzivo_ponovo.py)."""
    from zailiprotiv.site import slug as site_slug
    out = []
    for m in json.loads((conv / "members.json").read_text(encoding="utf-8"))["members"]:
        name = " ".join(w for w in translit.latin(m["name"]).split() if w.lower().rstrip(".") not in {"mr", "dr", "prof"}).title()
        out.append(Person(person_key(name), name, site_slug(name, 60), translit.latin(m.get("group") or "")))
    return Roster(out)


def roster_text(r: Roster) -> str:
    return "Spisak poslanika: " + "; ".join(sorted(p.name for p in r.people)) + "\n\n"


def notes_material(day: str, conv: Path, rec: dict) -> tuple[str, list[str], dict[str, str], dict[str, str]]:
    """The day from the notes: (lines, speakers to name, their lists, what each said)."""
    speeches: dict[str, dict] = {}
    for f in sorted((conv / "transcripts").glob("*.json")):
        sitting = json.loads(f.read_text(encoding="utf-8"))
        n = next((d["day"] for d in sitting.get("days") or [] if d.get("listed_date") == day), None)
        if n is None:
            continue
        for k, s in (sitting.get("speeches") or {}).items():
            if s.get("day") == n and (s.get("text") or "").strip():
                speeches[f"{f.stem}/{k}"] = s
    if not speeches:
        sys.exit(f"no notes of {day} in {conv / 'transcripts'}")
    at: dict[str, tuple[int, int, str, str]] = {}  # a speech's key: (from, to, name, list) where the record found it
    for t in rec["govori"]:
        for k in t.get("beleske") or []:
            at[k] = (int(t["od"]), int(t["do"]), t["ime"], t.get("uloga") or t.get("grupa") or "")
    for c in rec.get("predsedavajuci") or []:
        for k in c.get("beleske") or []:
            at[k] = (int(c["od"]), int(c["do"]), "", "")
    lines, said, last_end, last_who = [], {}, min((v[0] for v in at.values()), default=0), None
    last_start = last_end
    for k in sorted(speeches):
        s = speeches[k]
        text = " ".join(translit.latin(s["text"]).split())
        if k in at:
            start, end, name, lista = at[k]
        else:
            start, end, name, lista = last_end, last_end, "", ""
        start = max(start, last_start)  # the notes' order stands: a speech found a little before the last (a chair's word
        last_start = start              # inside a turn) takes the last one's second
        if s.get("chair") or not name:
            who = sudija.CHAIR if s.get("chair") else f"{translit.latin(s.get('speaker', '')).title()} (nije nađen u snimku)"
        else:
            who = f"{name} ({lista or 'bez liste'})"
            said[name] = said.get(name, "") + " " + text
        clock = datetime.fromtimestamp(start, TZ).strftime("%H:%M:%S")
        lines.append(f"[{clock}] {who}: {text}" if who != last_who else f"[{clock}] {text}")
        last_who, last_end = who, max(last_end, end)
    turns = turns_of(rec)
    talk: dict[str, int] = {}
    for d in turns:
        talk[d["ime"]] = talk.get(d["ime"], 0) + max(0, d["do"] - d["od"])
    first = {d["ime"]: d["od"] for d in sorted(turns, key=lambda d: -d["od"])}
    need = sorted((n for n, x in talk.items() if x >= sudija.SPOKE), key=lambda n: first[n])
    return "\n".join(lines), need, {d["ime"]: d["lista"] for d in turns}, said


def transcript_material(day: str, folder: Path, rec: dict, r: Roster) -> tuple[str, list[str], dict[str, str], dict[str, str]]:
    """The day from the service's transcript, shown as the service shows it (state_said.shown: the corrections)."""
    f = folder / "prepis" / f"{day}.json"
    if not f.exists():
        sys.exit(f"no transcript at {f}: copy /data/prepis/{day}.json out of the measuring container")
    said = {str(k): str(v) for k, v in json.loads(f.read_text(encoding="utf-8")).items()}
    w = folder / "cekanje.json"
    waiting = json.loads(w.read_text(encoding="utf-8")) if w.exists() else {}
    rules = waiting.get("ispravke") if isinstance(waiting.get("ispravke"), dict) else None
    forms = ispravke.name_forms([p.name for p in r.people])
    return sudija.material(sudija.pieces(said), turns_of(rec), TZ, lambda x: ispravke.apply(x, rules, forms))


def report(done: dict | None, need: list[str]) -> None:
    if done is None:
        print("NO SUMMARY: no reply passed the checks (see the log)")
        return
    s = done["dan"]
    print(f"naslov: {s.get('naslov')}\nkratko: {s.get('kratko')}\nukratko: {s.get('ukratko')}\n")
    for o in s.get("odluke") or []:
        print(f"  odluka {o.get('vreme')}: {o.get('sta')}  {o.get('glasovi') or ''}")
    print()
    for g in s.get("govornici") or []:
        ok = "NIJE NAĐENO" if g.get("ime") in done["bez_oslonca"] else "nađeno"
        print(f"- {g.get('ime')} ({g.get('lista')}): {g.get('o_cemu')}\n    oslonac [{ok}]:")
        for x in done["oslonac"].get(g.get("ime"), []):
            print(f"      {x}")
    print("\nstill failing:", "; ".join(done["provera"]) or "nothing")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("izvor", choices=("beleske", "prepis"))
    ap.add_argument("dan")
    ap.add_argument("--izlaz", required=True, type=Path)
    ap.add_argument("--podaci", type=Path, help="prepis: the folder copied out of /data")
    ap.add_argument("--bez-modela", action="store_true")
    a = ap.parse_args(argv)
    conv = convocation(a.dan)
    rec = json.loads((conv / "snimak" / f"{a.dan}.json").read_text(encoding="utf-8"))
    r = roster(conv)
    if a.izvor == "beleske":
        text, need, lists, said = notes_material(a.dan, conv, rec)
        prompt, what = sudija.NOTES, "Stenografske beleške dana"
    else:
        if not a.podaci:
            ap.error("prepis needs --podaci")
        text, need, lists, said = transcript_material(a.dan, a.podaci, rec, r)
        prompt, what = sudija.WHOLE, "Prepis dana"
    print(f"{a.dan} from {a.izvor}: {len(text):,} characters, about {len(text) // 3:,} tokens in; speakers to name: {len(need)}")
    if a.bez_modela:
        print("\n".join(f"  {n} ({lists[n] or 'bez liste'}), {'has' if said.get(n) else 'NO'} text of their own" for n in need))
        return 0
    if not config.MODEL_KEY:
        sys.exit("ANTHROPIC_API_KEY is not set")
    done = sudija.whole_day(sudija.ask_claude, text, need, lists, said, roster_text(r), prompt, config.DAY_MODEL, what)
    report(done, need)
    if done is None:
        return 1
    dan = {**sudija.settle_votes(done["dan"]), "t": int(time.time()), "model": config.DAY_MODEL}
    if a.izvor == "beleske":
        dan["izvor"] = "beleske"
        kept = {"dan": dan, "delovi": [], "greske": 0, "model": config.DAY_MODEL, "izvor": "beleske"}
    else:
        old = a.podaci / "sazetak" / f"{a.dan}.json"
        kept = json.loads(old.read_text(encoding="utf-8")) if old.exists() else {"delovi": [], "greske": 0}
        kept.update({"dan": dan, "model": config.DAY_MODEL})
    for sub, body in (("sazetak", kept), ("osnova", {"model": config.DAY_MODEL, "oslonac": done["oslonac"], "bez_oslonca": done["bez_oslonca"]})):
        out = a.izlaz / sub / f"{a.dan}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(body, ensure_ascii=False, indent=1), encoding="utf-8")
        print("written:", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
