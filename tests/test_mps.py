from zailiprotiv import mps


def test_one_key_for_both_layouts():
    assert mps.key("АТЛАГИЋ проф. др МАРКО") == mps.key("проф. др Марко Атлагић")
    assert mps.key("БЕЛОИЦА МАРТАЋ АНА") == mps.key("Ана Белоица Мартаћ")
    assert mps.key("ИЛИЋ-СТОШИЋ БИЉАНА") == mps.key("Биљана Илић-Стошић")
    assert mps.key("ЗДРАВКОВИЋ проф. др сц. мед. МАРИЈА") == mps.key("проф. др сц. мед. Марија Здравковић")
    assert mps.key("ЈОВАНОВИЋ НАТАША") != mps.key("ИВАНОВИЋ НАТАША")


def test_clashes():
    votes = [{"rows": [[1, "ЈОВАНОВИЋ ДАРКО", "za", "ПГ А"], [2, "Дарко Јовановић", "za", "Б"]]}]
    assert mps.clashes(votes) == {mps.key("Дарко Јовановић"): {"ЈОВАНОВИЋ ДАРКО", "Дарко Јовановић"}}
