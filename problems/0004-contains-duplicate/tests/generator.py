"""Deterministic generated test cases for 0004-contains-duplicate.

Keep large LeetCode-style judge sets generated, not hand-written in cases.json.
"""

from __future__ import annotations

import argparse
import json
import random
from typing import Any


def generate(seed: int = 0, count: int = 100) -> dict:
    rng = random.Random(seed)
    cases: list[dict[str, Any]] = []

    # 固定示例
    cases.append(
        {
            "name": "generated-example-1",
            "input": {"args": [[1, 2, 3, 1]]},
            "expected": True,
            "compare": "exact",
            "tags": ["generated", "example"],
        }
    )
    cases.append(
        {
            "name": "generated-example-2",
            "input": {"args": [[1, 2, 3, 4]]},
            "expected": False,
            "compare": "exact",
            "tags": ["generated", "example"],
        }
    )

    idx = 0
    while len(cases) < count:
        n = rng.randint(1, 60)
        has_dup = rng.random() < 0.5
        nums = list(range(n))
        if has_dup and n >= 2:
            duplicate_base = rng.randrange(n)
            duplicate_pos = rng.randrange(1, n)
            nums[duplicate_pos] = nums[0] if duplicate_pos != 0 else nums[1]
        else:
            nums = list(range(n))
            rng.shuffle(nums)
        has_dup = len(nums) != len(set(nums))

        cases.append(
            {
                "name": f"generated-{idx}",
                "input": {"args": [nums]},
                "expected": has_dup,
                "compare": "exact",
                "tags": ["generated"],
            }
        )
        idx += 1

    return {"version": 1, "cases": cases[:count]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--count", type=int, default=100)
    args = parser.parse_args()
    print(json.dumps(generate(seed=args.seed, count=args.count), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
