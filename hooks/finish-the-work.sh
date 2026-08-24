#!/bin/bash
# finish-the-work.sh — Stop hook
# Detects early termination where the agent only PROMISES work without doing it, and re-engages it.
# Deterministic (regex). Infinite loops are guarded by stop_hook_active AND a cumulative per-session cap.
# stdin: JSON { transcript_path, stop_hook_active, session_id, cwd, ... }
# stdout: {"decision":"block","reason":"..."} to continue, otherwise empty (exit 0)

set -e
input=$(cat)

# Loop guard: if this hook already forced one continuation, do not block again.
active=$(printf '%s' "$input" | python3 -c "import sys,json; print(json.load(sys.stdin).get('stop_hook_active', False))" 2>/dev/null || echo "False")
if [ "$active" = "True" ]; then exit 0; fi

tpath=$(printf '%s' "$input" | python3 -c "import sys,json; print(json.load(sys.stdin).get('transcript_path',''))" 2>/dev/null || echo "")
if [ -z "$tpath" ] || [ ! -f "$tpath" ]; then exit 0; fi
# Reject paths outside TMPDIR or HOME to block path-traversal via crafted hook input.
case "$tpath" in
    "${TMPDIR:-/tmp}"/* | "$HOME"/*) ;;
    *) exit 0 ;;
esac

# Session identity for the cumulative block cap (mirrors ledger.ledger_key).
sid=$(printf '%s' "$input" | python3 -c "import sys,json; print(json.load(sys.stdin).get('session_id') or 'no-session')" 2>/dev/null || echo "no-session")
scwd=$(printf '%s' "$input" | python3 -c "import sys,json; print(json.load(sys.stdin).get('cwd') or '')" 2>/dev/null || echo "")

# Extract the last assistant message's text and whether it ended with a tool call.
python3 - "$tpath" "$sid" "$scwd" <<'PY'
import sys, json, re

path = sys.argv[1]
session_id = sys.argv[2] if len(sys.argv) > 2 else "no-session"
cwd = sys.argv[3] if len(sys.argv) > 3 else ""

# Cumulative cap, matching the sibling gates (gate_stop MAX_STOP_BLOCKS=2,
# context-guard MAX_BLOCKS=2). stop_hook_active only alternates block/allow, so
# without this a phrasing that keeps tripping the regex blocks on every other
# Stop forever. After MAX_FINISH_BLOCKS the guard steps aside for the session.
MAX_FINISH_BLOCKS = 2


def _counter_path():
    import hashlib, os
    root = os.environ.get("FABLIZE_DATA") or os.path.join(os.path.expanduser("~"), ".fablize")
    key = hashlib.sha256(f"{session_id}|{cwd}".encode("utf-8", "replace")).hexdigest()[:24]
    return os.path.join(root, "finish-blocks", f"{key}.json")


def _blocks_so_far():
    try:
        with open(_counter_path()) as fh:
            return int(json.load(fh).get("blocks") or 0)
    except Exception:
        return 0


def _record_block(n):
    import os
    p = _counter_path()
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as fh:
            json.dump({"blocks": n}, fh)
    except Exception:
        pass  # fail open: a counter we cannot persist must not break the hook


last_text = ""
last_had_tool = False
try:
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            msg = obj.get("message", obj)
            if obj.get("type") == "assistant" or msg.get("role") == "assistant":
                content = msg.get("content", [])
                if isinstance(content, list):
                    texts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
                    tools = [b for b in content if isinstance(b, dict) and b.get("type") == "tool_use"]
                    if texts or tools:
                        last_text = "\n".join(texts).strip()
                        last_had_tool = bool(tools)
except Exception:
    sys.exit(0)

# Ended with a tool call (still working) or with no text -> not an early stop.
if last_had_tool or not last_text:
    sys.exit(0)

# Inspect only the closing paragraph, not the whole report.
tail = last_text[-400:]

# Unfulfilled-promise patterns (English + Korean). Future/intent only; past tense is excluded.
promise = re.search(
    r"\b(I'?ll|I will|let me|next,? I|now I'?ll)\b[^.]{0,60}\b(now|next|then|implement|create|write|add|run|fix|save|build|start|proceed)\b",
    tail, re.IGNORECASE)

# A legitimate stop that ends by asking the user passes through.
asks_user = re.search(
    r"(\?|shall i|would you like|do you want|let me know|which option)",
    tail, re.IGNORECASE)

if promise and not asks_user:
    seen = _blocks_so_far()
    if seen >= MAX_FINISH_BLOCKS:
        # Cap reached: step aside rather than blocking this session forever.
        sys.exit(0)
    _record_block(seen + 1)
    out = {
        "decision": "block",
        "reason": "Your previous response ended by stating an intent to do work without actually doing it. "
                  "Do that work now with tool calls. End the turn only when the task is complete or you are "
                  "blocked on input that only the user can provide. "
                  f"(Block {seen + 1}/{MAX_FINISH_BLOCKS})"
    }
    print(json.dumps(out, ensure_ascii=False))
sys.exit(0)
PY
