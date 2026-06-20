---
description: Set up fablize always-on (inject the operating block into CLAUDE.md).
---

Run the fablize setup. Ask only once, up front.

## Detecting --no-star

Before doing anything, check whether the user passed `--no-star` (or equivalent phrases such as "without starring", "skip the star", "don't star", "no star"). If so, set `NO_STAR=true` and pass `--no-star` to `setup.sh` in Step 2.

## Step 1 — Ask whether/where to set up (one question)

Use AskUserQuestion. **Phrase the question and options in the user's current conversation language** (detect it from recent messages).

- **Question (meaning, translate to the user's language):** "Set up fablize? (Note: setup will star this repo on GitHub using your `gh` credentials as a thank-you. Pass `--no-star` to skip.)"
- **Options (meaning, translate):**
  1. "Local — this project only (recommended)"
  2. "Global — all projects"
  3. "Cancel"

If the user picks "Cancel", stop and do nothing.

## Step 2 — Run setup (no second prompt)

The user already consented in Step 1. For "Local" or "Global", run setup:

```bash
# With star (default):
bash ${CLAUDE_PLUGIN_ROOT}/setup/setup.sh <local|global>

# Without star (if --no-star was detected in the command or the user said so):
bash ${CLAUDE_PLUGIN_ROOT}/setup/setup.sh <local|global> --no-star
```

`setup.sh` backs up CLAUDE.md, injects the `<!-- FABLIZE -->` block, writes `~/.fablize/progress.json`, and (unless `--no-star`) stars the repo via `gh` (skips if already starred or gh is not signed in; never blocks). Report the result briefly.
