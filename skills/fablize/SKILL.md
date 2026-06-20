---
name: fablize
description: A harness that makes Opus (or any Claude model) behave like Fable — it enforces seeing a task through to the end, with evidence and verification, as procedure. Use when starting a multi-step task (2+ sequential stories), long autonomous work, debugging or root-cause investigation, building render/executable artifacts (HTML, SVG, games, charts), or when the user says "fablize", "see it through", "verify as you go", "split into goals".
---

# fablize — run Opus like Fable

> Principle: a harness cannot raise a model's ceiling. It makes the model go all the way to its own ceiling — by enforcing verification, completion, and investigation as procedure. When the capability ceiling is the blocker (open-ended creative detail, self-driven discovery), escalate (§4).
>
> Apply only what the task signals (smallest matching discipline; overlap only when genuinely multi-category). When installed always-on, this routing is automatic.

## 0. First run — set up automatically (once)

Before doing the requested task, check whether fablize has been onboarded on this machine:

```bash
cat ~/.fablize/progress.json 2>/dev/null
```

- If the file **exists** — skip onboarding, go straight to the task.
- If it is **missing** — onboard once with a single AskUserQuestion. **Phrase the question and options in the user's current conversation language** (detect it from recent messages — Korean, English, Japanese, etc.).
  - **Question (meaning, translate to the user's language):** "Set up fablize? (Note: setup will star this repo on GitHub using your `gh` credentials as a thank-you. You can skip the star by choosing Skip-star below.)"
  - **Options (meaning, translate):** "Local — this project only (recommended)" / "Global — all projects" / "Local, no star" / "Skip".
  - On **Local** — run setup with starring:
    ```bash
    bash ${CLAUDE_PLUGIN_ROOT}/setup/setup.sh local
    ```
  - On **Global** — run setup with starring:
    ```bash
    bash ${CLAUDE_PLUGIN_ROOT}/setup/setup.sh global
    ```
  - On **Local, no star** — run setup without starring:
    ```bash
    bash ${CLAUDE_PLUGIN_ROOT}/setup/setup.sh local --no-star
    ```
  - On **Skip** — record it so it won't ask again, then continue:
    ```bash
    mkdir -p ~/.fablize && printf '{"setup_done":false,"skipped":true}' > ~/.fablize/progress.json
    ```

Also detect if the user invoked with `--no-star` (or phrases like "without starring", "skip the star", "no star") — if so, always pass `--no-star` to `setup.sh` regardless of which scope option they pick.

This means the user can just run `/fablize` (or trigger it) without running setup first — the first run onboards itself, once, with one question.

## 1. Multi-story loop (2+ sequential stories)

Decompose into sequential stories and complete one at a time, producing evidence as you go. Self-contained — no external goal system required. Run from the repo root; state persists in `./.fablize/` (resume with `status` even across sessions).

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/goals.py create --brief "<summary>" \
  --goal "title::verifiable objective" --goal "title::..."   # the last goal must be a verification story
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/goals.py next         # activate a story + handoff
# ... work that story only ...
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/goals.py checkpoint --id G001 --status complete --evidence "<concrete evidence>"
# the final story is a verification gate: --verify-cmd "<command>" --verify-evidence "<result>" are required
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/goals.py status       # first command when resuming
```

Rules: `complete` requires non-empty evidence; the final goal cannot complete without a verify command and its result (the engine refuses). If blocked, record `--status blocked` and report. Single-step tasks skip this loop.

## 2. Deep investigation (debugging / unknown cause / review)

Read and follow `${CLAUDE_PLUGIN_ROOT}/packs/investigation-protocol.txt`: reproduce first → form 3+ competing hypotheses → gather evidence per hypothesis → trace the full causal chain (removing the symptom is not removing the defect) → verify before and after → report the hypotheses you rejected. For reviews, report everything including low-confidence findings and filter in a separate step.

## 3. Verification grounding (render/executable artifacts — always)

For artifacts whose correctness only shows when run (HTML, SVG, games, UI, charts), follow `${CLAUDE_PLUGIN_ROOT}/packs/verification-grounding-pack.txt`: run it in the real renderer → observe the actual output → fix what the observation reveals → re-run. A static parse confirms well-formed, not correct.

## 3-1. Working style (always)

Lead with the outcome. Stay within the requested scope (no incidental refactors or abstractions). Ground every completion claim in a tool result from this session. Confirm before destructive or hard-to-reverse actions.

## 4. At the capability ceiling (escalate)

Signals you have hit the model's ceiling: stuck on the same problem 2+ times; open-ended creation where detail itself is the value; deep review that needs out-of-spec discovery. These are capability, not procedure, and a harness cannot fill them. In order: (1) adaptive thinking already scales with difficulty — recommend `/effort xhigh` to the user to push the current model to its ceiling; (2) **reactive effort delegation** — if the blocker is a bounded, hard *slice* (not the whole task), delegate just that slice to a background Workflow with `effort:'max'` (model inherited): package the evidence (symptoms, attempts, failure point, repro, the specific sub-question) as the `agent()` prompt, force a structured return via `schema`, then resume with its result as authoritative. This is the only real per-task effort knob in a normal session — the Agent tool exposes `model` but no `effort`; only Workflow/Agent SDK do. **Opt-in, and not yet proven on real work** (the shadow layer in `docs/MEASUREMENT_PROTOCOL.md` measures whether it helps): use it for a genuinely stuck slice, not routinely, and **never trigger it from risk/deep classification alone** — that over-escalates simple high-risk tasks (false-escalate); (3) if still short, hand off to a stronger model in a fresh session with the same evidence package; (4) otherwise report the limit honestly and name where a human must step in.

## Install (always-on, optional)

Run once: `bash ${CLAUDE_PLUGIN_ROOT}/setup/setup.sh` → choose local (recommended) or global. Uninstall: `bash ${CLAUDE_PLUGIN_ROOT}/setup/uninstall.sh`. The UserPromptSubmit router hook registers automatically when the plugin is installed.
