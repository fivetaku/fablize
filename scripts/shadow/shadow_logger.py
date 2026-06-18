#!/usr/bin/env python3
"""Out-of-band shadow logger for fablize measurement (M2).

Writes measurement events to ~/.fablize/history/events.jsonl (append-only).

OUT-OF-BAND GUARANTEE: this module is invoked only by out-of-band tooling
(the post-hoc collector / future side-effect callers). It NEVER emits to the
model — no additionalContext, no systemMessage, no stdout the gate reads. It
only appends to events.jsonl outside the repo. See docs/MEASUREMENT_PROTOCOL.md
(§3 out-of-band, §4 holdout, §7 sunset).
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# §4: 20% of sessions run gate OFF (pure baseline holdout). Deterministic per session.
HOLDOUT_OFF_FRACTION = 0.20
# §7: default sunset horizon (sessions). Recorded, enforced by the analysis step (M4).
SUNSET_SESSIONS = 50


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def data_root() -> Path:
    """Same convention as the gate ledger: ~/.fablize (override FABLIZE_DATA)."""
    env = os.environ.get("FABLIZE_DATA")
    base = Path(env).expanduser() if env else Path.home() / ".fablize"
    return base.resolve()


def events_path() -> Path:
    return data_root() / "history" / "events.jsonl"


def holdout_arm(session_id: str) -> str:
    """Deterministic per-session arm. 'off' = holdout (gate disabled = pure
    baseline), 'on' = gated. Computed from a session_id hash so the same session
    always lands in the same arm. NOT exposed to the model (out-of-band)."""
    if not session_id:
        return "on"
    h = hashlib.sha256(("holdout|" + session_id).encode("utf-8", "replace")).hexdigest()
    bucket = int(h[:8], 16) / 0xFFFFFFFF
    return "off" if bucket < HOLDOUT_OFF_FRACTION else "on"


def make_event(session_id: str, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "ts": utc_now(),
        "session_id": session_id or "no-session",
        "holdout_arm": holdout_arm(session_id),
        "event_type": event_type,
        "payload": payload,
    }


def append_event(event: dict[str, Any], path: Path | None = None) -> Path:
    """Append one event as a JSON line (append-only, never rewrites)."""
    p = path or events_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(event, ensure_ascii=True, sort_keys=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
    return p
