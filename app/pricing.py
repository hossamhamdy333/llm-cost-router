# USD per 1M tokens, Gemini API list prices (Oct 2026)
PRICES = {
    "cheap": {"input": 0.25, "output": 1.50},
    "strong": {"input": 1.50, "output": 9.00},
}


def cost_usd(tier, prompt_tokens, completion_tokens):
    p = PRICES[tier]
    return (prompt_tokens * p["input"] + completion_tokens * p["output"]) / 1_000_000
