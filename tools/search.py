"""What Google Search showed of the site: the searches it came up for, its pages, clicks and positions.

Asked of the Search Console API by the `visits` workflow (search=true), with a Google service account's key in the
repository secret GSC_KEY (the account added as a user of the Search Console property, "Restricted" is enough).
Only sums; a search seen fewer than three times is left out, as the run's log is public. Search Console's numbers
come two to three days late.

    python3 tools/search.py DAYS"""
import json
import os
import sys
from datetime import date, timedelta

PROPERTY = "sc-domain:zailiprotiv.rs"  # the Domain property: the site, the notes and the downloads together
LEAST = 3


def main(days: int):
    key = os.environ.get("GSC_KEY", "").strip()
    if not key:
        print("Search Console: no key (repository secret GSC_KEY); see tools/search.py.")
        return
    from google.oauth2 import service_account
    from google.auth.transport.requests import AuthorizedSession
    creds = service_account.Credentials.from_service_account_info(
        json.loads(key), scopes=["https://www.googleapis.com/auth/webmasters.readonly"])
    http = AuthorizedSession(creds)
    end = date.today() - timedelta(days=2)
    start = end - timedelta(days=days - 1)
    url = f"https://searchconsole.googleapis.com/webmasters/v3/sites/{PROPERTY.replace(':', '%3A')}/searchAnalytics/query"

    def ask(dims: list[str], limit: int = 50, kind: str = "web") -> list[dict]:
        r = http.post(url, json={"startDate": start.isoformat(), "endDate": end.isoformat(), "dimensions": dims,
                                 "rowLimit": limit, "type": kind})
        if r.status_code != 200:
            print(f"  Search Console answered {r.status_code}: {r.text[:300]}")
            return []
        return r.json().get("rows", [])

    print(f"Google Search, {start} to {end} (searches seen fewer than {LEAST} times left out)")
    total = ask([], 1)
    if total:
        t = total[0]
        print(f"  {t['impressions']:.0f} times shown, {t['clicks']:.0f} clicks, average position {t['position']:.1f}")
    for title, dims, limit in (("Searches", ["query"], 60), ("Pages", ["page"], 40), ("Devices", ["device"], 5),
                               ("Countries", ["country"], 10), ("By day", ["date"], days + 1)):
        rows = ask(dims, limit)
        print(f"\n{title}  (shown / clicks / position)")
        for r in sorted(rows, key=lambda r: r["keys"][0]) if dims == ["date"] else rows:
            if r["impressions"] >= LEAST or dims == ["date"]:
                print(f"  {r['impressions']:>6.0f} {r['clicks']:>5.0f} {r['position']:>6.1f}  {r['keys'][0]}")
    rows = ask(["page"], 20, "image")
    if rows:
        print("\nGoogle Images: pages  (shown / clicks / position)")
        for r in rows:
            if r["impressions"] >= LEAST:
                print(f"  {r['impressions']:>6.0f} {r['clicks']:>5.0f} {r['position']:>6.1f}  {r['keys'][0]}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 28)
