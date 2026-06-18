#!/usr/bin/env python3
"""Test the silent-recovery guard (#3): repeated_failure detection.

Run directly: `python3 tests/test_recovery.py`. Verifies one-off failures stay
quiet, the same failure class repeating >=2 discloses, path/number variants
normalize to the same class, and the threshold is honoured.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "gate"))


def main() -> int:
    from parse_tool_result import repeated_failure

    failures: list[str] = []

    # empty / single occurrence => quiet (None)
    if repeated_failure([]) is not None:
        failures.append("empty should be None")
    one = [{"kind": "tool-result", "summary": "ECONNREFUSED localhost:5432"}]
    if repeated_failure(one) is not None:
        failures.append("single occurrence should be None (recover quietly)")

    # same class x2 => discloses (sig, 2)
    two = [
        {"summary": "build FAILED — ECONNREFUSED localhost:5432"},
        {"summary": "build FAILED — ECONNREFUSED localhost:5432"},
    ]
    r = repeated_failure(two)
    if not r or r[1] != 2:
        failures.append(f"2x same class should be (sig, 2), got {r}")

    # numbers/paths vary but same class => still grouped
    variants = [
        {"summary": "build FAILED — ECONNREFUSED localhost:5432"},
        {"summary": "build FAILED — ECONNREFUSED localhost:9999"},
    ]
    rv = repeated_failure(variants)
    if not rv or rv[1] != 2:
        failures.append(f"normalized variants should count as same class, got {rv}")

    # distinct most-recent class => quiet
    diff = [
        {"summary": "SyntaxError: invalid syntax"},
        {"summary": "ECONNREFUSED localhost:5432"},
    ]
    if repeated_failure(diff) is not None:
        failures.append("distinct last-class (count 1) should be None")

    # threshold respected: 2 occurrences but threshold=3 => quiet
    two_same = [{"summary": "err X"}, {"summary": "err X"}]
    if repeated_failure(two_same, threshold=3) is not None:
        failures.append("threshold=3 with 2 occurrences should be None")

    if failures:
        print("RESULT: FAIL")
        for x in failures:
            print("  -", x)
        return 1
    print("RESULT: recovery guard pass (one-off quiet; 2x same class discloses; "
          "paths/numbers normalized; threshold respected)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
