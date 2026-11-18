"""The web part: the page in both scripts, the changing part of it, the state as JSON, and the fonts."""
from __future__ import annotations

import logging
import os
import re
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from . import config, worker
from .stream import VIDEO
from .page import fragment, page
from .state import Tracker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
tracker = Tracker(config.STATE_PATH)
_stop = threading.Event()
_tz = ZoneInfo(config.TZ)
FONTS = Path(__file__).parent / "static" / "fonts"
URL = os.environ.get("PUBLIC_URL", "").strip()  # the page's own address, for canonical links
NO_STORE = {"Cache-Control": "no-store"}


@asynccontextmanager
async def lifespan(_: FastAPI):
    threading.Thread(target=worker.run, args=(tracker, _stop), daemon=True).start()
    yield
    _stop.set()


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


def _page(cyr: bool) -> HTMLResponse:
    return HTMLResponse(page(tracker.snapshot(), cyr=cyr, site=config.SITE, tz=_tz, url=URL, waiting=tracker.waiting,
                             live=VIDEO.get("id", "")), headers=NO_STORE)


def _part(cyr: bool) -> HTMLResponse:
    return HTMLResponse(fragment(tracker.snapshot(), cyr=cyr, site=config.SITE, tz=_tz), headers=NO_STORE)


@app.get("/")
def latin_page() -> HTMLResponse:
    return _page(False)


@app.get("/cir/")
def cyrillic_page() -> HTMLResponse:
    return _page(True)


@app.get("/deo")
def latin_part() -> HTMLResponse:
    return _part(False)


@app.get("/cir/deo")
def cyrillic_part() -> HTMLResponse:
    return _part(True)


@app.get("/stanje.json")
def state() -> JSONResponse:
    return JSONResponse(tracker.snapshot(), headers=NO_STORE)


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


@app.get("/dan/{day}.json")
def day(day: str) -> JSONResponse:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
        raise HTTPException(404)
    rec = tracker.record(day)
    if rec is None:
        raise HTTPException(404)
    return JSONResponse(rec, headers=NO_STORE)


@app.get("/fonts/{name}")
def font(name: str) -> FileResponse:
    path = FONTS / name
    if path.parent != FONTS or not path.is_file():
        raise HTTPException(404)
    return FileResponse(path, headers={"Cache-Control": "public, max-age=31536000, immutable"})
