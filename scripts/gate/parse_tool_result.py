#!/usr/bin/env python3
"""Parse tool inputs/outputs into compact ledger facts (fablize observation gate).

Ported from fable-ish. Detects (a) which files changed and their kind, and
(b) whether a verification command ran and observably succeeded or failed.
"""

from __future__ import annotations

import re
from typing import Any

from ledger import classify_path_kind, redact


VERIFY_RE = re.compile(
    r"(?i)\b("
    r"pytest|unittest|go\s+test|cargo\s+test|npm\s+test|pnpm\s+test|yarn\s+test|bun\s+test|"
    r"mvn\s+test|gradle\s+test|rspec|vitest|jest|playwright|cypress|"
    r"lint|eslint|ruff|flake8|mypy|pyright|tsc|typecheck|"
    r"build|check|validate|verify|json\.tool|py_compile|curl"
    r")\b"
)
FAILURE_RE = re.compile(
    r"(?i)(command not found|no such file or directory|traceback|syntaxerror|failed|failure|"
    r"\berror:|\b[1-9][0-9]*\s+errors?\b|exit code [1-9]|exited with code [1-9]|"
    r"tests? failed|build failed|lint failed)"
)
SUCCESS_RE = re.compile(r"(?i)\b(passed|success|succeeded|0 failed|build completed|done|valid)\b")
MUTATING_BASH_RE = re.compile(
    r"(?i)\b(apply_patch|python\s+.*\s+-m\s+compileall|chmod|mkdir|mv|cp|rm|touch|"
    r"npm\s+run\s+build|pnpm\s+build|yarn\s+build)\b"
)


def response_text(value: Any, limit: int = 4000) -> str:
    parts: list[str] = []

    def walk(item: Any) -> None:
        if len(" ".join(parts)) > limit:
            return
        if isinstance(item, str):
            parts.append(item)
        elif isinstance(item, dict):
            for key in ("stdout", "stderr", "output", "message", "text", "content", "error", "summary"):
                if key in item:
                    walk(item[key])
            if not parts:
                for child in item.values():
                    walk(child)
        elif isinstance(item, list):
            for child in item[:20]:
                walk(child)

    walk(value)
    return redact(" ".join(parts), limit)


def command_from_input(input_data: dict[str, Any]) -> str:
    tool_input = input_data.get("tool_input")
    if isinstance(tool_input, dict):
        return str(tool_input.get("command") or tool_input.get("description") or "")
    if isinstance(tool_input, str):
        return tool_input
    return ""


def explicit_status(input_data: dict[str, Any]) -> bool | None:
    """Machine-readable success/failure from the tool_response (exit code / success
    bool), or None when the host provides no such field. This is ground truth; it
    is NOT inferred from output text."""
    for candidate in (input_data, input_data.get("tool_response")):
        if isinstance(candidate, dict):
            for key in ("success", "ok"):
                if isinstance(candidate.get(key), bool):
                    return bool(candidate[key])
            for key in ("exit_code", "exitCode", "returncode", "status"):
                value = candidate.get(key)
                if isinstance(value, int):
                    return value == 0
                if isinstance(value, str) and value.isdigit():
                    return int(value) == 0
    return None


def exit_success(input_data: dict[str, Any], text: str) -> bool | None:
    status = explicit_status(input_data)
    if status is not None:
        return status
    # No machine-readable status: fall back to text heuristics. Used only for
    # verification-command bookkeeping, NOT for the failure nudge (see
    # detect_failure), which must never guess a failure from output text.
    if FAILURE_RE.search(text):
        return False
    if SUCCESS_RE.search(text):
        return True
    return None


def is_verification_command(command: str) -> bool:
    return bool(VERIFY_RE.search(command or ""))


def detect_failure(input_data: dict[str, Any]) -> dict[str, Any] | None:
    # Fire ONLY on a machine-confirmed failure (nonzero exit / success:false).
    # We deliberately do NOT infer failure from output text: hosts that omit an
    # exit code (e.g. Bash here) made the old text heuristic flag every benign
    # 'No such file or directory' / 'error:' / 'failed' string in stdout — greps,
    # log reads, and SSM runs that succeeded. Verification bookkeeping keeps its
    # text fallback via exit_success; the failure nudge must be ground-truth only.
    if explicit_status(input_data) is False:
        text = response_text(input_data.get("tool_response", input_data))
        return {"kind": "tool-result", "summary": redact(text or command_from_input(input_data), 240)}
    return None


def changed_paths(input_data: dict[str, Any]) -> list[str]:
    tool_name = str(input_data.get("tool_name") or "")
    tool_input = input_data.get("tool_input")
    paths: list[str] = []
    if isinstance(tool_input, dict):
        file_path = tool_input.get("file_path")
        if file_path:
            paths.append(str(file_path))
    if tool_name in {"Edit", "Write", "NotebookEdit", "MultiEdit"}:
        return paths or ["edit"]
    return paths


def changed_kinds(input_data: dict[str, Any]) -> list[str]:
    paths = changed_paths(input_data)
    if paths:
        return sorted({classify_path_kind(path.strip()) for path in paths})
    tool_name = str(input_data.get("tool_name") or "")
    command = command_from_input(input_data)
    if tool_name == "Bash" and MUTATING_BASH_RE.search(command):
        return ["other"]
    return []


def verification_record(input_data: dict[str, Any]) -> dict[str, Any] | None:
    command = command_from_input(input_data)
    if not command or not is_verification_command(command):
        return None
    text = response_text(input_data.get("tool_response", input_data), 1000)
    success = exit_success(input_data, text)
    return {
        "command": redact(command, 220),
        "success": bool(success) if success is not None else None,
        "summary": redact(text, 220),
    }


def _failure_signature(summary: str) -> str:
    """Normalize a failure summary into a stable class key. Numbers and paths
    differ between occurrences of the same failure, so collapse them so that
    e.g. two 'ECONNREFUSED localhost:5432' land on the same class."""
    s = (summary or "").lower()
    s = re.sub(r"[/\\][^\s]+", " path ", s)   # paths vary
    s = re.sub(r"\d+", "#", s)                # numbers vary
    s = re.sub(r"\s+", " ", s).strip()
    return s[:80]


def repeated_failure(failures: list[dict[str, Any]], threshold: int = 2) -> tuple[str, int] | None:
    """If the most recent failure's class has occurred `threshold`+ times in the
    ledger, return (signature, count). Drives the silent-recovery guard: recover
    quietly from one-offs, but disclose a repeating failure class."""
    if not failures:
        return None
    sig = _failure_signature(failures[-1].get("summary", ""))
    if not sig:
        return None
    count = sum(1 for f in failures if _failure_signature(f.get("summary", "")) == sig)
    return (sig, count) if count >= threshold else None
