# AlgoLab AI

AlgoLab AI is a repository-local LeetCode-style practice workspace for AI coding agents. Clone the repo, open the repo root in Codex, Claude Code, or another AI coding tool, and use natural language to create problems, write tests, run checks, and keep review records.

No global skill, plugin, or MCP installation is required for the default workflow.

## Quick Start

1. Clone this repository.
2. Open the repository root in your AI coding tool.
3. Ask the agent for an AlgoLab task in natural language.

Example prompts:

- `给我出一道中等难度动态规划题，用 Python 作为默认解法语言。`
- `切到 0004，接下来我只在 current 目录里做。`
- `帮我给 longest-stable-subarray 补充边界测试。`
- `跑一下这道题的本地测试，并分析失败原因。`
- `根据最近的错题记录，推荐下一道练习题。`
- `用 C++ 新建一道滑动窗口题，但暂时不用跑本地判题。`

By default, the agent acts as a problem setter and coach, not as an answer generator. Creating a problem should not include a full working solution unless you explicitly ask for the answer or implementation.

The agent should read `AGENTS.md` first. Claude Code reads `CLAUDE.md`, which imports `AGENTS.md`. For AlgoLab-specific work, the agent then reads the local `skills/algolab/SKILL.md`.

Chinese documentation is available in `docs/README_zh.md`; the Chinese agent companion is `docs/AGENTS_zh.md`, but it is not imported by default.

## What The Agent Does

When you ask for a new problem, the agent creates a folder under `problems/<id>-<slug>/` with:

- `problem.md`: statement, constraints, examples, and notes.
- `meta.json`: stable metadata for discovery and indexing.
- `tests/interface.json`: language-neutral function contract.
- `tests/cases.json`: language-neutral test cases.
- `tests/generator.py` and `tests/oracle.py`: optional deterministic generation and trusted checking helpers.
- `records/`: generated reports, test analysis, and optional attempt/review notes.
- `solutions/<language>/`: your solution workspace.

The Python helper CLI exists for agents, not for users. The agent may call `python3 -m algolab ...` internally to keep the structure consistent, run local checks, and update records.

## Problem IDs And TESTS.md

Every managed problem receives a stable numeric ID such as `0003`.

- `.algolab/index.json` stores the catalog, `max_id`, and `last_problem_id`.
- `current/TESTS.md` is a local command sheet for the active problem and may contain absolute paths for this checkout.
- New problems created by the helper update both files automatically.
- Existing legacy folders can still be resolved by slug, but ID is the preferred test target.

After a problem is created, `current/TESTS.md` shows two command blocks: a direct command for the active problem, and a variable-based command you can edit:

```bash
python3 -m algolab test current --language java --generated --generated-count 200 --generated-seed 0 --fail-fast --case-timeout 3 --jobs 4 --batch-size 25 --report-md
```

```bash
PROBLEM_ID="current"
LANGUAGE="java"

python3 -m algolab test "$PROBLEM_ID" --language "$LANGUAGE" --generated --generated-count 200 --generated-seed 0 --fail-fast --case-timeout 3 --jobs 4 --batch-size 25 --report-md
```

## Language Support

Solution languages are controlled by `.algolab/config.json`.

- `supported_solution_languages`: languages the workspace can create solution folders for.
- `runner_languages`: languages the local helper can judge today.
- `runner_dir`: relative path for language runner adapters.

Default solution languages:

- C: `solutions/c/solution.c`
- C++: `solutions/cpp/solution.cpp`
- Java: `solutions/java/Solution.java`
- Go: `solutions/go/solution.go`
- Python: `solutions/python/solution.py`
- Rust: `solutions/rust/solution.rs`

Current implemented local runners: Python and Java.

For C, C++, Go, and Rust, the workspace can create solution files now. Local judging runners for those languages are intentionally tracked separately and should be added later.

Runner files live at:

```text
algolab/runners/
  python.py
  java.py
  common.py
```

Future runners should use this convention:

```text
algolab/runners/c.py
algolab/runners/cpp.py
algolab/runners/go.py
algolab/runners/rust.py
```

Each runner module exposes:

```python
def run_case(problem_dir, interface, case):
    ...
```

## Running Tests Manually

Users can run the same helper command the agent uses. The easiest path is to open `current/TESTS.md`; use the latest direct command, or edit `PROBLEM_ID` and `LANGUAGE` in the variable command.

Run Java tests:

```bash
python3 -m algolab test <id> --language java
```

Run Java tests and write a Markdown report:

```bash
python3 -m algolab test <id> --language java --generated --generated-count 200 --generated-seed 0 --fail-fast --case-timeout 3 --jobs 4 --batch-size 25 --report-md
```

The report path is written into `current/TESTS.md` as an absolute path, typically under:

