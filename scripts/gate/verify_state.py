#!/usr/bin/env python3
"""Stop-time decision for the fablize observation gate.

The decision is made purely from observed ledger state — never from the
assistant's claim text — so it is language-agnostic. Deep-only: it blocks a
DEEP, non-docs task that changed files but has no OBSERVED successful
verification. This catches "I changed code and tests pass" when no test was
ever run, or ran and failed. Normal mode no longer hard-blocks (deep-only —
measured noise with no proven benefit). Complementary to finish-the-work.sh
(which catches promise-no-act).
"""

from __future__ import annotations

from typing import Any


MAX_STOP_BLOCKS = 2


def has_successful_verification(ledger: dict[str, Any]) -> bool:
    return any(result.get("success") is True for result in ledger.get("verification_results", []))


def has_any_verification(ledger: dict[str, Any]) -> bool:
    return bool(ledger.get("verification_commands") or ledger.get("verification_results"))


def docs_only(ledger: dict[str, Any]) -> bool:
    kinds = set(ledger.get("change_kinds", []))
    return bool(ledger.get("changed_files_seen")) and bool(kinds) and kinds <= {"docs"}


def should_block_stop(ledger: dict[str, Any]) -> tuple[bool, str]:
    mode = ledger.get("task_mode") or "quick"
    stop_blocks = int(ledger.get("stop_blocks") or 0)
    changed = bool(ledger.get("changed_files_seen"))
    verified = has_successful_verification(ledger)

    if stop_blocks >= MAX_STOP_BLOCKS:
        return False, ""
    if mode == "quick":
        return False, ""
    if docs_only(ledger):
        return False, ""
    if mode == "deep" and not verified:
        if changed:
            return True, "fablize gate: run the narrowest verification command for the changed behavior before final response, or record why none applies."
        if not has_any_verification(ledger):
            return True, "fablize gate: add one observable proof, or explicitly record why this deep task has no runnable verifier."
    # deep-only: normal mode no longer hard-blocks. Measured 0 proven benefit +
    # ~7 firings/session of observable noise (see docs/MEASUREMENT_PROTOCOL.md);
    # normal still gets an advisory prompt nudge, just no Stop block.
    return False, ""


def warning_after_max_blocks(ledger: dict[str, Any]) -> str:
    if int(ledger.get("stop_blocks") or 0) >= MAX_STOP_BLOCKS and not has_successful_verification(ledger):
        return "fablize gate: verification evidence is still missing — include that gap in the final report."
    return ""
