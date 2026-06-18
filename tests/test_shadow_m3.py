#!/usr/bin/env python3
"""M3 tests: holdout toggle (gate_stop, env-gated) + outcome collector.

Run directly: `python3 tests/test_shadow_m3.py`. Verifies the holdout layer is
default-OFF (so the gate is unchanged) and only suppresses for the 'off' arm
when FABLIZE_HOLDOUT=1, and that the outcome parser counts reverts/rework/
reinstructions.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "shadow"))
sys.path.insert(0, str(ROOT / "hooks"))


def main() -> int:
    import shadow_logger as SL
    import outcome_collect as OC
    import gate_stop as GS

    failures: list[str] = []

    # --- outcome parser (pure) ---
    commits = [
        {"hash": "a", "subject": "feat: x", "files": ["a.py", "b.py"]},
        {"hash": "b", "subject": 'Revert "feat: x"', "files": ["a.py"]},
        {"hash": "c", "subject": "fix: a again", "files": ["a.py"]},
    ]
    o = OC.parse_outcomes(commits, user_messages=["좋아", "아니 다시 해줘", "this is wrong"])
    if o["commits"] != 3:
        failures.append(f"commits={o['commits']} (want 3)")
    if o["reverts"] != 1:
        failures.append(f"reverts={o['reverts']} (want 1)")
    if o["rework_files"] != 1:
        failures.append(f"rework_files={o['rework_files']} (want 1; a.py in 3 commits)")
    if o["reinstructions"] != 2:
        failures.append(f"reinstructions={o['reinstructions']} (want 2)")
    if OC.parse_outcomes([], None)["reinstructions"] is not None:
        failures.append("reinstructions must be None when no transcript given")

    # --- holdout suppression (gate_stop, env-gated) ---
    off_id = next(s for i in range(5000) if SL.holdout_arm(s := f"s{i}") == "off")
    on_id = next(s for i in range(5000) if SL.holdout_arm(s := f"s{i}") == "on")

    os.environ.pop("FABLIZE_HOLDOUT", None)
    if GS._holdout_suppresses({"session_id": off_id}) is not False:
        failures.append("default (env unset) must NOT suppress, even for off arm")

    os.environ["FABLIZE_HOLDOUT"] = "1"
    if GS._holdout_suppresses({"session_id": off_id}) is not True:
        failures.append("env=1 + off arm must suppress")
    if GS._holdout_suppresses({"session_id": on_id}) is not False:
        failures.append("env=1 + on arm must NOT suppress")
    os.environ.pop("FABLIZE_HOLDOUT", None)

    if failures:
        print("RESULT: FAIL")
        for f in failures:
            print("  -", f)
        return 1
    print("RESULT: M3 pass (outcome: 1 revert / 1 rework / 2 reinstruct; "
          "holdout default-off, suppresses only off-arm when enabled)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
