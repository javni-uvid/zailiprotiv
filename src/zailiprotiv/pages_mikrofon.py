"""The page shown at mikrofon.zailiprotiv.rs while "Ko sada govori" is down (17 Nov 2026).

"Ko sada govori" (live/) runs on the maintainer's computer behind a Cloudflare tunnel; when the computer is off,
Cloudflare answers with its own error. The edge worker (live/edge/) then shows this page instead, built with the
site: what the page is and why it is down, where the broadcast is, the next sitting convened, and a few facts from
the site's data, each by the same rule as on the page it links to, about no MP in particular.
"""
from __future__ import annotations

from zailiprotiv.config import LIVE

PAGE = "mikrofon.html"


def facts(*, stats: dict, numbers: list[dict], items: list[dict], most_against, totals: dict, active: str) -> list[dict]:
    """The facts, each {"text", "href"}: whole numbers from the site's own counts, in a fixed order."""
    out = [{"text": f"Na sajtu je {stats['all_laws']} zakona iz {len(numbers)} saziva, od 2012, i "
                    f"{stats['all_mps']} poslanika, svaki sa svakim svojim glasom.", "href": "zakoni.html"}]
    n = next((x for x in numbers if x["conv"]["n"] == active), None)
    if n:
        years = n["conv"]["years"]
        if n["with_bill"]:
            out.append({"text": f"U sazivu {years} po hitnom postupku predloženo je {n['urgent']} od "
                                f"{n['with_bill']} zakona.", "href": "brojke.html"})
        if n["days"] is not None:
            d = n["days"]
            out.append({"text": f"Polovina zakona u sazivu {years} usvojena je za {d} "
                                f"{'dan' if d % 10 == 1 and d % 100 != 11 else 'dana'} ili manje od podnošenja predloga.",
                        "href": "brojke.html"})
        if n["voted"]:
            out.append({"text": f"{n['unopposed']} od {n['voted']} zakona u sazivu {years} prošlo je bez ijednog "
                                f"glasa protiv.", "href": "brojke.html"})
    top = (most_against(items, 1) or [None])[0]
    if top:
        c = top["final"]["counts"]
        out.append({"text": f"Najveći udeo glasova protiv u sazivu {n['conv']['years'] if n else ''}: "
                            f"{top['law']['short']}, {c['za']} za i {c['protiv']} protiv.".replace("sazivu :", "sazivu:"),
                    "href": f"zakon/{top['slug']}.html"})
    t = next(iter(totals.values()), None)  # the newest convocation with notes read
    if t:
        out.append({"text": f"U {t['sittings']} sednica saziva {t['years']} čije su beleške pročitane: "
                            f"{t['speeches']} govora, {t['measures']} mera predsedavajućeg i {t['exchanges']} "
                            f"razmena replika.", "href": t["page"]})
        word, times = t["harsh_word"]
        if word:
            out.append({"text": f"Teška reč izgovorena najčešće u sazivu {t['years']}: „{word}“, u svim oblicima "
                                f"{times} puta.", "href": t["page_who"]})
    return out


def render(*, common: dict, env, out, facts_: list[dict], coming: list[dict]) -> None:
    """mikrofon.html: an ordinary page of the site (its links relative), which the edge worker (live/edge) shows at
    mikrofon.zailiprotiv.rs with a <base> pointing them back to the site; noindex, so out of the sitemap."""
    (out / PAGE).write_text(env.get_template("mikrofon.html").render(
        **common, facts=facts_, coming=coming[:1], broadcast=LIVE, root=""), encoding="utf-8")
