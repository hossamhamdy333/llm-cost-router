from prometheus_client import Counter, Histogram

REQUESTS = Counter("router_requests", "Requests by tier", ["tier"])
ERRORS = Counter("router_errors", "Failed model calls", ["tier"])
COST = Counter("router_cost_usd", "Cost at list price in USD", ["tier"])
SAVED = Counter("router_saved_usd", "Estimated USD saved vs always using strong")
TOKENS = Counter("router_tokens", "Tokens used", ["tier", "kind"])
LATENCY = Histogram("router_latency_seconds", "Model call latency", ["tier"])
