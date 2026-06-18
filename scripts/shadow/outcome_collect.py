#!/usr/bin/env python3
"""Outcome-signal collector for fablize measurement (M3) — out-of-band, post-hoc.

Extracts result signals (the dependent variables of §5) from a repo's git
history (+ an optional transcript) and writes one 'outcome' event per session
to events.jsonl. The pure parse function is testable without git or a model.

Signals: reverts (revert commits), rework_files (files touched in >1 commit =
churn), reinstructions (optional — user correction turns in a transcript).
Never touches the gate; reads git/transcript only and appends out-of-band.
"""
from __future__ import annotations

import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from shadow_logger import append_event, make_event  # noqa: E402

REVERT_RE = re.compile(r"(?i)\brevert\b|^revert ")
# Heuristic correction markers for user reinstructions (KO + EN).
REINSTRUCT_RE = re.compile(
    r"(아니|다시|틀렸|틀린|되돌|복구|원복|wrong|no,|not what|undo|revert that)",
    re.IGNORECASE,
)


def parse_outcomes(commits: list[dict], user_messages: list[str] | None = None) -> dict:
    """commits: [{hash, subject, files:[...]}]. user_messages: optional list of
    user-turn strings. Returns the outcome signal dict. Pure — no I/O."""
    reverts = sum(1 for c in commits if REVERT_RE.search(c.get("subject", "") or ""))
    file_counts: Counter[str] = Counter()
    for c in commits:
        for f in set(c.get("files", []) or []):
            file_counts[f] += 1
    rework_files = sum(1 for _, n in file_counts.items() if n > 1)
    reinstructions = None
    if user_messages is not None:
        reinstructions = sum(1 for m in user_messages if REINSTRUCT_RE.search(m or ""))
    return {
        "commits": len(commits),
        "reverts": reverts,
        "rework_files": rework_files,
        "reinstructions": reinstructions,
    }


def git_commits(repo: Path | str, max_count: int = 200) -> list[dict]:
    """Read recent commits with changed files. Returns [] on any failure."""
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "log", f"-{max_count}", "--name-only",
             "--pretty=format:%x01%H%x02%s"],
            capture_output=True, text=True, timeout=20,
        )
        if out.returncode != 0:
            return []
    except Exception:
        return []
    commits: list[dict] = []
    for block in out.stdout.split("\x01"):
        block = block.strip("\n")
        if not block.strip():
            continue
        head, _, rest = block.partition("\n")
        h, _, subj = head.partition("\x02")
        files = [ln for ln in rest.splitlines() if ln.strip()]
        commits.append({"hash": h, "subject": subj, "files": files})
    return commits


def collect(repo: Path | str, session_id: str, user_messages: list[str] | None = None) -> dict:
    signals = parse_outcomes(git_commits(repo), user_messages)
    append_event(make_event(session_id, "outcome", signals))
    return signals


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "."
    sid = sys.argv[2] if len(sys.argv) > 2 else "cli"
    print(f"outcome_collect: {collect(target, sid)}")
