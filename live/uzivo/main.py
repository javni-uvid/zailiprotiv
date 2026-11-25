"""The web part: the page in both scripts, the changing part of it, the state as JSON, and the fonts."""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import threading
import time
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response

from . import config, deljenje, picture, pretplata, slusaj
from .obavesti import Bell
from .page import admin_page, fragment, listen_html, manifest, page, service_worker, transcript_page

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
APART = config.ROLE == "strana"  # the measuring is another process: its files are read, nothing of it is loaded here
if APART:
    from .citac import Reader
    tracker = Reader(config.STATE_PATH)
    slusaj.told = lambda: tracker.sada.get("zvuk") or {}
else:
    from . import merenje
    tracker = merenje.tracker()
_stop = threading.Event()
bell = Bell()
mailer = pretplata.Mailer(Path(config.STATE_PATH).parent / "mejl", pretplata.day_mail(tracker))
_tz = ZoneInfo(config.TZ)
FONTS = Path(__file__).parent / "static" / "fonts"
URL = os.environ.get("PUBLIC_URL", "").strip()  # the page's own address, for canonical links
NO_STORE = {"Cache-Control": "no-store"}


@asynccontextmanager
async def lifespan(_: FastAPI):
    if not APART:
        merenje.start(tracker, _stop, bell)
    pretplata.Watch(tracker, mailer, _stop).start()
    yield
    _stop.set()


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
# What says who speaks now. Without the measuring (no heartbeat, or its loop standing: citac.Reader.alive) none of it is
# served, as when the service is down: the edge then gives its last answer or the site's page, the counter's watch
# tells the maintainer, and an open page keeps what it shows. The days kept, the mail and the rest go on.
MOMENT = {"/", "/cir", "/cir/", "/deo", "/cir/deo", "/stanje.json", "/stanje.js", "/slika.png", "/cir/slika.png", "/prica.png",
          "/cir/prica.png"}
SPEECH = re.compile(r"/(cir/)?govor/")


@app.middleware("http")
async def only_while_measured(request: Request, call_next):
    if APART and (request.url.path in MOMENT or SPEECH.match(request.url.path)) and not await asyncio.to_thread(tracker.alive):
        return Response("Servis trenutno ne radi.", status_code=503, media_type="text/plain; charset=utf-8",
                        headers={**NO_STORE, "Retry-After": "30"})
    return await call_next(request)


@app.get("/zdravlje")
def health() -> JSONResponse:
    """That this process answers, and which commit it is (Docker's check of the page's container, and mikrofon.ps1's while
    the measuring is down): the measuring has a check of its own."""
    return JSONResponse({"ok": True, "verzija": config.VERSION}, headers=NO_STORE)


def _video() -> str:
    """The YouTube id of the broadcast being read."""
    if APART:
        return str(tracker.sada.get("video") or "")
    from .stream import VIDEO
    return VIDEO.get("id", "")


def _versions() -> dict:
    """The commit of the page, and of the measuring (another one when they were put live apart)."""
    return {"verzija": config.VERSION, "merenje": str(tracker.sada.get("verzija") or "") if APART else config.VERSION}


def _page(cyr: bool, speech: int | None = None) -> HTMLResponse:
    snap = tracker.snapshot()  # first: the rest is read with it
    return HTMLResponse(page(snap, cyr=cyr, site=config.SITE, tz=_tz, url=URL, waiting=tracker.waiting,
                             live=_video(), analytics=config.ANALYTICS_TOKEN, api=config.VOTES_API,
                             push_key=config.PUSH_KEY, version=config.VERSION, sample=bool(_sample_day()), speech=speech),
                        headers=NO_STORE)


def _sample_day():
    """The day whose mail is shown as a sample: the last one on the page, once its summary is shown to everyone."""
    from datetime import date
    if not config.SHOW_SUMMARY:
        return None
    day = str(tracker.snapshot().get("dan") or "")
    try:
        return date.fromisoformat(day) if isinstance((tracker.summary_of(day) or {}).get("dan"), dict) else None
    except ValueError:
        return None


