#!/usr/bin/env python3
"""Test the goal engine's `add` command (extend a live plan without recreating it).

Run directly: `python3 tests/test_goals.py`. Verifies that added stories get fresh
ids without renumbering, `--after` inserts in place and `next` honours list order,
the verification gate moves to a newly appended final story (and the old final
becomes an ordinary story), bad input is refused, and the ledger records the add.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOALS = ROOT / "scripts" / "goals.py"


def run(cwd: str, *args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    return subprocess.run([sys.executable, str(GOALS), *args], cwd=cwd, env=env,
                          capture_output=True, text=True, encoding="utf-8")


def order(cwd: str) -> list[str]:
    plan = json.loads((Path(cwd) / ".fablize" / "goals.json").read_text(encoding="utf-8"))
    return [g["id"] for g in plan["goals"]]


def main() -> int:
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as d:
        run(d, "create", "--brief", "t", "--goal", "A::a", "--goal", "B::b", "--goal", "C::c")
        run(d, "next")
        run(d, "checkpoint", "--id", "G001", "--status", "complete", "--evidence", "ok")

        # insert after G001: fresh id G004, existing ids untouched
        r = run(d, "add", "--goal", "Mid::inserted", "--after", "G001")
        if r.returncode != 0:
            failures.append(f"add --after failed: {r.stderr or r.stdout}")
        if order(d) != ["G001", "G004", "G002", "G003"]:
            failures.append(f"insert order wrong: {order(d)}")

        # next follows list order, so the inserted story is activated first
        r = run(d, "next")
        if "G004" not in r.stdout.splitlines()[0]:
            failures.append(f"next should activate G004, got: {r.stdout.splitlines()[0]}")

        # append two: ids continue from the highest, final moves to G006
        r = run(d, "add", "--goal", "T1::tail", "--goal", "T2::new final")
        if order(d) != ["G001", "G004", "G002", "G003", "G005", "G006"]:
            failures.append(f"append order wrong: {order(d)}")
        if "G006" not in r.stdout or "gate" not in r.stdout:
            failures.append("append past the final story should announce the moved verification gate")

        # old final (G003) is now ordinary: completes without verify args
        for gid in ("G004", "G002", "G003", "G005"):
            if gid != "G004":
                run(d, "next")
            r = run(d, "checkpoint", "--id", gid, "--status", "complete", "--evidence", "ok")
            if r.returncode != 0:
                failures.append(f"{gid} should complete without verify args: {r.stderr.strip()}")

        # new final (G006) is gated
        run(d, "next")
        r = run(d, "checkpoint", "--id", "G006", "--status", "complete", "--evidence", "ok")
        if r.returncode == 0:
            failures.append("new final story G006 completed without --verify-cmd/--verify-evidence")
        r = run(d, "checkpoint", "--id", "G006", "--status", "complete", "--evidence", "ok",
                "--verify-cmd", "echo ok", "--verify-evidence", "ok")
        if r.returncode != 0:
            failures.append(f"G006 should complete with verify args: {r.stderr.strip()}")

        # refusals
        if run(d, "add", "--goal", "x::y", "--after", "G099").returncode == 0:
            failures.append("unknown --after id should be refused")
        if run(d, "add", "--goal", "no separator").returncode == 0:
            failures.append("goal without '::' should be refused")
        if run(d, "add").returncode == 0:
            failures.append("add with no --goal should be refused")

        # ledger records each add with its ids and anchor
        events = [json.loads(line) for line in (Path(d) / ".fablize" / "ledger.jsonl").read_text(encoding="utf-8").splitlines()]
        added = [e for e in events if e["event"] == "goals_added"]
        if [e["ids"] for e in added] != [["G004"], ["G005", "G006"]]:
            failures.append(f"ledger goals_added events wrong: {added}")
        if added and added[0].get("after") != "G001":
            failures.append(f"ledger should record the --after anchor, got {added[0].get('after')}")

    with tempfile.TemporaryDirectory() as d:
        if run(d, "add", "--goal", "x::y").returncode == 0:
            failures.append("add without a plan should be refused")

    if failures:
        print("FAIL")
        for f in failures:
            print("  -", f)
        return 1
    print("PASS: add command (insert, append, gate move, refusals, ledger)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
