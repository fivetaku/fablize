#!/bin/bash
# finish-the-work.sh — Stop hook
# Detects early termination where the agent only PROMISES work without doing it, and re-engages it.
# Deterministic (regex). Infinite loops are guarded by stop_hook_active.
# stdin: JSON { transcript_path, stop_hook_active, ... }
# stdout: {"decision":"block","reason":"..."} to continue, otherwise empty (exit 0)

set -e
input=$(cat)

# Loop guard: if this hook already forced one continuation, do not block again.
active=$(printf '%s' "$input" | python3 -c "import sys,json; print(json.load(sys.stdin).get('stop_hook_active', False))" 2>/dev/null || echo "False")
if [ "$active" = "True" ]; then exit 0; fi

tpath=$(printf '%s' "$input" | python3 -c "import sys,json; print(json.load(sys.stdin).get('transcript_path',''))" 2>/dev/null || echo "")
if [ -z "$tpath" ] || [ ! -f "$tpath" ]; then exit 0; fi

# Extract the last assistant message's text and whether it ended with a tool call.
python3 - "$tpath" <<'PY'
import sys, json, re

path = sys.argv[1]
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
    out = {
        "decision": "block",
        "reason": "Your previous response ended by stating an intent to do work without actually doing it. "
                  "Do that work now with tool calls. End the turn only when the task is complete or you are "
                  "blocked on input that only the user can provide."
    }
    print(json.dumps(out, ensure_ascii=False))
sys.exit(0)
PY
