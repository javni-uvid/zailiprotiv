"""The family's look and links (family.py): the bar and the footer block name every site of Javni uvid, in the
page's script, and the stylesheet served is the family's in front of the site's own."""

import re
from pathlib import Path

from zailiprotiv import cyrillic, family

STATIC = Path(family.__file__).parent / "static"


def test_the_bar_names_the_family_and_its_sites_and_marks_this_one():
    bar = family.bar("lat", "../index.html")
    data = family.sites()
    assert f'class="ju-name" href="{data["family"]["url"]["lat"]}"' in bar
    assert '<a aria-current="page" href="../index.html">Za ili Protiv</a>' in bar
    others = [s for s in data["sites"] if s["id"] != family.ME]
    assert others, "the family has other sites to link"
    for s in others:
        assert f'href="{s["url"]["lat"]}" data-cir-href="{s["url"]["cyr"]}">{s["name"]["lat"]}</a>' in bar


def test_the_footer_block_says_the_promise_and_a_line_on_each_site():
    foot, data = family.foot("lat", "index.html"), family.sites()
    assert data["family"]["promise"]["lat"] in foot and "#nacela" in foot
    for s in data["sites"]:
        assert s["about"]["lat"] in foot


def test_the_cyrillic_twin_leads_to_the_others_cyrillic_pages():
    """The Latin page's bar becomes Cyrillic with the rest of the page, and each link takes the address of the
    other site's Cyrillic edition; this site's own link stays a page of the twin."""
    twin = cyrillic.page(f"<body>{family.bar('lat', '../index.html')}{family.foot('lat', '../index.html')}</body>", "zakon/x.html")
    data = family.sites()
    assert "Јавни увид" in twin and "За или Против" in twin and "Javni uvid" not in twin
    assert f'href="{data["family"]["url"]["cyr"]}"' in twin and f'href="{data["family"]["url"]["lat"]}"' not in twin
    for s in data["sites"]:
        if s["id"] != family.ME:
            assert f'href="{s["url"]["cyr"]}"' in twin and s["name"]["cyr"] in twin
    assert 'aria-current="page" href="../index.html"' in twin


def test_a_page_written_in_its_own_script_gets_that_script_and_no_twin():
    bar = family.bar("cyr", "https://zailiprotiv.rs/cir/", twin=False)
    assert "Јавни увид" in bar and "data-cir-href" not in bar and 'href="https://zailiprotiv.rs/cir/"' in bar


def test_the_stylesheet_served_is_the_familys_then_the_sites_own():
    css = family.stylesheet().decode("utf-8")
    own = (STATIC / "style.css").read_text(encoding="utf-8")
    assert css.index(".ju-bar") < css.index("Za ili Protiv. Colours mean kinds of vote")
    assert css.count("@font-face") == 3 and "@font-face" not in own  # the font is declared once, by the family
    # Every font file the family's stylesheet names is one the site serves.
    for name in re.findall(r"url\(fonts/([^)]+)\)", css):
        assert (STATIC / "fonts" / name).is_file(), name


def test_the_sites_own_stylesheet_takes_the_base_from_the_family():
    """No base colour, font or step of the scale is declared twice: the site's names are the family's values."""
    own = (STATIC / "style.css").read_text(encoding="utf-8")
    root = own[own.index(":root {"):own.index("* { box-sizing")]
    for name in ("bg", "fg", "muted", "line", "card"):
        assert f"--{name}: var(--ju-{name});" in root
    assert "--serif: var(--ju-serif);" in root and "--t-3: var(--ju-t-3);" in root
    assert not re.search(r"--(?:bg|fg|muted|line|card):\s*#", own)
