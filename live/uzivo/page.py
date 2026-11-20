"""The page, in Latin and in Cyrillic, from the tracker's snapshot. Only the standard library: the repository's tests
render it. The page loads nothing from elsewhere: the fonts are served with it, the one script is inline."""
from __future__ import annotations

import json
import time
from datetime import datetime
from html import escape
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

from . import config
from .names import cyrillic, given_first

LIVE = "https://www.parlament.gov.rs/prenosi/sednice-narodne-skupstine.2083.html"

TEXT = {
    "title": "Ko sada govori u Skupštini",
    "lead": "Govornik u Narodnoj skupštini u ovom trenutku, pročitan iz potpisa u prenosu uživo.",
    "intro": "Ko upravo govori u Narodnoj skupštini i koliko dugo, čitano uživo iz potpisa u prenosu. Deo sajta",
    "intro_end": ": nezavisan, besplatan pregled svakog zakona i glasanja svakog poslanika.",
    "hero_sub": "Uživo iz prenosa: ko je za govornicom, koliko dugo i šta govori.",
    "hero_cta": "Kako glasa svaki poslanik",
    "speaks": "govori",
    "longer": "duže od {p}% današnjih govora",
    "longest": "najduži govor danas",
    "d_today": "Danas",
    "d_conv": "saziv",
    "d_turn": "{n}. put za govornicom",
    "d_total": "ukupno {t}",
    "d_rank": "{m}. po vremenu od {n} govornika",
    "d_conv_line": "{t} u {n} {w}",
    "next_fact": "Sledeća činjenica",
    "share_now": "Podeli ovaj trenutak",
    "sh_head": "Sada govori u Skupštini",
    "sh_already": "govori već",
    "sh_today": "danas ukupno {t} · {n}. put za govornicom",
    "sh_first": "prvi put danas za govornicom",
    "sh_note": "Čitano iz potpisa u prenosu, automatski; može da pogreši.",
    "sh_text": "%1 govori već %2 min u Skupštini (%3). Uživo:",  # filled by the script; digits survive Cyrillic
    "sh_done": "Slika je sačuvana, a tekst kopiran.",
    "h_most": "Najviše vremena za govornicom %1: %2, %3",
    "h_today": "danas",
    "h_share": "%1% vremena svih govornika",
    "h_more": "više nego svi govornici liste „%1“ zajedno (%2)",
    "n_time": "vreme govora",
    "n_turns": "govora",
    "n_people": "govornika",
    "n_words": "reči u prepisu",
    "said_now": "Šta govori · automatski prepis, kasni oko minut, može da pogreši",
    "said_all": "Ceo prepis dana",
    "said_link": "prepis",
    "said_title": "Automatski prepis dana",
    "said_lead": "Šta je ko rekao za govornicom, zapisano automatski (Whisper) sa zvuka prenosa, komad po komad dok "
                 "govor traje. Prepis greši u imenima, brojevima i na mestima gde se govornici smenjuju, pa nije "
                 "citat: za citat služe stenografske beleške Skupštine, koje sajt objavljuje kad stignu. Ništa nije "
                 "prepričano ni skraćeno.",
    "said_none": "Za ovaj dan još nema prepisa.",
    "said_unsigned": "Bez potpisa: predsedavajući ili sala · automatski prepis, može da pogreši",
    "said_nobody": "Bez potpisa: predsedavajući ili sala",
    "said_report": "Prijavi grešku u prepisu",
    "said_second": "drugo, tačnije čitanje",
    "said_fix": "Prepis prvo objavimo, pa ispravljamo: poznate greške u pravopisu i imenima popravljamo po spisku, a "
                "grešku koju vidite možete da nam javite uz svaki govor. Ispravljamo kako je napisano, nikad šta je rečeno.",
    "said_back": "Nazad na „Ko sada govori“",
    "st_open": "Dan u karticama",
    "st_total": "ukupno vreme za govornicom",
    "st_most": "Najviše vremena za govornicom",
    "st_longest": "Najduži govor bez prekida",
    "st_often": "Najviše puta za govornicom",
    "st_times": "puta",
    "st_end": "Ko su ljudi koji govore i kako glasaju?",
    "st_site": "Svaki zakon i svaki glas",
    "st_close": "Zatvori",
    "st_hint": "Dodir desno: dalje · levo: nazad",
    "so_far": "Dosad danas",
    "paused": "Sada niko nije za govornicom ili se ime ne vidi u potpisu.",
    "share_day": "Podeli presek dana",
    "share_tall": "Uspravna slika za priču",
    "ag": "Dnevni red",
    "ag_done": "%1 od %2 tačaka gotovo",
    "ag_now": "u toku",
    "ag_next": "na redu",
    "ag_gotova": "gotova",
    "ag_site": "po sajtu Skupštine",
    "ag_said": "po rečima predsedavajućeg (automatski prepis)",
    "ag_note": "Dnevni red je sa sajta Skupštine. Tačka je gotova kad to napiše Skupština na stranici sednice ili kad "
               "predsedavajući pređe na sledeću; ovo drugo čitamo iz automatskog prepisa i može da pogreši.",
    "steps": "Šta se desilo danas",
    "steps_then": "Šta se desilo",
    "steps_lead": "Koraci sednice redom, najnoviji prvi.",
    "steps_said": "po rečima predsedavajućeg, prepoznato automatski sa zvuka prenosa i provereno uz dnevni red i sliku prenosa; i dalje može da pogreši",
    "steps_site": "sajt Skupštine",
    "steps_site_key": "zvanično: napisala Skupština na stranici sednice; vreme je vreme objave, ne događaja",
    "steps_official": "Zvanično",
    "steps_pub": "objava",
    "steps_published": "objavljeno oko %1, događaj je bio ranije",
    "steps_more": "Svi koraci",
    "news": "Novo:",
    "news_page": "stranica poslanika",
    "coming": "Sledeća sednica",
    "at": "u",
    "nx_in": "počinje za",
    "nx_soon": "Počinje uskoro",
    "nx_today": "Danas",
    "nx_tomorrow": "Sutra",
    "nx_day1": "dan",
    "nx_days": "dana",
    "nx_agenda": "Dnevni red",
    "nx_note": "Prenos će biti ovde čim sednica počne, a stranica se sama osvežava.",
    "add_home": "Dodaj na početni ekran",
    "add_sub": "Sledeći put do prenosa jednim dodirom.",
    "add_ios": "Na iPhoneu: dodirnite „Podeli“, pa „Dodaj na početni ekran“. Otvorena odatle, stranica može i da vas "
               "obavesti kad sednica počne.",
    "nt_on": "Obavesti me kad sednica počne",
    "nt_done": "Obaveštenje stiže kad prenos sednice počne.",
    "nt_off": "Isključi",
    "nt_blocked": "Obaveštenja za ovu stranicu su isključena u podešavanjima pregledača.",
    "nt_err": "Uključivanje nije uspelo; pokušajte ponovo malo kasnije.",
    "nt_note": "Jedno obaveštenje kad prenos sednice počne, najviše jednom dnevno. Šalje ga vaš pregledač preko "
               "svog servisa (Gugl, Epl ili Mozila); kod nas ostaje samo adresa za to obaveštenje, dok ga ne isključite.",
    "al_down": "Mikrofon ne radi",
    "al_down_body": "Sednica je u toku, a mikrofon.zailiprotiv.rs ne odgovara već %1 min.",
    "al_back": "Mikrofon ponovo radi",
    "al_back_body": "Nije odgovarao %1 min.",
    "nt_title": "Sednica je počela",
    "nt_body": "Prenos uživo i ko sada govori u Skupštini.",
    "app_name": "Mikrofon",
    "version": "Verzija",
    "sd_text": "Ko je koliko govorio u Skupštini:",
    "og_now": "Sada govori: %1",
    "og_since": "za govornicom od %1",
    "lists": "Vreme za govornicom po listama",
    "no_list": "Vlada i gosti",
    "other_lists": "poslanici manjih lista i van grupa",
    "timeline": "Tok dana",
    "timeline_note": "Svaki blok je jedan govor; klik vodi na njega u spisku ispod.",
    "since": "govori od",
    "min": "min",
    "unknown": "Prenos je u toku, ali se ime govornika sada ne vidi u potpisu.",
    "none": "Skupština sada ne zaseda ili prenos nije dostupan.",
    "not_listed": "ime iz potpisa; nije na spisku poslanika ovog sajta",
    "today": "Danas su govorili",
    "today_none": "Danas još niko nije prepoznat u prenosu.",
    "last_day": "Poslednji dan sednice",
    "from_recording": "Pročitano posle sednice sa celog snimka prenosa, istim pravilom za svakog govornika: govor "
                      "traje od prvog do poslednjeg kadra s imenom. Predsedavajući nema potpis i nije u spisku.",
    "recording": "snimak",
    "recording_title": "Na snimku prenosa, od mesta gde je govor počeo",
    "checked": "provereno pre",
    "s": "s",
    "how_title": "Kako ovo radi",
    "how": "Ime čitamo automatski iz potpisa ispod govornika u prenosu Skupštine, s jednim kadrom na oko pet "
           "sekundi, isto za svakog govornika. Ime poredimo sa spiskom poslanika ovog sajta; ime kog na spisku "
           "nema prikazujemo samo kad je jasno pročitano. Govor traje dok se u potpisu vidi isto ime, a završava "
           "se kad se pojavi drugo ime ili kad se 25 sekundi ne vidi nijedno. Prenos kasni za salom 15 do 25 "
           "sekundi, a automatsko čitanje može da pogreši. Mesto na snimku je mesto gde se ime prvi put pojavilo, "
           "oko pet sekundi ranije. Spisak poslednjeg dana sednice ostaje dok sledeće zasedanje ne počne.",
    "play_live": "Pusti prenos uživo",
    "play_day": "Pusti snimak dana",
    "part": "Deo",
    "yt_note": "Klik učitava plejer sa Jutjuba (Gugl). Dok ne kliknete, sa Jutjuba se ništa ne učitava.",
    "yt_live_note": "Prenos Skupštine sa Jutjuba (Gugl) učitava se tek kad ga pustite, u režimu bez kolačića.",
    "play_live": "Gledaj prenos",
    "archive_note": "Snimak iz arhive Skupštine (Videonet), pušta se tek na klik. Klik na „▶ snimak“ kod "
                    "govora pušta ga od tog mesta.",
    "counted": "Bez kolačića; posete se samo broje (Cloudflare Web Analytics, bez praćenja pojedinaca)",
    "uses_counted": "Brojač sajta zbraja po danu i koliko je puta ova stranica otvorena, koliko puta je gledana duže "
                    "od 1, 5, 15 i 30 minuta i koliko puta je pušten prenos ili snimak, otvoren dnevni red ili nešto "
                    "podeljeno, i koliko puta je dodata na početni ekran ili otvorena sa njega i uključena ili isključena "
                    "obaveštenja; bez oznake uređaja i bez ičega o tome ko je to bio",
    "wait_title": "Dok čekate",
    "quiz_lead": "Kviz o Skupštini: {n} pitanja iz brojki i beleški sajta Za ili Protiv. Pogodite, pa vidite koliko "
                 "ste blizu.",
    "question": "Pitanje",
    "questions": "Pitanja",
    "right_is": "Tačno je",
    "next_q": "Sledeće pitanje",
    "see_result": "Vidi rezultat",
    "result": "Rezultat",
    "share": "Podeli rezultat",
    "again": "Igraj ponovo",
    "copied": "Tekst i link su kopirani.",
    "share_text": "Moj rezultat u kvizu o Skupštini:",
    "share_end": "Za ili Protiv, „Ko sada govori“.",
    "answer": "Odgovor",
    "yes": "Tačno!",
    "no": "Nije.",
    "how_counted": "Kako je izračunato",
    "score": "Pogođeno",
    "of": "od",
    "q_all": "Sve tačno! Skupštinu pratite pažljivije od većine.",
    "q_some": "Brojke iznenade i one koji prate sednice. Svaka je na sajtu, s pravilom kako je izračunata.",
    "q_none": "Ništa? Zato i postoji ovaj sajt: sve brojke su tamo, s pravilom kako su izračunate.",
    "know": "Da li ste znali",
    "facts_note": "Brojevi su iz dokumenata Skupštine, izračunati istim pravilom kao na stranicama na koje vode.",
    "live": "Prenos uživo na sajtu Skupštine",
    "home": "Svi zakoni i glasanja poslanika",
    "o_votes": "Konačna glasanja o zakonima:",
    "v_za": "za",
    "v_protiv": "protiv",
    "v_uzdrzan": "uzdržan",
    "o_new": "Novi poslanik u ovom sazivu",
    "o_more": "Svi glasovi i govori na Za ili Protiv",
    "site_cta": "Svaki zakon od 2012. i kako je glasao svaki poslanik",
    "totals": "Ko je koliko govorio",
    "day_page": "Ceo dan na sajtu: svaki govor sa snimkom i linkom za deljenje",
    "conv_page": "Ko koliko govori u celom sazivu",
    "totals_rest": "Ostalih",
    "speakers_n": "govornika",
    "all_turns": "Svi govori, redom",
    "speeches_1": "govor",
    "speeches_n": "govora",
    "script": "Ћирилица",
}


# The site's mark (the chamber as one arc, "za" blue and "protiv" orange), and this page's own beside it: a microphone
# drawn the same way, its capsule in the one colour and its cradle and stand in the other (19 Nov 2026).
ARC = ('<svg class="brand-mark" viewBox="0 0 120 76" aria-hidden="true"><path class="m-za" d="M 14 66 A 46 46 0 0 1 83 26.2"/>'
       '<path class="m-protiv" d="M 89.6 30.8 A 46 46 0 0 1 106 66"/></svg>')
MIC = ('<svg class="mic-mark" viewBox="0 0 76 84" role="img" aria-label="Mikrofon"><rect class="m-za" x="26" y="6" width="24" height="40" rx="12"/>'
       '<path class="m-protiv" d="M 12 36 A 26 26 0 0 0 64 36"/><path class="m-protiv" d="M 38 62 V 78"/></svg>')


def _brand(cyr: bool) -> str:
    words = ('<span class="w-za">За</span> или <span class="w-protiv">Против</span>' if cyr
             else '<span class="w-za">Za</span> ili <span class="w-protiv">Protiv</span>')
    return ARC + f"<span>{words}</span>"


def _fill(text: str, *values) -> str:
    """A text with %1, %2… filled in (the marks survive Cyrillic, which braces' names would not)."""
    for i, v in enumerate(values, 1):
        text = text.replace(f"%{i}", str(v), 1)
    return text


def _t(key: str, cyr: bool) -> str:
    return cyrillic(TEXT[key]) if cyr else TEXT[key]


def _name(s: str, cyr: bool) -> str:
    return cyrillic(s) if cyr else s


def _clock(ts: int, tz: ZoneInfo) -> str:
    return datetime.fromtimestamp(ts, tz).strftime("%H:%M")


def _minutes(sec: int) -> str:
    return str(max(1, round(sec / 60)))


MONTHS = ("januar", "februar", "mart", "april", "maj", "jun", "jul", "avgust", "septembar", "oktobar", "novembar",
          "decembar")


def _date(day: str) -> str:
    y, m, d = (int(x) for x in day.split("-"))
    return f"{d}. {MONTHS[m - 1]} {y}."


