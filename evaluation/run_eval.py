import argparse
import json
import random
import re
import time
from pathlib import Path

from app import llm
from app.pricing import cost_usd
from app.router import route

HERE = Path(__file__).resolve().parent
QUESTIONS = HERE.parent / "data" / "questions.json"
CACHE = HERE / "results.jsonl"
PAIRS = HERE / "pairwise.jsonl"
SUMMARY = HERE / "summary.md"

JUDGE_PROMPT = """You are grading an answer to a question.
Score it from 1 to 10 for correctness, completeness and clarity.
Reply with only the number.

Question:
{q}

Answer:
{a}
"""

PAIR_VERSION = 2

PAIR_PROMPT = """Two answers to the same question are shown below.
Pick the one that serves the person who asked better. Correctness comes first.
Do not prefer an answer only because it is longer or more detailed than the question needs.
If both are correct and sufficient, reply TIE.
Reply with exactly one word: A, B or TIE.

Question:
{q}

Answer A:
{a}

Answer B:
{b}
"""


def parse_score(text):
    m = re.search(r"\d+(\.\d+)?", text or "")
    if not m:
        return None
    return max(1.0, min(10.0, float(m.group())))


def parse_verdict(text):
    words = re.findall(r"[A-Za-z]+", (text or "").upper())
    if words and words[0] in ("A", "B", "TIE"):
        return words[0]
    return None


class DailyQuota(Exception):
    pass


def is_daily_quota(err):
    text = str(err)
    return "PerDay" in text or "per day" in text


def with_retry(fn, tries=5):
    for i in range(tries):
        try:
            return fn()
        except Exception as e:
            if is_daily_quota(e):
                raise DailyQuota(str(e)[:100]) from e
            if i == tries - 1:
                raise
            wait = 15 * (i + 1)
            print(f"retry in {wait}s: {str(e)[:60]}")
            time.sleep(wait)


def generate(tier, prompt):
    def once():
        start = time.time()
        resp = llm.ask_model(tier, prompt)
        return resp, round((time.time() - start) * 1000)

    return with_retry(once)


def judge(question, answer):
    prompt = JUDGE_PROMPT.format(q=question, a=answer)
    resp = with_retry(lambda: llm.judge_model(prompt))
    return parse_score(resp.choices[0].message.content)


def cheap_is_a(qid):
    return random.Random(qid).random() < 0.5


def compare(question, cheap_answer, strong_answer, qid):
    a_first = cheap_is_a(qid)
    a, b = (cheap_answer, strong_answer) if a_first else (strong_answer, cheap_answer)
    prompt = PAIR_PROMPT.format(q=question, a=a, b=b)
    resp = with_retry(lambda: llm.judge_model(prompt))
    verdict = parse_verdict(resp.choices[0].message.content)
    if verdict is None:
        return None
    if verdict == "TIE":
        return "tie"
    cheap_won = (verdict == "A") == a_first
    return "cheap" if cheap_won else "strong"


def load_jsonl(path):
    out = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                out.append(json.loads(line))
    return out


def write_jsonl(path, records):
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    tmp.replace(path)


def load_cache():
    return {f"{r['id']}:{r['tier']}": r for r in load_jsonl(CACHE)}


def save(done):
    write_jsonl(CACHE, list(done.values()))


def load_pairs():
    return {r["id"]: r for r in load_jsonl(PAIRS)}


def save_pairs(pairs):
    write_jsonl(PAIRS, list(pairs.values()))


def is_complete(questions, results):
    return all(
        f"{q['id']}:{t}" in results for q in questions for t in ("cheap", "strong")
    )


def run(limit=None):
    all_questions = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    texts = {q["id"]: q["question"] for q in all_questions}
    questions = all_questions[:limit] if limit else all_questions
    done = load_cache()

    try:
        for rec in done.values():
            if rec.get("judge") != llm.JUDGE_MODEL:
                rec["score"] = judge(texts[rec["id"]], rec["answer"])
                rec["judge"] = llm.JUDGE_MODEL
                save(done)
                print(f"rejudged q{rec['id']} {rec['tier']} score={rec['score']}")
    except DailyQuota as e:
        print(f"Daily limit reached on the judge model. Run again after the reset. {e}")
        return questions, done

    for tier in ("cheap", "strong"):
        for q in questions:
            key = f"{q['id']}:{tier}"
            if key in done:
                continue
            try:
                resp, latency_ms = generate(tier, q["question"])
                answer = resp.choices[0].message.content or ""
                score = judge(q["question"], answer)
            except DailyQuota as e:
                print(f"Daily limit reached for {tier}. Run again after the reset. {e}")
                break
            pt = resp.usage.prompt_tokens
            ct = resp.usage.completion_tokens
            done[key] = {
                "id": q["id"],
                "tier": tier,
                "model": getattr(resp, "model", None),
                "prompt_tokens": pt,
                "completion_tokens": ct,
                "cost_usd": cost_usd(tier, pt, ct),
                "latency_ms": latency_ms,
                "score": score,
                "judge": llm.JUDGE_MODEL,
                "answer": answer,
            }
            save(done)
            print(f"q{q['id']} {tier} score={score} cost=${done[key]['cost_usd']:.5f}")
    return questions, done


