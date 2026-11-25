"""Whether an agent is in a worktree, by what Orca says (pocisti.sh asks before it removes one).

    uv run --no-project agenti.py <worktree> <orca worktree ps --json> <orca terminal list --json>

Exit 0: nobody is, the worktree may go. Exit 1: somebody is, or it can't be told; the reason is printed. Whatever
is missing, cut short or shaped otherwise is "can't be told": a folder kept costs little, a stopped session a lot.
An agent open in a terminal of the worktree keeps it, whether it works, waits for an answer or is idle; one that has
been done and silent for QUIET keeps it no more (a worker nobody closed), nor does one whose terminal is gone for as
long. Orca drops an agent from both lists some seconds after it exits. Only the standard library."""
import json
import sys
import time

QUIET = 24 * 3600.0  # seconds; a worktree is a day's at most (work.md)


def _path(p) -> str:
    return str(p or "").replace("\\", "/").rstrip("/").casefold()


def _rows(told, key):
    """The list in an answer of Orca's; None when it isn't there whole."""
    r = told.get("result") if isinstance(told, dict) and told.get("ok") is True else None
    rows = r.get(key) if isinstance(r, dict) else None
    whole = isinstance(rows, list) and r.get("truncated") is False and all(isinstance(x, dict) for x in rows)
    return rows if whole else None


def keeps(worktree: str, ps, terminals, now: float) -> str:
    """Why the worktree stays; empty when nobody is in it."""
    here = _path(worktree)
    ps, terminals = _rows(ps, "worktrees"), _rows(terminals, "terminals")
    if ps is None or terminals is None:
        return "Orca nije rekla ko u njemu radi"
    mine = [w for w in ps if _path(w.get("path")) == here]
    if not mine:
        return "Orca ga ne zna"
    known = set()
    for w in mine:
        agents = w.get("agents")
        if not isinstance(agents, list) or not all(isinstance(a, dict) for a in agents):
            return "Orca nije rekla ko u njemu radi"
        for a in agents:
            known.add(a.get("address"))
            at, live, state = a.get("updatedAt"), a.get("hasLivePty") is not False, a.get("state")
            silent = now - at / 1000 if isinstance(at, (int, float)) else 0.0
            if silent <= QUIET or (live and state != "done"):
                return f"u njemu je agent {a.get('agentType') or '?'} ({state or '?'}, {silent / 3600:.1f} h bez promene)"
    for t in terminals:
        at = t.get("worktreePath") or str(t.get("worktreeId") or "").partition("::")[2]
        if _path(at) == here and t.get("agentIdentity") and t.get("connected") is not False and t.get("handle") not in known:
            return f"u njemu je agent {t['agentIdentity']}"
    return ""


def _read(name):
    try:
        with open(name, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    why = keeps(sys.argv[1], _read(sys.argv[2]), _read(sys.argv[3]), time.time())
    print(why)
    sys.exit(1 if why else 0)
