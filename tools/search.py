"""What Google Search showed of the site: the searches it came up for, its pages, clicks and positions.

Asked of the Search Console API by the `visits` workflow (search=true), with a Google service account's key in the
repository secret GSC_KEY (the account added as a user of the Search Console property, "Restricted" is enough).
Only sums; a search seen fewer than three times is left out, as the run's log is public. Search Console's numbers
come two to three days late.

With --inspect N, also whether Google took the site's pages into its index: N addresses of each kind of page
(a law, an MP, an MP's votes, …) in each script, spread evenly over the sitemap, asked of the URL Inspection API
(2,000 a day per property). What Google says of each kind is summed; the pages are the site's own, public anyway.

    python3 tools/search.py DAYS [--inspect N]"""
import json
import os
import re
import sys
import urllib.request
from collections import Counter
from datetime import date, timedelta

PROPERTY = "sc-domain:zailiprotiv.rs"  # the Domain property: the site, the notes and the downloads together
SITE = "https://zailiprotiv.rs/"
LEAST = 3


def session():
    """An authorised session for the Search Console API, or None (and why) when the key is missing or not one."""
    key = os.environ.get("GSC_KEY", "").strip()
    if not key:
        print("Search Console: no key (repository secret GSC_KEY); see tools/search.py.")
        return None
    try:
        info = json.loads(key)
    except ValueError:
        print("Search Console: GSC_KEY is not a JSON key; set it to the whole service account key file "
              "(gh secret set GSC_KEY < key.json).")
        return None
    from google.oauth2 import service_account
    from google.auth.transport.requests import AuthorizedSession
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/webmasters.readonly"])
    return AuthorizedSession(creds)


def kind(address: str) -> str:
    """The kind of page an address of the site is, and its script: "zakon", "poslanik glasovi", "cir spiskovi"…"""
    path = address[len(SITE):]
    script = "cir " if path.startswith("cir/") else ""
    path = path.removeprefix("cir/")
    if "/" not in path:
        return script + ("spiskovi" if re.search(r"-(\d+|s\d+)$", path) else "glavne")
    folder, name = path.split("/", 1)
    end = re.search(r"-(glasovi|govori)$", name)
    return script + folder + (" " + end.group(1) if end else "")


def sample(addresses: list[str], n: int) -> dict[str, list[str]]:
    """N addresses of each kind, spread evenly over its list (the same ones each time, while the sitemap is)."""
    by_kind: dict[str, list[str]] = {}
    for a in sorted(addresses):
        by_kind.setdefault(kind(a), []).append(a)
    return {k: [v[i * len(v) // n] for i in range(n)] if len(v) > n else v for k, v in sorted(by_kind.items())}


def inspect(http, n: int) -> None:
    """Whether Google indexed a sample of each kind of page, and the canonical address it chose for it."""
    with urllib.request.urlopen(urllib.request.Request(SITE + "sitemap.xml", headers={"User-Agent": "zailiprotiv"})) as r:
        addresses = re.findall(r"<loc>([^<]+)</loc>", r.read().decode("utf-8"))
    addresses = [a for a in addresses if a.startswith(SITE) and not a.endswith(".png")]
    picked = sample(addresses, n)
    print(f"\nIndexed? {sum(map(len, picked.values()))} of the sitemap's {len(addresses)} pages, up to {n} of each kind "
          "(URL Inspection; the state as Google last saw it)")
    url = "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect"

    def ask(page: str):
        """Google's answer for one address; None when it gave none twice (it once kept a request two minutes)."""
        import requests
        for _ in range(2):
            try:
                return http.post(url, json={"inspectionUrl": page, "siteUrl": PROPERTY}, timeout=60)
            except requests.RequestException as e:
                print(f"    {page}: {type(e).__name__}", flush=True)
        return None

    for k, pages in picked.items():
        states, other_canonical, never = Counter(), [], 0
        for page in pages:
            r = ask(page)
            if r is None:
                states["(no answer)"] += 1
                continue
            if r.status_code != 200:
                print(f"  Search Console answered {r.status_code}: {r.text[:300]}")
                return
            s = r.json().get("inspectionResult", {}).get("indexStatusResult", {})
            states[s.get("coverageState", "?")] += 1
            never += not s.get("lastCrawlTime")
            if s.get("googleCanonical") and s.get("googleCanonical") != page:
                other_canonical.append(f"{page} → {s['googleCanonical']}")
        print(f"\n  {k}  ({len(pages)} asked; never crawled: {never})", flush=True)
        for state, c in states.most_common():
            print(f"    {c:>3}  {state}")
        for line in other_canonical[:3]:
            print(f"    Google's canonical is another page: {line}")


def main(days: int, n_inspect: int = 0):
    http = session()
    if http is None:
        return
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
    if n_inspect:
        inspect(http, n_inspect)


if __name__ == "__main__":
    args = sys.argv[1:]
    n = int(args[args.index("--inspect") + 1]) if "--inspect" in args else 0
    days = [a for i, a in enumerate(args) if a != "--inspect" and (i == 0 or args[i - 1] != "--inspect")]
    main(int(days[0]) if days else 28, n)
