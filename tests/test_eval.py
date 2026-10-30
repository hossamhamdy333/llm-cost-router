from evaluation.run_eval import parse_score, summarize


def rec(cost, score):
    return {"cost_usd": cost, "score": score, "latency_ms": 1000}


def test_parse_plain_number():
    assert parse_score("8") == 8.0


def test_parse_fraction_text():
    assert parse_score("Score: 7/10") == 7.0


def test_parse_clamps_and_handles_junk():
    assert parse_score("42") == 10.0
    assert parse_score("no idea") is None
    assert parse_score(None) is None


def test_summarize_savings():
    questions = [
        {"id": 1, "question": "What is the capital of France?", "label": "easy"},
        {"id": 2, "question": "Compare two databases and explain the trade-off.", "label": "hard"},
    ]
    results = {
        "1:cheap": rec(1, 9), "1:strong": rec(10, 9),
        "2:cheap": rec(2, 4), "2:strong": rec(20, 9),
    }
    s = summarize(questions, results)
    assert s["strategies"]["router"]["cost"] == 21
    assert s["strategies"]["always_strong"]["cost"] == 30
    assert round(s["strategies"]["router"]["saving_pct"], 1) == 30.0
    assert s["strategies"]["router"]["quality"] == 9
    assert s["strategies"]["always_cheap"]["quality"] == 6.5
    assert s["agreement_pct"] == 100


def test_daily_quota_detection():
    from evaluation.run_eval import is_daily_quota

    assert is_daily_quota("Generate content requests per day limit exceeded")
    assert is_daily_quota("quotaId: GenerateRequestsPerDayPerProjectPerModel-FreeTier")
    assert not is_daily_quota("Quota exceeded: limit 5 per minute")


def test_retry_turns_daily_quota_into_stop(monkeypatch):
    import pytest
    from evaluation import run_eval

    monkeypatch.setattr(run_eval.time, "sleep", lambda s: None)

    def fail():
        raise RuntimeError("requests per day limit exceeded")

    with pytest.raises(run_eval.DailyQuota):
        run_eval.with_retry(fail)


def test_retry_recovers_after_minute_limit(monkeypatch):
    from evaluation import run_eval

    monkeypatch.setattr(run_eval.time, "sleep", lambda s: None)
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise RuntimeError("429 per minute")
        return "ok"

    assert run_eval.with_retry(flaky) == "ok"
    assert len(calls) == 3


def test_is_complete():
    from evaluation.run_eval import is_complete

    qs = [{"id": 1}]
    assert not is_complete(qs, {"1:cheap": {}})
    assert is_complete(qs, {"1:cheap": {}, "1:strong": {}})


def fake_judge(text):
    from types import SimpleNamespace

    msg = SimpleNamespace(content=text)
    return lambda prompt: SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def test_parse_verdict():
    from evaluation.run_eval import parse_verdict

    assert parse_verdict("A") == "A"
    assert parse_verdict("b.") == "B"
    assert parse_verdict("Tie") == "TIE"
    assert parse_verdict("Both are fine") is None
    assert parse_verdict("") is None


def test_compare_maps_order_back(monkeypatch):
    from evaluation import run_eval

    monkeypatch.setattr(run_eval, "cheap_is_a", lambda qid: True)
    monkeypatch.setattr(run_eval.llm, "judge_model", fake_judge("A"))
    assert run_eval.compare("q", "c", "s", 1) == "cheap"
    monkeypatch.setattr(run_eval.llm, "judge_model", fake_judge("B"))
    assert run_eval.compare("q", "c", "s", 1) == "strong"

    monkeypatch.setattr(run_eval, "cheap_is_a", lambda qid: False)
    monkeypatch.setattr(run_eval.llm, "judge_model", fake_judge("A"))
    assert run_eval.compare("q", "c", "s", 1) == "strong"
    monkeypatch.setattr(run_eval.llm, "judge_model", fake_judge("B"))
    assert run_eval.compare("q", "c", "s", 1) == "cheap"

    monkeypatch.setattr(run_eval.llm, "judge_model", fake_judge("TIE"))
    assert run_eval.compare("q", "c", "s", 1) == "tie"


def test_summarize_head_to_head():
    questions = [
        {"id": 1, "question": "What is the capital of France?", "label": "easy"},
        {"id": 2, "question": "Compare two databases and explain the trade-off.", "label": "hard"},
    ]
    results = {
        "1:cheap": rec(1, 9), "1:strong": rec(10, 9),
        "2:cheap": rec(2, 4), "2:strong": rec(20, 9),
    }
    pairs = {1: {"id": 1, "winner": "tie"}, 2: {"id": 2, "winner": "strong"}}
    h = summarize(questions, results, pairs)["head_to_head"]
    assert h["routed_cheap"] == {"cheap": 0, "tie": 1, "strong": 0}
    assert h["routed_strong"] == {"cheap": 0, "tie": 0, "strong": 1}


def test_old_prompt_version_is_not_complete():
    from evaluation.run_eval import PAIR_VERSION, pairs_complete

    qs = [{"id": 1}]
    assert not pairs_complete(qs, {1: {"id": 1, "winner": "tie"}})
    assert not pairs_complete(qs, {1: {"id": 1, "winner": "tie", "prompt": PAIR_VERSION - 1}})
    assert pairs_complete(qs, {1: {"id": 1, "winner": "tie", "prompt": PAIR_VERSION}})


def test_summary_has_answer_length():
    questions = [{"id": 1, "question": "What is the capital of France?", "label": "easy"}]
    results = {
        "1:cheap": {"cost_usd": 1, "score": 9, "latency_ms": 1000, "answer": "Paris."},
        "1:strong": {"cost_usd": 10, "score": 9, "latency_ms": 1000, "answer": "The capital is Paris, a city on the Seine."},
    }
    s = summarize(questions, results)
    assert s["strategies"]["always_cheap"]["words"] == 1
    assert s["strategies"]["always_strong"]["words"] == 9