def _sample(cyr: bool) -> Response:
    """The last day's mail as a page, so that a reader sees what they sign up for (23 Nov 2026): the same mail, made
    by the same code, with a line on top saying what it is; nobody's unsubscribe link in it."""
    day = _sample_day()
    html = pretplata.sample(mailer.build, day, cyr) if day else ""
    if not html:
        return RedirectResponse("/cir/#mejl" if cyr else "/#mejl", status_code=302, headers=NO_STORE)
    return HTMLResponse(html, headers={"Cache-Control": "public, max-age=300", "X-Robots-Tag": "noindex"})


@app.get("/mejl/primer")
def mail_sample() -> Response:
    return _sample(False)


@app.get("/cir/mejl/primer")
def cyrillic_mail_sample() -> Response:
    return _sample(True)


_parts: dict[bool, tuple[dict, str, str]] = {}  # per script: the snapshot, the part drawn from it, its mark


def _part(cyr: bool, request: Request) -> Response:
    """The changing part, drawn once per snapshot (every open page asks for it every few seconds), with a mark
    (ETag) so that a page holding the same part gets a 304 and nothing else (20 Nov 2026)."""
    snap = tracker.snapshot()
    kept = _parts.get(cyr)
    if kept and kept[0] is snap:
        html, tag = kept[1], kept[2]
    else:
        html = fragment(snap, cyr=cyr, site=config.SITE, tz=_tz)
        tag = '"' + hashlib.blake2s(html.encode(), digest_size=8).hexdigest() + '"'
        _parts[cyr] = (snap, html, tag)
    headers = {"Cache-Control": "no-cache", "ETag": tag}
    asked = [t.strip().removeprefix("W/") for t in request.headers.get("if-none-match", "").split(",")]
    if tag in asked:  # Cloudflare passes the mark on, made weak ("W/") when it compresses the answer
        return Response(status_code=304, headers=headers)
    # As text, not HTML: the page's script reads it as text, and Cloudflare drops the ETag of an HTML answer, which
    # it may rewrite (checked 20 Nov 2026: the mark reached the tunnel and not the browser).
    return Response(html, media_type="text/plain; charset=utf-8", headers=headers)


@app.get("/")
def latin_page() -> HTMLResponse:
    return _page(False)


@app.get("/cir/")
def cyrillic_page() -> HTMLResponse:
    return _page(True)


def _speech(cyr: bool, sek: str) -> Response:
    """A shared speech (deljenje.py): the page with it, while its day is on the page; else the site's own page of that
    day, when the site has one; else the page as it is."""
    at = deljenje.moment(sek)
    if at:
        if deljenje.turn_at(tracker.snapshot().get("danas") or [], at):
            return _page(cyr, at)
        to = deljenje.elsewhere(at, tracker.waiting, cyr=cyr, tz=_tz)
        if to:
            return RedirectResponse(to, status_code=302, headers=NO_STORE)
    return RedirectResponse("/cir/" if cyr else "/", status_code=302, headers=NO_STORE)


@app.get("/govor/{sek}")
def latin_speech(sek: str) -> Response:
    return _speech(False, sek)


@app.get("/cir/govor/{sek}")
def cyrillic_speech(sek: str) -> Response:
    return _speech(True, sek)


@app.get("/deo")
def latin_part(request: Request) -> Response:
    return _part(False, request)


@app.get("/cir/deo")
def cyrillic_part(request: Request) -> Response:
    return _part(True, request)


_pictures: dict[tuple[bool, bool], tuple[float, bytes]] = {}
PICTURE_KEEP = 20  # seconds a drawn picture serves everyone


