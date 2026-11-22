"""The page "Podrži" (podrzi.html): readers' support by bank transfer, with an NBS IPS QR code a bank's app scans
(22 Nov 2026, the maintainer's decision: no ads, principle 5; donations to the maintainer's account, said so).

The codes are drawn here, as SVG in the page itself: nothing is loaded from elsewhere (publish.check). The text a code
holds is the NBS's "PR" (payment order) form, checked against the NBS's validator when written (22 Nov 2026):
K:PR|V:01|C:1|R:<18 digits>|N:<payee>|I:RSD<amount>|SF:<payment code>|S:<purpose>. The amount is mandatory in the
form; the payer can change it in the app, so the page offers a few and says so. From data/settings.json `support`:
{"account", "name", "place", "code", "purpose", "amounts", "paypal"} (all public by design: they are on the page)."""
from __future__ import annotations

import io
import re

PAGE = "podrzi.html"


def account_ok(account: str) -> bool:
    """A Serbian account of 18 digits whose last two are its control number (ISO 7064, mod 97)."""
    return bool(re.fullmatch(r"\d{18}", account)) and 98 - int(account[:16]) * 100 % 97 == int(account[16:])


def payload(s: dict, amount: int) -> str:
    """The text of the NBS IPS QR code for a payment of `amount` dinars."""
    payee = s["name"] + ("\r\n" + s["place"] if s.get("place") else "")
    return (f'K:PR|V:01|C:1|R:{s["account"]}|N:{payee}|I:RSD{amount},00|SF:{s.get("code", "289")}'
            f'|S:{s.get("purpose", "")[:35]}')


def qr_svg(text: str) -> str:
    """The code as an SVG element: error correction M, a quiet zone of four modules, dark on white in either theme."""
    import segno
    buf = io.BytesIO()
    segno.make(text, error="m", micro=False, encoding="utf-8").save(
        buf, kind="svg", scale=4, border=4, dark="#000", light="#fff", xmldecl=False, svgns=True, nl=False,
        title="NBS IPS QR", svgclass="ips-qr")
    svg = buf.getvalue().decode("utf-8")
    w, h = re.search(r'width="(\d+)"', svg).group(1), re.search(r'height="(\d+)"', svg).group(1)
    svg = re.sub(r'\s(?:width|height)="\d+"', "", svg, count=2)  # sized by the page: the viewBox keeps its shape
    return svg.replace("<svg ", f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="NBS IPS QR" ', 1)


def account_shown(account: str) -> str:
    """The account as banks print it: 265-0000006768585-38."""
    return f"{account[:3]}-{account[3:16]}-{account[16:]}"


def render(*, settings: dict, env, common: dict, out) -> bool:
    """Writes podrzi.html when `support` is set with a valid account; whether it was written."""
    s = settings.get("support") or {}
    if not s.get("account") or not s.get("name") or not account_ok(s["account"]):
        return False
    import segno
    codes = [{"amount": a, "svg": qr_svg(payload(s, a)), "text": payload(s, a)} for a in s.get("amounts") or [500]]
    for c in codes:  # a picture to keep, for a bank's app that reads a code from the phone's gallery
        segno.make(c["text"], error="m", micro=False, encoding="utf-8").save(
            str(out / f'podrzi-{c["amount"]}.png'), kind="png", scale=10, border=4)
    (out / PAGE).write_text(env.get_template("support.html").render(
        **common, s=s, codes=codes, account=account_shown(s["account"]), root=""), encoding="utf-8")
    return True
