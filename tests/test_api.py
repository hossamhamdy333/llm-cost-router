from types import SimpleNamespace

from fastapi.testclient import TestClient

from app import llm
from app.main import app

client = TestClient(app)


def fake_response(text="ok"):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
    )


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_easy_question_uses_cheap_model(monkeypatch):
    calls = []

    def fake(tier, question):
        calls.append(tier)
        return fake_response("Paris")

    monkeypatch.setattr(llm, "ask_model", fake)
    r = client.post("/ask", json={"question": "What is the capital of France?"})
    body = r.json()
    assert r.status_code == 200
    assert calls == ["cheap"]
    assert body["tier"] == "cheap"
    assert body["model"] == llm.MODELS["cheap"]
    assert body["answer"] == "Paris"
    assert body["prompt_tokens"] == 10


def test_hard_question_uses_strong_model(monkeypatch):
    monkeypatch.setattr(llm, "ask_model", lambda t, q: fake_response())
    q = "Compare two architectures for a chat app and explain the trade-off."
    body = client.post("/ask", json={"question": q}).json()
    assert body["tier"] == "strong"


def test_force_tier_overrides_router(monkeypatch):
    monkeypatch.setattr(llm, "ask_model", lambda t, q: fake_response())
    body = client.post(
        "/ask", json={"question": "hi", "force_tier": "strong"}
    ).json()
    assert body["tier"] == "strong"


def test_model_error_returns_502(monkeypatch):
    def boom(tier, question):
        raise RuntimeError("rate limit")

    monkeypatch.setattr(llm, "ask_model", boom)
    r = client.post("/ask", json={"question": "hi"})
    assert r.status_code == 502


def test_empty_question_rejected():
    assert client.post("/ask", json={"question": ""}).status_code == 422


def test_bad_force_tier_rejected():
    r = client.post("/ask", json={"question": "hi", "force_tier": "free"})
    assert r.status_code == 422


def test_response_has_cost(monkeypatch):
    monkeypatch.setattr(llm, "ask_model", lambda t, q: fake_response())
    body = client.post("/ask", json={"question": "hi"}).json()
    assert abs(body["cost_usd"] - 0.00001) < 1e-12
    assert body["strong_cost_usd"] > body["cost_usd"]


def test_metrics_endpoint_counts_requests(monkeypatch):
    from prometheus_client import REGISTRY

    monkeypatch.setattr(llm, "ask_model", lambda t, q: fake_response())
    before = REGISTRY.get_sample_value("router_requests_total", {"tier": "cheap"}) or 0
    client.post("/ask", json={"question": "hi"})
    after = REGISTRY.get_sample_value("router_requests_total", {"tier": "cheap"})
    assert after == before + 1

    text = client.get("/metrics").text
    assert "router_requests_total" in text
    assert "router_saved_usd_total" in text


def test_error_is_counted(monkeypatch):
    from prometheus_client import REGISTRY

    def boom(tier, question):
        raise RuntimeError("down")

    monkeypatch.setattr(llm, "ask_model", boom)
    before = REGISTRY.get_sample_value("router_errors_total", {"tier": "cheap"}) or 0
    client.post("/ask", json={"question": "hi"})
    assert REGISTRY.get_sample_value("router_errors_total", {"tier": "cheap"}) == before + 1
