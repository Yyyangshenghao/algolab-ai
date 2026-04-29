# AlgoLab Workspace

This repository is a local algorithm-practice workspace. Users interact with the AI agent in natural language; they should not need to run commands manually.

## Distribution

- This repository is meant to be cloned from GitHub and opened at the repo root in Codex, Claude Code, or another AI coding tool.
- Do not require users to install global skills, plugins, or MCP servers for the default workflow.
- `skills/algolab/SKILL.md` is a repository-local workflow spec. Do not copy it into a user's global skill directory unless explicitly requested.
- `docs/AGENTS_zh.md` is a Chinese human-readable companion. Do not import it by default.

## Workflow

- For AlgoLab tasks such as creating problems, generating tests, running checks, reviewing failures, or recommending next practice, read `skills/algolab/SKILL.md` first.
- If `current/` is missing after a fresh clone, run `python3 -m algolab current` to rebuild the local active-problem workspace.
- The user-facing interface is natural language. If helper scripts are useful, the agent should run them and summarize the result.
- `python3 -m algolab ...` commands are internal helper tools for agents, not the product interface for users.
- Do not hand off command-line steps to the user unless the user asks for commands.
- Problems and tests are language-neutral. Solutions should live under `solutions/<language>/` when possible.
- Enabled solution languages come from `.algolab/config.json` `supported_solution_languages`.
- Every managed problem has a stable numeric ID. Prefer that ID for testing and lookup.
- `current/TESTS.md` is the compact local test command sheet; keep the latest direct command plus the `PROBLEM_ID`/`LANGUAGE` variable command, but do not list all problems there.
- After a current problem is selected, prefer paths under `current/` for day-to-day work. Treat `problems/` as the persistent backing store.
- Avoid full-repo or full-problem scans as the collection grows. Use `.algolab/index.json` and targeted paths first.

## Internal Helpers

- Initialize: `python3 -m algolab init .`
- Create problem skeleton: `python3 -m algolab new --slug <slug> --title "<title>" --topic <topic> --difficulty easy|medium|hard --solution-language <language>`
- Run local tests by ID: `python3 -m algolab test <id> --language <runner-language> --generated --generated-count 200 --generated-seed 0 --fail-fast --case-timeout 3 --jobs 4 --batch-size 25 --report-md`
- Switch current problem workspace: `python3 -m algolab current <id-or-slug>`
- Append test inventory: `python3 -m algolab analyze-tests <id>`
- Record attempt: `python3 -m algolab record <id> --status pass|fail|partial|skip --notes "..."`
- Check structure: `python3 -m algolab doctor`
- Refresh current test commands: `python3 -m algolab refresh-tests`
- Refresh local IDEA Java module: `python3 -m algolab refresh-idea`
- Show progress: `python3 -m algolab stats`

## Rules

- Default role is problem setter and coach, not answer generator. Do not provide a full working solution or fill in `solutions/<language>/` unless the user explicitly asks for the answer or implementation.
- For discovery, read `.algolab/index.json` before listing or opening many files under `problems/`.
- Only read a full problem directory after selecting a target ID or slug.
- Before changing an existing problem, read `problem.md`, `meta.json`, `tests/interface.json`, `tests/cases.json`, and relevant files in `records/`.
- Do not overwrite the user's `solution.*` or historical records unless explicitly asked; append records instead.
- When creating a problem, allocate the next ID, update `.algolab/index.json` `max_id` and `last_problem_id`, refresh `current/TESTS.md`, and include statement, constraints, examples, test strategy, and starter cases.
- `current` is a minimal active-problem workspace. It should contain only `problem.md`, `tests/`, `solutions/`, and a local `TESTS.md` command file. Do not add `records/`, report aliases, package bridges, or metadata aliases there. Use it when the user says to switch, open, focus, or continue a problem workspace. Do not ask the user to run the command; run `algolab current <id-or-slug>` yourself.
- Starter solution files are placeholders only. They may contain signatures and `TODO`/throwing stubs, but must not contain the intended algorithm.
- Do not bake a single programming language into the problem statement unless the user asks for a language-specific exercise.
- Tests should be language-neutral: `tests/interface.json` defines the callable contract, and `tests/cases.json` stores values.
- When adding tests, cover examples, boundaries, degenerate inputs, randomized or constructed cases, and counterexamples.
- The agent should run relevant local checks itself and report the result in natural language.
- Only languages listed in `runner_languages` have local runners. Current implemented runners are Python and Java.
- Runner adapters live under `algolab/runners/<language>.py` and expose `run_case(...)`; for performance, add `run_cases(...)`.
- Local tests default to fail-fast. Stop scheduling more batches after the first compile error, runner error, timeout, or failed case.
- A single case has a default 3 second timeout. Treat timeout as an algorithmic complexity failure unless the user explicitly changes `--case-timeout`.
- If `.idea/` exists, IDEA uses one stable module at `current/solutions/java`; switching problems refreshes the active solution symlink instead of creating per-problem modules. Open Java files through `current/solutions/java/Solution.java`, not `problems/.../solutions/java`, for IDE source-root behavior.
- Do not load generated caches, `__pycache__`, large logs, or unrelated historical records unless needed for the current request.

## Internationalization

- Read `.algolab/config.json` `i18n.ui_locale` for replies and `i18n.problem_locale` for new problem statements.
- Write the chosen problem language to `meta.json.locale`.
- Localize user-facing prose: problem statements, hints, explanations, reviews, and test analysis.
- Keep machine fields stable in English: JSON keys, directory names, slugs, statuses, compare modes, and script interfaces.
- If the user specifies a language for a task, follow that request and record it in `meta.json.locale` or the relevant record.
