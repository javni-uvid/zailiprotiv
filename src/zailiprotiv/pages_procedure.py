"""Bills in procedure and the sittings convened.

Moved out of `site.build` (13 Nov 2026); it takes what it needs from the build as arguments.
"""
from __future__ import annotations

from zailiprotiv.site import (  # noqa: F401
    days_between, dt, json, kinds, slug
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
    # Every bill gets a page of its own (predlog/<name>.html): what is known of it while it waits. The name comes
    # from the title and, when two bills share one, the file's own name at the Assembly, so it does not move when
    # another bill arrives. A bill since passed keeps its address and sends the reader on to the law's page.
    names = {}
    for row in waiting + gone:
        base = slug(row["title"])
        names.setdefault("zakon-" + base[len("predlog-zakona-"):] if base.startswith("predlog-zakona-") else base, []).append(row)
    (out / "predlog").mkdir(exist_ok=True)
    page = env.get_template("bill.html")
    for base, rows in names.items():
        for row in rows:
            row["slug"] = base if len(rows) == 1 else f"{base}-{slug(row['pdf'].rsplit('/', 1)[-1].removesuffix('.pdf'))}"
    shared = {row["slug"] for rows in names.values() if len(rows) > 1 for row in rows}  # one title, several bills
    for row in waiting + gone:
        row["summary"] = loaded[current][2].get(row.get("bill_file", ""), {}).get("summary")
        row["ocr"] = bool(loaded[current][2].get(row.get("bill_file", ""), {}).get("ocr"))
        (out / "predlog" / f"{row['slug']}.html").write_text(page.render(  # a title shared by several: with its day
            **common, b=row, waits=row in waiting, checked=proc["fetched"], root="../",
            shared=row["slug"] in shared), encoding="utf-8")
    # The counter accepts votes on the bills that wait, by the name "p.<bill>": added to the list the build wrote.
    allowed_path = out / "glasanje.json"
    if allowed_path.exists():
        allowed = json.loads(allowed_path.read_text(encoding="utf-8"))
        allowed["laws"].update({"p." + row["slug"]: [] for row in waiting})
        allowed_path.write_text(json.dumps(allowed, separators=(",", ":")), encoding="utf-8")
    waiting.sort(key=lambda r: (r["submitted"] or "", r["title"]), reverse=True)
    gone.sort(key=lambda r: (r["last_seen"], r["submitted"] or ""), reverse=True)
    who_label = {"vlada": "Vlada", "poslanici": "Poslanici", "drugi": "Drugi predlagači"}
    (out / "u-proceduri.html").write_text(env.get_template("procedure.html").render(
        **common, waiting=waiting, gone=gone[:200], coming=coming, checked=proc["fetched"], who_label=who_label,
        who_counts=[(k, who_label[k], sum(1 for r in waiting if r["who"] == k)) for k in who_label],
        oldest=min((r["submitted"] for r in waiting if r["submitted"]), default=None), root=""), encoding="utf-8")
    render.gone = gone
    return coming, waiting
