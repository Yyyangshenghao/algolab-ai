from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import solution_path_for


def run_case(problem_dir: Path, interface: dict[str, Any], case: dict[str, Any]) -> Any:
    solution_path = solution_path_for(problem_dir, "go")
    if not solution_path.is_file():
        raise RuntimeError(f"missing Go solution: {solution_path}")
    raise RuntimeError(
        "Go runner is scaffolded but not implemented yet; "
        "expected flow: generate a temporary Go harness, run with go test or go run, parse JSON output"
    )
