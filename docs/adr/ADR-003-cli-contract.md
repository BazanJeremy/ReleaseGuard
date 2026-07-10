# ADR-003: CLI contract — verdict-mapped exit codes, ASCII output, threshold flags only

- **Status:** Accepted
- **Date:** 2026-07-10
- **Deciders:** Jérémy Bazan

## Context

S3 exposes the gate as a command line usable in any CI. Most of the contract was already fixed by ADR-001 (exit codes 0 GO / 1 CONDITIONAL GO / 2 NO GO / 3 error; thresholds exposed as flags); this ADR settles the remaining surface and one deliberate narrowing.

## Decision

- **stdlib `argparse`, no CLI framework** — same reasoning as FlakySense ADR-006: zero dependencies for a four-flag surface.
- **`--junit` required; `--coverage` and `--flaky` optional** — mirrors ADR-001 signal optionality exactly.
- **Usage errors exit 3, not argparse's default 2.** argparse exits 2 on a bad flag; 2 means NO GO here. A CI script would read a typo as a blocked release. The parser is overridden so *every* non-verdict outcome is 3.
- **Threshold flags only; weights are not tunable** (`--coverage-floor`, `--coverage-target`, `--go-threshold`, `--flaky-penalty`). This narrows ADR-001's "S3 exposes them as CLI flags": thresholds are per-run risk appetite, but the signal weighting *is* the gate's identity — changing it should be a governance decision recorded in a superseding ADR, not a pipeline flag someone tweaks to get green.
- **ASCII-only text output**; `--json` emits the full `ReleaseRecommendation` (lossless round-trip, pinned by test).
- Both `releaseguard` (console script) and `python -m releaseguard` work.

## Options Considered

1. **argparse + verdict-mapped exit codes + threshold-only flags** — **Accepted.**
2. Click/Typer — nicer help output, one more dependency for four flags. Rejected.
3. Exposing weight flags too — literal reading of ADR-001, but lets any pipeline redefine what "release ready" means ad hoc. Rejected; documented as a narrowing.

## Consequences

- Any CI can gate on the exit code: `releaseguard ... || test $? -le 1` ships conditionals, blocks NO GO. This repo's own CI does exactly that (dogfood gate).
- The exit-code collision fix is pinned by a test (`test_usage_error_exits_3_not_argparses_2`).
- Weight changes now have a named, deliberate cost (a superseding ADR) — the audit trail survives.
