# CLAUDE.md — ReleaseGuard

> Release-readiness agent — fuses heterogeneous quality signals (test results, coverage, flakiness) into a single, explainable go/no-go recommendation.
> Portfolio project P5 of a 6-project AI Test Engineering portfolio.

## Project State — READ FIRST

- **Status: ✅ S1 delivered (2026-07-10) — next: S2, parsers + scoring engine.**
- S1: ADR-001 accepted (hard gates + weighted score), Pydantic v2 models, policy constants module, three canonical scenario fixtures (GO / NO GO / CONDITIONAL), 39 contract tests, zero-key CI.
- Work discipline: **small, session-scoped increments** — one concern per session, plan validated before code, feature branch + PR to `main`.

## Project Goal

Answer one question a release manager asks daily: **"can we ship this build?"** — with evidence, not gut feeling.

- **Signal ingestion**: parse standard CI artifacts — JUnit XML (test results), Cobertura XML (coverage), FlakySense JSON report (flakiness).
- **Signal fusion**: hard gates + weighted scoring produce a verdict: `GO` / `CONDITIONAL GO` / `NO GO`, with per-signal breakdown.
- **Explainable output**: every verdict carries its rationale — which gate tripped, which signal dragged the score, what conditions apply.

Differentiating skills vs P1–P4: **heterogeneous signal fusion and decision-making under gates** (P4 was sequential agent orchestration on a single stream). Soft interop with P4: a FlakySense report is just one input signal — no runtime coupling between repos.

## Deliberate scope cuts (quality over quantity)

- **No Docker.** P4 already demonstrates container packaging (ADR-007); repeating it adds nothing. P5's deployment story is the **dogfood CI gate**: this repo's own CI runs ReleaseGuard on its own test/coverage artifacts and publishes the verdict in the job summary.
- **No multi-agent pipeline.** One evaluator with a System 1 (deterministic gates + weighted score) and an optional System 2 (LLM-narrated rationale for CONDITIONAL verdicts). Same env-gated LLM pattern as FlakySense ADR-004.
- **Three parsers only** (JUnit, Cobertura, FlakySense JSON). New signal types are an extension point, not v1 scope.

## Sprint Plan (2 simulated weeks, 3 sessions)

- **S1 — Architecture**: CLAUDE.md, scaffold, ADR-001 (gate model), Pydantic v2 models, sample fixtures (3 release scenarios), contract tests.
- **S2 — Implementation**: the three parsers, scoring engine + gates, env-gated LLM narrative layer.
- **S3 — Integration**: CLI (`releaseguard`, verdict-mapped exit codes), dogfood CI gate, senior README, bug-evidence log.

## Architecture Principles (non-negotiable, portfolio-wide)

1. **Deterministic fallback on every AI component.** Full test suite and CI run green with **zero API keys**. LLM calls are an enhancement layer.
2. **Pydantic v2** for all data models.
3. **ADRs in `docs/adr/`** are first-class deliverables. Superseded, never edited retroactively.
4. **Bugs found by tests = portfolio evidence.** Document (what the test caught, why it mattered) before fixing.
5. **Free/open-source only.** Solo-buildable. No paid services, no enterprise access.

## Environment

- OS: Windows 11, shell: PowerShell
- Python 3.14, virtualenv in `.venv` — activate: `.\.venv\Scripts\Activate.ps1`
- Run tests with: `python -m pytest` — **NEVER** bare `pytest`
- CI: GitHub Actions (free tier), zero API keys, no Docker
- Console output ASCII-only (legacy Windows consoles garble non-ASCII); verify CLI pipe behavior through Git Bash, not PowerShell 5.1

## Conventions

- Codebase, comments, README, ADRs: **professional English** (Swiss/international market). Conversation with the user: French.
- Commits: small, atomic, imperative English (`feat: …`, `test: …`, `docs: adr-002 …`).
- Branch workflow: never commit to `main` directly. Each session works on a feature branch (`feat/…`, `docs/…`, `fix/…`) keeping its atomic commits, then opens a GitHub PR to `main`. No "Generated with Claude Code" footer in PR bodies.
- Targeted changes only. The user runs everything locally and pastes exact errors — fix precisely, never rewrite broadly.
- Never scan `.venv/` or generated report folders (token waste).

## Definition of Done (per component)

- [ ] Pydantic v2 models with validation
- [ ] Deterministic behavior implemented and tested (LLM strictly optional)
- [ ] Unit tests green via `python -m pytest`
- [ ] Docstrings + entry in README architecture section
- [ ] ADR updated/added if a design decision was made
