#!/usr/bin/env bash
# fablize — star the repo on GitHub via gh. Consent is obtained by the setup prompt that calls this
# ("Set up fablize? ... and stars the repo"), so this does not ask again.
# Fail-silent: never blocks. Skips if already starred or gh is unavailable.
set -uo pipefail
REPO="fivetaku/fablize"

if gh auth status &>/dev/null; then
  if gh api "user/starred/$REPO" &>/dev/null; then
    echo "★ fablize already starred — thank you!"
  # NOTE: the endpoint must NOT have a leading slash. On Git Bash (MSYS) a
  # leading "/user/..." is rewritten to a Windows filesystem path
  # (C:/Program Files/Git/user/...) and the request fails. Keep it slash-less
  # and surface the real error instead of swallowing it with &>/dev/null.
  elif star_err=$(gh api -X PUT "user/starred/$REPO" 2>&1); then
    echo "★ Starred fablize on GitHub — thank you!"
  else
    echo "Could not star automatically ($star_err) — star here: https://github.com/$REPO"
  fi
else
  echo "Sign in to gh (\`gh auth login\`) to auto-star next time, or star here: https://github.com/$REPO"
fi
exit 0
