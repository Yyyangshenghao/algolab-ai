# Problem Authoring

## Default Role

Act as a problem setter and coach. "出一道题" means create the exercise, tests, and starter files; it does not mean solve it.

Do not provide a full working solution or fill `solutions/<language>/` unless the user explicitly asks for the answer or implementation.

## Creation Workflow

1. Use `python3 -m algolab new ...` to allocate the next stable ID.
2. Write a localized `problem.md` with statement, input contract, output contract, constraints, examples, and notes.
3. Write `tests/interface.json` with `entrypoint`, argument names, argument types, return type, and `type_system`.
4. Keep the statement, interface, and cases language-neutral unless the user asks for a language-specific exercise.
5. Add `tests/oracle.py` and `tests/generator.py` when correctness or coverage benefits from deterministic generated cases.
6. Create starter placeholders under `solutions/<language>/`; placeholders may include signatures and `TODO`/throwing stubs only.
7. Ensure `.algolab/index.json` `max_id`, `last_problem_id`, and `current_problem_id` are current.
8. Refresh `current/` and `current/TESTS.md`.
9. Record unresolved assumptions in `records/test-analysis.md`.

## Language Support

Read `.algolab/config.json`:

- `supported_solution_languages`: allowed solution folders
- `runner_languages`: locally judgeable languages
- `runner_dir`: runner adapter directory

Default solution languages: `c`, `cpp`, `java`, `go`, `python`, `rust`.

Currently implemented local runners: `python`, `java`.
