"""A sitting's summary written from its days' summaries (28 Nov 2026; the maintainer: "Dodatno želim summary za sednicu
na osnovu tekstova summary za specifične dane"). The only material is the days' published files (data/<N>/sazetak/<day>.json:
naslov, kratko, ukratko, odluke), never a transcript or the notes: the sitting's summary says nothing the days' do not.
The day's model (DAY_MODEL) and the day summary's rules (sudija._RULES), run from the repository on a computer.

    PYTHONUTF8=1 uv run python tools/sazetak_sednice.py <sitting's page name> <day> [<day> ...] [--izlaz <folder>] [--bez-modela]

<sitting's page name> is the name of its page on the site (`sednica/<name>`); the days are those of the sitting with a
day summary. Written: <folder>/sednica-<name>.json, the folder by default the convocation's `data/<N>/sazetak/`, where the
site reads it: {"naslov", "kratko", "ukratko", "dani", "model", "izvor": "dani", "t"}. Checked before it is written: every
figure and every name (a word in capitals not opening a sentence) in the reply occurs in the days' texts; the reply is
asked once more with what failed, and nothing is written when it still fails. `--bez-modela`: only what would be sent,
and its size. Needs ANTHROPIC_API_KEY."""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "src"), str(REPO / "live")]
from uzivo import config, sudija  # noqa: E402

PROMPT = f"""Pišeš sažetak cele sednice Narodne skupštine Srbije iz sažetaka njenih dana. Ti sažeci su jedini izvor: ne
dodaješ ništa čega u njima nema, ni iz sopstvenog znanja.

{sudija._RULES.replace("u prepisu", "u sažecima dana").replace("prepis nije izvor za citat", "sažeci nisu izvor za citat").replace("kako su izgovoreni u prepisu", "kako stoje u sažecima dana")}
8. Ne praviš spisak govornika i ne prepričavaš pojedine govore. Ime pišeš samo kad je ono deo odluke (izbor, imenovanje,
   ostavka) i tačno kako stoji u sažecima dana.
9. Glasove ne navodiš.

IZLAZ: samo JSON, bez ikakvog drugog teksta:
{{"naslov": "najviše 60 znakova: šta je Skupština na ovoj sednici odlučila, kao cela kratka rečenica, bez nabrajanja,
   bez brojeva i bez ocene",
 "kratko": "dve ili tri rečenice, najviše 400 znakova: glavne odluke sednice",
 "ukratko": "jedan pasus, 5 do 7 rečenica: tok sednice po danima i njene odluke"}}"""

_NUM = re.compile(r"\d+(?:[.,]\d+)*")
_WORD = re.compile(r"[A-ZČĆŽŠĐ][\wčćžšđČĆŽŠĐ-]*")


def _fold(s: str) -> str:
    return sudija._fold(s)


def material(conv: Path, days: list[str]) -> tuple[str, str]:
    """The days' summaries as the model reads them, and all their text (for the checks)."""
    parts, plain = [], []
    for d in sorted(days):
        f = conv / "sazetak" / f"{d}.json"
        if not f.exists():
            sys.exit(f"no summary of {d} at {f}")
        dan = json.loads(f.read_text(encoding="utf-8")).get("dan") or {}
        if not dan.get("ukratko"):
            sys.exit(f"{f} has no day summary")
        decisions = [o.get("sta", "") for o in dan.get("odluke") or [] if isinstance(o, dict) and o.get("sta")]
        block = [f"Dan {d}", f"Naslov: {dan.get('naslov', '')}", f"Kratko: {dan.get('kratko', '')}",
                 f"Ukratko: {dan.get('ukratko', '')}"] + (["Odluke:"] + [f"- {x}" for x in decisions] if decisions else [])
        parts.append("\n".join(block))
        plain += [d, dan.get("naslov", ""), dan.get("kratko", ""), dan.get("ukratko", "")] + decisions
    return "\n\n".join(parts), "\n".join(plain)


