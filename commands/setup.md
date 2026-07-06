---
description: Set up fablize always-on (inject the operating block into CLAUDE.md).
---

Run the fablize setup. Ask only once, up front.

## Step 1 — Ask whether/where to set up (one question)

Use AskUserQuestion. **Phrase the question and options in the user's current conversation language** (detect it from recent messages).
- **Question (meaning, translate to the user's language):** "Set up fablize?"
- **Options (meaning, translate):**
  1. "Local — this project only (recommended)"
  2. "Global — all projects"
  3. "Cancel"

If the user picks "Cancel", stop and do nothing.

## Step 2 — Run setup

For "Local" or "Global", run setup:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/setup/setup.sh <local|global>
```

`setup.sh` backs up CLAUDE.md, injects the `<!-- FABLIZE -->` block, and writes `~/.fablize/progress.json`. It never stars the repo by itself. Report the result briefly.

## Step 3 — GitHub star (opt-in, asked at most once)

Run:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/setup/setup.sh ask
```

If the output starts with `STAR_ASK`, immediately call the **AskUserQuestion** tool once, with the question and options phrased **in the user's language** (prefer the live conversation's language if it is evident; otherwise fall back to the language code after `STAR_ASK` — `ko`→Korean, `ja`→Japanese, `en`→English. Never default to one language blindly):
- header: a short localized "GitHub Star" label
- question: ask whether they'd like to give fablize a GitHub ⭐ to support it — note it is optional and every feature works either way
- options: exactly two — (1) yes, star it → then run `bash ${CLAUDE_PLUGIN_ROOT}/setup/setup.sh star yes`; (2) no thanks → then run `bash ${CLAUDE_PLUGIN_ROOT}/setup/setup.sh star no`

If the output is empty, continue silently — the question was already asked before. Do not narrate beyond the question itself.
