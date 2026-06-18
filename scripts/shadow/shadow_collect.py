#!/usr/bin/env python3
"""Post-hoc out-of-band collector for fablize measurement (M2).

Reads ~/.fablize/ledgers/*.json (written by the LIVE gate, unmodified) and
emits measurement events to events.jsonl. Runs as a SEPARATE process: it does
not import or modify any gate hook, so gate behavior and the 16/16 regression
are structurally unchanged. Idempotent — dedupes by (ledger_key, last_updated).

Events per ledger snapshot (see docs/MEASUREMENT_PROTOCOL.md §2, §8):
  - classify         : task_mode + risk_flags + change_kinds
  - gate_fire        : would the Stop gate have fired? (stop_blocks, changed, verified)
  - effort_candidate : shadow label only (placeholder basis; real signal is HOLD)
  - recovery_repeat  : count of recorded failures (silent-recovery signal, no intervention)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from shadow_logger import append_event, data_root, events_path, make_event  # noqa: E402


def _seen_dedupe_keys(path: Path) -> set[str]:
    seen: set[str] = set()
    if not path.exists():
        return seen
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        key = event.get("payload", {}).get("_dedupe")
        if key:
            seen.add(key)
    return seen


def collect() -> int:
    """Snapshot every ledger into events.jsonl. Returns number of events written."""
    root = data_root()
    ledgers_dir = root / "ledgers"
    ep = events_path()
    seen = _seen_dedupe_keys(ep)
    written = 0
    if not ledgers_dir.exists():
        return 0

    for ledger_file in sorted(ledgers_dir.glob("*.json")):
        try:
            led = json.loads(ledger_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(led, dict):
            continue

        key = ledger_file.stem
        stamp = led.get("last_updated", "")
        dedupe = f"{key}|{stamp}"
        if dedupe in seen:
            continue

        sid = key  # ledger key = sha256(session_id|cwd)[:24] — stable session identity
        mode = led.get("task_mode", "quick")
        risk = led.get("risk_flags", []) or []
        changed = bool(led.get("changed_files_seen"))
        verified = bool(led.get("verification_results"))
        stop_blocks = int(led.get("stop_blocks") or 0)
        change_kinds = led.get("change_kinds", []) or []
        failures = led.get("failures", []) or []
        base = {"_dedupe": dedupe, "ledger_key": key, "last_updated": stamp}

        append_event(make_event(sid, "classify", {
            **base, "mode": mode, "risk_flags": risk, "change_kinds": change_kinds,
        }))
        # §5/§8: would the gate have fired? (normal/deep + changed + not verified)
        would_fire = mode in ("normal", "deep") and changed and not verified
        append_event(make_event(sid, "gate_fire", {
            **base, "stop_blocks": stop_blocks, "changed": changed,
            "verified": verified, "would_fire": would_fire,
        }))
        # §7/§8: effort delegation candidate — LABEL ONLY, no actual delegation.
        # Placeholder basis (mode==deep); the real difficulty signal stays HOLD.
        append_event(make_event(sid, "effort_candidate", {
            **base, "candidate": mode == "deep", "basis": "mode==deep (shadow placeholder)",
        }))
        # silent-recovery signal — count only, no intervention.
        append_event(make_event(sid, "recovery_repeat", {
            **base, "failure_count": len(failures),
        }))
        written += 4

    return written


if __name__ == "__main__":
    count = collect()
    print(f"shadow_collect: wrote {count} events -> {events_path()}")
