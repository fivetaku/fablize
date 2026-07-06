#!/usr/bin/env bash
# fablize always-on setup — inject the operating block into CLAUDE.md (idempotent, with backup).
# The UserPromptSubmit router hook is registered automatically by hooks.json on plugin install,
# so this script does NOT touch settings.json (no risk of clobbering existing hooks/settings).
# Usage:
#   setup.sh [global|local]  -> inject the block (no arg = interactive; default local). Never stars.
#   setup.sh ask             -> iff no star decision is on record, atomically record an "asked"
#                               marker AND print "STAR_ASK <lang>". The command/skill flow then
#                               asks via AskUserQuestion (Claude-only; cannot be issued from bash).
#                               Recording the marker HERE guarantees the question is shown at most
#                               once, even if the caller never reports the answer back.
#   setup.sh star yes|no     -> record the decision; star the repo ONLY on an explicit "yes".
# This script never stars the repo without an explicit "star yes" (issue #4).
set -euo pipefail

ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
BLOCK_TPL="$ROOT/setup/fablize-block.md"
REPO="fivetaku/fablize"
REPO_URL="https://github.com/fivetaku/fablize"
CONFIG_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
STATE_DIR="$HOME/.fablize"
STAR_MARKER="$STATE_DIR/star.json"

# --- detect a fallback UI language from past Claude session transcripts (best-effort) ---
# Counts Hangul / Kana / Latin letters in HUMAN-typed user text only (skips tool results,
# assistant turns and JSON structure, which are ASCII-heavy and would skew to English).
detect_lang() {
  command -v python3 >/dev/null 2>&1 || { echo en; return; }
  python3 - "$CONFIG_DIR/projects" 2>/dev/null <<'PY' || echo en
import sys, os, glob, json
base = sys.argv[1]
try:
    files = sorted(glob.glob(os.path.join(base, "**", "*.jsonl"), recursive=True),
                   key=os.path.getmtime, reverse=True)[:20]
except Exception:
    files = []
# Vote per message (presence of script), not per char — so a few large ASCII
# pastes (code, logs, specs) don't drown out many short typed Korean turns.
ko = ja = en = 0
msgs = 0
def vote(s):
    global ko, ja, en, msgs
    hk = hj = hl = False
    for ch in s:
        o = ord(ch)
        if 0xAC00 <= o <= 0xD7A3: hk = True
        elif 0x3040 <= o <= 0x30FF: hj = True
        elif 65 <= o <= 90 or 97 <= o <= 122: hl = True
    if hk: ko += 1
    elif hj: ja += 1
    elif hl: en += 1
    if hk or hj or hl: msgs += 1
for f in files:
    if msgs >= 400: break
    try:
        fh = open(f, encoding="utf-8", errors="ignore")
    except Exception:
        continue
    for line in fh:
        if msgs >= 400: break
        try:
            m = json.loads(line).get("message")
        except Exception:
            continue
        if not isinstance(m, dict) or m.get("role") != "user":
            continue
        c = m.get("content")
        if isinstance(c, str):
            vote(c)
        elif isinstance(c, list):
            for part in c:
                if isinstance(part, dict) and part.get("type") == "text":
                    vote(part.get("text", ""))
    fh.close()
if ko and ko >= ja and ko >= en: print("ko")
elif ja and ja >= ko and ja >= en: print("ja")
else: print("en")
PY
}

# --- record the star decision (and star the repo on an explicit "yes") ---
write_star() {  # $1 = decision (yes|no|asked)
  mkdir -p "$STATE_DIR"
  ts=$(date +%s 2>/dev/null || echo 0)
  printf '{"star_decision":"%s","ts":%s}\n' "$1" "$ts" > "$STAR_MARKER"
}

if [ "${1:-}" = "star" ]; then
  DECISION="${2:-no}"
  write_star "$DECISION"
  if [ "$DECISION" = "yes" ] && command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
    gh api "user/starred/$REPO" >/dev/null 2>&1 \
      || gh api -X PUT "user/starred/$REPO" >/dev/null 2>&1 || true
  fi
  exit 0
fi

# ask mode: emit the star prompt EXACTLY ONCE, recording it deterministically in bash.
if [ "${1:-}" = "ask" ]; then
  if [ ! -f "$STAR_MARKER" ]; then
    write_star "asked"
    echo "STAR_ASK $(detect_lang)"
  fi
  exit 0
fi

command -v python3 >/dev/null 2>&1 || { echo "fablize: python3 is required."; exit 1; }
[ -f "$BLOCK_TPL" ] || { echo "fablize: block template not found ($BLOCK_TPL)"; exit 1; }

scope="${1:-}"
if [ -z "$scope" ]; then
  printf "fablize — inject the operating block into: [l]ocal (this project, recommended) / [g]lobal (all projects): "
  read -r ans
  case "$ans" in g*|G*) scope=global;; l*|L*|"") scope=local;; *) echo "cancelled"; exit 1;; esac
fi
case "$scope" in
  global) CLAUDE_MD="$HOME/.claude/CLAUDE.md";;
  local)  CLAUDE_MD="$PWD/CLAUDE.md";;
  *) echo "fablize: scope must be global or local"; exit 1;;
esac
echo "fablize → $scope ($CLAUDE_MD)"

mkdir -p "$(dirname "$CLAUDE_MD")"; touch "$CLAUDE_MD"
ts=$(python3 -c "import time;print(int(time.time()))")
cp "$CLAUDE_MD" "$CLAUDE_MD.fablize-bak.$ts" && echo "  backup: $CLAUDE_MD.fablize-bak.$ts"

# Substitute __PLUGIN_ROOT__ -> real path, then inject idempotently (remove old markers, re-insert).
python3 - "$CLAUDE_MD" "$BLOCK_TPL" "$ROOT" <<'PY'
import sys, re, pathlib
md, tpl, root = sys.argv[1], sys.argv[2], sys.argv[3]
p = pathlib.Path(md)
cur = p.read_text(encoding="utf-8") if p.exists() else ""
block = pathlib.Path(tpl).read_text(encoding="utf-8").strip().replace("__PLUGIN_ROOT__", root)
cur = re.sub(r"<!-- FABLIZE:BEGIN.*?FABLIZE:END -->\n?", "", cur, flags=re.S).rstrip()
p.write_text((cur + "\n\n" + block + "\n") if cur else (block + "\n"), encoding="utf-8")
print("  ✓ CLAUDE.md: FABLIZE operating block injected (idempotent)")
PY

# Record setup state so the skill won't auto-run setup again.
mkdir -p "$STATE_DIR"
python3 - "$scope" "$ts" <<'PY'
import json, sys, os
p = os.path.expanduser("~/.fablize/progress.json")
json.dump({"setup_done": True, "scope": sys.argv[1], "version": "2.1.1", "ts": int(sys.argv[2])}, open(p, "w"))
PY

echo "fablize setup complete ($scope) — applies from the next session."
echo "  state: ~/.fablize/progress.json"
echo "  Uninstall: bash $ROOT/setup/uninstall.sh $scope"
echo "  Note: the router hook is auto-registered on plugin install. The early-stop hook (finish-the-work)"
echo "        is often already registered globally — register $ROOT/hooks/finish-the-work.sh as a Stop hook"
echo "        only if it is not (avoid duplicates)."
