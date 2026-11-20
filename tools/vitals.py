"""How fast the pages are for those who open them: Core Web Vitals as Cloudflare Web Analytics measured them.

LCP (when the largest thing on the first screen is drawn; good up to 2.5 s), INP (how long the page takes to answer
a tap; good up to 200 ms) and CLS (how much the page jumps while loading; good up to 0.1), each as the share of
measured page loads that were good, middling and poor, by host and device and for the most opened pages. Google
judges a page by the 75th percentile, so "good" for three loads in four is the line to hold.

Asked of Cloudflare's GraphQL analytics by the `visits` workflow, with the account's token. Sums only, and a row
measured fewer than twenty times is left out: the log is public, and a share of so few says nothing. `schema` as
the first argument prints the fields Cloudflare offers instead (they have changed before)."""
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

API = "https://api.cloudflare.com/client/v4/graphql"
DATASET = "rumWebVitalsEventsAdaptiveGroups"
LEAST = 20
METRICS = (("LCP", "lcp"), ("INP", "inp"), ("CLS", "cls"))
SUMS = " ".join(f"{m}Good {m}NeedsImprovement {m}Poor {m}Total" for _, m in METRICS)


def post(query: str, variables: dict | None = None) -> dict:
    req = urllib.request.Request(API, data=json.dumps({"query": query, "variables": variables or {}}).encode(),
                                 headers={"Authorization": f"Bearer {os.environ['CLOUDFLARE_API_TOKEN']}",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def share(part: int, whole: int) -> str:
    return f"{round(100 * part / whole):>3}%" if whole else "   –"


def line(sums: dict) -> str:
    """Good / middling / poor for each metric, and how many loads it was measured on."""
    out = []
    for name, m in METRICS:
        whole = sums.get(f"{m}Total") or 0
        out.append(f"{name} {share(sums.get(f'{m}Good') or 0, whole)} {share(sums.get(f'{m}NeedsImprovement') or 0, whole)}"
                   f" {share(sums.get(f'{m}Poor') or 0, whole)} ({whole})")
    return "   ".join(out)


def groups(dimensions: str, variables: dict, limit: int) -> list:
    query = """query($acc: String!, $since: Time!, $until: Time!) { viewer { accounts(filter: {accountTag: $acc}) {
      rows: %s(limit: %d, orderBy: [count_DESC],
        filter: {datetime_geq: $since, datetime_leq: $until, bot: 0}) { count sum { %s } dimensions { %s } } } } }""" % (
        DATASET, limit, SUMS, dimensions)
    got = post(query, variables)
    if got.get("errors"):
        print("Cloudflare:", "; ".join(e.get("message", "?") for e in got["errors"])[:600])
        return []
    return got["data"]["viewer"]["accounts"][0]["rows"]


def schema():
    """The dataset's fields as Cloudflare names them now: found from the query's root, by name, a step at a time."""
    def fields(type_name: str) -> dict:
        got = post('{ __type(name: "%s") { fields { name type { name kind ofType { name kind ofType { name kind ofType { name } } } } } } }' % type_name)
        out = {}
        for f in ((got.get("data") or {}).get("__type") or {}).get("fields") or []:
            t = f["type"]
            while t and not t.get("name"):
                t = t.get("ofType")
            out[f["name"]] = (t or {}).get("name")
        return out
    root = ((post("{ __schema { queryType { name } } }").get("data") or {}).get("__schema") or {}).get("queryType", {}).get("name")
    at = root
    for step in ("viewer", "accounts"):
        at = fields(at).get(step)
    account = fields(at)
    print("Datasets with 'rum' in the name:", ", ".join(sorted(n for n in account if "rum" in n.lower())))
    row = fields(account.get(DATASET) or "")
    for part in sorted(row):
        inner = fields(row[part]) if row[part] else {}
        print(f"\n{DATASET}.{part}: {', '.join(sorted(inner)) or row[part]}")


def main(hours: int):
    until = datetime.now(timezone.utc)
    since = until - timedelta(hours=hours)
    variables = {"acc": os.environ["CLOUDFLARE_ACCOUNT_ID"], "since": since.strftime("%Y-%m-%dT%H:%M:%SZ"),
                 "until": until.strftime("%Y-%m-%dT%H:%M:%SZ")}
    print(f"Core Web Vitals, last {hours} h, to {variables['until']}: share of loads good / middling / poor, "
          f"(loads measured); rows under {LEAST} left out")
    print("Good: LCP to 2.5 s, INP to 200 ms, CLS to 0.1. The line to hold: good for 75% or more.")
    for title, dims, limit in (("By host and device", "requestHost deviceType", 12), ("By page", "requestHost requestPath", 30)):
        rows = groups(dims, variables, limit)
        print(f"\n{title}")
        for r in rows:
            if r["count"] >= LEAST:
                d = r["dimensions"]
                where = f"{d['requestHost']} {d.get('deviceType') or d.get('requestPath') or ''}".strip()
                print(f"  {line(r['sum'])}   {where}")


if __name__ == "__main__":
    if sys.argv[1:2] == ["schema"]:
        schema()
    else:
        main(int(sys.argv[1]) if len(sys.argv) > 1 else 24)
