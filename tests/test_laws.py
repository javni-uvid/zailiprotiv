from zailiprotiv import laws

# Two rows of the Assembly's page of adopted laws, as served on 12 Nov 2026 (cut to what the reader uses).
PAGE = """<table>
<tr> <td align="left" class="lawtitle"> <strong>
 <a href="/upload/archive/files/lat/pdf/zakoni/14_saziv/2694-26 - Lat..pdf">Zakon o potvrđivanju Protokola o
 eksplozivnim ostacima rata (Protokol V)</a> <h4 class="related">Povezani dokumenti</h4> <ul class="related"> <li>
 <a href="/upload/archive/files/lat/pdf/predlozi_zakona/14_saziv/2694-26 - Lat..pdf">Predlog zakona o potvrđivanju
 Protokola o eksplozivnim ostacima rata (Protokol V)</a> (21. avgust 2026. ) </li> </ul> </strong> </td>
 <td nowrap=""> 31. avgust 2026. </td> <td nowrap="">7/26 (МU)</td>
 <td nowrap=""> <a href="/upload/archive/files/lat/pdf/zakoni/14_saziv/2694-26 - Lat..pdf">PDF</a> ,
 <a href="/upload/archive/files/lat/doc/zakoni/14_saziv/2694-26 - Lat..doc">DOC</a> </td> </tr>
<tr> <td class="lawtitle"> <strong>
 <a href="/upload/archive/files/lat/pdf/zakoni/14_saziv/2691-26.pdf">Zakon o izmenama i dopuni Zakona o budžetu
 Republike Srbije za 2026. godinu</a> <ul class="related"> <li>
 <a href="/upload/archive/files/cir/pdf/predlozi_zakona/14_saziv/400-2691_26.pdf">Predlog zakona o izmenama i
 dopuni Zakona o budžetu Republike Srbije za 2026. godinu</a> (24. avgust 2026. ) </li> </ul> </strong> </td>
 <td nowrap=""> 31. avgust 2026. </td> <td nowrap="">80/26</td>
 <td nowrap=""> <a href="/upload/archive/files/lat/pdf/zakoni/14_saziv/2691-26.pdf">PDF</a> </td> </tr>
<tr><td>Наслов табеле</td></tr>
</table>"""


def test_adopted_laws():
    treaty, budget = laws.parse(PAGE)
    assert treaty.title == "Zakon o potvrđivanju Protokola o eksplozivnim ostacima rata (Protokol V)"
    assert (treaty.passed, treaty.gazette, treaty.treaty, treaty.submitted) == ("2026-08-31", "7/26", True,
                                                                               "2026-08-21")
    assert treaty.bill_pdf.endswith("/predlozi_zakona/14_saziv/2694-26 - Lat..pdf")
    assert budget.title.startswith("Zakon o izmenama i dopuni Zakona o budžetu")
    assert (budget.gazette, budget.treaty, budget.passed) == ("80/26", False, "2026-08-31")
    assert "/cir/pdf/predlozi_zakona/" in budget.bill_pdf


def test_dates_in_both_scripts():
    assert laws.date("1. децембар 2025.") == "2025-12-01"
    assert laws.date("(9. mart 2024. )") == "2024-03-09"
    assert laws.date("80/26") is None