def _picture(cyr: bool, tall: bool = False) -> Response:
    """The picture of the moment (picture.py): the link preview and the share of the day. Drawn at most once in
    twenty seconds per script, and kept as long by Cloudflare and the browser."""
    now = time.monotonic()
    kept = _pictures.get((cyr, tall))
    if not kept or now - kept[0] > PICTURE_KEEP:
        host = URL.split("//")[-1].strip("/")
        draw = picture.render_tall if tall else picture.render
        kept = (now, draw(tracker.snapshot(), cyr=cyr, tz=_tz, host=host))
        _pictures[(cyr, tall)] = kept
    return Response(kept[1], media_type="image/png", headers={"Cache-Control": f"public, max-age={PICTURE_KEEP}"})


@app.get("/slika.png")
def latin_picture() -> Response:
    return _picture(False)


@app.get("/cir/slika.png")
def cyrillic_picture() -> Response:
    return _picture(True)


_still: dict[bool, bytes] = {}


def _speech_picture(cyr: bool) -> Response:
    """The picture of a link to a speech: the still one (no speaker, no day), before a sitting too. Drawn once."""
    if cyr not in _still:
        _still[cyr] = picture.render({}, cyr=cyr, tz=_tz, host=URL.split("//")[-1].strip("/"))
    return Response(_still[cyr], media_type="image/png", headers=DAY)


@app.get("/govor.png")
def latin_speech_picture() -> Response:
    return _speech_picture(False)


@app.get("/cir/govor.png")
def cyrillic_speech_picture() -> Response:
    return _speech_picture(True)


@app.get("/prica.png")
def latin_story() -> Response:
    """The same moment upright, for a phone's story."""
    return _picture(False, tall=True)


@app.get("/cir/prica.png")
def cyrillic_story() -> Response:
    return _picture(True, tall=True)


_said: dict[bool, tuple[float, str]] = {}


def _transcript(cyr: bool, key: str = "") -> HTMLResponse:
    """The day's automatic transcript (prepis.py), put together at most once in twenty seconds per script. With the
    transcript off the page (config.SHOW_TRANSCRIPT) only for whoever has the key (config.TRANSCRIPT_KEY, as ?k=):
    anyone else is led back to the page, and the keyed answer is kept by nobody and sends no address on."""
    private = not config.SHOW_TRANSCRIPT
    if not config.transcript_open(key):
        return RedirectResponse("/cir/" if cyr else "/", status_code=302, headers=NO_STORE)
    now = time.monotonic()
    kept = _said.get(cyr)
    if not kept or now - kept[0] > PICTURE_KEEP:
        kept = (now, transcript_page(tracker.transcript(), cyr=cyr, site=config.SITE, tz=_tz, url=URL))
        _said[cyr] = kept
    if private:
        return HTMLResponse(kept[1], headers={"Cache-Control": "private, no-store", "Referrer-Policy": "no-referrer",
                                              "X-Robots-Tag": "noindex, nofollow"})
    return HTMLResponse(kept[1], headers={"Cache-Control": f"public, max-age={PICTURE_KEEP}"})


@app.get("/prepis")
def latin_transcript(k: str = "") -> HTMLResponse:
    return _transcript(False, k)


@app.get("/cir/prepis")
def cyrillic_transcript(k: str = "") -> HTMLResponse:
    return _transcript(True, k)


@app.get("/stanje.json")
def state() -> JSONResponse:
    return JSONResponse({**tracker.snapshot(), **_versions()}, headers=NO_STORE)


@app.get("/stanje.js")
def state_shared() -> JSONResponse:
    """The same state for other pages to read (18 Nov 2026: a joke page on a quick tunnel, whose 200 requests in
    flight its visitors filled): any origin may read it, and as a ".js" Cloudflare keeps it two seconds, so however
    many read it the computer answers once in two seconds per Cloudflare location."""
    return JSONResponse(tracker.snapshot(), headers={"Cache-Control": "public, max-age=2, s-maxage=2",
                                                     "Access-Control-Allow-Origin": "*"})


@app.get("/dani.json")
def days() -> JSONResponse:
    """The days this service has a record of, for the site's workflow that takes them in."""
    return JSONResponse({"dani": tracker.days_kept()}, headers=NO_STORE)


