from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import solution_path_for


def run_case(problem_dir: Path, interface: dict[str, Any], case: dict[str, Any]) -> Any:
    solution_path = solution_path_for(problem_dir, "cpp")
    if not solution_path.is_file():
        raise RuntimeError(f"missing C++ solution: {solution_path}")
    raise RuntimeError(
        "C++ runner is scaffolded but not implemented yet; "
        "expected flow: generate a temporary C++ harness, compile with c++, clang++, or g++, run with JSON input, parse JSON output"
    )
