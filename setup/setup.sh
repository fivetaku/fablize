#!/usr/bin/env bash
# fablize always-on setup — inject the operating block into CLAUDE.md (idempotent, with backup).
# The UserPromptSubmit router hook is registered automatically by hooks.json on plugin install,
# so this script does NOT touch settings.json (no risk of clobbering existing hooks/settings).
# Usage: setup.sh [global|local]   (no arg = interactive; default local)
set -euo pipefail

ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
BLOCK_TPL="$ROOT/setup/fablize-block.md"
REPO_URL="https://github.com/fivetaku/fablize"

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
mkdir -p "$HOME/.fablize"
python3 - "$scope" "$ts" <<'PY'
import json, sys, os
p = os.path.expanduser("~/.fablize/progress.json")
json.dump({"setup_done": True, "scope": sys.argv[1], "version": "2.0.0", "ts": int(sys.argv[2])}, open(p, "w"))
PY

echo "fablize setup complete ($scope) — applies from the next session."
echo "  state: ~/.fablize/progress.json"
echo "  Uninstall: bash $ROOT/setup/uninstall.sh $scope"
echo "  Note: the router hook is auto-registered on plugin install. The early-stop hook (finish-the-work)"
echo "        is often already registered globally — register $ROOT/hooks/finish-the-work.sh as a Stop hook"
echo "        only if it is not (avoid duplicates)."

# Star the repo (consent was given by the setup prompt's ⭐). Deterministic — not left to the caller.
bash "$ROOT/setup/star.sh" || true
