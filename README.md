# llm-cost-router

A FastAPI service that sends each question to a cheap or a strong Gemini model depending on how hard it looks, logs the cost of every request, and exposes Prometheus metrics.

**Stack:** Python, FastAPI, LiteLLM, Prometheus, Docker, pytest
**Models:** `gemini-3.1-flash-lite` (cheap), `gemini-3.5-flash` (strong)

**Result:** on 50 test questions the router cost $0.44 instead of $0.55 for always using the strong model, a 19.5% saving. On the 30 questions it sent to the cheap model, a judge rated the cheap answer as good as or better than the strong one in 27 (90%).

**Demo:** there is no hosted demo. Run it locally with Docker, see below.

## How it works

The router gives each question a difficulty score from simple rules:

- a hard keyword such as compare, design, debug, explain or implement adds 3
- a code block adds 2
- a very long question adds 1 or 2
- more than one question mark adds 1
- a short question with an easy keyword (what is, define, translate) subtracts 1

A score of 3 or more goes to the strong model, anything lower goes to the cheap one. You can force a model with `force_tier`.

Endpoints:

- `POST /ask` returns the answer, the model used, token counts, `cost_usd`, and what the same tokens would have cost on the strong model
- `GET /health`
- `GET /metrics` for Prometheus

```bash
curl -s localhost:8000/ask -H "Content-Type: application/json" \
  -d '{"question":"What is the capital of Japan?"}'
```

```json
{"answer":"The capital of Japan is Tokyo.","tier":"cheap","model":"gemini/gemini-3.1-flash-lite","score":-1,"reason":"easy keyword","prompt_tokens":8,"completion_tokens":7,"cost_usd":1.25e-05,"strong_cost_usd":7.5e-05,"latency_ms":2768}
```

## Run it

You need a free Gemini API key from Google AI Studio.

```bash
docker build -t llm-cost-router .
export GEMINI_API_KEY=your_key
docker run --rm -p 8000:8000 -e GEMINI_API_KEY llm-cost-router
```

Without Docker:

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=your_key
uvicorn app.main:app --port 8000
```

## Metrics

| Metric | Meaning |
|---|---|
| `router_requests_total{tier}` | requests per tier |
| `router_errors_total{tier}` | failed model calls |
| `router_cost_usd_total{tier}` | cost at list price |
| `router_saved_usd_total` | estimated saving against always using the strong model |
| `router_tokens_total{tier,kind}` | input and output tokens |
| `router_latency_seconds{tier}` | model call latency |

Each request also writes one log line with the tier, tokens and cost.

## Evaluation

I wrote 50 questions (30 easy, 20 hard) in `data/questions.json`, ran every one on both models, and compared three strategies. Costs use Gemini list prices from October 2026: $0.25 input and $1.50 output per million tokens for the cheap model, $1.50 and $9.00 for the strong one. On the free tier the real cost is $0. The numbers are what the same usage would cost on a paid plan. Hidden thinking tokens are billed as output and are included.

| Strategy | Total cost (USD) | Saving vs always strong | Avg score (1-10) | Avg answer length (words) |
|---|---|---|---|---|
| Always strong | 0.5456 | 0.0% | 10.00 | 311 |
| Always cheap | 0.0293 | 94.6% | 9.96 | 237 |
| Router | 0.4392 | 19.5% | 10.00 | 310 |

The 1-10 score is not useful here, because the judge gave almost every answer a 10. The head-to-head comparison below says more. A judge sees the cheap and the strong answer in random order and picks the better one, or a tie.

| Router sent the question to | Questions | Cheap better | Tie | Strong better |
|---|---|---|---|---|
| Cheap model | 30 | 2 | 25 | 3 |
| Strong model | 20 | 2 | 11 | 7 |

The router sent 20 questions to the strong model, but the strong answer was clearly better on only 7 of them. So the router is cautious, and a smarter one could save more. I did not train a classifier, because 50 labelled questions are too few to train and test on honestly.

To repeat the run: `python -m evaluation.run_eval`. Results are cached in `evaluation/results.jsonl` and `evaluation/pairwise.jsonl`. The free tier allows only 20 strong-model requests a day, so the first run took several days. A repeat on cached results makes no API calls.

## Limits

- The savings depend on the question mix. My set is 40% hard. With mostly easy traffic the saving would be larger.
- I tuned the router rules on these same 50 questions. The first version matched my easy/hard labels on 37 of 50, and one change brought it to 50 of 50. Treat 100% as optimistic.
- The judge is a Gemini Flash-Lite model, so it may favour Gemini answers. My first head-to-head prompt asked for completeness and favoured the longer strong answers (strong better on 17 of the first 27 easy questions). I changed it to ignore length and reran everything. The final prompt is in `evaluation/run_eval.py`.
- I do not report latency. My first measurement included rate-limit retry waits, so the numbers were wrong.
- Both models are in the same Flash family. The quality gap is smaller than it would be between Flash and Pro, which my free key could not use.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

34 tests cover the router rules, pricing, the API with mocked model calls, the metrics, and the evaluation logic.