def unfounded(s: dict, source: str) -> list[str]:
    """What the reply says that the days' texts do not: a figure, or a name (a capitalised word not opening a sentence;
    Serbian names change their ending, so its first letters, all but the last two, must open a word of the days)."""
    words = {_fold(w) for w in re.findall(r"[\wčćžšđČĆŽŠĐ]+", source)}
    nums = set(_NUM.findall(source))
    out = []
    for key in ("naslov", "kratko", "ukratko"):
        text = s.get(key) or ""
        out += [f"broj {n!r} ({key}) nije u sažecima dana" for n in _NUM.findall(text) if n not in nums]
        for sentence in re.split(r"(?<=[.!?:])\s+", text):
            for m in list(_WORD.finditer(sentence))[1:] if sentence else []:
                w = _fold(m.group())
                stem = w[:max(4, len(w) - 2)]
                if not any(x.startswith(stem) for x in words):
                    out.append(f"ime {m.group()!r} ({key}) nije u sažecima dana")
    return out


def shape(s: dict | None) -> list[str]:
    if not isinstance(s, dict):
        return ["nema odgovora"]
    out = [f"nema polja {k!r}" for k in ("naslov", "kratko", "ukratko") if not isinstance(s.get(k), str) or not s[k].strip()]
    if not out and len(s["naslov"]) > 80:
        out.append("naslov je duži od 60 znakova")
    return out


def write(ask, text: str, source: str, model: str) -> tuple[dict | None, list[str]]:
    """The sitting's summary asked of `model`, checked, asked once more with what was wrong: (summary, []) or
    (None, what the last reply failed)."""
    note, failed = "", ["nije pitano"]
    for _ in range(2):
        s = sudija.reply_json(ask(PROMPT, "Sažeci dana sednice:\n\n" + text + note, 32000, "medium", model))
        failed = shape(s) or unfounded(s, source)
        if not failed:
            return {k: s[k].strip() for k in ("naslov", "kratko", "ukratko")}, []
        note = "\n\nPrethodni odgovor nije prošao proveru: " + "; ".join(failed) + ". Napiši ga ponovo po pravilima."
    return None, failed


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("sednica", help="the sitting's page name on the site (sednica/<name>)")
    ap.add_argument("dani", nargs="+")
    ap.add_argument("--izlaz", type=Path, help="default: the convocation's data/<N>/sazetak/")
    ap.add_argument("--bez-modela", action="store_true")
    a = ap.parse_args(argv)
    found = sorted({f.parent.parent for d in a.dani for f in REPO.glob(f"data/*/sazetak/{d}.json")})
    if len(found) != 1:
        sys.exit(f"the days' summaries are not in one convocation's data/<N>/sazetak: {found or 'none found'}")
    conv = found[0]
    text, source = material(conv, a.dani)
    print(f"{a.sednica}: {len(a.dani)} days, {len(text):,} characters, about {len(text) // 3:,} tokens in")
    if a.bez_modela:
        print("\n--- system ---\n" + PROMPT + "\n\n--- material ---\n" + text)
        return 0
    if not config.MODEL_KEY:
        sys.exit("ANTHROPIC_API_KEY is not set")
    s, failed = write(sudija.ask_claude, text, source, config.DAY_MODEL)
    if s is None:
        print("NO SUMMARY: the reply still fails:", "; ".join(failed))
        return 1
    print(f"naslov: {s['naslov']}\nkratko: {s['kratko']}\nukratko: {s['ukratko']}")
    out = (a.izlaz or conv / "sazetak") / f"sednica-{a.sednica}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    body = {**s, "dani": sorted(a.dani), "model": config.DAY_MODEL, "izvor": "dani", "t": int(time.time())}
    out.write_text(json.dumps(body, ensure_ascii=False, indent=1), encoding="utf-8")
    print("written:", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
