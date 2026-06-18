#!/usr/bin/env python3
"""Standalone test for the out-of-band shadow logger (M2).

Run directly: `python3 tests/test_shadow.py` (not via pytest — same convention
as test_gate.py). Verifies: deterministic holdout ~20%, collector emits the 4
event types, idempotency, would_fire logic, and that events.jsonl lands
out-of-band (outside the repo).
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "shadow"))


def main() -> int:
    import shadow_logger as SL

    failures: list[str] = []

    # 1. holdout deterministic
    if SL.holdout_arm("abc") != SL.holdout_arm("abc"):
        failures.append("holdout_arm not deterministic")

    # 2. holdout fraction ~20% over many session ids
    ids = [f"sess-{i}" for i in range(3000)]
    off = sum(1 for s in ids if SL.holdout_arm(s) == "off")
    frac = off / len(ids)
    if not (0.15 < frac < 0.25):
        failures.append(f"holdout off fraction {frac:.3f} not ~0.20")

    # 3. collect from a sample ledger in an isolated temp data root
    with tempfile.TemporaryDirectory() as td:
        os.environ["FABLIZE_DATA"] = td
        tmp = Path(td)
        (tmp / "ledgers").mkdir(parents=True)
        (tmp / "ledgers" / "deadbeefcafe000000000001.json").write_text(
            json.dumps({
                "task_mode": "deep", "risk_flags": ["database"],
                "changed_files_seen": True, "change_kinds": ["code"],
                "verification_results": [], "failures": [{"kind": "test"}],
                "stop_blocks": 1, "last_updated": "2026-06-18T00:00:00+00:00",
            }), encoding="utf-8")

        import shadow_collect as SC

        n = SC.collect()
        if n != 4:
            failures.append(f"expected 4 events, got {n}")

        ep = tmp / "history" / "events.jsonl"
        lines = ep.read_text(encoding="utf-8").strip().splitlines() if ep.exists() else []
        if len(lines) != 4:
            failures.append(f"expected 4 event lines, got {len(lines)}")

        events = [json.loads(line) for line in lines]
        types = {e["event_type"] for e in events}
        if types != {"classify", "gate_fire", "effort_candidate", "recovery_repeat"}:
            failures.append(f"unexpected event types: {types}")

        # would_fire: deep + changed + not verified => True
        gate_events = [e for e in events if e["event_type"] == "gate_fire"]
        if not gate_events or gate_events[0]["payload"].get("would_fire") is not True:
            failures.append("gate_fire.would_fire should be True for deep+changed+unverified")

        # holdout arm recorded on every event
        if any(e.get("holdout_arm") not in ("on", "off") for e in events):
            failures.append("holdout_arm missing/invalid on some event")

        # idempotent: re-run with same ledger (same last_updated) writes nothing new
        n2 = SC.collect()
        if n2 != 0:
            failures.append(f"collector not idempotent: {n2} new events on re-run")

        # out-of-band: events.jsonl must live under data root, NOT inside the repo
        if str(ROOT) in str(ep.resolve()):
            failures.append("events.jsonl is inside the repo (must be out-of-band)")

        os.environ.pop("FABLIZE_DATA", None)

    if failures:
        print("RESULT: FAIL")
        for f in failures:
            print("  -", f)
        return 1
    print(f"RESULT: all shadow checks pass (holdout off={frac:.3f}, 4 event types, "
          f"idempotent, out-of-band)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
