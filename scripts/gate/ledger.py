#!/usr/bin/env python3
"""Small JSON ledger for the fablize observation gate.

Ported from fable-ish (gate-comparison experiment, 2026-06-14). Only the
observed-evidence subsystem is carried over; danger-blocking stays with the
host harness. Ledger state lives under ~/.fablize/ledgers/ (override with
FABLIZE_DATA) so it survives reboots, unlike the original /tmp default.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


DEFAULT_LEDGER: dict[str, Any] = {
    "task_mode": "quick",
    "risk_flags": [],
    "changed_files_seen": False,
    "change_kinds": [],
    "verification_commands": [],
    "verification_results": [],
    "failures": [],
    "stop_blocks": 0,
    "last_updated": "",
}

SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*['\"]?[^'\"\s]+"),
    re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{12,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{12,}"),
]

CODE_EXTS = {
    ".c", ".cc", ".cpp", ".cs", ".css", ".go", ".java", ".js", ".jsx", ".kt",
    ".mjs", ".php", ".py", ".rb", ".rs", ".scss", ".sh", ".sql", ".swift",
    ".ts", ".tsx",
}
DOC_EXTS = {".md", ".mdx", ".rst", ".txt", ".adoc"}
CONFIG_EXTS = {".json", ".jsonc", ".toml", ".yaml", ".yml", ".ini", ".cfg", ".conf", ".lock"}
ASSET_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico", ".pdf", ".mp3", ".mp4"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def redact(text: Any, limit: int = 500) -> str:
    value = "" if text is None else str(text)
    value = value.replace("\r", " ").replace("\n", " ").strip()
    for pattern in SECRET_PATTERNS:
        value = pattern.sub("[REDACTED]", value)
    if len(value) > limit:
        return value[: limit - 3] + "..."
    return value


def data_root() -> Path:
    env_data = os.environ.get("FABLIZE_DATA")
    base = Path(env_data).expanduser() if env_data else Path.home() / ".fablize"
    return base.resolve()


def ledger_key(input_data: dict[str, Any]) -> str:
    cwd = input_data.get("cwd") or os.getcwd()
    session_id = input_data.get("session_id") or "no-session"
    raw = f"{session_id}|{cwd}"
    return hashlib.sha256(raw.encode("utf-8", "replace")).hexdigest()[:24]


def ledger_path(input_data: dict[str, Any]) -> Path:
    return data_root() / "ledgers" / f"{ledger_key(input_data)}.json"


def default_ledger() -> dict[str, Any]:
    return copy.deepcopy(DEFAULT_LEDGER)


def load_ledger(input_data: dict[str, Any]) -> dict[str, Any]:
    path = ledger_path(input_data)
    if not path.exists():
        return default_ledger()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = default_ledger()
        data["failures"].append(
            {"kind": "ledger", "summary": "Ledger could not be read; continuing fresh."}
        )
        return data

    ledger = default_ledger()
    if isinstance(data, dict):
        ledger.update({key: data.get(key, value) for key, value in ledger.items()})
    for key in ("risk_flags", "change_kinds", "verification_commands", "verification_results", "failures"):
        if not isinstance(ledger.get(key), list):
            ledger[key] = []
    return ledger


def save_ledger(input_data: dict[str, Any], ledger: dict[str, Any]) -> Path:
    path = ledger_path(input_data)
    path.parent.mkdir(parents=True, exist_ok=True)
    ledger["last_updated"] = utc_now()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(ledger, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)
    return path


def update_ledger(input_data: dict[str, Any], updater: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
    ledger = load_ledger(input_data)
    updater(ledger)
    trim_ledger(ledger)
    save_ledger(input_data, ledger)
    return ledger


def trim_ledger(ledger: dict[str, Any]) -> None:
    for key in ("risk_flags", "change_kinds"):
        values: list[Any] = []
        for value in ledger.get(key, []):
            if value not in values:
                values.append(value)
        ledger[key] = values[:20]
    for key in ("verification_commands", "verification_results", "failures"):
        ledger[key] = ledger.get(key, [])[-40:]


def add_unique(ledger: dict[str, Any], key: str, values: list[str]) -> None:
    existing = list(ledger.get(key, []))
    for value in values:
        if value and value not in existing:
            existing.append(value)
    ledger[key] = existing


def classify_path_kind(path_value: str) -> str:
    path = Path(path_value)
    name = path.name.lower()
    suffix = path.suffix.lower()
    parts = {part.lower() for part in path.parts}
    if suffix in DOC_EXTS or name in {"readme", "readme.md", "agents.md"} or "docs" in parts:
        return "docs"
    if suffix in CODE_EXTS:
        return "code"
    if suffix in CONFIG_EXTS or name.startswith(".env"):
        return "config"
    if suffix in ASSET_EXTS:
        return "assets"
    return "other"


def read_stdin_json() -> dict[str, Any]:
    import sys

    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"_parse_error": "invalid stdin json"}
    return data if isinstance(data, dict) else {"_input": data}


def emit_json(payload: dict[str, Any]) -> None:
    import sys

    sys.stdout.write(json.dumps(payload, ensure_ascii=True) + "\n")