def pairs_complete(questions, pairs):
    return all(pairs.get(q["id"], {}).get("prompt") == PAIR_VERSION for q in questions)


def run_pairwise(questions, results):
    pairs = load_pairs()
    for q in questions:
        if pairs.get(q["id"], {}).get("prompt") == PAIR_VERSION:
            continue
        cheap = results.get(f"{q['id']}:cheap")
        strong = results.get(f"{q['id']}:strong")
        if not cheap or not strong:
            continue
        try:
            winner = compare(q["question"], cheap["answer"], strong["answer"], q["id"])
        except DailyQuota as e:
            print(f"Daily limit reached on the judge model. {e}")
            break
        if winner is None:
            continue
        pairs[q["id"]] = {"id": q["id"], "winner": winner, "prompt": PAIR_VERSION}
        save_pairs(pairs)
        print(f"q{q['id']} head-to-head: {winner}")
    return pairs


def summarize(questions, results, pairs=None):
    rows = {"always_strong": [], "always_cheap": [], "router": []}
    head = {
        "routed_cheap": {"cheap": 0, "tie": 0, "strong": 0},
        "routed_strong": {"cheap": 0, "tie": 0, "strong": 0},
    }
    agree = 0
    for q in questions:
        cheap = results[f"{q['id']}:cheap"]
        strong = results[f"{q['id']}:strong"]
        picked = route(q["question"]).tier
        rows["always_cheap"].append(cheap)
        rows["always_strong"].append(strong)
        rows["router"].append(strong if picked == "strong" else cheap)
        wanted = "strong" if q["label"] == "hard" else "cheap"
        if picked == wanted:
            agree += 1
        if pairs and q["id"] in pairs:
            group = "routed_cheap" if picked == "cheap" else "routed_strong"
            head[group][pairs[q["id"]]["winner"]] += 1

    out = {}
    for name, recs in rows.items():
        scores = [r["score"] for r in recs if r["score"] is not None]
        out[name] = {
            "cost": sum(r["cost_usd"] for r in recs),
            "quality": sum(scores) / len(scores) if scores else None,
            "latency_s": sum(r["latency_ms"] for r in recs) / len(recs) / 1000,
            "words": sum(len(r.get("answer", "").split()) for r in recs) / len(recs),
        }
    base = out["always_strong"]["cost"]
    for v in out.values():
        v["saving_pct"] = 100 * (1 - v["cost"] / base)
    return {
        "strategies": out,
        "agreement_pct": 100 * agree / len(questions),
        "head_to_head": head if pairs else None,
    }


def to_markdown(summary, n):
    lines = [
        f"Results on {n} questions.",
        "",
        "| Strategy | Total cost (USD) | Saving vs always-strong | Avg score (1-10) | Avg answer length (words) |",
        "|---|---|---|---|---|",
    ]
    names = {
        "always_strong": "Always strong",
        "always_cheap": "Always cheap",
        "router": "Router",
    }
    for key, label in names.items():
        v = summary["strategies"][key]
        q = "n/a" if v["quality"] is None else f"{v['quality']:.2f}"
        lines.append(
            f"| {label} | {v['cost']:.4f} | {v['saving_pct']:.1f}% | {q} | {v['words']:.0f} |"
        )
    head = summary.get("head_to_head")
    if head:
        lines += [
            "",
            "Head-to-head: a judge sees the cheap and strong answer in random order and picks the better one.",
            "",
            "| Router sent the question to | Questions | Cheap better | Tie | Strong better |",
            "|---|---|---|---|---|",
        ]
        for key, label in (("routed_cheap", "Cheap model"), ("routed_strong", "Strong model")):
            h = head[key]
            total = h["cheap"] + h["tie"] + h["strong"]
            lines.append(f"| {label} | {total} | {h['cheap']} | {h['tie']} | {h['strong']} |")
    lines += ["", f"Router agreement with my easy/hard labels: {summary['agreement_pct']:.0f}%"]
    return "\n".join(lines)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    qs, res = run(args.limit)
    pairs = run_pairwise(qs, res)
    if is_complete(qs, res) and pairs_complete(qs, pairs):
        text = to_markdown(summarize(qs, res, pairs), len(qs))
        SUMMARY.write_text(text + "\n", encoding="utf-8")
        print()
        print(text)
    else:
        print(
            f"\nProgress: {len(res)} of {2 * len(qs)} answers, "
            f"{len(pairs)} of {len(qs)} head-to-head. Run the same command again later."
        )
