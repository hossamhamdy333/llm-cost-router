import logging
import time
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, Field

from app import llm, metrics
from app.pricing import cost_usd
from app.router import route

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("router")

app = FastAPI(title="LLM Cost Router")


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=8000)
    force_tier: Optional[Literal["cheap", "strong"]] = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/metrics")
def prometheus_metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/ask")
def ask(req: AskRequest):
    decision = route(req.question)
    tier = req.force_tier or decision.tier

    start = time.time()
    try:
        resp = llm.ask_model(tier, req.question)
    except Exception as e:
        metrics.ERRORS.labels(tier).inc()
        log.warning("tier=%s error=%s", tier, e)
        raise HTTPException(status_code=502, detail=f"model call failed: {e}")
    seconds = time.time() - start

    pt = resp.usage.prompt_tokens
    ct = resp.usage.completion_tokens
    cost = cost_usd(tier, pt, ct)
    strong_cost = cost_usd("strong", pt, ct)
    saved = strong_cost - cost

    metrics.REQUESTS.labels(tier).inc()
    metrics.COST.labels(tier).inc(cost)
    metrics.SAVED.inc(saved)
    metrics.TOKENS.labels(tier, "input").inc(pt)
    metrics.TOKENS.labels(tier, "output").inc(ct)
    metrics.LATENCY.labels(tier).observe(seconds)

    log.info(
        "tier=%s model=%s in=%d out=%d cost_usd=%.6f latency_ms=%d",
        tier, llm.MODELS[tier], pt, ct, cost, round(seconds * 1000),
    )

    return {
        "answer": resp.choices[0].message.content,
        "tier": tier,
        "model": llm.MODELS[tier],
        "score": decision.score,
        "reason": decision.reason,
        "prompt_tokens": pt,
        "completion_tokens": ct,
        "cost_usd": cost,
        "strong_cost_usd": strong_cost,
        "latency_ms": round(seconds * 1000),
    }
