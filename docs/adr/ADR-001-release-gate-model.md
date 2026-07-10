# ADR-001: Release gate model — hard gates + weighted score

- **Status:** Accepted
- **Date:** 2026-07-10
- **Deciders:** Jérémy Bazan

## Context

ReleaseGuard must fuse three heterogeneous signals (test results, coverage, flakiness) into one verdict: `GO` / `CONDITIONAL GO` / `NO GO`. The naive approach — a weighted average of normalized signals — is a known anti-pattern for release gates: excellent coverage can arithmetically mask a failing smoke test. A release verdict needs a structure where **blockers cannot be compensated**.

## Decision

Two-layer decision model: **hard gates first, weighted score second**.

### Layer 1 — Hard gates (any trip ⇒ `NO GO`)

| Gate | Condition |
|------|-----------|
| G1 — real failure | ≥ 1 failing test **not** identified as flaky by the flakiness signal |
| G2 — coverage floor | line coverage < **60%** |

**Cross-signal rule:** a failing test that *is* in the flaky list does **not** trip G1. It degrades the flakiness signal instead, and caps the final verdict at `CONDITIONAL GO` — the failure is excused, but named as a condition. This is the core signal-fusion behavior: no single parser can produce this decision alone.

### Layer 2 — Weighted score (only if no gate trips)

`score = 0.50 · tests + 0.25 · coverage + 0.25 · flakiness`, each signal normalized to [0, 1]:

- **tests** — pass rate, flaky-excused failures excluded from the failure count
- **coverage** — linear ramp: 60% ⇒ 0.0, 85% ⇒ 1.0, clamped
- **flakiness** — `max(0, 1 − 5 · flaky_ratio)`: 0% flaky ⇒ 1.0, ≥ 20% flaky ⇒ 0.0

Verdict: `score ≥ 0.80` ⇒ `GO`; otherwise `CONDITIONAL GO` with a machine-generated conditions list.

**`NO GO` requires an identifiable blocker.** Below the gates, the score can only choose between `GO` and `CONDITIONAL GO` — a low score without a named blocker is a conditional ship with listed risks, not a veto.

### Missing signals

- JUnit report **mandatory** — no test evidence, no verdict (error, not `NO GO`).
- Coverage and flakiness reports **optional** — remaining weights renormalize proportionally, G1 treats all failures as real when the flaky signal is absent, and the missing signal is auto-appended to the conditions list.

### System 1 / System 2 split

- System 1 (deterministic): gates, score, verdict, template-based rationale. Always available, zero API keys.
- System 2 (LLM, env-gated per the FlakySense ADR-004 pattern): narrates rationale and conditions **only for `CONDITIONAL GO`** — the gray zone where nuance helps. `GO` and `NO GO` rationales stay System 1 always: a hard verdict must never depend on LLM availability.

### Output contract

`ReleaseRecommendation { verdict, score, gates[], signals[], conditions[], rationale, generated_by }`.
CLI exit codes (S3): `0` GO · `1` CONDITIONAL GO · `2` NO GO · `3` error.

## Options Considered

1. **Pure weighted average** — simple, but averaging compensates blockers; a release gate must not trade a failing test against coverage points. Rejected.
2. **Hard gates + weighted score** — blockers veto, score grades the rest; auditable per-signal breakdown. **Accepted.**
3. **ML-learned weights** — no training data at portfolio scale, opaque to a release manager, unmaintainable solo. Rejected.

## Consequences

- Deterministic and auditable: every verdict reproducible from artifacts alone; per-signal and per-gate breakdown in the output.
- Thresholds (weights 0.50/0.25/0.25, floor 60%, target 85%, GO ≥ 0.80, ×5 flaky penalty) are opinionated defaults documented here; S3 exposes them as CLI flags but the defaults are the reference.
- The flaky-excuse rule inherits the flaky report's quality: a wrong flaky classification wrongly excuses a real failure. Mitigation: excused failures are always listed by name in `conditions[]` — visible, never silent.
- Follow-up: the CONDITIONAL GO threshold band may need tuning once fixtures exist (S1 contract tests will pin the three canonical scenarios).
