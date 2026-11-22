"""pages_support.py: "Podrži", the NBS IPS QR codes drawn in the page."""
from zailiprotiv import cyrillic, pages_support as ps

S = {"account": "265000000676858538", "name": "Marko Pomorišac", "place": "Novi Sad", "code": "289",
     "purpose": "Podrška projektu Za ili Protiv", "amounts": [300, 500]}


def test_the_account_and_the_codes_text():
    assert ps.account_ok("265000000676858538") and not ps.account_ok("265000000676858539")
    assert not ps.account_ok("26500000067685853")
    assert ps.account_shown("265000000676858538") == "265-0000006768585-38"
    # the form the NBS's validator accepted on 22 Nov 2026: the amount is mandatory, the payer may change it
    assert ps.payload(S, 500) == ("K:PR|V:01|C:1|R:265000000676858538|N:Marko Pomorišac\r\nNovi Sad|I:RSD500,00"
                                  "|SF:289|S:Podrška projektu Za ili Protiv")


def test_the_code_is_drawn_in_the_page_and_kept_out_of_the_cyrillic():
    svg = ps.qr_svg(ps.payload(S, 300))
    assert svg.startswith('<svg viewBox="0 0 ') and 'class="ips-qr"' in svg and "http" not in svg.replace("http://www.w3.org/2000/svg", "")
    html = f"<html><body><p>Podrži</p>{svg}</body></html>"
    out = cyrillic.page(html, "podrzi.html")
    assert "Подржи" in out and svg[svg.index("<title>"):] in out  # the drawing and its title as they were
    assert svg[svg.index("<path"):] in out  # the drawing as it was


def test_no_page_without_a_valid_account(tmp_path):
    assert not ps.render(settings={"support": {**S, "account": "123"}}, env=None, common={}, out=tmp_path)
    assert not ps.render(settings={}, env=None, common={}, out=tmp_path)
