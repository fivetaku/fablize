#!/usr/bin/env python3
"""Robustness / safety checks for the fablize observation gate before wiring it global.

Covers the failure modes the gate-comparison doc warned about:
  - fail-open on bad/empty input (never crash, never block on our own bug)
  - cannot trap the agent forever (MAX_STOP_BLOCKS then allow)
  - respects the stop_hook_active loop guard
  - precision spot-checks: typecheck-success passes; config-edit-unverified reminds
"""

import json
import os
import subprocess
import sys
import tempfile

HOOKS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")
PY = sys.executable


def run(script, payload, data_dir, raw=False):
    env = dict(os.environ)
    env["FABLIZE_DATA"] = data_dir
    stdin = payload if raw else json.dumps(payload)
    p = subprocess.run([PY, os.path.join(HOOKS, script)], input=stdin,
                       capture_output=True, text=True, env=env)
    return p


def as_json(p):
    try:
        return json.loads(p.stdout or "{}")
    except json.JSONDecodeError:
        return {"_raw": p.stdout}


def blocks(p):
    return as_json(p).get("decision") == "block"


checks = []


def check(name, cond):
    checks.append((name, bool(cond)))


# --- A. fail-open: empty + invalid stdin on every hook -> exit 0, never block ---
for script in ("gate_prompt.py", "gate_post_tool.py", "gate_stop.py"):
    dd = tempfile.mkdtemp(prefix="fz_")
    pe = run(script, "", dd, raw=True)
    pi = run(script, "}{not json", dd, raw=True)
    check(f"{script} empty-stdin exit0+noblock", pe.returncode == 0 and not blocks(pe))
    check(f"{script} bad-json exit0+noblock", pi.returncode == 0 and not blocks(pi))

# --- B. stop_hook_active guard: a would-block session must NOT block when guard set ---
dd = tempfile.mkdtemp(prefix="fz_")
run("gate_prompt.py", {"prompt": "implement X production-ready", "session_id": "B", "cwd": "/w"}, dd)
run("gate_post_tool.py", {"tool_name": "Edit", "tool_input": {"file_path": "src/x.py", "old_string": "a", "new_string": "b"}, "session_id": "B", "cwd": "/w"}, dd)
p_guard = run("gate_stop.py", {"session_id": "B", "cwd": "/w", "stop_hook_active": True}, dd)
check("stop_hook_active=true -> no block", not blocks(p_guard))

# --- C. cannot trap forever: same session blocks at most MAX_STOP_BLOCKS(2), then allows ---
dd = tempfile.mkdtemp(prefix="fz_")
run("gate_prompt.py", {"prompt": "implement X production-ready", "session_id": "C", "cwd": "/w"}, dd)
run("gate_post_tool.py", {"tool_name": "Edit", "tool_input": {"file_path": "src/x.py", "old_string": "a", "new_string": "b"}, "session_id": "C", "cwd": "/w"}, dd)
d1 = blocks(run("gate_stop.py", {"session_id": "C", "cwd": "/w", "stop_hook_active": False}, dd))
d2 = blocks(run("gate_stop.py", {"session_id": "C", "cwd": "/w", "stop_hook_active": False}, dd))
d3 = blocks(run("gate_stop.py", {"session_id": "C", "cwd": "/w", "stop_hook_active": False}, dd))
check("blocks first 2 then allows (no infinite trap)", d1 and d2 and not d3)

# --- D. precision: deep task + code edit + typecheck SUCCESS -> allow ---
dd = tempfile.mkdtemp(prefix="fz_")
run("gate_prompt.py", {"prompt": "refactor the parser thoroughly", "session_id": "D", "cwd": "/w"}, dd)
run("gate_post_tool.py", {"tool_name": "Edit", "tool_input": {"file_path": "src/p.ts", "old_string": "a", "new_string": "b"}, "session_id": "D", "cwd": "/w"}, dd)
run("gate_post_tool.py", {"tool_name": "Bash", "tool_input": {"command": "tsc --noEmit"}, "tool_response": {"exit_code": 0, "stdout": "done"}, "session_id": "D", "cwd": "/w"}, dd)
p_ts = run("gate_stop.py", {"session_id": "D", "cwd": "/w", "stop_hook_active": False}, dd)
check("deep + code edit + tsc success -> allow", not blocks(p_ts))

# --- E. lecture-style Korean doc prompt defaults to quick -> never blocks ---
dd = tempfile.mkdtemp(prefix="fz_")
run("gate_prompt.py", {"prompt": "윤자동 2회차 강의 준비해줘", "session_id": "E", "cwd": "/w"}, dd)
run("gate_post_tool.py", {"tool_name": "Edit", "tool_input": {"file_path": "course.md", "old_string": "a", "new_string": "b"}, "session_id": "E", "cwd": "/w"}, dd)
p_kr = run("gate_stop.py", {"session_id": "E", "cwd": "/w", "stop_hook_active": False}, dd)
check("KO lecture prompt (quick default) -> allow", not blocks(p_kr))

print("=" * 80)
print("fablize observation gate — robustness / safety checks")
print("=" * 80)
fails = 0
for name, ok in checks:
    fails += 0 if ok else 1
    print(f"  [{'OK' if ok else 'FAIL'}] {name}")
print("-" * 80)
print(f"RESULT: {'all pass' if not fails else str(fails) + ' FAILED'} ({len(checks)} checks)")
sys.exit(1 if fails else 0)
