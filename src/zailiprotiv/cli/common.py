"""What the commands share: the data folder of the convocation worked on (set by `main` from --convocation), and
helpers."""

from __future__ import annotations

import json
import re
import urllib.parse
from pathlib import Path

from zailiprotiv import jsonfile
from zailiprotiv.config import CURRENT


ROOT = Path("data")
DATA = ROOT / CURRENT  # the convocation's own folder; `--convocation N` before the command picks another
CONVOCATION = CURRENT


def _shrunk(path: Path, what: str, now: int, counts=lambda v: True) -> bool:
    """True, with a warning, when a new reading has far fewer entries than the file it would replace: the Assembly's
    page then shows something else (a new convocation's empty list, an error page), and what was read is kept. A
    convocation's laws and sittings only grow."""
    if not path.exists():
        return False
    before = sum(1 for v in jsonfile.load(path)[what].values() if counts(v))
    if jsonfile.shrank(now, before, least=10):
        print(f"::warning::{what}: the Assembly's page gives {now}, the file has {before}. Kept the file: has a new "
              f"convocation taken over the page? See AGENTS.md, 'The Fifteenth convocation'.")
        return True
    return False


def all_votes(folder: Path) -> dict[str, dict]:
    out = {}
    for path in sorted(folder.glob("*.json")):
        store = json.loads(path.read_text(encoding="utf-8"))
        for key, v in store["votes"].items():
            out[key] = {**v, "sitting": store["sitting"]}
    return out


def _waiting(laws_path: Path) -> tuple[Path, dict, list[dict]]:
    """The bills in procedure now (procedure.json beside laws.json), as records the commands for laws can read: each
    with its `bill_pdf`. They are read and summarised like the bills of adopted laws, before the vote."""
    path = laws_path.parent / "procedure.json"
    if not path.exists():
        return path, {}, []
    store = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for pdf, b in store["bills"].items():
        if b["last_seen"] == store["fetched"]:
            b["bill_pdf"] = pdf
            out.append(b)
    return path, store, out


def sitting_id(url: str) -> str:
    """The number the Assembly's site gives a sitting's page ("…_Народне.53524.43.html" → "53524")."""
    m = re.search(r"\.(\d+)\.43\.html$", urllib.parse.unquote(url))
    return m.group(1) if m else re.sub(r"\W+", "_", url)[-40:]


def file_name(url: str) -> str:
    """A plain file name for a roll call or a bill, from its address below its folder: ASCII, no spaces."""
    path = urllib.parse.unquote(urllib.parse.urlsplit(url).path)
    path = re.split(r"rezultati_glasanja/|Listinzi/|predlozi_zakona/", path, flags=re.I)[-1]
    return re.sub(r"[^A-Za-z0-9.-]+", "_", path).strip("_").lower()


def _pending(args):
    """Laws whose bill has a memorandum and no current summary, newest first: (law, memo, bill file name)."""
    from zailiprotiv import summaries
    store = json.loads(Path(args.laws).read_text(encoding="utf-8"))
    out = []
    for law in sorted(store["laws"].values(), key=lambda l: (l.get("passed") or "", l["title"]), reverse=True):
        name = law.get("bill_file")
        if not name or not (Path(args.bills) / name).exists():
            continue
        memo = json.loads((Path(args.bills) / name).read_text(encoding="utf-8"))
        if not memo.get("sections"):
            continue
        target = Path(args.out) / name
        if target.exists() and json.loads(target.read_text(encoding="utf-8")).get("fingerprint") == \
                summaries.fingerprint(summaries.material(law, memo)):
            continue
        out.append((law, memo, name))
    return out


def _debated(args):
    """The laws whose sitting's notes have been read, with what debates.material needs: (law, bill, notes, final,
    item), the most votes against first."""
    from zailiprotiv import site
    laws_, votes_, bills_ = site.load(DATA)
    notes = site.load_transcripts(DATA)
    items = [{"law": l, "final": votes_.get(l.get("final_vote") or "")} for l in laws_["laws"].values()]
    out = []
    for it in site.most_against(items, len(items)):
        law, final = it["law"], it["final"]
        n = notes.get(final["sitting"])
        d = site.debate_of(law, final, n) if n else None
        if d and law.get("bill_file"):
            out.append((law, bills_.get(law["bill_file"], {}), n, final, d["item"]))
    return out, votes_, bills_


def _batch_client(args):
    """The API client and the batch state, or None when there is no way in (the workflow then does nothing): an API
    key, or in GitHub Actions the repository's identity exchanged for a short-lived token (`federated`)."""
    import os
    from zailiprotiv import batch, federated
    state = batch.State(ROOT / "batches.json")
    if os.environ.get("ANTHROPIC_API_KEY"):
        import anthropic
        return anthropic.Anthropic(), state
    if federated.available():
        return federated.client(), state
    print("No ANTHROPIC_API_KEY and no federated sign-in: nothing sent")
    return None, None