def _hms(sec: int) -> str:
    h, m, s = sec // 3600, sec % 3600 // 60, sec % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _recording(d: dict, cyr: bool) -> str:
    """A link to the turn's place in the recording, where the record knows it: in a file of the broadcaster's archive
    (`datoteka`, a day read from the recording) or in the YouTube video of the live broadcast."""
    if d.get("snimak") is None or not (d.get("datoteka") or d.get("video")):
        return ""
    href = escape(f'{d["datoteka"]}#t={d["snimak"]}' if d.get("datoteka") else
                  f'https://www.youtube.com/watch?v={d["video"]}&t={d["snimak"]}s')
    # The page's player opens it in place on a click (data-*); without the script the link opens the recording.
    data = (f'data-file="{escape(d["datoteka"])}"' if d.get("datoteka") else f'data-yt="{escape(d["video"])}"')
    data += f' data-t="{int(d["snimak"])}"' 
    return (f' <a class="rec" href="{href}" {data}title="{escape(_t("recording_title", cyr))}">▶ '
            f'{escape(_t("recording", cyr))} {_hms(d["snimak"])}</a>')


def fragment(snap: dict, *, cyr: bool, site: str, tz: ZoneInfo) -> str:
    """The part of the page that changes: who speaks now, and today's turns."""
    t = lambda k: escape(_t(k, cyr))
    if not config.SHOW_TRANSCRIPT:  # the transcript is written down but not shown (config.SHOW_TRANSCRIPT)
        bare = lambda d: {k: v for k, v in d.items() if k not in ("prepis", "reci", "prepis_ceo")}
        snap = {**snap, "bez_potpisa": None, "sada": bare(snap["sada"]) if snap.get("sada") else snap.get("sada"),
                "danas": [bare(d) for d in snap.get("danas") or []]}
    out = [f'<div id="deo" data-checked="{snap["provereno"]}">']
    cur = snap.get("sada")
    # On the page in this order (the styles' `order`): who is on, the broadcast, the box about the speaker, what is
    # being said, the day. The name and the picture come first on a phone, 86% of the visits (19 Nov 2026).
    for n in sorted(snap.get("obavestenja") or [], key=lambda n: str(n.get("od", "")))[-1:]:  # the newest of what the Assembly has decided, as its own site says it (the site's data/obavestenja.json)
        text = escape(_name(n["tekst"], cyr))
        more = ""
        if str(n.get("url", "")).startswith("https://"):
            more += f' <a href="{escape(n["url"])}">{escape(_name(n.get("izvor") or "izvor", cyr))}</a>'
        if n.get("adresa") and str(n["adresa"]).replace("-", "").isalnum():
            more += f' · <a href="{escape(site + ("cir/" if cyr else "") + "poslanik/" + n["adresa"])}">{t("news_page")}</a>'
        out.append(f'<p class="news"><b>{t("news")}</b> {text}{more}</p>')
    out.append(_agenda(snap, cyr=cyr))
    out.append('<section class="sp-top">')
    said = ""
    if snap["stanje"] == "govori" and cur:
        head, box, said = _speaker(cur, cyr=cyr, site=site, tz=tz)
        out.append(head + '</section><section class="sp">' + box)
    else:
        out.append(f'<p class="state">{t("unknown" if snap["stanje"] == "nepoznato" else "none")}</p>')
        if snap["stanje"] == "nema_prenosa":
            out.append(countdown(snap, cyr=cyr, tz=tz))
        out.append('</section><section class="sp">' + _pause(snap, cyr=cyr, tz=tz))
    if snap["provereno"]:
        out.append(f'<p class="meta" id="checked">{t("checked")} <span>0</span> {t("s")}</p>')
    if not said and snap.get("bez_potpisa"):  # nobody's caption on: the chair's words (or the hall's), named as no one's
        u = snap["bez_potpisa"]
        tail = u["tekst"]
        tail = ("… " + tail.split(" ", 1)[-1]) if len(tail) >= 400 else tail
        said = (f'<div class="said-now"><p class="src">{t("said_unsigned")}</p><p>{escape(_name(tail, cyr))}</p>'
                f'<p class="meta"><a href="{"/cir" if cyr else ""}/prepis">{t("said_all")} →</a></p></div>')
    out.append(f'</section><section class="said-sec">{said}</section>{_steps(snap, cyr=cyr, tz=tz, site=site)}<section class="day">')
    if snap.get("ranije") and snap["danas"]:
        when = _date(snap["dan"])
        out.append(f'<h2>{t("last_day")}, {escape(cyrillic(when) if cyr else when)}</h2>')
        if snap.get("snimak"):
            out.append(f'<p class="meta">{t("from_recording")}</p>')
    else:
        out.append(f'<h2>{t("today")}</h2>')
    if snap["danas"]:
        every = snap["danas"] + ([cur] if snap["stanje"] == "govori" and cur else [])
        shade = _shades(every)
        line = headline(every, cyr=cyr, when=_when(snap, cyr))
        out.append(_tiles(every, cyr=cyr))
        if line and (snap["stanje"] == "govori" and cur):  # otherwise the summary above already says it
            out.append(f'<p class="hl">{escape(line)}</p>')
        out.append(_cards(snap, every, shade, cyr=cyr, site=site, tz=tz))
        out.append(_lists(every, shade, cyr=cyr))
        out.append(_timeline(every, shade, cur if snap["stanje"] == "govori" else None, cyr=cyr, tz=tz))
        out.append(_totals(every, cyr=cyr, site=site, shade=shade))
        where = f'{site}{"cir/" if cyr else ""}'
        more = [f'<a href="{escape(where)}govornici">{t("conv_page")} →</a>']
        if snap.get("snimak") and snap.get("dan"):  # a day read from the recording has its page on the site
            more.insert(0, f'<a href="{escape(where)}govornici/{escape(snap["dan"])}">{t("day_page")} →</a>')
        out.append('<p class="more">' + " · ".join(more) + "</p>")
        out.append(f'<h3 class="sub">{t("all_turns")}</h3>')
        out.append('<ol class="turns">')
        for d in snap["danas"]:
            nm = escape(_name(given_first(d["ime"]), cyr))
            if d["adresa"]:
                nm = f'<a href="{escape(site + ("cir/" if cyr else "") + "poslanik/" + d["adresa"])}">{nm}</a>'
            side = d["uloga"] or d["grupa"]
            side = f' <span class="meta">{escape(_name(side, cyr))}</span>' if side else ""
            if d.get("reci"):
                side += (f' <a class="meta said" href="{"/cir" if cyr else ""}/prepis#t{int(d["od"])}">{t("said_link")}</a>')
            out.append(f'<li id="t{int(d["od"])}"><span class="time">{_clock(d["od"], tz)}–{_clock(d["do"], tz)}</span> {nm}{side}'
                       f' <span class="meta">· {_minutes(d["sekundi"])} {t("min")}</span>{_recording(d, cyr)}</li>')
        out.append("</ol>")
    else:
        out.append(f'<p class="meta">{t("today_none")}</p>')
    out.append("</section></div>")
    return "\n".join(out)



def _agenda(snap: dict, *, cyr: bool) -> str:
    """The sitting's agenda under the broadcast, folded to one line (how many items are done, which is on), the
    items with their state when opened: done by the Assembly's page, done or under way by what the chair said, or
    next in turn (state._agenda). Each state says where it is from."""
    a = snap.get("dnevni_red")
    if not a or not a.get("tacke"):
        return ""
    t = lambda k: escape(_t(k, cyr))
    s = lambda x: escape(_name(x, cyr))
    items = a["tacke"]
    done = sum(1 for x in items if x["stanje"] == "gotova")
    on = next((x for x in items if x["stanje"] in ("u_toku", "na_redu")), None)
    head = f'<b>{t("ag")}</b> <span>{escape(_fill(_t("ag_done", cyr), done, len(items)))}</span>'
    if on:
        head += f'<span class="ag-on">{t("ag_now" if on["stanje"] == "u_toku" else "ag_next")}: {s(on["tekst"])}</span>'
    rows = []
    for x in items:
        mark = {"gotova": "✓", "u_toku": "●", "na_redu": "→"}.get(x["stanje"], "")
        state = ""
        if x["stanje"] == "gotova":
            when = _date(x["kada"]).rsplit(" ", 1)[0] if x.get("kada") else ""
            src = t("ag_site" if x["izvor"] == "sajt" else "ag_said")
            state = f'<span class="src">{t("ag_gotova")}{", " + escape(cyrillic(when) if cyr else when) if when else ""} · {src}</span>'
            if x.get("sta"):
                state += f'<span class="ag-what">{s(x["sta"])}</span>'
        elif x["stanje"] == "u_toku":
            state = f'<span class="src">{t("ag_now")} · {t("ag_said")}</span>'
        elif x["stanje"] == "na_redu":
            state = f'<span class="src">{t("ag_next")}</span>'
        rows.append(f'<li class="ag-{x["stanje"] or "ceka"}"><i aria-hidden="true">{mark}</i><span><b>{x["n"]}.</b> {s(x["tekst"])}{state}</span></li>')
    title = s(a.get("naslov", ""))
    if str(a.get("url", "")).startswith("https://"):
        title = f'<a href="{escape(a["url"])}">{title}</a>'
    return (f'<details class="agenda" id="dnevni-red"><summary>{head}</summary><p class="meta">{title}</p>'
            f'<ol>{"".join(rows)}</ol><p class="meta">{t("ag_note")}</p></details>')


# A step heard in the chair's words, as the page writes it: our own short line for the kind of step, never the
# sentence as the transcript has it (19 Nov 2026: the transcript's wording errs too much to be shown).
STEP_TITLES = {"Sednica otvorena": "Sednica je otvorena", "Nastavak rada": "Rad je nastavljen", "Pauza": "Pauza",
               "Kraj rada": "Kraj rada za danas", "Glasanje": "Glasanje", "Glasanje zaključeno": "Glasanje je zaključeno",
               "Pretres otvoren": "Pretres je otvoren", "Pretres zaključen": "Pretres je zaključen"}
STEP_SAME = 900  # the same step heard again within this many seconds is one line (the chair repeats the phrases)
STEP_QUIET = 240  # a break (or the day's end) is one when nobody is at the rostrum for this long after it is said
STEP_IDLE = 600  # work is resumed when nobody was at the rostrum for this long before the chair says so
_UNDER_WAY = {"Glasanje", "Glasanje zaključeno", "Pretres otvoren", "Pretres zaključen"}


def steps_shown(snap: dict) -> list[dict]:
    """The day's steps as shown, newest first: [{"t", "izvor", "naslov", "opis", "url"}]. From the Assembly's page: its
    sentence, whole. From the chair's words: the step's name (STEP_TITLES), shown only when something else bears it
    out (19 Nov 2026, the maintainer's decision: what cannot be confirmed is not shown):
    - a move to an agenda item: the agenda has the item, and its number is higher than the last one heard today;
    - a break, the day's end: nobody is at the rostrum for STEP_QUIET seconds after it (so it shows that much later);
    - work resumed: a break shown before it, nobody had spoken yet today, or nobody was at the rostrum for
      STEP_IDLE before it (once: a second "we go on" with no break between is the chair's turn of phrase);
      the sitting opened: nobody had spoken yet;
    - a vote, a debate opened or closed: an agenda item is under way;
    - the floor given to an MP ("Reč ima: …"): the chair's words name exactly one sitting MP, whole (hronika.floor),
      and no turn read from the picture stands at that time (with captions on, the captions say who speaks);
    - anything else (a measure, "the chair notes that…") waits for the Assembly's own page.
    The same step within a quarter of an hour is one line."""
    from .hronika import find, item_no
    agenda = (snap.get("dnevni_red") or {}).get("tacke") or []
    items = {int(x["n"]): x["tekst"] for x in agenda}
    now = snap.get("provereno") or 0
    turns = [(d["od"], d["do"]) for d in snap.get("danas") or []]
    if snap.get("sada"):
        turns.append((snap["sada"]["od"], now))
    quiet = lambda t: now >= t + STEP_QUIET and not any(a < t + STEP_QUIET and b > t + 30 for a, b in turns)
    first = lambda t: not any(b < t - 30 for a, b in turns)
    idle = lambda t: not any(a < t and b > t - STEP_IDLE for a, b in turns)  # nobody at the rostrum just before
    out: list[dict] = []
    last: dict[str, int] = {}
    item, paused, resumed = 0, False, ""
    for e in sorted(snap.get("hronika") or [], key=lambda e: e["t"]):
        if e.get("izvor") == "sajt":
            out.append({"t": e["t"], "izvor": "sajt", "naslov": "", "opis": e.get("tekst", ""), "url": e.get("url", "")})
            continue
        kind, more, t = e.get("vrsta", ""), "", e["t"]
        if kind == "Reč ima":  # the chair named a sitting MP (hronika.floor); only while the picture names nobody
            title = "Reč ima: " + given_first(e.get("tekst", ""))
            if any(a < t + 180 and b > t - 60 for a, b in turns) or t - last.get(title, -10 ** 9) < STEP_SAME:
                continue
            last[title] = t
            out.append({"t": t, "izvor": "prepis", "naslov": title, "opis": "", "url": "", "adresa": e.get("url", ""), "rec": True})
            continue
        if kind not in {k for k, _ in find(e.get("tekst", ""))}:
            continue  # kept by a rule since mended: today's rules no longer find it in the sentence
        title = STEP_TITLES.get(kind, "")
        if kind == "Tačka dnevnog reda":
            n = item_no(e.get("tekst", ""))
            if not n or n not in items or n <= item:
                continue
            title, more = f"Prelazak na {n}. tačku dnevnog reda", items[n]
        elif kind in ("Pauza", "Kraj rada"):
            if not quiet(t):
                continue
        elif kind == "Nastavak rada":
            if not (paused or first(t) or (idle(t) and resumed != "on")):
                continue
        elif kind == "Sednica otvorena":
            if not first(t):
                continue
        elif kind in _UNDER_WAY:
            if not (item or any(x.get("stanje") == "u_toku" for x in agenda)):
                continue
        else:
            continue
        if t - last.get(title, -10 ** 9) < STEP_SAME:
            continue
        last[title] = t
        if kind == "Tačka dnevnog reda":
            item = n
        paused = kind in ("Pauza", "Kraj rada") or (paused and kind != "Nastavak rada")
        resumed = "on" if kind == "Nastavak rada" else ("" if paused else resumed)
        out.append({"t": t, "izvor": "prepis", "naslov": title, "opis": more, "url": ""})
    return out[::-1]


