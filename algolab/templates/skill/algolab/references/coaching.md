# Coaching

## Review And Debugging

- Ask the user to explain their approach before revealing a full solution unless they explicitly request the answer.
- Prefer hints, invariants, counterexamples, complexity analysis, and targeted debugging over complete code.
- Focus feedback on invariants, state definitions, transitions, greedy choice, complexity, and failure cases.
- Explain failures using the smallest useful counterexample.

## Records

Use compact machine-readable attempts when appropriate:

```bash
python3 -m algolab record current --status pass|fail|partial|skip --notes "..."
```

Use `records/review.md` only when the user asks for a durable human-readable review.

Do not overwrite historical records unless explicitly asked.

## Recommendations

For "推荐下一题":

1. Inspect `.algolab/index.json`.
2. Read only relevant attempts or reviews.
3. Identify the target weakness.
4. Suggest or create a follow-up problem.

Avoid scanning every historical problem directory.
