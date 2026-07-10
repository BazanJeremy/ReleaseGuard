"""Gate-model constants — the single source for every ADR-001 number.

The evaluator (S2) and the CLI defaults (S3) import from here; nothing else
in the codebase may hard-code a threshold. Rationale for each value lives in
docs/adr/ADR-001-release-gate-model.md.
"""

# Layer 2 — weighted score (weights must sum to 1.0)
WEIGHT_TESTS = 0.50
WEIGHT_COVERAGE = 0.25
WEIGHT_FLAKINESS = 0.25

# Gate G2 and coverage normalization: 60% => 0.0, 85% => 1.0, clamped
COVERAGE_FLOOR = 0.60
COVERAGE_TARGET = 0.85

# Verdict split: score >= threshold => GO, below => CONDITIONAL GO
GO_THRESHOLD = 0.80

# Flakiness normalization: max(0, 1 - FLAKY_PENALTY * flaky_ratio)
# => 20% flaky tests zeroes the signal
FLAKY_PENALTY = 5.0
