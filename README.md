English | [한국어](README.ko.md)

# fablize — run Opus like Fable

[![GitHub stars](https://img.shields.io/github/stars/fivetaku/fablize?style=flat&color=yellow)](https://github.com/fivetaku/fablize/stargazers)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

A Claude Code plugin that makes Opus (or any Claude model) **see a task through to the end — with evidence and verification — as procedure, not as luck.**

## Why

When Fable 5 shipped, I ran a controlled comparison of Fable 5 and Opus 4.8 (an A/B set of 19 runs plus 26 real working sessions, ~1,500 tool calls). The finding:

- On closed, answer-bearing work (code, logic, builds), the two models were effectively tied.
- The gap appeared only on open-ended work, and its nature was "following an implication one step further."
- That depth is **model capability** — it could not be transferred by instructions or a harness. An injection experiment confirmed it: Opus could not reproduce the defects Fable found on its own.
- But the **procedure** of good work — actually running what you build, seeing it through, investigating systematically — does transfer.

fablize applies only the procedures whose effect was verified. It does not raise the model's ceiling; it makes the model reach its own ceiling.

## What transfers and what doesn't

| Trait | Transferable? | Reason |
|---|:--:|---|
| Verification grounding (run & observe the artifact) | ✅ shipped | A procedure Opus skipped "not because it can't, but because it didn't." Injecting it raised render-verification behavior measurably. |
| Multi-story completion + evidence gate | ✅ shipped | A procedure — decompose, checkpoint, refuse completion without proof. |
| Systematic investigation (reproduce → hypotheses → causal chain) | ✅ shipped | A procedure — on par with what the strong model already does. |
| Early-stop prevention | ✅ shipped | A deterministic hook — catches "I'll do X" without doing it. |
| Out-of-spec defect discovery | ❌ not possible | Capability. Injection was refuted — the model finds it, or it doesn't. |
| Open-ended creative detail | ❌ not possible | Capability. Shows only where there is no fixed answer. |
| Self-driven propagation depth | ❌ not possible | Capability. Directed propagation transfers; self-started depth does not. |

The non-transferable rows are the model's job (or a human's), not a harness's. When you hit them, fablize tells you to escalate instead of pretending.

## What's included (verified only)

- **Verification grounding** — render/executable artifacts (HTML, SVG, games, charts) are run and observed before completion.
- **Multi-story verification gate** — `goals.py` decomposes work and refuses a groundless "done."
- **Investigation protocol** — reproduce, compete hypotheses, trace the full causal chain.
- **Early-stop hook** — blocks promising-without-doing.
- **Per-task router** — injects only the matching verified discipline.

Negligible or unverified ideas (style mimicry, broad reasoning injection, a silent-recovery guard, a review-recall scan) are **not shipped.** They stay in personal development until a controlled experiment confirms their effect.

## Install

```
/plugin marketplace add fivetaku/fablize
/plugin install fablize
```

The per-task router (a UserPromptSubmit hook) registers automatically.

For always-on operation (the rules resident in context), run once:

```
bash ${CLAUDE_PLUGIN_ROOT}/setup/setup.sh    # choose local (recommended) or global
```

Uninstall: `bash ${CLAUDE_PLUGIN_ROOT}/setup/uninstall.sh`

> If fablize helps, a ⭐ on the repo means a lot — setup asks once and can open the page for you.

## How it behaves

- Trigger with `/fablize` or phrases like "see it through", or automatically when installed always-on.
- 2+ stories → decompose + verification gate. Debugging → investigation protocol. Render artifact → verification grounding. Hard task → adaptive thinking plus an `/effort xhigh` suggestion.
- At the capability ceiling, escalate to a stronger model or a human.

## Honest limits

- It cannot raise model capability. Open-ended creative quality and self-driven discovery are out of reach — that is a model-choice decision, not a harness one.
- The effect numbers come from a small, single-family (Claude) self-measurement (the 19-run A/B set). The direction is solid; the decimals are not asserted.
- The early-stop hook can misfire on a declarative offer ("I'll write the report if you want") — phrasing offers as questions avoids it.

## License

MIT
