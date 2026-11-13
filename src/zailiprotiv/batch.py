"""Many requests to the model at once, through the Message Batches API: half the price of single calls, and the
writing runs in GitHub Actions instead of a Claude session.

A batch can take from minutes to hours. Its id is kept in data/batches.json (committed), so a run that stops
waiting picks the results up next time instead of paying for them again. The same file counts how often a reply
failed its check, with the last reply and what was wrong, so the next try can be asked to fix it, and a request is
not sent again after `TRIES` failures (those wait for a person).
"""
from __future__ import annotations

import json
import time
from pathlib import Path

TRIES = 2
POLL = 60  # seconds between looks at a batch
# Room for a reply, in tokens. Only what is written is paid for, so this is generous: Cyrillic takes many tokens,
# and a reply cut off at the limit is paid for and thrown away.
ROOM = 16000


class State:
    """data/batches.json: {"pending": {kind: {"id", "names"}}, "refused": {kind: {name: {"tries", "reply", "errors"}}},
    "usage": {kind: {model: {"replies", "input", "cache_written", "cache_read", "output"}}}}."""

    def __init__(self, path: Path):
        self.path = path
        self.data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        self.data.setdefault("pending", {})
        self.data.setdefault("refused", {})
        self.data.setdefault("usage", {})

    def save(self) -> None:
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    def pending(self, kind: str) -> dict | None:
        return self.data["pending"].get(kind)

    def refused(self, kind: str, name: str) -> dict | None:
        return self.data["refused"].get(kind, {}).get(name)

    def gave_up(self, kind: str, name: str) -> bool:
        r = self.refused(kind, name)
        return bool(r and r["tries"] >= TRIES)

    def spent(self, kind: str, message) -> None:
        """Add one reply's tokens to the count of its kind and model (what the writing has cost so far)."""
        u = getattr(message, "usage", None)
        if u is None:
            return
        row = self.data["usage"].setdefault(kind, {}).setdefault(getattr(message, "model", "") or "?", {})
        for key, field in (("replies", None), ("input", "input_tokens"), ("cache_written", "cache_creation_input_tokens"),
                           ("cache_read", "cache_read_input_tokens"), ("output", "output_tokens")):
            row[key] = row.get(key, 0) + (1 if field is None else getattr(u, field, 0) or 0)

    def refuse(self, kind: str, name: str, reply: str, errors: list[str]) -> None:
        r = self.data["refused"].setdefault(kind, {}).setdefault(name, {"tries": 0})
        r.update(tries=r["tries"] + 1, reply=reply[:20000], errors=errors[:20])

    def accept(self, kind: str, name: str) -> None:
        self.data["refused"].get(kind, {}).pop(name, None)
        if not self.data["refused"].get(kind):
            self.data["refused"].pop(kind, None)


def cached(system: str) -> list[dict]:
    """The rules, marked for the prompt cache: every request of a batch sends the same rules, and the cache's
    discount adds to the batch's (best effort, as requests run side by side)."""
    return [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]


def messages(kind: str, name: str, user: str, state: State) -> list[dict]:
    """The conversation for one request: the material, and after a refused reply, that reply and what was wrong."""
    msgs = [{"role": "user", "content": user}]
    r = state.refused(kind, name)
    if r and r.get("reply"):
        msgs += [{"role": "assistant", "content": r["reply"]},
                 {"role": "user", "content": "Провера је одбила одговор:\n- " + "\n- ".join(r["errors"]) +
                  "\nИсправи то и врати цео JSON објекат поново, без иједне речи пре или после."}]
    return msgs


def run(client, state: State, kind: str, requests: dict[str, dict], wait_minutes: float,
        force: bool = False) -> dict[str, str] | None:
    """Send `requests` ({name: Messages API params}) as one batch, or pick up the batch of this kind already sent,
    and wait for it. The text of each reply by name; None if the batch is still running after `wait_minutes` (its id
    stays in the state for the next run). Names may be any text: the API sees their position only."""
    pending = state.pending(kind)
    if pending is None:
        if not requests:
            return {}
        if state.data.get("paused") and not force:  # "paused": true in data/batches.json: finish what was sent, send nothing new
            print(f"{kind}: paused, {len(requests)} requests not sent")
            return {}
        names = sorted(requests)
        batch = client.messages.batches.create(requests=[{"custom_id": f"r{i}", "params": requests[n]}
                                                         for i, n in enumerate(names)])
        pending = {"id": batch.id, "names": names}
        state.data["pending"][kind] = pending
        state.save()
        print(f"{kind}: batch {batch.id} sent, {len(names)} requests")
    else:
        print(f"{kind}: picking up batch {pending['id']} ({len(pending['names'])} requests)")
    deadline = time.monotonic() + wait_minutes * 60
    while True:
        batch = client.messages.batches.retrieve(pending["id"])
        if batch.processing_status == "ended":
            break
        if time.monotonic() >= deadline:
            print(f"{kind}: batch {pending['id']} still running, results next run")
            return None
        time.sleep(POLL)
    out = {}
    for entry in client.messages.batches.results(pending["id"]):
        name = pending["names"][int(entry.custom_id[1:])]
        if entry.result.type == "succeeded":
            state.spent(kind, entry.result.message)
        if entry.result.type == "succeeded" and getattr(entry.result.message, "stop_reason", "") == "max_tokens":
            print(f"  {name}: cut off at the limit, sent again next run")  # our limit's fault: not a refused reply
        elif entry.result.type == "succeeded":
            out[name] = "".join(b.text for b in entry.result.message.content if getattr(b, "type", "") == "text")
        else:
            print(f"  {name}: {entry.result.type}")
    del state.data["pending"][kind]
    state.save()
    return out
