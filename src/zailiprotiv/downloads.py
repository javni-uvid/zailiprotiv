"""Downloads: the laws and the roll calls as CSV and JSON.

Moved out of `site.build` (13 Nov 2026); it takes what it needs from the build as arguments.
"""
from __future__ import annotations

from zailiprotiv.site import (  # noqa: F401
    ORDINAL_NAME, VOTES, json, latin, mps
)


def write(*, common, domain, env, items_by_conv, out, people):
    # Downloads: every law with its final vote, and every MP's final votes by convocation (CSV), and the roll call
    # of each law beside its page (CSV and JSON).
    import csv, io
    site_url = f"https://{domain}/" if domain else ""

    def display_name(name):
        mp = people.get(mps.key(name))
        return mp.name if mp else name
    (out / "podaci").mkdir(exist_ok=True)
    def write_csv(path, header, rows):
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(header)
        w.writerows(rows)
        path.write_text(buf.getvalue(), encoding="utf-8")
    write_csv(out / "podaci" / "zakoni.csv",
              ["saziv", "usvojen", "kratak_naziv", "zvanican_naziv", "vrsta", "oblast", "za", "protiv", "uzdrzan",
               "nije_glasao", "nije_prisutan", "strana", "glasanje_pdf", "zakon_pdf", "predlog_pdf"],
              [[it["conv"], it["law"].get("passed"), it["law"]["short"], latin(it["law"]["title"]), latin(it["kind"]),
                "; ".join(latin(a) for a in it.get("areas") or []),
                *[(it["final"] or {}).get("counts", {}).get(v, "") if it.get("final") else "" for v in VOTES],
                f"{site_url}zakon/{it['slug']}.html", (it.get("final") or {}).get("key", "").split("#")[0],
                it["law"].get("pdf", ""), it["law"].get("bill_pdf", "")]
               for its in items_by_conv.values() for it in its])
    downloads = []
    for conv, its in items_by_conv.items():
        rows = []
        for it in its:
            f = it.get("final")
            if not f:
                continue
            for _, name, how, group in f["rows"]:
                rows.append([it["law"].get("passed"), it["law"]["short"], display_name(name), latin(group), how])
        write_csv(out / "podaci" / f"glasovi-{conv}.csv", ["usvojen", "zakon", "poslanik", "grupa", "glas"], rows)
        downloads.append({"conv": conv, "name": ORDINAL_NAME.get(conv, conv), "rows": len(rows), "laws": len(its)})
        for it in its:
            f = it.get("final")
            if f:
                roll = [[display_name(n), latin(g), how] for _, n, how, g in f["rows"]]
                write_csv(out / "zakon" / f"{it['slug']}.csv", ["poslanik", "grupa", "glas"], roll)
                (out / "zakon" / f"{it['slug']}.json").write_text(json.dumps(
                    {"zakon": it["law"]["short"], "zvanican_naziv": latin(it["law"]["title"]), "usvojen": it["law"].get("passed"),
                     "glasanje": f["when"], "pdf": f["key"].split("#")[0], "rezultat": f["counts"],
                     "glasovi": [{"poslanik": a, "grupa": b, "glas": c} for a, b, c in roll]},
                    ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "podaci.html").write_text(env.get_template("data.html").render(**common, downloads=downloads, root=""),
                                     encoding="utf-8")
    (out / "kako-racunamo.html").write_text(env.get_template("method.html").render(**common, root=""), encoding="utf-8")
    if domain:
        (out / "CNAME").write_text(domain + "\n", encoding="utf-8")
        base = f"https://{domain}/"
        pages = sorted(p.relative_to(out).as_posix() for p in out.rglob("*.html"))
        (out / "sitemap.xml").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + "".join(f"<url><loc>{base}{p}</loc></url>\n" for p in pages) + "</urlset>\n", encoding="utf-8")
        (out / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {base}sitemap.xml\n", encoding="utf-8")
