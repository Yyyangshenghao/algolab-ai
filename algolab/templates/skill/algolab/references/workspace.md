# Workspace

## Repository Mode

- This is a repository-local workflow. Do not install the skill globally unless the user explicitly asks.
- `AGENTS.md` and `CLAUDE.md` are the root agent entrypoints.
- `docs/AGENTS_zh.md` and `docs/README_zh.md` are human-readable companions, not default agent imports.

## Discovery

- Read `.algolab/index.json` before scanning `problems/`.
- Use stable numeric IDs for lookup and testing.
- Open a full problem directory only after selecting a target ID or slug.
- Avoid generated caches, `__pycache__`, large logs, and unrelated historical records.

## Current Workspace

Use `python3 -m algolab current <id-or-slug>` when the user says "切到", "打开", "当前做", "继续", "focus", or similar.

After a fresh clone, `current/` is absent because it is ignored. Run `python3 -m algolab current` to rebuild it from `.algolab/index.json` and the current or latest indexed problem.

`current/` must stay minimal:

```text
current/
  problem.md
  TESTS.md
  tests/
  solutions/<language>/
```

Do not add `records/`, report aliases, package import bridges, or metadata aliases to `current/`.

`current/TESTS.md` is a local generated command file. It may contain absolute paths for this checkout and should contain two command blocks only:

- direct command for the current problem
- variable command with `PROBLEM_ID` and `LANGUAGE`

## IDEA

If `.idea/` exists, refresh the stable Java module with `python3 -m algolab refresh-idea`.

- IDEA source root: `current/solutions/java`
- Open Java files through `current/solutions/java/Solution.java`.
- Do not create per-problem IDEA modules.

## Helper Commands

- `python3 -m algolab refresh-tests`
- `python3 -m algolab doctor`
- `python3 -m algolab stats`
