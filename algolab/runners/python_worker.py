from __future__ import annotations

import json
import signal
import sys
from pathlib import Path
from typing import Any

from .common import case_arguments
from .python import load_solution


def timeout_handler(_signum: int, _frame: Any) -> None:
    raise TimeoutError("case exceeded the configured timeout")


def run_payload(payload: dict[str, Any]) -> dict[str, Any]:
    problem_dir = Path(str(payload["problem_dir"]))
    interface = payload.get("interface") or {}
    cases = payload.get("cases") or []
    case_timeout = float(payload.get("case_timeout") or 0)
    fail_fast = bool(payload.get("fail_fast"))
    entrypoint = str(interface.get("entrypoint") or "solve")
    solve = load_solution(problem_dir, entrypoint)

    results: list[dict[str, Any]] = []
    if case_timeout > 0:
        signal.signal(signal.SIGALRM, timeout_handler)

    for case in cases:
        args_value, kwargs_value = case_arguments(case)
        try:
            if case_timeout > 0:
                signal.setitimer(signal.ITIMER_REAL, case_timeout)
            value = solve(*args_value, **kwargs_value)
        except BaseException as exc:  # noqa: BLE001 - user solution failures are case results.
            results.append({"ok": False, "error": f"{type(exc).__name__}: {exc}"})
            if fail_fast:
                break
        else:
            results.append({"ok": True, "value": value})
        finally:
            if case_timeout > 0:
                signal.setitimer(signal.ITIMER_REAL, 0)

    return {"results": results}


def main() -> int:
    payload = json.loads(sys.stdin.read())
    json.dump(run_payload(payload), sys.stdout, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
