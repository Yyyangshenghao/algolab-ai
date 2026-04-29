"""Deterministic generated test cases for {{slug}}.

Keep large LeetCode-style judge sets generated, not hand-written in cases.json.
"""

from __future__ import annotations

import argparse
import json
import random


def generate(seed: int = 0, count: int = 100) -> dict:
    rng = random.Random(seed)
    _ = rng
    _ = count
    return {"version": 1, "cases": []}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--count", type=int, default=100)
    args = parser.parse_args()
    print(json.dumps(generate(seed=args.seed, count=args.count), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
