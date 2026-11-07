from ask import find_quote

HITS = [{"source": "a.pdf", "page": 4, "text": "Deep-sleep mode with RTC timer running:\n10 uA typical."}]


def test_real_quote_is_found_even_with_different_spacing_and_case():
    assert find_quote("deep-sleep mode with RTC timer running: 10 uA typical", HITS)["page"] == 4


def test_made_up_quote_is_rejected():
    assert find_quote("Deep-sleep current is 5 uA.", HITS) is None


def test_empty_quote_is_rejected():
    assert find_quote("", HITS) is None
