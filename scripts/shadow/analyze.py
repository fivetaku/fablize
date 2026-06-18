#!/usr/bin/env python3
"""Stratified analysis + sunset for fablize measurement (M4) — read-only.

Reads events.jsonl and compares the two holdout arms (on vs off) — the §1
harness-paradox question: does the Stop gate reduce, increase, or not change
rework/revert signals vs a gate-off baseline? Also computes sunset status (§7).
Pure functions (stratified_compare, sunset_status) are testable without I/O.
Read-only: never writes, never touches the gate.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from shadow_logger import SUNSET_SESSIONS, events_path  # noqa: E402


def load_events(path: str | Path | None = None) -> list[dict]:
    p = Path(path) if path else events_path()
    if not p.exists():
        return []
    out: list[dict] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _mean(xs: list) -> float | None:
    vals = [x for x in xs if x is not None]
    return (sum(vals) / len(vals)) if vals else None


def stratified_compare(events: list[dict]) -> dict:
    """Group events by holdout arm and compute per-arm signals. Returns the
    on-vs-off comparison incl. the harness-paradox revert delta (on - off)."""
    arms = ("on", "off")
    sessions = {a: set() for a in arms}
    fire = {a: [0, 0] for a in arms}        # [would_fire, total]
    outcomes = {a: [] for a in arms}
    for e in events:
        a = e.get("holdout_arm")
        if a not in sessions:
            continue
        sessions[a].add(e.get("session_id"))
        et = e.get("event_type")
        if et == "gate_fire":
            fire[a][1] += 1
            if e.get("payload", {}).get("would_fire"):
                fire[a][0] += 1
        elif et == "outcome":
            outcomes[a].append(e.get("payload", {}))

    res: dict = {}
    for a in arms:
        f = fire[a]
        res[a] = {
            "sessions": len(sessions[a]),
            "gate_fire_rate": (f[0] / f[1]) if f[1] else None,
            "mean_reverts": _mean([o.get("reverts") for o in outcomes[a]]),
            "mean_reinstructions": _mean([o.get("reinstructions") for o in outcomes[a]]),
            "n_outcomes": len(outcomes[a]),
        }
    on_r, off_r = res["on"]["mean_reverts"], res["off"]["mean_reverts"]
    res["harness_paradox_revert_delta"] = (
        None if on_r is None or off_r is None else on_r - off_r
    )
    return res


def sunset_status(events: list[dict], horizon: int = SUNSET_SESSIONS) -> dict:
    """§7 sunset: once `horizon` distinct sessions are collected without a
    comparable on/off signal, recommend removing the instrumentation."""
    n = len({e.get("session_id") for e in events if e.get("session_id")})
    cmp = stratified_compare(events)
    signal = cmp["harness_paradox_revert_delta"] is not None
    expired = (n >= horizon) and not signal
    if expired:
        rec = "remove (sunset reached, no comparable on/off signal)"
    elif signal:
        rec = "keep (comparable signal available — analyze)"
    else:
        rec = "keep collecting (insufficient data)"
    return {
        "distinct_sessions": n, "horizon": horizon,
        "signal_present": signal, "expired": expired, "recommendation": rec,
    }


def main() -> int:
    ev = load_events()
    print("stratified_compare:", json.dumps(stratified_compare(ev), ensure_ascii=False, indent=2))
    print("sunset_status:", json.dumps(sunset_status(ev), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
