from dataclasses import dataclass

HARD_WORDS = [
    "explain why", "compare", "analyze", "analyse", "design", "prove",
    "step by step", "trade-off", "tradeoff", "architecture", "optimize",
    "derive", "debug", "refactor", "implement", "pros and cons",
    "explain", "python function", "write a function",
]
EASY_WORDS = [
    "what is", "who is", "define", "capital of", "translate",
    "when did", "how many", "what does",
]
CODE_MARKERS = ["```", "def ", "class ", "import ", "select ", "traceback"]


@dataclass
class Decision:
    tier: str
    score: int
    reason: str


def score_question(question):
    q = question.lower()
    words = len(q.split())
    score = 0
    reasons = []

    if words > 60:
        score += 2
        reasons.append("very long")
    elif words > 25:
        score += 1
        reasons.append("long")

    hard_hits = [w for w in HARD_WORDS if w in q]
    if hard_hits:
        score += 3
        reasons.append("hard keyword: " + hard_hits[0])

    if any(m in q for m in CODE_MARKERS):
        score += 2
        reasons.append("has code")

    if q.count("?") > 1:
        score += 1
        reasons.append("many questions")

    if words <= 12 and any(w in q for w in EASY_WORDS):
        score -= 1
        reasons.append("easy keyword")

    return score, ", ".join(reasons) or "no signals"


def route(question, threshold=3):
    score, reason = score_question(question)
    tier = "strong" if score >= threshold else "cheap"
    return Decision(tier=tier, score=score, reason=reason)
