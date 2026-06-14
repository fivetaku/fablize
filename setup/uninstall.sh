#!/usr/bin/env bash
# fablize uninstall — remove the FABLIZE block from CLAUDE.md (idempotent).
# The router hook is removed automatically when the plugin is uninstalled.
# Usage: uninstall.sh [global|local]
set -euo pipefail

scope="${1:-}"
if [ -z "$scope" ]; then
  printf "fablize — remove the operating block from: [l]ocal / [g]lobal: "
  read -r ans
  case "$ans" in g*|G*) scope=global;; *) scope=local;; esac
fi
case "$scope" in
  global) CLAUDE_MD="$HOME/.claude/CLAUDE.md";;
  local)  CLAUDE_MD="$PWD/CLAUDE.md";;
  *) echo "fablize: scope must be global or local"; exit 1;;
esac
[ -f "$CLAUDE_MD" ] || { echo "fablize: $CLAUDE_MD not found — nothing to remove."; exit 0; }

python3 - "$CLAUDE_MD" <<'PY'
import sys, re, pathlib
p = pathlib.Path(sys.argv[1])
cur = p.read_text(encoding="utf-8")
new = re.sub(r"\n*<!-- FABLIZE:BEGIN.*?FABLIZE:END -->\n?", "\n", cur, flags=re.S)
p.write_text(new, encoding="utf-8")
print("  ✓ FABLIZE block removed" if new != cur else "  = no FABLIZE block (already removed)")
PY

echo "fablize uninstall complete ($scope). The router hook is removed when you /plugin uninstall."
echo "  Backups ($CLAUDE_MD.fablize-bak.*) can be deleted manually if no longer needed."
