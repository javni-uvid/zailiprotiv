"""What Cloudflare Web Analytics counted on the site: pages, where visitors came from, devices, hours.

Asked of Cloudflare's GraphQL analytics by the `visits` workflow, with the account's token. Only sums are printed,
and a row seen fewer than three times is left out: the run's log is public, and a sum of one can be a person.
No address, no single request, nothing about any one visitor is asked for at all."""
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

API = "https://api.cloudflare.com/client/v4/graphql"
LEAST = 3


def ask(query: str, variables: dict) -> dict:
    req = urllib.request.Request(API, data=json.dumps({"query": query, "variables": variables}).encode(),
                                 headers={"Authorization": f"Bearer {os.environ['CLOUDFLARE_API_TOKEN']}",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        got = json.load(r)
    if got.get("errors"):
        print("Cloudflare:", "; ".join(e.get("message", "?") for e in got["errors"])[:600])
        return {}
    return got["data"]["viewer"]["accounts"][0]


def groups(dimension: str, variables: dict, limit: int = 40, order: str = "sum_visits_DESC") -> list:
    query = """query($acc: String!, $since: Time!, $until: Time!) { viewer { accounts(filter: {accountTag: $acc}) {
      rows: rumPageloadEventsAdaptiveGroups(limit: %d, orderBy: [%s],
        filter: {datetime_geq: $since, datetime_leq: $until, bot: 0}) { count sum { visits } dimensions { %s } } } } }""" % (limit, order, dimension)
    return ask(query, variables).get("rows", [])


def came_from(variables: dict, own: set):
    """The day a visit came from another site and the page it came to: which day's post brought readers where.
    Not the other site's page: browsers send only its address's host (the default referrer policy since 2020), so
    Cloudflare's refererPath is "/" for all (tried 22 Nov 2026). Sums of three or more, as everywhere."""
    dims = "refererHost date requestHost requestPath"
    print("\nCame from, by day  (page views / visits; the other site -> our page)")
    shown = 0
    for r in groups(dims, variables, 200, "count_DESC"):
        d = r["dimensions"]
        host = d["refererHost"] or ""
        if r["count"] < LEAST or not host or host in own or host.endswith(".zailiprotiv.rs"):
            continue
        print(f"  {r['count']:>6} {r['sum']['visits']:>6}  {d['date']}  {host}  ->  {d['requestHost']}{d['requestPath']}")
        shown += 1
        if shown == 40:
            break


def main(hours: int):
    until = datetime.now(timezone.utc)
    since = until - timedelta(hours=hours)
    variables = {"acc": os.environ["CLOUDFLARE_ACCOUNT_ID"], "since": since.strftime("%Y-%m-%dT%H:%M:%SZ"),
                 "until": until.strftime("%Y-%m-%dT%H:%M:%SZ")}
    print(f"Web Analytics, last {hours} h, to {variables['until']} (browsers only; rows under {LEAST} left out)")
    total = groups("requestHost", variables)
    for r in total:
        if r["count"] >= LEAST:
            print(f"  {r['dimensions']['requestHost']}: {r['count']} page views, {r['sum']['visits']} visits")
    for title, dim, limit in (("Pages", "requestPath", 60), ("Came from", "refererHost", 25), ("Device", "deviceType", 5),
                              ("Country", "countryName", 12), ("Browser", "userAgentBrowser", 8)):
        rows = groups(dim, variables, limit, "count_DESC")
        print(f"\n{title}  (page views / visits)")
        for r in rows:
            if r["count"] >= LEAST:
                print(f"  {r['count']:>6} {r['sum']['visits']:>6}  {r['dimensions'][dim] or '(none)'}")
    came_from(variables, {r["dimensions"]["requestHost"] for r in total})
    rows = groups("datetimeHour", variables, hours + 2, "datetimeHour_ASC")
    print("\nBy hour, UTC  (page views / visits)")
    for r in rows:
        print(f"  {r['dimensions']['datetimeHour'][5:16]}  {r['count']:>5} {r['sum']['visits']:>5}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 24)
