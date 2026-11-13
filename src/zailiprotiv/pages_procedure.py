"""Bills in procedure and the sittings convened.

Moved out of `site.build` (13 Nov 2026); it takes what it needs from the build as arguments.
"""
from __future__ import annotations

from zailiprotiv.site import (  # noqa: F401
    days_between, dt, json, kinds
)


def render(*, common, current, env, items_by_conv, loaded, out, root):
    # Bills in procedure (the current convocation): what waits now, what is no longer listed, and the sittings
    # convened whose votes are not out yet, with their agenda.
    from zailiprotiv import link as link_, procedure as procedure_
    proc_path, index_path = root / current / "procedure.json", root / current / "index.json"
    proc = json.loads(proc_path.read_text(encoding="utf-8")) if proc_path.exists() else {"bills": {}, "fetched": ""}
    sittings_index = json.loads(index_path.read_text(encoding="utf-8"))["sittings"] if index_path.exists() else {}
    today = dt.date.today()
    coming = sorted(({"title": sv["title"], "url": u, "starts": sv.get("starts", ""), "agenda": sv["agenda"]}
                     for u, sv in sittings_index.items() if sv.get("agenda") and not sv.get("votes")
                     and (sv.get("starts") or "9999")[:10] >= (today - dt.timedelta(days=45)).isoformat()),
                    key=lambda x: x["starts"])
    on_agenda = {}
    for sv in coming:
        for item in sv["agenda"]:
            on_agenda.setdefault(link_.act_name(item), sv)
    by_bill_pdf = {it["law"].get("bill_pdf"): it for it in items_by_conv[current] if it["law"].get("bill_pdf")}
    waiting, gone = [], []
    for pdf, b in proc["bills"].items():
        row = {**b, "pdf": pdf, "who": procedure_.proposer_kind(b["proposer"]),
               "kind": kinds.KINDS.get(kinds.kind(b["title"]), ""), "kind_key": kinds.kind(b["title"]),
               "days": days_between(b["submitted"], today.isoformat()), "law": by_bill_pdf.get(pdf),
               "gist": ((loaded[current][2].get(b.get("bill_file", ""), {}).get("summary") or {}).get("summary") or {}).get("ukratko", ""),
               "areas": b.get("areas") or [],
               "sitting": on_agenda.get(link_.act_name(b["title"]))}
        (waiting if b["last_seen"] == proc["fetched"] and not row["law"] else gone).append(row)
    waiting.sort(key=lambda r: (r["submitted"] or "", r["title"]), reverse=True)
    gone.sort(key=lambda r: (r["last_seen"], r["submitted"] or ""), reverse=True)
    who_label = {"vlada": "Vlada", "poslanici": "Poslanici", "drugi": "Drugi predlagači"}
    (out / "u-proceduri.html").write_text(env.get_template("procedure.html").render(
        **common, waiting=waiting, gone=gone[:200], coming=coming, checked=proc["fetched"], who_label=who_label,
        who_counts=[(k, who_label[k], sum(1 for r in waiting if r["who"] == k)) for k in who_label],
        oldest=min((r["submitted"] for r in waiting if r["submitted"]), default=None), root=""), encoding="utf-8")
    return coming, waiting
