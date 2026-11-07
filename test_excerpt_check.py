from ask import find_quote

HITS = [{"source": "a.pdf", "page": 4, "text": "Deep-sleep mode with RTC timer running:\n10 uA typical."}]


def test_real_quote_is_found_even_with_different_spacing_and_case():
    assert find_quote("deep-sleep mode with RTC timer running: 10 uA typical", HITS)["page"] == 4


def test_quote_matches_across_a_pdf_line_break_inside_a_word():
    hits = [{"source": "esp32.pdf", "page": 61, "text": "no output driver or internal pull-\nup/pull-down circuitry ."}]
    assert find_quote("no output driver or internal pull-up/pull-down circuitry.", hits)["page"] == 61


def test_made_up_quote_is_rejected():
    assert find_quote("Deep-sleep current is 5 uA.", HITS) is None


def test_empty_quote_is_rejected():
    assert find_quote("", HITS) is None


def test_log_query_writes_one_json_line(tmp_path, monkeypatch):
    import ask

    monkeypatch.setattr(ask, "LOG_PATH", tmp_path / "queries.jsonl")
    result = {"answer": "10 uA", "quote": "x", "source": HITS[0], "hits": [{**HITS[0], "distance": 0.21}]}
    ask.log_query("deep sleep current?", result, retrieval_ms=50, llm_ms=900)

    [record] = ask.read_log()
    assert record["verified"] is True
    assert record["retrieved"][0]["page"] == 4
    assert record["llm_ms"] == 900
