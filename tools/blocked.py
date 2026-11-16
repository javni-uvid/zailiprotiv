"""What Cloudflare stopped on the way to the site: its security events, summed, and how search engines' crawlers fared.

Asked by the `visits` workflow (blocked=true), with the account's token (it needs Zone → Analytics: Read and
Zone: Read). Only sums are printed, by action, by what acted (a rule, Bot Fight Mode, …) and by host; for the
crawlers of search engines also the path, as a page's address is not about a person. No address, no single visitor.
Also: what the zone answers to Google's crawler (its status codes), from the zone's own request counts."""
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

API = "https://api.cloudflare.com/client/v4"
LEAST = 3
CRAWLERS = ("Googlebot", "bingbot", "Google-InspectionTool", "GoogleOther", "AdsBot-Google", "Storebot-Google")


def call(path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(API + path, data=json.dumps(body).encode() if body else None,
                                 headers={"Authorization": f"Bearer {os.environ['CLOUDFLARE_API_TOKEN']}",
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return {"errors": [{"message": f"{e.code} {e.read()[:300]!r}"}]}


def graph(query: str, variables: dict) -> list:
    got = call("/graphql", {"query": query, "variables": variables})
    if got.get("errors"):
        print("  Cloudflare:", "; ".join(e.get("message", "?") for e in got["errors"])[:600])
        return []
    return got["data"]["viewer"]["zones"][0]["rows"]


def main(hours: int):
    zones = call("/zones?name=zailiprotiv.rs")
    if not zones.get("result"):
        print("The zone could not be read (the token needs Zone: Read):", zones.get("errors"))
        return
    zone = zones["result"][0]["id"]
    until = datetime.now(timezone.utc)
    since = until - timedelta(hours=min(hours, 24))  # the adaptive groups keep a day at most on the free plan
    v = {"zone": zone, "since": since.strftime("%Y-%m-%dT%H:%M:%SZ"), "until": until.strftime("%Y-%m-%dT%H:%M:%SZ")}
    print(f"Security events, {v['since']} to {v['until']} (rows under {LEAST} left out)")

    def events(dims: str, extra: str = "", limit: int = 30) -> list:
        q = """query($zone: String!, $since: Time!, $until: Time!) { viewer { zones(filter: {zoneTag: $zone}) {
          rows: firewallEventsAdaptiveGroups(limit: %d, orderBy: [count_DESC],
            filter: {datetime_geq: $since, datetime_leq: $until%s}) { count dimensions { %s } } } } }""" % (limit, extra, dims)
        return graph(q, v)

    print("\nAll events: action, what acted, host")
    for r in events("action source clientRequestHTTPHost"):
        d = r["dimensions"]
        if r["count"] >= LEAST:
            print(f"  {r['count']:>6}  {d['action']:<18} {d['source']:<22} {d['clientRequestHTTPHost']}")
    for bot in CRAWLERS:
        rows = events("action source ruleId clientRequestHTTPHost clientRequestPath", f', userAgent_like: "%{bot}%"', 20)
        if rows:
            print(f"\n{bot}: action, what acted, rule, host, path")
            for r in rows:
                d = r["dimensions"]
                print(f"  {r['count']:>6}  {d['action']:<18} {d['source']:<22} {d['ruleId'] or '-':<12} {d['clientRequestHTTPHost']}{d['clientRequestPath']}")
    print("\nWhat Google's crawlers got from the zone (status codes; a challenge or a block is 403)")
    q = """query($zone: String!, $since: Time!, $until: Time!) { viewer { zones(filter: {zoneTag: $zone}) {
      rows: httpRequestsAdaptiveGroups(limit: 30, orderBy: [count_DESC],
        filter: {datetime_geq: $since, datetime_leq: $until, userAgent_like: "%Google%"}) {
        count dimensions { edgeResponseStatus clientRequestHTTPHost } } } } }"""
    for r in graph(q, v):
        d = r["dimensions"]
        print(f"  {r['count']:>6}  {d['edgeResponseStatus']}  {d['clientRequestHTTPHost']}")
    print("\nThe 403s Google's crawlers got: hour, host, path, what acted, the crawler")
    for dims in ("datetimeHour clientRequestHTTPHost clientRequestPath securityAction securitySource userAgent",
                 "datetimeHour clientRequestHTTPHost clientRequestPath userAgent"):  # the security fields, where the plan has them
        q = """query($zone: String!, $since: Time!, $until: Time!) { viewer { zones(filter: {zoneTag: $zone}) {
          rows: httpRequestsAdaptiveGroups(limit: 40, orderBy: [datetimeHour_ASC],
            filter: {datetime_geq: $since, datetime_leq: $until, userAgent_like: "%%Google%%", edgeResponseStatus: 403}) {
            count dimensions { %s } } } } }""" % dims
        rows = graph(q, v)
        if rows:
            for r in rows:
                d = r["dimensions"]
                bot = next((b for b in CRAWLERS if b in d["userAgent"]), d["userAgent"][:40])
                print(f"  {r['count']:>4}  {d['datetimeHour'][5:16]}  {d['clientRequestHTTPHost']}{d['clientRequestPath']}"
                      f"  {d.get('securityAction', '')} {d.get('securitySource', '')}  {bot}")
            break
    print("\nThe zone's settings that stop bots")
    for path in ("/settings/security_level", "/settings/browser_check", "/bot_management"):
        got = call(f"/zones/{zone}{path}")
        res = got.get("result")
        if isinstance(res, dict):
            res = {k: res[k] for k in res if k in ("value", "fight_mode", "ai_bots_protection", "sbfm_definitely_automated",
                                                   "sbfm_likely_automated", "sbfm_verified_bots", "crawler_protection",
                                                   "enable_js", "is_robots_txt_managed")}
        print(f"  {path}: {res if res is not None else got.get('errors')}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 24)
