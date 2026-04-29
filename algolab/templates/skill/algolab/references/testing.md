# Testing

## Test Model

Tests are language-neutral.

- `tests/interface.json`: callable contract
- `tests/cases.json`: small readable input/output values
- `tests/oracle.py`: slow trusted checker when useful
- `tests/generator.py`: deterministic judge-style generated cases

Prefer `input.args`. Use `input.kwargs` only for Python-specific workflows.

## Case Design

Cover:

- examples
- boundaries
- degenerate inputs
- adversarial or counterexample cases
- randomized or constructed oracle-checked cases

Keep `tests/cases.json` readable. Put large coverage in `tests/generator.py` instead of storing hundreds of cases in JSON.

Use `compare: "exact"` by default. Use `unordered_list` or `any_of` only when the output contract allows multiple valid outputs.

`tests/generator.py` must accept `--seed` and `--count`, print JSON shaped like `tests/cases.json`, and use deterministic randomness.

## Running

Default run shape:

```bash
python3 -m algolab test current --language <runner-language> --generated --generated-count 200 --generated-seed 0 --fail-fast --case-timeout 3 --jobs 4 --batch-size 25 --report-md
```

Use `current/TESTS.md` when giving human-readable command guidance. Its report path may be absolute and checkout-specific.

Local tests default to fail-fast:

- stop on compile errors
- stop on runner errors
- stop on first failed case
- stop on case timeout

A single case has a default 3 second timeout. Treat timeout as an algorithmic complexity failure unless the user explicitly changes `--case-timeout`.

After editing `tests/cases.json` or `tests/generator.py`, run:

```bash
python3 -m algolab analyze-tests current
python3 -m algolab test current --generated --fail-fast --case-timeout 3 --jobs 4 --batch-size 25
```
