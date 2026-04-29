---
name: algolab
description: Use when working in a local algorithm practice workspace: creating LeetCode-style problems, generating test cases, running local checks, recording attempts, reviewing failures, switching the current problem workspace, or coaching algorithm practice with files under problems/.
---

# AlgoLab

Use this repository-local skill for AlgoLab workspaces. The user interacts in natural language; helper commands are internal tools for the agent unless the user explicitly asks for commands.

## First Steps

1. Find the workspace root by locating `.algolab/config.json`.
2. Read `AGENTS.md` or `CLAUDE.md` if present.
3. Read `.algolab/index.json` before scanning `problems/`.
4. Select a target ID or slug before opening a full problem directory.
5. Load only the reference file needed for the current intent.

## Core Guardrails

- Default role: problem setter and coach, not answer generator.
- Do not provide a full working solution or fill `solutions/<language>/` unless the user explicitly asks for the answer or implementation.
- Do not overwrite `solution.*` or `records/*` unless explicitly asked; append records instead.
- Do not ask the user to run commands unless they request command-line instructions.
- Keep `current/` minimal: `problem.md`, `tests/`, `solutions/`, and local `TESTS.md` only.
- Do not add `records/`, report aliases, package bridges, or metadata aliases to `current/`.
- Avoid generated caches, `__pycache__`, large logs, and unrelated historical records.
- Use `.algolab/config.json` `i18n` for user-facing language.

## Intent Routing

- Workspace discovery, switching current problem, command paths, IDEA behavior: read [workspace.md](references/workspace.md).
- New problem, statement, metadata, starter files, no-answer policy: read [problem-authoring.md](references/problem-authoring.md).
- Test cases, generators, oracle, reports, fail-fast, timeouts: read [testing.md](references/testing.md).
- Language runner contracts, Java/Python details, adding runners: read [runners.md](references/runners.md).
- Review, debugging, attempt records, recommendations: read [coaching.md](references/coaching.md).
- Locale-specific output rules: read [i18n.md](references/i18n.md).

## Common Helper Commands

- Create problem: `python3 -m algolab new --slug <slug> --title "<title>" --topic <topic> --difficulty easy|medium|hard --solution-language <language>`
- Switch current workspace: `python3 -m algolab current <id-or-slug>`
- Run tests: `python3 -m algolab test <id|current> --language <runner-language> --generated --fail-fast --case-timeout 3 --jobs 4 --batch-size 25 --report-md`
- Refresh local test commands: `python3 -m algolab refresh-tests`
- Append test inventory: `python3 -m algolab analyze-tests <id|current>`
- Record attempt: `python3 -m algolab record <id|current> --status pass|fail|partial|skip --notes "..."`
- Check structure: `python3 -m algolab doctor`
- Show progress: `python3 -m algolab stats`

These commands are for agents. Keep the user-facing workflow natural-language first.
