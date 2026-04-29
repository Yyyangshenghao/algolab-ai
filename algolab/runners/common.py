from __future__ import annotations

from pathlib import Path
from typing import Any


def solution_path_for(problem_dir: Path, language: str) -> Path:
    if language == "python":
        scoped = problem_dir / "solutions" / "python" / "solution.py"
        if scoped.is_file():
            return scoped
        return problem_dir / "solution.py"
    paths = {
        "c": problem_dir / "solutions" / "c" / "solution.c",
        "cpp": problem_dir / "solutions" / "cpp" / "solution.cpp",
        "java": problem_dir / "solutions" / "java" / "Solution.java",
        "go": problem_dir / "solutions" / "go" / "solution.go",
        "rust": problem_dir / "solutions" / "rust" / "solution.rs",
    }
    if language in paths:
        return paths[language]
    raise RuntimeError(f"unsupported solution language: {language}")


def case_arguments(case: dict[str, Any]) -> tuple[list[Any], dict[str, Any]]:
    case_input = case.get("input", {})
    args_value = case_input.get("args", []) if isinstance(case_input, dict) else []
    kwargs_value = case_input.get("kwargs", {}) if isinstance(case_input, dict) else {}
    if not isinstance(args_value, list) or not isinstance(kwargs_value, dict):
        raise RuntimeError("case input must contain list `args` and object `kwargs`")
    return args_value, kwargs_value