@app.get("/mejl/posalji")
def mail_ask(dan: str = "", k: str = "") -> HTMLResponse:
    """The maintainer's link in the day's mail: a page with one button (mail scanners open links; sending to all must
    be his click)."""
    return HTMLResponse(pretplata.page_ask(dan, k), headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer",
                                                           "X-Robots-Tag": "noindex, nofollow"})


@app.post("/mejl/posalji")
async def mail_send(request: Request) -> HTMLResponse:
    """The button: the day's mail to everyone confirmed, once, until noon the next day (pretplata.Mailer.to_all)."""
    from urllib.parse import parse_qs
    form = parse_qs((await request.body()).decode("utf-8", "replace")[:500])
    dan, k = (form.get("dan") or [""])[0], (form.get("k") or [""])[0]
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", dan):
        return HTMLResponse(pretplata.page_done("kod", 0), status_code=400)
    from datetime import date
    what, n = await asyncio.to_thread(mailer.to_all, date.fromisoformat(dan), k)
    return HTMLResponse(pretplata.page_done(what, n), headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow"})


@app.get("/sazetak")
def summary_keyed(k: str = "", dan: str = "") -> Response:
    """The model's summaries of a day as kept (sudija.py), for the maintainer while they are off the page: only with
    the transcript's key (?k=), kept by nobody and sending no address on; anyone else is led back to the page."""
    if not config.admin_open(k):
        return RedirectResponse("/", status_code=302, headers=NO_STORE)
    day = dan if re.fullmatch(r"\d{4}-\d{2}-\d{2}", dan) else tracker.snapshot()["dan"]
    return JSONResponse({"dan": day, **tracker.summary_of(day)}, headers={
        "Cache-Control": "private, no-store", "Referrer-Policy": "no-referrer", "X-Robots-Tag": "noindex, nofollow"})


@app.get("/sazetak/{day}.json")
def summary_of_day(day: str) -> JSONResponse:
    """A day's summaries for the site (uzivo-pull), once they are on the page (config.SHOW_SUMMARY)."""
    if not config.SHOW_SUMMARY or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
        raise HTTPException(404)
    kept = tracker.summary_of(day)
    if not kept:
        raise HTTPException(404)
    return JSONResponse({"dan": day, **{k: v for k, v in kept.items() if k != "vidjeno"}}, headers=NO_STORE)


@app.get("/dan/{day}.json")
def day(day: str) -> JSONResponse:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
        raise HTTPException(404)
    rec = tracker.record(day)
    if rec is None:
        raise HTTPException(404)
    return JSONResponse(rec, headers=NO_STORE)


ICON_SIZES = {"ikona-180": (180, False), "ikona-192": (192, False), "ikona-512": (512, False),
              "ikona-maskable-512": (512, True)}
_icons: dict[str, bytes] = {}
DAY = {"Cache-Control": "public, max-age=86400"}


@app.get("/manifest.webmanifest")
def latin_manifest() -> JSONResponse:
    return JSONResponse(manifest(False), media_type="application/manifest+json", headers=DAY)


@app.get("/cir/manifest.webmanifest")
def cyrillic_manifest() -> JSONResponse:
    return JSONResponse(manifest(True), media_type="application/manifest+json", headers=DAY)


@app.get("/slusaj/{k}/")
def listen_page(k: str) -> Response:
    """Listening live, sound only (slusaj.py): the maintainer's trial, behind the key."""
    if not config.admin_open(k):
        raise HTTPException(404)
    return HTMLResponse(listen_html(), headers={"Cache-Control": "private, no-store", "Referrer-Policy": "no-referrer",
                                                "X-Robots-Tag": "noindex, nofollow"})


@app.get("/slusaj/{k}/z.m3u8")
def listen_playlist(k: str) -> Response:
    if not config.admin_open(k):
        raise HTTPException(404)
    text = slusaj.playlist()
    if not text:
        raise HTTPException(404)
    return Response(text, media_type="application/vnd.apple.mpegurl", headers={"Cache-Control": "no-store"})


@app.get("/slusaj/{k}/{name}")
def listen_segment(k: str, name: str) -> Response:
    if not config.admin_open(k):
        raise HTTPException(404)
    f = slusaj.PLAYLIST.segment(name)
    if not f:
        raise HTTPException(404)
    return FileResponse(f, media_type="video/mp2t", headers={"Cache-Control": "private, max-age=120"})


@app.get("/slusaj/{name}")
def listen_public(name: str) -> Response:
    """The playlist and its segments for all, once listening is open (SLUSAJ_JAVNO)."""
    if not config.LISTEN_PUBLIC:
        raise HTTPException(404)
    if name == "z.m3u8":
        text = slusaj.playlist()
        if not text:
            raise HTTPException(404)
        return Response(text, media_type="application/vnd.apple.mpegurl", headers={"Cache-Control": "no-cache, max-age=2"})
    f = slusaj.PLAYLIST.segment(name)
    if not f:
        raise HTTPException(404)
    return FileResponse(f, media_type="video/mp2t", headers={"Cache-Control": "public, max-age=300, immutable"})


@app.get("/upozorenja")
def alerts_page(k: str = "") -> Response:
    """The maintainer's page for the outage alerts (page.admin_page); anyone without the key is led to the page."""
    if not config.admin_open(k):
        return RedirectResponse("/", status_code=302, headers=NO_STORE)
    return HTMLResponse(admin_page(config.TRANSCRIPT_KEY, config.PUSH_KEY), headers={"Cache-Control": "private, no-store",
                        "Referrer-Policy": "no-referrer", "X-Robots-Tag": "noindex, nofollow"})


@app.post("/upozorenja")
async def alerts_device(request: Request, k: str = "") -> JSONResponse:
    """This device on (or off) the outage alerts: handed to the counter with the service's token."""
    if not config.admin_open(k):
        raise HTTPException(403)
    try:
        body = await request.json()
    except ValueError:
        raise HTTPException(400)
    endpoint = body.get("endpoint") if isinstance(body, dict) else None
    if not isinstance(endpoint, str) or not endpoint.startswith("https://") or len(endpoint) > 1000:
        raise HTTPException(400)
    ok = await asyncio.to_thread(bell.admin, endpoint, body.get("on", True) is not False)
    if not ok:
        raise HTTPException(502)
    return JSONResponse({"ok": True}, headers=NO_STORE)


@app.get("/sw.js")
def sw(j: str = "") -> Response:
    """The page's service worker, for the notifications (page.service_worker); never kept, so a change reaches
    every browser at its next visit."""
    return Response(service_worker(j == "cir", config.PUSH_KEY, config.VOTES_API), media_type="text/javascript",
                    headers={"Cache-Control": "no-cache"})


@app.get("/{name}.png")
def home_icon(name: str) -> Response:
    """The icons for a phone's home screen (picture.icon), drawn once."""
    if name not in ICON_SIZES:
        raise HTTPException(404)
    if name not in _icons:
        _icons[name] = picture.icon(*ICON_SIZES[name])
    return Response(_icons[name], media_type="image/png", headers=DAY)


@lru_cache(maxsize=1)
def _fonts() -> dict[str, Path]:
    return {p.name: p for p in FONTS.iterdir() if p.is_file()} if FONTS.is_dir() else {}


@app.get("/caslav.webp")
def caslav() -> FileResponse:
    """The cat in a heart beside "Podrži" (23 Nov 2026), served by the page itself."""
    return FileResponse(Path(__file__).parent / "static" / "caslav.webp", media_type="image/webp",
                        headers={"Cache-Control": "public, max-age=604800"})


@app.get("/fonts/{name}")
def font(name: str) -> FileResponse:
    path = _fonts().get(name)  # one of the folder's own files: no path is built from what was asked
    if not path:
        raise HTTPException(404)
    return FileResponse(path, headers={"Cache-Control": "public, max-age=31536000, immutable"})
