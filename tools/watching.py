"""How long "Ko sada govori" (mikrofon.zailiprotiv.rs) is looked at, from sums only.

While the page is in view it asks for its changing part (`/deo`, `/cir/deo`) every five seconds and stops while
hidden (live/uzivo/page.py), so the zone's count of those requests, times five seconds, is the time the page was in
front of someone; per hour, the count divided by 720 is how many had it open at once, on average. Divided by Web
Analytics' visits it is the mean time a visit kept the page in view. A mean only: no visit is followed, and no
address, single request or visitor is asked for. While the service is down the page shown asks for nothing, so those
hours count no time.

Asked by the `visits` workflow with the account's token (Zone: Read and Zone → Analytics: Read, as tools/blocked.py).
"""
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

API = "https://api.cloudflare.com/client/v4"
HOST = "mikrofon.zailiprotiv.rs"
PARTS = ("/deo", "/cir/deo")
EVERY = 5  # seconds between two asks of the page's part while it is in view


def call(path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(API + path, data=json.dumps(body).encode() if body else None,
                                 headers={"Authorization": f"Bearer {os.environ['CLOUDFLARE_API_TOKEN']}",
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return {"errors": [{"message": f"{e.code} {e.read()[:300]!r}"}]}


def graph(query: str, variables: dict, where: str) -> list:
    got = call("/graphql", {"query": query, "variables": variables})
    if got.get("errors"):
        print("  Cloudflare:", "; ".join(e.get("message", "?") for e in got["errors"])[:600])
        return []
    return got["data"]["viewer"][where][0]["rows"]


def minutes(seconds: float) -> str:
    return f"{seconds / 60:.1f} min"


def main(hours: int):
    zones = call("/zones?name=zailiprotiv.rs")
    if not zones.get("result"):
        print("The zone could not be read (the token needs Zone: Read):", zones.get("errors"))
        return
    until = datetime.now(timezone.utc)
    since = until - timedelta(hours=min(hours, 24))  # the adaptive groups keep a day at most on the free plan
    v = {"zone": zones["result"][0]["id"], "acc": os.environ["CLOUDFLARE_ACCOUNT_ID"],
         "since": since.strftime("%Y-%m-%dT%H:%M:%SZ"), "until": until.strftime("%Y-%m-%dT%H:%M:%SZ")}
    q = """query($zone: String!, $since: Time!, $until: Time!) { viewer { zones(filter: {zoneTag: $zone}) {
      rows: httpRequestsAdaptiveGroups(limit: 100, orderBy: [datetimeHour_ASC],
        filter: {datetime_geq: $since, datetime_leq: $until, clientRequestHTTPHost: "%s",
                 clientRequestPath_in: [%s], edgeResponseStatus: 200}) {
        count dimensions { datetimeHour } } } } }""" % (HOST, ", ".join(f'"{p}"' for p in PARTS))
    asks = {r["dimensions"]["datetimeHour"]: r["count"] for r in graph(q, {k: v[k] for k in ("zone", "since", "until")}, "zones")}
    q = """query($acc: String!, $since: Time!, $until: Time!) { viewer { accounts(filter: {accountTag: $acc}) {
      rows: rumPageloadEventsAdaptiveGroups(limit: 100, orderBy: [datetimeHour_ASC],
        filter: {datetime_geq: $since, datetime_leq: $until, bot: 0, requestHost: "%s"}) {
        count sum { visits } dimensions { datetimeHour } } } } }""" % HOST
    visits = {r["dimensions"]["datetimeHour"]: r["sum"]["visits"]
              for r in graph(q, {k: v[k] for k in ("acc", "since", "until")}, "accounts")}
    print(f"How long {HOST} is in view, {v['since']} to {v['until']} (from its part asked every {EVERY} s while in view)")
    if not asks:
        print("  nothing counted")
        return
    print("  hour, UTC     open at once (= hours in view)   visits   per visit")
    for hour in sorted(set(asks) | set(visits)):
        n, seen = asks.get(hour, 0), visits.get(hour, 0)
        per = minutes(n * EVERY / seen) if seen else "-"
        print(f"  {hour[5:16]}  {n * EVERY / 3600:>12.0f}                     {seen:>6}   {per:>9}")
    n, seen = sum(asks.values()), sum(visits.values())
    print(f"\n  in all: {n * EVERY / 3600:.0f} h in view over {seen} visits, {minutes(n * EVERY / seen) if seen else '-'} a visit"
          " on average (a mean: a few long watchers weigh as much as many short visits)")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 24)
