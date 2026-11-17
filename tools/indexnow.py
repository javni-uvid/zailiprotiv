"""Tell search engines which pages changed: the date in the sitemap (<lastmod>), and IndexNow (Bing, Yandex, Seznam,
Naver; Google does not take part).

    python3 tools/indexnow.py list _site .cache/indexnow.json changed.txt [--all]   (the build: pages whose text changed)
    python3 tools/indexnow.py send changed.txt                               (after publishing: tell them)

A page counts as changed when the text of its <main> changed since the last build that was told, so the footer's
dates and the styles' version don't make every page new. The first run lists every page. The key is in
data/settings.json and at https://zailiprotiv.rs/<key>.txt (it is public by design: it only shows the site is ours)."""
import hashlib
import json
import re
import sys
import urllib.request
from pathlib import Path

HOST = "zailiprotiv.rs"
MAIN = re.compile(r"<main\b.*?</main>", re.S)
# The pictures of a page, for Google Images (image sitemap): its own share picture and an MP's portrait. The site's
# general picture, on most pages, is left out.
OG = re.compile(r'<meta property="og:image" content="([^"]+)"')
PORTRAIT = re.compile(r'<img class="mp-photo" src="([^"]+)"')
VERSION = re.compile(r"\?v=[0-9a-f]+")


IMAGES: dict[str, list[str]] = {}  # address → its pictures, filled by pages()


def pages(site: Path) -> dict[str, str]:
    """Every page in the sitemap, by its address, with a hash of its main text."""
    from urllib.parse import urljoin
    out = {}
    for url in re.findall(r"<loc>([^<]+)</loc>", (site / "sitemap.xml").read_text(encoding="utf-8")):
        path = url.split(HOST + "/", 1)[1]
        f = site / (path + "index.html" if path == "" or path.endswith("/") else path if path.endswith(".html") else path + ".html")
        if f.exists():
            text = f.read_text(encoding="utf-8")
            m = MAIN.search(text)
            out[url] = hashlib.sha256(VERSION.sub("", m.group(0) if m else text).encode()).hexdigest()[:16]
            pics = [x for x in OG.findall(text) if not x.endswith("/za-ili-protiv.png")]
            pics += [urljoin(url, x) for x in PORTRAIT.findall(text)]
            if pics:
                IMAGES[url] = pics
    return out


def main():
    if sys.argv[1] == "list":
        site, store, listing = Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
        old = json.loads(store.read_text(encoding="utf-8")) if store.exists() else {}
        old = {u: v if isinstance(v, list) else [v, None] for u, v in old.items()}  # {address: [hash, day it changed]}
        now = pages(site)
        today = __import__("datetime").date.today().isoformat()
        changed = [u for u, h in now.items() if old.get(u, [None])[0] != h or "--all" in sys.argv]
        fresh = {u for u, h in now.items() if old.get(u, [None])[0] != h}  # the day only moves when the text did
        kept = {u: [h, today if u in fresh or not old.get(u, [0, 0])[1] else old[u][1]] for u, h in now.items()}
        # The sitemap says when each page last changed (Google and Bing use it when it is right).
        sm = site / "sitemap.xml"
        def entry(m):
            u = m.group(1)
            if u not in kept:
                return m.group(0)
            pics = "".join(f"<image:image><image:loc>{x}</image:loc></image:image>" for x in IMAGES.get(u, []))
            return f"<url><loc>{u}</loc><lastmod>{kept[u][1]}</lastmod>{pics}</url>"
        text = re.sub(r"<url><loc>([^<]+)</loc></url>", entry, sm.read_text(encoding="utf-8"))
        text = text.replace('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
                            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
                            'xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">', 1)
        sm.write_text(text, encoding="utf-8")
        listing.write_text("\n".join(changed) + ("\n" if changed else ""), encoding="utf-8")
        store.parent.mkdir(parents=True, exist_ok=True)
        store.write_text(json.dumps(kept, separators=(",", ":")), encoding="utf-8")
        print(f"indexnow: {len(now)} pages, {len(changed)} changed since the last build")
        return
    urls = [u for u in Path(sys.argv[2]).read_text(encoding="utf-8").split("\n") if u]
    key = json.loads(Path("data/settings.json").read_text(encoding="utf-8")).get("indexnow_key")
    if not urls or not key:
        print("indexnow: nothing to tell" if urls else "indexnow: no page changed")
        return
    for i in range(0, len(urls), 10000):  # at most 10,000 addresses to a request
        body = {"host": HOST, "key": key, "keyLocation": f"https://{HOST}/{key}.txt", "urlList": urls[i:i + 10000]}
        req = urllib.request.Request("https://api.indexnow.org/indexnow", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json; charset=utf-8"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                print(f"indexnow: {len(body['urlList'])} addresses sent, answer {r.status}")
        except urllib.error.HTTPError as e:
            print(f"indexnow: answer {e.code} {e.read()[:200]!r}")


if __name__ == "__main__":
    main()
