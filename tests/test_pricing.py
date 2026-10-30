from app.pricing import cost_usd


def test_cheap_cost():
    assert cost_usd("cheap", 1_000_000, 1_000_000) == 1.75


def test_strong_cost():
    assert cost_usd("strong", 1_000_000, 1_000_000) == 10.5


def test_small_request():
    assert abs(cost_usd("cheap", 10, 5) - 0.00001) < 1e-12


def test_strong_costs_more_for_same_tokens():
    assert cost_usd("strong", 500, 500) > cost_usd("cheap", 500, 500)