def _steps(snap: dict, *, cyr: bool, tz: ZoneInfo, site: str = "") -> str:
    """The day's steps as a line of time, newest first (steps_shown): the hour, a mark for where the line is from
    (a ring: heard in the chair's words; a full dot: written by the Assembly), and the line. The first six shown,
    the rest folded."""
    rows = steps_shown(snap)
    if not rows:
        return ""
    t = lambda k: escape(_t(k, cyr))
    s = lambda x: escape(_name(x, cyr))

    def line(e: dict) -> str:
        if e["izvor"] == "sajt":
            src = t("steps_site")
            if str(e["url"]).startswith("https://"):
                src = f'<a href="{escape(e["url"])}">{src} ↗</a>'
            body = (f'<p class="st-text"><b class="st-off">{t("steps_official")}</b> {s(e["opis"])}</p>'
                    f'<p class="st-src">{src} · {escape(_fill(_t("steps_published", cyr), _clock(e["t"], tz)))}</p>')
        elif e.get("rec"):
            head, _, who = e["naslov"].partition(": ")
            who = s(who)
            if e.get("adresa") and str(e["adresa"]).replace("-", "").isalnum():
                who = f'<a href="{escape(site + ("cir/" if cyr else "") + "poslanik/" + e["adresa"])}">{who}</a>'
            body = f'<p class="st-floor">{s(head)}: <b>{who}</b></p>'
        else:
            body = f'<p class="st-title">{s(e["naslov"])}</p>' + (f'<p class="st-what">{s(e["opis"])}</p>' if e["opis"] else "")
        when = _clock(e["t"], tz) + (f'<small>{t("steps_pub")}</small>' if e["izvor"] == "sajt" else "")
        return (f'<li class="st-{e["izvor"]}{" st-rec" if e.get("rec") else ""}"><span class="time">{when}</span><i aria-hidden="true"></i>'
                f'<div>{body}</div></li>')
    first, rest = rows[:8], rows[8:]
    more = (f'<details><summary>{t("steps_more")} ({len(rows)})</summary><ol class="steps">{"".join(line(e) for e in rest)}</ol></details>'
            if rest else "")
    key = (f'<p class="st-key"><span class="st-prepis"><i aria-hidden="true"></i>{t("steps_said")}</span>'
           f'<span class="st-sajt"><i aria-hidden="true"></i>{t("steps_site_key")}</span></p>')
    # between sittings, the last sitting day's steps, under its date (20 Nov 2026: after midnight the list was gone)
    head = t("steps")
    if snap.get("ranije") and snap.get("dan"):
        when = _date(snap["dan"])
        head = f'{t("steps_then")}, {escape(cyrillic(when) if cyr else when)}'
    return (f'<section class="steps-sec"><h2>{head}</h2><p class="meta">{t("steps_lead")}</p>'
            f'<ol class="steps">{"".join(line(e) for e in first)}</ol>{more}{key}</section>')


def _tiles(turns: list[dict], *, cyr: bool) -> str:
    """The day in four numbers: time on the floor, turns, speakers, and the words written down so far (when the
    transcript is on)."""
    t = lambda k: escape(_t(k, cyr))
    if len(turns) < 2:
        return ""
    words = sum(d.get("reci", 0) for d in turns)
    cells = [(_dur(sum(max(0, d["sekundi"]) for d in turns), cyr), t("n_time")), (len(turns), t("n_turns")),
             (len({d["ime"] for d in turns}), t("n_people"))]
    if words:
        cells.append((f"{words:,}".replace(",", "."), t("n_words")))
    return '<dl class="tiles">' + "".join(f'<div><dd>{escape(str(v))}</dd><dt>{k}</dt></div>' for v, k in cells) + "</dl>"


def _cards(snap: dict, turns: list[dict], shade: dict[str, str], *, cyr: bool, site: str, tz: ZoneInfo) -> str:
    """The day in a few cards to tap through (19 Nov 2026, the maintainer's choice): the whole time, who had the
    most, the time by list, the longest turn, who came up most often, and the way to the site. Every card by a rule,
    the same whoever it names. The cards wait hidden in the page; the script shows them full screen on a tap."""
    rows = leaders(turns)
    if len(rows) < 2:
        return ""
    t = lambda k: escape(_t(k, cyr))
    n = lambda x: escape(_name(x, cyr))
    if snap.get("ranije") and snap.get("dan"):
        when = _date(snap["dan"])
        when = cyrillic(when) if cyr else when
    else:
        when = _t("h_today", cyr).capitalize() + ", " + (cyrillic(_date(snap["dan"])) if cyr else _date(snap["dan"]))
    whole = sum(r[1] for r in rows)
    card = lambda kicker, body: f'<section class="st-c"><p class="st-k">{kicker}</p>{body}</section>'
    out = [card(escape(when), f'<p class="st-big">{_dur(whole, cyr)}</p><p class="st-s">{t("st_total")}</p>'
                              f'<p class="st-row"><b>{len(turns)}</b> {t("n_turns")} · <b>{len(rows)}</b> {t("n_people")}</p>')]
    name, sec, _ = rows[0]
    out.append(card(t("st_most"), f'<p class="st-name">{n(given_first(name))}</p><p class="st-big">{_dur(sec, cyr)}</p>'
                                  f'<p class="st-s">{escape(headline(turns, cyr=cyr, when=_when(snap, cyr)))}</p>'))
    lists = _lists(turns, shade, cyr=cyr)
    if lists:
        out.append(f'<section class="st-c">{lists.replace("<h3 class=\"sub\">", "<p class=\"st-k\">").replace("</h3>", "</p>")}</section>')
    longest = max(turns, key=lambda d: (d["sekundi"], -d["od"]))
    out.append(card(t("st_longest"), f'<p class="st-name">{n(given_first(longest["ime"]))}</p>'
                                     f'<p class="st-big">{_dur(longest["sekundi"], cyr)}</p>'
                                     f'<p class="st-s">{_clock(longest["od"], tz)}–{_clock(longest["do"], tz)}</p>'))
    count: dict[str, int] = {}
    for d in turns:
        count[d["ime"]] = count.get(d["ime"], 0) + 1
    often = max(count, key=lambda k: (count[k], k))
    if count[often] >= 3:
        out.append(card(t("st_often"), f'<p class="st-name">{n(given_first(often))}</p>'
                                       f'<p class="st-big">{count[often]} <small>{t("st_times")}</small></p>'))
    home = site + ("cir/" if cyr else "")
    out.append(card(t("st_end"), f'<p class="st-name">{t("st_site")}</p>'
                                 f'<p><a class="cta" href="{escape(home)}">zailiprotiv.rs →</a></p>'))
    go = (f'<p class="acts st-go"><button type="button" class="share-now st-open">▶ {t("st_open")}</button></p>'
          if snap["stanje"] == "govori" and snap.get("sada") else "")
    return (go +
            f'<div class="st-data" hidden data-close="{t("st_close")}" data-hint="{t("st_hint")}">{"".join(out)}</div>')


def transcript_page(data: dict, *, cyr: bool, site: str, tz: ZoneInfo, url: str = "") -> str:
    """The day's automatic transcript, turn by turn, newest first: a page of its own, so that the part of the main
    page every visitor asks for every few seconds stays small."""
    t = lambda k: escape(_t(k, cyr))
    base = "/cir/" if cyr else "/"
    home = site + ("cir/" if cyr else "")
    when = _date(data["dan"]) if data.get("dan") else ""
    rows = []
    for d in data["govori"]:
        nm = escape(_name(given_first(d["ime"]), cyr)) if not d.get("bez") else f'<i>{t("said_nobody")}</i>'
        if d["adresa"]:
            nm = f'<a href="{escape(home + "poslanik/" + d["adresa"])}">{nm}</a>'
        text = escape(cyrillic(d["tekst"]) if cyr else d["tekst"])
        subject = f'Ispravka prepisa: {given_first(d["ime"]) or "bez potpisa"}, {data.get("dan", "")} {_clock(d["od"], tz)}'
        body = "Pogrešno napisano:\n\nTreba da piše:\n\n(Ispravljamo pravopis i imena, ne ono što je rečeno.)"
        mail = f'mailto:kontakt@zailiprotiv.rs?subject={quote(subject)}&body={quote(body)}'
        second = f' · {t("said_second")}' if d.get("ceo") else ""
        rows.append(f'<article id="t{int(d["od"])}"><h2>{nm} <span class="meta">{_clock(d["od"], tz)}–{_clock(d["do"], tz)}'
                    f' · {_minutes(d["sekundi"])} {t("min")}{second}</span></h2><p>{text}</p>'
                    f'<p class="meta"><a href="{escape(mail)}">{t("said_report")}</a></p></article>')
    body = "".join(rows) or f'<p class="meta">{t("said_none")}</p>'
    brand = _brand(cyr)
    return f"""<!doctype html>
<html lang="{"sr-Cyrl" if cyr else "sr-Latn"}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{t("said_title")}{", " + escape(cyrillic(when) if cyr else when) if when else ""} · {"За или Против" if cyr else "Za ili Protiv"}</title>
<meta name="robots" content="noindex">
<link rel="icon" type="image/svg+xml" href="{escape(site)}favicon.svg">
<style>{CSS}</style>
</head>
<body>
<header class="top"><a class="brand" href="{escape(home)}">{brand}</a><span class="top-r"><a class="mic" href="{base}" title="{t("title")}">{MIC}</a><a href="{base}">{t("said_back")}</a></span></header>
<main class="said-page">
<h1>{t("said_title")}{", " + escape(cyrillic(when) if cyr else when) if when else ""}</h1>
<p class="lead">{t("said_lead")}</p>
<p class="meta">{t("said_fix")}</p>
{body}
<p><a href="{base}">← {t("said_back")}</a></p>
</main>
<script>
// The page as it is now, asked for again every twenty seconds while it is looked at; what is read stays in place.
setInterval(function () {{
  if (document.hidden) return;
  fetch(location.pathname + location.search, {{ cache: "no-store" }}).then(function (r) {{ return r.ok ? r.text() : null; }}).then(function (html) {{
    if (!html) return;
    var now = new DOMParser().parseFromString(html, "text/html").querySelector("main");
    var main = document.querySelector("main");
    if (now && main && now.innerHTML !== main.innerHTML) main.innerHTML = now.innerHTML;
  }}).catch(function () {{}});
}}, 20000);
</script>
</body>
</html>"""


def _when(snap: dict, cyr: bool) -> str:
    """"danas", or the date of the earlier day shown."""
    if snap.get("ranije") and snap.get("dan"):
        day = _date(snap["dan"]).rstrip(".")
        return day.rsplit(" ", 1)[0]  # "18. novembar": the year is in the heading
    return ""


WEEKDAYS = ("ponedeljak", "utorak", "sreda", "četvrtak", "petak", "subota", "nedelja")
STALE = 12 * 3600  # a sitting convened this long ago with no broadcast seen is no longer counted down to


def _units(cyr: bool) -> dict[str, str]:
    """The countdown's words; hours as "ч" in Cyrillic, as _dur writes them (letter by letter "h" would be "х")."""
    return {"d1": _t("nx_day1", cyr), "dn": _t("nx_days", cyr), "h": "ч" if cyr else "h", "m": "мин" if cyr else "min",
            "soon": _t("nx_soon", cyr)}


def left(sec: int, u: dict[str, str]) -> str:
    """Time left as the countdown writes it (the page's script writes it the same way each second): days and hours,
    or hours and minutes, or minutes."""
    if sec <= 0:
        return u["soon"]
    d, rest = divmod(int(sec), 86400)
    h, m = rest // 3600, rest % 3600 // 60
    if d:
        return f'{d} {u["d1"] if d % 10 == 1 and d % 100 != 11 else u["dn"]}' + (f' {h} {u["h"]}' if h else "")
    if h:
        return f'{h} {u["h"]} {m} {u["m"]}'
    return f'{max(1, m)} {u["m"]}'


def countdown(snap: dict, *, cyr: bool, tz: ZoneInfo, now: float | None = None) -> str:
    """Between sittings, the next one convened (20 Nov 2026, the maintainer's choice, for visitors to know when to come
    back): when it begins, counted down each second by the page's script (by days when the Assembly gives no hour),
    its title and agenda as the Assembly lists them. Nothing when none is convened, or one convened has long begun."""
    c = snap.get("sazvano") or {}
    p = str(c.get("pocinje") or "")
    try:
        day = datetime.strptime(p[:10], "%Y-%m-%d").date()
    except ValueError:
        return ""
    now = time.time() if now is None else now
    t = lambda k: escape(_t(k, cyr))
    hour = p[11:16] if len(p) >= 16 else ""
    when = f'{WEEKDAYS[day.weekday()].capitalize()}, {_date(p[:10])}' + (f' {TEXT["at"]} {hour}' if hour else "")
    if hour:
        at = int(datetime.strptime(p[:16], "%Y-%m-%dT%H:%M").replace(tzinfo=tz).timestamp())
        if now - at > STALE:
            return ""
        u = _units(cyr)
        data = " ".join(f'data-{k}="{escape(v)}"' for k, v in u.items())
        big = (f'<p class="nx-big"><span{" hidden" if now >= at else ""}>{t("nx_in")}</span> '
               f'<b class="nx-in" data-at="{at}" {data}>{escape(left(at - int(now), u))}</b></p>')
    else:
        days = (day - datetime.fromtimestamp(now, tz).date()).days
        if days < 0:
            return ""
        if days < 2:
            big = f'<p class="nx-big"><b>{t("nx_today" if days == 0 else "nx_tomorrow")}</b></p>'
        else:
            word = t("nx_day1" if days % 10 == 1 and days % 100 != 11 else "nx_days")
            big = f'<p class="nx-big"><span>{t("nx_in")}</span> <b>{days} {word}</b></p>'
    title = escape(_name(c.get("naslov", ""), cyr))
    if str(c.get("url", "")).startswith("https://"):
        title = f'<a href="{escape(c["url"])}">{title}</a>'
    items = [x for x in c.get("tacke") or [] if x]
    agenda = (f'<details class="nx-ag" id="nx-ag"><summary>{t("nx_agenda")} ({len(items)})</summary><ol>'
              + "".join(f'<li>{escape(_name(x, cyr))}</li>' for x in items) + "</ol></details>") if items else ""
    return (f'<div class="nx"><p class="src">{t("coming")}</p>{big}'
            f'<p class="nx-when">{escape(_name(when, cyr))}</p><p class="nx-title">{title}</p>{agenda}'
            f'<p class="meta">{t("nx_note")}</p></div>')


def manifest(cyr: bool) -> dict:
    """The page as an app on a phone's home screen (20 Nov 2026): its name, where it opens, its icons (picture.icon)."""
    base = "/cir/" if cyr else "/"
    icon = lambda src, size, purpose: {"src": src, "sizes": f"{size}x{size}", "type": "image/png", "purpose": purpose}
    return {"id": base, "name": _t("title", cyr), "short_name": _t("app_name", cyr), "description": _t("lead", cyr),
            "lang": "sr-Cyrl" if cyr else "sr-Latn", "start_url": base, "scope": base, "display": "standalone",
            "background_color": "#ffffff", "theme_color": "#ffffff",
            "icons": [icon("/ikona-192.png", 192, "any"), icon("/ikona-512.png", 512, "any"),
                      icon("/ikona-maskable-512.png", 512, "maskable")]}


