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
# Reject paths outside TMPDIR or HOME to block path-traversal via crafted hook input.
case "$tpath" in
    "${TMPDIR:-/tmp}"/* | "$HOME"/*) ;;
    *) exit 0 ;;
esac

# Extract the last assistant message's text, whether it ended with a tool call,
# and whether the recent transcript shows an async Agent still running.
python3 - "$tpath" <<'PY'
import sys, json, re

path = sys.argv[1]
records = []
last_text = ""
last_had_tool = False


def content_blocks(msg):
    content = msg.get("content", []) if isinstance(msg, dict) else []
    if isinstance(content, list):
        return [b for b in content if isinstance(b, dict)]
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return []


def text_from(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(text_from(v) for v in value)
    if isinstance(value, dict):
        parts = []
        for key in ("text", "content", "message"):
            if key in value:
                parts.append(text_from(value[key]))
        return "\n".join(p for p in parts if p)
    return ""


ASYNC_AGENT_LAUNCH = re.compile(
    r"\b(async\s+agent\s+launched|agent\s+task\s+launched|launched\s+in\s+background|running\s+in\s+background)\b",
    re.IGNORECASE,
)
AGENT_COMPLETE = re.compile(
    r"(\b(agent|background agent|async agent)\b.{0,120}\b(completed|finished|done|returned|reported|report back|results? (are|is )?ready)\b)"
    r"|(\b(completed|finished|returned)\b.{0,120}\b(agent|background agent|async agent)\b)"
    r"|(에이전트.{0,80}(완료|끝|보고|결과|도착))"
    r"|((완료|도착).{0,80}에이전트)",
    re.IGNORECASE,
)


def has_inflight_background_agent(items):
    agent_tool_ids = set()
    in_flight = set()
    unknown_launches = 0

    for obj in items:
        msg = obj.get("message", obj) if isinstance(obj, dict) else {}
        blocks = content_blocks(msg)
        for block in blocks:
            btype = block.get("type")
            if btype == "tool_use" and block.get("name") == "Agent":
                tool_id = block.get("id")
                if tool_id:
                    agent_tool_ids.add(tool_id)
                continue

            text = text_from(block)
            if btype == "tool_result":
                tool_use_id = block.get("tool_use_id")
                is_agent_result = bool(tool_use_id and tool_use_id in agent_tool_ids)
                is_async_launch = bool(ASYNC_AGENT_LAUNCH.search(text))
                if is_agent_result and is_async_launch:
                    in_flight.add(tool_use_id)
                    continue
                if is_async_launch:
                    # Be defensive about transcript variants that omit tool_use_id.
                    unknown_launches += 1
                    in_flight.add(f"unknown:{unknown_launches}")
                    continue
                if tool_use_id and tool_use_id in in_flight and AGENT_COMPLETE.search(text):
                    in_flight.discard(tool_use_id)
                    continue

            # Completion notifications are separate transcript messages in some
            # clients. If one appears after a launch, the turn is no longer a
            # valid wait/yield state for finish-the-work.
            if in_flight and text and not ASYNC_AGENT_LAUNCH.search(text) and AGENT_COMPLETE.search(text):
                in_flight.clear()

    return bool(in_flight)


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
            records.append(obj)
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

# Waiting for an already-launched background Agent is a legitimate yield point,
# not an unfulfilled promise to do work in this turn.
if has_inflight_background_agent(records):
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
