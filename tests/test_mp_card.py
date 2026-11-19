from zailiprotiv import mp_card


def _facts(**kw):
    base = dict(slug="a", by_conv=[], floor=[], exchanges=[], apart=0, voted=0, busiest=None, words=[],
                day=lambda d: d + ".", given_first=lambda n: n)
    return [str(f["n"]) + " " + str(f["text"]) for f in mp_card.facts(**{**base, **kw})]


def test_a_fact_without_data_is_left_out():
    assert _facts() == []


def test_the_card_says_each_number_once_with_its_source():
    floor = [{"speeches": 3, "words": 15600, "measures": 1, "measures_likely": 0, "harsh": 0,
              "longest": {"words": 9000, "date": "2026-11-01", "url": "s.html#g1"}}]
    ex = [{"a": {"slug": "a", "name": "A"}, "b": {"slug": "b", "name": "Bjelić Ana"}},
          {"a": {"slug": "b", "name": "Bjelić Ana"}, "b": {"slug": "a", "name": "A"}},
          {"a": {"slug": "a", "name": "A"}, "b": {"slug": "", "name": "Gost"}}]
    conv = [{"name": "Četrnaesti", "present": (90, 100), "median": 0.8,
             "agree": [{"group": "Svoja", "share": 0.99, "own": True}, {"group": "Druga", "share": 0.4, "own": False}]}]
    got = _facts(floor=floor, exchanges=ex, by_conv=conv, apart=2, voted=50, busiest=(3, "2026-11-01", "s.html#g1"),
                 words=["lovci"])
    text = " | ".join(got)
    assert got[0].startswith("90% prisustva")
    assert "2 glasa drugačija od većine" in text and 'href="#drugacije"' in text
    assert "oko 2 sata govora" in text  # 15.600 words at 130 a minute
    assert "9.000 reči u najdužem govoru" in text and 'href="s.html#g1"' in text
    assert "3 govora u jednom danu" in text
    assert 'href="b.html">Bjelić Ana</a> (2)' in text and "Gost (1)" in text
    assert "grupe Druga" in text and "Svoja" not in text  # the own group is not the most alike
    assert "<i>lovci</i>" in text and ".." not in text


def test_no_vote_unlike_the_group_is_said_as_such():
    assert any(f.startswith("Nijedan glas drugačiji") and "(10 glasova" in f for f in _facts(voted=10))
    assert _facts(voted=1) == []  # one vote says nothing of a habit
