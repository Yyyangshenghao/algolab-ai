from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from .common import case_arguments, solution_path_for


def load_solution(problem_dir: Path, entrypoint: str):
    solution_path = solution_path_for(problem_dir, "python")
    if not solution_path.is_file():
        raise RuntimeError(f"missing Python solution: {solution_path}")
    spec = importlib.util.spec_from_file_location(f"algolab_solution_{problem_dir.name}", solution_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import Python solution from {solution_path}")
    module = importlib.util.module_from_spec(spec)
    import_paths = [str(solution_path.parent), str(problem_dir)]
    for import_path in reversed(import_paths):
        sys.path.insert(0, import_path)
    try:
        spec.loader.exec_module(module)
    finally:
        for import_path in import_paths:
            try:
                sys.path.remove(import_path)
            except ValueError:
                pass
    solve = getattr(module, entrypoint, None)
    if not callable(solve):
        raise RuntimeError(f"Python solution must define callable `{entrypoint}`")
    return solve


def run_case(problem_dir: Path, interface: dict[str, Any], case: dict[str, Any]) -> Any:
    entrypoint = str(interface.get("entrypoint") or "solve")
    args_value, kwargs_value = case_arguments(case)
    solve = load_solution(problem_dir, entrypoint)
    return solve(*args_value, **kwargs_value)


def run_cases(
    problem_dir: Path,
    interface: dict[str, Any],
    cases: list[dict[str, Any]],
    *,
    fail_fast: bool = False,
    case_timeout: float = 0,
) -> list[Any]:
    if case_timeout > 0:
        payload = {
            "problem_dir": str(problem_dir),
            "interface": interface,
            "cases": cases,
            "case_timeout": case_timeout,
            "fail_fast": fail_fast,
        }
        batch_timeout = max(10.0, (case_timeout * max(len(cases), 1)) + 5.0)
        result = subprocess.run(
            [sys.executable, "-m", "algolab.runners.python_worker"],
            input=json.dumps(payload, ensure_ascii=False),
            capture_output=True,
            text=True,
            timeout=batch_timeout,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout).strip())
        data = json.loads(result.stdout)
        values: list[Any] = []
        for item in data.get("results", []):
            if item.get("ok"):
                values.append(item.get("value"))
            else:
                values.append(RuntimeError(str(item.get("error", "Python solution failed"))))
        return values

    entrypoint = str(interface.get("entrypoint") or "solve")
    solve = load_solution(problem_dir, entrypoint)
    results: list[Any] = []
    for case in cases:
        args_value, kwargs_value = case_arguments(case)
        try:
            results.append(solve(*args_value, **kwargs_value))
        except Exception as exc:  # noqa: BLE001 - preserve per-case user solution errors.
            results.append(exc)
            if fail_fast:
                break
    return results
