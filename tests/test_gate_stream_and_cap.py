#!/usr/bin/env python3
"""Regression tests for two gate defects.

1. detect_failure() must not classify a tool call as failed just because its
   STDOUT contains a failure word. Reading or grepping source that discusses
   errors is not encountering one.
2. finish-the-work.sh must stop blocking after MAX_FINISH_BLOCKS, matching its
   sibling gates (gate_stop MAX_STOP_BLOCKS=2, context-guard MAX_BLOCKS=2).

Standalone script, like the other tests here. Exit non-zero on any mismatch.
"""

import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "gate"))

from parse_tool_result import detect_failure, verification_record  # noqa: E402

fails = []


def check(label, got, want):
    ok = got == want
    print(f"  [{'OK' if ok else 'XX'}] {label}  (want={want} got={got})")
    if not ok:
        fails.append(label)


print("detect_failure: stdout must not imply failure")

check(
    "read source containing 'failed'/'error:' in stdout",
    detect_failure({
        "tool_name": "Bash",
        "tool_input": {"command": "cat parse_tool_result.py"},
        "tool_response": {"stdout": "FAILURE_RE = r'failed|failure|\\berror:'", "stderr": ""},
    }) is not None,
    False,
)

check(
    "grep hitting 'Traceback' inside a log file",
    detect_failure({
        "tool_name": "Bash",
        "tool_input": {"command": "grep -n Traceback app.log"},
        "tool_response": {"stdout": "42: Traceback (most recent call last):", "stderr": ""},
    }) is not None,
    False,
)

check(
    "real failure via structured exit_code=1",
    detect_failure({
        "tool_name": "Bash",
        "tool_input": {"command": "npm test"},
        "tool_response": {"stdout": "", "stderr": "1 test failed", "exit_code": 1},
    }) is not None,
    True,
)

check(
    "real failure via stderr, no exit code",
    detect_failure({
        "tool_name": "Bash",
        "tool_input": {"command": "npm run build"},
        "tool_response": {"stdout": "", "stderr": "npm ERR! Build failed with 2 errors"},
    }) is not None,
    True,
)

check(
    "clean success is not a failure",
    detect_failure({
        "tool_name": "Bash",
        "tool_input": {"command": "npm test"},
        "tool_response": {"stdout": "142 passed, 0 failed", "stderr": "", "exit_code": 0},
    }) is not None,
    False,
)

# verification_record() keeps its text heuristic: the command already matched
# VERIFY_RE, so its stdout genuinely is a verdict.
check(
    "verification_record still reads a failing test run",
    verification_record({
        "tool_name": "Bash",
        "tool_input": {"command": "npm test"},
        "tool_response": {"stdout": "", "stderr": "1 test failed", "exit_code": 1},
    })["success"],
    False,
)

print()
print("finish-the-work.sh: cumulative block cap")

HOOK = os.path.join(ROOT, "hooks", "finish-the-work.sh")
PROMISE = "I will now implement the parser and run the tests."

with tempfile.TemporaryDirectory(dir=os.path.expanduser("~")) as tmp:
    env = dict(os.environ, FABLIZE_DATA=os.path.join(tmp, "data"))
    transcript = os.path.join(tmp, "tr.jsonl")

    def write_transcript(text):
        with open(transcript, "w") as fh:
            fh.write(json.dumps({
                "type": "assistant",
                "message": {"role": "assistant", "content": [{"type": "text", "text": text}]},
            }) + "\n")

    def stop(session, **kw):
        payload = dict({
            "session_id": session,
            "transcript_path": transcript,
            "cwd": tmp,
            "stop_hook_active": False,
        }, **kw)
        out = subprocess.run(
            ["bash", HOOK], input=json.dumps(payload),
            capture_output=True, text=True, timeout=20, env=env,
        ).stdout.strip()
        if not out:
            return False
        return json.loads(out).get("decision") == "block"

    write_transcript(PROMISE)
    seq = [stop("cap") for _ in range(5)]
    check("blocks exactly twice, then steps aside", seq, [True, True, False, False, False])
    check("loop guard still short-circuits", stop("guard", stop_hook_active=True), False)

    write_transcript("Done. Ran the suite: 12 passed.")
    check("honest completion passes", stop("honest"), False)

    write_transcript("Should I use option A or B?")
    check("question ending passes", stop("question"), False)

print()
if fails:
    print(f"RESULT: {len(fails)} FAILED -> {fails}")
    sys.exit(1)
print("RESULT: all pass (10 checks)")
