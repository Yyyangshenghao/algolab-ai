from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any


class RunnerError(RuntimeError):
    pass


def load_runner(language: str):
    try:
        return importlib.import_module(f"algolab.runners.{language}")
    except ModuleNotFoundError as exc:
        if exc.name == f"algolab.runners.{language}":
            raise RunnerError(f"local runner for `{language}` is not implemented yet") from exc
        raise


def run_case(problem_dir: Path, language: str, interface: dict[str, Any], case: dict[str, Any]) -> Any:
    runner = load_runner(language)
    return runner.run_case(problem_dir, interface, case)


def run_cases(
    problem_dir: Path,
    language: str,
    interface: dict[str, Any],
    cases: list[dict[str, Any]],
    *,
    fail_fast: bool = False,
    case_timeout: float = 0,
) -> list[Any]:
    runner = load_runner(language)
    if hasattr(runner, "run_cases"):
        return runner.run_cases(problem_dir, interface, cases, fail_fast=fail_fast, case_timeout=case_timeout)
    results: list[Any] = []
    for case in cases:
        try:
            results.append(runner.run_case(problem_dir, interface, case))
        except Exception as exc:  # noqa: BLE001 - preserve runner errors as case results.
            results.append(exc)
            if fail_fast:
                break
    return results