def _pause(snap: dict, *, cyr: bool, tz: ZoneInfo) -> str:
    """While nobody is on (a break, or between sittings): the day so far in place of an empty box. The sentence of the
    day, the three with the most time, and the picture of it to share (`picture.py`, the page's link preview too)."""
    turns = snap.get("danas") or []
    line = headline(turns, cyr=cyr, when=_when(snap, cyr))
    if not line:
        return ""
    t = lambda k: escape(_t(k, cyr))
    if snap.get("ranije"):
        when = _date(snap["dan"])
        head = f'{t("last_day")}, {escape(cyrillic(when) if cyr else when)}'
    else:
        head = t("so_far")
    top = "".join(f'<li><b>{escape(_name(given_first(n), cyr))}</b> <span>{_dur(sec, cyr)}</span></li>'
                  for n, sec, _ in leaders(turns)[:3])
    src = ("/cir" if cyr else "") + "/slika.png"
    tall = ("/cir" if cyr else "") + "/prica.png"
    coming = snap.get("sazvano")
    nxt = ""
    if coming and coming.get("pocinje") and snap["stanje"] != "nema_prenosa":  # between sittings: the countdown says it
        day = _date(coming["pocinje"][:10])
        hour = f' {t("at")} {escape(coming["pocinje"][11:16])}' if len(coming["pocinje"]) > 10 else ""
        title = escape(_name(coming.get("naslov", ""), cyr))
        if str(coming.get("url", "")).startswith("https://"):
            title = f'<a href="{escape(coming["url"])}">{title}</a>'
        nxt = f'<p class="pz-next"><b>{t("coming")}:</b> {escape(cyrillic(day) if cyr else day)}{hour}. {title}</p>'
    return (f'<div class="o pz"><p class="src">{head}</p><p class="hl">{escape(line)}</p><ol class="pz-top">{top}</ol>{nxt}'
            f'<p class="acts"><button type="button" class="share-now st-open">▶ {t("st_open")}</button> '
            f'<button type="button" class="share-now share-day" data-src="{src}" '
            f'data-text="{t("sd_text")}" data-done="{t("sh_done")}">{t("share_day")}</button> '
            f'<button type="button" class="share-now share-day tall" data-src="{tall}" '
            f'data-text="{t("sd_text")}" data-done="{t("sh_done")}">{t("share_tall")}</button></p>'
            f'<p class="meta share-said" hidden></p></div>')


