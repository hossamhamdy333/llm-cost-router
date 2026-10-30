import litellm

MODELS = {
    "cheap": "gemini/gemini-3.1-flash-lite",
    "strong": "gemini/gemini-3.5-flash",
}


def ask_model(tier, question):
    return litellm.completion(
        model=MODELS[tier],
        messages=[{"role": "user", "content": question}],
        max_tokens=4096,
    )


JUDGE_MODEL = "gemini/gemini-3.5-flash-lite"


def judge_model(prompt):
    return litellm.completion(
        model=JUDGE_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2048,
    )
