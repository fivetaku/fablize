#!/usr/bin/env python3
"""Regression: file content must not be mistaken for a tool failure.

detect_failure() text-greps the tool response for failure words. For Bash that
response is a command log, so the heuristic is right. For Edit/Write it is the
FILE ITSELF — so editing a doc containing "Failed attempts", a changelog saying
"fixed the failure", or a test fixture with "3 errors" was reported as a failed
tool call, and the agent was told not to report completion.

These tools signal failure structurally (success/ok/exit_code), never in prose,
so content tools now consult only that signal. Bash behaviour is unchanged.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "gate"))

from parse_tool_result import detect_failure  # noqa: E402


def edit(content, tool="Edit"):
    return {"tool_name": tool, "tool_input": {"file_path": "/repo/notes.md"},
            "tool_response": {"content": content}}


# (label, payload, expected_failure)
CASES = [
    # --- the bug: prose inside an edited file is not a tool failure ---
    ("edit: '## Failed attempts' heading", edit("## Failed attempts"), False),
    ("edit: prose 'documents a failure mode'", edit("documents a failure mode"), False),
    ("edit: 'probe reports 1 error, 0 warnings'", edit("probe reports 1 error, 0 warnings"), False),
    ("edit: changelog 'fixed the failure'", edit("- fixed the failure in the parser"), False),
    ("edit: 'error: ' inside a code sample", edit("example output:\nerror: cannot find module"), False),
    ("write: same content via Write", edit("## Failed attempts", tool="Write"), False),
    ("read: same content via Read", edit("build failed", tool="Read"), False),
    ("edit: clean content (control)", edit("all good here"), False),

    # --- still caught: content tools that really failed report it structurally ---
    ("edit: structural success=False", {
        "tool_name": "Edit", "tool_input": {"file_path": "/repo/a.py"},
        "tool_response": {"success": False, "error": "String to replace not found"}}, True),
    ("write: structural exit_code=1", {
        "tool_name": "Write", "tool_input": {"file_path": "/repo/a.py"},
        "tool_response": {"exit_code": 1}}, True),

    # --- unchanged: Bash output really is a command log ---
    ("bash: nonzero exit", {
        "tool_name": "Bash", "tool_input": {"command": "pytest"},
        "tool_response": {"stdout": "2 failed, 3 passed", "exit_code": 1}}, True),
    ("bash: textual failure, no exit code", {
        "tool_name": "Bash", "tool_input": {"command": "npm run build"},
        "tool_response": {"stdout": "build failed"}}, True),
    ("bash: traceback", {
        "tool_name": "Bash", "tool_input": {"command": "python x.py"},
        "tool_response": {"stdout": "Traceback (most recent call last):"}}, True),
    ("bash: clean run", {
        "tool_name": "Bash", "tool_input": {"command": "pytest"},
        "tool_response": {"stdout": "5 passed in 0.31s", "exit_code": 0}}, False),
]


def main():
    bad = 0
    for label, payload, want in CASES:
        got = bool(detect_failure(payload))
        if got != want:
            bad += 1
            print(f"MISMATCH  expected_failure={want} got={got}  {label}")
    if bad:
        print(f"RESULT: {bad}/{len(CASES)} mismatches")
        return 1
    print(f"RESULT: all pass ({len(CASES)} checks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
