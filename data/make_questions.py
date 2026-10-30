import json

easy = [
    "What is the capital of Japan?",
    "Who wrote Hamlet?",
    "Define photosynthesis in one sentence.",
    "How many days are in a leap year?",
    "Translate \"good morning\" to Spanish.",
    "What does CPU stand for?",
    "When did World War II end?",
    "What is 15% of 200?",
    "Name three primary colors.",
    "What is the boiling point of water in Celsius?",
    "Who painted the Mona Lisa?",
    "What is the largest planet in the solar system?",
    "Convert 5 kilometers to miles.",
    "What does HTTP stand for?",
    "Give me a synonym for \"happy\".",
    "What is the chemical symbol for gold?",
    "Write a one-line greeting for a birthday card.",
    "What is the square root of 144?",
    "Which language is used for styling web pages?",
    "What does an API do, in one sentence?",
    "Fix the spelling: \"recieve the pakage\".",
    "What is the plural of \"mouse\" (the animal)?",
    "What time zone is Cairo in?",
    "What is a noun?",
    "Name the longest river in Africa.",
    "What is the difference between \"affect\" and \"effect\"?",
    "Summarize in one sentence: The meeting is moved from Monday to Wednesday because the manager is travelling.",
    "What is Git used for?",
    "Give a short definition of machine learning.",
    "How many bytes are in a kilobyte?",
]

hard = [
    "Compare a B-tree index and a hash index in a database and explain when each one is better.",
    "Explain why gradient descent can get stuck at saddle points and how momentum helps.",
    "Design a rate limiter for an API used by 10 million users and explain the trade-offs.",
    "Debug this Python code and explain the bug:\n```python\ndef avg(xs):\n    return sum(xs) / len(xs)\nprint(avg([]))\n```",
    "Analyze the pros and cons of microservices versus a monolith for a 5-person startup.",
    "Prove that the sum of two even integers is even, step by step.",
    "Write a Python function that merges overlapping intervals and explain its time complexity.",
    "Explain the difference between L1 and L2 regularization and how each one affects the weights of a linear model.",
    "Optimize this SQL query and explain why it is slow: SELECT * FROM orders WHERE YEAR(created_at) = 2025 AND customer_id IN (SELECT id FROM customers WHERE country = 'EG');",
    "Compare RAG and fine-tuning for adding company knowledge to an LLM, and say when to choose each.",
    "A model has 99% accuracy on a fraud dataset where 0.5% of cases are fraud. Explain why this may be misleading and which metrics to use instead.",
    "Explain how the Raft consensus algorithm elects a leader, step by step.",
    "Design a database schema for a ride sharing app and explain your choices.",
    "Refactor this function to be easier to test and explain what you changed:\n```python\ndef report():\n    import requests\n    r = requests.get(\"http://x.com/data\")\n    print(sum(r.json()))\n```",
    "Derive the gradient of the mean squared error loss with respect to the weights of a linear regression model.",
    "Analyze why transformer attention is quadratic in sequence length and name two ways to reduce that cost.",
    "Compare Docker containers and virtual machines in terms of isolation, performance and security.",
    "Explain the trade-off between consistency and availability in a distributed database during a network partition.",
    "Implement an LRU cache in Python and explain how you made get and put O(1).",
    "Explain step by step how to choose between precision and recall for a cancer screening model.",
]

items = [{"id": i + 1, "question": q, "label": "easy"} for i, q in enumerate(easy)]
items += [{"id": len(easy) + i + 1, "question": q, "label": "hard"} for i, q in enumerate(hard)]
assert len(items) == 50

with open("data/questions.json", "w", encoding="utf-8") as f:
    json.dump(items, f, indent=2, ensure_ascii=False)
