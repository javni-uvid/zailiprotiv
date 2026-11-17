

def test_commonest_harsh_word_counts_its_forms_together():
    from zailiprotiv import pages_floor
    assert pages_floor.commonest(["издајници", "издајника", "лопов", "издајници", "лопове"]) == ("izdajnici", 3)
    assert pages_floor.commonest([]) == (None, 0)