```text
problems/<id>-<slug>/records/test-results.md
```

By default, tests stop scheduling new batches after the first compile error, runner error, timeout, or failed case. Each individual case has a 3 second timeout; use `--no-fail-fast` or `--case-timeout <seconds>` only when you intentionally need different behavior.

The report contains a compact table with each executed case, status, expected value, and actual value.

## IntelliJ IDEA

Java practice files use LeetCode-style default-package `Solution.java` classes. To avoid duplicate `Solution` class conflicts across problems, AlgoLab keeps one local minimal `current` workspace, and IDEA uses one stable module at `current/solutions/java`.

For normal use, stay inside `current/`:

```text
current/
  problem.md
  TESTS.md
  tests/
  solutions/<language>/
```

The real `problems/<id>-<slug>/` folder remains the backing store. Open Java files through `current/solutions/java/Solution.java` so IDEA treats them as source files. `records/`, reports, package bridges, and metadata aliases are intentionally not mirrored into `current/`.

Switch the active problem workspace:

```bash
python3 -m algolab current <id-or-slug>
```

Refresh the stable IDEA module after manual folder changes:

```bash
python3 -m algolab refresh-idea
```

`algolab new` switches `current` to the new problem and refreshes the IDEA module automatically when `.idea/` exists.

Java solution contract:

- Backing file: `solutions/java/Solution.java`
- Current workspace file: `current/solutions/java/Solution.java`
- Class: `public class Solution`
- Method name: `tests/interface.json` `entrypoint`, usually `solve`
- No Java package declaration
- Use array types for `list<T>`, for example `list<int>` maps to `int[]`

## Test Model

Tests are intentionally not duplicated per language.

- `tests/interface.json` defines the callable contract: entrypoint, argument names, argument types, return type, and type-system version.
- `tests/cases.json` stores a small readable set of language-neutral input/output values.
- `tests/oracle.py` stores a slow trusted implementation when useful.
- `tests/generator.py` deterministically generates large hidden-style judge cases without storing hundreds of rows in JSON.
- Language runners are adapters: they read the same interface and cases, call the solution in that language, and compare the result.

Use positional `input.args` in cases by default. `input.kwargs` is allowed for Python-specific workflows, but portable problems should avoid it.

Generated case scripts must accept:

```bash
python3 tests/generator.py --seed 0 --count 200
```

and print JSON in the same shape as `tests/cases.json`.

For larger generated suites, `test` supports batch parallelism:

```bash
python3 -m algolab test <id> --language java --generated --fail-fast --case-timeout 3 --jobs 4 --batch-size 25
```

Java uses a batch harness so each batch compiles once instead of compiling every case.

Current portable type vocabulary:

- `int`, `long`, `float`, `bool`, `string`
- `list<T>`
- `map<K,V>`
- `tuple<T1,T2,...>`
- `optional<T>`

## Scaling

The repository is designed to grow without forcing the agent to read every historical file.

- `.algolab/index.json` is the lightweight catalog for discovery, stats, and recommendations.
- The agent should read the index first, then open a full problem folder only after selecting a target ID or slug.
- Generated caches, large logs, and unrelated historical records should not be loaded unless the current task needs them.
- `python3 -m algolab doctor` checks for stale index entries or unindexed problem directories.

## Internationalization

Localization is part of the workspace contract.

- `i18n.ui_locale`: default language for agent replies.
- `i18n.problem_locale`: default language for new problem statements.
- `meta.json.locale`: language used by a specific problem.

User-facing prose is localized. Machine-readable fields stay stable in English: JSON keys, directory names, slugs, statuses, compare modes, and script interfaces.

## Problem Layout

```text
problems/<id>-<slug>/
  problem.md
  meta.json
  solutions/
    c/solution.c
    cpp/solution.cpp
    java/Solution.java
    go/solution.go
    python/solution.py
    rust/solution.rs
  tests/
    interface.json
    cases.json
    generator.py
    oracle.py
  records/
    test-analysis.md
    test-results.md
    attempts.jsonl  # optional, created by --record
    review.md       # optional, created during review
```

## Configuration

Edit `.algolab/config.json` to change defaults:

```json
{
  "default_solution_language": "python",
  "supported_solution_languages": ["c", "cpp", "java", "go", "python", "rust"],
  "runner_languages": ["python", "java"],
  "runner_dir": "algolab/runners",
  "i18n": {
    "ui_locale": "zh-CN",
    "problem_locale": "zh-CN"
  }
}
```

## Design Principle

The durable interface is the file structure and repository-local AI workflow spec. Scripts are implementation details that make agent actions repeatable and auditable.

Problems and test cases should stay language-neutral unless the user explicitly asks for a language-specific exercise.
