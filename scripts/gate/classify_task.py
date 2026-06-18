#!/usr/bin/env python3
"""Task-mode classification for the fablize observation gate (bilingual KO/EN).

Trimmed port of fable-ish: only prompt classification (quick / normal / deep)
and the per-mode context nudge are kept. Danger/secret command blocking is the
host harness's job (e.g. block_dangerous.py), so it is intentionally dropped.
"""

from __future__ import annotations

import re


QUICK_RE = re.compile(
    r"(?i)\b(quick|brief|briefly|simple|simply|just explain|explain only|review only|direction|"
    r"check only|no edits|do not edit)\b|간단히|빠르게|설명만|검토만|방향|확인만"
)
DEEP_RE = re.compile(
    r"(?i)\b(deep|thorough|thoroughly|exhaustive|end-to-end|production-ready|deploy|deployment|"
    r"migration|database|auth|security|refactor|large|complex|implement the plan)\b|"
    r"끝까지|철저|전부|전체|배포|마이그레이션|인증|보안|리팩터"
)
NORMAL_RE = re.compile(
    r"(?i)\b(implement|fix|debug|change|edit|create|build|test|lint|review|update)\b|"
    r"구현|수정|고쳐|디버그|작성|생성|테스트|검증"
)


def classify_prompt(prompt: str) -> tuple[str, list[str]]:
    text = prompt or ""
    lowered = text.lower()
    risks: list[str] = []
    if "production" in lowered or "배포" in text:
        risks.append("production")
    if re.search(r"(?i)\b(db|database|migration|migrate|schema)\b|데이터베이스|마이그레이션", text):
        risks.append("database")
    if re.search(r"(?i)\b(auth|secret|token|api[_ -]?key|password)\b|인증|비밀|토큰", text):
        risks.append("secret-or-auth")
    if re.search(r"(?i)\b(git\s+push|release|publish)\b|릴리즈|배포", text):
        risks.append("remote-write")

    if DEEP_RE.search(text) or any(flag in risks for flag in ("production", "database", "remote-write")):
        return "deep", risks
    if QUICK_RE.search(text) and not risks:
        return "quick", risks
    if NORMAL_RE.search(text):
        return "normal", risks
    return "quick", risks


def context_for_mode(mode: str, risk_flags: list[str]) -> str:
    lines = [f"fablize gate — task mode: {mode}."]
    if risk_flags:
        lines.append("Risk flags: " + ", ".join(risk_flags) + ".")
    if mode == "quick":
        lines.append("Keep it concise; no forced verification.")
    elif mode == "normal":
        lines.append("If files change, run one relevant verification command or state why none applies.")
    elif mode == "deep":
        lines.append(
            "Define the exit proof before completion and verify changed behavior before final. "
            "If you verified a change or your claims rest on tool results, state the evidence "
            "(and any gaps) in one line; if nothing changed and there is nothing to verify, "
            "skip the verification note."
        )
    lines.append("Never claim verification that was not actually observed in a tool result.")
    return "\n".join(lines[:10])
