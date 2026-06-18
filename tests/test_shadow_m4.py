#!/usr/bin/env python3
"""M4 tests: stratified analysis, sunset logic, and the deep->effort wiring guard.

Run directly: `python3 tests/test_shadow_m4.py`. The wiring guard asserts the
gate decision code never references effort/delegation/workflow — the
false-escalate risk identified in measurement (risk->deep is a verification
signal only; wiring it to effort would over-escalate simple high-risk tasks).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "shadow"))


def _ev(sid: str, arm: str, et: str, payload: dict) -> dict:
    return {"session_id": sid, "holdout_arm": arm, "event_type": et, "payload": payload}


def main() -> int:
    import analyze as AN

    failures: list[str] = []

    events = [
        _ev("s1", "on", "gate_fire", {"would_fire": True}),
        _ev("s1", "on", "outcome", {"reverts": 2, "reinstructions": 1}),
        _ev("s2", "on", "gate_fire", {"would_fire": False}),
        _ev("s2", "on", "outcome", {"reverts": 0, "reinstructions": 0}),
        _ev("s3", "off", "gate_fire", {"would_fire": True}),
        _ev("s3", "off", "outcome", {"reverts": 3, "reinstructions": 2}),
        _ev("s4", "off", "outcome", {"reverts": 1, "reinstructions": 1}),
    ]
    c = AN.stratified_compare(events)
    if c["on"]["sessions"] != 2:
        failures.append(f"on sessions={c['on']['sessions']} (want 2)")
    if c["off"]["sessions"] != 2:
        failures.append(f"off sessions={c['off']['sessions']} (want 2)")
    if c["on"]["gate_fire_rate"] is None or abs(c["on"]["gate_fire_rate"] - 0.5) > 1e-9:
        failures.append(f"on gate_fire_rate={c['on']['gate_fire_rate']} (want 0.5)")
    if c["on"]["mean_reverts"] is None or abs(c["on"]["mean_reverts"] - 1.0) > 1e-9:
        failures.append(f"on mean_reverts={c['on']['mean_reverts']} (want 1.0)")
    if c["off"]["mean_reverts"] is None or abs(c["off"]["mean_reverts"] - 2.0) > 1e-9:
        failures.append(f"off mean_reverts={c['off']['mean_reverts']} (want 2.0)")
    # harness-paradox delta = on(1.0) - off(2.0) = -1.0 (gate ON has fewer reverts here)
    if c["harness_paradox_revert_delta"] is None or abs(c["harness_paradox_revert_delta"] + 1.0) > 1e-9:
        failures.append(f"paradox delta={c['harness_paradox_revert_delta']} (want -1.0)")

    # sunset: few sessions + comparable signal => not expired
    s = AN.sunset_status(events, horizon=50)
    if s["expired"] is not False:
        failures.append("sunset should NOT be expired with 4 sessions")
    if s["signal_present"] is not True:
        failures.append("signal should be present (both arms have outcomes)")
    # sunset expired: >=horizon sessions, only one arm => no comparable signal
    many = [_ev(f"x{i}", "on", "outcome", {"reverts": 1}) for i in range(50)]
    s2 = AN.sunset_status(many, horizon=50)
    if s2["expired"] is not True:
        failures.append("sunset SHOULD be expired: 50 sessions, no off-arm signal")

    # deep->effort wiring guard: gate decision code must not reference effort/delegation
    pat = re.compile(r"effort|delegat|workflow", re.IGNORECASE)
    gate_files = [
        ROOT / "scripts" / "gate" / "classify_task.py",
        ROOT / "scripts" / "gate" / "verify_state.py",
        ROOT / "hooks" / "gate_prompt.py",
        ROOT / "hooks" / "gate_post_tool.py",
        ROOT / "hooks" / "gate_stop.py",
    ]
    for gf in gate_files:
        if gf.exists() and pat.search(gf.read_text(encoding="utf-8")):
            failures.append(f"deep->effort wiring token in {gf.name} (false-escalate risk)")

    if failures:
        print("RESULT: FAIL")
        for f in failures:
            print("  -", f)
        return 1
    print("RESULT: M4 pass (stratified on/off, paradox delta=-1.0, sunset expiry, "
          "deep->effort wiring absent in gate code)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
