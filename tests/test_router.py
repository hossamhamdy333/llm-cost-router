from app.router import route


def test_simple_fact_goes_cheap():
    assert route("What is the capital of France?").tier == "cheap"


def test_short_greeting_goes_cheap():
    assert route("hi, how are you?").tier == "cheap"


def test_code_and_hard_word_goes_strong():
    q = "Debug this code:\n```python\ndef f(x):\n    return x/0\n```"
    assert route(q).tier == "strong"


def test_design_question_goes_strong():
    q = "Compare two architectures for a chat app and explain the trade-off."
    assert route(q).tier == "strong"


def test_long_question_alone_is_not_enough():
    q = " ".join(["word"] * 70)
    assert route(q).tier == "cheap"


def test_threshold_can_change():
    q = "Compare cats and dogs."
    assert route(q, threshold=2).tier == "strong"
    assert route(q, threshold=5).tier == "cheap"


def test_decision_has_reason():
    d = route("Prove that sqrt(2) is irrational, step by step.")
    assert "hard keyword" in d.reason