def _dur(sec: int, cyr: bool = False) -> str:
    h, m = divmod(max(60, sec) // 60, 60)
    hour, minute = ("ч", "мин") if cyr else ("h", "min")
    return f"{h} {hour} {m} {minute}" if h else f"{m} {minute}"


def _totals(turns: list[dict], *, cyr: bool, site: str, top: int = 8, shade: dict[str, str] | None = None) -> str:
    """The day's time on the floor per speaker, longest first, as bars: the turns summed, by the same rule for all."""
    t = lambda k: escape(_t(k, cyr))
    by: dict[str, list] = {}
    tone: dict[str, str] = {}
    for d in turns:
        tone.setdefault(d["ime"], (shade or {}).get(d.get("lista") or "", ""))
        row = by.setdefault(d["ime"], [0, 0, d.get("adresa", ""),
                                       (d.get("lista") or "").strip("*") or d.get("uloga") or d.get("grupa") or ""])
        row[0] += max(0, d["sekundi"])
        row[1] += 1
    rows = sorted(by.items(), key=lambda kv: -kv[1][0])
    if len(rows) < 2:
        return ""
    whole = sum(r[0] for _, r in rows) or 1
    most = rows[0][1][0] or 1
    out = [f'<h3 class="sub">{t("totals")}</h3><div class="tot">']
    def line(name_html: str, side: str, sec: int, n: int, rest: bool = False, cls: str = "") -> str:
        share = f"{100 * sec / whole:.0f}".replace(".", ",")
        word = t("speeches_1") if n == 1 else t("speeches_n")
        under = f'<span>{escape(_name(side, cyr))}</span>' if side else ""
        return (f'<div class="tr{" rest" if rest else ""}"><div class="tn">{name_html}{under}</div>'
                f'<div class="tb"><i{f' class="{cls}"' if cls else ""} style="width:{max(1.5, 100 * sec / most):.1f}%"></i></div>'
                f'<div class="tv"><b>{_dur(sec, cyr)}</b><span>{share}% · {n} {word}</span></div></div>')
    for name, (sec, n, slug, side) in rows[:top]:
        nm = escape(_name(given_first(name), cyr))
        if slug:
            nm = f'<a href="{escape(site + ("cir/" if cyr else "") + "poslanik/" + slug)}">{nm}</a>'
        out.append(line(nm, side, sec, n, cls=tone.get(name, "")))
    rest = rows[top:]
    if rest:
        out.append(line(f'{t("totals_rest")} {len(rest)} {t("speakers_n")}', "", sum(r[0] for _, r in rest),
                        sum(r[1] for _, r in rest), rest=True))
    out.append("</div>")
    return "".join(out)


def _speaker(cur: dict, *, cyr: bool, site: str, tz: ZoneInfo) -> tuple[str, str, str]:
    """The speaker: the portrait (an MP's, from the Assembly, served by the site), the name, the list, a clock that
    runs, and a box: the day so far and the convocation first (there for every speaker), then one line about the MP
    at a time, each saying where it is from, the way to the MP's page and the picture to share. The same for every
    speaker, by rules; a name not on the site's list gets the day's numbers only."""
    t = lambda k: escape(_t(k, cyr))
    s = lambda x: escape(_name(x, cyr))
    o = cur.get("o") or {}
    page_ = f'{site}{"cir/" if cyr else ""}poslanik/{cur["adresa"]}' if cur["adresa"] else ""
    name = s(given_first(cur["ime"]))
    shown = f'<a href="{escape(page_)}">{name}</a>' if page_ else name
    side = cur.get("uloga") or cur.get("lista") or cur.get("grupa") or ""
    out = ['<div class="sp-head">']
    if o.get("foto") and str(o["foto"]).replace(".", "").replace("-", "").isalnum():
        out.append(f'<img class="ph" src="{escape(site)}foto/{escape(o["foto"])}" width="72" height="96" alt="">')
    out.append(f'<div><p class="now"><span class="dot" aria-hidden="true"></span><span class="who">{shown}</span></p>')
    if side:
        out.append(f'<p class="side">{s(side)}</p>')
    if not cur["adresa"]:
        out.append(f'<p class="meta">({t("not_listed")})</p>')
    longer = (" · " + s(TEXT["longest"] if cur["duze"] >= 100 else TEXT["longer"].format(p=cur["duze"]))) if cur.get("duze", 0) >= 50 else ""
    out.append(f'<p class="clock"><b class="clk" data-od="{int(cur["od"])}" data-sek="{int(cur["sekundi"])}">'
               f'{_hms(max(0, cur["sekundi"]))}</b> <span>{t("since")} {_clock(cur["od"], tz)}{longer}</span></p></div></div>')
    head, out = "".join(out), []
    out.append('<div class="o">')
    today, line = cur.get("danas"), ""
    if today:
        bits = [TEXT["d_turn"].format(n=today["n"]), TEXT["d_total"].format(t=_dur(today["sek"], cyr))]
        if today["od"] >= 2:
            bits.append(TEXT["d_rank"].format(m=today["mesto"], n=today["od"]))
        out.append(f'<dl class="nums"><div><dt>{t("d_today")}</dt><dd>{s(" · ".join(bits))}</dd></div>')
        conv = cur.get("saziv")
        if conv:
            words = TEXT["d_conv_line"].format(t=_dur(conv["sek"], cyr), n=conv["n"],
                                               w=TEXT["speeches_1"] if conv["n"] == 1 else TEXT["speeches_n"])
            out.append(f'<div><dt>{escape(str(conv["broj"]))}. {t("d_conv")}</dt><dd>{s(words)}</dd></div>')
        out.append("</dl>")
        line = TEXT["sh_today"].format(t=_dur(today["sek"], cyr), n=today["n"]) if today["n"] > 1 else TEXT["sh_first"]
    lines = [c for c in o.get("c") or [] if c.get("t")]
    if not lines and o.get("f"):  # the site's file as it was before 19 Nov 2026
        lines = [{"t": f, "iz": ""} for f in o["f"]]
    if lines:
        items = "".join(f'<li>{f"""<span class="src">{s(c["iz"])}</span>""" if c.get("iz") else ""}{s(c["t"])}</li>'
                        for c in lines)
        more = (f'<button type="button" class="rot-next" aria-label="{t("next_fact")}"><span class="rot-n">1/{len(lines)}'
                f'</span> ›</button>') if len(lines) > 1 else ""
        out.append(f'<div class="rot-w"><ul class="rot">{items}</ul>{more}</div>')
    said = ""
    if cur.get("prepis"):
        tail = cur["prepis"]
        tail = ("… " + tail.split(" ", 1)[-1]) if len(tail) >= 400 else tail  # cut at a word, not inside one
        said = (f'<div class="said-now"><p class="src">{t("said_now")}</p><p>{s(tail)}</p>'
                f'<p class="meta"><a href="{"/cir" if cyr else ""}/prepis#t{int(cur["od"])}">{t("said_all")} →</a></p></div>')
    when = _date(datetime.fromtimestamp(cur["do"], tz).strftime("%Y-%m-%d")) + f' u {_clock(cur["do"], tz)}'
    data = {"head": _t("sh_head", cyr), "name": _name(given_first(cur["ime"]), cyr), "side": _name(side, cyr),
            "already": _t("sh_already", cyr), "min": _t("min", cyr), "line": _name(line, cyr), "when": _name(when, cyr),
            "note": _t("sh_note", cyr), "text": _t("sh_text", cyr), "done": _t("sh_done", cyr)}
    attrs = " ".join(f'data-{k}="{escape(v)}"' for k, v in data.items())
    cta = f'<a class="cta" href="{escape(page_)}">{t("o_more")} →</a> ' if page_ else ""
    tall = (f' <button type="button" class="share-now share-day tall" data-src="{"/cir" if cyr else ""}/prica.png" '
            f'data-text="{t("sd_text")}" data-done="{t("sh_done")}">{t("share_tall")}</button>')
    out.append(f'<p class="acts">{cta}<button type="button" class="share-now" {attrs}>{t("share_now")}</button>{tall}</p>'
               f'<p class="meta share-said" hidden></p></div>')
    return head, "".join(out), said


def leaders(turns: list[dict]) -> list[tuple[str, int, str]]:
    """Today's speakers by time, longest first: (name, seconds, list)."""
    by: dict[str, list] = {}
    for d in turns:
        x = by.setdefault(d["ime"], [0, d.get("lista") or ""])
        x[0] += max(0, d["sekundi"])
    return sorted(((k, v[0], v[1]) for k, v in by.items()), key=lambda r: (-r[1], r[0]))


def headline(turns: list[dict], *, cyr: bool, when: str = "") -> str:
    """The day in one sentence, by one rule whoever leads: the speaker with the most time, their time, and either the
    largest other list whose speakers together had less, or their share of all the time. With two speakers or more."""
    rows = leaders(turns)
    whole = sum(r[1] for r in rows)
    if len(rows) < 2 or not whole:
        return ""
    name, sec, own = rows[0]
    per: dict[str, int] = {}
    for _, v, l in rows:
        if l and l != "*" and l != own:
            per[l] = per.get(l, 0) + v
    less = sorted((l for l in per if per[l] < sec), key=lambda l: (-per[l], l))
    n = lambda x: _name(x, cyr)
    tail = (_fill(_t("h_more", cyr), n(less[0]), _dur(per[less[0]], cyr)) if less
            else _fill(_t("h_share", cyr), round(100 * sec / whole)))
    return _fill(_t("h_most", cyr), n(when or TEXT["h_today"]), n(given_first(name)), _dur(sec, cyr)) + ", " + tail + "."


# The colour of a list in the day's bars (19 Nov 2026, the maintainer's decision; an exception to "colour only for
# za and protiv", kept to this page). Hues apart from those two, checked for colour-blind readers; a list not named
# here keeps a shade of grey, and the key beside the bar always names each.
LIST_COLOURS = {"Aleksandar Vučić - Srbija pobeđuje": "c-av", "Studentska lista": "c-sl"}
HEX = {"c-av": "#1d4ed8", "c-sl": "#e11d48", "c-mn": "#0f9d8a", "l1": "#5c5c5c", "l2": "#9a9a9a", "l3": "#c4c4c4",
       "lx": "#d8d8d8"}  # the same colours for the picture (picture.py), which has no stylesheet


def _shades(turns: list[dict]) -> dict[str, str]:
    """The class of each list with time today: its colour (LIST_COLOURS), one colour for sitting MPs of smaller lists
    or no group together, a shade of grey for a list with no colour of its own, hatched grey for the rest."""
    by: dict[str, int] = {}
    for d in turns:
        by[d.get("lista") or ""] = by.get(d.get("lista") or "", 0) + max(0, d["sekundi"])
    named = sorted((k for k in by if k and k != "*" and k not in LIST_COLOURS), key=lambda k: (-by[k], k))
    return {**{k: f"l{min(i + 1, 3)}" for i, k in enumerate(named)}, **LIST_COLOURS, "*": "c-mn", "": "lx"}


def _lists(turns: list[dict], shade: dict[str, str], *, cyr: bool) -> str:
    """The day's time by list as one bar and its key: the turns summed, by the same rule for every list."""
    t = lambda k: escape(_t(k, cyr))
    by: dict[str, list[int]] = {}
    for d in turns:
        x = by.setdefault(d.get("lista") or "", [0, 0])
        x[0] += max(0, d["sekundi"])
        x[1] += 1
    whole = sum(x[0] for x in by.values())
    if not whole or len(turns) < 2:
        return ""
    rows = sorted(by.items(), key=lambda kv: (("*", "").index(kv[0]) + 1 if kv[0] in ("*", "") else 0, -kv[1][0], kv[0]))
    label = lambda k: t("no_list") if not k else t("other_lists") if k == "*" else escape(_name(k, cyr))
    bar = "".join(f'<i class="{shade[k]}" style="width:{100 * v[0] / whole:.2f}%"></i>' for k, v in rows if v[0])
    key = "".join(f'<li><i class="{shade[k]}"></i><span>{label(k)}</span>'
                  f'<b>{_dur(v[0], cyr)}</b><em>{100 * v[0] / whole:.0f}%</em></li>' for k, v in rows if v[0])
    return f'<h3 class="sub">{t("lists")}</h3><div class="lb">{bar}</div><ul class="lk">{key}</ul>'


def _timeline(turns: list[dict], shade: dict[str, str], cur: dict | None, *, cyr: bool, tz: ZoneInfo) -> str:
    """The day as a strip from its first turn to its last: a block a turn, in its list's shade, the one now on marked;
    a click leads to the turn in the list below. Breaks show as gaps."""
    if len(turns) < 3:
        return ""
    t = lambda k: escape(_t(k, cyr))
    start, end = min(d["od"] for d in turns), max(d["do"] for d in turns)
    span = max(60, end - start)
    blocks = []
    for d in sorted(turns, key=lambda d: d["od"]):
        on = cur is not None and d is cur
        tip = f'{_clock(d["od"], tz)} {_name(given_first(d["ime"]), cyr)} · {_minutes(d["sekundi"])} {_t("min", cyr)}'
        blocks.append(f'<a class="{shade.get(d.get("lista") or "", "lx")}{" on" if on else ""}" '
                      f'href="#{"deo" if on else "t" + str(int(d["od"]))}" title="{escape(tip)}" '
                      f'style="left:{100 * (d["od"] - start) / span:.2f}%;width:{max(0.35, 100 * (d["do"] - d["od"]) / span):.2f}%"></a>')
    first = datetime.fromtimestamp(start, tz)
    marks = [f'<span style="left:0">{first.strftime("%H:%M")}</span>']
    hour = first.replace(minute=0, second=0, microsecond=0)
    while True:
        hour = datetime.fromtimestamp(hour.timestamp() + 3600, tz)
        at = 100 * (hour.timestamp() - start) / span
        if at > 97:
            break
        if at > 13:
            marks.append(f'<span style="left:{at:.2f}%">{hour.strftime("%H")}</span>')
    return (f'<h3 class="sub">{t("timeline")}</h3><div class="tl">{"".join(blocks)}</div>'
            f'<div class="tl-ax" aria-hidden="true">{"".join(marks)}</div><p class="meta">{t("timeline_note")}</p>')


def _shared(name: str) -> str:
    """A file the page shares with the site's mikrofon page (src/zailiprotiv/templates): copied into the image beside
    this module, read from the repository when run from it (the tests)."""
    for path in (Path(__file__).parent / "static" / name,
                 Path(__file__).resolve().parents[2] / "src" / "zailiprotiv" / "templates" / name):
        if path.is_file():
            return path.read_text(encoding="utf-8")
    return ""


CSS = """
@font-face { font-family: "Literata"; font-style: normal; font-display: swap; font-weight: 200 900;
  src: url(/fonts/literata-latin-ext-wght-normal.woff2) format("woff2");
  unicode-range: U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C4,U+2113,U+2C60-2C7F,U+A720-A7FF; }
@font-face { font-family: "Literata"; font-style: normal; font-display: swap; font-weight: 200 900;
  src: url(/fonts/literata-cyrillic-wght-normal.woff2) format("woff2"); unicode-range: U+0301,U+0400-045F,U+0490-0491,U+04B0-04B1,U+2116; }
@font-face { font-family: "Literata"; font-style: normal; font-display: swap; font-weight: 200 900;
  src: url(/fonts/literata-latin-wght-normal.woff2) format("woff2");
  unicode-range: U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD; }
:root { --bg: #fff; --fg: #111; --muted: #555; --line: #d9d9d9; --za: #1f5fa8; --protiv: #c2410c;
  --c-av: #1d4ed8; --c-sl: #e11d48; --c-mn: #0f9d8a;
  --serif: "Literata", Georgia, "Times New Roman", serif; }
@media (prefers-color-scheme: dark) { :root { --bg: #111318; --fg: #f1f1ee; --muted: #a8adb8; --line: #30343c; --za: #7cc0f5; --protiv: #ff9a52; --c-av: #4a86f0; --c-sl: #ef3a5d; --c-mn: #12a594; } }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--fg); font: 16px/1.55 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
a { color: var(--fg); text-underline-offset: 2px; } a:hover { color: var(--za); }
.top { display: flex; flex-wrap: wrap; gap: 0 2rem; align-items: baseline; justify-content: space-between; max-width: 760px; margin: 0 auto; padding: 1rem 20px .6rem; border-bottom: 3px solid var(--fg); }
.brand { font-family: var(--serif); font-weight: 700; font-size: 1.5rem; text-decoration: none; letter-spacing: -.01em; display: inline-flex; align-items: center; gap: .5rem; }
.brand-mark { width: 2.1rem; height: auto; flex: none; } .brand-mark path, .mic-mark path, .mic-mark rect { fill: none; stroke-width: 16; }
.mic-mark { width: 1.35rem; height: auto; display: block; } .mic-mark path, .mic-mark rect { stroke-width: 9; }
.m-za { stroke: var(--za); } .m-protiv { stroke: var(--protiv); }
.top { align-items: center; } .top-r { display: inline-flex; align-items: center; gap: .9rem; } .top-r .mic { display: block; }
.brand .w-za { color: var(--za); } .brand .w-protiv { color: var(--protiv); }
main { max-width: 760px; margin: 0 auto; padding: 0 20px 3rem; }
h1, h2 { font-family: var(--serif); font-weight: 700; letter-spacing: -.015em; }
h1 { font-size: clamp(1.7rem, 4.5vw, 2.4rem); line-height: 1.12; margin: 1.4rem 0 .4rem; }
h2 { font-size: 1.35rem; margin: 2.4rem 0 .6rem; }
.lead, .meta { color: var(--muted); } .meta { font-size: .9rem; margin: .2rem 0; }
.now { display: flex; gap: .8rem; align-items: baseline; margin: 2rem 0 .3rem; }
.o { margin: .9rem 0 0; padding: .8rem 1rem; border: 1px solid var(--line); border-radius: 8px; }
.o p, .o ul { margin: 0 0 .5rem; } .o ul { padding-left: 1.1rem; color: var(--muted); font-size: .95rem; }
.v-za { color: var(--za); } .v-protiv { color: var(--protiv); }
.cta { display: inline-block; font-weight: 600; text-decoration: none; padding: .45rem .8rem; border-radius: 6px;
  background: var(--fg); color: var(--bg); } .cta:hover { color: var(--bg); opacity: .85; }
.site-cta { margin: 1.4rem 0 0; font-weight: 600; } .site-cta a { color: var(--za); }
.dot { flex: none; width: .8rem; height: .8rem; border-radius: 50%; background: var(--protiv); }
.who { font-family: var(--serif); font-weight: 700; font-size: clamp(2rem, 7vw, 3.4rem); line-height: 1.05; }
.who a { text-decoration: none; }
.side { font-size: 1.15rem; margin: .2rem 0 .3rem 1.6rem; }
.now ~ .meta { margin-left: 1.6rem; }
.state { font-family: var(--serif); font-size: 1.5rem; margin: 2rem 0 .4rem; }
.turns { list-style: none; padding: 0; margin: 0; }
.turns li { padding: .5rem 0; border-bottom: 1px solid var(--line); }
.rec { font-size: .9rem; color: var(--muted); white-space: nowrap; margin-left: .3rem; font-variant-numeric: tabular-nums; }
.time { font-variant-numeric: tabular-nums; color: var(--muted); margin-right: .4rem; }
footer { max-width: 760px; margin: 0 auto; padding: 1.2rem 20px 3rem; border-top: 1px solid var(--line); color: var(--muted); font-size: .9rem; }
h3 { font-family: var(--serif); }
h3.sub { font-size: 1.1rem; margin: 1.6rem 0 .6rem; }
.tot { display: grid; gap: .55rem; }
.tr { display: grid; grid-template-columns: minmax(9rem, 14rem) 1fr 7.5rem; gap: .8rem; align-items: center; }
.tn { font-weight: 600; line-height: 1.2; } .tn a { text-decoration: none; }
.tn span { display: block; font-weight: 400; font-size: .8rem; color: var(--muted); }
.tb { height: .9rem; } .tb i { display: block; height: 100%; background: var(--fg); border-radius: 0 3px 3px 0; opacity: .8; }
.tv { line-height: 1.15; font-variant-numeric: tabular-nums; } .tv b { display: block; }
.tv span { font-size: .8rem; color: var(--muted); }
.tr.rest .tn { color: var(--muted); font-weight: 500; } .tr.rest .tb i { opacity: .35; }
@media (max-width: 520px) { .tr { grid-template-columns: 1fr 6.5rem; } .tb { grid-column: 1 / -1; order: 3; height: .6rem; } }
.now { padding-top: .2rem; }
.o { background: color-mix(in srgb, var(--fg) 4%, transparent); }
/* The order on the page: the speaker, the player, the day. #deo is replaced whole every few seconds and the player must
   stay, so #deo's two parts are laid out as the page's own (display: contents) and ordered around the player. */
main { display: flex; flex-direction: column; }
main > * { order: 6; }
main > h1, main > .lead, main > .hero { order: 0; }
#deo { display: contents; }
.news { order: 0; margin: .9rem 0 0; padding: .7rem .9rem; border: 2px solid var(--fg); border-radius: 8px; font-size: .98rem; line-height: 1.45; } .news b { text-transform: uppercase; letter-spacing: .06em; font-size: .8rem; color: var(--protiv); margin-right: .3rem; }
main > .player { order: 1; } .sp-top { order: 2; } .sp { order: 3; } .said-sec { order: 4; } .day { order: 5; }
.agenda { order: 1; margin: .9rem 0 0; border: 1px solid var(--line); border-radius: 10px; padding: .7rem .9rem; }
.agenda summary { cursor: pointer; display: flex; flex-wrap: wrap; gap: .2rem .7rem; align-items: baseline; list-style: none; line-height: 1.4; }
.agenda summary::-webkit-details-marker { display: none; } .agenda summary { position: relative; padding-right: 1.4rem; } .agenda summary::after { content: "+"; position: absolute; right: 0; top: 0; color: var(--muted); } .agenda[open] summary::after { content: "−"; }
.agenda summary > span { color: var(--muted); font-size: .92rem; } .agenda .ag-on { flex: 1 1 100%; color: var(--fg); font-size: .98rem; }
.agenda ol { list-style: none; margin: .5rem 0; padding: 0; } .agenda li { display: grid; grid-template-columns: 1.3rem 1fr; gap: .4rem; padding: .45rem 0; border-top: 1px solid var(--line); line-height: 1.4; }
.agenda li i { font-style: normal; font-weight: 700; } .agenda li .src { display: block; margin: .15rem 0 0; } .ag-what { display: block; color: var(--muted); font-size: .9rem; }
.ag-gotova > span > b, .ag-gotova { color: var(--muted); } .ag-gotova i { color: var(--za); } .ag-u_toku i { color: var(--protiv); } .ag-u_toku, .ag-na_redu { font-weight: 600; } .agenda li .src, .ag-what { font-weight: 400; }
.steps-sec { order: 4; } .steps-sec h2 { margin-bottom: .2rem; }
.steps { list-style: none; margin: .9rem 0 0; padding: 0; }
.steps li { display: grid; grid-template-columns: 2.9rem 1.1rem 1fr; gap: 0 .55rem; position: relative; padding: 0 0 1.05rem; line-height: 1.45; }
.steps li::before { content: ""; position: absolute; left: calc(2.9rem + .55rem + .55rem - 1px); top: 1.1rem; bottom: -.3rem; width: 2px; background: var(--line); }
.steps li:last-child::before { display: none; } .steps li:last-child { padding-bottom: .2rem; }
.steps .time { color: var(--muted); font-variant-numeric: tabular-nums; font-size: .9rem; padding-top: .08rem; text-align: right; }
.steps li > i, .st-key i { box-sizing: border-box; width: .7rem; height: .7rem; border-radius: 50%; border: 2px solid var(--fg); background: var(--bg); }
.steps li > i { margin: .38rem auto 0; position: relative; z-index: 1; } .steps li.st-sajt > i { background: var(--fg); }
.steps .time small { display: block; font-size: .75rem; line-height: 1.1; letter-spacing: .02em; } .st-off { font: 700 .75rem/1 system-ui, sans-serif; letter-spacing: .06em; text-transform: uppercase; border: 1px solid var(--fg); border-radius: 4px; padding: .12rem .32rem; margin-right: .25rem; vertical-align: .12em; white-space: nowrap; }
.st-floor { color: var(--muted); font-size: .95rem; } .st-floor b { color: var(--fg); font-weight: 600; } .steps li.st-rec { padding-bottom: .7rem; } .steps li.st-rec > i { width: .5rem; height: .5rem; margin-top: .48rem; border-color: var(--muted); }
.steps p { margin: 0; } .st-title { font-weight: 650; } .st-what { color: var(--muted); font-size: .92rem; margin-top: .1rem; }
.st-text { max-width: 42rem; font-size: .97rem; } .st-src { font-size: .8rem; color: var(--muted); margin-top: .2rem; } .st-src a { color: inherit; }
.st-key { display: flex; flex-wrap: wrap; gap: .3rem 1.2rem; margin: .9rem 0 0; padding-top: .6rem; border-top: 1px solid var(--line); font-size: .8rem; color: var(--muted); }
.st-key span { display: inline-flex; align-items: baseline; gap: .4rem; } .st-key i { flex: none; width: .6rem; height: .6rem; border-color: var(--muted); align-self: center; } .st-key .st-sajt i { background: var(--muted); }
.steps-sec { border: 1px solid var(--line); border-radius: 10px; padding: 1rem 1.1rem; margin-top: 1rem; } .steps-sec h2 { margin-top: 0; }
.steps-sec details { margin-top: .2rem; } .steps-sec details[open] summary { margin-bottom: .2rem; } .steps-sec summary { cursor: pointer; color: var(--muted); font-size: .9rem; }
.said-sec:empty { display: none; } .said-sec .said-now { border: 1px solid var(--line); border-radius: 8px; padding: .8rem 1rem; }
.pz-next { margin: 0 0 .9rem; }
/* The top of the page (19 Nov 2026, the maintainer's request: the old line of text was cramped): what the page is in
   a few words, and one clear way to the site. Then the newest notice, then the broadcast. */
.hero { display: flex; flex-wrap: wrap; gap: .9rem 1.5rem; align-items: center; justify-content: space-between; margin: 1.1rem 0 0; padding: 1rem 1.1rem; border-radius: 12px; background: color-mix(in srgb, var(--fg) 5%, transparent); }
.hero > div { flex: 1 1 16rem; min-width: 0; }
.hero h1 { font-family: var(--serif); font-size: clamp(1.45rem, 5vw, 1.9rem); line-height: 1.15; letter-spacing: -.015em; text-transform: none; margin: 0 0 .3rem; }
.hero-sub { margin: 0; color: var(--muted); font-size: .98rem; line-height: 1.4; }
.hero-cta { flex: 0 1 auto; display: flex; flex-direction: column; gap: .1rem; padding: .6rem 1rem; border-radius: 10px; background: var(--fg); color: var(--bg); text-decoration: none; line-height: 1.25; }
.hero-cta:hover { color: var(--bg); opacity: .88; } .hero-cta span { font-size: .82rem; opacity: .8; } .hero-cta b { font-size: 1.05rem; }
@media (max-width: 520px) { .hero { padding: .9rem; } .hero-cta { flex: 1 1 100%; } .hero-cta b { white-space: nowrap; } }
main > .player { margin-top: 1rem; }
.lead { font-size: .92rem; margin: 0 0 .4rem; max-width: 40rem; }
.sp-head { display: flex; gap: 1rem; align-items: flex-start; margin: 1.2rem 0 0; }
.sp-head > div { min-width: 0; flex: 1; }
.ph { flex: none; width: 72px; height: 96px; object-fit: cover; border-radius: 6px; background: var(--line); }
.sp .now { margin: 0 0 .2rem; } .sp .side { margin: .1rem 0 .2rem; font-size: 1.05rem; }
.sp .meta { margin-left: 0; }
.who { font-size: clamp(1.9rem, 7vw, 3.2rem); overflow-wrap: anywhere; }
.dot { align-self: center; animation: pulse 1.6s ease-in-out infinite; }
@keyframes pulse { 50% { opacity: .35; } }
@media (prefers-reduced-motion: reduce) { .dot { animation: none; } }
.clock { margin: .3rem 0 0; color: var(--muted); font-size: .95rem; }
.clk { font-family: var(--serif); font-size: 1.9rem; line-height: 1; color: var(--fg); font-variant-numeric: tabular-nums; margin-right: .5rem; }
.nums { margin: 0 0 .7rem; display: grid; gap: .35rem; }
.nums div { display: grid; grid-template-columns: 5.4rem 1fr; gap: .6rem; align-items: baseline; }
.nums dt, .src { font-size: .76rem; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }
.nums dd { margin: 0; font-weight: 600; }
.rot-w { display: flex; gap: .8rem; align-items: flex-start; justify-content: space-between; border-top: 1px solid var(--line);
  padding-top: .7rem; margin-bottom: .8rem; min-height: 5.2rem; }
.rot { list-style: none; margin: 0; padding: 0; flex: 1; color: var(--fg); font-size: 1rem; }
.o .rot { padding-left: 0; color: var(--fg); font-size: 1rem; margin: 0; }
.rot li { display: none; } .rot:not(.js) li:first-child, .rot.js li.on { display: block; }
.src { display: block; margin-bottom: .15rem; }
.rot-next { flex: none; border: 1px solid var(--line); background: none; color: var(--muted); border-radius: 999px;
  padding: .35rem .8rem; min-height: 2rem; font: inherit; font-size: .85rem; cursor: pointer; font-variant-numeric: tabular-nums; }
.acts { display: flex; flex-wrap: wrap; gap: .5rem; margin: 0; }
.share-now { font: inherit; font-weight: 600; padding: .45rem .8rem; border-radius: 6px; border: 1px solid var(--fg);
  background: none; color: var(--fg); cursor: pointer; }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(7.5rem, 1fr)); gap: .6rem; margin: .4rem 0 1.2rem; }
.tiles div { border: 1px solid var(--line); border-radius: 8px; padding: .6rem .8rem; }
.tiles dd { margin: 0; font-family: var(--serif); font-weight: 700; font-size: 1.5rem; line-height: 1.2; font-variant-numeric: tabular-nums; }
.tiles dt { color: var(--muted); font-size: .82rem; }
.said-now { border-top: 1px solid var(--line); margin: .9rem 0; padding-top: .7rem; }
.said-now p { margin: .2rem 0; } .said-now > p:nth-child(2) { font-size: 1rem; line-height: 1.5; }
a.said { margin-left: .3rem; }
.said-page article { border-top: 1px solid var(--line); padding: .9rem 0; } .said-page article:target { background: color-mix(in srgb, var(--za) 8%, transparent); }
.said-page h2 { font-size: 1.15rem; margin: 0 0 .3rem; } .said-page h2 .meta { font-family: system-ui, sans-serif; font-weight: 400; font-size: .85rem; }
.said-page article p { margin: 0; max-width: 44rem; }
.st-go { margin: 0 0 1.2rem; }
.st { position: fixed; inset: 0; z-index: 50; background: #0b0d12; color: #f4f4f1; display: flex; flex-direction: column; }
.st-bar { display: flex; gap: 4px; padding: 12px 14px 0; } .st-bar i { flex: 1; height: 3px; border-radius: 2px; background: rgba(255,255,255,.25); overflow: hidden; }
.st-bar i b { display: block; height: 100%; width: 0; background: #fff; } .st-bar i.done b { width: 100%; }
.st-bar i.on b { animation: st-run var(--st-t, 6s) linear forwards; } @keyframes st-run { to { width: 100%; } }
@media (prefers-reduced-motion: reduce) { .st-bar i.on b { animation: none; width: 100%; } }
/* Said to a screen reader, not shown: who has the floor now (the page's part is replaced without a word). */
.sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); margin: 0; }
.st-x { position: absolute; top: 22px; right: 10px; z-index: 2; background: none; border: 0; color: #fff; font-size: 1.8rem; line-height: 1; padding: .3rem .6rem; cursor: pointer; }
.st-stage { flex: 1; display: grid; place-items: center; padding: 1.5rem; }
.st-c { width: 100%; max-width: 26rem; } .st-c a { color: #fff; }
.st-k { text-transform: uppercase; letter-spacing: .08em; font-size: .8rem; font-weight: 700; color: #ffb37a; margin: 0 0 1rem; }
.st-big { font-family: var(--serif); font-weight: 700; font-size: clamp(3rem, 16vw, 5rem); line-height: 1; margin: .2rem 0 .6rem; } .st-big small { font-size: 40%; }
.st-name { font-family: var(--serif); font-weight: 700; font-size: clamp(1.6rem, 7vw, 2.4rem); line-height: 1.15; margin: 0 0 .6rem; }
.st-s { color: #c9ccd3; font-size: 1.05rem; line-height: 1.45; margin: 0 0 .8rem; } .st-row { font-size: 1.1rem; margin: 1rem 0 0; }
.st .lk { font-size: 1rem; } .st .lk em { color: #c9ccd3; } .st .lk i { border-color: transparent; } .st .lb { height: 2rem; }
.st .cta { display: inline-block; background: #fff; color: #111; padding: .6rem 1rem; border-radius: 6px; font-weight: 700; text-decoration: none; }
.st-hint { text-align: center; color: #8d919b; font-size: .8rem; margin: 0; padding: 0 0 1rem; }
.hl { font-family: var(--serif, Georgia, serif); font-size: 1.25rem; line-height: 1.35; font-weight: 700; margin: .2rem 0 1rem; max-width: 40rem; }
.pz .hl { margin: .3rem 0 .6rem; } .pz-top { margin: 0 0 .9rem; padding-left: 1.3rem; } .pz-top span { color: var(--muted); margin-left: .4rem; }
.lb { display: flex; height: 1.5rem; border-radius: 4px; overflow: hidden; gap: 2px; }
.lb i { display: block; min-width: 3px; }
.l0 { background: var(--fg); } .l1 { background: color-mix(in srgb, var(--fg) 62%, var(--bg)); }
.l2 { background: color-mix(in srgb, var(--fg) 38%, var(--bg)); } .l3 { background: color-mix(in srgb, var(--fg) 22%, var(--bg)); }
.l4 { background: color-mix(in srgb, var(--fg) 12%, var(--bg)); }
.c-av, .tb i.c-av { background: var(--c-av); } .c-sl, .tb i.c-sl { background: var(--c-sl); } .c-mn, .tb i.c-mn { background: var(--c-mn); }
.tb i.lx { background: repeating-linear-gradient(135deg, color-mix(in srgb, var(--fg) 45%, var(--bg)) 0 2px, var(--bg) 2px 5px); }
.lx { background: repeating-linear-gradient(135deg, color-mix(in srgb, var(--fg) 45%, var(--bg)) 0 2px, var(--bg) 2px 5px); }
.lk { list-style: none; margin: .6rem 0 0; padding: 0; display: grid; gap: .3rem; font-size: .92rem; }
.lk li { display: grid; grid-template-columns: 1rem 1fr auto 3rem; gap: .6rem; align-items: center; }
.lk i { width: 1rem; height: 1rem; border-radius: 3px; border: 1px solid var(--line); }
.lk b, .lk em { font-variant-numeric: tabular-nums; white-space: nowrap; } .lk em { font-style: normal; color: var(--muted); text-align: right; }
.tl { position: relative; height: 2rem; background: color-mix(in srgb, var(--fg) 5%, transparent); border-radius: 4px; overflow: hidden; }
.tl a { position: absolute; top: 5px; bottom: 5px; min-width: 2px; }
.tl a.on { top: 0; bottom: 0; min-width: 5px; box-shadow: inset 0 0 0 2px var(--fg); z-index: 1; }
.tl a:hover { opacity: .7; }
.tl-ax { position: relative; height: 1.2rem; font-size: .75rem; color: var(--muted); font-variant-numeric: tabular-nums; }
.tl-ax span { position: absolute; top: .15rem; transform: translateX(-50%); } .tl-ax span:first-child { transform: none; }
.turns li:target { background: color-mix(in srgb, var(--za) 12%, transparent); }
/* The next sitting, counted down (between sittings), and the way onto the phone's home screen (20 Nov 2026). */
.nx { margin: .9rem 0 0; padding: .9rem 1.1rem; border: 2px solid var(--fg); border-radius: 12px; }
.nx p { margin: 0; } .nx .src { margin-bottom: .2rem; }
.nx-big { font-family: var(--serif); font-weight: 700; font-size: clamp(1.7rem, 7vw, 2.4rem); line-height: 1.15; font-variant-numeric: tabular-nums; }
.nx-big span { display: block; font-family: system-ui, sans-serif; font-weight: 400; font-size: .95rem; color: var(--muted); }
.nx-when { font-weight: 600; margin-top: .3rem !important; } .nx-title { color: var(--muted); font-size: .95rem; margin: .1rem 0 .6rem !important; }
.nx-ag { margin: 0 0 .6rem; } .nx-ag summary { cursor: pointer; font-weight: 600; } .nx-ag ol { margin: .4rem 0 0; padding-left: 1.4rem; line-height: 1.4; } .nx-ag li { margin: .2rem 0; }
.add-home { order: 3; margin: 1rem 0 0; } .add-home p { margin: .3rem 0; }
.nt-off { font: inherit; background: none; border: 0; padding: 0; color: var(--fg); text-decoration: underline; cursor: pointer; }
.add-home[hidden], .add-home [hidden] { display: none; }
.add-btn { font: inherit; font-weight: 600; padding: .45rem .8rem; border-radius: 6px; border: 1px solid var(--fg); background: none; color: var(--fg); cursor: pointer; }
/* A phone (86% of the visits): the head made short, so the broadcast is in the first screen (20 Nov 2026). */
@media (max-width: 520px) {
  .top { padding: .7rem 16px .5rem; } main { padding: 0 16px 3rem; }
  .hero { margin-top: .6rem; padding: .6rem .75rem; gap: .5rem; }
  .hero h1 { font-size: 1.2rem; margin: 0; } .hero-sub { display: none; }
  .hero-cta { flex: 1 1 100%; flex-direction: row; flex-wrap: wrap; justify-content: space-between; align-items: baseline; gap: 0 .6rem; padding: .4rem .75rem; }
  .hero-cta span { font-size: .78rem; } .hero-cta b { font-size: .95rem; }
  .news { margin-top: .6rem; padding: .5rem .7rem; font-size: .88rem; line-height: 1.4; }
  main > .player { margin-top: .6rem; }
}
""" + _shared("mikrofon.css")

SCRIPT = _shared("mikrofon.js") + """
(function () {
  var base = document.body.getAttribute("data-base");
  // Every five seconds, as the caption is read once a segment (five seconds); not while the tab is out of sight,
  // and once at once when it comes back. Each ask is a request through Cloudflare and to the computer it runs on.
  // The clock beside the speaker: the seconds the page was given, plus those passed since; never back within a turn.
  var got = Date.now(), last = { od: "", s: 0 };
  function hms(s) { var h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), x = s % 60;
    return (h ? h + ":" + (m < 10 ? "0" : "") : "") + m + ":" + (x < 10 ? "0" : "") + x; }
  function seconds(c) {
    var od = c.getAttribute("data-od"), s = (+c.getAttribute("data-sek")) + Math.round((Date.now() - got) / 1000);
    if (last.od === od && last.s > s) s = last.s;
    last = { od: od, s: s };
    return s;
  }
  // One line about the speaker at a time, the next every fifteen seconds or on a tap; from the first for each speaker.
  var turn = { od: "", t: 0, skip: 0 };
  function rotate() {
    var u = document.querySelector(".rot"), c = document.querySelector(".clk");
    if (!u) return;
    var od = c ? c.getAttribute("data-od") : "";
    if (turn.od !== od) turn = { od: od, t: Date.now(), skip: 0 };
    var n = u.children.length, k = (Math.floor((Date.now() - turn.t) / 15000) + turn.skip) % n;
    u.classList.add("js");
    for (var i = 0; i < n; i++) u.children[i].classList.toggle("on", i === k);
    var no = document.querySelector(".rot-n");
    if (no) no.textContent = (k + 1) + "/" + n;
  }
  // The next sitting's countdown, written as page.left writes it.
  function until() {
    var b = document.querySelector(".nx-in");
    if (!b) return;
    var w = function (k) { return b.getAttribute("data-" + k); };
    var s = Math.floor(+w("at") - Date.now() / 1000), out;
    if (s <= 0) { out = w("soon"); if (b.previousElementSibling) b.previousElementSibling.hidden = true; }
    else {
      var d = Math.floor(s / 86400), h = Math.floor(s % 86400 / 3600), m = Math.floor(s % 3600 / 60);
      out = d ? d + " " + (d % 10 === 1 && d % 100 !== 11 ? w("d1") : w("dn")) + (h ? " " + h + " " + w("h") : "")
        : h ? h + " " + w("h") + " " + m + " " + w("m") : Math.max(1, m) + " " + w("m");
    }
    if (b.textContent !== out) b.textContent = out;
  }
  function tick() {
    var d = document.getElementById("deo"), c = document.querySelector("#checked span"), k = document.querySelector(".clk");
    if (d && c) c.textContent = Math.max(0, Math.round(Date.now() / 1000 - (+d.getAttribute("data-checked"))));
    if (k) k.textContent = hms(seconds(k));
    rotate();
    until();
  }
  // Every five seconds, as the caption is read once a segment (five seconds); not while the tab is out of sight,
  // and once at once when it comes back. Each ask is a request through Cloudflare and to the computer it runs on.
  var heard = null;
  function said() {
    var w = document.querySelector("#deo .who"), side = document.querySelector("#deo .sp .side"), line = document.getElementById("ko");
    var now = w ? w.textContent.trim() : "";
    if (heard !== null && now && now !== heard && line) line.textContent = now + (side ? ", " + side.textContent.trim() : "");
    heard = now;
  }
  function load() {
    if (document.hidden) return;
    fetch(base + "deo", { cache: "no-store" }).then(function (r) { return r.ok ? r.text() : null; })
      .then(function (html) {
        if (!html) return;
        // what the reader opened (the agenda, the folded steps) stays open when the part is replaced
        var open = [].map.call(document.querySelectorAll("#deo details[open]"), function (d) { return d.id || d.parentNode.className; });
        // the keyboard's place too: the same kind of thing, the same one in order, has the focus again
        var deo = document.getElementById("deo"), f = document.activeElement, keep = null;
        if (f && deo.contains(f)) {
          var sel = f.tagName.toLowerCase() + (typeof f.className === "string" && f.className.trim() ? "." + f.className.trim().split(" ").filter(Boolean).join(".") : "");
          keep = [sel, [].indexOf.call(deo.querySelectorAll(sel), f)];
        }
        deo.outerHTML = html;
        [].forEach.call(document.querySelectorAll("#deo details"), function (d) { if (open.indexOf(d.id || d.parentNode.className) >= 0) d.open = true; });
        if (keep) { var again = document.querySelectorAll("#deo " + keep[0])[keep[1]]; if (again) again.focus({ preventScroll: true }); }
        got = Date.now(); tick(); said();
      })
      .catch(function () {});
  }
  setInterval(load, 5000); setInterval(tick, 1000); tick(); said();
  document.addEventListener("visibilitychange", function () { if (!document.hidden) load(); });

  // "Podeli ovaj trenutak": a picture drawn here, in the browser, of who speaks and for how long, with the page's
  // address; handed to the share sheet where there is one, else saved, with the text copied.
  function fit(g, text, weight, size, family, width) {
    do { g.font = weight + " " + size + "px " + family; size -= 4; } while (g.measureText(text).width > width && size > 24);
  }
  function picture(b, minutes) {
    var W = 1200, H = 675, P = 64, c = document.createElement("canvas"), g = c.getContext("2d");
    var serif = '"Literata", Georgia, serif', sans = 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';
    var d = function (k) { return b.getAttribute("data-" + k) || ""; };
    c.width = W; c.height = H;
    g.fillStyle = "#fff"; g.fillRect(0, 0, W, H);
    g.textBaseline = "alphabetic";
    var brand = document.querySelector(".brand"), x = P;
    g.font = "700 40px " + serif;
    (brand ? brand.textContent : "Za ili Protiv").split(" ").forEach(function (w, i) {
      g.fillStyle = i === 0 ? "#1f5fa8" : i === 2 ? "#c2410c" : "#111";
      g.fillText(w, x, 84); x += g.measureText(w + " ").width;
    });
    g.fillStyle = "#555"; g.font = "400 26px " + sans; g.textAlign = "right";
    g.fillText(location.host, W - P, 82); g.textAlign = "left";
    g.fillStyle = "#111"; g.fillRect(P, 108, W - 2 * P, 4);
    g.fillStyle = "#c2410c"; g.beginPath(); g.arc(P + 11, 166, 11, 0, 7); g.fill();
    g.fillStyle = "#555"; g.font = "700 26px " + sans; g.fillText(d("head").toUpperCase(), P + 36, 175);
    g.fillStyle = "#111"; fit(g, d("name"), 700, 104, serif, W - 2 * P); g.fillText(d("name"), P, 290);
    g.fillStyle = "#555"; fit(g, d("side"), 400, 36, sans, W - 2 * P); g.fillText(d("side"), P, 344);
    g.fillStyle = "#555"; g.font = "400 34px " + sans; g.fillText(d("already"), P, 452);
    var w0 = g.measureText(d("already") + " ").width;
    g.fillStyle = "#111"; g.font = "700 150px " + serif; g.fillText(String(minutes), P + w0 + 6, 480);
    var w1 = g.measureText(String(minutes)).width;
    g.font = "700 56px " + serif; g.fillText(d("min"), P + w0 + w1 + 26, 480);
    g.fillStyle = "#111"; fit(g, d("line"), 600, 34, sans, W - 2 * P); g.fillText(d("line"), P, 548);
    g.fillStyle = "#555"; g.font = "400 24px " + sans;
    g.fillText(d("when") + " · " + d("note"), P, 622);
    return c;
  }
  var story = null;
  function stories() {
    var data = document.querySelector(".st-data");
    if (!data || story) return;
    var cards = [].slice.call(data.children).map(function (c) { return c.outerHTML; }), i = -1, timer = null;
    var calm = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
    var el = document.createElement("div");
    el.className = "st"; el.setAttribute("role", "dialog"); el.setAttribute("aria-modal", "true");
    el.innerHTML = '<div class="st-bar">' + cards.map(function () { return "<i><b></b></i>"; }).join("") + '</div>' +
      '<button type="button" class="st-x" aria-label="' + data.getAttribute("data-close") + '">×</button>' +
      '<div class="st-stage"></div><p class="st-hint">' + data.getAttribute("data-hint") + '</p>';
    document.body.appendChild(el);
    var stage = el.querySelector(".st-stage"), bars = el.querySelectorAll(".st-bar i");
    function close() {
      clearTimeout(timer); el.remove(); story = null; document.removeEventListener("keydown", key);
      var back = document.querySelector(".st-open"); if (back) back.focus({ preventScroll: true });
    }
    function show(k) {
      if (k >= cards.length) { close(); return; }
      i = Math.max(0, k);
      stage.innerHTML = cards[i];
      for (var j = 0; j < bars.length; j++) { bars[j].className = j < i ? "done" : ""; }
      void bars[i].offsetWidth; bars[i].className = "on";
      clearTimeout(timer);
      if (!calm && i < cards.length - 1) timer = setTimeout(function () { show(i + 1); }, 6000);
    }
    function key(e) { if (e.key === "Escape") close(); else if (e.key === "ArrowRight") show(i + 1); else if (e.key === "ArrowLeft") show(i - 1); }
    el.addEventListener("click", function (e) {
      if (e.target.closest(".st-x")) { close(); return; }
      if (e.target.closest("a")) return;
      show(e.clientX < window.innerWidth / 3 ? i - 1 : i + 1);
    });
    document.addEventListener("keydown", key);
    story = el; show(0); el.querySelector(".st-x").focus();
  }
  function shareDay(b) {
    var url = location.origin + location.pathname, text = b.getAttribute("data-text") + " " + url;
    var said = b.parentNode.parentNode.querySelector(".share-said");
    var plain = function () {
      if (navigator.share) { navigator.share({ text: text }).catch(function () {}); return; }
      if (navigator.clipboard) navigator.clipboard.writeText(text).catch(function () {});
      if (said) { said.textContent = b.getAttribute("data-done"); said.hidden = false; }
    };
    fetch(b.getAttribute("data-src") + "?" + Date.now()).then(function (r) { if (!r.ok) throw 0; return r.blob(); }).then(function (blob) {
      var file = new File([blob], "ko-je-koliko-govorio.png", { type: "image/png" });
      if (navigator.canShare && navigator.canShare({ files: [file] })) {
        navigator.share({ files: [file], text: text }).catch(function () {}); return;
      }
      var a = document.createElement("a");
      a.href = URL.createObjectURL(file); a.download = file.name; document.body.appendChild(a); a.click(); a.remove();
      if (navigator.clipboard) navigator.clipboard.writeText(text).catch(function () {});
      if (said) { said.textContent = b.getAttribute("data-done"); said.hidden = false; }
    }).catch(plain);
  }
  document.addEventListener("click", function (e) {
    var t = e.target.closest ? e.target : null;
    if (t && t.closest(".rot-next, .rot")) { turn.skip++; rotate(); return; }
    var b = t && t.closest(".share-now");
    if (!b) return;
    if (b.classList.contains("st-open")) { stories(); return; }
    if (b.classList.contains("share-day")) { shareDay(b); return; }
    var k = document.querySelector(".clk"), minutes = Math.max(1, Math.floor((k ? seconds(k) : 0) / 60));
    var url = location.origin + location.pathname;
    var text = b.getAttribute("data-text").replace("%1", b.getAttribute("data-name")).replace("%2", minutes)
      .replace("%3", b.getAttribute("data-line")) + " " + url;
    var said = document.querySelector(".share-said");
    try {
      var c = picture(b, minutes), bin = atob(c.toDataURL("image/png").split(",")[1]), bytes = new Uint8Array(bin.length);
      for (var i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
      var file = new File([bytes], "ko-sada-govori.png", { type: "image/png" });
      if (navigator.canShare && navigator.canShare({ files: [file] })) {
        navigator.share({ files: [file], text: text }).catch(function () {});
        return;
      }
      if (navigator.share) { navigator.share({ text: text }).catch(function () {}); return; }
      var a = document.createElement("a");
      a.href = URL.createObjectURL(file); a.download = file.name; document.body.appendChild(a); a.click(); a.remove();
    } catch (err) { if (navigator.share) { navigator.share({ text: text }).catch(function () {}); return; } }
    if (navigator.clipboard) navigator.clipboard.writeText(text).catch(function () {});
    if (said) { said.textContent = b.getAttribute("data-done"); said.hidden = false; }
  });
})();
// More of the page's uses for the same counter as the broadcast's ▶ (mikrofon.js, "mikrofon.pusti"): a sum per day,
// nothing with it, each at most once per page opened, so every count is "pages where this happened". Time out of
// sight is not counted.
(function () {
  var api = (document.body.getAttribute("data-api") || "").replace(/\\/$/, "");
  if (!/^https:\\/\\//.test(api) || !window.fetch) return;
  var sent = {};
  function use(what) {
    if (sent[what]) return;
    sent[what] = 1;
    try {
      fetch(api + "/e", { method: "POST", headers: { "content-type": "text/plain" }, keepalive: true,
                          body: JSON.stringify({ e: "mikrofon." + what }) }).catch(function () {});
    } catch (err) {}
  }
  use("otvori");
  var seen = 0, marks = [[60, "1min"], [300, "5min"], [900, "15min"], [1800, "30min"]];
  var clock = setInterval(function () {
    if (document.hidden) return;
    seen++;
    for (var i = 0; i < marks.length; i++) if (seen >= marks[i][0]) use(marks[i][1]);
    if (seen >= 1800) clearInterval(clock);
  }, 1000);
  document.addEventListener("click", function (e) {
    var t = e.target.closest ? e.target : null;
    if (!t) return;
    if (t.closest(".play:not(.facade), .part")) use("snimak");
    else if (t.closest("#dnevni-red > summary")) use("tacke");
    else if (t.closest("#nx-ag > summary")) use("sledeca");
    else if (t.closest(".rot-next, .rot")) use("redovi");
    else if (t.closest(".st-open")) use("kartice");
    else if (t.closest(".share-day")) use("dan");
    else if (t.closest(".share-now")) use("podeli");
    var a = t.closest("a[href]");
    if (a && a.hostname === "zailiprotiv.rs") use("sajt");
  }, true);
  window.mikrofonUse = use;
})();
// "Ne propustite sednicu": the page on the phone's home screen, and a notification when a sitting's broadcast begins.
// Home screen (20 Nov 2026): opened from there is counted; elsewhere the browser's own offer to add the page is shown
// as our button when the browser makes one (Chrome, Edge, Samsung), and on an iPhone, which makes none, a line saying
// where Safari keeps it. Nothing is installed but the page's address and icon.
// Notifications (20 Nov 2026): on a press, the browser is asked for leave, the page's service worker (/sw.js) is
// registered and the browser's push address sent to the site's counter; "Isključi" takes it back there too.
(function () {
  var use = function (w) { if (window.mikrofonUse) window.mikrofonUse(w); };
  var box = document.querySelector(".add-home");
  if (!box) return;
  var part = function (k) { return box.querySelector("." + k); };
  function show(k, on) { var el = part(k); if (el) el.hidden = !on; box.hidden = ![].some.call(box.children, function (c) { return !c.hidden; }); }
  var home = (window.matchMedia && matchMedia("(display-mode: standalone)").matches) || navigator.standalone;
  if (home) use("ekran");
  else {
    var ask = null;
    window.addEventListener("beforeinstallprompt", function (e) { e.preventDefault(); ask = e; show("add", true); });
    window.addEventListener("appinstalled", function () { show("add", false); use("dodato"); });
    if (/iPhone|iPad|iPod/.test(navigator.userAgent)) show("add-ios", true);
    part("add-go").addEventListener("click", function () {
      if (!ask) return;
      use("dodaj"); ask.prompt();
      ask.userChoice.then(function () { ask = null; show("add", false); }).catch(function () {});
    });
  }
  var key = box.getAttribute("data-key") || "", api = (document.body.getAttribute("data-api") || "").replace(/\\/$/, "");
  var cir = document.documentElement.lang === "sr-Cyrl";
  if (!key || !/^https:\\/\\//.test(api) || !("serviceWorker" in navigator) || !("PushManager" in window) || !("Notification" in window)) return;
  function bytes(s) {
    var b = atob(s.replace(/-/g, "+").replace(/_/g, "/")), out = new Uint8Array(b.length);
    for (var i = 0; i < b.length; i++) out[i] = b.charCodeAt(i);
    return out;
  }
  function tell(path, sub) {
    return fetch(api + path, { method: "POST", headers: { "content-type": "text/plain" },
                               body: JSON.stringify({ endpoint: sub.endpoint, cir: cir }) })
      .then(function (r) { if (!r.ok) throw new Error("counter " + r.status); });
  }
  function state(on) { show("nt", !on); show("nt-done", on); show("nt-note", true); show("nt-err", false); }
  function failed() { show("nt-err", true); }
  if (Notification.permission === "denied") { show("nt-blocked", true); return; }
  navigator.serviceWorker.getRegistration("/").then(function (r) { return r ? r.pushManager.getSubscription() : null; })
    .then(function (s) { state(!!s); }).catch(function () { state(false); });
  part("nt-on").addEventListener("click", function () {
    Notification.requestPermission().then(function (p) {
      if (p !== "granted") { show("nt", false); show("nt-blocked", p === "denied"); return; }
      return navigator.serviceWorker.register("/sw.js" + (cir ? "?j=cir" : ""), { scope: "/" })
        .then(function () { return navigator.serviceWorker.ready; })
        .then(function (r) { return r.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: bytes(key) }); })
        .then(function (s) { return tell("/p", s); })
        .then(function () { state(true); use("obavesti"); });
    }).catch(failed);
  });
  part("nt-off").addEventListener("click", function () {
    navigator.serviceWorker.getRegistration("/").then(function (r) { return r ? r.pushManager.getSubscription() : null; })
      .then(function (s) { if (!s) return; return tell("/p/odjava", s).then(function () { return s.unsubscribe(); }); })
      .then(function () { state(false); use("odjavi"); }).catch(failed);
  });
})();
"""


def admin_page(key: str, push_key: str) -> str:
    """/upozorenja?k=…: the maintainer turns on, on this device, a notification when this service is down while a
    sitting is on (the counter's watch, worker/). Shown to the key only; the device's push address goes to the
    service, which hands it to the counter with its token."""
    k = json.dumps(key)
    return f"""<!doctype html>
<html lang="sr-Latn"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex">
<title>Upozorenja · Mikrofon</title><style>{CSS}</style></head>
<body><main><h1>Upozorenja za održavanje</h1>
<p class="lead">Ovaj uređaj dobija obaveštenje kad mikrofon.zailiprotiv.rs ne odgovara dve provere zaredom (oko pet minuta),
radnim danom od 7 do 20 h, dok Skupština na svom sajtu piše da je sednica u toku; i još jedno kad ponovo proradi.</p>
<p><button type="button" class="add-btn" id="on">Uključi na ovom uređaju</button>
<button type="button" class="add-btn" id="off">Isključi</button></p>
<p class="meta" id="said"></p><p><a href="/">← Ko sada govori</a></p></main>
<script>
(function () {{
  var key = {json.dumps(push_key)}, k = {k}, said = document.getElementById("said");
  function bytes(s) {{ var b = atob(s.replace(/-/g, "+").replace(/_/g, "/")), o = new Uint8Array(b.length);
    for (var i = 0; i < b.length; i++) o[i] = b.charCodeAt(i); return o; }}
  function tell(endpoint, on) {{
    return fetch("/upozorenja?k=" + encodeURIComponent(k), {{ method: "POST", headers: {{ "content-type": "application/json" }},
      body: JSON.stringify({{ endpoint: endpoint, on: on }}) }}).then(function (r) {{ if (!r.ok) throw new Error(r.status); }});
  }}
  document.getElementById("on").onclick = function () {{
    Notification.requestPermission().then(function (p) {{
      if (p !== "granted") throw new Error("dozvola: " + p);
      return navigator.serviceWorker.register("/sw.js", {{ scope: "/" }}).then(function () {{ return navigator.serviceWorker.ready; }});
    }}).then(function (r) {{ return r.pushManager.getSubscription().then(function (s) {{
      return s || r.pushManager.subscribe({{ userVisibleOnly: true, applicationServerKey: bytes(key) }}); }}); }})
      .then(function (s) {{ return tell(s.endpoint, true); }})
      .then(function () {{ said.textContent = "Uključeno na ovom uređaju."; }})
      .catch(function (e) {{ said.textContent = "Nije uspelo: " + e.message; }});
  }};
  document.getElementById("off").onclick = function () {{
    navigator.serviceWorker.getRegistration("/").then(function (r) {{ return r ? r.pushManager.getSubscription() : null; }})
      .then(function (s) {{ if (!s) throw new Error("ovaj uređaj nema prijavu"); return tell(s.endpoint, false); }})
      .then(function () {{ said.textContent = "Isključeno na ovom uređaju."; }})
      .catch(function (e) {{ said.textContent = "Nije uspelo: " + e.message; }});
  }};
}})();
</script></body></html>"""


def service_worker(cyr: bool, key: str, api: str) -> str:
    """The page's service worker (/sw.js; ?j=cir for the Cyrillic page): it only shows the notification when a push
    comes (a push carries nothing: the words are here) and opens the page on a tap. It handles no requests, so the
    page loads as it would without it."""
    words = json.dumps({"title": _t("nt_title", cyr), "body": _t("nt_body", cyr), "url": "/cir/" if cyr else "/",
                        "lang": "sr-Cyrl" if cyr else "sr-Latn", "key": key, "api": api.rstrip("/"), "cir": cyr,
                        "down": _t("al_down", cyr), "down_body": _t("al_down_body", cyr),
                        "back": _t("al_back", cyr), "back_body": _t("al_back_body", cyr)},
                       ensure_ascii=False)
    return f"""const W = {words};
self.addEventListener("install", function () {{ self.skipWaiting(); }});
self.addEventListener("activate", function (e) {{ e.waitUntil(self.clients.claim()); }});
// A push carries nothing: the counter says which it was (the sitting's, or for the maintainer's devices the watch's).
self.addEventListener("push", function (e) {{
  var which = self.registration.pushManager.getSubscription().then(function (s) {{
    return fetch(W.api + "/p/vrsta", {{ method: "POST", headers: {{ "content-type": "text/plain" }},
                                        body: JSON.stringify({{ endpoint: s ? s.endpoint : "" }}) }});
  }}).then(function (r) {{ return r.json(); }}).catch(function () {{ return {{ vrsta: "sednica" }}; }});
  e.waitUntil(which.then(function (k) {{
    var t = W.title, b = W.body, tag = "sednica", n = String(k.min || 0);
    if (k.vrsta === "kvar") {{ t = W.down; b = W.down_body.replace("%1", n); tag = "kvar"; }}
    else if (k.vrsta === "oporavak") {{ t = W.back; b = W.back_body.replace("%1", n); tag = "kvar"; }}
    return self.registration.showNotification(t, {{ body: b, icon: "/ikona-192.png", tag: tag, lang: W.lang,
                                                    data: {{ url: W.url }} }});
  }}));
}});
self.addEventListener("notificationclick", function (e) {{
  e.notification.close();
  e.waitUntil(self.clients.matchAll({{ type: "window", includeUncontrolled: true }}).then(function (list) {{
    for (var i = 0; i < list.length; i++) if (new URL(list[i].url).pathname === W.url && list[i].focus) return list[i].focus();
    return self.clients.openWindow(W.url);
  }}));
}});
// A push address the browser renewed: the counter is told the new one.
self.addEventListener("pushsubscriptionchange", function (e) {{
  if (!W.key || !W.api) return;
  var raw = atob(W.key.replace(/-/g, "+").replace(/_/g, "/")), key = new Uint8Array(raw.length);
  for (var i = 0; i < raw.length; i++) key[i] = raw.charCodeAt(i);
  e.waitUntil(self.registration.pushManager.subscribe({{ userVisibleOnly: true, applicationServerKey: key }})
    .then(function (s) {{ return fetch(W.api + "/p", {{ method: "POST", headers: {{ "content-type": "text/plain" }},
      body: JSON.stringify({{ endpoint: s.endpoint, cir: W.cir }}) }}); }}));
}});
"""


def og_text(snap: dict, *, cyr: bool, tz: ZoneInfo) -> tuple[str, str]:
    """The link preview's title and line: who is on and since when, or the sentence of the day, or what the page is."""
    cur = snap.get("sada")
    turns = (snap.get("danas") or []) + ([cur] if snap["stanje"] == "govori" and cur else [])
    line = headline(turns, cyr=cyr, when=_when(snap, cyr)) or _t("lead", cyr)
    if snap["stanje"] == "govori" and cur:
        side = cur.get("lista", "").strip("*") or cur.get("uloga") or cur.get("grupa") or ""
        title = _fill(_t("og_now", cyr), _name(given_first(cur["ime"]), cyr)) + (f" ({_name(side, cyr)})" if side else "")
        return title, _fill(_t("og_since", cyr), _clock(cur["od"], tz)) + ". " + line
    return _t("title", cyr), line


def _og(snap: dict, *, cyr: bool, url: str, tz: ZoneInfo) -> str:
    """What a pasted link shows (X, Viber, Facebook): the title and line above and the picture of the moment
    (`picture.py`). The picture's address changes with the turn, since some services keep a picture by its address."""
    if not url:
        return ""
    title, line = og_text(snap, cyr=cyr, tz=tz)
    cur = snap.get("sada") if snap["stanje"] == "govori" else None
    mark = int(cur["od"]) if cur else f'{snap.get("dan", "")}-{len(snap.get("danas") or [])}'
    img = f'{url}{"cir/" if cyr else ""}slika.png?v={mark}'
    e = escape
    return (f'<meta property="og:type" content="website"><meta property="og:url" content="{e(url + ("cir/" if cyr else ""))}">'
            f'<meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(line)}">'
            f'<meta property="og:image" content="{e(img)}"><meta property="og:image:width" content="1200">'
            f'<meta property="og:image:height" content="630"><meta name="twitter:card" content="summary_large_image">'
            f'<meta name="twitter:title" content="{e(title)}"><meta name="twitter:description" content="{e(line)}">'
            f'<meta name="twitter:image" content="{e(img)}">')


def _beacon(token: str) -> str:
    """Cloudflare Web Analytics, as on the site (base.html): the page counted, no cookies, nobody followed."""
    if not token or not token.isalnum():
        return ""
    return ('<script type="module" src="https://static.cloudflareinsights.com/beacon.min.js" '
            f'data-cf-beacon=\'{{"token": "{token}"}}\'></script>')


def player(snap: dict, *, cyr: bool, live: str = "", tz: ZoneInfo | None = None) -> str:
    """The player: while the broadcast is on, the YouTube video of it; between sittings, the last day's recording in
    the broadcaster's archive, from its first turn. Only a button until clicked (AGENTS.md, principle 5)."""
    t = lambda k: escape(_t(k, cyr))
    if snap["stanje"] != "nema_prenosa" and live:
        # A facade (19 Nov 2026, the maintainer's decision, in place of YouTube's player on the page from the start):
        # our own picture of the moment (picture.py) with ▶; a press loads the player, playing, and is counted.
        # Nothing from YouTube loads before it: the page opens faster on a phone.
        img = ("/cir" if cyr else "") + "/slika.png"
        button = (f'<button type="button" class="play facade" data-yt="{escape(live)}" data-t="0" data-e="mikrofon.pusti">'
                  f'<img src="{img}" alt="" width="1200" height="630" decoding="async">'
                  f'<span>▶ {t("play_live")}</span></button>')
        note = t("yt_live_note")
    else:
        parts = snap.get("datoteke") or []
        first = next((d for d in reversed(snap["danas"]) if d.get("datoteka") and d.get("snimak") is not None), None)
        if not parts and not first:
            return ""
        url, at = (parts[0]["url"], 0) if parts else (first["datoteka"], int(first["snimak"]))
        button = f'<button type="button" class="play" data-file="{escape(url)}" data-t="{at}">▶ {t("play_day")}</button>'
        note = t("archive_note")
        if len(parts) > 1:  # the day in several files: each one, by the hours it covers
            chips = "".join(f'<li><button type="button" class="part" data-file="{escape(p["url"])}" data-t="0">'
                            f'{t("part")} {i} · {_clock(p["od"], tz)}–{_clock(p["od"] + p["trajanje"], tz)}</button></li>'
                            for i, p in enumerate(parts, 1))
            return (f'<section class="player"><div class="screen" id="screen">{button}</div><ul class="parts">{chips}'
                    f'</ul><p class="meta">{note}</p></section>')
    return f'<section class="player"><div class="screen" id="screen">{button}</div><p class="meta">{note}</p></section>'


def waiting_part(w: dict | None, *, cyr: bool, site: str) -> str:
    """"Dok čekate": the site's quiz, one question at a time like the site's own quiz, and facts (pages_mikrofon),
    shown between sittings; the markup as the site's mikrofon page has it, for the same script and styles."""
    w = w or {}
    quiz, facts = w.get("kviz") or [], w.get("cinjenice") or []
    if not quiz and not facts:
        return ""
    t = lambda k: escape(_t(k, cyr))
    s = lambda text: escape(cyrillic(text) if cyr else text)
    home = site + ("cir/" if cyr else "")
    href = lambda h: escape(h if h.startswith("http") else home + h)
    n = len(quiz)
    out = [f'<h2>{t("wait_title")}</h2>']
    if quiz:
        marks = "".join(f'<button type="button" aria-label="{t("question")} {i}">{i}</button>' for i in range(1, n + 1))
        out.append(f'<p>{s(_t("quiz_lead", False).format(n=n))}</p><div class="mq" id="mq">'
                   f'<nav class="mq-strip" hidden aria-label="{t("questions")}">{marks}</nav><ol class="mq-list">')
        for i, q in enumerate(quiz, 1):
            opts = "".join(f'<button type="button" class="mq-o" data-i="{k}">{s(o)}</button>'
                           for k, o in enumerate(q["options"]))
            more = s(q["more"]) if q.get("more") else t("how_counted")
            out.append(f'<li class="mq-q" data-a="{int(q["answer"])}"><p class="mq-n">{t("question")} {i} {t("of")} {n}</p>'
                       f'<h3 class="mq-ask">{s(q["q"])}</h3><div class="mq-opts" role="group">{opts}</div>'
                       f'<details class="mq-why"><summary>{t("answer")}</summary>'
                       f'<p class="mq-verdict"><span class="mq-yes">{t("yes")}</span><span class="mq-no"><b>{t("no")} </b>'
                       f'{t("right_is")} {s(q["options"][int(q["answer"])])}.</span></p>'
                       f'<p>{s(q["why"])} <a href="{href(q["href"])}">{more}</a></p>'
                       f'<p class="mq-next"><span class="mq-auto"></span><button type="button" class="mq-go">'
                       f'{t("see_result" if i == n else "next_q")}</button></p></details></li>')
        out.append('</ol><section class="mq-end" hidden aria-live="polite">'
                   f'<p class="mq-n">{t("result")}</p><p class="mq-big"><span class="mq-got">0</span> {t("of")} {n}</p>'
                   + "".join(f'<p data-k="{k}" hidden>{t("q_" + k)}</p>' for k in ("all", "some", "none"))
                   + f'<p class="mq-acts"><button type="button" class="mq-share">{t("share")}</button> '
                     f'<button type="button" class="mq-again">{t("again")}</button></p>'
                     f'<p class="meta mq-shared" hidden>{t("copied")}</p>'
                     f'<p class="mq-share-text" hidden>{t("share_text")} <span class="mq-got">0</span> {t("of")} {n}. '
                     f'{t("share_end")}</p></section></div>')
    if facts:
        out.append(f'<h3>{t("know")}</h3><ul class="facts">')
        out += [f'<li><a href="{href(f["href"])}">{s(f["text"])}</a></li>' for f in facts]
        out.append(f'</ul><p class="meta">{t("facts_note")}</p>')
    return "\n".join(out)


def page(snap: dict, *, cyr: bool, site: str, tz: ZoneInfo, url: str = "", waiting: dict | None = None,
         live: str = "", analytics: str = "", api: str = "", push_key: str = "", version: str = "") -> str:
    t = lambda k: escape(_t(k, cyr))
    lang = "sr-Cyrl" if cyr else "sr-Latn"
    base = "/cir/" if cyr else "/"
    other = "/" if cyr else "/cir/"
    other_label = "Latinica" if cyr else TEXT["script"]
    home = site + ("cir/" if cyr else "")
    alt = (f'<link rel="canonical" href="{escape(url + base[1:])}">'
           f'<link rel="alternate" hreflang="sr-Latn" href="{escape(url)}">'
           f'<link rel="alternate" hreflang="sr-Cyrl" href="{escape(url + "cir/")}">') if url else ""
    brand = _brand(cyr)
    return f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{t("title")} · {"За или Против" if cyr else "Za ili Protiv"}</title>
<meta name="description" content="{t("lead")}">
{alt}
{_og(snap, cyr=cyr, url=url, tz=tz)}
<link rel="icon" type="image/svg+xml" href="{escape(site)}favicon.svg">
<link rel="manifest" href="{base}manifest.webmanifest">
<link rel="apple-touch-icon" href="/ikona-180.png">
<meta name="apple-mobile-web-app-title" content="{t("app_name")}">
<meta name="mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-capable" content="yes">
<meta name="theme-color" content="#ffffff" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#111318" media="(prefers-color-scheme: dark)">
<style>{CSS}</style>
</head>
<body data-base="{base}"{f' data-api="{escape(api)}"' if api.startswith("https://") else ""}>
<header class="top"><a class="brand" href="{escape(home)}">{brand}</a><span class="top-r"><a class="mic" href="{base}" title="{t("title")}">{MIC}</a><a href="{other}" hreflang="{"sr-Latn" if cyr else "sr-Cyrl"}">{other_label}</a></span></header>
<main>
<p class="sr" id="ko" aria-live="polite"></p>
<section class="hero">
<div><h1>{t("title")}</h1><p class="hero-sub">{t("hero_sub")}</p></div>
<a class="hero-cta" href="{escape(home)}"><span>{t("hero_cta")}</span><b>zailiprotiv.rs →</b></a>
</section>
{player(snap, cyr=cyr, live=live, tz=tz)}
{fragment(snap, cyr=cyr, site=site, tz=tz)}
<section class="add-home" hidden{f' data-key="{escape(push_key)}"' if push_key and api.startswith("https://") else ""}>
<p class="nt" hidden><button type="button" class="add-btn nt-on">{t("nt_on")}</button></p>
<p class="nt-done" hidden>{t("nt_done")} <button type="button" class="nt-off">{t("nt_off")}</button></p>
<p class="nt-blocked meta" hidden>{t("nt_blocked")}</p>
<p class="nt-err meta" hidden>{t("nt_err")}</p>
<p class="add" hidden><button type="button" class="add-btn add-go">{t("add_home")}</button> <span class="meta">{t("add_sub")}</span></p>
<p class="add-ios meta" hidden>{t("add_ios")}</p>
<p class="nt-note meta" hidden>{t("nt_note")}</p>
</section>
<p class="site-cta"><a href="{escape(home)}">{t("site_cta")}: zailiprotiv.rs →</a></p>
{waiting_part(waiting, cyr=cyr, site=site) if snap["stanje"] == "nema_prenosa" else ""}
<h2>{t("how_title")}</h2>
<p>{t("how")}</p>
<p><a href="{LIVE}">{t("live")}</a> · <a href="{escape(home)}">{t("home")}</a></p>
</main>
<footer>{"За или Против" if cyr else "Za ili Protiv"}: <a href="{escape(home)}">zailiprotiv.rs</a>{(". " + t("counted")) if analytics else ""}{(". " + t("uses_counted")) if api.startswith("https://") else ""}.{f' <span class="ver">{t("version")} {escape(version)}</span>' if version else ""}</footer>
<script>{SCRIPT}</script>
{_beacon(analytics)}
</body>
</html>
"""
